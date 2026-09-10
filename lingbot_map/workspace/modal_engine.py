"""Private Modal transport with bounded execution and durable cleanup records."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
import time
import uuid
from contextlib import suppress
from pathlib import Path

from .config import RESEARCH_ACKNOWLEDGEMENT, Settings
from .database import Database, QuotaExceeded
from .engines import (
    EngineDescriptor,
    EngineResult,
    EngineUnavailable,
    JobCancelled,
    LingbotResearchEngine,
    ProducedArtifact,
    _public_report,
    _validate_glb,
    cleanup_result,
)
from .runner_contract import (
    CAPTURE_VOLUME,
    MAX_FRAMES,
    MODAL_APP,
    MODEL_SHA256,
    REMOTE_TIMEOUT,
    sampled_frame_count,
)

logger = logging.getLogger(__name__)


class ModalLingbotEngine(LingbotResearchEngine):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = Database(settings.data_dir / "workspace.sqlite3")

    @property
    def descriptor(self) -> EngineDescriptor:
        reasons = (
            ()
            if self.settings.research_acknowledgement == RESEARCH_ACKNOWLEDGEMENT
            else ("The operator has not acknowledged the research-preview terms.",)
        )
        return EngineDescriptor(
            id="lingbot-research-v1",
            name="LingBot-Map on Modal",
            available=not reasons,
            research_only=True,
            commercially_cleared=False,
            unavailable_reasons=reasons,
        )

    def provenance(self):
        return {
            "engine": self.descriptor.id,
            "researchOnly": True,
            "commerciallyCleared": False,
            "checkpointSha256": MODEL_SHA256,
            "runner": "Modal",
            "modelInference": True,
        }

    def estimate_units(self, source_metadata, params):
        if not source_metadata:
            raise ValueError("A validated capture is required")
        if (
            params.get("maskSky")
            or params.get("rotate")
            or params.get("mode", "streaming") != "streaming"
        ):
            raise ValueError(
                "The beta supports streaming reconstruction without sky masking or rotation"
            )
        # Earlier uploads persisted milliseconds only. Reserve the upper rounding
        # boundary for those rows; new metadata uses the decoder's exact timing.
        duration = source_metadata.get("samplingDurationSeconds")
        if duration is None:
            duration = float(source_metadata["durationSeconds"]) + 0.0005
        return sampled_frame_count(
            float(duration),
            int(source_metadata["frames"]),
            int(params.get("maxFrames", MAX_FRAMES)),
            int(params.get("extractFps", 3)),
        )

    def reserve_run(self, attempt_id: str, job_id: str, deadline: float) -> None:
        now = time.time()
        # A rolling 30-day budget is conservative: every submission is charged its
        # maximum GPU runtime, including failures, and retries reserve another slot.
        with self.database.transaction() as connection:
            used = (
                connection.execute(
                    "SELECT COUNT(*) FROM remote_runs WHERE created_at>?", (now - 30 * 86400,)
                ).fetchone()[0]
                * REMOTE_TIMEOUT
            )
            if used + REMOTE_TIMEOUT > self.settings.modal_gpu_seconds_budget:
                raise QuotaExceeded("The beta's GPU allowance is used up. Please try again later.")
            connection.execute(
                "INSERT INTO remote_runs(attempt_id,job_id,created_at,cleanup_after) "
                "VALUES (?,?,?,?)",
                # A spawn can succeed remotely before its call ID is persisted.
                # Let even a last-moment start finish before deleting its prefix.
                (attempt_id, job_id, now, deadline + REMOTE_TIMEOUT + 120),
            )

    def cleanup_remote_runs(self):
        asyncio.run(self._cleanup_remote_runs())

    async def _cleanup_remote_runs(self):
        with self.database.transaction() as connection:
            connection.execute(
                "DELETE FROM remote_runs WHERE cleaned=1 AND created_at<?",
                (time.time() - 31 * 86400,),
            )
            rows = connection.execute(
                "SELECT * FROM remote_runs WHERE cleaned=0 AND cleanup_after<? "
                "ORDER BY cleanup_after LIMIT 5",
                (time.time(),),
            ).fetchall()
        if not rows:
            return
        import modal

        volume = modal.Volume.from_name(CAPTURE_VOLUME)
        for row in rows:
            try:
                async with asyncio.timeout(2):
                    if row["call_id"]:
                        with suppress(modal.exception.NotFoundError):
                            await modal.FunctionCall.from_id(row["call_id"]).cancel.aio(
                                terminate_containers=True
                            )
                    with suppress(FileNotFoundError, modal.exception.NotFoundError):
                        await volume.remove_file.aio("/" + row["attempt_id"], recursive=True)
                with self.database.transaction() as connection:
                    connection.execute(
                        "UPDATE remote_runs SET cleaned=1 WHERE attempt_id=?", (row["attempt_id"],)
                    )
            except Exception:
                logger.warning("Remote capture cleanup will be retried")
                with self.database.transaction() as connection:
                    connection.execute(
                        "UPDATE remote_runs SET cleanup_after=? WHERE attempt_id=?",
                        (time.time() + 60, row["attempt_id"]),
                    )

    def run(self, context, progress, cancelled):
        if not self.descriptor.available:
            raise EngineUnavailable("; ".join(self.descriptor.unavailable_reasons))
        if context.source_path is None:
            raise ValueError("A source video is required")
        if cancelled():
            raise JobCancelled("Cancelled before upload")
        return asyncio.run(self._run_with_cancellation(context, progress, cancelled))

    async def _run_with_cancellation(self, context, progress, cancelled):
        async def watch_cancellation():
            while not cancelled():
                await asyncio.sleep(0.1)
            raise JobCancelled("Reconstruction cancelled")

        work = asyncio.create_task(self._run_remote(context, progress))
        watcher = asyncio.create_task(watch_cancellation())
        delivered = False
        try:
            async with asyncio.timeout(self.settings.job_timeout_seconds):
                done, _ = await asyncio.wait((work, watcher), return_when=asyncio.FIRST_COMPLETED)
                if watcher in done:
                    await watcher
                result = await work
                delivered = True
                return result
        finally:
            for task in (work, watcher):
                task.cancel()
            for task in (work, watcher):
                with suppress(asyncio.CancelledError, Exception):
                    await task
            if not delivered and not work.cancelled() and work.exception() is None:
                cleanup_result(work.result())

    async def _run_remote(self, context, progress):
        import modal

        frame_limit = self.estimate_units(context.source_metadata, context.params)
        if context.reserved_units is not None:
            # Resumed jobs may predate precise timing metadata. Never ask the
            # runner for more frames than their persisted capacity reservation.
            frame_limit = min(frame_limit, context.reserved_units)
        if frame_limit < 2:
            raise ValueError("The capture reservation does not permit reconstruction")
        attempt = uuid.uuid4().hex
        deadline = time.time() + self.settings.job_timeout_seconds
        self.reserve_run(attempt, context.job_id, deadline)
        work_dir = Path(tempfile.mkdtemp(prefix=f"{context.job_id}-", dir=context.work_root))
        volume = modal.Volume.from_name(CAPTURE_VOLUME)
        call = None
        succeeded = False
        try:
            progress("uploading_to_gpu", 0.15)
            async with volume.batch_upload.aio() as batch:
                batch.put_file(str(context.source_path), f"/{attempt}/source.video")
            function = modal.Function.from_name(MODAL_APP, "reconstruct")
            call = await function.spawn.aio(
                attempt_id=attempt,
                research_ack=self.settings.research_acknowledgement,
                max_frames=frame_limit,
                extract_fps=int(context.params.get("extractFps", 3)),
                expires_at=deadline,
            )
            with self.database.transaction() as connection:
                connection.execute(
                    "UPDATE remote_runs SET call_id=? WHERE attempt_id=?", (call.object_id, attempt)
                )
            progress("reconstructing", 0.3)
            raw_report = await call.get.aio()
            progress("exporting", 0.85)
            path = work_dir / "scene.glb"
            size = 0
            with path.open("wb") as stream:
                async for chunk in volume.read_file.aio(f"/{attempt}/scene.glb"):
                    size += len(chunk)
                    if size > self.settings.max_artifact_bytes:
                        raise ValueError("Reconstruction exceeds the artifact size limit")
                    stream.write(chunk)
            path.chmod(0o600)
            _validate_glb(path)
            if not isinstance(raw_report, dict):
                raise ValueError("The runner returned an invalid report")
            report = _public_report(raw_report)
            if report.get("checkpointSha256") != MODEL_SHA256:
                raise ValueError("The runner used an unexpected checkpoint")
            used_units = report.get("frames")
            if type(used_units) is not int or not 2 <= used_units <= frame_limit:
                raise ValueError("The runner returned an invalid sampled-frame count")
            result = EngineResult(
                artifacts=(
                    ProducedArtifact(
                        kind="scene",
                        filename="wayline-space.glb",
                        media_type="model/gltf-binary",
                        license_id="NOASSERTION",
                        path=path,
                        metadata={**report, "researchOnly": True},
                    ),
                    ProducedArtifact(
                        kind="manifest",
                        filename="reconstruction.json",
                        media_type="application/json",
                        license_id="NOASSERTION",
                        payload=json.dumps(report).encode(),
                    ),
                ),
                used_units=used_units,
                report=report,
                cleanup_dir=work_dir,
            )
            succeeded = True
            return result
        finally:
            if call is not None and not succeeded:
                try:
                    async with asyncio.timeout(10):
                        await call.cancel.aio(terminate_containers=True)
                except Exception:
                    logger.warning("GPU cancellation will be retried by cleanup")
            if not succeeded:
                shutil.rmtree(work_dir, ignore_errors=True)
            else:
                # Cleanup failure must not discard a valid downloaded result.
                try:
                    with self.database.transaction() as connection:
                        connection.execute(
                            "UPDATE remote_runs SET cleanup_after=? WHERE attempt_id=?",
                            (time.time(), attempt),
                        )
                except Exception:
                    logger.warning("Remote cleanup will use its reserved deadline")
