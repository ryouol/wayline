"""Application service for uploads, durable jobs, artifacts, and worker recovery."""

from __future__ import annotations

import json
import logging
import re
import shutil
import threading
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any, BinaryIO

from .config import Settings
from .database import SCHEMA_VERSION, Database
from .engines import (
    EngineContext,
    EngineResult,
    EngineUnavailable,
    JobCancelled,
    ReconstructionEngine,
    cleanup_result,
    engine_registry,
)
from .storage import LocalObjectStore, ObjectTooLarge

logger = logging.getLogger(__name__)

ALLOWED_VIDEO_TYPES = {
    "video/mp4": {".mp4", ".m4v", ".mov"},
    "video/quicktime": {".mov"},
    "video/x-msvideo": {".avi"},
    "video/x-matroska": {".mkv"},
}


class UploadRejected(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def safe_filename(value: str | None) -> str:
    name = Path(value or "upload.mp4").name.strip()
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:120].strip(". ")
    return name or "upload.mp4"


def detect_video_container(header: bytes) -> str | None:
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video/mp4"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"AVI ":
        return "video/x-msvideo"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return "video/x-matroska"
    return None


class VideoInspector:
    """Metadata probe isolated so production can replace OpenCV with ffprobe."""

    def inspect(self, path: Path) -> dict[str, Any]:
        try:
            import cv2
        except ImportError as error:  # pragma: no cover - dependency guard
            raise UploadRejected(
                "video inspection support is not installed", status_code=503
            ) from error
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise UploadRejected("The file could not be decoded as video.")
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
            frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        finally:
            capture.release()
        if fps <= 0 or frames <= 0 or width <= 0 or height <= 0:
            raise UploadRejected("The video has no readable frames or timing metadata.")
        return {
            "fps": round(fps, 3),
            "frames": frames,
            "durationSeconds": round(frames / fps, 3),
            "width": width,
            "height": height,
        }


class WorkspaceService:
    def __init__(
        self,
        settings: Settings,
        *,
        inspector: VideoInspector | None = None,
        engines: dict[str, ReconstructionEngine] | None = None,
    ):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        settings.data_dir.chmod(0o700)
        self.database = Database(settings.data_dir / "workspace.sqlite3")
        self.store = LocalObjectStore(settings.data_dir / "objects")
        self.inspector = inspector or VideoInspector()
        self.engines = engines or engine_registry(settings)
        self.work_root = settings.data_dir / "work"
        self.work_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.work_root.chmod(0o700)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._worker: threading.Thread | None = None

    def initialize(self) -> dict[str, int]:
        self.database.initialize()
        if self.settings.bootstrap_token:
            self.database.bootstrap(
                token=self.settings.bootstrap_token,
                tenant_name=self.settings.bootstrap_tenant_name,
                quota_units=self.settings.tenant_quota_units,
            )
        recovery = self.database.recover_jobs(max_attempts=self.settings.max_job_attempts)
        partial_artifacts = self.database.delete_artifacts_for_incomplete_jobs()
        for key in partial_artifacts:
            self.store.delete(key)
        if partial_artifacts:
            logger.warning("discarded %s partial artifacts during recovery", len(partial_artifacts))
        return recovery

    def start_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(
            target=self._worker_loop, name="workspace-worker", daemon=True
        )
        self._worker.start()

    def stop_worker(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._worker:
            self._worker.join(timeout=5)

    def engine_descriptors(self) -> list[dict[str, Any]]:
        values = []
        for engine in self.engines.values():
            descriptor = engine.descriptor
            values.append(
                {
                    "id": descriptor.id,
                    "name": descriptor.name,
                    "available": descriptor.available,
                    "researchOnly": descriptor.research_only,
                    "commerciallyCleared": descriptor.commercially_cleared,
                    "unavailableReasons": list(descriptor.unavailable_reasons),
                }
            )
        return values

    def upload_video(
        self,
        *,
        tenant_id: str,
        filename: str | None,
        media_type: str | None,
        stream: BinaryIO,
    ) -> dict[str, Any]:
        original_name = safe_filename(filename)
        suffix = Path(original_name).suffix.lower()
        declared = (media_type or "").lower().split(";", 1)[0]
        if declared not in ALLOWED_VIDEO_TYPES or suffix not in ALLOWED_VIDEO_TYPES[declared]:
            raise UploadRejected("Use an MP4, MOV, AVI, or MKV video file.", status_code=415)
        key = f"tenants/{tenant_id}/assets/{uuid.uuid4().hex}{suffix}"
        try:
            stored = self.store.put_stream(key, stream, max_bytes=self.settings.max_upload_bytes)
        except ObjectTooLarge as error:
            raise UploadRejected(
                f"Video exceeds the {self.settings.max_upload_bytes // (1024 * 1024)} MiB limit.",
                status_code=413,
            ) from error
        path = self.store.path_for_local_use(key)
        try:
            with path.open("rb") as uploaded:
                detected = detect_video_container(uploaded.read(32))
            if detected is None:
                raise UploadRejected(
                    "The file signature does not match a supported video container.",
                    status_code=415,
                )
            if declared == "video/quicktime" and detected == "video/mp4":
                detected = declared
            if declared != detected:
                raise UploadRejected(
                    "The declared media type does not match the file contents.", status_code=415
                )
            metadata = self.inspector.inspect(path)
            if metadata["durationSeconds"] > self.settings.max_video_seconds:
                raise UploadRejected(
                    f"Video is longer than the {self.settings.max_video_seconds}-second limit.",
                    status_code=413,
                )
            if metadata["frames"] > self.settings.max_video_frames:
                raise UploadRejected(
                    f"Video exceeds the {self.settings.max_video_frames}-frame limit.",
                    status_code=413,
                )
            if max(metadata["width"], metadata["height"]) > self.settings.max_video_dimension:
                raise UploadRejected(
                    f"Video dimensions exceed {self.settings.max_video_dimension}px.",
                    status_code=413,
                )
            metadata["container"] = detected
            return self.database.create_asset(
                tenant_id=tenant_id,
                object_key=stored.key,
                original_name=original_name,
                media_type=detected,
                size_bytes=stored.size_bytes,
                sha256=stored.sha256,
                metadata=metadata,
            )
        except Exception:
            self.store.delete(key)
            raise

    def submit_sample(self, tenant_id: str) -> dict[str, Any]:
        return self._submit(tenant_id, "synthetic-sample-v1", None, {})

    def submit_research(
        self, tenant_id: str, *, asset_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        return self._submit(tenant_id, "lingbot-research-v1", asset_id, params)

    def _submit(
        self, tenant_id: str, engine_id: str, asset_id: str | None, params: dict[str, Any]
    ) -> dict[str, Any]:
        engine = self.engines.get(engine_id)
        if engine is None:
            raise KeyError(engine_id)
        if not engine.descriptor.available:
            raise EngineUnavailable("; ".join(engine.descriptor.unavailable_reasons))
        metadata = None
        if asset_id:
            metadata = self.database.get_asset(tenant_id, asset_id)["metadata"]
        reservation = engine.estimate_units(metadata, params)
        job = self.database.create_job(
            tenant_id=tenant_id,
            engine_id=engine_id,
            source_asset_id=asset_id,
            params=params,
            provenance=engine.provenance(),
            reserve_units=reservation,
        )
        self._wake.set()
        return job

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            processed = self.process_next_job()
            if not processed:
                self._wake.wait(self.settings.worker_poll_seconds)
                self._wake.clear()

    def process_next_job(self) -> bool:
        job = self.database.claim_next_job(
            lease_seconds=self.settings.job_timeout_seconds,
            max_attempts=self.settings.max_job_attempts,
        )
        if job is None:
            return False
        self._process_job(job)
        return True

    def _process_job(self, job: dict[str, Any]) -> None:
        tenant_id, job_id = job["tenant_id"], job["id"]
        engine = self.engines[job["engine_id"]]
        result: EngineResult | None = None
        stored_keys: list[str] = []
        try:
            source_path = None
            source_metadata = None
            if job["source_asset_id"]:
                source = self.database.get_asset(tenant_id, job["source_asset_id"])
                source_path = self.store.path_for_local_use(source["object_key"])
                source_metadata = source["metadata"]

            def progress(stage: str, value: float) -> None:
                self.database.update_job_progress(
                    tenant_id,
                    job_id,
                    stage=stage,
                    progress=value,
                    lease_seconds=self.settings.job_timeout_seconds,
                )

            def cancelled() -> bool:
                return self.database.cancellation_requested(tenant_id, job_id)

            result = engine.run(
                EngineContext(
                    job_id=job_id,
                    tenant_id=tenant_id,
                    params=job["params"],
                    source_path=source_path,
                    source_metadata=source_metadata,
                    work_root=self.work_root,
                ),
                progress,
                cancelled,
            )
            if cancelled():
                raise JobCancelled("job cancelled before artifacts were committed")
            progress("storing", 0.92)
            for artifact in result.artifacts:
                suffix = Path(artifact.filename).suffix.lower()
                key = f"tenants/{tenant_id}/jobs/{job_id}/{uuid.uuid4().hex}{suffix}"
                if artifact.payload is not None:
                    stored = self.store.put_bytes(
                        key, artifact.payload, max_bytes=100 * 1024 * 1024
                    )
                elif artifact.path is not None:
                    stored = self.store.copy_from_path(
                        key, artifact.path, max_bytes=100 * 1024 * 1024
                    )
                else:
                    raise RuntimeError("engine produced an artifact without bytes or a file")
                stored_keys.append(key)
                self.database.create_artifact(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    kind=artifact.kind,
                    object_key=stored.key,
                    filename=safe_filename(artifact.filename),
                    media_type=artifact.media_type,
                    size_bytes=stored.size_bytes,
                    sha256=stored.sha256,
                    license_id=artifact.license_id,
                    metadata=artifact.metadata,
                )
            completed = self.database.finish_job(tenant_id, job_id, used_units=result.used_units)
            if not completed:
                self._discard_job_artifacts(tenant_id, job_id, stored_keys)
        except JobCancelled as error:
            self._discard_job_artifacts(tenant_id, job_id, stored_keys)
            self.database.fail_job(
                tenant_id, job_id, code="cancelled", message=str(error), cancelled=True
            )
        except Exception as error:  # keep the worker alive; details remain server-side
            logger.exception("job %s failed", job_id)
            self._discard_job_artifacts(tenant_id, job_id, stored_keys)
            code = "engine_unavailable" if isinstance(error, EngineUnavailable) else "job_failed"
            self.database.fail_job(
                tenant_id,
                job_id,
                code=code,
                message="The job could not be completed. Check server logs with the job ID.",
            )
        finally:
            cleanup_result(result)
            self._cleanup_job_workdirs(job_id)

    def _discard_job_artifacts(self, tenant_id: str, job_id: str, stored_keys: list[str]) -> None:
        keys = set(stored_keys + self.database.delete_artifacts_for_job(tenant_id, job_id))
        for key in keys:
            self.store.delete(key)

    def _cleanup_job_workdirs(self, job_id: str) -> None:
        """Remove private runner directories even when an engine exits before returning."""

        prefix = f"{job_id}-"
        for candidate in self.work_root.iterdir():
            if not candidate.name.startswith(prefix):
                continue
            if candidate.is_symlink():
                candidate.unlink(missing_ok=True)
            elif candidate.is_dir() and candidate.parent.resolve() == self.work_root.resolve():
                shutil.rmtree(candidate, ignore_errors=True)

    def delete_job(self, tenant_id: str, job_id: str) -> None:
        artifact_keys, source_key = self.database.delete_job_records(tenant_id, job_id)
        for key in artifact_keys:
            self.store.delete(key)
        if source_key:
            self.store.delete(source_key)

    def delete_asset(self, tenant_id: str, asset_id: str) -> None:
        self.store.delete(self.database.delete_asset_record(tenant_id, asset_id))

    def export_health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "database": str(self.database.path),
            "storage": "local-object-store",
            "worker": bool(self._worker and self._worker.is_alive()),
        }

    def ready(self, *, require_worker: bool) -> bool:
        """Check the durable dependencies without exposing their paths."""

        probe_key = f".health/{uuid.uuid4().hex}.probe"
        try:
            with self.database.connect() as connection:
                row = connection.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
            if row is None or int(row[0]) != SCHEMA_VERSION:
                return False
            self.store.put_bytes(probe_key, b"1", max_bytes=1)
            self.store.delete(probe_key)
            return not require_worker or bool(self._worker and self._worker.is_alive())
        except Exception:
            return False
        finally:
            with suppress(Exception):
                self.store.delete(probe_key)

    def write_runtime_manifest(self) -> None:
        manifest = {
            "schemaVersion": 1,
            "environment": self.settings.environment,
            "storage": {
                "driver": "local",
                "migrationBoundary": "ObjectStore protocol (S3-compatible implementation)",
            },
            "database": {
                "driver": "sqlite",
                "migrationBoundary": "Database repository (Postgres implementation)",
            },
            "engines": self.engine_descriptors(),
        }
        target = self.settings.data_dir / "runtime-manifest.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.chmod(0o600)
        temporary.replace(target)
