import fcntl
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import time
from types import SimpleNamespace

import pytest

from lingbot_map.workspace import recovery
from lingbot_map.workspace.backup import create_snapshot, restore_snapshot

NOW = 1_800_000_000


class FakeVolume:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.files = {"/manual-20260910/keep.age": b"keep"}
        self.uploads = []
        self.removed = []
        self.fail_after_upload = False
        self.corrupt_read = False
        self.fail_remove = False
        self.fail_upload_number = None

    def upload(self, source, remote):
        state = recovery.load_state(self.data_dir)
        # Admission is durable before the provider sees any bytes.
        reservation = state["attempts"][-1]["reservations"][0 if remote.endswith(".age") else 1]
        assert reservation["bytes"] >= source.stat().st_size
        if remote.endswith(".age"):
            assert source.stat().st_size <= recovery.PART_BYTES
            assert len(list(source.parent.glob("part*.age"))) == 1
        self.uploads.append(remote)
        self.files[remote] = source.read_bytes()
        if self.fail_after_upload or len(self.uploads) == self.fail_upload_number:
            raise OSError("provider URL and private token must not reach status")

    def read(self, remote):
        value = self.files[remote]
        yield value[:-1] + b"!" if self.corrupt_read else value

    def remove(self, prefix):
        assert recovery.PREFIX.fullmatch(prefix)
        self.removed.append(prefix)
        if self.fail_remove:
            raise OSError("provider failure")
        self.files = {
            key: value for key, value in self.files.items() if not key.startswith(prefix + "/")
        }


@pytest.fixture
def setup(service, tenant_id, tmp_path):
    service.submit_sample(tenant_id)
    service.process_next_job()
    volume = FakeVolume(service.settings.data_dir)
    calls = []

    def fake_encrypt(snapshot, target, recipient, environment):
        calls.append(
            {
                "files": {str(p.relative_to(snapshot)) for p in snapshot.rglob("*") if p.is_file()},
                "environment": environment,
            }
        )
        target.write_bytes(b"x" * 1400)

    def run(at=NOW, **kwargs):
        return recovery.run_once(
            service.settings.data_dir,
            "age1test",
            "vo-test",
            staging_root=tmp_path,
            volume=volume,
            encrypt=fake_encrypt,
            now=at,
            **kwargs,
        )

    return SimpleNamespace(
        run=run, volume=volume, calls=calls, data_dir=service.settings.data_dir, staging=tmp_path
    )


def test_daily_admission_survives_restart_and_reservations_precede_upload(setup):
    assert setup.run()
    state = recovery.load_state(setup.data_dir)
    assert state["last_success"] == NOW
    assert len(setup.volume.uploads) == 2
    assert sum(item["bytes"] for item in state["attempts"][0]["reservations"]) > 1400
    assert not setup.run(NOW + recovery.DAY - 1)
    assert len(setup.volume.uploads) == 2
    assert setup.run(NOW + recovery.DAY)
    assert len(recovery.load_state(setup.data_dir)["attempts"]) == 2
    assert (setup.data_dir / recovery.STATE_NAME).stat().st_mode & 0o777 == 0o600
    assert not list(setup.staging.glob("wayline-recovery-*"))


def test_uncertain_upload_remains_charged_and_cleanup_runs_at_exhausted_allowance(setup):
    setup.volume.fail_after_upload = True
    assert not setup.run()
    first = recovery.load_state(setup.data_dir)["attempts"][0]
    charged = sum(item["bytes"] for item in first["reservations"])
    assert charged > 1400
    assert first["error"] == "backup_failed"
    assert len(setup.volume.uploads) == 1
    assert not setup.run(upload_budget_bytes=charged)
    setup.volume.fail_after_upload = False
    assert not setup.run(NOW + recovery.DAY, upload_budget_bytes=charged)
    assert len(setup.volume.uploads) == 1
    assert first["prefix"] in setup.volume.removed
    state = recovery.load_state(setup.data_dir)
    assert state["attempts"][-1]["error"] == "upload_allowance_exhausted"
    assert state["attempts"][0]["reservations"] == first["reservations"]
    assert setup.run(NOW + 31 * recovery.DAY)


def test_failed_readback_never_publishes_completion_or_prunes_good_set(setup):
    assert setup.run()
    good = set(setup.volume.files)
    setup.volume.corrupt_read = True
    assert not setup.run(NOW + recovery.DAY)
    assert good <= setup.volume.files.keys()
    last = recovery.load_state(setup.data_dir)["attempts"][-1]
    assert last["error"] == "remote_verification_failed"
    assert last["prefix"] + "/complete.json" not in setup.volume.files
    assert len(last["reservations"]) == 2


def test_retention_preserves_seven_verified_sets_and_other_prefixes(setup):
    for day in range(9):
        assert setup.run(NOW + day * recovery.DAY)
    completed = [key for key in setup.volume.files if key.endswith("/complete.json")]
    assert len(completed) == 7
    assert setup.volume.files["/manual-20260910/keep.age"] == b"keep"
    assert len(setup.volume.removed) == 2
    # Retention failure preserves the new verified set and records the failure.
    setup.volume.fail_remove = True
    assert not setup.run(NOW + 9 * recovery.DAY)
    state = recovery.load_state(setup.data_dir)
    assert state["last_success"] == NOW + 9 * recovery.DAY
    assert state["attempts"][-1]["status"] == "complete"
    assert state["attempts"][-1]["error"] == "backup_failed"


def test_snapshot_excludes_work_orphans_and_unrelated_environment(setup):
    (setup.data_dir / "work" / "not-a-backup.txt").write_text("partial capture")
    (setup.data_dir / "objects" / "uncommitted.bin").write_bytes(b"private orphan")
    assert setup.run(
        environment={
            "WAYLINE_GOOGLE_CLIENT_SECRET": "test-google-secret",
            "MODAL_TOKEN_SECRET": "test-modal-secret",
            "UNRELATED_PROJECT_TOKEN": "must-not-copy",
            "RENDER_API_KEY": "must-not-copy",
            "SSH_AUTH_SOCK": "must-not-copy",
        }
    )
    assert setup.calls[0]["environment"] == {
        "WAYLINE_GOOGLE_CLIENT_SECRET": "test-google-secret",
        "MODAL_TOKEN_SECRET": "test-modal-secret",
    }
    assert "objects/uncommitted.bin" not in setup.calls[0]["files"]
    assert all(not name.startswith("work/") for name in setup.calls[0]["files"])
    assert "test-google-secret" not in (setup.data_dir / recovery.STATE_NAME).read_text()


def test_low_staging_space_consumes_daily_attempt_without_upload(setup, monkeypatch):
    monkeypatch.setattr(recovery.shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    assert not setup.run()
    assert not setup.volume.uploads
    state = recovery.load_state(setup.data_dir)
    assert state["attempts"][-1]["error"] == "staging_space_low"
    assert not setup.run(NOW + 60)


def test_snapshot_byte_ceiling_cleans_partial_copy(service, tmp_path):
    target = tmp_path / "too-small"
    with pytest.raises(ValueError, match="byte ceiling"):
        create_snapshot(service.settings.data_dir, target, online=True, max_bytes=1)
    assert not target.exists()


def test_rejects_unowned_retention_path_before_provider_access(setup):
    state = {
        "format": 1,
        "last_attempt": 0,
        "last_success": 0,
        "attempts": [
            {
                "prefix": "/manual-20260910",
                "created_at": NOW - 40 * recovery.DAY,
                "status": "failed",
                "reservations": [],
            }
        ],
    }
    recovery.save_state(setup.data_dir, state)
    with pytest.raises(recovery.RecoveryFailure, match="invalid_state"):
        setup.run()
    assert not setup.volume.uploads and not setup.volume.removed


def test_real_age_archive_restores_and_environment_stays_encrypted(
    service, tenant_id, tmp_path, monkeypatch
):
    monkeypatch.setattr(recovery, "PART_BYTES", 64 * 1024)
    age, keygen = shutil.which("age"), shutil.which("age-keygen")
    if not age or not keygen:
        pytest.skip("Local age binaries are unavailable; CI installs them before this test")
    key = tmp_path / "test-age.key"
    result = subprocess.run([keygen, "-o", str(key)], capture_output=True, check=True)
    recipient = result.stderr.decode().split("Public key: ", 1)[1].strip()
    service.submit_sample(tenant_id)
    service.process_next_job()
    volume = FakeVolume(service.settings.data_dir)
    assert recovery.run_once(
        service.settings.data_dir,
        recipient,
        "vo-test",
        staging_root=tmp_path,
        now=NOW,
        volume=volume,
        environment={"LINGBOT_BOOTSTRAP_TOKEN": "private-test-token"},
    )
    marker_path = next(name for name in volume.files if name.endswith("complete.json"))
    marker = json.loads(volume.files[marker_path])
    assert len(marker["archive"]["parts"]) > 1
    chunks = []
    for part in marker["archive"]["parts"]:
        chunk = volume.files[marker_path.rsplit("/", 1)[0] + "/" + part["name"]]
        assert len(chunk) == part["bytes"] <= recovery.PART_BYTES
        assert hashlib.sha256(chunk).hexdigest() == part["sha256"]
        chunks.append(chunk)
    archive = b"".join(chunks)
    assert len(archive) == marker["archive"]["bytes"]
    assert hashlib.sha256(archive).hexdigest() == marker["archive"]["sha256"]
    assert b"private-test-token" not in archive and b"SQLite format" not in archive
    decrypted = subprocess.run(
        [age, "-d", "-i", str(key)], input=archive, capture_output=True, check=True
    ).stdout
    extracted = tmp_path / "extracted"
    with tarfile.open(fileobj=io.BytesIO(decrypted)) as content:
        content.extractall(extracted, filter="data")
    assert json.loads((extracted / "environment.json").read_text())["envVars"] == {
        "LINGBOT_BOOTSTRAP_TOKEN": "private-test-token"
    }
    assert restore_snapshot(extracted / "workspace", tmp_path / "restored")["files"] >= 4
    restored_state = recovery.load_state(tmp_path / "restored")
    assert restored_state["last_attempt"] == NOW
    assert len(restored_state["attempts"][-1]["reservations"]) == 2
    assert sum(item["bytes"] for item in restored_state["attempts"][-1]["reservations"]) >= len(
        archive
    )

    assert restored_state["attempts"][-1]["status"] == "retained"
    restored_prefix = restored_state["attempts"][-1]["prefix"]
    volume.data_dir = tmp_path / "restored"
    volume.fail_after_upload = True
    assert not recovery.run_once(
        volume.data_dir,
        recipient,
        "vo-test",
        staging_root=tmp_path,
        now=NOW + recovery.DAY,
        volume=volume,
        environment={},
    )
    assert restored_prefix not in volume.removed
    assert restored_prefix + "/complete.json" in volume.files


def test_failed_second_part_does_not_publish_completion_or_refund(setup, monkeypatch):
    monkeypatch.setattr(recovery, "PART_BYTES", 512)
    setup.volume.fail_upload_number = 2
    assert not setup.run()
    assert len(setup.volume.uploads) == 2
    assert setup.volume.uploads[0].endswith("/part-0000.age")
    assert setup.volume.uploads[1].endswith("/part-0001.age")
    assert not any(name.endswith("/complete.json") for name in setup.volume.files)
    state = recovery.load_state(setup.data_dir)
    assert sum(item["bytes"] for item in state["attempts"][-1]["reservations"]) > 1400
    assert not setup.run(NOW + 60)
    assert len(setup.volume.uploads) == 2
    assert not list(setup.staging.glob("wayline-recovery-*"))


def test_exhausted_allowance_avoids_snapshot_and_compacts_only_expired_pruned_rows(
    setup, monkeypatch
):
    old = NOW - 40 * recovery.DAY
    rows = [
        {
            "prefix": "/scheduled/1800000000-" + "a" * 32,
            "created_at": old,
            "status": "pruned",
            "reservations": [{"at": old, "bytes": 100}],
        },
        {
            "prefix": "/scheduled/1800000000-" + "b" * 32,
            "created_at": old,
            "status": "pruned",
            "reservations": [{"at": NOW - 1, "bytes": 100}],
        },
        {
            "prefix": "/scheduled/1800000000-" + "c" * 32,
            "created_at": old,
            "status": "complete",
            "reservations": [{"at": old, "bytes": 100}],
        },
    ]
    recovery.save_state(
        setup.data_dir,
        {
            "format": 1,
            "last_attempt": old,
            "last_success": old,
            "attempts": rows,
        },
    )

    def forbidden_snapshot(*args, **kwargs):
        pytest.fail("An exhausted allowance must be checked before snapshot copying")

    monkeypatch.setattr(recovery, "create_snapshot", forbidden_snapshot)
    assert not setup.run(upload_budget_bytes=1)
    state = recovery.load_state(setup.data_dir)
    assert {row["prefix"] for row in state["attempts"][:-1]} == {
        rows[1]["prefix"],
        rows[2]["prefix"],
    }
    assert state["attempts"][-1]["error"] == "upload_allowance_exhausted"
    assert not setup.volume.uploads and not setup.volume.removed


def test_supervisor_timeout_kills_child_without_rapid_retry(setup, monkeypatch):
    # The child writes durable admission, then simulates a stuck provider.
    original_popen = subprocess.Popen
    script = """import sys,time
from pathlib import Path
from lingbot_map.workspace.recovery import save_state
save_state(Path(sys.argv[1]), {'format':1,'last_attempt':time.time(),'last_success':0,
'attempts':[{'prefix':'/scheduled/1800000000-'+'a'*32,'created_at':time.time(),
'status':'running','reservations':[{'at':time.time(),'bytes':1400}]}]})
time.sleep(60)
"""

    def spawn(command, **kwargs):
        return original_popen([command[0], "-c", script, str(setup.data_dir)], **kwargs)

    monkeypatch.setattr(recovery.subprocess, "Popen", spawn)
    worker = recovery.RecoveryWorker(
        setup.data_dir, "age1test", "vo-test", staging_root=setup.staging, timeout_seconds=1
    )
    started = time.monotonic()
    worker._run_child()
    assert time.monotonic() - started < 5
    state = recovery.load_state(setup.data_dir)
    assert state["attempts"][0]["status"] == "failed"
    assert state["attempts"][0]["reservations"][0]["bytes"] == 1400
    assert time.time() - state["last_attempt"] < recovery.DAY


def test_restart_cleans_abandoned_staging_but_respects_active_invocation(setup):
    prefix = "/scheduled/1800000000-" + "b" * 32
    state = {
        "format": 1,
        "last_attempt": NOW,
        "last_success": 0,
        "attempts": [
            {
                "prefix": prefix,
                "created_at": NOW,
                "status": "running",
                "reservations": [{"at": NOW, "bytes": 1000}],
            }
        ],
    }
    recovery.save_state(setup.data_dir, state)
    temporary = setup.staging / ("wayline-recovery-" + prefix.rsplit("/", 1)[1])
    temporary.mkdir()
    (temporary / "partial-plaintext").write_text("private test data")
    worker = recovery.RecoveryWorker(
        setup.data_dir, "age1test", "vo-test", staging_root=setup.staging
    )
    with (setup.data_dir / ".recovery.lock").open("a+b") as locked:
        fcntl.flock(locked, fcntl.LOCK_EX)
        worker._recover_interrupted()
        assert temporary.exists()
        assert recovery.load_state(setup.data_dir)["attempts"][0]["status"] == "running"
    worker._recover_interrupted()
    assert not temporary.exists()
    repaired = recovery.load_state(setup.data_dir)
    assert repaired["attempts"][0]["status"] == "failed"
    assert repaired["attempts"][0]["reservations"] == [{"at": NOW, "bytes": 1000}]
    assert repaired["last_attempt"] == NOW


def test_full_size_part_manifests_do_not_accumulate_in_retained_ledger(setup, monkeypatch):
    parts = [
        {"name": f"part-{i:04d}.age", "bytes": recovery.PART_BYTES, "sha256": "a" * 64}
        for i in range(448)
    ]
    monkeypatch.setattr(
        recovery,
        "_upload_archive",
        lambda *args: {"bytes": 448 * recovery.PART_BYTES, "sha256": "b" * 64, "parts": parts},
    )
    for day in range(8):
        assert setup.run(NOW + day * recovery.DAY)
    state = recovery.load_state(setup.data_dir)
    complete = [item for item in state["attempts"] if item["status"] == "complete"]
    assert len(complete) == 7
    assert all(set(item["archive"]) == {"bytes", "sha256"} for item in complete)
    assert len(json.dumps(state).encode()) < 16 * 1024
    for item in complete:
        marker = json.loads(setup.volume.files[item["prefix"] + "/complete.json"])
        assert marker["archive"]["parts"] == parts


def test_enabled_service_stops_recovery_child_while_samples_remain_responsive(
    service, tenant_id, monkeypatch
):
    from dataclasses import replace

    original_popen = subprocess.Popen
    children = []
    script = """import fcntl,sys,time
from pathlib import Path
from lingbot_map.workspace.recovery import save_state
path=Path(sys.argv[1])
with (path/'.recovery.lock').open('a+b') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    save_state(path, {'format':1,'last_attempt':time.time(),'last_success':0,
      'attempts':[{'prefix':'/scheduled/1800000000-'+'a'*32,'created_at':time.time(),
       'status':'running','reservations':[{'at':time.time(),'bytes':1400}]}]})
    (path/'recovery-child-started').touch()
    time.sleep(60)
"""

    def spawn(command, **kwargs):
        child = original_popen([command[0], "-c", script, str(service.settings.data_dir)], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(recovery.subprocess, "Popen", spawn)
    service.settings = replace(
        service.settings, recovery_recipient="age1" + "a" * 58, recovery_volume_id="vo-test"
    )
    service.start_worker()
    try:
        deadline = time.monotonic() + 5
        while not (service.settings.data_dir / "recovery-child-started").exists():
            assert time.monotonic() < deadline
            time.sleep(0.01)
        job = service.submit_sample(tenant_id)
        while service.database.get_job(tenant_id, job["id"])["state"] != "ready":
            assert time.monotonic() < deadline
            time.sleep(0.01)
    finally:
        service.stop_worker()
    assert len(children) == 1 and children[0].poll() is not None
    state = recovery.load_state(service.settings.data_dir)
    assert state["attempts"][0]["status"] == "failed"
    assert state["attempts"][0]["reservations"][0]["bytes"] == 1400


def test_uncertain_restored_candidate_does_not_replace_a_verified_retention_slot(setup):
    for day in range(7):
        assert setup.run(NOW + day * recovery.DAY)
    state = recovery.load_state(setup.data_dir)
    state["attempts"].append(
        {
            "prefix": "/scheduled/1800000000-" + "f" * 32,
            "created_at": NOW + 7 * recovery.DAY,
            "status": "retained",
            "reservations": [],
        }
    )
    recovery.save_state(setup.data_dir, state)
    assert setup.run(NOW + 8 * recovery.DAY)
    verified = [
        i for i in recovery.load_state(setup.data_dir)["attempts"] if i["status"] == "complete"
    ]
    assert len(verified) == 7
    assert all(i["prefix"] + "/complete.json" in setup.volume.files for i in verified)


def test_expired_pruned_entries_compact_when_provider_cleanup_fails(setup):
    state = {"format": 1, "last_attempt": 0, "last_success": 0, "attempts": []}
    for status, suffix in [("pruned", "a"), ("failed", "b")]:
        state["attempts"].append(
            {
                "prefix": "/scheduled/1700000000-" + suffix * 32,
                "created_at": NOW - 40 * recovery.DAY,
                "status": status,
                "reservations": [{"at": NOW - 40 * recovery.DAY, "bytes": 1400}],
            }
        )
    recovery.save_state(setup.data_dir, state)
    setup.volume.fail_remove = True
    assert not setup.run()
    prefixes = [i["prefix"] for i in recovery.load_state(setup.data_dir)["attempts"]]
    assert state["attempts"][0]["prefix"] not in prefixes
    assert state["attempts"][1]["prefix"] in prefixes
    assert not setup.calls
