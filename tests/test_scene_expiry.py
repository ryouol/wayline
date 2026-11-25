"""Displayed deadlines follow the existing retention policy without changing it."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.identity import TRIAL_TTL_SECONDS
from lingbot_map.workspace.service import WorkspaceService

from .conftest import BOOTSTRAP_TOKEN


def test_deadline_matches_retention_and_revokes_shared_scene(settings, monkeypatch):
    settings = replace(settings, terminal_job_retention_seconds=600)
    service = WorkspaceService(settings)
    headers = {"Authorization": f"Bearer {BOOTSTRAP_TOKEN}"}
    with TestClient(create_app(settings, service=service, start_worker=False)) as client:
        policy = client.get("/api/me", headers=headers).json()["retention"]
        assert policy == {
            "terminalJobSeconds": 600,
            "unattachedUploadSeconds": settings.unattached_asset_retention_seconds,
            "workspaceExpiresAt": None,
        }
        queued = client.post("/api/jobs/sample", headers=headers).json()
        assert queued["expiresAt"] is None
        assert service.process_next_job()
        path = f"/api/jobs/{queued['id']}"
        job = client.get(path, headers=headers).json()
        assert job["expiresAt"] == job["finishedAt"] + 600
        assert (
            client.get("/api/jobs", headers=headers).json()["jobs"][0]["expiresAt"]
            == job["expiresAt"]
        )
        scene = next(item for item in job["artifacts"] if item["kind"] == "scene")
        share = client.post(
            f"/api/artifacts/{scene['id']}/shares", headers=headers, json={"ttlSeconds": 3600}
        ).json()
        public = {"Authorization": "Bearer " + share["url"].split("#")[1]}
        monkeypatch.setattr("time.time", lambda: job["expiresAt"] - 1)
        assert service.run_retention()["jobs"] == 0
        assert client.get(path, headers=headers).status_code == 200
        assert client.get("/api/public/share", headers=public).status_code == 200
        monkeypatch.setattr("time.time", lambda: job["expiresAt"] + 1)
        assert service.run_retention()["jobs"] == 1
        assert client.get(path, headers=headers).status_code == 404
        assert client.get("/api/public/share", headers=public).status_code == 404


@pytest.mark.parametrize("state", ["ready", "failed", "cancelled"])
@pytest.mark.parametrize("finished", [None, 0, 200])
def test_terminal_deadlines_use_the_same_timestamp_as_cleanup(
    authenticated_client, service, settings, state, finished
):
    job = authenticated_client.post("/api/jobs/sample").json()
    with service.database.transaction() as connection:
        connection.execute(
            "UPDATE jobs SET state=?,finished_at=?,updated_at=100 WHERE id=?",
            (state, finished, job["id"]),
        )
    value = authenticated_client.get(f"/api/jobs/{job['id']}").json()
    expected = (100 if finished is None else finished) + settings.terminal_job_retention_seconds
    assert value["expiresAt"] == expected


def test_trial_deadline_uses_workspace_age_not_scene_completion(client, service, monkeypatch):
    response = client.post("/api/trial").json()
    client.headers["X-CSRF-Token"] = response["csrfToken"]
    policy = client.get("/api/me").json()["retention"]
    with service.database.connect() as connection:
        created = connection.execute(
            "SELECT created_at FROM identities WHERE provider='trial'"
        ).fetchone()[0]
    expiry = created + TRIAL_TTL_SECONDS
    assert policy["workspaceExpiresAt"] == expiry
    job = client.post("/api/jobs/sample").json()
    assert job["expiresAt"] == expiry
    assert service.process_next_job()
    assert client.get(f"/api/jobs/{job['id']}").json()["expiresAt"] == expiry
    monkeypatch.setattr("time.time", lambda: expiry + 1)
    assert service.run_retention()["expiredTrials"] == 1
    assert client.get("/api/me").status_code == 401
