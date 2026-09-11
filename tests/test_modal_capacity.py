import io
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import modal
import pytest
from starlette.requests import Request

from lingbot_map.workspace.config import RESEARCH_ACKNOWLEDGEMENT
from lingbot_map.workspace.database import StaleAttempt
from lingbot_map.workspace.engines import LingbotResearchEngine
from lingbot_map.workspace.identity import IdentityStore
from lingbot_map.workspace.modal_engine import ModalLingbotEngine, ReconstructionCapacityExceeded
from lingbot_map.workspace.runner_contract import REMOTE_TIMEOUT

from .test_modal_engine import mock_transport
from .test_workspace_api import fake_mp4


@pytest.fixture
def capacity_engine(settings, service, monkeypatch):
    engine = ModalLingbotEngine(
        replace(
            settings,
            modal_enabled=True,
            research_acknowledgement=RESEARCH_ACKNOWLEDGEMENT,
            modal_gpu_seconds_budget=REMOTE_TIMEOUT,
        )
    )
    service.engines[engine.descriptor.id] = engine
    monkeypatch.setattr(
        modal.Volume, "from_name", lambda *a, **kw: pytest.fail("Unexpected provider access")
    )
    return engine


def upload(service, tenant):
    return service.upload_video(
        tenant_id=tenant,
        filename="capture.mp4",
        media_type="video/mp4",
        stream=io.BytesIO(fake_mp4()),
    )


@pytest.fixture
def capture(service, tenant_id, capacity_engine):
    return upload(service, tenant_id)


def submit(service, tenant, asset, **kwargs):
    return service.submit_research(tenant, asset_id=asset["id"], params={"maxFrames": 30}, **kwargs)


def claim(service):
    return service.database.claim_next_job(
        worker_id="capacity-worker", lease_seconds=30, max_attempts=3
    )


def scalar(service, query, parameters=()):
    with service.database.connect() as connection:
        return connection.execute(query, parameters).fetchone()[0]


def test_last_slot_admission_is_atomic_and_queued_cancellation_releases_it(
    service, tenant_id, capacity_engine, capture, authenticated_client
):
    barrier = Barrier(2)

    def admit(_):
        barrier.wait(timeout=5)
        try:
            return submit(service, tenant_id, capture)
        except ReconstructionCapacityExceeded:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted = [job for job in pool.map(admit, range(2)) if job]
    assert len(accepted) == 1
    assert scalar(service, "SELECT COUNT(*) FROM jobs") == 1
    assert capacity_engine.descriptor.available
    public = authenticated_client.get("/api/engines").json()["engines"]
    remote = next(engine for engine in public if engine["id"] == capacity_engine.descriptor.id)
    assert remote["available"] is False
    assert remote["unavailableReasons"] == [capacity_engine.capacity_unavailable_reason()]
    service.cancel_job(tenant_id, accepted[0]["id"])
    assert capacity_engine.capacity_unavailable_reason() is None
    assert submit(service, tenant_id, capture)["state"] == "queued"


def test_own_hold_becomes_a_charge_that_survives_cancel_delete_and_cleanup(
    service, tenant_id, capacity_engine, capture, monkeypatch
):
    job = submit(service, tenant_id, capture)
    attempt = claim(service)
    capacity_engine.reserve_run("charged-run", job["id"], time.time() + 30)
    assert scalar(service, "SELECT COUNT(*) FROM remote_runs") == 1
    service.cancel_job(tenant_id, job["id"])
    service.database.fail_job(
        tenant_id,
        job["id"],
        attempt_token=attempt["attempt_token"],
        worker_id=attempt["worker_id"],
        code="cancelled",
        message="Cancelled",
    )
    service.delete_job(tenant_id, job["id"])
    calls = mock_transport(monkeypatch)
    with service.database.transaction() as connection:
        connection.execute("UPDATE remote_runs SET cleanup_after=0")
    capacity_engine.cleanup_remote_runs()
    assert calls.removed == ["/charged-run"]
    assert scalar(service, "SELECT cleaned FROM remote_runs") == 1
    assert capacity_engine.capacity_unavailable_reason()


def test_recovered_job_requires_an_additional_remote_charge(
    service, tenant_id, capacity_engine, capture
):
    job = submit(service, tenant_id, capture)
    claim(service)
    capacity_engine.reserve_run("first-attempt", job["id"], time.time() + 30)
    with service.database.transaction() as connection:
        connection.execute("UPDATE jobs SET lease_expires_at=0 WHERE id=?", (job["id"],))
    assert service.database.recover_jobs(max_attempts=3)["requeued"] == 1
    claim(service)
    with pytest.raises(ReconstructionCapacityExceeded):
        capacity_engine.reserve_run("second-attempt", job["id"], time.time() + 30)
    capacity_engine.settings = replace(
        capacity_engine.settings, modal_gpu_seconds_budget=2 * REMOTE_TIMEOUT
    )
    capacity_engine.reserve_run("second-attempt", job["id"], time.time() + 30)
    assert scalar(service, "SELECT COUNT(*) FROM remote_runs") == 2


@pytest.mark.parametrize("age_days", [29, 31])
@pytest.mark.parametrize("cleaned", [False, True])
def test_rolling_budget_counts_charges_independently_of_cleanup(
    service, capacity_engine, age_days, cleaned
):
    capacity_engine.reserve_run("historical", "deleted-job", time.time() + 30)
    with service.database.transaction() as connection:
        connection.execute(
            "UPDATE remote_runs SET created_at=?,cleaned=?",
            (time.time() - age_days * 86400, cleaned),
        )
    assert bool(capacity_engine.capacity_unavailable_reason()) == (age_days < 30)


def test_full_capacity_rejects_before_multipart_but_preserves_hash_checked_upload_replay(
    service, capacity_engine, authenticated_client, monkeypatch
):
    files = {"file": ("capture.mp4", fake_mp4(), "video/mp4")}
    headers = {"Idempotency-Key": "capacity-upload-key"}
    first = authenticated_client.post("/api/assets", files=files, headers=headers)
    assert first.status_code == 201
    capacity_engine.reserve_run("occupied", "another-workspace", time.time() + 30)

    async def forbidden_parser(*args, **kwargs):
        pytest.fail("Capacity must be checked before parsing upload bytes")

    with monkeypatch.context() as patch:
        patch.setattr(Request, "form", forbidden_parser)
        blocked = authenticated_client.post("/api/assets", files=files)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == capacity_engine.capacity_unavailable_reason()
    replay = authenticated_client.post("/api/assets", files=files, headers=headers)
    assert replay.status_code == 201 and replay.json() == first.json()
    conflict = authenticated_client.post(
        "/api/assets", headers=headers, files={"file": ("capture.mp4", fake_mp4(128), "video/mp4")}
    )
    assert conflict.status_code == 409 and conflict.json()["code"] == "idempotency_conflict"
    assert scalar(service, "SELECT COUNT(*) FROM assets") == 1
    assert scalar(service, "SELECT COUNT(*) FROM object_claims") == 0
    assert len(list((service.settings.data_dir / "objects").rglob("*.mp4"))) == 1


def test_upload_rechecks_capacity_after_inspection(
    service, capacity_engine, authenticated_client, monkeypatch
):
    original = service.inspector.inspect

    def fill_capacity(path):
        metadata = original(path)
        capacity_engine.reserve_run("racing-charge", "another-workspace", time.time() + 30)
        return metadata

    monkeypatch.setattr(service.inspector, "inspect", fill_capacity)
    response = authenticated_client.post(
        "/api/assets",
        headers={"Idempotency-Key": "racing-upload-key"},
        files={"file": ("capture.mp4", fake_mp4(), "video/mp4")},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == capacity_engine.capacity_unavailable_reason()
    for table in ["assets", "object_claims", "idempotency_keys"]:
        assert scalar(service, f"SELECT COUNT(*) FROM {table}") == 0
    assert not list((service.settings.data_dir / "objects").rglob("*.mp4"))


def test_research_idempotency_replays_after_capacity_is_exhausted(
    capacity_engine, capture, authenticated_client
):
    payload = {"assetId": capture["id"], "maxFrames": 30}
    headers = {"Idempotency-Key": "capacity-research-key"}
    first = authenticated_client.post("/api/jobs/research", json=payload, headers=headers)
    assert first.status_code == 202 and capacity_engine.capacity_unavailable_reason()
    replay = authenticated_client.post("/api/jobs/research", json=payload, headers=headers)
    assert replay.status_code == 202 and replay.json() == first.json()
    conflict = authenticated_client.post(
        "/api/jobs/research", json={**payload, "maxFrames": 31}, headers=headers
    )
    assert conflict.status_code == 409 and conflict.json()["code"] == "idempotency_conflict"
    assert authenticated_client.post("/api/jobs/research", json=payload).status_code == 409


def test_modal_capacity_does_not_gate_samples_or_local_engines(service, tenant_id, capacity_engine):
    capacity_engine.reserve_run("occupied", "another-workspace", time.time() + 30)
    sample = service.submit_sample(tenant_id)
    assert service.process_next_job(engine_ids=("synthetic-sample-v1",))
    assert service.database.get_job(tenant_id, sample["id"])["state"] == "ready"
    local = LingbotResearchEngine(
        replace(
            capacity_engine.settings,
            modal_enabled=False,
            research_command="unused-test-runner",
            checkpoint_path=service.settings.data_dir / "unused",
            checkpoint_sha256="a" * 64,
        )
    )
    service.engines[local.descriptor.id] = local
    assert service.upload_unavailable_reason(tenant_id) is None
    assert submit(service, tenant_id, upload(service, tenant_id))["state"] == "queued"
    assert next(item for item in service.engine_descriptors() if item["id"] == local.descriptor.id)[
        "available"
    ]


@pytest.mark.parametrize("previously_charged", [False, True])
def test_worker_capacity_denial_preserves_personal_retries_only_without_a_prior_charge(
    service, capacity_engine, previously_charged
):
    tenant = IdentityStore(service.database).create_workspace(
        subject="capacity-user", name="Explorer", guest=False, max_accounts=10, quota=120
    )["tenant_id"]
    capacity_engine.reserve_run("occupied", "another-workspace", time.time() + 30)
    for index in range(3):
        capacity_engine.settings = replace(
            capacity_engine.settings, modal_gpu_seconds_budget=2 * REMOTE_TIMEOUT
        )
        job = submit(service, tenant, upload(service, tenant))
        with service.database.transaction() as connection:
            original = dict(
                connection.execute(
                    "SELECT * FROM usage_ledger WHERE job_id=?", (job["id"],)
                ).fetchone()
            )
            if previously_charged:
                connection.execute(
                    "INSERT INTO remote_runs(attempt_id,job_id,created_at,cleanup_after,cleaned) "
                    "VALUES (?,?,?,0,1)",
                    (f"old-{index}", job["id"], time.time() - 31 * 86400),
                )
        capacity_engine.settings = replace(
            capacity_engine.settings, modal_gpu_seconds_budget=REMOTE_TIMEOUT
        )
        assert service.process_next_job()
        failed = service.database.get_job(tenant, job["id"])
        assert failed["state"] == "failed" and failed["error_code"] == "preview_capacity"
        assert failed["error_message"] == capacity_engine.capacity_unavailable_reason()
        with service.database.connect() as connection:
            ledger = dict(
                connection.execute(
                    "SELECT * FROM usage_ledger WHERE id=?", (original["id"],)
                ).fetchone()
            )
        assert ledger == {
            **original,
            "event": "reserve" if previously_charged else "capacity_denied",
        }
        service.delete_job(tenant, job["id"])
    assert service.database.quota(tenant)["reserved_units"] == 0
    assert service.database.reconstruction_allowance(tenant)["state"] == (
        "retry_later" if previously_charged else "available"
    )
    assert scalar(
        service,
        "SELECT COUNT(*) FROM usage_ledger WHERE tenant_id=? AND event='capacity_denied'",
        (tenant,),
    ) == (0 if previously_charged else 3)


def test_stale_worker_cannot_exempt_a_retry(service, tenant_id, capture):
    job = submit(service, tenant_id, capture)
    attempt = claim(service)
    with pytest.raises(StaleAttempt):
        service.database.fail_job(
            tenant_id,
            job["id"],
            attempt_token="stale-attempt",
            worker_id=attempt["worker_id"],
            code="preview_capacity",
            message="Paused",
        )
    assert (
        scalar(service, "SELECT event FROM usage_ledger WHERE job_id=?", (job["id"],)) == "reserve"
    )
    assert service.database.get_job(tenant_id, job["id"])["state"] == "running"
