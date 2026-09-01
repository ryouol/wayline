from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.config import Settings
from lingbot_map.workspace.service import WorkspaceService

BOOTSTRAP_TOKEN = "test-workspace-token-that-is-long-enough"


class StubInspector:
    def inspect(self, _path):
        return {
            "fps": 10.0,
            "frames": 100,
            "durationSeconds": 10.0,
            "width": 640,
            "height": 480,
        }


@pytest.fixture
def settings(tmp_path):
    value = Settings(
        data_dir=tmp_path / "workspace",
        environment="test",
        bootstrap_token=BOOTSTRAP_TOKEN,
        cookie_secure=False,
        max_upload_bytes=1024 * 1024,
        worker_poll_seconds=0.01,
        job_timeout_seconds=30,
    )
    value.validate()
    return value


@pytest.fixture
def service(settings):
    value = WorkspaceService(settings, inspector=StubInspector())
    value.initialize()
    return value


@pytest.fixture
def client(settings, service):
    app = create_app(settings, service=service, start_worker=False)
    with TestClient(app) as value:
        yield value


@pytest.fixture
def authenticated_client(client):
    response = client.post("/api/session", json={"token": BOOTSTRAP_TOKEN})
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrfToken"]
    return client


@pytest.fixture
def tenant_id(service):
    principal = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)
    assert principal
    return principal["tenant_id"]


@pytest.fixture
def small_settings(settings):
    return replace(settings, max_upload_bytes=32)
