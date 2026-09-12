"""FastAPI surface for the authenticated 3D scene workspace."""

import argparse
import asyncio
import hmac
import logging
import re
import shutil
import tempfile
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi import (
    Path as ApiPath,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import ClientDisconnect

from .analytics import register_analytics_routes
from .auth_routes import register_auth_routes
from .config import Settings
from .database import (
    IdempotencyConflict,
    IdempotencyInProgress,
    InvalidTransition,
    QuotaExceeded,
    RateLimitExceeded,
    token_digest,
)
from .engines import EngineUnavailable
from .identity import IdentityStore
from .pages import SUPPORT_PAGES, app_page, support_page
from .request_limits import RequestBodyLimitMiddleware
from .runtime_lock import workspace_lock
from .service import InvalidEngineParameters, UploadRejected, WorkspaceService

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_COOKIE = "scene_workspace_session"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
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
    accountType: Literal["operator", "google", "trial"] = "operator"


class LoginResponse(BaseModel):
    csrfToken: str
    user: UserResponse


class QuotaResponse(BaseModel):
    quota_units: int
    reserved_units: int
    consumed_units: int
    available_units: int
    stored_bytes: int
    asset_count: int
    unattached_asset_count: int
    job_count: int
    artifact_count: int
    share_count: int
    storage_limit_bytes: int
    asset_limit: int
    unattached_asset_limit: int
    job_limit: int
    artifact_limit: int
    share_limit: int


class ReconstructionAllowanceResponse(BaseModel):
    state: Literal["available", "processing", "used", "retry_later"]
    message: str
    limit: int
    remaining: int


class MeResponse(BaseModel):
    user: UserResponse
    csrfToken: str | None
    quota: QuotaResponse
    reconstructionAllowance: ReconstructionAllowanceResponse | None


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
    linkedJobCount: int
    deletable: bool
    deleteBlockedReason: str | None


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
    displayName: str
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
    nextCursor: str | None


class AssetsResponse(BaseModel):
    assets: list[AssetResponse]
    nextCursor: str | None


class CancelResponse(BaseModel):
    state: Literal["cancelled", "cancelling"]


class ShareResponse(BaseModel):
    id: str
    expiresAt: float
    url: str


class ShareInventoryItem(BaseModel):
    id: str
    artifactId: str
    filename: str
    kind: str
    expiresAt: float
    revokedAt: float | None
    createdAt: float
    researchOnly: bool


class SharesResponse(BaseModel):
    shares: list[ShareInventoryItem]
    nextCursor: str | None


class DeletionResponse(BaseModel):
    state: Literal["deleting", "revoked"]
    id: str


class BulkDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jobIds: list[str] = Field(default_factory=list, max_length=100)
    assetIds: list[str] = Field(default_factory=list, max_length=100)
    shareIds: list[str] = Field(default_factory=list, max_length=100)


class BulkDeleteResponse(BaseModel):
    state: Literal["deleting"]
    accepted: dict[str, list[str]]
    errors: dict[str, str]


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
    researchOnly: bool
    commercialWarning: str | None


JobId = Annotated[str, ApiPath(pattern=r"^job_[0-9a-f]{32}$")]
AssetId = Annotated[str, ApiPath(pattern=r"^ast_[0-9a-f]{32}$")]
ArtifactId = Annotated[str, ApiPath(pattern=r"^art_[0-9a-f]{32}$")]
ShareId = Annotated[str, ApiPath(pattern=r"^shr_[0-9a-f]{32}$")]
IdempotencyKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=8, max_length=200),
]


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

    def __init__(self, limit: int = 10, window_seconds: int = 60, max_keys: int = 10_000):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self._lock:
            now = time.monotonic()
            if key not in self._attempts and len(self._attempts) >= self.max_keys:
                key = "__overflow_client_bucket__"
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
    source_name = Path(value.get("source_original_name") or "").stem
    display_name = " ".join(source_name.replace("_", " ").split()) or "Captured space"
    result = {
        "id": value["id"],
        "displayName": (
            "Synthetic studio" if value["engine_id"] == "synthetic-sample-v1" else display_name
        ),
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
    linked_job_count = int(value.get("linked_job_count", 0))
    linked_label = "scene" if linked_job_count == 1 else "scenes"
    return {
        "id": value["id"],
        "name": value["original_name"],
        "mediaType": value["media_type"],
        "sizeBytes": value["size_bytes"],
        "sha256": value["sha256"],
        "metadata": value["metadata"],
        "createdAt": value["created_at"],
        "linkedJobCount": linked_job_count,
        "deletable": linked_job_count == 0,
        "deleteBlockedReason": (
            None
            if linked_job_count == 0
            else (
                f"This upload is retained by {linked_job_count} {linked_label}. "
                f"Delete the linked {linked_label} first."
            )
        ),
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
    identities = IdentityStore(workspace.database)
    upload_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        recovery = workspace.initialize()
        workspace.write_runtime_manifest()
        if any(recovery.values()):
            logger.warning("job recovery result: %s", recovery)
        if start_worker:
            workspace.start_worker()
        try:
            yield
        finally:
            workspace.stop_worker()

    application = FastAPI(
        title="Wayline",
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
    application.add_middleware(
        RequestBodyLimitMiddleware, max_upload_bytes=runtime.max_upload_bytes
    )

    register_auth_routes(application, workspace, runtime, limiter, SESSION_COOKIE)
    register_analytics_routes(
        application, workspace.database, runtime, LoginLimiter(limit=120, max_keys=1)
    )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            # Capability tokens appear in share URLs; never copy paths to logs.
            logger.exception("unhandled workspace request failure")
            response = (
                support_page(
                    "Something went wrong",
                    "The workspace could not complete this request.",
                    "<p>Please return to your workspace and try again. "
                    "Existing jobs are not automatically resubmitted.</p>",
                    status=500,
                    origin=runtime.public_base_url,
                )
                if "text/html" in request.headers.get("accept", "")
                and not request.url.path.startswith("/api/")
                else JSONResponse(
                    status_code=500,
                    content={"detail": "The request could not be completed."},
                )
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; media-src 'self' blob:; object-src 'none'; "
            "frame-ancestors 'none'; base-uri 'self'; "
            "form-action 'self'; require-trusted-types-for 'script'; trusted-types default"
        )
        if request.url.path == "/s" or request.url.path.startswith(("/api/", "/s/", "/auth/")):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        principal_marker = getattr(request.state, "workspace_principal_marker", None)
        if principal_marker:
            response.headers["X-Workspace-Principal"] = principal_marker
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
        request.state.workspace_principal_marker = token_digest(
            f"{value['tenant_id']}\0{value['user_id']}"
        )
        logout_request = request.method == "DELETE" and request.url.path == "/api/session"
        if method == "cookie" and logout_request:
            # Sign-out remains possible with stale CSRF state, but not from a
            # cross-site browser request. SameSite=Strict is defense in depth.
            origin = request.headers.get("origin")
            expected_origin = runtime.public_base_url or str(request.base_url).rstrip("/")
            if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin is not None and origin != expected_origin
            ):
                raise HTTPException(403, "Cross-origin sign out is not allowed.")
        if method == "cookie" and request.method in UNSAFE_METHODS and not logout_request:
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

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError):
        # Pydantic's default response echoes input, including malformed tokens.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
                    for item in error.errors()
                ]
            },
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException):
        if (
            error.status_code == 404
            and "text/html" in request.headers.get("accept", "")
            and not request.url.path.startswith("/api/")
        ):
            return support_page(
                "Page unavailable",
                "This page or share is unavailable.",
                "<p>The page may have moved, or this share may have expired or been revoked. "
                "Ask the owner for a new link.</p>",
                status=404,
                origin=runtime.public_base_url,
            )
        return JSONResponse(
            {"detail": error.detail}, status_code=error.status_code, headers=error.headers
        )

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

    @application.exception_handler(RateLimitExceeded)
    async def rate_error(_: Request, error: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": str(error), "code": "rate_limit_exceeded"},
            headers={"Retry-After": "60"},
        )

    @application.exception_handler(IdempotencyConflict)
    async def idempotency_conflict(_: Request, error: IdempotencyConflict):
        return JSONResponse(
            status_code=409,
            content={"detail": str(error), "code": "idempotency_conflict"},
        )

    @application.exception_handler(IdempotencyInProgress)
    async def idempotency_pending(_: Request, error: IdempotencyInProgress):
        return JSONResponse(
            status_code=409,
            content={"detail": str(error), "code": "idempotency_in_progress"},
            headers={"Retry-After": "2"},
        )

    @application.get("/healthz", response_model=HealthResponse)
    def health():
        if not workspace.ready(require_worker=start_worker):
            raise HTTPException(503, "Workspace dependencies are not ready.")
        return {"status": "ok"}

    @application.post("/api/session", response_model=LoginResponse)
    def login(payload: LoginRequest, request: Request, response: Response):
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(429, "Too many login attempts. Try again in one minute.")
        authenticated = workspace.database.authenticate_api_token(payload.token)
        if not authenticated:
            raise HTTPException(401, "Invalid workspace token.")
        request.state.workspace_principal_marker = token_digest(
            f"{authenticated['tenant_id']}\0{authenticated['user_id']}"
        )
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
    def me(current: CurrentPrincipal):
        csrf = None
        if current.method == "cookie" and current.session_id:
            csrf = workspace.database.session_csrf(current.session_id)
        return {
            "user": {
                "displayName": current.display_name,
                "tenantName": current.tenant_name,
                "accountType": identities.account_type(current.user_id),
            },
            "csrfToken": csrf,
            "quota": workspace.database.quota(current.tenant_id),
            "reconstructionAllowance": workspace.database.reconstruction_allowance(
                current.tenant_id
            ),
        }

    @application.delete("/api/session", status_code=204)
    def logout(current: CurrentPrincipal, response: Response):
        if current.session_id:
            workspace.database.delete_session(current.session_id)
        response.delete_cookie(
            SESSION_COOKIE, path="/", secure=runtime.cookie_secure, samesite="strict"
        )

    @application.get("/api/engines", response_model=EnginesResponse)
    def engines(current: CurrentPrincipal):
        descriptors = workspace.engine_descriptors()
        if identities.is_guest(current.user_id):
            for engine in descriptors:
                if engine["id"] != "synthetic-sample-v1":
                    engine["available"] = False
                    engine["unavailableReasons"] = [
                        "Sign in with Google to upload a video."
                        if runtime.signup_enabled
                        else "Video reconstruction is not available in this playground yet."
                    ]
        return {"engines": descriptors}

    @application.post(
        "/api/assets",
        status_code=201,
        response_model=AssetResponse,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {"file": {"type": "string", "format": "binary"}},
                            "additionalProperties": False,
                        }
                    }
                },
            }
        },
    )
    async def upload_asset(
        request: Request,
        current: CurrentPrincipal,
        idempotency_key: IdempotencyKey = None,
    ):
        if await run_in_threadpool(identities.is_guest, current.user_id):
            raise HTTPException(403, "Sign in with Google to upload your own video.")
        reason = await run_in_threadpool(workspace.upload_unavailable_reason, current.tenant_id)
        if reason and not await run_in_threadpool(
            workspace.database.has_completed_idempotency,
            current.tenant_id,
            "POST:/api/assets",
            idempotency_key,
        ):
            raise HTTPException(409, reason)
        if not upload_lock.acquire(blocking=False):
            raise HTTPException(
                429,
                "Another upload is in progress. Please try again shortly.",
                headers={"Retry-After": "5"},
            )
        try:
            await run_in_threadpool(
                workspace.database.consume_rate,
                current.tenant_id,
                "upload_request",
                limit=runtime.upload_rate_per_minute,
            )
            free = (await run_in_threadpool(shutil.disk_usage, tempfile.gettempdir())).free
            if free < runtime.max_upload_bytes + runtime.storage_min_free_bytes:
                raise HTTPException(507, "There is not enough temporary storage for an upload.")
            # Parse only after authentication and admission. File() dependencies
            # would spool the entire multipart body before checking the principal.
            try:
                async with asyncio.timeout(runtime.upload_timeout_seconds):
                    form = await request.form(max_files=1, max_fields=0)
            except TimeoutError as error:
                raise HTTPException(408, "Upload timed out. Please try again.") from error
            except ClientDisconnect as error:
                raise HTTPException(400, "Upload connection was interrupted.") from error
            try:
                file = form.get("file")
                if not isinstance(file, UploadFile):
                    raise HTTPException(422, "Provide one video in the file field.")
                result = await run_in_threadpool(
                    workspace.upload_video,
                    tenant_id=current.tenant_id,
                    filename=file.filename,
                    media_type=file.content_type,
                    stream=file.file,
                    idempotency_key=idempotency_key,
                )
            finally:
                await form.close()
        except UploadRejected as error:
            raise HTTPException(error.status_code, str(error)) from error
        finally:
            upload_lock.release()
        return _asset(result)

    @application.get("/api/assets", response_model=AssetsResponse)
    def list_assets(
        current: CurrentPrincipal,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
    ):
        try:
            assets, next_cursor = workspace.database.page_assets(
                current.tenant_id, limit=limit, cursor=cursor
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return {"assets": [_asset(item) for item in assets], "nextCursor": next_cursor}

    @application.delete("/api/assets/{asset_id}", status_code=202, response_model=DeletionResponse)
    def delete_asset(
        asset_id: AssetId,
        current: CurrentPrincipal,
        idempotency_key: IdempotencyKey = None,
    ):
        try:
            return workspace.delete_asset(
                current.tenant_id, asset_id, idempotency_key=idempotency_key
            )
        except KeyError as error:
            raise HTTPException(404, "Asset not found.") from error
        except InvalidTransition as error:
            raise HTTPException(409, str(error)) from error

    @application.post("/api/jobs/sample", status_code=202, response_model=JobResponse)
    def sample_job(current: CurrentPrincipal, idempotency_key: IdempotencyKey = None):
        return _job(workspace.submit_sample(current.tenant_id, idempotency_key=idempotency_key))

    @application.post("/api/jobs/research", status_code=202, response_model=JobResponse)
    def research_job(
        payload: ResearchJobRequest,
        current: CurrentPrincipal,
        idempotency_key: IdempotencyKey = None,
    ):
        if identities.is_guest(current.user_id):
            raise HTTPException(403, "Sign in with Google to reconstruct a video.")
        try:
            result = workspace.submit_research(
                current.tenant_id,
                asset_id=payload.assetId,
                params=payload.model_dump(exclude={"assetId"}),
                idempotency_key=idempotency_key,
            )
        except InvalidEngineParameters as error:
            raise HTTPException(422, str(error)) from error
        return _job(result)

    @application.get("/api/jobs", response_model=JobsResponse)
    def list_jobs(
        current: CurrentPrincipal,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
    ):
        try:
            jobs, next_cursor = workspace.database.page_jobs(
                current.tenant_id, limit=limit, cursor=cursor
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return {"jobs": [_job(item) for item in jobs], "nextCursor": next_cursor}

    @application.get("/api/jobs/{job_id}", response_model=JobDetailResponse)
    def get_job(job_id: JobId, current: CurrentPrincipal):
        try:
            value = workspace.database.get_job(current.tenant_id, job_id)
        except KeyError as error:
            raise HTTPException(404, "Job not found.") from error
        return _job(value, include_artifacts=True)

    @application.post("/api/jobs/{job_id}/cancel", status_code=202, response_model=CancelResponse)
    def cancel_job(
        job_id: JobId,
        current: CurrentPrincipal,
        idempotency_key: IdempotencyKey = None,
    ):
        try:
            return workspace.cancel_job(current.tenant_id, job_id, idempotency_key=idempotency_key)
        except KeyError as error:
            raise HTTPException(404, "Job not found.") from error
        except InvalidTransition as error:
            raise HTTPException(409, str(error)) from error

    @application.delete("/api/jobs/{job_id}", status_code=202, response_model=DeletionResponse)
    def delete_job(
        job_id: JobId,
        current: CurrentPrincipal,
        idempotency_key: IdempotencyKey = None,
    ):
        try:
            return workspace.delete_job(current.tenant_id, job_id, idempotency_key=idempotency_key)
        except KeyError as error:
            raise HTTPException(404, "Job not found.") from error
        except InvalidTransition as error:
            raise HTTPException(409, str(error)) from error

    def artifact_for(artifact_id: str, current: Principal) -> dict[str, Any]:
        try:
            return workspace.database.get_published_artifact(current.tenant_id, artifact_id)
        except KeyError as error:
            raise HTTPException(404, "Artifact not found.") from error

    def deliver_artifact(artifact: dict[str, Any], request: Request, *, attachment=False):
        # A single range cannot amplify a response beyond its reserved file size.
        if "," in request.headers.get("range", ""):
            raise HTTPException(416, "Only a single byte range is supported.")
        path = workspace.store.path_for_local_use(artifact["object_key"])
        try:
            file_stat = path.stat()
        except FileNotFoundError as error:
            raise HTTPException(404, "Artifact not found.") from error
        workspace.database.reserve_delivery_bytes(
            file_stat.st_size, limit=runtime.scene_delivery_budget_bytes
        )
        return FileResponse(
            path,
            media_type=artifact["media_type"],
            filename=artifact["filename"],
            content_disposition_type="attachment" if attachment else "inline",
            stat_result=file_stat,
        )

    @application.get("/api/artifacts/{artifact_id}/content")
    def artifact_content(artifact_id: ArtifactId, request: Request, current: CurrentPrincipal):
        return deliver_artifact(artifact_for(artifact_id, current), request)

    @application.get("/api/artifacts/{artifact_id}/download")
    def artifact_download(artifact_id: ArtifactId, request: Request, current: CurrentPrincipal):
        return deliver_artifact(artifact_for(artifact_id, current), request, attachment=True)

    @application.post(
        "/api/artifacts/{artifact_id}/shares", status_code=201, response_model=ShareResponse
    )
    def create_share(
        artifact_id: ArtifactId,
        payload: ShareRequest,
        current: CurrentPrincipal,
        idempotency_key: IdempotencyKey = None,
    ):
        try:
            share = workspace.create_share(
                current.tenant_id,
                artifact_id,
                ttl_seconds=payload.ttlSeconds,
                idempotency_key=idempotency_key,
            )
        except KeyError as error:
            raise HTTPException(404, "Artifact not found.") from error
        path = f"/s#{share['token']}"
        return {
            "id": share["id"],
            "expiresAt": share["expires_at"],
            "url": f"{runtime.public_base_url}{path}" if runtime.public_base_url else path,
        }

    @application.get("/api/shares", response_model=SharesResponse)
    def list_shares(
        current: CurrentPrincipal,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
    ):
        try:
            shares, next_cursor = workspace.database.page_shares(
                current.tenant_id, limit=limit, cursor=cursor
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return {
            "shares": [
                {
                    "id": item["id"],
                    "artifactId": item["artifact_id"],
                    "filename": item["filename"],
                    "kind": item["kind"],
                    "expiresAt": item["expires_at"],
                    "revokedAt": item["revoked_at"],
                    "createdAt": item["created_at"],
                    "researchOnly": bool(item["metadata"].get("researchOnly")),
                }
                for item in shares
            ],
            "nextCursor": next_cursor,
        }

    @application.delete("/api/shares/{share_id}", status_code=202, response_model=DeletionResponse)
    def revoke_share(
        share_id: ShareId,
        current: CurrentPrincipal,
        idempotency_key: IdempotencyKey = None,
    ):
        try:
            return workspace.revoke_share(
                current.tenant_id, share_id, idempotency_key=idempotency_key
            )
        except KeyError as error:
            raise HTTPException(404, "Share not found.") from error

    @application.post("/api/bulk-delete", status_code=202, response_model=BulkDeleteResponse)
    def bulk_delete(
        payload: BulkDeleteRequest,
        current: CurrentPrincipal,
        idempotency_key: IdempotencyKey = None,
    ):
        patterns = {
            "jobIds": (payload.jobIds, "job_"),
            "assetIds": (payload.assetIds, "ast_"),
            "shareIds": (payload.shareIds, "shr_"),
        }
        total = sum(len(values) for values, _ in patterns.values())
        if total == 0:
            raise HTTPException(422, "Bulk deletion requires at least one record.")
        if total > 100:
            raise HTTPException(422, "Bulk deletion accepts at most 100 total records.")
        for label, (values, prefix) in patterns.items():
            if any(
                len(value) != 36
                or not value.startswith(prefix)
                or any(char not in "0123456789abcdef" for char in value[4:])
                for value in values
            ):
                raise HTTPException(422, f"{label} contains an invalid identifier.")
        return workspace.bulk_delete(
            current.tenant_id,
            job_ids=payload.jobIds,
            asset_ids=payload.assetIds,
            share_ids=payload.shareIds,
            idempotency_key=idempotency_key,
        )

    def resolve_public_share(request: Request):
        authorization = request.headers.get("authorization", "")
        token = authorization.removeprefix("Bearer ")
        if not authorization.startswith("Bearer ") or not re.fullmatch(
            r"[A-Za-z0-9_-]{32,64}", token
        ):
            raise HTTPException(404, "Share not found or expired.")
        value = workspace.database.resolve_share(token)
        if not value:
            raise HTTPException(404, "Share not found or expired.")
        return value

    @application.get("/api/public/share", response_model=PublicShareResponse)
    def public_share(request: Request):
        value = resolve_public_share(request)
        research_only = bool(value["metadata"].get("researchOnly"))
        return {
            "artifact": {
                "filename": value["filename"],
                "mediaType": value["media_type"],
                "sizeBytes": value["size_bytes"],
                "sha256": value["sha256"],
                "licenseId": value["license_id"],
                "metadata": value["metadata"],
                "contentUrl": "/api/public/share/content",
            },
            "expiresAt": value["expires_at"],
            "researchOnly": research_only,
            "commercialWarning": (
                "Research-only output. Model, checkpoint, and training-data commercial rights "
                "have not been cleared. Do not use this artifact commercially."
                if research_only
                else None
            ),
        }

    @application.get("/api/public/share/content")
    def public_share_content(request: Request):
        return deliver_artifact(resolve_public_share(request), request)

    @application.get("/s")
    def share_page():
        return app_page(
            "share.html",
            "Shared space — Wayline",
            "A permissioned, expiring 3D scene review.",
            runtime.public_base_url,
        )

    @application.get("/")
    def index():
        return app_page(
            "index.html",
            "Wayline — a new perspective",
            "A private workspace for reviewable 3D scene artifacts.",
            runtime.public_base_url,
        )

    @application.get("/privacy", include_in_schema=False)
    def privacy():
        return support_page(*SUPPORT_PAGES["privacy"], origin=runtime.public_base_url)

    @application.get("/terms", include_in_schema=False)
    def terms():
        return support_page(*SUPPORT_PAGES["terms"], origin=runtime.public_base_url)

    @application.get("/contact", include_in_schema=False)
    def contact():
        return support_page(*SUPPORT_PAGES["contact"], origin=runtime.public_base_url)

    @application.get("/robots.txt", include_in_schema=False)
    def robots():
        return Response("User-agent: *\nDisallow: /\n", media_type="text/plain")

    @application.get("/sitemap.xml", include_in_schema=False)
    def sitemap():
        # A private application has no indexable routes. Never enumerate shares.
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>',
            media_type="application/xml",
        )

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Wayline")
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

    # OAuth callbacks can contain authorization codes. Avoid default request logs.
    with workspace_lock(settings.data_dir):
        uvicorn.run(
            create_app(settings),
            host=args.host,
            port=args.port,
            log_level="info",
            access_log=False,
        )


if __name__ == "__main__":
    main()
