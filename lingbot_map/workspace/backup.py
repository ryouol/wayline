"""Verified snapshots of SQLite, private objects, and the share secret.

Run with `python -m lingbot_map.workspace.backup --help`.
Snapshots contain private data and must be stored encrypted off the application disk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import time
from contextlib import closing, nullcontext
from pathlib import Path

from .runtime_lock import workspace_lock
from .storage import validate_object_key

REQUIRED_FILES = {"workspace.sqlite3", "share-token.secret"}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_database(path: Path) -> None:
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Snapshot database integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Snapshot contains broken database references")


def copy_private(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError("Snapshots support regular files only")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        target.chmod(0o600)
        shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)


def referenced_objects(data_dir: Path) -> list[tuple[str, int, str]]:
    with closing(
        sqlite3.connect(f"{(data_dir / 'workspace.sqlite3').as_uri()}?mode=ro", uri=True)
    ) as connection:
        return connection.execute(
            "SELECT object_key,size_bytes,sha256 FROM assets UNION ALL "
            "SELECT object_key,size_bytes,sha256 FROM artifacts"
        ).fetchall()


def check_objects(data_dir: Path, files: dict) -> None:
    for key, size, sha256 in referenced_objects(data_dir):
        name = "objects/" + validate_object_key(key)
        if files.get(name) != {"size": size, "sha256": sha256}:
            raise ValueError("A database-referenced object is missing or corrupt")


def create_snapshot(data_dir: Path, output: Path, *, online: bool = False) -> dict:
    """Copy a SQLite snapshot and verify its immutable object references.

    Online copies exclude unreferenced files. Concurrent deletion may make a
    referenced file disappear; that attempt fails and removes the partial copy.
    Offline mode keeps exclusive workspace ownership and copies all objects.
    """
    data_dir, output = data_dir.resolve(), output.resolve()
    if output.is_relative_to(data_dir):
        raise ValueError("Store the snapshot outside the workspace data directory")
    with nullcontext() if online else workspace_lock(data_dir):
        if not all((data_dir / name).is_file() for name in REQUIRED_FILES):
            raise ValueError("Workspace database or share secret is missing")
        output.mkdir(mode=0o700)
        try:
            with (
                closing(
                    sqlite3.connect(
                        f"{(data_dir / 'workspace.sqlite3').as_uri()}?mode=ro", uri=True
                    )
                ) as source,
                closing(sqlite3.connect(output / "workspace.sqlite3")) as target,
            ):
                deadline = time.monotonic() + 30

                def check_deadline(_status: int, _remaining: int, _total: int) -> None:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Snapshot database copy exceeded 30 seconds")

                source.backup(target, pages=256, progress=check_deadline)
                target.execute("PRAGMA journal_mode=DELETE")
            (output / "workspace.sqlite3").chmod(0o600)
            copy_private(data_dir / "share-token.secret", output / "share-token.secret")
            manifest_file = data_dir / "runtime-manifest.json"
            if manifest_file.exists():
                copy_private(manifest_file, output / manifest_file.name)
            objects = (
                [
                    data_dir / "objects" / validate_object_key(key)
                    for key, _, _ in referenced_objects(output)
                ]
                if online
                else sorted((data_dir / "objects").rglob("*"))
            )
            for source_file in objects:
                if source_file.is_symlink():
                    raise ValueError("Object storage contains a symlink")
                if online or source_file.is_file():
                    copy_private(source_file, output / source_file.relative_to(data_dir))
            check_database(output / "workspace.sqlite3")
            files = {
                str(path.relative_to(output)): {"size": path.stat().st_size, "sha256": digest(path)}
                for path in sorted(output.rglob("*"))
                if path.is_file()
            }
            manifest = {"format": 1, "files": files}
            check_objects(output, files)
            (output / "snapshot.json").write_text(json.dumps(manifest, indent=2) + "\n")
            (output / "snapshot.json").chmod(0o600)
            return manifest
        except BaseException:
            shutil.rmtree(output)
            raise


def restore_snapshot(snapshot: Path, output: Path) -> dict:
    snapshot, output = snapshot.resolve(), output.resolve()
    manifest = json.loads((snapshot / "snapshot.json").read_text())
    files = manifest.get("files", {})
    if (
        manifest.get("format") != 1
        or not isinstance(files, dict)
        or not files.keys() >= REQUIRED_FILES
    ):
        raise ValueError("Snapshot manifest is incomplete or unsupported")
    if output.is_relative_to(snapshot):
        raise ValueError("Restore into a new directory outside the snapshot")
    output.mkdir(mode=0o700)
    try:
        for name, metadata in files.items():
            source = snapshot / name
            if (
                Path(name).is_absolute()
                or ".." in Path(name).parts
                or not source.resolve().is_relative_to(snapshot)
            ):
                raise ValueError("Snapshot contains an unsafe path")
            copy_private(source, output / name)
            copied = output / name
            if copied.stat().st_size != metadata["size"] or digest(copied) != metadata["sha256"]:
                raise ValueError("Snapshot file failed integrity verification")
        check_database(output / "workspace.sqlite3")
        check_objects(output, files)
        if (output / "share-token.secret").stat().st_size != 32:
            raise ValueError("Snapshot share secret is invalid")
        return {"files": len(files)}
    except BaseException:
        shutil.rmtree(output)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or restore a private, verified Wayline snapshot"
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)
    create = subparsers.add_parser("create", help="create a verified workspace snapshot")
    create.add_argument("--data-dir", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument(
        "--online",
        action="store_true",
        help="copy the running workspace; concurrent object deletion can fail the attempt",
    )
    restore = subparsers.add_parser("restore", help="restore into a new, empty location")
    restore.add_argument("--snapshot", type=Path, required=True)
    restore.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.operation == "create":
        result = create_snapshot(args.data_dir, args.output, online=args.online)
        print(f"Created and verified snapshot with {len(result['files'])} files.")
    else:
        result = restore_snapshot(args.snapshot, args.output)
        print(f"Restored and verified {result['files']} files.")


if __name__ == "__main__":
    main()
