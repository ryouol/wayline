"""Abrupt process death across the real SQLite/object publication boundary."""

from __future__ import annotations

import hashlib
import multiprocessing
import signal
import socket
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import replace

import requests
import uvicorn

from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.engines import SyntheticSampleEngine
from lingbot_map.workspace.runtime_lock import workspace_lock
from lingbot_map.workspace.service import WorkspaceService

from .conftest import BOOTSTRAP_TOKEN


class MeasuredSampleEngine(SyntheticSampleEngine):
    """Real CC0 sample bytes with one local test unit to verify settlement."""

    def run(self, context, progress, cancelled):
        return replace(super().run(context, progress, cancelled), used_units=1)


def _service(settings):
    return WorkspaceService(settings, engines={"synthetic-sample-v1": MeasuredSampleEngine()})


def _serve(settings, listener, committed):
    # Use the same exclusive runtime ownership and lifespan as the normal CLI.
    with workspace_lock(settings.data_dir):
        service = _service(settings)
        if committed is not None:
            create_artifact = service.database.create_artifact

            def pause_after_commit(**values):
                artifact = create_artifact(**values)
                # The original method has committed and closed its connection.
                # SIGKILL here must bypass job settlement and all worker finally blocks.
                committed.send(artifact)
                threading.Event().wait(30)
                raise TimeoutError("Parent did not kill the paused test worker")

            service.database.create_artifact = pause_after_commit
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(settings, service=service),
                log_level="critical",
                access_log=False,
                timeout_graceful_shutdown=1,
            )
        )
        server.run(sockets=[listener])


@contextmanager
def _running_app(settings, committed=None):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        base = f"http://127.0.0.1:{listener.getsockname()[1]}"
        process = multiprocessing.get_context("spawn").Process(
            target=_serve, args=(settings, listener, committed)
        )
        process.start()
        try:
            with requests.Session() as client:
                client.trust_env = False
                client.headers["Authorization"] = f"Bearer {BOOTSTRAP_TOKEN}"
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    assert process.is_alive(), f"Server exited with {process.exitcode}"
                    try:
                        if client.get(f"{base}/healthz", timeout=0.25).status_code == 200:
                            break
                    except requests.RequestException:
                        pass
                    time.sleep(0.02)
                else:
                    raise AssertionError("Local process did not become healthy")
                yield process, client, base
        finally:
            if process.is_alive():
                process.terminate()
            process.join(3)
            if process.is_alive():
                process.kill()
                process.join(3)
            assert not process.is_alive(), "Test process survived cleanup"
            process.close()


def _rows(settings, query, parameters=()):
    path = settings.data_dir / "workspace.sqlite3"
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        return connection.execute(query, parameters).fetchall()
    finally:
        connection.close()


def test_sigkill_during_publication_recovers_without_exposing_or_double_charging(settings):
    settings = replace(settings, job_timeout_seconds=3, shutdown_timeout_seconds=1)
    # Seed an unrelated completed scene before the disposable runtime starts.
    with workspace_lock(settings.data_dir):
        service = _service(settings)
        service.initialize()
        tenant_id = service.database.authenticate_api_token(BOOTSTRAP_TOKEN)["tenant_id"]
        original = service.submit_sample(tenant_id)
        assert service.process_next_job()
    observed, committed = multiprocessing.get_context("spawn").Pipe(duplex=False)
    key = {"Idempotency-Key": "process-crash-submission-0001"}
    try:
        with _running_app(settings, committed) as (process, client, base):
            original_detail = client.get(f"{base}/api/jobs/{original['id']}", timeout=3).json()
            assert original_detail["state"] == "ready"
            original_scene = next(a for a in original_detail["artifacts"] if a["kind"] == "scene")
            download = client.get(base + original_scene["downloadUrl"], timeout=3)
            assert download.status_code == 200
            original_bytes = download.content
            assert hashlib.sha256(original_bytes).hexdigest() == original_scene["sha256"]

            submitted = client.post(f"{base}/api/jobs/sample", headers=key, timeout=3)
            assert submitted.status_code == 202
            job_id = submitted.json()["id"]
            assert observed.poll(10), "Worker never committed its first artifact"
            partial = observed.recv()
            assert partial["job_id"] == job_id
            old_path = service.store.path_for_local_use(partial["object_key"])
            assert old_path.is_file()
            assert _rows(settings, "SELECT id FROM artifacts WHERE id=?", (partial["id"],))
            lease = _rows(settings, "SELECT lease_expires_at FROM jobs WHERE id=?", (job_id,))[0][0]

            pending = client.get(f"{base}/api/jobs/{job_id}", timeout=3).json()
            assert pending["state"] == "running"
            assert pending["artifacts"] == []
            for route in ("content", "download"):
                response = client.get(f"{base}/api/artifacts/{partial['id']}/{route}", timeout=3)
                assert response.status_code == 404
            assert (
                client.post(
                    f"{base}/api/artifacts/{partial['id']}/shares",
                    json={"ttlSeconds": 300},
                    timeout=3,
                ).status_code
                == 404
            )

            process.kill()
            process.join(3)
            assert process.exitcode == -signal.SIGKILL
            # These survive the kill: neither cooperative shutdown nor cleanup ran.
            assert old_path.is_file()
            assert _rows(settings, "SELECT id FROM artifacts WHERE id=?", (partial["id"],))
            assert _rows(settings, "SELECT state FROM jobs WHERE id=?", (job_id,)) == [("running",)]
            assert _rows(
                settings, "SELECT event,units FROM usage_ledger WHERE job_id=?", (job_id,)
            ) == [("reserve", 1)]

        # Let the configured lease expire normally; never rewrite persisted time.
        time.sleep(max(0, lease - time.time()) + 0.02)
        with _running_app(settings) as (_, client, base):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                completed = client.get(f"{base}/api/jobs/{job_id}", timeout=1).json()
                if completed["state"] in {"ready", "failed", "cancelled"}:
                    break
                time.sleep(0.02)
            assert completed["state"] == "ready"
            assert completed["attempt"] == 2
            assert sorted(a["kind"] for a in completed["artifacts"]) == ["manifest", "scene"]
            scene = next(a for a in completed["artifacts"] if a["kind"] == "scene")
            download = client.get(base + scene["downloadUrl"], timeout=3)
            assert download.status_code == 200
            assert download.content == original_bytes
            assert partial["id"] not in {a["id"] for a in completed["artifacts"]}
            assert not old_path.exists()
            assert (
                client.get(f"{base}/api/artifacts/{partial['id']}/content", timeout=3).status_code
                == 404
            )
            assert _rows(settings, "SELECT COUNT(*) FROM object_claims") == [(0,)]
            assert _rows(settings, "SELECT COUNT(*) FROM deletion_outbox") == [(0,)]
            assert _rows(settings, "SELECT COUNT(*) FROM remote_runs") == [(0,)]
            assert _rows(
                settings,
                "SELECT event,units FROM usage_ledger WHERE job_id=? ORDER BY event",
                (job_id,),
            ) == [("consume", 1), ("release", -1), ("reserve", 1)]
            assert _rows(
                settings,
                "SELECT reserved_units,consumed_units FROM tenants WHERE id=?",
                (tenant_id,),
            ) == [(0, 2)]
            assert _rows(settings, "PRAGMA integrity_check") == [("ok",)]

            replay = client.post(f"{base}/api/jobs/sample", headers=key, timeout=3)
            assert replay.status_code == 202
            assert replay.json()["id"] == job_id
            assert _rows(settings, "SELECT COUNT(*) FROM jobs") == [(2,)]
            assert _rows(settings, "SELECT COUNT(*) FROM artifacts") == [(4,)]
            preserved = client.get(f"{base}/api/jobs/{original['id']}", timeout=3).json()
            assert preserved == original_detail
            download = client.get(base + original_scene["downloadUrl"], timeout=3)
            assert download.status_code == 200
            assert download.content == original_bytes
    finally:
        observed.close()
        committed.close()
