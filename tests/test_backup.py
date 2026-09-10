from dataclasses import replace

import pytest

from lingbot_map.workspace.backup import create_snapshot, restore_snapshot
from lingbot_map.workspace.runtime_lock import workspace_lock
from lingbot_map.workspace.service import WorkspaceService


def test_restore_preserves_scene_and_idempotent_share(service, tenant_id, tmp_path):
    job = service.submit_sample(tenant_id)
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    share = service.create_share(
        tenant_id, artifact["id"], ttl_seconds=300, idempotency_key="restore-share-0001"
    )
    original = service.store.path_for_local_use(artifact["object_key"]).read_bytes()
    snapshot = tmp_path / "snapshot"
    create_snapshot(service.settings.data_dir, snapshot)
    restored = tmp_path / "restored"
    assert restore_snapshot(snapshot, restored)["files"] >= 4
    recovered = WorkspaceService(replace(service.settings, data_dir=restored))
    recovered.initialize()
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
