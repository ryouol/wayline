"""FastAPI surface for the authenticated 3D scene workspace."""

import argparse
import hmac
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi import (
    Path as ApiPath,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .database import InvalidTransition, QuotaExceeded, token_digest
from .engines import EngineUnavailable
from .service import UploadRejected, WorkspaceService

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_COOKIE = "scene_workspace_session"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=16, max_length=512)


class ResearchJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assetId: str = Field(pattern=r"^ast_[0-9a-f]{32}$")
    extractFps: int = Field(default=3, ge=1, le=15)
    maxFrames: int = Field(default=120, ge=30, le=9_000)
    rotate: bool = False
    maskSky: bool = False
    memoryGuard: bool = True
    mode: Literal["streaming", "windowed"] = "streaming"


class ShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ttlSeconds: int = Field(default=86_400, ge=300, le=7 * 86_400)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class UserResponse(BaseModel):
    displayName: str
    tenantName: str


class LoginResponse(BaseModel):
    csrfToken: str
    user: UserResponse


class QuotaResponse(BaseModel):
    quota_units: int
    reserved_units: int
    consumed_units: int
    available_units: int


class MeResponse(BaseModel):
    user: UserResponse
    csrfToken: str | None
    quota: QuotaResponse


class EngineResponse(BaseModel):
    id: str
    name: str
    available: bool
    researchOnly: bool
    commerciallyCleared: bool
    unavailableReasons: list[str]


class EnginesResponse(BaseModel):
    engines: list[EngineResponse]


class AssetResponse(BaseModel):
    id: str
    name: str
    mediaType: str
    sizeBytes: int
    sha256: str
    metadata: dict[str, Any]
    createdAt: float


class ArtifactResponse(BaseModel):
    id: str
    kind: str
    filename: str
    mediaType: str
    sizeBytes: int
    sha256: str
    licenseId: str
    metadata: dict[str, Any]
    viewUrl: str
    downloadUrl: str


class JobErrorResponse(BaseModel):
    code: str
    message: str


class JobResponse(BaseModel):
    id: str
    engineId: str
    sourceAssetId: str | None
    state: Literal["queued", "running", "ready", "failed", "cancelled"]
    stage: str
    progress: float
    params: dict[str, Any]
    provenance: dict[str, Any]
    reservedUnits: int
    usedUnits: int
    cancellationRequested: bool
    attempt: int
    error: JobErrorResponse | None
    createdAt: float
    updatedAt: float
    startedAt: float | None
    finishedAt: float | None


class JobDetailResponse(JobResponse):
    artifacts: list[ArtifactResponse]


class JobsResponse(BaseModel):
    jobs: list[JobResponse]


class CancelResponse(BaseModel):
    state: Literal["cancelled", "cancelling"]


class ShareResponse(BaseModel):
    id: str
    expiresAt: float
    url: str


class PublicArtifactResponse(BaseModel):
    filename: str
    mediaType: str
    sizeBytes: int
    sha256: str
    licenseId: str
    metadata: dict[str, Any]
    contentUrl: str


class PublicShareResponse(BaseModel):
    artifact: PublicArtifactResponse
    expiresAt: float


JobId = Annotated[str, ApiPath(pattern=r"^job_[0-9a-f]{32}$")]
AssetId = Annotated[str, ApiPath(pattern=r"^ast_[0-9a-f]{32}$")]
ArtifactId = Annotated[str, ApiPath(pattern=r"^art_[0-9a-f]{32}$")]
ShareId = Annotated[str, ApiPath(pattern=r"^shr_[0-9a-f]{32}$")]
ShareToken = Annotated[str, ApiPath(min_length=32, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


@dataclass(frozen=True, slots=True)
class Principal:
    tenant_id: str
    user_id: str
    display_name: str
    tenant_name: str
    method: Literal["bearer", "cookie"]
    session_id: str | None = None
    csrf_hash: str | None = None


class LoginLimiter:
    """Small per-process guard; production proxies should add distributed limits."""

    def __init__(self, limit: int = 10, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        values = self._attempts[key]
        while values and values[0] <= now - self.window_seconds:
            values.popleft()
        if len(values) >= self.limit:
            return False
        values.append(now)
        return True


def _artifact(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": value["id"],
        "kind": value["kind"],
        "filename": value["filename"],
        "mediaType": value["media_type"],
        "sizeBytes": value["size_bytes"],
        "sha256": value["sha256"],
        "licenseId": value["license_id"],
        "metadata": value["metadata"],
        "viewUrl": f"/api/artifacts/{value['id']}/content",
        "downloadUrl": f"/api/artifacts/{value['id']}/download",
    }


def _job(value: dict[str, Any], *, include_artifacts: bool = False) -> dict[str, Any]:
    result = {
        "id": value["id"],
        "engineId": value["engine_id"],
        "sourceAssetId": value["source_asset_id"],
        "state": value["state"],
        "stage": value["stage"],
        "progress": value["progress"],
        "params": value["params"],
        "provenance": value["provenance"],
        "reservedUnits": value["reserved_units"],
        "usedUnits": value["used_units"],
        "cancellationRequested": value["cancellation_requested"],
        "attempt": value["attempt"],
        "error": (
            {"code": value["error_code"], "message": value["error_message"]}
            if value["error_code"]
            else None
        ),
        "createdAt": value["created_at"],
        "updatedAt": value["updated_at"],
        "startedAt": value["started_at"],
        "finishedAt": value["finished_at"],
    }
    if include_artifacts:
        result["artifacts"] = [_artifact(item) for item in value.get("artifacts", [])]
    return result


def _asset(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": value["id"],
        "name": value["original_name"],
        "mediaType": value["media_type"],
        "sizeBytes": value["size_bytes"],
        "sha256": value["sha256"],
        "metadata": value["metadata"],
        "createdAt": value["created_at"],
    }


def create_app(
    settings: Settings | None = None,
    *,
    service: WorkspaceService | None = None,
    start_worker: bool = True,
) -> FastAPI:
    runtime = settings or Settings.from_env()
    runtime.validate()
    workspace = service or WorkspaceService(runtime)
    limiter = LoginLimiter()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        recovery = workspace.initialize()
        workspace.write_runtime_manifest()
        if recovery["requeued"] or recovery["failed"]:
            logger.warning("job recovery result: %s", recovery)
        if start_worker:
            workspace.start_worker()
        try:
            yield
        finally:
            workspace.stop_worker()

    application = FastAPI(
        title="3D Scene Workspace",
        version="0.2.0",
        docs_url=None if runtime.environment == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if runtime.environment == "production" else "/openapi.json",
        lifespan=lifespan,
    )
    application.state.workspace = workspace
    allowed_hosts = list(runtime.allowed_hosts)
    if runtime.environment != "production":
        allowed_hosts.extend(["testserver", "localhost", "127.0.0.1"])
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=sorted(set(allowed_hosts)))

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        rejected: Response | None = None
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                declared_bytes = int(content_length)
            except ValueError:
                rejected = JSONResponse(
                    status_code=400, content={"detail": "Invalid Content-Length."}
                )
            else:
                upload_ceiling = runtime.max_upload_bytes + 1024 * 1024
                request_ceiling = upload_ceiling if request.url.path == "/api/assets" else 64 * 1024
                if declared_bytes < 0 or declared_bytes > request_ceiling:
                    rejected = JSONResponse(
                        status_code=413, content={"detail": "Request body is too large."}
                    )
        response = rejected or await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; "
            "form-action 'self'; require-trusted-types-for 'script'; trusted-types default"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def principal(
        request: Request, x_csrf_token: Annotated[str | None, Header()] = None
    ) -> Principal:
        authorization = request.headers.get("authorization", "")
        value: dict[str, Any] | None = None
        method: Literal["bearer", "cookie"]
        if authorization.startswith("Bearer "):
            method = "bearer"
            token = authorization.removeprefix("Bearer ").strip()
            value = workspace.database.authenticate_api_token(token) if token else None
        else:
            method = "cookie"
            token = request.cookies.get(SESSION_COOKIE, "")
            value = workspace.database.authenticate_session(token) if token else None
        if not value:
            raise HTTPException(401, "Authentication required.")
        if method == "cookie" and request.method in UNSAFE_METHODS:
            supplied = token_digest(x_csrf_token) if x_csrf_token else ""
            if not hmac.compare_digest(supplied, value["csrf_hash"]):
                raise HTTPException(403, "CSRF token is missing or invalid.")
        return Principal(
            tenant_id=value["tenant_id"],
            user_id=value["user_id"],
            display_name=value["display_name"],
            tenant_name=value["tenant_name"],
            method=method,
            session_id=value.get("session_id"),
            csrf_hash=value.get("csrf_hash"),
        )

    CurrentPrincipal = Annotated[Principal, Depends(principal)]

    @application.exception_handler(QuotaExceeded)
    async def quota_error(_: Request, error: QuotaExceeded):
        return JSONResponse(
            status_code=409, content={"detail": str(error), "code": "quota_exceeded"}
        )

    @application.exception_handler(EngineUnavailable)
    async def engine_error(_: Request, error: EngineUnavailable):
        return JSONResponse(
            status_code=409, content={"detail": str(error), "code": "engine_unavailable"}
        )

    @application.get("/healthz", response_model=HealthResponse)
    async def health():
        return {"status": "ok"}

    @application.post("/api/session", response_model=LoginResponse)
    async def login(payload: LoginRequest, request: Request, response: Response):
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(429, "Too many login attempts. Try again in one minute.")
        authenticated = workspace.database.authenticate_api_token(payload.token)
        if not authenticated:
            raise HTTPException(401, "Invalid workspace token.")
        session_token, csrf_token = workspace.database.create_session(
            authenticated, runtime.session_ttl_seconds
        )
        response.set_cookie(
            SESSION_COOKIE,
            session_token,
            max_age=runtime.session_ttl_seconds,
            httponly=True,
            secure=runtime.cookie_secure,
            samesite="strict",
            path="/",
        )
        return {
            "csrfToken": csrf_token,
            "user": {
                "displayName": authenticated["display_name"],
                "tenantName": authenticated["tenant_name"],
            },
        }

    @application.get("/api/me", response_model=MeResponse)
    async def me(current: CurrentPrincipal):
        csrf = None
        if current.method == "cookie" and current.session_id:
            csrf = workspace.database.rotate_csrf(current.session_id)
        return {
            "user": {"displayName": current.display_name, "tenantName": current.tenant_name},
            "csrfToken": csrf,
            "quota": workspace.database.quota(current.tenant_id),
        }

    @application.delete("/api/session", status_code=204)
    async def logout(current: CurrentPrincipal, response: Response):
        if current.session_id:
            workspace.database.delete_session(current.session_id)
        response.delete_cookie(
            SESSION_COOKIE, path="/", secure=runtime.cookie_secure, samesite="strict"
        )

    @application.get("/api/engines", response_model=EnginesResponse)
    async def engines(_: CurrentPrincipal):
        return {"engines": workspace.engine_descriptors()}

    @application.post("/api/assets", status_code=201, response_model=AssetResponse)
    async def upload_asset(current: CurrentPrincipal, file: Annotated[UploadFile, File()]):
        try:
            result = workspace.upload_video(
                tenant_id=current.tenant_id,
                filename=file.filename,
                media_type=file.content_type,
                stream=file.file,
            )
        except UploadRejected as error:
            raise HTTPException(error.status_code, str(error)) from error
        finally:
            await file.close()
        return _asset(result)

    @application.delete("/api/assets/{asset_id}", status_code=204)
    async def delete_asset(asset_id: AssetId, current: CurrentPrincipal):
        try:
            workspace.delete_asset(current.tenant_id, asset_id)
        except KeyError as error:
            raise HTTPException(404, "Asset not found.") from error
        except InvalidTransition as error:
            raise HTTPException(409, str(error)) from error

    @application.post("/api/jobs/sample", status_code=202, response_model=JobResponse)
    async def sample_job(current: CurrentPrincipal):
        return _job(workspace.submit_sample(current.tenant_id))

    @application.post("/api/jobs/research", status_code=202, response_model=JobResponse)
    async def research_job(payload: ResearchJobRequest, current: CurrentPrincipal):
        return _job(
            workspace.submit_research(
                current.tenant_id,
                asset_id=payload.assetId,
                params=payload.model_dump(exclude={"assetId"}),
            )
        )

    @application.get("/api/jobs", response_model=JobsResponse)
    async def list_jobs(current: CurrentPrincipal):
        return {"jobs": [_job(item) for item in workspace.database.list_jobs(current.tenant_id)]}

    @application.get("/api/jobs/{job_id}", response_model=JobDetailResponse)
    async def get_job(job_id: JobId, current: CurrentPrincipal):
        try:
            value = workspace.database.get_job(current.tenant_id, job_id)
        except KeyError as error:
            raise HTTPException(404, "Job not found.") from error
        return _job(value, include_artifacts=True)

    @application.post("/api/jobs/{job_id}/cancel", status_code=202, response_model=CancelResponse)
    async def cancel_job(job_id: JobId, current: CurrentPrincipal):
        try:
            state = workspace.database.request_cancellation(current.tenant_id, job_id)
        except KeyError as error:
            raise HTTPException(404, "Job not found.") from error
        except InvalidTransition as error:
            raise HTTPException(409, str(error)) from error
        return {"state": state}

    @application.delete("/api/jobs/{job_id}", status_code=204)
    async def delete_job(job_id: JobId, current: CurrentPrincipal):
        try:
            workspace.delete_job(current.tenant_id, job_id)
        except KeyError as error:
            raise HTTPException(404, "Job not found.") from error
        except InvalidTransition as error:
            raise HTTPException(409, str(error)) from error

    def artifact_for(artifact_id: str, current: Principal) -> dict[str, Any]:
        try:
            return workspace.database.get_artifact(current.tenant_id, artifact_id)
        except KeyError as error:
            raise HTTPException(404, "Artifact not found.") from error

    @application.get("/api/artifacts/{artifact_id}/content")
    async def artifact_content(artifact_id: ArtifactId, current: CurrentPrincipal):
        artifact = artifact_for(artifact_id, current)
        return FileResponse(
            workspace.store.path_for_local_use(artifact["object_key"]),
            media_type=artifact["media_type"],
            headers={"Content-Disposition": f'inline; filename="{artifact["filename"]}"'},
        )

    @application.get("/api/artifacts/{artifact_id}/download")
    async def artifact_download(artifact_id: ArtifactId, current: CurrentPrincipal):
        artifact = artifact_for(artifact_id, current)
        return FileResponse(
            workspace.store.path_for_local_use(artifact["object_key"]),
            media_type=artifact["media_type"],
            filename=artifact["filename"],
        )

    @application.post(
        "/api/artifacts/{artifact_id}/shares", status_code=201, response_model=ShareResponse
    )
    async def create_share(
        artifact_id: ArtifactId, payload: ShareRequest, current: CurrentPrincipal
    ):
        try:
            share, token = workspace.database.create_share(
                current.tenant_id, artifact_id, ttl_seconds=payload.ttlSeconds
            )
        except KeyError as error:
            raise HTTPException(404, "Artifact not found.") from error
        path = f"/s/{token}"
        return {
            "id": share["id"],
            "expiresAt": share["expires_at"],
            "url": f"{runtime.public_base_url}{path}" if runtime.public_base_url else path,
        }

    @application.delete("/api/shares/{share_id}", status_code=204)
    async def revoke_share(share_id: ShareId, current: CurrentPrincipal):
        try:
            workspace.database.revoke_share(current.tenant_id, share_id)
        except KeyError as error:
            raise HTTPException(404, "Share not found.") from error

    @application.get("/api/public/shares/{token}", response_model=PublicShareResponse)
    async def public_share(token: ShareToken):
        value = workspace.database.resolve_share(token)
        if not value:
            raise HTTPException(404, "Share not found or expired.")
        return {
            "artifact": {
                "filename": value["filename"],
                "mediaType": value["media_type"],
                "sizeBytes": value["size_bytes"],
                "sha256": value["sha256"],
                "licenseId": value["license_id"],
                "metadata": value["metadata"],
                "contentUrl": f"/api/public/shares/{token}/content",
            },
            "expiresAt": value["expires_at"],
        }

    @application.get("/api/public/shares/{token}/content")
    async def public_share_content(token: ShareToken):
        value = workspace.database.resolve_share(token)
        if not value:
            raise HTTPException(404, "Share not found or expired.")
        return FileResponse(
            workspace.store.path_for_local_use(value["object_key"]),
            media_type=value["media_type"],
            headers={"Content-Disposition": f'inline; filename="{value["filename"]}"'},
        )

    @application.get("/s/{token}")
    async def share_page(token: ShareToken):
        if not workspace.database.resolve_share(token):
            raise HTTPException(404, "Share not found or expired.")
        return FileResponse(STATIC_DIR / "share.html")

    @application.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the authenticated 3D Scene Workspace")
    parser.add_argument(
        "--dev", action="store_true", help="generate a local token if none is configured"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    settings = Settings.from_env(development=args.dev)
    if settings.generated_bootstrap_token:
        print("Development workspace token (shown once):")
        print(settings.bootstrap_token)
    import uvicorn

    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
