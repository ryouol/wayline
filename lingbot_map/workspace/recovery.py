"""Nightly encrypted offsite recovery sets for the single Render instance.

The allowance counts application upload reservations, including failed attempts;
it does not measure the SDK's internal network retries or provider invoice.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
from pathlib import Path

from .backup import create_snapshot, digest, referenced_objects

logger = logging.getLogger(__name__)
DAY = 86400
MAX_SNAPSHOT_BYTES = 4 * 1024**3
DEFAULT_UPLOAD_BUDGET = 10 * 1024**3
PART_BYTES = 8 * 1024**2
MARKER_BYTES = 128 * 1024
STATE_NAME = "recovery-state.json"
PREFIX = re.compile(r"^/scheduled/[0-9]{10}-[a-f0-9]{32}$")
ENVIRONMENT_KEYS = frozenset(
    [
        "LINGBOT_ENV",
        "LINGBOT_DATA_DIR",
        "LINGBOT_BOOTSTRAP_TOKEN",
        "LINGBOT_TENANT_NAME",
        "LINGBOT_COOKIE_SECURE",
        "LINGBOT_SESSION_TTL_SECONDS",
        "LINGBOT_MAX_UPLOAD_BYTES",
        "LINGBOT_UPLOAD_TIMEOUT_SECONDS",
        "LINGBOT_MAX_ARTIFACT_BYTES",
        "LINGBOT_GLOBAL_STORAGE_BYTES",
        "LINGBOT_STORAGE_MIN_FREE_BYTES",
        "LINGBOT_GLOBAL_MAX_INFLIGHT_OBJECTS",
        "LINGBOT_TENANT_MAX_INFLIGHT_OBJECTS",
        "LINGBOT_MAX_VIDEO_SECONDS",
        "LINGBOT_MAX_VIDEO_FRAMES",
        "LINGBOT_MAX_VIDEO_DIMENSION",
        "LINGBOT_TENANT_QUOTA_UNITS",
        "LINGBOT_TENANT_STORAGE_BYTES",
        "LINGBOT_TENANT_MAX_ASSETS",
        "LINGBOT_TENANT_MAX_UNATTACHED_ASSETS",
        "LINGBOT_TENANT_MAX_JOBS",
        "LINGBOT_TENANT_MAX_ARTIFACTS",
        "LINGBOT_TENANT_MAX_SHARES",
        "LINGBOT_UPLOAD_RATE_PER_MINUTE",
        "LINGBOT_JOB_RATE_PER_MINUTE",
        "LINGBOT_SHARE_RATE_PER_MINUTE",
        "LINGBOT_TERMINAL_JOB_RETENTION_SECONDS",
        "LINGBOT_UNATTACHED_ASSET_RETENTION_SECONDS",
        "LINGBOT_IDEMPOTENCY_TTL_SECONDS",
        "LINGBOT_SHUTDOWN_TIMEOUT_SECONDS",
        "LINGBOT_READINESS_PROBE_TTL_SECONDS",
        "LINGBOT_WORKER_POLL_SECONDS",
        "LINGBOT_JOB_TIMEOUT_SECONDS",
        "LINGBOT_MAX_JOB_ATTEMPTS",
        "LINGBOT_PUBLIC_BASE_URL",
        "LINGBOT_ALLOWED_HOSTS",
        "LINGBOT_RESEARCH_ACK",
        "WAYLINE_SCENE_DELIVERY_BUDGET_BYTES",
        "WAYLINE_SIGNUP_ENABLED",
        "WAYLINE_TRIAL_ENABLED",
        "WAYLINE_GOOGLE_CLIENT_ID",
        "WAYLINE_GOOGLE_CLIENT_SECRET",
        "WAYLINE_SIGNUP_MAX_ACCOUNTS",
        "WAYLINE_TRIAL_MAX_ACCOUNTS",
        "WAYLINE_SIGNUP_QUOTA_UNITS",
        "WAYLINE_MODAL_ENABLED",
        "WAYLINE_GPU_SECONDS_BUDGET",
        "MODAL_TOKEN_ID",
        "MODAL_TOKEN_SECRET",
        "WAYLINE_RECOVERY_RECIPIENT",
        "WAYLINE_RECOVERY_VOLUME_ID",
        "WAYLINE_RECOVERY_UPLOAD_BUDGET_BYTES",
        "RENDER_SERVICE_ID",
        "RENDER_GIT_COMMIT",
    ]
)


class RecoveryFailure(Exception):
    """Safe operator-facing failure category, without provider exception text."""


def load_state(data_dir: Path) -> dict:
    path = data_dir / STATE_NAME
    if not path.exists():
        return {"format": 1, "last_attempt": 0, "last_success": 0, "attempts": []}
    if path.is_symlink():
        raise RecoveryFailure("invalid_state")
    state = json.loads(path.read_text())
    if state.get("format") != 1 or not isinstance(state.get("attempts"), list):
        raise RecoveryFailure("invalid_state")
    for attempt in state["attempts"]:
        if not PREFIX.fullmatch(attempt["prefix"]):
            raise RecoveryFailure("invalid_state")
    return state


def save_state(data_dir: Path, state: dict) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", dir=data_dir, prefix=".recovery-", delete=False
    ) as out:
        temporary = Path(out.name)
        try:
            json.dump(state, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
            os.replace(temporary, data_dir / STATE_NAME)
        finally:
            temporary.unlink(missing_ok=True)
    descriptor = os.open(data_dir, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def encrypt_snapshot(snapshot: Path, target: Path, recipient: str, environment: dict) -> None:
    """Stream tar directly to age; no plaintext tar or environment file is written."""
    age = shutil.which("age")
    if age is None:
        raise RecoveryFailure("age_unavailable")
    payload = json.dumps({"format": 1, "envVars": environment}, sort_keys=True).encode()
    if len(payload) > 65536:
        raise RecoveryFailure("environment_too_large")
    with target.open("xb") as output:
        target.chmod(0o600)
        process = subprocess.Popen(
            [age, "-r", recipient], stdin=subprocess.PIPE, stdout=output, stderr=subprocess.DEVNULL
        )
        try:
            assert process.stdin is not None
            with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
                archive.add(snapshot, arcname="workspace", recursive=True)
                info = tarfile.TarInfo("environment.json")
                info.size, info.mode = len(payload), 0o600
                archive.addfile(info, io.BytesIO(payload))
            process.stdin.close()
            if process.wait(timeout=30) != 0:
                raise RecoveryFailure("encryption_failed")
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


class ModalRecoveryVolume:
    def __init__(self, volume_id: str):
        import modal

        self.volume = modal.Volume.from_id(volume_id)

    def upload(self, source: Path, remote: str) -> None:
        with self.volume.batch_upload() as batch:
            batch.put_file(source, remote)

    def read(self, remote: str):
        return self.volume.read_file(remote)

    def remove(self, prefix: str) -> None:
        import modal

        with contextlib.suppress(FileNotFoundError, modal.exception.NotFoundError):
            self.volume.remove_file(prefix, recursive=True)


def _reserved_bytes(state, now):
    return sum(
        reservation["bytes"]
        for item in state["attempts"]
        for reservation in item["reservations"]
        if reservation["at"] > now - 30 * DAY
    )


def _reserve_upload(data_dir, state, attempt, size, budget, now):
    if size < 0 or _reserved_bytes(state, now) + size > budget:
        raise RecoveryFailure("upload_allowance_exhausted")
    attempt["reservations"].append({"at": now, "bytes": size})
    save_state(data_dir, state)


def _upload_verified(source, remote, volume, reserved_bytes):
    size, expected = source.stat().st_size, digest(source)
    if size > reserved_bytes:
        raise RecoveryFailure("archive_exceeds_reservation")
    try:
        volume.upload(source, remote)
    except Exception as error:
        logger.warning("Recovery upload failed (%s)", type(error).__name__)
        raise RecoveryFailure("remote_upload_failed") from None
    for attempt in range(3):
        received, sha = 0, hashlib.sha256()
        try:
            for chunk in volume.read(remote):
                received += len(chunk)
                if received > size:
                    raise RecoveryFailure("remote_verification_failed")
                sha.update(chunk)
        except RecoveryFailure:
            raise
        except Exception as error:
            if attempt == 2:
                logger.warning("Recovery readback failed (%s)", type(error).__name__)
                raise RecoveryFailure("remote_readback_failed") from None
            # Refresh the SDK's download URLs after transient post-upload errors.
            # Retry only reads; never duplicate an uncertain upload.
            time.sleep((2, 5)[attempt])
            continue
        if received != size or sha.hexdigest() != expected:
            raise RecoveryFailure("remote_verification_failed")
        return {"bytes": size, "sha256": expected}
    raise RecoveryFailure("remote_verification_failed")


def _upload_archive(archive, prefix, volume, reserved_bytes):
    # Small sequential files avoid SDK concurrency based on the host's CPU/RAM.
    if archive.stat().st_size > reserved_bytes:
        raise RecoveryFailure("archive_exceeds_reservation")
    parts: list[dict] = []
    size, sha = 0, hashlib.sha256()
    part = archive.parent / "part.age"
    with archive.open("rb") as incoming:
        while chunk := incoming.read(PART_BYTES):
            size += len(chunk)
            if size > reserved_bytes:
                raise RecoveryFailure("archive_exceeds_reservation")
            sha.update(chunk)
            name = f"part-{len(parts):04d}.age"
            with part.open("xb") as output:
                part.chmod(0o600)
                output.write(chunk)
            del chunk
            try:
                metadata = _upload_verified(part, prefix + "/" + name, volume, PART_BYTES)
                parts.append({"name": name, **metadata})
            finally:
                part.unlink()
    return {"bytes": size, "sha256": sha.hexdigest(), "parts": parts}


def _retire(data_dir, state, volume, *, prune_completed=False, active_prefix=None):
    protected = {"complete", "retained"}
    completed = [item for item in state["attempts"] if item["status"] == "complete"]
    keep = {item["prefix"] for item in completed[-7:]}
    if len(completed) < 7:
        keep.update(item["prefix"] for item in state["attempts"] if item["status"] == "retained")
    for item in state["attempts"]:
        if (
            item["prefix"] in keep
            or item["prefix"] == active_prefix
            or item["status"] == "pruned"
            or (item["status"] in protected and not prune_completed)
        ):
            continue
        volume.remove(item["prefix"])
        item["status"] = "pruned"
        save_state(data_dir, state)


def run_once(
    data_dir: Path,
    recipient: str,
    volume_id: str,
    *,
    upload_budget_bytes: int = DEFAULT_UPLOAD_BUDGET,
    staging_root: Path = Path("/tmp"),
    now: float | None = None,
    volume=None,
    encrypt=encrypt_snapshot,
    environment: dict | None = None,
    retry_failed: bool = False,
) -> bool:
    """Admit daily work or one explicit failed-attempt retry per rolling day."""
    now = time.time() if now is None else now
    with (data_dir / ".recovery.lock").open("a+b") as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        state = load_state(data_dir)
        operator_retry = now - state["last_attempt"] < DAY
        if operator_retry:
            recent = [item for item in state["attempts"] if item["created_at"] > now - DAY]
            if (
                not retry_failed
                or len(recent) != 1
                or recent[0]["status"] != "failed"
                or recent[0].get("operator_retry", False)
            ):
                return False
        attempt: dict = {
            "prefix": f"/scheduled/{int(now):010d}-{uuid.uuid4().hex}",
            "created_at": now,
            "operator_retry": operator_retry,
            "status": "running",
            "reservations": [],
        }
        state["last_attempt"] = now
        state["attempts"].append(attempt)
        save_state(data_dir, state)
        temporary = staging_root / ("wayline-recovery-" + attempt["prefix"].rsplit("/", 1)[1])
        try:
            if staging_root.resolve().is_relative_to(data_dir.resolve()):
                raise RecoveryFailure("unsafe_staging_directory")
            state["attempts"] = [
                item
                for item in state["attempts"]
                if item["status"] != "pruned"
                or any(reservation["at"] > now - 30 * DAY for reservation in item["reservations"])
            ]
            save_state(data_dir, state)
            # Cleanup of previous partial uploads must continue when this month's
            # upload allowance is exhausted. Completed sets are preserved here.
            volume = volume if volume is not None else ModalRecoveryVolume(volume_id)
            _retire(data_dir, state, volume, active_prefix=attempt["prefix"])
            objects = referenced_objects(data_dir)
            estimate = sum(size for _, size, _ in objects)
            estimate += (data_dir / "workspace.sqlite3").stat().st_size
            if _reserved_bytes(state, now) + estimate + MARKER_BYTES > upload_budget_bytes:
                raise RecoveryFailure("upload_allowance_exhausted")
            estimate += 131072 + 2048 * len(objects)
            if estimate > MAX_SNAPSHOT_BYTES:
                raise RecoveryFailure("snapshot_too_large")
            if shutil.disk_usage(staging_root).free < 2 * estimate + 512 * 1024**2:
                raise RecoveryFailure("staging_space_low")
            temporary.mkdir(mode=0o700)
            snapshot = temporary / "workspace"
            manifest = create_snapshot(
                data_dir, snapshot, online=True, max_bytes=MAX_SNAPSHOT_BYTES
            )
            if sum(item["size"] for item in manifest["files"].values()) > MAX_SNAPSHOT_BYTES:
                raise RecoveryFailure("snapshot_too_large")
            selected = {
                key: value
                for key, value in (os.environ if environment is None else environment).items()
                if key in ENVIRONMENT_KEYS
            }
            # Reserve before encryption so the recovery set contains its own
            # conservative charges. Keep those charges even on an uncertain failure.
            total = sum(item["size"] for item in manifest["files"].values())
            archive_limit = total + total // 1024 + 4096 * len(manifest["files"]) + 512 * 1024
            _reserve_upload(data_dir, state, attempt, archive_limit, upload_budget_bytes, now)
            _reserve_upload(data_dir, state, attempt, MARKER_BYTES, upload_budget_bytes, now)
            state_copy = snapshot / STATE_NAME
            # A restore must protect its source archive until a newer verified
            # set exists. "retained" does not claim this live upload has finished.
            embedded_state = {
                **state,
                "attempts": [
                    {**item, "status": "retained"} if item is attempt else item
                    for item in state["attempts"]
                ],
            }
            state_bytes = json.dumps(embedded_state, sort_keys=True).encode()
            if len(state_bytes) > 256 * 1024:
                raise RecoveryFailure("recovery_state_too_large")
            state_copy.write_bytes(state_bytes)
            state_copy.chmod(0o600)
            manifest["files"][STATE_NAME] = {"size": len(state_bytes), "sha256": digest(state_copy)}
            (snapshot / "snapshot.json").write_text(json.dumps(manifest))
            archive = temporary / "workspace.tar.age"
            encrypt(snapshot, archive, recipient, selected)
            if archive.stat().st_size > MAX_SNAPSHOT_BYTES + 16 * 1024**2:
                raise RecoveryFailure("snapshot_too_large")
            metadata = _upload_archive(
                archive,
                attempt["prefix"],
                volume,
                archive_limit,
            )
            marker = temporary / "complete.json"
            marker.write_text(json.dumps({"format": 1, "created_at": now, "archive": metadata}))
            marker.chmod(0o600)
            _upload_verified(
                marker,
                attempt["prefix"] + "/complete.json",
                volume,
                MARKER_BYTES,
            )
            attempt.update(
                status="complete",
                archive={key: metadata[key] for key in ("bytes", "sha256")},
            )
            state["last_success"] = now
            save_state(data_dir, state)
            # A verified new set must exist before any old completed set is removed.
            _retire(data_dir, state, volume, prune_completed=True)
            logger.info("Recovery backup completed and verified")
            return True
        except Exception as error:
            category = str(error) if isinstance(error, RecoveryFailure) else "backup_failed"
            if attempt["status"] != "complete":
                attempt["status"] = "failed"
            attempt["error"] = category
            save_state(data_dir, state)
            logger.warning("Recovery backup requires attention: %s", category)
            return False
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)


class RecoveryWorker:
    """One supervisor thread; its child and age are killed together on shutdown."""

    def __init__(
        self,
        data_dir: Path,
        recipient: str,
        volume_id: str,
        *,
        upload_budget_bytes: int = DEFAULT_UPLOAD_BUDGET,
        staging_root: Path = Path("/tmp"),
        timeout_seconds: int = 900,
    ):
        self.data_dir, self.recipient, self.volume_id = data_dir, recipient, volume_id
        self.upload_budget_bytes = upload_budget_bytes
        self.staging_root, self.timeout_seconds = staging_root, timeout_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="recovery-worker", daemon=True)
        self._thread.start()

    def is_alive(self):
        return bool(self._thread and self._thread.is_alive())

    def stop(self, timeout=30):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise RuntimeError("recovery worker did not stop within shutdown deadline")

    def _loop(self):
        was_stale = False
        while not self._stop.is_set():
            try:
                self._recover_interrupted()
                state = load_state(self.data_dir)
                stale = time.time() - state["last_success"] > 36 * 3600
                if stale and not was_stale:
                    logger.warning("Recovery backup is stale: no verified set within 36 hours")
                was_stale = stale
                if time.time() - state["last_attempt"] >= DAY:
                    self._run_child()
            except Exception:
                logger.warning("Recovery supervisor requires attention")
            self._stop.wait(60)

    def _run_child(self, *, retry_failed=False):
        command = [
            sys.executable,
            "-m",
            __name__,
            "--data-dir",
            str(self.data_dir),
            "--recipient",
            self.recipient,
            "--volume-id",
            self.volume_id,
            "--upload-budget-bytes",
            str(self.upload_budget_bytes),
            "--staging-root",
            str(self.staging_root),
        ]
        if retry_failed:
            command.append("--retry-failed")
        process = subprocess.Popen(command, start_new_session=True)
        deadline = time.monotonic() + self.timeout_seconds
        try:
            while process.poll() is None and not self._stop.wait(0.1):
                if time.monotonic() >= deadline:
                    break
        finally:
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            self._recover_interrupted()

    def _recover_interrupted(self):
        # A manual invocation may own the recovery lock. Never modify its ledger
        # or remove its staging directory, even after our own child exits.
        with (self.data_dir / ".recovery.lock").open("a+b") as lock:
            os.chmod(lock.name, 0o600)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            state = load_state(self.data_dir)
            changed = False
            for attempt in state["attempts"]:
                temporary = self.staging_root / (
                    "wayline-recovery-" + attempt["prefix"].rsplit("/", 1)[1]
                )
                if temporary.exists():
                    shutil.rmtree(temporary)
                if attempt["status"] == "running":
                    attempt.update(status="failed", error="interrupted")
                    changed = True
            if changed:
                save_state(self.data_dir, state)


def main():
    parser = argparse.ArgumentParser(description="Create one due encrypted recovery set")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--volume-id", required=True)
    parser.add_argument("--upload-budget-bytes", type=int, default=DEFAULT_UPLOAD_BUDGET)
    parser.add_argument("--staging-root", type=Path, default=Path("/tmp"))
    parser.add_argument(
        "--retry-failed", action="store_true", help="one operator retry per 24 hours"
    )
    args = parser.parse_args()
    run_once(**vars(args))


if __name__ == "__main__":
    main()
