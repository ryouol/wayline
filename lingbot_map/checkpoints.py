"""Checkpoint integrity checks shared by CLI and worker adapters."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path
from typing import Any


class CheckpointRejected(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_digest(path: Path, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit.strip().lower()
    sidecar = Path(f"{path}.sha256")
    if not sidecar.is_file() or sidecar.is_symlink():
        return None
    value = sidecar.read_text(encoding="utf-8").strip().split()[0].lower()
    return value


def verify_checkpoint(path: Path, expected_sha256: str, max_bytes: int) -> dict[str, Any]:
    """Verify type, permissions, size, and an exact SHA-256 digest."""

    if path.is_symlink() or not path.is_file():
        raise CheckpointRejected("checkpoint must be a regular, non-symlink file")
    info = path.stat()
    if info.st_size <= 0 or info.st_size > max_bytes:
        raise CheckpointRejected("checkpoint size is outside the configured safety limit")
    if info.st_mode & stat.S_IWOTH:
        raise CheckpointRejected("checkpoint must not be world-writable")
    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha256
    ):
        raise CheckpointRejected("checkpoint requires an exact lowercase SHA-256 digest")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise CheckpointRejected("checkpoint SHA-256 does not match the pinned manifest")
    return {"path": str(path), "sha256": actual, "sizeBytes": info.st_size}
