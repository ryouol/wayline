"""Application service for uploads, durable jobs, artifacts, and worker recovery."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
import uuid
from base64 import urlsafe_b64encode
from contextlib import suppress
from pathlib import Path
from typing import Any, BinaryIO

from .config import Settings
from .database import (
    SCHEMA_VERSION,
    Database,
    InvalidTransition,
    StaleAttempt,
)
from .engines import (
    EngineContext,
    EngineResult,
    EngineUnavailable,
    JobCancelled,
    ReconstructionEngine,
    cleanup_result,
    engine_registry,
)
from .storage import LocalObjectStore, ObjectStore, ObjectTooLarge, StoredObject

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
        database: Database | None = None,
        store: ObjectStore | None = None,
    ):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        settings.data_dir.chmod(0o700)
        self.database = database or Database(settings.data_dir / "workspace.sqlite3")
        self.store: ObjectStore = store or LocalObjectStore(settings.data_dir / "objects")
        self.inspector = inspector or VideoInspector()
        self.engines = engines or engine_registry(settings)
        self.work_root = settings.data_dir / "work"
        self.work_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.work_root.chmod(0o700)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._worker: threading.Thread | None = None
        self._worker_id = f"worker_{uuid.uuid4().hex}"
        self._maintenance_at = 0.0
        self._full_maintenance_at = 0.0
        self._readiness_lock = threading.Lock()
        self._readiness_checked_at = 0.0
        self._readiness_value = False
        self._reconciliation_missing: set[str] = set()
        self._share_secret = self._load_or_create_share_secret()

    def _load_or_create_share_secret(self) -> bytes:
        target = self.settings.data_dir / "share-token.secret"
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            secret = target.read_bytes()
        else:
            secret = os.urandom(32)
            try:
                os.write(descriptor, secret)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        target.chmod(0o600)
        if len(secret) != 32:
            raise RuntimeError("share token secret must contain exactly 32 bytes")
        return secret

    def _derived_share_token(
        self,
        tenant_id: str,
        idempotency_key: str,
        request_hash: str,
        seed: str,
    ) -> str:
        message = f"{tenant_id}\0{idempotency_key}\0{request_hash}\0{seed}".encode()
        return (
            urlsafe_b64encode(hmac.digest(self._share_secret, message, "sha256"))
            .decode("ascii")
            .rstrip("=")
        )

    def initialize(self) -> dict[str, int]:
        self.database.initialize()
        if self.settings.bootstrap_token:
            self.database.bootstrap(
                token=self.settings.bootstrap_token,
                tenant_name=self.settings.bootstrap_tenant_name,
                quota_units=self.settings.tenant_quota_units,
                storage_limit_bytes=self.settings.tenant_storage_bytes,
                asset_limit=self.settings.tenant_max_assets,
                unattached_asset_limit=self.settings.tenant_max_unattached_assets,
                job_limit=self.settings.tenant_max_jobs,
                artifact_limit=self.settings.tenant_max_artifacts,
                share_limit=self.settings.tenant_max_shares,
            )
        recovery = self.database.recover_jobs(max_attempts=self.settings.max_job_attempts)
        partial_artifacts = self.database.queue_incomplete_artifacts()
        abandoned_claims = self.recover_object_claims(force=True)
        retention = self.run_retention()
        reconciliation = self.reconcile_storage()
        self.drain_deletions()
        if partial_artifacts:
            logger.warning("queued %s partial artifacts during recovery", partial_artifacts)
        if abandoned_claims:
            logger.warning("recovered %s provisional object claims", abandoned_claims)
        if any(retention.values()) or reconciliation["orphans"]:
            logger.info("workspace maintenance: retention=%s storage=%s", retention, reconciliation)
        return recovery

    def start_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker_id = f"worker_{uuid.uuid4().hex}"
        self._worker = threading.Thread(
            target=self._worker_loop, name="workspace-worker", daemon=True
        )
        self._worker.start()

    def stop_worker(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._worker:
            self._worker.join(timeout=self.settings.shutdown_timeout_seconds)
            if self._worker.is_alive():
                raise RuntimeError("worker did not stop within the configured shutdown deadline")
            self._worker = None

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

    @staticmethod
    def request_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _idempotency_begin(
        self,
        tenant_id: str,
        scope: str,
        key: str | None,
        payload: dict[str, Any],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        request_hash = self.request_hash(payload)
        replay = self.database.begin_idempotency(
            tenant_id,
            scope,
            key,
            request_hash,
            ttl_seconds=self.settings.idempotency_ttl_seconds,
            connection=connection,
        )
        return request_hash, replay["response"] if replay else None

    def _idempotency_complete(
        self,
        tenant_id: str,
        scope: str,
        key: str | None,
        request_hash: str,
        response: dict[str, Any],
        *,
        status_code: int,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        self.database.complete_idempotency(
            tenant_id,
            scope,
            key,
            request_hash,
            status_code=status_code,
            response=response,
            connection=connection,
        )

    def _queue_object_deletion(self, tenant_id: str, stored: StoredObject) -> None:
        """Make cleanup durable before making a best-effort deletion pass."""

        try:
            self.database.queue_orphan_object(tenant_id, stored.key, stored.size_bytes)
        except Exception:
            # The database is itself the durable dependency. If it is unavailable,
            # avoid masking the caller's error and make one direct cleanup attempt;
            # startup reconciliation catches anything that remains.
            logger.exception("could not persist cleanup for object %s", stored.key)
            with suppress(Exception):
                self.store.delete(stored.key)
            return
        self.drain_deletions()

    def _claim_ttl(self) -> int:
        return max(
            15 * 60,
            self.settings.job_timeout_seconds + self.settings.shutdown_timeout_seconds + 60,
        )

    def _release_object_claim(self, tenant_id: str, key: str) -> None:
        try:
            self.database.release_object_claim(tenant_id, key)
        except Exception:
            # A durable stale claim is safer than making a committed object look
            # orphaned. Startup/periodic claim recovery will reconcile it later.
            logger.exception("could not release provisional object claim %s", key)

    def _claim_object(self, tenant_id: str, key: str, *, reserve_bytes: int, purpose: str) -> None:
        free_bytes = shutil.disk_usage(self.settings.data_dir).free
        self.database.claim_object(
            tenant_id,
            key,
            ttl_seconds=self._claim_ttl(),
            reserve_bytes=reserve_bytes,
            purpose=purpose,
            global_storage_bytes=self.settings.global_storage_bytes,
            physical_free_bytes=free_bytes,
            min_free_bytes=self.settings.storage_min_free_bytes,
            global_inflight_limit=self.settings.global_max_inflight_objects,
            tenant_inflight_limit=self.settings.tenant_max_inflight_objects,
        )

    def recover_object_claims(self, *, force: bool = False) -> int:
        """Measure interrupted writes before releasing their durable reservations."""

        recovered = 0
        for claim in self.database.object_claims_due(force=force):
            try:
                with self.store.open(claim["object_key"]) as stream:
                    stream.seek(0, 2)
                    actual_size: int | None = stream.tell()
            except FileNotFoundError:
                actual_size = None
            except Exception:
                logger.exception("could not inspect claimed object %s", claim["object_key"])
                continue
            if self.database.recover_object_claim(
                claim["tenant_id"], claim["object_key"], actual_size=actual_size
            ):
                recovered += 1
        return recovered

    def upload_video(
        self,
        *,
        tenant_id: str,
        filename: str | None,
        media_type: str | None,
        stream: BinaryIO,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        original_name = safe_filename(filename)
        suffix = Path(original_name).suffix.lower()
        declared = (media_type or "").lower().split(";", 1)[0]
        if declared not in ALLOWED_VIDEO_TYPES or suffix not in ALLOWED_VIDEO_TYPES[declared]:
            raise UploadRejected("Use an MP4, MOV, AVI, or MKV video file.", status_code=415)
        self.database.consume_rate(
            tenant_id,
            "upload",
            limit=self.settings.upload_rate_per_minute,
        )
        key = f"tenants/{tenant_id}/assets/{uuid.uuid4().hex}{suffix}"
        asset_recorded = False
        self._claim_object(
            tenant_id,
            key,
            reserve_bytes=self.settings.max_upload_bytes,
            purpose="upload",
        )
        try:
            try:
                stored = self.store.put_stream(
                    key, stream, max_bytes=self.settings.max_upload_bytes
                )
            except Exception:
                self._release_object_claim(tenant_id, key)
                raise
        except ObjectTooLarge as error:
            raise UploadRejected(
                f"Video exceeds the {self.settings.max_upload_bytes // (1024 * 1024)} MiB limit.",
                status_code=413,
            ) from error
        try:
            self.database.size_object_claim(tenant_id, key, stored.size_bytes)
            path = self.store.path_for_local_use(key)
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
            scope = "POST:/api/assets"
            payload = {
                "filename": original_name,
                "mediaType": detected,
                "sha256": stored.sha256,
                "sizeBytes": stored.size_bytes,
            }
            created_result: dict[str, Any] | None = None
            with self.database.transaction() as connection:
                request_hash, replay = self._idempotency_begin(
                    tenant_id,
                    scope,
                    idempotency_key,
                    payload,
                    connection=connection,
                )
                if replay is None:
                    created_result = self.database.create_asset(
                        tenant_id=tenant_id,
                        object_key=stored.key,
                        original_name=original_name,
                        media_type=detected,
                        size_bytes=stored.size_bytes,
                        sha256=stored.sha256,
                        metadata=metadata,
                        connection=connection,
                    )
                    self._idempotency_complete(
                        tenant_id,
                        scope,
                        idempotency_key,
                        request_hash,
                        created_result,
                        status_code=201,
                        connection=connection,
                    )
            if replay is not None:
                self._queue_object_deletion(tenant_id, stored)
                return replay
            if created_result is None:  # pragma: no cover - internal invariant
                raise RuntimeError("asset transaction completed without a result")
            asset_recorded = True
            return created_result
        except Exception:
            if not asset_recorded:
                self._queue_object_deletion(tenant_id, stored)
            raise
        finally:
            self._release_object_claim(tenant_id, key)

    def submit_sample(
        self, tenant_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        return self._submit(
            tenant_id,
            "synthetic-sample-v1",
            None,
            {},
            idempotency_key=idempotency_key,
            route_scope="POST:/api/jobs/sample",
        )

    def submit_research(
        self,
        tenant_id: str,
        *,
        asset_id: str,
        params: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._submit(
            tenant_id,
            "lingbot-research-v1",
            asset_id,
            params,
            idempotency_key=idempotency_key,
            route_scope="POST:/api/jobs/research",
        )

    def _submit(
        self,
        tenant_id: str,
        engine_id: str,
        asset_id: str | None,
        params: dict[str, Any],
        *,
        idempotency_key: str | None,
        route_scope: str,
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
        with self.database.transaction() as connection:
            request_hash, replay = self._idempotency_begin(
                tenant_id,
                route_scope,
                idempotency_key,
                {"engineId": engine_id, "assetId": asset_id, "params": params},
                connection=connection,
            )
            if replay is not None:
                return replay
            job = self.database.create_job(
                tenant_id=tenant_id,
                engine_id=engine_id,
                source_asset_id=asset_id,
                params=params,
                provenance=engine.provenance(),
                reserve_units=reservation,
                rate_limit=self.settings.job_rate_per_minute,
                connection=connection,
            )
            self._idempotency_complete(
                tenant_id,
                route_scope,
                idempotency_key,
                request_hash,
                job,
                status_code=202,
                connection=connection,
            )
        self._wake.set()
        return job

    def _worker_loop(self) -> None:
        consecutive_failures = 0
        while not self._stop.is_set():
            try:
                processed = self._worker_iteration()
            except Exception:
                consecutive_failures += 1
                delay = min(
                    5.0,
                    max(self.settings.worker_poll_seconds, 0.1)
                    * (2 ** min(consecutive_failures - 1, 6)),
                )
                logger.exception(
                    "workspace worker iteration failed; retrying in %.2f seconds", delay
                )
                self._stop.wait(delay)
                continue
            consecutive_failures = 0
            if not processed:
                self._wake.wait(self.settings.worker_poll_seconds)
                self._wake.clear()

    def _worker_iteration(self) -> bool:
        now = time.monotonic()
        if now - self._maintenance_at >= 5:
            self.database.recover_jobs(max_attempts=self.settings.max_job_attempts)
            self.database.queue_incomplete_artifacts()
            self.recover_object_claims()
            self.drain_deletions()
            self._maintenance_at = now
        if now - self._full_maintenance_at >= 60:
            retention = self.run_retention()
            reconciliation = self.reconcile_storage()
            self.drain_deletions()
            if any(retention.values()) or reconciliation["orphans"]:
                logger.info(
                    "workspace maintenance: retention=%s storage=%s",
                    retention,
                    reconciliation,
                )
            self._full_maintenance_at = now
        if self._stop.is_set():
            return False
        return self.process_next_job()

    def process_next_job(self) -> bool:
        job = self.database.claim_next_job(
            worker_id=self._worker_id,
            lease_seconds=self.settings.job_timeout_seconds,
            max_attempts=self.settings.max_job_attempts,
        )
        if job is None:
            return False
        self._process_job(job)
        return True

    def _process_job(self, job: dict[str, Any]) -> None:
        tenant_id, job_id = job["tenant_id"], job["id"]
        attempt_token = job["attempt_token"]
        worker_id = job["worker_id"]
        engine = self.engines[job["engine_id"]]
        result: EngineResult | None = None
        stored_objects: list[StoredObject] = []
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
                    attempt_token=attempt_token,
                    worker_id=worker_id,
                    stage=stage,
                    progress=value,
                    lease_seconds=self.settings.job_timeout_seconds,
                )

            def cancelled() -> bool:
                return self._stop.is_set() or self.database.attempt_cancelled(
                    tenant_id,
                    job_id,
                    attempt_token=attempt_token,
                    worker_id=worker_id,
                )

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
                key = (
                    f"tenants/{tenant_id}/jobs/{job_id}/attempts/"
                    f"{attempt_token}/{uuid.uuid4().hex}{suffix}"
                )
                self._claim_object(
                    tenant_id,
                    key,
                    reserve_bytes=self.settings.max_artifact_bytes,
                    purpose="artifact",
                )
                stored: StoredObject | None = None
                claim_releasable = False
                try:
                    if artifact.payload is not None:
                        stored = self.store.put_bytes(
                            key, artifact.payload, max_bytes=self.settings.max_artifact_bytes
                        )
                    elif artifact.path is not None:
                        stored = self.store.copy_from_path(
                            key, artifact.path, max_bytes=self.settings.max_artifact_bytes
                        )
                    else:
                        raise RuntimeError("engine produced an artifact without bytes or a file")
                    stored_objects.append(stored)
                    self.database.size_object_claim(tenant_id, key, stored.size_bytes)
                    self.database.create_artifact(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        attempt_token=attempt_token,
                        worker_id=worker_id,
                        kind=artifact.kind,
                        object_key=stored.key,
                        filename=safe_filename(artifact.filename),
                        media_type=artifact.media_type,
                        size_bytes=stored.size_bytes,
                        sha256=stored.sha256,
                        license_id=artifact.license_id,
                        metadata=artifact.metadata,
                    )
                    claim_releasable = True
                except Exception:
                    if stored is None:
                        claim_releasable = True
                    else:
                        try:
                            self.database.queue_orphan_object(
                                tenant_id, stored.key, stored.size_bytes
                            )
                            claim_releasable = True
                        except Exception:
                            logger.exception(
                                "could not persist failed artifact cleanup for %s", stored.key
                            )
                    raise
                finally:
                    if claim_releasable:
                        self._release_object_claim(tenant_id, key)
            completed = self.database.finish_job(
                tenant_id,
                job_id,
                attempt_token=attempt_token,
                worker_id=worker_id,
                used_units=result.used_units,
            )
            if not completed:
                self._discard_attempt_artifacts(tenant_id, job_id, attempt_token, stored_objects)
        except JobCancelled as error:
            self._discard_attempt_artifacts(tenant_id, job_id, attempt_token, stored_objects)
            try:
                if self._stop.is_set():
                    self.database.interrupt_attempt(
                        tenant_id,
                        job_id,
                        attempt_token=attempt_token,
                        worker_id=worker_id,
                    )
                else:
                    self.database.fail_job(
                        tenant_id,
                        job_id,
                        attempt_token=attempt_token,
                        worker_id=worker_id,
                        code="cancelled",
                        message=str(error),
                        cancelled=True,
                    )
            except StaleAttempt:
                logger.info("attempt %s lost ownership during cancellation", attempt_token)
        except StaleAttempt:
            logger.info("stale attempt %s stopped mutating job %s", attempt_token, job_id)
            self._discard_attempt_artifacts(tenant_id, job_id, attempt_token, stored_objects)
        except Exception as error:  # keep the worker alive; details remain server-side
            logger.exception("job %s failed", job_id)
            self._discard_attempt_artifacts(tenant_id, job_id, attempt_token, stored_objects)
            code = "engine_unavailable" if isinstance(error, EngineUnavailable) else "job_failed"
            try:
                self.database.fail_job(
                    tenant_id,
                    job_id,
                    attempt_token=attempt_token,
                    worker_id=worker_id,
                    code=code,
                    message="The job could not be completed. Check server logs with the job ID.",
                )
            except StaleAttempt:
                logger.info("attempt %s lost ownership before failure settlement", attempt_token)
        finally:
            cleanup_result(result)
            self._cleanup_job_workdirs(job_id)

    def _discard_attempt_artifacts(
        self,
        tenant_id: str,
        job_id: str,
        attempt_token: str,
        stored_objects: list[StoredObject],
    ) -> None:
        self.database.queue_attempt_artifacts(tenant_id, job_id, attempt_token=attempt_token)
        for stored in stored_objects:
            self.database.queue_orphan_object(tenant_id, stored.key, stored.size_bytes)
        self.drain_deletions()

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

    def cancel_job(
        self, tenant_id: str, job_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        scope = "POST:/api/jobs/{job_id}/cancel"
        with self.database.transaction() as connection:
            request_hash, replay = self._idempotency_begin(
                tenant_id,
                scope,
                idempotency_key,
                {"jobId": job_id},
                connection=connection,
            )
            if replay is not None:
                return replay
            result = {
                "state": self.database.request_cancellation(
                    tenant_id, job_id, connection=connection
                )
            }
            self._idempotency_complete(
                tenant_id,
                scope,
                idempotency_key,
                request_hash,
                result,
                status_code=202,
                connection=connection,
            )
            return result

    def create_share(
        self,
        tenant_id: str,
        artifact_id: str,
        *,
        ttl_seconds: int,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        scope = "POST:/api/artifacts/{artifact_id}/shares"
        with self.database.transaction() as connection:
            request_hash, replay = self._idempotency_begin(
                tenant_id,
                scope,
                idempotency_key,
                {"artifactId": artifact_id, "ttlSeconds": ttl_seconds},
                connection=connection,
            )
            if replay is not None:
                if idempotency_key:
                    seed = replay.pop("_tokenSeed", "")
                    if not seed:
                        raise RuntimeError("idempotent share record is missing its token seed")
                    replay["token"] = self._derived_share_token(
                        tenant_id,
                        idempotency_key,
                        request_hash,
                        seed,
                    )
                    if not self.database.share_token_matches(
                        tenant_id,
                        replay["id"],
                        replay["token"],
                    ):
                        raise RuntimeError(
                            "share-token secret does not match the idempotent share record"
                        )
                return replay
            token_seed = secrets.token_urlsafe(18) if idempotency_key else ""
            derived_token = None
            if idempotency_key:
                derived_token = self._derived_share_token(
                    tenant_id,
                    idempotency_key,
                    request_hash,
                    token_seed,
                )
            share, token = self.database.create_share(
                tenant_id,
                artifact_id,
                ttl_seconds=ttl_seconds,
                rate_limit=self.settings.share_rate_per_minute,
                raw_token=derived_token,
                connection=connection,
            )
            result = {**share, "token": token}
            self._idempotency_complete(
                tenant_id,
                scope,
                idempotency_key,
                request_hash,
                {**share, "_tokenSeed": token_seed},
                status_code=201,
                connection=connection,
            )
            return result

    def revoke_share(
        self, tenant_id: str, share_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        scope = "DELETE:/api/shares/{share_id}"
        with self.database.transaction() as connection:
            request_hash, replay = self._idempotency_begin(
                tenant_id,
                scope,
                idempotency_key,
                {"shareId": share_id},
                connection=connection,
            )
            if replay is not None:
                return replay
            self.database.revoke_share(tenant_id, share_id, connection=connection)
            result = {"state": "revoked", "id": share_id}
            self._idempotency_complete(
                tenant_id,
                scope,
                idempotency_key,
                request_hash,
                result,
                status_code=202,
                connection=connection,
            )
            return result

    def delete_job(
        self, tenant_id: str, job_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        scope = "DELETE:/api/jobs/{job_id}"
        with self.database.transaction() as connection:
            request_hash, replay = self._idempotency_begin(
                tenant_id,
                scope,
                idempotency_key,
                {"jobId": job_id},
                connection=connection,
            )
            if replay is not None:
                return replay
            self.database.queue_delete_job(tenant_id, job_id, connection=connection)
            result = {"state": "deleting", "id": job_id}
            self._idempotency_complete(
                tenant_id,
                scope,
                idempotency_key,
                request_hash,
                result,
                status_code=202,
                connection=connection,
            )
        self.drain_deletions()
        return result

    def delete_asset(
        self, tenant_id: str, asset_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        scope = "DELETE:/api/assets/{asset_id}"
        with self.database.transaction() as connection:
            request_hash, replay = self._idempotency_begin(
                tenant_id,
                scope,
                idempotency_key,
                {"assetId": asset_id},
                connection=connection,
            )
            if replay is not None:
                return replay
            self.database.queue_delete_asset(tenant_id, asset_id, connection=connection)
            result = {"state": "deleting", "id": asset_id}
            self._idempotency_complete(
                tenant_id,
                scope,
                idempotency_key,
                request_hash,
                result,
                status_code=202,
                connection=connection,
            )
        self.drain_deletions()
        return result

    def bulk_delete(
        self,
        tenant_id: str,
        *,
        job_ids: list[str],
        asset_ids: list[str],
        share_ids: list[str],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        scope = "POST:/api/bulk-delete"
        payload = {
            "jobIds": sorted(set(job_ids)),
            "assetIds": sorted(set(asset_ids)),
            "shareIds": sorted(set(share_ids)),
        }
        with self.database.transaction() as connection:
            request_hash, replay = self._idempotency_begin(
                tenant_id,
                scope,
                idempotency_key,
                payload,
                connection=connection,
            )
            if replay is not None:
                return replay
            result: dict[str, list[str]] = {"jobs": [], "assets": [], "shares": []}
            errors: dict[str, str] = {}
            preexisting_assets = self.database.existing_asset_ids(
                tenant_id, payload["assetIds"], connection=connection
            )
            for share_id in payload["shareIds"]:
                try:
                    self.database.revoke_share(tenant_id, share_id, connection=connection)
                    result["shares"].append(share_id)
                except KeyError as error:
                    errors[share_id] = str(error)
            for job_id in payload["jobIds"]:
                try:
                    self.database.queue_delete_job(tenant_id, job_id, connection=connection)
                    result["jobs"].append(job_id)
                except (KeyError, InvalidTransition) as error:
                    errors[job_id] = str(error)
            for asset_id in payload["assetIds"]:
                try:
                    self.database.queue_delete_asset(tenant_id, asset_id, connection=connection)
                    result["assets"].append(asset_id)
                except KeyError as error:
                    # A selected terminal job can atomically cascade its last source
                    # upload.  An explicitly selected upload that existed at the start
                    # is therefore already accepted, not a false per-record failure.
                    if asset_id in preexisting_assets:
                        result["assets"].append(asset_id)
                    else:
                        errors[asset_id] = str(error)
                except InvalidTransition as error:
                    errors[asset_id] = str(error)
            response: dict[str, Any] = {
                "state": "deleting",
                "accepted": result,
                "errors": errors,
            }
            if not any(result.values()):
                self.database.abandon_idempotency(
                    tenant_id,
                    scope,
                    idempotency_key,
                    request_hash,
                    connection=connection,
                )
                return response
            self._idempotency_complete(
                tenant_id,
                scope,
                idempotency_key,
                request_hash,
                response,
                status_code=202,
                connection=connection,
            )
        self.drain_deletions()
        return response

    def drain_deletions(self, *, limit: int = 100) -> int:
        completed = 0
        for deletion in self.database.due_deletions(limit=limit):
            try:
                self.store.delete(deletion["object_key"])
            except Exception as error:
                logger.warning(
                    "object deletion %s failed: %s", deletion["id"], type(error).__name__
                )
                self.database.fail_deletion(deletion["id"], str(error))
            else:
                self.database.complete_deletion(deletion["id"])
                completed += 1
        return completed

    def run_retention(self) -> dict[str, int]:
        now = time.time()
        return self.database.run_retention(
            terminal_before=now - self.settings.terminal_job_retention_seconds,
            unattached_before=now - self.settings.unattached_asset_retention_seconds,
        )

    def reconcile_storage(self) -> dict[str, int]:
        stored = set(self.store.iter_keys("tenants"))
        known = self.database.known_object_keys()
        active = self.database.active_object_keys()
        orphans = 0
        for key in sorted(stored - known):
            parts = key.split("/", 3)
            if len(parts) < 3 or parts[0] != "tenants":
                continue
            try:
                with self.store.open(key) as stream:
                    stream.seek(0, 2)
                    size = stream.tell()
            except Exception:
                size = 0
            self.database.queue_orphan_object(parts[1], key, size)
            orphans += 1
        self._reconciliation_missing = active - stored
        return {"orphans": orphans, "missing": len(self._reconciliation_missing)}

    def export_health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "database": str(self.database.path),
            "storage": type(self.store).__name__,
            "worker": bool(self._worker and self._worker.is_alive()),
        }

    def ready(self, *, require_worker: bool) -> bool:
        """Check the durable dependencies without exposing their paths."""

        now = time.monotonic()
        worker_ready = not require_worker or bool(self._worker and self._worker.is_alive())
        if not worker_ready or self._reconciliation_missing:
            return False
        with self._readiness_lock:
            if (
                now - self._readiness_checked_at <= self.settings.readiness_probe_ttl_seconds
                and self._readiness_value
            ):
                return True
            probe_key = ".health/readiness.probe"
            try:
                with self.database.connect() as connection:
                    row = connection.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
                if row is None or int(row[0]) != SCHEMA_VERSION:
                    self._readiness_value = False
                else:
                    self.store.put_bytes(probe_key, b"1", max_bytes=1)
                    self.store.delete(probe_key)
                    self._readiness_value = True
            except Exception:
                self._readiness_value = False
            finally:
                self._readiness_checked_at = now
                with suppress(Exception):
                    self.store.delete(probe_key)
            return self._readiness_value

    def write_runtime_manifest(self) -> None:
        manifest = {
            "schemaVersion": 2,
            "environment": self.settings.environment,
            "storage": {
                "driver": type(self.store).__name__,
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
