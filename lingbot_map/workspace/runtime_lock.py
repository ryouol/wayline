"""Exclusive ownership of a single-instance workspace and offline snapshots."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def workspace_lock(data_dir: Path) -> Iterator[None]:
    import fcntl

    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = data_dir / ".instance.lock"
    with path.open("a+b") as handle:
        path.chmod(0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(
                "Stop Wayline before taking a snapshot or starting another instance."
            ) from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
