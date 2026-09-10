import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from lingbot_map.workspace import backup
from lingbot_map.workspace.backup import create_snapshot, restore_snapshot
from lingbot_map.workspace.runtime_lock import workspace_lock
from lingbot_map.workspace.service import WorkspaceService


@pytest.mark.parametrize("online", [False, True])
def test_restore_preserves_scene_and_idempotent_share(service, tenant_id, tmp_path, online):
    source_video = Path(__file__).parent / "fixtures" / "vfr-test-pattern.mp4"
    with source_video.open("rb") as stream:
        asset = service.upload_video(
            tenant_id=tenant_id, filename="capture.mp4", media_type="video/mp4", stream=stream
        )
    job = service.submit_sample(tenant_id)
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    share = service.create_share(
        tenant_id, artifact["id"], ttl_seconds=300, idempotency_key="restore-share-0001"
    )
    original = service.store.path_for_local_use(artifact["object_key"]).read_bytes()
    snapshot = tmp_path / "snapshot"
    create_snapshot(service.settings.data_dir, snapshot, online=online)
    restored = tmp_path / "restored"
    assert restore_snapshot(snapshot, restored)["files"] >= 4
    recovered = WorkspaceService(replace(service.settings, data_dir=restored))
    recovered.initialize()
    assert (
        recovered.store.path_for_local_use(asset["object_key"]).read_bytes()
        == source_video.read_bytes()
    )
    assert recovered.store.path_for_local_use(artifact["object_key"]).read_bytes() == original
    assert recovered.database.resolve_share(share["token"])["id"] == artifact["id"]
    assert (
        recovered.create_share(
            tenant_id, artifact["id"], ttl_seconds=300, idempotency_key="restore-share-0001"
        )
        == share
    )


def test_snapshot_requires_stopped_runtime_and_refuses_overwrite(service, tmp_path):
    output = tmp_path / "snapshot"
    with (
        workspace_lock(service.settings.data_dir),
        pytest.raises(RuntimeError, match="Stop Wayline"),
    ):
        create_snapshot(service.settings.data_dir, output)
    assert not output.exists()
    create_snapshot(service.settings.data_dir, output)
    with pytest.raises(FileExistsError):
        create_snapshot(service.settings.data_dir, output)
    assert (output / "snapshot.json").is_file()
    with pytest.raises(FileExistsError):
        restore_snapshot(output, service.settings.data_dir)


def test_restore_rejects_corruption_without_leaving_partial_data(service, tmp_path):
    snapshot = tmp_path / "snapshot"
    create_snapshot(service.settings.data_dir, snapshot)
    (snapshot / "share-token.secret").write_bytes(b"x" * 32)
    restored = tmp_path / "restored"
    with pytest.raises(ValueError, match="integrity verification"):
        restore_snapshot(snapshot, restored)
    assert not restored.exists()


def test_snapshot_rejects_missing_database_referenced_object(service, tenant_id, tmp_path):
    job = service.submit_sample(tenant_id)
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    service.store.path_for_local_use(artifact["object_key"]).unlink()
    snapshot = tmp_path / "snapshot"
    with pytest.raises(ValueError, match="database-referenced object"):
        create_snapshot(service.settings.data_dir, snapshot)
    assert not snapshot.exists()


def test_online_snapshot_excludes_later_publications_and_unreferenced_files(
    service, tenant_id, tmp_path, monkeypatch
):
    job = service.submit_sample(tenant_id)
    service.process_next_job()
    service.store.put_bytes("unreferenced.bin", b"not committed", max_bytes=100)
    copy_private = backup.copy_private
    later_jobs = []

    def publish_after_database_copy(source, target):
        if source.name == "share-token.secret":
            later_jobs.append(service.submit_sample(tenant_id))
            service.process_next_job()
        copy_private(source, target)

    monkeypatch.setattr(backup, "copy_private", publish_after_database_copy)
    snapshot = tmp_path / "snapshot"
    with workspace_lock(service.settings.data_dir):
        manifest = create_snapshot(service.settings.data_dir, snapshot, online=True)
    monkeypatch.setattr(backup, "copy_private", copy_private)
    assert len(later_jobs) == 1
    assert service.database.get_job(tenant_id, later_jobs[0]["id"])["state"] == "ready"
    with closing(sqlite3.connect(snapshot / "workspace.sqlite3")) as connection:
        assert connection.execute("SELECT id FROM jobs").fetchall() == [(job["id"],)]
    artifacts = service.database.get_job(tenant_id, job["id"])["artifacts"]
    assert {name for name in manifest["files"] if name.startswith("objects/")} == {
        "objects/" + artifact["object_key"] for artifact in artifacts
    }
    restore_snapshot(snapshot, tmp_path / "restored")


@pytest.mark.parametrize("change", ["delete", "corrupt"])
def test_online_snapshot_rejects_object_changes_after_database_copy(
    service, tenant_id, tmp_path, monkeypatch, change
):
    job = service.submit_sample(tenant_id)
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    source_object = service.store.path_for_local_use(artifact["object_key"])
    copy_private = backup.copy_private

    def change_before_object_copy(source, target):
        if source == source_object:
            if change == "delete":
                service.delete_job(tenant_id, job["id"])
            else:
                source.write_bytes(b"corrupt")
        copy_private(source, target)

    monkeypatch.setattr(backup, "copy_private", change_before_object_copy)
    snapshot = tmp_path / "snapshot"
    with pytest.raises(ValueError, match="regular files|missing or corrupt"):
        create_snapshot(service.settings.data_dir, snapshot, online=True)
    assert not snapshot.exists()


def test_snapshot_database_timeout_removes_partial_copy(service, tmp_path, monkeypatch):
    times = iter([0, 31])
    monkeypatch.setattr(backup, "time", SimpleNamespace(monotonic=lambda: next(times)))
    snapshot = tmp_path / "snapshot"
    with pytest.raises(TimeoutError, match="30 seconds"):
        create_snapshot(service.settings.data_dir, snapshot, online=True)
    assert not snapshot.exists()
