from __future__ import annotations

import io
import sqlite3
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.database import (
    Database,
    QuotaExceeded,
    RateLimitExceeded,
    StaleAttempt,
)
from lingbot_map.workspace.engines import (
    EngineContext,
    EngineDescriptor,
    EngineResult,
    JobCancelled,
    ReconstructionEngine,
)
from lingbot_map.workspace.service import UploadRejected, WorkspaceService
from lingbot_map.workspace.storage import LocalObjectStore

from .conftest import BOOTSTRAP_TOKEN, StubInspector
from .test_workspace_api import fake_mp4


def test_schema_one_migrates_in_place_with_new_durability_tables(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta(version INTEGER NOT NULL);
            INSERT INTO schema_meta VALUES(1);
            CREATE TABLE tenants(
                id TEXT PRIMARY KEY,name TEXT NOT NULL,quota_units INTEGER NOT NULL,
                reserved_units INTEGER NOT NULL DEFAULT 0,
                consumed_units INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL
            );
            INSERT INTO tenants VALUES('ten_legacy','Legacy',100,0,0,1);
            CREATE TABLE jobs(
                id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,source_asset_id TEXT,
                engine_id TEXT NOT NULL,state TEXT NOT NULL,stage TEXT NOT NULL,
                progress REAL NOT NULL,params_json TEXT NOT NULL,
                provenance_json TEXT NOT NULL,reserved_units INTEGER NOT NULL,
                used_units INTEGER NOT NULL,cancellation_requested INTEGER NOT NULL,
                attempt INTEGER NOT NULL,lease_expires_at REAL,error_code TEXT,
                error_message TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL,
                started_at REAL,finished_at REAL
            );
            CREATE TABLE artifacts(
                id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,job_id TEXT NOT NULL,
                kind TEXT NOT NULL,object_key TEXT NOT NULL UNIQUE,filename TEXT NOT NULL,
                media_type TEXT NOT NULL,size_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,
                license_id TEXT NOT NULL,metadata_json TEXT NOT NULL,created_at REAL NOT NULL
            );
            """
        )

    database = Database(path)
    database.initialize()
    with database.connect() as connection:
        assert connection.execute("SELECT version FROM schema_meta").fetchone()[0] == 3
        assert connection.execute("SELECT name FROM tenants").fetchone()[0] == "Legacy"
        tenant_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tenants)").fetchall()
        }
        job_columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
        artifact_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(artifacts)").fetchall()
        }
        claim_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(object_claims)").fetchall()
        }
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"storage_limit_bytes", "asset_limit", "share_limit"} <= tenant_columns
    assert {"attempt_token", "worker_id"} <= job_columns
    assert "attempt_token" in artifact_columns
    assert {"size_bytes", "materialized", "purpose"} <= claim_columns
    assert {"deletion_outbox", "idempotency_keys", "rate_buckets", "object_claims"} <= tables


def test_schema_two_invalidates_unrecoverable_sessions_and_preserves_claims(tmp_path):
    path = tmp_path / "schema-two.sqlite3"
    database = Database(path)
    database.initialize()
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            DROP TABLE sessions;
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE, csrf_hash TEXT NOT NULL,
                expires_at REAL NOT NULL, created_at REAL NOT NULL
            );
            INSERT INTO sessions VALUES('ses_old','ten_old','usr_old','token','csrf',9999999999,1);
            DROP TABLE object_claims;
            CREATE TABLE object_claims (
                object_key TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0, expires_at REAL NOT NULL,
                created_at REAL NOT NULL
            );
            INSERT INTO object_claims VALUES('tenants/ten_old/orphan.bin','ten_old',42,1,1);
            UPDATE schema_meta SET version=2;
            """
        )

    database.initialize()
    with database.connect() as connection:
        assert connection.execute("SELECT version FROM schema_meta").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
        claim = connection.execute(
            "SELECT size_bytes,materialized,purpose FROM object_claims"
        ).fetchone()
    assert tuple(claim) == (42, 0, "legacy")


def test_only_expired_leases_recover_and_old_attempt_cannot_mutate(service, tenant_id):
    job = service.submit_sample(tenant_id)
    first = service.database.claim_next_job(
        worker_id="worker-a", lease_seconds=3600, max_attempts=2
    )
    assert first and service.database.recover_jobs(max_attempts=2) == {
        "requeued": 0,
        "failed": 0,
        "cancelled": 0,
    }

    with service.database.transaction() as connection:
        connection.execute("UPDATE jobs SET lease_expires_at=0 WHERE id=?", (job["id"],))
    assert service.database.recover_jobs(max_attempts=2) == {
        "requeued": 1,
        "failed": 0,
        "cancelled": 0,
    }
    second = service.database.claim_next_job(
        worker_id="worker-b", lease_seconds=3600, max_attempts=2
    )
    assert second and second["attempt_token"] != first["attempt_token"]

    with pytest.raises(StaleAttempt):
        service.database.update_job_progress(
            tenant_id,
            job["id"],
            attempt_token=first["attempt_token"],
            worker_id=first["worker_id"],
            stage="storing",
            progress=0.9,
            lease_seconds=30,
        )

    current = service.store.put_bytes(
        f"tenants/{tenant_id}/jobs/{job['id']}/attempts/{second['attempt_token']}/scene.glb",
        b"current",
        max_bytes=64,
    )
    artifact = service.database.create_artifact(
        tenant_id=tenant_id,
        job_id=job["id"],
        attempt_token=second["attempt_token"],
        worker_id=second["worker_id"],
        kind="scene",
        object_key=current.key,
        filename="scene.glb",
        media_type="model/gltf-binary",
        size_bytes=current.size_bytes,
        sha256=current.sha256,
        license_id="CC0-1.0",
        metadata={},
    )
    stale = service.store.put_bytes(
        f"tenants/{tenant_id}/jobs/{job['id']}/attempts/{first['attempt_token']}/stale.glb",
        b"stale",
        max_bytes=64,
    )
    service._discard_attempt_artifacts(tenant_id, job["id"], first["attempt_token"], [stale])
    assert service.database.get_artifact(tenant_id, artifact["id"])["id"] == artifact["id"]
    assert service.store.path_for_local_use(current.key).is_file()


def test_revoked_bootstrap_token_cannot_be_silently_reactivated(service):
    replacement = "replacement-bootstrap-token-that-is-long-enough"
    service.database.bootstrap(token=replacement, tenant_name="Local", quota_units=100)
    assert service.database.authenticate_api_token(BOOTSTRAP_TOKEN) is None
    assert service.database.authenticate_api_token(replacement) is not None
    with pytest.raises(RuntimeError, match="previously revoked"):
        service.database.bootstrap(
            token=BOOTSTRAP_TOKEN,
            tenant_name="Local",
            quota_units=100,
        )


class CooperativeEngine(ReconstructionEngine):
    def __init__(self, started: threading.Event):
        self.started = started

    @property
    def descriptor(self) -> EngineDescriptor:
        return EngineDescriptor(
            id="synthetic-sample-v1",
            name="cooperative test engine",
            available=True,
            research_only=False,
            commercially_cleared=True,
        )

    def estimate_units(self, source_metadata, params):
        return 1

    def provenance(self):
        return {"engine": self.descriptor.id, "license": "CC0-1.0"}

    def run(self, context: EngineContext, progress, cancelled) -> EngineResult:
        self.started.set()
        while not cancelled():
            time.sleep(0.01)
        raise JobCancelled("shutdown requested")


def test_shutdown_cancels_active_attempt_waits_and_requeues(settings):
    started = threading.Event()
    service = WorkspaceService(
        replace(settings, shutdown_timeout_seconds=2),
        engines={"synthetic-sample-v1": CooperativeEngine(started)},
    )
    service.initialize()
    tenant_id = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
    job = service.submit_sample(tenant_id)
    service.start_worker()
    assert started.wait(1)
    service.stop_worker()
    recovered = service.database.get_job(tenant_id, job["id"])
    assert recovered["state"] == "queued"
    assert recovered["attempt"] == 0
    assert service.database.quota(tenant_id)["reserved_units"] == 1
    assert service._worker is None


def test_cancelled_lost_worker_settles_and_refunds_instead_of_sticking(service, tenant_id):
    job = service.submit_sample(tenant_id)
    claimed = service.database.claim_next_job(
        worker_id="lost-worker", lease_seconds=3600, max_attempts=2
    )
    assert claimed and service.database.request_cancellation(tenant_id, job["id"]) == "cancelling"
    with service.database.transaction() as connection:
        connection.execute("UPDATE jobs SET lease_expires_at=0 WHERE id=?", (job["id"],))

    assert service.database.recover_jobs(max_attempts=2) == {
        "requeued": 0,
        "failed": 0,
        "cancelled": 1,
    }
    settled = service.database.get_job(tenant_id, job["id"])
    assert settled["state"] == "cancelled"
    assert service.database.quota(tenant_id)["reserved_units"] == 0


def test_failed_object_delete_remains_durable_and_retries(service, tenant_id, monkeypatch):
    job = service.submit_sample(tenant_id)
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    path = service.store.path_for_local_use(artifact["object_key"])
    original_delete = service.store.delete

    def fail_delete(_key):
        raise OSError("object store unavailable")

    monkeypatch.setattr(service.store, "delete", fail_delete)
    assert service.delete_job(tenant_id, job["id"])["state"] == "deleting"
    assert service.database.pending_deletion_count() > 0
    assert path.exists()
    with pytest.raises(KeyError):
        service.database.get_job(tenant_id, job["id"])

    monkeypatch.setattr(service.store, "delete", original_delete)
    with service.database.transaction() as connection:
        connection.execute("UPDATE deletion_outbox SET next_attempt_at=0")
    service.drain_deletions(limit=100)
    assert service.database.pending_deletion_count() == 0
    assert not path.exists()


def test_transactional_storage_job_and_rate_quotas(settings):
    limited = replace(
        settings,
        tenant_storage_bytes=100,
        tenant_max_jobs=1,
        job_rate_per_minute=1,
    )
    service = WorkspaceService(limited, inspector=StubInspector())
    service.initialize()
    tenant_id = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
    first = service.submit_sample(tenant_id)
    with pytest.raises(QuotaExceeded, match="job count"):
        service.submit_sample(tenant_id)
    service.process_next_job()
    assert service.database.get_job(tenant_id, first["id"])["state"] == "failed"
    assert service.database.quota(tenant_id)["stored_bytes"] == 0

    rate_limited = WorkspaceService(
        replace(
            settings,
            data_dir=settings.data_dir.parent / "rate-workspace",
            job_rate_per_minute=1,
            tenant_max_jobs=10,
        ),
        inspector=StubInspector(),
    )
    rate_limited.initialize()
    other_tenant = rate_limited.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
    rate_limited.submit_sample(other_tenant)
    with pytest.raises(RateLimitExceeded):
        rate_limited.submit_sample(other_tenant)


def test_concurrent_job_quota_reservation_is_atomic(settings):
    limited = replace(settings, tenant_max_jobs=1, job_rate_per_minute=10)
    service = WorkspaceService(limited, inspector=StubInspector())
    service.initialize()
    tenant_id = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def submit() -> None:
        barrier.wait()
        try:
            service.submit_sample(tenant_id)
        except QuotaExceeded:
            outcomes.append("quota")
        else:
            outcomes.append("created")

    threads = [threading.Thread(target=submit) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()

    assert sorted(outcomes) == ["created", "quota"]
    quota = service.database.quota(tenant_id)
    assert quota["job_count"] == 1
    assert quota["reserved_units"] == 1


def test_unattached_upload_limit_removes_rejected_object(settings):
    limited = replace(settings, tenant_max_assets=2, tenant_max_unattached_assets=1)
    service = WorkspaceService(limited, inspector=StubInspector())
    with TestClient(create_app(limited, service=service, start_worker=False)) as client:
        login = client.post("/api/session", json={"token": BOOTSTRAP_TOKEN})
        client.headers["X-CSRF-Token"] = login.json()["csrfToken"]
        assert (
            client.post(
                "/api/assets", files={"file": ("one.mp4", fake_mp4(), "video/mp4")}
            ).status_code
            == 201
        )
        rejected = client.post(
            "/api/assets", files={"file": ("two.mp4", fake_mp4(80), "video/mp4")}
        )
        assert rejected.status_code == 409
        assert rejected.json()["code"] == "quota_exceeded"
    assert len(list((limited.data_dir / "objects").rglob("*.mp4"))) == 1


def test_rejected_upload_cleanup_is_durable_during_store_outage(service, tenant_id, monkeypatch):
    original_delete = service.store.delete

    def fail_delete(_key):
        raise OSError("object store unavailable")

    monkeypatch.setattr(service.store, "delete", fail_delete)
    with pytest.raises(UploadRejected, match="does not match"):
        service.upload_video(
            tenant_id=tenant_id,
            filename="mismatch.avi",
            media_type="video/x-msvideo",
            stream=io.BytesIO(fake_mp4()),
        )
    assert service.database.pending_deletion_count() == 1
    assert len(list((service.settings.data_dir / "objects").rglob("*.avi"))) == 1

    monkeypatch.setattr(service.store, "delete", original_delete)
    with service.database.transaction() as connection:
        connection.execute("UPDATE deletion_outbox SET next_attempt_at=0")
    service.drain_deletions()
    assert service.database.pending_deletion_count() == 0
    assert list((service.settings.data_dir / "objects").rglob("*.avi")) == []


def test_rejected_upload_still_consumes_durable_start_rate(settings):
    limited = replace(settings, upload_rate_per_minute=1)
    service = WorkspaceService(limited, inspector=StubInspector())
    service.initialize()
    tenant_id = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
    with pytest.raises(UploadRejected, match="does not match"):
        service.upload_video(
            tenant_id=tenant_id,
            filename="mismatch.avi",
            media_type="video/x-msvideo",
            stream=io.BytesIO(fake_mp4()),
        )
    with pytest.raises(RateLimitExceeded):
        service.upload_video(
            tenant_id=tenant_id,
            filename="walkthrough.mp4",
            media_type="video/mp4",
            stream=io.BytesIO(fake_mp4()),
        )


def test_cursor_inventories_and_route_scoped_idempotency(authenticated_client, service, tenant_id):
    key = "same-request-key-0001"
    headers = {"Idempotency-Key": key}
    first = authenticated_client.post("/api/jobs/sample", headers=headers)
    replay = authenticated_client.post("/api/jobs/sample", headers=headers)
    assert first.status_code == replay.status_code == 202
    assert first.json()["id"] == replay.json()["id"]
    assert len(service.database.list_jobs(tenant_id)) == 1

    for index in range(3):
        authenticated_client.post(
            "/api/jobs/sample", headers={"Idempotency-Key": f"page-key-{index:08d}"}
        )
    page_one = authenticated_client.get("/api/jobs?limit=2").json()
    assert len(page_one["jobs"]) == 2 and page_one["nextCursor"]
    page_two = authenticated_client.get(
        "/api/jobs", params={"limit": 2, "cursor": page_one["nextCursor"]}
    ).json()
    first_ids = {item["id"] for item in page_one["jobs"]}
    second_ids = {item["id"] for item in page_two["jobs"]}
    assert not first_ids & second_ids

    for index in range(3):
        assert (
            authenticated_client.post(
                "/api/assets",
                files={"file": (f"walkthrough-{index}.mp4", fake_mp4(), "video/mp4")},
            ).status_code
            == 201
        )
    asset_page_one = authenticated_client.get("/api/assets?limit=2").json()
    asset_page_two = authenticated_client.get(
        "/api/assets", params={"limit": 2, "cursor": asset_page_one["nextCursor"]}
    ).json()
    assert len(asset_page_one["assets"]) == 2 and asset_page_one["nextCursor"]
    assert not {item["id"] for item in asset_page_one["assets"]} & {
        item["id"] for item in asset_page_two["assets"]
    }

    assert service.process_next_job() is True
    artifact = service.database.get_job(tenant_id, first.json()["id"])["artifacts"][0]
    for seconds in (300, 600, 900):
        assert (
            authenticated_client.post(
                f"/api/artifacts/{artifact['id']}/shares",
                json={"ttlSeconds": seconds},
            ).status_code
            == 201
        )
    share_page_one = authenticated_client.get("/api/shares?limit=2").json()
    share_page_two = authenticated_client.get(
        "/api/shares", params={"limit": 2, "cursor": share_page_one["nextCursor"]}
    ).json()
    assert len(share_page_one["shares"]) == 2 and share_page_one["nextCursor"]
    assert not {item["id"] for item in share_page_one["shares"]} & {
        item["id"] for item in share_page_two["shares"]
    }


def test_upload_idempotency_reuses_asset_and_deletes_duplicate_object(
    authenticated_client, service
):
    headers = {"Idempotency-Key": "upload-request-key-0001"}
    first = authenticated_client.post(
        "/api/assets",
        files={"file": ("walkthrough.mp4", fake_mp4(), "video/mp4")},
        headers=headers,
    )
    replay = authenticated_client.post(
        "/api/assets",
        files={"file": ("walkthrough.mp4", fake_mp4(), "video/mp4")},
        headers=headers,
    )
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    assert len(list((service.settings.data_dir / "objects").rglob("*.mp4"))) == 1


def test_share_idempotency_replays_without_storing_raw_capability(
    authenticated_client, service, tenant_id
):
    job = authenticated_client.post("/api/jobs/sample").json()
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    headers = {"Idempotency-Key": "share-request-key-0001"}
    first = authenticated_client.post(
        f"/api/artifacts/{artifact['id']}/shares",
        json={"ttlSeconds": 300},
        headers=headers,
    )
    replay = authenticated_client.post(
        f"/api/artifacts/{artifact['id']}/shares",
        json={"ttlSeconds": 300},
        headers=headers,
    )
    assert first.json() == replay.json()
    token = first.json()["url"].rsplit("/", 1)[-1]
    with service.database.connect() as connection:
        record = connection.execute(
            "SELECT response_json FROM idempotency_keys WHERE scope LIKE 'POST:/api/artifacts%'"
        ).fetchone()[0]
        share_count = connection.execute("SELECT COUNT(*) FROM shares").fetchone()[0]
    assert token not in record
    assert share_count == 1
    conflict = authenticated_client.post(
        f"/api/artifacts/{artifact['id']}/shares",
        json={"ttlSeconds": 600},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"


def test_reused_expired_share_idempotency_key_gets_a_fresh_capability(
    authenticated_client, service, tenant_id
):
    job = authenticated_client.post("/api/jobs/sample").json()
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    headers = {"Idempotency-Key": "reusable-share-key-0001"}
    first = authenticated_client.post(
        f"/api/artifacts/{artifact['id']}/shares",
        json={"ttlSeconds": 300},
        headers=headers,
    )
    with service.database.transaction() as connection:
        connection.execute("UPDATE idempotency_keys SET expires_at=0")
    second = authenticated_client.post(
        f"/api/artifacts/{artifact['id']}/shares",
        json={"ttlSeconds": 300},
        headers=headers,
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["url"] != second.json()["url"]


def test_public_research_share_has_explicit_noncommercial_warning(
    authenticated_client, service, tenant_id
):
    job = authenticated_client.post("/api/jobs/sample").json()
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    with service.database.transaction() as connection:
        connection.execute(
            "UPDATE artifacts SET metadata_json=? WHERE id=?",
            ('{"researchOnly":true}', artifact["id"]),
        )
    share = authenticated_client.post(
        f"/api/artifacts/{artifact['id']}/shares", json={"ttlSeconds": 300}
    ).json()
    token = share["url"].rsplit("/", 1)[-1]
    public = authenticated_client.get(f"/api/public/shares/{token}").json()
    assert public["researchOnly"] is True
    assert "Do not use this artifact commercially" in public["commercialWarning"]


def test_asset_share_inventories_and_bulk_deletion(authenticated_client, service, tenant_id):
    upload = authenticated_client.post(
        "/api/assets", files={"file": ("orphan.mp4", fake_mp4(), "video/mp4")}
    ).json()
    job = authenticated_client.post("/api/jobs/sample").json()
    service.process_next_job()
    artifact = service.database.get_job(tenant_id, job["id"])["artifacts"][0]
    share = authenticated_client.post(
        f"/api/artifacts/{artifact['id']}/shares", json={"ttlSeconds": 300}
    ).json()
    assets = authenticated_client.get("/api/assets").json()["assets"]
    shares = authenticated_client.get("/api/shares").json()["shares"]
    assert [item["id"] for item in assets] == [upload["id"]]
    assert [item["id"] for item in shares] == [share["id"]]

    response = authenticated_client.post(
        "/api/bulk-delete",
        json={"jobIds": [job["id"]], "assetIds": [upload["id"]], "shareIds": [share["id"]]},
        headers={"Idempotency-Key": "bulk-delete-key-0001"},
    )
    assert response.status_code == 202
    assert response.json()["errors"] == {}
    assert authenticated_client.get("/api/assets").json()["assets"] == []
    assert authenticated_client.get("/api/shares").json()["shares"] == []
    assert authenticated_client.get("/api/jobs").json()["jobs"] == []


def test_retention_and_storage_reconciliation_are_bounded(service, tenant_id):
    orphan = service.store.put_bytes(
        f"tenants/{tenant_id}/orphan/untracked.bin", b"orphan", max_bytes=64
    )
    result = service.reconcile_storage()
    assert result["orphans"] == 1
    assert service.database.pending_deletion_count() == 1
    service.drain_deletions()
    with pytest.raises(FileNotFoundError):
        service.store.path_for_local_use(orphan.key)

    job = service.submit_sample(tenant_id)
    service.process_next_job()
    with service.database.transaction() as connection:
        connection.execute("UPDATE jobs SET finished_at=0,updated_at=0 WHERE id=?", (job["id"],))
        connection.execute("UPDATE usage_ledger SET created_at=0 WHERE job_id=?", (job["id"],))
    retained = service.database.run_retention(terminal_before=1, unattached_before=1)
    assert retained["jobs"] == 1
    assert retained["ledger"] == 2
    service.drain_deletions()
    assert service.database.quota(tenant_id)["job_count"] == 0


class RecordingStore:
    def __init__(self, root: Path):
        self.delegate = LocalObjectStore(root)
        self.operations: list[str] = []

    def put_stream(self, key, stream, *, max_bytes):
        self.operations.append("put_stream")
        return self.delegate.put_stream(key, stream, max_bytes=max_bytes)

    def put_bytes(self, key, payload, *, max_bytes):
        self.operations.append("put_bytes")
        return self.delegate.put_bytes(key, payload, max_bytes=max_bytes)

    def open(self, key):
        return self.delegate.open(key)

    def path_for_local_use(self, key):
        return self.delegate.path_for_local_use(key)

    def delete(self, key):
        self.operations.append("delete")
        self.delegate.delete(key)

    def copy_from_path(self, key, source, *, max_bytes):
        self.operations.append("copy_from_path")
        return self.delegate.copy_from_path(key, source, max_bytes=max_bytes)

    def iter_keys(self, prefix=""):
        return self.delegate.iter_keys(prefix)


def test_object_store_protocol_is_injected_and_exercised(settings):
    store = RecordingStore(settings.data_dir / "injected-objects")
    service = WorkspaceService(settings, inspector=StubInspector(), store=store)
    service.initialize()
    tenant_id = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
    service.submit_sample(tenant_id)
    service.process_next_job()
    assert service.store is store
    assert "put_bytes" in store.operations
    assert len(store.iter_keys("tenants")) == 2


def test_upload_and_artifact_claims_exist_before_object_io(service, tenant_id, monkeypatch):
    observed: list[tuple[str, int, int]] = []
    original_stream = service.store.put_stream
    original_bytes = service.store.put_bytes

    def assert_reserved(key):
        with service.database.connect() as connection:
            claim = connection.execute(
                "SELECT purpose,size_bytes,materialized FROM object_claims WHERE object_key=?",
                (key,),
            ).fetchone()
        assert claim is not None
        observed.append((claim["purpose"], claim["size_bytes"], claim["materialized"]))

    def put_stream(key, stream, *, max_bytes):
        assert_reserved(key)
        return original_stream(key, stream, max_bytes=max_bytes)

    def put_bytes(key, payload, *, max_bytes):
        assert_reserved(key)
        return original_bytes(key, payload, max_bytes=max_bytes)

    monkeypatch.setattr(service.store, "put_stream", put_stream)
    monkeypatch.setattr(service.store, "put_bytes", put_bytes)
    service.upload_video(
        tenant_id=tenant_id,
        filename="walkthrough.mp4",
        media_type="video/mp4",
        stream=io.BytesIO(fake_mp4()),
    )
    service.submit_sample(tenant_id)
    assert service.process_next_job() is True
    assert ("upload", service.settings.max_upload_bytes, 0) in observed
    assert ("artifact", service.settings.max_artifact_bytes, 0) in observed


def test_reconciliation_does_not_delete_an_inflight_claim(service, tenant_id):
    key = f"tenants/{tenant_id}/assets/inflight.mp4"
    service.database.claim_object(tenant_id, key, ttl_seconds=300)
    stored = service.store.put_bytes(key, fake_mp4(), max_bytes=1_024)
    service.database.size_object_claim(tenant_id, key, stored.size_bytes)

    assert service.reconcile_storage() == {"orphans": 0, "missing": 0}
    assert service.store.path_for_local_use(key).is_file()
    assert service.database.quota(tenant_id)["stored_bytes"] == stored.size_bytes

    service.database.release_object_claim(tenant_id, key)
    assert service.reconcile_storage() == {"orphans": 1, "missing": 0}
    service.drain_deletions()
    with pytest.raises(FileNotFoundError):
        service.store.path_for_local_use(key)


def test_inflight_claim_bytes_are_reserved_transactionally(settings):
    limited = replace(settings, tenant_storage_bytes=100)
    service = WorkspaceService(limited, inspector=StubInspector())
    service.initialize()
    tenant_id = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
    first = f"tenants/{tenant_id}/assets/first.mp4"
    second = f"tenants/{tenant_id}/assets/second.mp4"
    service.database.claim_object(tenant_id, first, ttl_seconds=300)
    service.database.claim_object(tenant_id, second, ttl_seconds=300)
    service.database.size_object_claim(tenant_id, first, 80)
    with pytest.raises(QuotaExceeded, match="storage byte"):
        service.database.size_object_claim(tenant_id, second, 30)
    assert service.database.quota(tenant_id)["stored_bytes"] == 80


def test_pre_io_claims_enforce_global_bytes_and_inflight_slots(settings):
    limited = replace(
        settings,
        max_upload_bytes=80,
        max_artifact_bytes=100,
        global_storage_bytes=120,
        storage_min_free_bytes=0,
        global_max_inflight_objects=2,
        tenant_max_inflight_objects=2,
    )
    service = WorkspaceService(limited, inspector=StubInspector())
    service.initialize()
    tenant_id = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
    first = f"tenants/{tenant_id}/assets/first-reserved.mp4"
    second = f"tenants/{tenant_id}/assets/second-reserved.mp4"
    service._claim_object(tenant_id, first, reserve_bytes=80, purpose="upload")
    assert service.database.quota(tenant_id)["stored_bytes"] == 80
    with pytest.raises(QuotaExceeded, match="global storage"):
        service._claim_object(tenant_id, second, reserve_bytes=80, purpose="upload")
    assert not service.store.iter_keys("tenants")

    slots = WorkspaceService(
        replace(
            limited,
            data_dir=limited.data_dir.parent / "slot-workspace",
            global_storage_bytes=1_000,
            global_max_inflight_objects=2,
            tenant_max_inflight_objects=1,
        ),
        inspector=StubInspector(),
    )
    slots.initialize()
    slots_tenant = slots.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
    first_slot = f"tenants/{slots_tenant}/assets/one.mp4"
    slots._claim_object(slots_tenant, first_slot, reserve_bytes=80, purpose="upload")
    with pytest.raises(QuotaExceeded, match="tenant in-flight"):
        slots._claim_object(
            slots_tenant,
            f"tenants/{slots_tenant}/assets/two.mp4",
            reserve_bytes=80,
            purpose="upload",
        )
    other = slots.database.provision_tenant(
        token="second-budget-tenant-token-long-enough",
        tenant_name="Second budget tenant",
        quota_units=100,
        storage_limit_bytes=1_000,
    )
    second_slot = f"tenants/{other['tenant_id']}/assets/one.mp4"
    slots._claim_object(other["tenant_id"], second_slot, reserve_bytes=80, purpose="upload")
    with pytest.raises(QuotaExceeded, match="global in-flight"):
        slots._claim_object(
            other["tenant_id"],
            f"tenants/{other['tenant_id']}/assets/two.mp4",
            reserve_bytes=80,
            purpose="upload",
        )

    slots.database.release_object_claim(slots_tenant, first_slot)
    slots.database.release_object_claim(other["tenant_id"], second_slot)
    with pytest.raises(QuotaExceeded, match="minimum-free-space"):
        slots.database.claim_object(
            slots_tenant,
            f"tenants/{slots_tenant}/assets/disk-budget.mp4",
            ttl_seconds=300,
            reserve_bytes=80,
            purpose="upload",
            global_storage_bytes=1_000,
            physical_free_bytes=100,
            min_free_bytes=30,
            global_inflight_limit=2,
            tenant_inflight_limit=1,
        )


def test_interrupted_claim_recovery_measures_orphan_bytes(service, tenant_id):
    key = f"tenants/{tenant_id}/assets/interrupted.mp4"
    service._claim_object(tenant_id, key, reserve_bytes=1_024, purpose="upload")
    stored = service.store.put_bytes(key, b"measured orphan", max_bytes=1_024)

    assert service.recover_object_claims(force=True) == 1
    with service.database.connect() as connection:
        outbox_size = connection.execute(
            "SELECT size_bytes FROM deletion_outbox WHERE object_key=?", (key,)
        ).fetchone()[0]
        claim_count = connection.execute(
            "SELECT COUNT(*) FROM object_claims WHERE object_key=?", (key,)
        ).fetchone()[0]
    assert outbox_size == stored.size_bytes
    assert claim_count == 0
    assert service.database.quota(tenant_id)["stored_bytes"] == stored.size_bytes


def test_idempotency_completion_failure_rolls_back_business_mutation(
    service, tenant_id, monkeypatch
):
    original = service.database.complete_idempotency

    def fail_completion(*_args, **_kwargs):
        raise OSError("simulated commit boundary failure")

    monkeypatch.setattr(service.database, "complete_idempotency", fail_completion)
    with pytest.raises(OSError, match="commit boundary"):
        service.submit_sample(tenant_id, idempotency_key="atomic-submit-key-0001")
    assert service.database.list_jobs(tenant_id) == []
    assert service.database.quota(tenant_id)["reserved_units"] == 0
    with service.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM idempotency_keys").fetchone()[0] == 0

    monkeypatch.setattr(service.database, "complete_idempotency", original)
    created = service.submit_sample(tenant_id, idempotency_key="atomic-submit-key-0001")
    assert created["state"] == "queued"


def test_worker_survives_iteration_failure_with_backoff(service, monkeypatch):
    recovered = threading.Event()
    calls = 0

    def flaky_iteration():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("transient database failure")
        recovered.set()
        return False

    monkeypatch.setattr(service, "_worker_iteration", flaky_iteration)
    service.start_worker()
    try:
        assert recovered.wait(timeout=2)
        assert service._worker and service._worker.is_alive()
    finally:
        service.stop_worker()


def test_future_schema_fails_before_any_schema_mutation(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta(version INTEGER NOT NULL);
            INSERT INTO schema_meta VALUES(999);
            CREATE TABLE future_only(marker TEXT NOT NULL);
            INSERT INTO future_only VALUES('preserve-me');
            """
        )
        before = connection.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    before_bytes = path.read_bytes()
    with pytest.raises(RuntimeError, match="schema 999"):
        Database(path).initialize()
    with sqlite3.connect(path) as connection:
        after = connection.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        assert connection.execute("SELECT marker FROM future_only").fetchone()[0] == "preserve-me"
    assert after == before
    assert path.read_bytes() == before_bytes
    assert not Path(f"{path}-wal").exists()
    assert not Path(f"{path}-shm").exists()


def test_partial_attempt_artifacts_are_not_published(authenticated_client, service, tenant_id):
    job = service.submit_sample(tenant_id)
    claimed = service.database.claim_next_job(
        worker_id="publishing-worker", lease_seconds=30, max_attempts=2
    )
    assert claimed and claimed["id"] == job["id"]
    stored = service.store.put_bytes(
        f"tenants/{tenant_id}/jobs/{job['id']}/attempts/{claimed['attempt_token']}/partial.glb",
        b"partial",
        max_bytes=64,
    )
    artifact = service.database.create_artifact(
        tenant_id=tenant_id,
        job_id=job["id"],
        attempt_token=claimed["attempt_token"],
        worker_id=claimed["worker_id"],
        kind="scene",
        object_key=stored.key,
        filename="partial.glb",
        media_type="model/gltf-binary",
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        license_id="NOASSERTION",
        metadata={},
    )

    detail = authenticated_client.get(f"/api/jobs/{job['id']}")
    assert detail.status_code == 200
    assert detail.json()["artifacts"] == []
    assert authenticated_client.get(f"/api/artifacts/{artifact['id']}/content").status_code == 404
    assert (
        authenticated_client.post(
            f"/api/artifacts/{artifact['id']}/shares", json={"ttlSeconds": 300}
        ).status_code
        == 404
    )
