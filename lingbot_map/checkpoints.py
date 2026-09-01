"""Race-resistant checkpoint integrity checks shared by every loader."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any


class CheckpointRejected(RuntimeError):
    pass


def _validate_digest(value: str) -> str:
    digest = value.strip().lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise CheckpointRejected("checkpoint requires an exact lowercase SHA-256 digest")
    return digest


def _open_checkpoint(path: Path) -> tuple[int, os.stat_result]:
    """Open a non-symlink regular file and bind checks to that descriptor."""

    try:
        before = path.lstat()
    except FileNotFoundError as error:
        raise CheckpointRejected("checkpoint does not exist") from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise CheckpointRejected("checkpoint must be a regular, non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise CheckpointRejected("checkpoint could not be opened safely") from error
    opened = os.fstat(descriptor)
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_dev != before.st_dev
        or opened.st_ino != before.st_ino
    ):
        os.close(descriptor)
        raise CheckpointRejected("checkpoint identity changed while it was opened")
    return descriptor, opened


def _validate_info(info: os.stat_result, max_bytes: int) -> None:
    if info.st_size <= 0 or info.st_size > max_bytes:
        raise CheckpointRejected("checkpoint size is outside the configured safety limit")
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise CheckpointRejected("checkpoint must not be group- or world-writable")


def _hash_descriptor(descriptor: int) -> str:
    digest = hashlib.sha256()
    while chunk := os.read(descriptor, 8 * 1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    descriptor, _ = _open_checkpoint(path)
    try:
        return _hash_descriptor(descriptor)
    finally:
        os.close(descriptor)


def _read_digest_sidecar(path: Path) -> str:
    descriptor, before = _open_checkpoint(path)
    try:
        _validate_info(before, 4 * 1024)
        payload = b""
        while chunk := os.read(descriptor, 4 * 1024):
            payload += chunk
            if len(payload) > 4 * 1024:
                raise CheckpointRejected("checkpoint digest sidecar is too large")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise CheckpointRejected("checkpoint digest sidecar changed while it was read")
    try:
        value = payload.decode("utf-8").strip().split()[0]
    except (UnicodeDecodeError, IndexError) as error:
        raise CheckpointRejected("checkpoint digest sidecar is invalid") from error
    return _validate_digest(value)


def expected_digest(path: Path, explicit: str | None = None) -> str | None:
    if explicit:
        return _validate_digest(explicit)
    sidecar = Path(f"{path}.sha256")
    if not sidecar.exists():
        return None
    return _read_digest_sidecar(sidecar)


def _prepare_private_cache_dir(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = cache_dir.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise CheckpointRejected("checkpoint cache must be a private, non-symlink directory")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise CheckpointRejected("checkpoint cache must be owned by the current user")
    cache_dir.chmod(0o700)
    return cache_dir.resolve(strict=True)


def verify_checkpoint(path: Path, expected_sha256: str, max_bytes: int) -> dict[str, Any]:
    """Verify identity, permissions, size, and digest on one open descriptor."""

    expected = _validate_digest(expected_sha256)
    descriptor, before = _open_checkpoint(path)
    try:
        _validate_info(before, max_bytes)
        actual = _hash_descriptor(descriptor)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise CheckpointRejected("checkpoint changed while its digest was calculated")
    if actual != expected:
        raise CheckpointRejected("checkpoint SHA-256 does not match the pinned manifest")
    return {"path": str(path.resolve(strict=True)), "sha256": actual, "sizeBytes": before.st_size}


def materialize_verified_checkpoint(
    path: Path,
    expected_sha256: str,
    max_bytes: int,
    cache_dir: Path,
) -> dict[str, Any]:
    """Copy a verified descriptor into a private content-addressed runtime path."""

    expected = _validate_digest(expected_sha256)
    cache_dir = _prepare_private_cache_dir(cache_dir)
    target = cache_dir / f"{expected}.checkpoint"
    if target.exists():
        record = verify_checkpoint(target, expected, max_bytes)
        os.chmod(target, 0o400)
        return record

    descriptor, before = _open_checkpoint(path)
    temporary: Path | None = None
    try:
        _validate_info(before, max_bytes)
        digest = hashlib.sha256()
        fd, name = tempfile.mkstemp(prefix=".checkpoint-", dir=cache_dir)
        temporary = Path(name)
        with os.fdopen(fd, "wb") as output:
            while chunk := os.read(descriptor, 8 * 1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise CheckpointRejected("checkpoint changed while it was copied")
        if digest.hexdigest() != expected:
            raise CheckpointRejected("checkpoint SHA-256 does not match the pinned manifest")
        os.chmod(temporary, 0o400)
        with suppress(FileExistsError):
            os.link(temporary, target)
        temporary.unlink(missing_ok=True)
        temporary = None
        os.chmod(target, 0o400)
        return verify_checkpoint(target, expected, max_bytes)
    finally:
        os.close(descriptor)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def verified_checkpoint_path(
    path: Path,
    explicit_digest: str | None,
    *,
    max_bytes: int = 6 * 1024 * 1024 * 1024,
    cache_dir: Path | None = None,
) -> Path:
    """Resolve a digest/sidecar and return a private immutable loader path."""

    digest = expected_digest(path, explicit_digest)
    if not digest:
        raise CheckpointRejected(
            "checkpoint loading requires --model_sha256 or a trusted .sha256 sidecar"
        )
    default_cache = Path(tempfile.gettempdir()) / f"lingbot-map-checkpoints-{os.getuid()}"
    record = materialize_verified_checkpoint(path, digest, max_bytes, cache_dir or default_cache)
    return Path(record["path"])
