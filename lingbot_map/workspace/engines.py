"""Pluggable reconstruction engines and the gated LingBot research adapter."""

from __future__ import annotations

import json
import math
import os
import shlex
import shutil
import signal
import struct
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lingbot_map.checkpoints import CheckpointRejected, materialize_verified_checkpoint

from .config import RESEARCH_ACKNOWLEDGEMENT, Settings
from .sample import SAMPLE_LICENSE_ID, SAMPLE_VERSION, build_synthetic_scene, sample_manifest

ProgressCallback = Callable[[str, float], None]
CancellationCallback = Callable[[], bool]
RUNNER_ENV_ALLOWLIST = {
    "CUDA_VISIBLE_DEVICES",
    "DYLD_LIBRARY_PATH",
    "LANG",
    "LC_ALL",
    "LD_LIBRARY_PATH",
    "MKL_NUM_THREADS",
    "NVIDIA_DRIVER_CAPABILITIES",
    "NVIDIA_VISIBLE_DEVICES",
    "OMP_NUM_THREADS",
    "PATH",
    "PYTHONPATH",
}


class EngineUnavailable(RuntimeError):
    pass


class JobCancelled(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EngineDescriptor:
    id: str
    name: str
    available: bool
    research_only: bool
    commercially_cleared: bool
    unavailable_reasons: tuple[str, ...] = ()


@dataclass(slots=True)
class EngineContext:
    job_id: str
    tenant_id: str
    params: dict[str, Any]
    source_path: Path | None
    source_metadata: dict[str, Any] | None
    work_root: Path


@dataclass(frozen=True, slots=True)
class ProducedArtifact:
    kind: str
    filename: str
    media_type: str
    license_id: str
    payload: bytes | None = None
    path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EngineResult:
    artifacts: tuple[ProducedArtifact, ...]
    used_units: int
    report: dict[str, Any]
    cleanup_dir: Path | None = None


class ReconstructionEngine(ABC):
    @property
    @abstractmethod
    def descriptor(self) -> EngineDescriptor: ...

    @abstractmethod
    def estimate_units(
        self, source_metadata: dict[str, Any] | None, params: dict[str, Any]
    ) -> int: ...

    @abstractmethod
    def provenance(self) -> dict[str, Any]: ...

    @abstractmethod
    def run(
        self,
        context: EngineContext,
        progress: ProgressCallback,
        cancelled: CancellationCallback,
    ) -> EngineResult: ...


def _validate_glb(path: Path) -> None:
    """Validate the fixed GLB header before a runner output reaches storage."""

    size = path.stat().st_size
    if size < 20 or size > 100 * 1024 * 1024:
        raise RuntimeError("research scene must be a GLB between 20 bytes and 100 MiB")
    with path.open("rb") as stream:
        magic, version, declared_size = struct.unpack("<III", stream.read(12))
    if magic != 0x46546C67 or version != 2 or declared_size != size:
        raise RuntimeError("research runner produced an invalid GLB 2.0 header")


def _public_report(value: dict[str, Any]) -> dict[str, Any]:
    """Allowlist bounded, non-sensitive runner metrics for API/share responses."""

    result: dict[str, Any] = {}
    numeric_keys = {
        "frames",
        "inferenceSeconds",
        "totalSeconds",
        "peakVramBytes",
        "artifactBytes",
        "pointCount",
    }
    string_keys = {"engineVersion", "license", "sourceRevision", "checkpointSha256"}
    for key in numeric_keys:
        item = value.get(key)
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            number = float(item)
            if math.isfinite(number) and number >= 0:
                result[key] = item
    for key in string_keys:
        item = value.get(key)
        if isinstance(item, str) and len(item) <= 128:
            result[key] = item
    for key in ("researchOnly", "commerciallyCleared"):
        if isinstance(value.get(key), bool):
            result[key] = value[key]
    warnings = value.get("warnings")
    if isinstance(warnings, list):
        result["warnings"] = [
            item for item in warnings[:10] if isinstance(item, str) and len(item) <= 300
        ]
    return result


class SyntheticSampleEngine(ReconstructionEngine):
    @property
    def descriptor(self) -> EngineDescriptor:
        return EngineDescriptor(
            id="synthetic-sample-v1",
            name="Synthetic workspace sample",
            available=True,
            research_only=False,
            commercially_cleared=True,
        )

    def estimate_units(self, source_metadata: dict[str, Any] | None, params: dict[str, Any]) -> int:
        return 1

    def provenance(self) -> dict[str, Any]:
        return {
            "engine": self.descriptor.id,
            "sampleVersion": SAMPLE_VERSION,
            "license": SAMPLE_LICENSE_ID,
            "sourceImages": False,
            "modelInference": False,
        }

    def run(
        self,
        context: EngineContext,
        progress: ProgressCallback,
        cancelled: CancellationCallback,
    ) -> EngineResult:
        progress("generating", 0.35)
        if cancelled():
            raise JobCancelled("cancelled before sample generation")
        scene = build_synthetic_scene()
        progress("exporting", 0.8)
        return EngineResult(
            artifacts=(
                ProducedArtifact(
                    kind="scene",
                    filename="synthetic-studio.glb",
                    media_type="model/gltf-binary",
                    license_id=SAMPLE_LICENSE_ID,
                    payload=scene.glb,
                    metadata={"pointCount": scene.point_count, "bounds": scene.bounds},
                ),
                ProducedArtifact(
                    kind="manifest",
                    filename="synthetic-studio-manifest.json",
                    media_type="application/json",
                    license_id=SAMPLE_LICENSE_ID,
                    payload=sample_manifest(scene),
                    metadata={"sampleVersion": SAMPLE_VERSION},
                ),
            ),
            # The reservation exercises quota/refund behavior, but a generated
            # sample consumes no model-compute units.
            used_units=0,
            report={"kind": "synthetic", "pointCount": scene.point_count},
        )


class LingbotResearchEngine(ReconstructionEngine):
    """Command adapter isolated behind explicit rights and integrity gates.

    The command is never evaluated through a shell. It receives a job manifest
    and output directory via environment variables and must create ``scene.glb``
    plus an optional ``report.json``. This keeps a future Modal/Kubernetes runner
    outside the web process and gives hosted deployments a stable boundary.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._checkpoint_cache = settings.data_dir / "verified-checkpoints"

    def _reasons(self) -> list[str]:
        reasons = []
        if self.settings.research_acknowledgement != RESEARCH_ACKNOWLEDGEMENT:
            reasons.append("research-only acknowledgement is missing")
        if not self.settings.research_command:
            reasons.append("research runner command is not configured")
        if not self.settings.checkpoint_path:
            reasons.append("checkpoint path is not configured")
        if not self.settings.checkpoint_sha256:
            reasons.append("checkpoint SHA-256 is not configured")
        return reasons

    @property
    def descriptor(self) -> EngineDescriptor:
        reasons = self._reasons()
        return EngineDescriptor(
            id="lingbot-research-v1",
            name="LingBot research adapter",
            available=not reasons,
            research_only=True,
            commercially_cleared=False,
            unavailable_reasons=tuple(reasons),
        )

    def estimate_units(self, source_metadata: dict[str, Any] | None, params: dict[str, Any]) -> int:
        if not source_metadata:
            raise ValueError("LingBot jobs require a validated video asset")
        if params.get("maskSky") and (
            not self.settings.skyseg_path or not self.settings.skyseg_sha256
        ):
            raise EngineUnavailable(
                "sky masking requires a path and exact SHA-256 for the auxiliary model"
            )
        requested = int(params.get("maxFrames") or source_metadata.get("frames") or 1)
        return max(1, min(requested, int(source_metadata.get("frames") or requested)))

    def provenance(self) -> dict[str, Any]:
        return {
            "engine": self.descriptor.id,
            "researchOnly": True,
            "commerciallyCleared": False,
            "rightsStatus": "checkpoint and training-data commercial rights unresolved",
            "checkpointSha256": self.settings.checkpoint_sha256 or None,
            "skysegSha256": self.settings.skyseg_sha256 or None,
        }

    def _checkpoint(self) -> dict[str, Any]:
        if not self.settings.checkpoint_path:
            raise EngineUnavailable("checkpoint path is not configured")
        try:
            return materialize_verified_checkpoint(
                self.settings.checkpoint_path,
                self.settings.checkpoint_sha256,
                self.settings.checkpoint_max_bytes,
                self._checkpoint_cache,
            )
        except CheckpointRejected as error:
            raise EngineUnavailable(str(error)) from error

    def _skyseg(self) -> dict[str, Any]:
        if not self.settings.skyseg_path:
            raise EngineUnavailable("sky segmentation path is not configured")
        try:
            return materialize_verified_checkpoint(
                self.settings.skyseg_path,
                self.settings.skyseg_sha256,
                self.settings.skyseg_max_bytes,
                self._checkpoint_cache,
            )
        except CheckpointRejected as error:
            raise EngineUnavailable(f"sky segmentation model: {error}") from error

    def run(
        self,
        context: EngineContext,
        progress: ProgressCallback,
        cancelled: CancellationCallback,
    ) -> EngineResult:
        descriptor = self.descriptor
        if not descriptor.available:
            raise EngineUnavailable("; ".join(descriptor.unavailable_reasons))
        if context.source_path is None:
            raise ValueError("LingBot jobs require a source video")
        checkpoint = self._checkpoint()
        skyseg = self._skyseg() if context.params.get("maskSky") else None
        work_dir = Path(tempfile.mkdtemp(prefix=f"{context.job_id}-", dir=context.work_root))
        output_dir = work_dir / "output"
        output_dir.mkdir(mode=0o700)
        public_manifest = {
            "schemaVersion": 1,
            "jobId": context.job_id,
            "sourceMetadata": context.source_metadata,
            "parameters": context.params,
            "checkpoint": {
                "sha256": checkpoint["sha256"],
                "sizeBytes": checkpoint["sizeBytes"],
            },
            "rights": self.provenance(),
        }
        if skyseg:
            public_manifest["auxiliaryModel"] = {
                "sha256": skyseg["sha256"],
                "sizeBytes": skyseg["sizeBytes"],
            }
        execution_manifest = {
            **public_manifest,
            "tenantId": context.tenant_id,
            "sourcePath": str(context.source_path),
            "checkpointPath": checkpoint["path"],
        }
        if skyseg:
            execution_manifest["skysegPath"] = skyseg["path"]
        manifest_path = work_dir / "job.json"
        manifest_path.write_text(
            json.dumps(execution_manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.chmod(manifest_path, 0o600)
        command = shlex.split(self.settings.research_command)
        if not command:
            raise EngineUnavailable("research runner command is empty")
        runner_home = work_dir / "home"
        runner_tmp = work_dir / "tmp"
        runner_home.mkdir(mode=0o700)
        runner_tmp.mkdir(mode=0o700)
        environment = {
            key: value for key, value in os.environ.items() if key in RUNNER_ENV_ALLOWLIST
        }
        environment.update(
            {
                "HOME": str(runner_home),
                "LINGBOT_JOB_MANIFEST": str(manifest_path),
                "LINGBOT_OUTPUT_DIR": str(output_dir),
                "LINGBOT_CHECKPOINT_PATH": str(checkpoint["path"]),
                "TMPDIR": str(runner_tmp),
            }
        )
        if skyseg:
            environment["LINGBOT_SKYSEG_PATH"] = str(skyseg["path"])
        log_path = work_dir / "runner.log"
        progress("reconstructing", 0.25)
        started = time.monotonic()
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                command,
                cwd=work_dir,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            while process.poll() is None:
                if cancelled():
                    self._terminate(process)
                    raise JobCancelled("research job cancelled")
                if time.monotonic() - started > self.settings.job_timeout_seconds:
                    self._terminate(process)
                    raise TimeoutError("research runner exceeded its time limit")
                log.flush()
                if log_path.stat().st_size > 10 * 1024 * 1024:
                    self._terminate(process)
                    raise RuntimeError("research runner log exceeded 10 MiB")
                time.sleep(0.25)
        if process.returncode != 0:
            raise RuntimeError(f"research runner exited with code {process.returncode}")
        scene = output_dir / "scene.glb"
        if scene.is_symlink() or not scene.is_file():
            raise RuntimeError("research runner did not produce a regular scene.glb")
        _validate_glb(scene)
        report_path = output_dir / "report.json"
        report: dict[str, Any] = {}
        if report_path.exists():
            if report_path.is_symlink() or report_path.stat().st_size > 1024 * 1024:
                raise RuntimeError("research report must be a regular JSON file under 1 MiB")
            raw_report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(raw_report, dict):
                raise RuntimeError("research report must contain a JSON object")
            report = _public_report(raw_report)
        progress("exporting", 0.85)
        return EngineResult(
            artifacts=(
                ProducedArtifact(
                    kind="scene",
                    filename="scene.glb",
                    media_type="model/gltf-binary",
                    license_id="NOASSERTION",
                    path=scene,
                    metadata={"researchOnly": True, "report": report},
                ),
                ProducedArtifact(
                    kind="manifest",
                    filename="job-manifest.json",
                    media_type="application/json",
                    license_id="NOASSERTION",
                    payload=(json.dumps(public_manifest, indent=2, sort_keys=True) + "\n").encode(
                        "utf-8"
                    ),
                    metadata={"researchOnly": True},
                ),
            ),
            used_units=self.estimate_units(context.source_metadata, context.params),
            report=report,
            cleanup_dir=work_dir,
        )

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            with suppress(ProcessLookupError):
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            # Always reap the direct child. A second timeout is exceptional and
            # must surface rather than leaving a zombie behind silently.
            process.wait(timeout=5)


def engine_registry(settings: Settings) -> dict[str, ReconstructionEngine]:
    from .modal_engine import ModalLingbotEngine

    engine = (
        ModalLingbotEngine(settings) if settings.modal_enabled else LingbotResearchEngine(settings)
    )
    engines: list[ReconstructionEngine] = [SyntheticSampleEngine(), engine]
    return {engine.descriptor.id: engine for engine in engines}


def cleanup_result(result: EngineResult | None) -> None:
    if result and result.cleanup_dir:
        shutil.rmtree(result.cleanup_dir, ignore_errors=True)
