from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.database import token_digest
from lingbot_map.workspace.service import WorkspaceService

from .conftest import BOOTSTRAP_TOKEN


def fake_mp4(size: int = 64) -> bytes:
    return b"\x00\x00\x00\x18ftypisom" + b"\x00" * max(0, size - 12)


def test_authentication_and_security_headers(client, service):
    response = client.get("/api/jobs")
    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    assert client.post("/api/session", json={"token": "wrong-token-value"}).status_code == 401
    login = client.post("/api/session", json={"token": BOOTSTRAP_TOKEN})
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=strict" in login.headers["set-cookie"]
    marker = login.headers["x-workspace-principal"]
    assert len(marker) == 64

    other_token = "other-principal-marker-token-long-enough"
    service.database.provision_tenant(token=other_token, tenant_name="Other", quota_units=10)
    other = client.get("/api/jobs", headers={"Authorization": f"Bearer {other_token}"})
    assert other.headers["x-workspace-principal"] != marker

    # Cookie-authenticated writes require the separate stable per-session CSRF token.
    assert client.post("/api/jobs/sample").status_code == 403
    client.headers["X-CSRF-Token"] = login.json()["csrfToken"]
    assert client.post("/api/jobs/sample").status_code == 202


def test_health_checks_database_storage_and_required_worker(client, service, monkeypatch):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert service.ready(require_worker=True) is False
    service.start_worker()
    try:
        assert service.ready(require_worker=True) is True
    finally:
        service.stop_worker()

    def fail_storage_probe(_key, _payload, *, max_bytes):
        raise OSError(f"private storage failure after {max_bytes} byte")

    monkeypatch.setattr(service.store, "put_bytes", fail_storage_probe)
    service._readiness_checked_at = 0
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"detail": "Workspace dependencies are not ready."}


def test_me_keeps_csrf_stable_across_tabs_and_logout_revokes_with_stale_header(
    authenticated_client,
):
    previous = authenticated_client.headers["X-CSRF-Token"]
    with TestClient(authenticated_client.app) as peer_tab:
        peer_tab.cookies.update(authenticated_client.cookies)
        peer_tab.headers["X-CSRF-Token"] = previous

        response = authenticated_client.get("/api/me")
        assert response.status_code == 200
        assert response.json()["csrfToken"] == previous
        assert peer_tab.post("/api/jobs/sample").status_code == 202

        authenticated_client.headers["X-CSRF-Token"] = "stale-token-from-another-tab"
        logout = authenticated_client.delete("/api/session")
        assert logout.status_code == 204
        assert peer_tab.get("/api/me").status_code == 401


def test_authenticated_csrf_failure_still_identifies_the_principal(authenticated_client):
    marker = authenticated_client.get("/api/me").headers["x-workspace-principal"]
    authenticated_client.headers["X-CSRF-Token"] = "invalid-csrf-token"
    rejected = authenticated_client.post("/api/jobs/sample")
    assert rejected.status_code == 403
    assert rejected.headers["x-workspace-principal"] == marker


def test_bearer_authentication_does_not_use_csrf(client):
    response = client.post(
        "/api/jobs/sample", headers={"Authorization": f"Bearer {BOOTSTRAP_TOKEN}"}
    )
    assert response.status_code == 202


def test_validated_upload_and_research_gate(authenticated_client, service):
    upload = authenticated_client.post(
        "/api/assets",
        files={"file": ("walkthrough.mp4", fake_mp4(), "video/mp4")},
    )
    assert upload.status_code == 201
    asset = upload.json()
    assert asset["metadata"]["frames"] == 100
    assert "object_key" not in asset

    research = authenticated_client.post(
        "/api/jobs/research",
        json={"assetId": asset["id"], "maxFrames": 60, "extractFps": 3},
    )
    assert research.status_code == 409
    assert research.json()["code"] == "engine_unavailable"
    assert (
        service.database.list_jobs(
            service.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
        )
        == []
    )


def test_upload_rejects_mismatched_content_and_removes_object(authenticated_client, service):
    response = authenticated_client.post(
        "/api/assets", files={"file": ("not-video.mp4", b"plain text", "video/mp4")}
    )
    assert response.status_code == 415
    assert list((service.settings.data_dir / "objects").rglob("*.mp4")) == []


def test_orphan_upload_can_be_deleted(authenticated_client, service):
    upload = authenticated_client.post(
        "/api/assets",
        files={"file": ("walkthrough.mp4", fake_mp4(), "video/mp4")},
    )
    assert upload.status_code == 201
    response = authenticated_client.delete(f"/api/assets/{upload.json()['id']}")
    assert response.status_code == 202
    assert response.json()["state"] == "deleting"
    assert list((service.settings.data_dir / "objects").rglob("*.mp4")) == []


def test_linked_upload_metadata_and_overlapping_bulk_cleanup(
    authenticated_client, service, tenant_id
):
    upload = authenticated_client.post(
        "/api/assets",
        files={"file": ("linked.mp4", fake_mp4(), "video/mp4")},
    ).json()
    assert upload["linkedJobCount"] == 0
    assert upload["deletable"] is True
    assert upload["deleteBlockedReason"] is None

    job = service.database.create_job(
        tenant_id=tenant_id,
        engine_id="synthetic-sample-v1",
        source_asset_id=upload["id"],
        params={},
        provenance={"fixture": True},
        reserve_units=0,
    )
    service.cancel_job(tenant_id, job["id"])

    linked = authenticated_client.get("/api/assets").json()["assets"][0]
    assert linked["linkedJobCount"] == 1
    assert linked["deletable"] is False
    assert linked["deleteBlockedReason"] == (
        "This upload is retained by 1 scene. Delete the linked scene first."
    )
    blocked = authenticated_client.delete(f"/api/assets/{upload['id']}")
    assert blocked.status_code == 409
    assert "referenced by jobs" in blocked.json()["detail"]

    cleanup = authenticated_client.post(
        "/api/bulk-delete",
        json={"jobIds": [job["id"]], "assetIds": [upload["id"]], "shareIds": []},
        headers={"Idempotency-Key": "linked-overlap-bulk-delete-0001"},
    )
    assert cleanup.status_code == 202
    assert cleanup.json() == {
        "state": "deleting",
        "accepted": {"jobs": [job["id"]], "assets": [upload["id"]], "shares": []},
        "errors": {},
    }
    assert authenticated_client.get("/api/assets").json()["assets"] == []
    assert authenticated_client.get("/api/jobs").json()["jobs"] == []


def test_upload_limit_returns_413(settings):
    from .conftest import StubInspector

    limited = replace(settings, max_upload_bytes=24)
    service = WorkspaceService(limited, inspector=StubInspector())
    with TestClient(create_app(limited, service=service, start_worker=False)) as client:
        login = client.post("/api/session", json={"token": BOOTSTRAP_TOKEN})
        client.headers["X-CSRF-Token"] = login.json()["csrfToken"]
        response = client.post(
            "/api/assets", files={"file": ("large.mp4", fake_mp4(128), "video/mp4")}
        )
    assert response.status_code == 413


def test_request_body_ceiling_rejects_before_parsing(client):
    response = client.post(
        "/api/session", content=b"", headers={"Content-Length": str(64 * 1024 + 1)}
    )
    assert response.status_code == 413
    assert response.headers["x-content-type-options"] == "nosniff"


def test_unhandled_500_keeps_security_headers(settings, service):
    app = create_app(settings, service=service, start_worker=False)

    @app.get("/test-only-unhandled-error")
    def unhandled_error():
        raise RuntimeError("private implementation detail")

    with TestClient(app, raise_server_exceptions=False) as error_client:
        response = error_client.get("/test-only-unhandled-error")
    assert response.status_code == 500
    assert response.json() == {"detail": "The request could not be completed."}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "private implementation detail" not in response.text


def test_production_disables_schema_validates_host_and_leaves_hsts_to_edge(settings):
    from .conftest import StubInspector

    production = replace(
        settings,
        environment="production",
        bootstrap_token="x" * 32,
        cookie_secure=True,
        public_base_url="https://scenes.example.com",
        allowed_hosts=("scenes.example.com",),
    )
    service = WorkspaceService(production, inspector=StubInspector())
    with TestClient(
        create_app(production, service=service, start_worker=False),
        base_url="https://scenes.example.com",
    ) as production_client:
        assert production_client.get("/openapi.json").status_code == 404
        health = production_client.get("/healthz")
        assert health.status_code == 200
        assert "strict-transport-security" not in health.headers
        assert (
            production_client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400
        )


def test_complete_sample_view_download_share_and_delete(authenticated_client, service, tenant_id):
    submitted = authenticated_client.post("/api/jobs/sample")
    assert submitted.status_code == 202
    job_id = submitted.json()["id"]
    assert service.database.quota(tenant_id)["reserved_units"] == 1

    assert service.process_next_job() is True
    result = authenticated_client.get(f"/api/jobs/{job_id}")
    assert result.status_code == 200
    job = result.json()
    assert job["state"] == "ready"
    assert job["progress"] == 1
    assert job["usedUnits"] == 0
    assert service.database.quota(tenant_id)["reserved_units"] == 0
    assert service.database.quota(tenant_id)["consumed_units"] == 0

    scene = next(item for item in job["artifacts"] if item["kind"] == "scene")
    content = authenticated_client.get(scene["viewUrl"])
    assert content.status_code == 200
    assert content.content[:4] == b"glTF"
    assert content.headers["content-type"].startswith("model/gltf-binary")

    manifest = next(item for item in job["artifacts"] if item["kind"] == "manifest")
    assert (
        authenticated_client.post(
            f"/api/artifacts/{manifest['id']}/shares", json={"ttlSeconds": 300}
        ).status_code
        == 404
    )

    share = authenticated_client.post(
        f"/api/artifacts/{scene['id']}/shares", json={"ttlSeconds": 300}
    )
    assert share.status_code == 201
    share_path = share.json()["url"]
    token = share_path.rsplit("/", 1)[-1]
    public = authenticated_client.get(f"/api/public/shares/{token}")
    assert public.status_code == 200
    assert public.json()["artifact"]["licenseId"] == "CC0-1.0"
    public_content = authenticated_client.get(f"/api/public/shares/{token}/content")
    assert public_content.content[:4] == b"glTF"

    deleted = authenticated_client.delete(f"/api/jobs/{job_id}")
    assert deleted.status_code == 202
    assert deleted.json()["state"] == "deleting"
    assert authenticated_client.get(scene["viewUrl"]).status_code == 404
    assert authenticated_client.get(f"/api/public/shares/{token}").status_code == 404
    assert list((service.settings.data_dir / "objects").rglob("*.glb")) == []


def test_queued_cancellation_releases_reservation(authenticated_client, service, tenant_id):
    job = authenticated_client.post("/api/jobs/sample").json()
    assert service.database.quota(tenant_id)["reserved_units"] == 1
    response = authenticated_client.post(f"/api/jobs/{job['id']}/cancel")
    assert response.status_code == 202
    assert response.json()["state"] == "cancelled"
    assert service.database.quota(tenant_id)["reserved_units"] == 0
    events = [(entry["event"], entry["units"]) for entry in service.database.ledger(tenant_id)]
    assert events[-2:] == [("reserve", 1), ("cancel", -1)]


def test_committed_running_cancel_wins_atomic_finish_and_discards_artifacts(
    service, tenant_id, monkeypatch
):
    job = service.submit_sample(tenant_id)
    original_finish = service.database.finish_job

    def cancel_then_finish(tenant, job_id, *, attempt_token, worker_id, used_units):
        assert service.database.request_cancellation(tenant, job_id) == "cancelling"
        return original_finish(
            tenant,
            job_id,
            attempt_token=attempt_token,
            worker_id=worker_id,
            used_units=used_units,
        )

    monkeypatch.setattr(service.database, "finish_job", cancel_then_finish)
    assert service.process_next_job() is True

    cancelled = service.database.get_job(tenant_id, job["id"])
    assert cancelled["state"] == "cancelled"
    assert cancelled["artifacts"] == []
    assert service.database.quota(tenant_id)["reserved_units"] == 0
    assert service.database.quota(tenant_id)["consumed_units"] == 0
    assert list((service.settings.data_dir / "objects").rglob("*.glb")) == []


def test_cancel_request_wins_when_running_job_fails(service, tenant_id):
    job = service.submit_sample(tenant_id)
    claimed = service.database.claim_next_job(
        worker_id="test-worker", lease_seconds=10, max_attempts=2
    )
    assert claimed and claimed["id"] == job["id"]
    assert service.database.request_cancellation(tenant_id, job["id"]) == "cancelling"

    service.database.fail_job(
        tenant_id,
        job["id"],
        attempt_token=claimed["attempt_token"],
        worker_id=claimed["worker_id"],
        code="job_failed",
        message="provider failed",
    )

    cancelled = service.database.get_job(tenant_id, job["id"])
    assert cancelled["state"] == "cancelled"
    assert cancelled["error_code"] == "cancelled"
    assert service.database.quota(tenant_id)["reserved_units"] == 0


def test_worker_recovery_requeues_once_then_fails_with_refund(service, tenant_id):
    job = service.submit_sample(tenant_id)
    claimed = service.database.claim_next_job(worker_id="worker-a", lease_seconds=1, max_attempts=2)
    assert claimed and claimed["id"] == job["id"] and claimed["attempt"] == 1
    partial = service.store.put_bytes(
        f"tenants/{tenant_id}/jobs/{job['id']}/partial.glb", b"partial", max_bytes=64
    )
    service.database.create_artifact(
        tenant_id=tenant_id,
        job_id=job["id"],
        attempt_token=claimed["attempt_token"],
        worker_id=claimed["worker_id"],
        kind="scene",
        object_key=partial.key,
        filename="partial.glb",
        media_type="model/gltf-binary",
        size_bytes=partial.size_bytes,
        sha256=partial.sha256,
        license_id="NOASSERTION",
        metadata={},
    )
    with service.database.transaction() as connection:
        connection.execute("UPDATE jobs SET lease_expires_at=0 WHERE id=?", (job["id"],))
    assert service.initialize() == {"requeued": 1, "failed": 0, "cancelled": 0}
    assert service.database.list_artifacts(tenant_id, job["id"]) == []
    assert not (service.settings.data_dir / "objects" / partial.key).exists()
    claimed = service.database.claim_next_job(worker_id="worker-b", lease_seconds=1, max_attempts=2)
    assert claimed and claimed["attempt"] == 2
    with service.database.transaction() as connection:
        connection.execute("UPDATE jobs SET lease_expires_at=0 WHERE id=?", (job["id"],))
    assert service.database.recover_jobs(max_attempts=2) == {
        "requeued": 0,
        "failed": 1,
        "cancelled": 0,
    }
    failed = service.database.get_job(tenant_id, job["id"])
    assert failed["state"] == "failed"
    assert failed["error_code"] == "worker_lost"
    assert service.database.quota(tenant_id)["reserved_units"] == 0


def test_tenant_scope_hides_jobs_and_artifacts(authenticated_client, service, tenant_id):
    job_id = authenticated_client.post("/api/jobs/sample").json()["id"]
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job_id)["artifacts"][0]

    other_token = "other-tenant-token-that-is-also-long-enough"
    service.database.provision_tenant(token=other_token, tenant_name="Other", quota_units=10)
    headers = {"Authorization": f"Bearer {other_token}"}
    assert authenticated_client.get(f"/api/jobs/{job_id}", headers=headers).status_code == 404
    assert (
        authenticated_client.get(
            f"/api/artifacts/{artifact['id']}/content", headers=headers
        ).status_code
        == 404
    )


def test_expired_share_is_not_resolved(service, tenant_id):
    job = service.submit_sample(tenant_id)
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    _, token = service.database.create_share(tenant_id, artifact["id"], ttl_seconds=-1)
    assert service.database.resolve_share(token) is None


def test_token_hashes_not_plaintext(service):
    with service.database.connect() as connection:
        stored = connection.execute("SELECT token_hash FROM api_tokens LIMIT 1").fetchone()[0]
    assert stored == token_digest(BOOTSTRAP_TOKEN)
    assert BOOTSTRAP_TOKEN not in stored
