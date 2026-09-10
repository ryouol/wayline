"""Scene delivery admission stays atomic, global and durable across restarts."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.database import Database, QuotaExceeded
from lingbot_map.workspace.sample import build_synthetic_scene
from lingbot_map.workspace.service import WorkspaceService

from .conftest import BOOTSTRAP_TOKEN


def test_all_scene_delivery_routes_share_an_allowance_after_restart(settings):
    scene_size = len(build_synthetic_scene().glb)
    limited = replace(settings, scene_delivery_budget_bytes=scene_size * 3)
    service = WorkspaceService(limited)
    headers = {"Authorization": f"Bearer {BOOTSTRAP_TOKEN}"}
    with TestClient(create_app(limited, service=service, start_worker=False)) as client:
        job = client.post("/api/jobs/sample", headers=headers).json()
        assert service.process_next_job()
        job = client.get(f"/api/jobs/{job['id']}", headers=headers).json()
        scene = next(item for item in job["artifacts"] if item["kind"] == "scene")
        view = f"/api/artifacts/{scene['id']}/content"
        download = f"/api/artifacts/{scene['id']}/download"
        share = client.post(
            f"/api/artifacts/{scene['id']}/shares", json={"ttlSeconds": 300}, headers=headers
        ).json()
        public_headers = {"Authorization": "Bearer " + share["url"].split("#")[1]}
        assert client.get(view).status_code == 401
        assert client.get(view, headers={**headers, "Range": "bytes=0-3,8-11"}).status_code == 416
        assert client.get(view, headers=headers).status_code == 200
        assert client.get(download, headers=headers).status_code == 200
        partial = client.get(
            "/api/public/share/content", headers={**public_headers, "Range": "bytes=0-3"}
        )
        assert partial.status_code == 206 and partial.content == b"glTF"
        for path, auth in (
            (view, headers),
            (download, headers),
            ("/api/public/share/content", public_headers),
        ):
            assert client.get(path, headers=auth).status_code == 409

    restarted = WorkspaceService(limited)
    with TestClient(create_app(limited, service=restarted, start_worker=False)) as client:
        assert client.get(download, headers=headers).status_code == 409
        assert client.delete(f"/api/jobs/{job['id']}", headers=headers).status_code == 202
        other_token = "another-isolated-operator-token-00000000"
        restarted.database.provision_tenant(token=other_token, tenant_name="Other", quota_units=10)
        other_headers = {"Authorization": f"Bearer {other_token}"}
        other_job = client.post("/api/jobs/sample", headers=other_headers).json()
        assert restarted.process_next_job()
        result = client.get(f"/api/jobs/{other_job['id']}", headers=other_headers).json()
        artifact = next(item for item in result["artifacts"] if item["kind"] == "scene")
        assert client.get(artifact["viewUrl"], headers=other_headers).status_code == 409
        with restarted.database.connect() as connection:
            assert (
                connection.execute("SELECT SUM(reserved_bytes) FROM delivery_budget").fetchone()[0]
                == scene_size * 3
            )


def test_concurrent_delivery_reservations_cannot_overspend(tmp_path):
    database = Database(tmp_path / "delivery.sqlite3")
    database.initialize()

    def reserve(_):
        try:
            database.reserve_delivery_bytes(10, limit=50)
            return True
        except QuotaExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(16))) == 5
    with database.connect() as connection:
        assert (
            connection.execute("SELECT SUM(reserved_bytes) FROM delivery_budget").fetchone()[0]
            == 50
        )


def test_delivery_budget_retains_full_month_and_expires_bounded_rows(tmp_path, monkeypatch):
    database = Database(tmp_path / "delivery.sqlite3")
    database.initialize()
    start = 20_000 * 86400
    monkeypatch.setattr("lingbot_map.workspace.database.time.time", lambda: start)
    database.reserve_delivery_bytes(100, limit=100)
    monkeypatch.setattr("lingbot_map.workspace.database.time.time", lambda: start + 31 * 86400)
    with pytest.raises(QuotaExceeded):
        database.reserve_delivery_bytes(1, limit=100)
    monkeypatch.setattr("lingbot_map.workspace.database.time.time", lambda: start + 32 * 86400)
    database.reserve_delivery_bytes(100, limit=100)
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM delivery_budget").fetchone()[0] == 1


def test_schema_four_upgrade_preserves_existing_workspaces(service):
    principal = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)
    with service.database.connect() as connection:
        connection.execute("DROP TABLE delivery_budget")
        connection.execute("UPDATE schema_meta SET version=4")
    service.database.initialize()
    assert service.database.authenticate_api_token(BOOTSTRAP_TOKEN) == principal
    service.database.reserve_delivery_bytes(1, limit=1)
    with service.database.connect() as connection:
        assert connection.execute("SELECT version FROM schema_meta").fetchone()[0] == 5
