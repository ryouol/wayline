from __future__ import annotations

from dataclasses import replace

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.database import token_digest
from lingbot_map.workspace.modal_engine import ModalLingbotEngine
from lingbot_map.workspace.service import VideoInspector, WorkspaceService

from .conftest import BOOTSTRAP_TOKEN


def fake_mp4(size: int = 64) -> bytes:
    return b"\x00\x00\x00\x18ftypisom" + b"\x00" * max(0, size - 12)


@pytest.mark.parametrize(
    ("filename", "media_type", "header"),
    [
        ("capture.mp4", "video/mp4", fake_mp4()),
        ("capture.m4v", "video/mp4", fake_mp4()),
        ("capture.mov", "video/mp4", fake_mp4()),
        ("capture.mov", "video/quicktime", fake_mp4()),
        ("capture.avi", "video/x-msvideo", b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 52),
        ("capture.mkv", "video/x-matroska", b"\x1a\x45\xdf\xa3" + b"\x00" * 60),
    ],
)
def test_public_upload_types_match_accepted_file_pairs(
    authenticated_client, filename, media_type, header
):
    configuration = authenticated_client.get("/api/config")
    assert configuration.status_code == 200
    suffix = "." + filename.rsplit(".", 1)[1]
    assert suffix in configuration.json()["acceptedVideoTypes"][media_type]
    uploaded = authenticated_client.post(
        "/api/assets", files={"file": (filename, header, media_type)}
    )
    assert uploaded.status_code == 201


def test_single_frame_upload_is_rejected_without_retaining_data_or_using_allowance(
    authenticated_client, service, tenant_id, tmp_path
):
    service.inspector = VideoInspector()
    before = service.database.quota(tenant_id)
    headers = {"Idempotency-Key": "minimum-frames-replacement"}

    def upload_frames(count):
        path = tmp_path / f"{count}-frames.avi"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
        assert writer.isOpened()
        try:
            for index in range(count):
                writer.write(np.full((48, 64, 3), index * 100, dtype=np.uint8))
        finally:
            writer.release()
        return authenticated_client.post(
            "/api/assets",
            headers=headers,
            files={"file": (path.name, path.read_bytes(), "video/x-msvideo")},
        )

    rejected = upload_frames(1)
    assert rejected.status_code == 400
    assert "at least two frames" in rejected.json()["detail"]
    assert authenticated_client.get("/api/assets").json()["assets"] == []
    assert authenticated_client.get("/api/jobs").json()["jobs"] == []
    assert authenticated_client.get("/api/submissions/upload", headers=headers).status_code == 404
    assert service.database.quota(tenant_id) == before
    assert not any(path.is_file() for path in (service.settings.data_dir / "objects").rglob("*"))

    accepted = upload_frames(2)
    assert accepted.status_code == 201
    asset = accepted.json()
    assert asset["metadata"]["frames"] == 2
    assert ModalLingbotEngine(service.settings).estimate_units(asset["metadata"], {}) == 2
    assert upload_frames(2).json()["id"] == asset["id"]
    assert (
        authenticated_client.get("/api/submissions/upload", headers=headers).json()["id"]
        == asset["id"]
    )
    assert len(authenticated_client.get("/api/assets").json()["assets"]) == 1
    assert authenticated_client.get("/api/jobs").json()["jobs"] == []
    quota = service.database.quota(tenant_id)
    for field in ("quota_units", "reserved_units", "consumed_units", "available_units"):
        assert quota[field] == before[field]


def test_upload_still_requires_an_accepted_declared_type(authenticated_client):
    response = authenticated_client.post(
        "/api/assets", files={"file": ("capture.mp4", fake_mp4(), "application/octet-stream")}
    )
    assert response.status_code == 415
    assert authenticated_client.get("/api/assets").json()["assets"] == []


@pytest.mark.parametrize("retained_fraction", [0.55, 0.85])
def test_truncated_upload_is_rejected_and_a_complete_replacement_can_be_retried(
    authenticated_client, service, tenant_id, tmp_path, retained_fraction
):
    service.inspector = VideoInspector()
    path = tmp_path / "capture.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    assert writer.isOpened()
    try:
        for index in range(20):
            writer.write(np.full((48, 64, 3), index * 10, dtype=np.uint8))
    finally:
        writer.release()
    complete = path.read_bytes()
    truncated = complete[: int(len(complete) * retained_fraction)]
    path.write_bytes(truncated)
    # The damaged container still advertises enough frames to pass metadata checks.
    assert service.inspector.inspect(path)["frames"] == 20
    before = service.database.quota(tenant_id)
    headers = {"Idempotency-Key": "truncated-capture-replacement"}

    def upload(data):
        return authenticated_client.post(
            "/api/assets",
            headers=headers,
            files={"file": (path.name, data, "video/x-msvideo")},
        )

    rejected = upload(truncated)
    assert rejected.status_code == 400
    assert "could not be decoded" in rejected.json()["detail"]
    assert authenticated_client.get("/api/assets").json()["assets"] == []
    assert authenticated_client.get("/api/jobs").json()["jobs"] == []
    assert authenticated_client.get("/api/submissions/upload", headers=headers).status_code == 404
    assert service.database.quota(tenant_id) == before
    assert not any(path.is_file() for path in (service.settings.data_dir / "objects").rglob("*"))
    with service.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM object_claims").fetchone()[0] == 0

    accepted = upload(complete)
    assert accepted.status_code == 201
    asset = accepted.json()
    assert asset["metadata"]["frames"] == 20
    assert upload(complete).json()["id"] == asset["id"]
    assert (
        authenticated_client.get("/api/submissions/upload", headers=headers).json()["id"]
        == asset["id"]
    )
    assert len(authenticated_client.get("/api/assets").json()["assets"]) == 1
    assert authenticated_client.get("/api/jobs").json()["jobs"] == []
    quota = service.database.quota(tenant_id)
    for field in ("quota_units", "reserved_units", "consumed_units", "available_units"):
        assert quota[field] == before[field]


@pytest.mark.parametrize("exceeded_limit", ["durationSeconds", "frames", "width"])
def test_upload_limits_are_checked_before_decoding_boundary_frames(
    authenticated_client, service, monkeypatch, exceeded_limit
):
    metadata = service.inspector.inspect(None)
    limits = {
        "durationSeconds": service.settings.max_video_seconds,
        "frames": service.settings.max_video_frames,
        "width": service.settings.max_video_dimension,
    }
    metadata[exceeded_limit] = limits[exceeded_limit] + 1
    monkeypatch.setattr(service.inspector, "inspect", lambda _path: metadata)

    def unexpected_decode(*_args):
        pytest.fail("Over-limit uploads must be rejected before decoding")

    monkeypatch.setattr(service.inspector, "validate_boundary_frames", unexpected_decode)
    response = authenticated_client.post(
        "/api/assets", files={"file": ("capture.mp4", fake_mp4(), "video/mp4")}
    )
    assert response.status_code == 413
    assert authenticated_client.get("/api/assets").json()["assets"] == []


@pytest.mark.parametrize("limit", [2048, 4096])
@pytest.mark.parametrize("long_side", ["width", "height"])
def test_public_resolution_limit_matches_upload_validation(
    settings, service, monkeypatch, limit, long_side
):
    runtime = replace(settings, max_video_dimension=limit)
    service.settings = runtime
    metadata = {
        "fps": 10.0,
        "frames": 100,
        "durationSeconds": 10.0,
        "width": 1080,
        "height": 1080,
        long_side: limit,
    }
    monkeypatch.setattr(service.inspector, "inspect", lambda _path: metadata.copy())
    with TestClient(create_app(runtime, service=service, start_worker=False)) as browser:
        response = browser.get("/api/config")
        assert response.status_code == 200
        assert response.json()["maxVideoDimension"] == limit
        headers = {"Authorization": f"Bearer {BOOTSTRAP_TOKEN}"}
        accepted = browser.post(
            "/api/assets",
            headers=headers,
            files={"file": ("at-limit.mp4", fake_mp4(), "video/mp4")},
        )
        assert accepted.status_code == 201
        metadata[long_side] = limit + 1
        rejected = browser.post(
            "/api/assets",
            headers=headers,
            files={"file": ("too-wide.mp4", fake_mp4(), "video/mp4")},
        )
        assert rejected.status_code == 413
        assert f"{limit}px" in rejected.json()["detail"]
        assert len(browser.get("/api/assets", headers=headers).json()["assets"]) == 1
        assert browser.get("/api/jobs", headers=headers).json()["jobs"] == []


def test_authentication_and_security_headers(client, service):
    response = client.get("/api/jobs")
    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    csp = dict(
        directive.strip().split(" ", 1)
        for directive in response.headers["content-security-policy"].split(";")
        if directive.strip()
    )
    assert csp["media-src"] == "'self' blob:"
    assert csp["script-src"] == "'self'"

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


@pytest.mark.parametrize(
    ("filename", "expected_name"),
    [
        ("a" * 116 + ".MP4", "a" * 116 + ".MP4"),
        ("a" * 117 + ".MP4", "a" * 116 + ".MP4"),
        ("part." + "a" * 180 + ".m4v", "part." + "a" * 111 + ".m4v"),
        ("." * 120 + "walkthrough.mov", "walkthrough.mov"),
        # Keep the existing stored name and receipt hash for an already-accepted upload.
        ("a" * 116 + ".MP4" + ".extra.mp4", "a" * 116 + ".MP4"),
    ],
)
def test_long_upload_filename_preserves_extension_and_receipt(
    authenticated_client, filename, expected_name
):
    files = {"file": (filename, fake_mp4(), "video/mp4")}
    headers = {"Idempotency-Key": "long-capture-name"}
    upload = authenticated_client.post("/api/assets", files=files, headers=headers)
    assert upload.status_code == 201
    assert upload.json()["name"] == expected_name
    replay = authenticated_client.post("/api/assets", files=files, headers=headers)
    assert replay.status_code == 201
    assert replay.json()["id"] == upload.json()["id"]
    assert len(authenticated_client.get("/api/assets").json()["assets"]) == 1


def test_long_upload_replays_a_receipt_with_a_different_valid_clipped_extension(
    authenticated_client,
):
    clipped = "a" * 116 + ".mp4"
    filename = clipped + ".export.mov"
    headers = {"Idempotency-Key": "previously-accepted-long-name"}
    # Prior versions persisted the first 120 characters in the receipt hash.
    previous = authenticated_client.post(
        "/api/assets", files={"file": (clipped, fake_mp4(), "video/mp4")}, headers=headers
    )
    assert previous.status_code == 201
    files = {"file": (filename, fake_mp4(), "video/mp4")}
    replay = authenticated_client.post("/api/assets", files=files, headers=headers)
    assert replay.status_code == 201
    assert replay.json()["id"] == previous.json()["id"]
    new = authenticated_client.post("/api/assets", files=files)
    assert new.status_code == 201
    assert new.json()["name"] == "a" * 116 + ".mov"


@pytest.mark.parametrize("suffix", [".exe", "without-extension", ".avi", "." + "a" * 130])
def test_long_filename_cannot_hide_an_unsupported_suffix(authenticated_client, service, suffix):
    response = authenticated_client.post(
        "/api/assets",
        files={"file": ("a" * 116 + ".mp4" + suffix, fake_mp4(), "video/mp4")},
    )
    assert response.status_code == 415
    assert authenticated_client.get("/api/assets").json()["assets"] == []
    assert not any(path.is_file() for path in (service.settings.data_dir / "objects").rglob("*"))


@pytest.mark.parametrize("filename", ["not-video.mp4", "a" * 160 + ".mp4"])
def test_upload_rejects_mismatched_content_and_removes_object(
    authenticated_client, service, filename
):
    response = authenticated_client.post(
        "/api/assets", files={"file": (filename, b"plain text", "video/mp4")}
    )
    assert response.status_code == 415
    assert list((service.settings.data_dir / "objects").rglob("*.mp4")) == []


def test_upload_submission_lookup_is_current_and_read_only(
    authenticated_client, service, tenant_id
):
    headers = {"Idempotency-Key": "uncertain-upload-key"}
    uploaded = authenticated_client.post(
        "/api/assets",
        files={"file": ("walkthrough.mp4", fake_mp4(), "video/mp4")},
        headers=headers,
    )
    assert uploaded.status_code == 201
    asset = uploaded.json()
    assert authenticated_client.get("/api/submissions/upload", headers=headers).json() == asset
    job = service.database.create_job(
        tenant_id=tenant_id,
        engine_id="synthetic-sample-v1",
        source_asset_id=asset["id"],
        params={},
        provenance={"fixture": True},
        reserve_units=0,
    )
    service.cancel_job(tenant_id, job["id"])
    expected = authenticated_client.get("/api/assets").json()["assets"][0]
    assert expected["linkedJobCount"] == 1 and not expected["deletable"]
    with service.database.connect() as connection:
        before = list(connection.iterdump())
    for _ in range(2):
        recovered = authenticated_client.get("/api/submissions/upload", headers=headers)
        assert recovered.status_code == 200
        assert recovered.headers["cache-control"] == "no-store"
        assert recovered.json() == expected, "Return current asset metadata, not a stale receipt"
        assert "object_key" not in recovered.json()
    with service.database.connect() as connection:
        assert list(connection.iterdump()) == before, "Lookup changes no receipt, quota or rate"
    assert len(list((service.settings.data_dir / "objects").rglob("*.mp4"))) == 1


def test_upload_submission_lookup_requires_a_valid_key(authenticated_client):
    for headers in [{}, {"Idempotency-Key": "short"}, {"Idempotency-Key": "x" * 201}]:
        response = authenticated_client.get("/api/submissions/upload", headers=headers)
        assert response.status_code == 422
        assert response.headers["cache-control"] == "no-store"


def test_completed_upload_receipt_survives_rate_limited_replay(settings, service):
    limited = replace(settings, upload_rate_per_minute=1)
    service.settings = limited
    headers = {
        "Authorization": f"Bearer {BOOTSTRAP_TOKEN}",
        "Idempotency-Key": "rate-limited-upload-replay",
    }
    with TestClient(create_app(limited, service=service, start_worker=False)) as client:
        first = client.post(
            "/api/assets",
            headers=headers,
            files={"file": ("walkthrough.mp4", fake_mp4(), "video/mp4")},
        )
        assert first.status_code == 201
        retry = client.post(
            "/api/assets",
            headers=headers,
            files={"file": ("walkthrough.mp4", fake_mp4(), "video/mp4")},
        )
        assert retry.status_code == 429
        assert retry.json()["code"] == "rate_limit_exceeded"
        recovered = client.get("/api/submissions/upload", headers=headers)
        assert recovered.status_code == 200 and recovered.json() == first.json()
        assert recovered.headers["cache-control"] == "no-store"
        assert len(client.get("/api/assets", headers=headers).json()["assets"]) == 1
        assert client.get("/api/jobs", headers=headers).json()["jobs"] == []


@pytest.mark.parametrize(
    "unavailable", ["missing", "expired", "pending", "scope", "tenant", "deleted"]
)
def test_upload_submission_lookup_respects_identity_and_lifetime(
    unavailable, authenticated_client, service, tenant_id
):
    headers = {"Idempotency-Key": "scoped-upload-key"}
    asset = authenticated_client.post(
        "/api/assets",
        files={"file": ("walkthrough.mp4", fake_mp4(), "video/mp4")},
        headers=headers,
    ).json()
    if unavailable == "missing":
        headers = {"Idempotency-Key": "unknown-upload-key"}
    elif unavailable == "deleted":
        service.delete_asset(tenant_id, asset["id"])
    else:
        other = service.database.provision_tenant(
            token="other-upload-lookup-test-token", tenant_name="Other", quota_units=100
        )["tenant_id"]
        column, value = {
            "expired": ("expires_at", 0),
            "pending": ("state", "in_progress"),
            "scope": ("scope", "POST:/api/jobs/research"),
            "tenant": ("tenant_id", other),
        }[unavailable]
        with service.database.connect() as connection:
            connection.execute(f"UPDATE idempotency_keys SET {column}=?", (value,))
    response = authenticated_client.get("/api/submissions/upload", headers=headers)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    authenticated_client.cookies.clear()
    response = authenticated_client.get("/api/submissions/upload", headers=headers)
    assert response.status_code == 401 and response.headers["cache-control"] == "no-store"


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


@pytest.mark.parametrize("state", ["queued", "running", "failed", "cancelled"])
def test_non_ready_list_has_complete_detail_fields(authenticated_client, service, tenant_id, state):
    job_id = service.submit_sample(tenant_id)["id"]
    assert service.process_next_job()
    assert service.database.get_job(tenant_id, job_id)["artifacts"]
    # Keep stored artifacts to verify that they are only published in ready state.
    with service.database.transaction() as connection:
        connection.execute(
            "UPDATE jobs SET state=?,stage=? WHERE id=? AND tenant_id=?",
            (state, state, job_id, tenant_id),
        )
    summary = authenticated_client.get("/api/jobs").json()["jobs"][0]
    detail = authenticated_client.get(f"/api/jobs/{job_id}").json()
    assert summary["id"] == job_id
    assert detail == {**summary, "artifacts": []}


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
    token = share_path.split("#", 1)[1]
    assert share_path.startswith("/s#")
    assert authenticated_client.get("/s").status_code == 200
    assert authenticated_client.get("/api/public/share").status_code == 404
    assert authenticated_client.get("/api/public/share/content").status_code == 404
    assert authenticated_client.get("/api/public/share?token=" + token).status_code == 404
    public = authenticated_client.get(
        "/api/public/share", headers={"Authorization": f"Bearer {token}"}
    )
    assert public.status_code == 200
    assert token not in str(public.url)
    assert public.headers["cache-control"] == "no-store"
    assert token not in public.text
    assert public.json()["artifact"]["licenseId"] == "CC0-1.0"
    public_content = authenticated_client.get(
        "/api/public/share/content", headers={"Authorization": f"Bearer {token}"}
    )
    assert public_content.content[:4] == b"glTF"

    deleted = authenticated_client.delete(f"/api/jobs/{job_id}")
    assert deleted.status_code == 202
    assert deleted.json()["state"] == "deleting"
    assert authenticated_client.get(scene["viewUrl"]).status_code == 404
    assert (
        authenticated_client.get(
            "/api/public/share", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 404
    )
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
