"""Object-storage interface and atomic local implementation."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size_bytes: int
    sha256: str


class ObjectStore(Protocol):
    """Minimal boundary implemented by local disk today and S3 in production."""

    def put_stream(self, key: str, stream: BinaryIO, *, max_bytes: int) -> StoredObject: ...

    def put_bytes(self, key: str, payload: bytes, *, max_bytes: int) -> StoredObject: ...

    def open(self, key: str) -> BinaryIO: ...

    def path_for_local_use(self, key: str) -> Path: ...

    def delete(self, key: str) -> None: ...


class ObjectTooLarge(ValueError):
    pass


def validate_object_key(key: str) -> str:
    path = PurePosixPath(key)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("invalid object key")
    if "\\" in key or "\x00" in key:
        raise ValueError("invalid object key")
    return path.as_posix()


class LocalObjectStore:
    """Atomic filesystem-backed object store.

    Keys have S3-style POSIX semantics and are resolved beneath ``root``. A
    future S3 implementation only needs to satisfy :class:`ObjectStore`.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, key: str) -> Path:
        safe = validate_object_key(key)
        candidate = (self.root / safe).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ValueError("object key escaped storage root")
        return candidate

    def put_stream(self, key: str, stream: BinaryIO, *, max_bytes: int) -> StoredObject:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        digest = hashlib.sha256()
        size = 0
        fd, temporary = tempfile.mkstemp(prefix=".upload-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise ObjectTooLarge(f"object exceeds {max_bytes} bytes")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise
        return StoredObject(
            key=validate_object_key(key), size_bytes=size, sha256=digest.hexdigest()
        )

    def put_bytes(self, key: str, payload: bytes, *, max_bytes: int) -> StoredObject:
        if len(payload) > max_bytes:
            raise ObjectTooLarge(f"object exceeds {max_bytes} bytes")
        return self.put_stream(key, io.BytesIO(payload), max_bytes=max_bytes)

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def path_for_local_use(self, key: str) -> Path:
        path = self._path(key)
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(key)
        return path

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent != self.root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def copy_from_path(self, key: str, source: Path, *, max_bytes: int) -> StoredObject:
        if source.is_symlink() or not source.is_file():
            raise ValueError("artifact must be a regular file")
        with source.open("rb") as stream:
            return self.put_stream(key, stream, max_bytes=max_bytes)

    def clear_prefix(self, prefix: str) -> None:
        path = self._path(prefix)
        if path.exists():
            shutil.rmtree(path)
