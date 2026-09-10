import asyncio
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from lingbot_map.workspace.config import RESEARCH_ACKNOWLEDGEMENT
from lingbot_map.workspace.database import QuotaExceeded
from lingbot_map.workspace.engines import (
    EngineContext,
    JobCancelled,
    cleanup_result,
    engine_registry,
)
from lingbot_map.workspace.modal_engine import MODEL_SHA256, ModalLingbotEngine
from lingbot_map.workspace.sample import build_synthetic_scene


@pytest.fixture
def remote_engine(settings, service):
    configured = replace(
        settings,
        modal_enabled=True,
        research_acknowledgement=RESEARCH_ACKNOWLEDGEMENT,
        modal_gpu_seconds_budget=600,
    )
    engine = ModalLingbotEngine(configured)
    source = configured.data_dir / "capture.mp4"
    source.write_bytes(b"test-only-video")
    work = configured.data_dir / "remote-test"
    work.mkdir()
    context = EngineContext(
        job_id="job_transport_test",
        tenant_id="tenant_test",
        params={"maxFrames": 30, "extractFps": 3},
        source_path=source,
        source_metadata={"durationSeconds": 10.0, "frames": 100},
        work_root=work,
    )
    return engine, context


def mock_transport(monkeypatch, *, stall=None, frames=30, missing_call=False, failed_removal=False):
    import modal

    calls = SimpleNamespace(cancelled=0, uploads=[], removed=[], submissions=[], polls=0)

    def asynchronous(function):
        return SimpleNamespace(aio=function)

    class Upload:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            if stall == "upload":
                await asyncio.Future()

        def put_file(self, source, destination):
            calls.uploads.append(destination)

    async def read_file(path):
        if stall == "download":
            await asyncio.Future()
        yield build_synthetic_scene().glb

    async def remove_file(path, recursive):
        if failed_removal:
            raise OSError("temporarily unavailable")
        calls.removed.append(path)

    async def get():
        calls.polls += 1
        if stall == "inference":
            await asyncio.Future()
        return {"checkpointSha256": MODEL_SHA256, "pointCount": 5908, "frames": frames}

    async def cancel(terminate_containers):
        calls.cancelled += 1
        if missing_call:
            raise modal.exception.NotFoundError("expired call")

    call = SimpleNamespace(object_id="fc_test", get=asynchronous(get), cancel=asynchronous(cancel))

    async def spawn(**kwargs):
        calls.submissions.append(kwargs)
        if stall == "spawn":
            await asyncio.Future()
        return call

    volume = SimpleNamespace(
        batch_upload=asynchronous(Upload),
        read_file=asynchronous(read_file),
        remove_file=asynchronous(remove_file),
    )
    monkeypatch.setattr(modal.Volume, "from_name", lambda *a, **kw: volume)
    monkeypatch.setattr(
        modal.Function, "from_name", lambda *a, **kw: SimpleNamespace(spawn=asynchronous(spawn))
    )
    monkeypatch.setattr(modal.FunctionCall, "from_id", lambda *a, **kw: call)
    return calls


def test_remote_transport_persists_call_budget_and_retrieves_artifact(remote_engine, monkeypatch):
    engine, context = remote_engine
    calls = mock_transport(monkeypatch)
    result = engine.run(context, lambda *a: None, lambda: False)
    try:
        assert result.used_units == 30
        assert result.artifacts[0].path.read_bytes()[:4] == b"glTF"
        assert calls.submissions[0]["max_frames"] == 30
        assert calls.submissions[0]["expires_at"] > 0
        assert len(calls.uploads) == 1
        with engine.database.connect() as connection:
            assert connection.execute("SELECT call_id FROM remote_runs").fetchone()[0] == "fc_test"
        with pytest.raises(QuotaExceeded):
            engine.run(context, lambda *a: None, lambda: False)
        engine.cleanup_remote_runs()
        assert len(calls.removed) == 1
    finally:
        cleanup_result(result)


def test_remote_cancel_is_forwarded_and_cleanup_survives_restart(remote_engine, monkeypatch):
    engine, context = remote_engine
    calls = mock_transport(monkeypatch, stall="inference")
    with pytest.raises(JobCancelled):
        engine.run(context, lambda *a: None, lambda: calls.polls > 0)
    assert calls.cancelled == 1
    assert not list(context.work_root.iterdir())
    with engine.database.transaction() as connection:
        assert (
            connection.execute("SELECT cleanup_after FROM remote_runs").fetchone()[0]
            > time.time() + 600
        )
        connection.execute("UPDATE remote_runs SET cleanup_after=0")
    restarted = ModalLingbotEngine(engine.settings)
    restarted.cleanup_remote_runs()
    assert len(calls.removed) == 1


@pytest.mark.parametrize("stage", ["upload", "spawn", "inference", "download"])
def test_stalled_remote_io_obeys_deadline(remote_engine, monkeypatch, stage):
    engine, context = remote_engine
    engine.settings = replace(engine.settings, job_timeout_seconds=0.15)
    calls = mock_transport(monkeypatch, stall=stage)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        engine.run(context, lambda *a: None, lambda: False)
    assert time.monotonic() - started < 2
    assert calls.cancelled == (1 if stage in {"inference", "download"} else 0)
    assert not list(context.work_root.iterdir())
    with engine.database.connect() as connection:
        row = connection.execute("SELECT * FROM remote_runs").fetchone()
        assert row["cleaned"] == 0
        assert row["cleanup_after"] > time.time() + 700


def test_stalled_upload_can_be_cancelled_without_a_call_id(remote_engine, monkeypatch):
    engine, context = remote_engine
    calls = mock_transport(monkeypatch, stall="upload")
    with pytest.raises(JobCancelled):
        engine.run(context, lambda *a: None, lambda: bool(calls.uploads))
    assert not calls.submissions
    assert not list(context.work_root.iterdir())


def test_expired_call_does_not_prevent_volume_cleanup(remote_engine, monkeypatch):
    engine, context = remote_engine
    calls = mock_transport(monkeypatch, missing_call=True)
    result = engine.run(context, lambda *a: None, lambda: False)
    cleanup_result(result)
    engine.cleanup_remote_runs()
    assert len(calls.removed) == 1


def test_cleanup_failure_yields_to_other_due_attempts(remote_engine, monkeypatch):
    engine, context = remote_engine
    mock_transport(monkeypatch, failed_removal=True)
    result = engine.run(context, lambda *a: None, lambda: False)
    cleanup_result(result)
    engine.cleanup_remote_runs()
    with engine.database.connect() as connection:
        row = connection.execute("SELECT * FROM remote_runs").fetchone()
        assert row["cleaned"] == 0
        assert row["cleanup_after"] > time.time() + 50


def test_low_fps_source_reserves_and_settles_actual_sample_count(remote_engine, monkeypatch):
    engine, context = remote_engine
    context = replace(context, source_metadata={"durationSeconds": 10.0, "frames": 10})
    assert engine.estimate_units(context.source_metadata, context.params) == 10
    mock_transport(monkeypatch, frames=10)
    result = engine.run(context, lambda *a: None, lambda: False)
    assert result.used_units == 10
    cleanup_result(result)


def test_registry_selects_modal_only_when_configured(settings):
    assert (
        type(engine_registry(settings)["lingbot-research-v1"]).__name__ == "LingbotResearchEngine"
    )
    selected = engine_registry(replace(settings, modal_enabled=True))["lingbot-research-v1"]
    assert isinstance(selected, ModalLingbotEngine)
    assert not selected.descriptor.available


def test_modal_rejects_incompatible_deadline_at_configuration(settings):
    with pytest.raises(ValueError, match="JOB_TIMEOUT_SECONDS <= 3600"):
        replace(settings, modal_enabled=True, job_timeout_seconds=7200).validate()


@pytest.mark.parametrize("params", [{"maxFrames": 121}, {"maskSky": True}, {"mode": "windowed"}])
def test_unsupported_modal_options_return_validation_error(
    authenticated_client, service, settings, params
):
    configured = replace(
        settings, modal_enabled=True, research_acknowledgement=RESEARCH_ACKNOWLEDGEMENT
    )
    service.engines["lingbot-research-v1"] = ModalLingbotEngine(configured)
    video = b"\x00\x00\x00\x18ftypmp42" + b"fixture" * 10
    uploaded = authenticated_client.post(
        "/api/assets", files={"file": ("capture.mp4", video, "video/mp4")}
    )
    assert uploaded.status_code == 201
    response = authenticated_client.post(
        "/api/jobs/research", json={"assetId": uploaded.json()["id"], **params}
    )
    assert response.status_code == 422
    assert response.json()["detail"]


def test_disabling_submission_keeps_durable_remote_cleanup(remote_engine, monkeypatch):
    from lingbot_map.workspace.service import WorkspaceService

    engine, context = remote_engine
    calls = mock_transport(monkeypatch)
    result = engine.run(context, lambda *a: None, lambda: False)
    cleanup_result(result)
    restarted = WorkspaceService(replace(engine.settings, modal_enabled=False))
    restarted.initialize()
    restarted.start_worker()
    try:
        deadline = time.monotonic() + 2
        while not calls.removed and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(calls.removed) == 1
    finally:
        restarted.stop_worker()
