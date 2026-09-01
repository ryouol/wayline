from __future__ import annotations

import ast
import hashlib
import io
import json
import stat
import struct
from pathlib import Path

import pytest

from lingbot_map.checkpoints import (
    CheckpointRejected,
    expected_digest,
    materialize_verified_checkpoint,
    verify_checkpoint,
)
from lingbot_map.workspace.config import Settings
from lingbot_map.workspace.sample import build_synthetic_scene
from lingbot_map.workspace.storage import LocalObjectStore, ObjectTooLarge, validate_object_key


def test_synthetic_sample_is_valid_glb_with_provenance():
    scene = build_synthetic_scene()
    magic, version, length = struct.unpack_from("<III", scene.glb)
    assert magic == 0x46546C67
    assert version == 2
    assert length == len(scene.glb)
    json_length, json_type = struct.unpack_from("<II", scene.glb, 12)
    assert json_type == 0x4E4F534A
    document = json.loads(scene.glb[20 : 20 + json_length])
    assert document["extras"]["license"] == "CC0-1.0"
    assert (
        document["extras"]["source"]
        == "deterministically generated; no source imagery and no model inference"
    )
    assert scene.point_count > 4_000


def test_object_store_rejects_traversal_and_enforces_limit(tmp_path):
    store = LocalObjectStore(tmp_path / "objects")
    for key in ("../escape", "/absolute", "a/../../escape", "a\\b"):
        with pytest.raises(ValueError):
            validate_object_key(key)
    with pytest.raises(ObjectTooLarge):
        store.put_stream("tenant/large.bin", io.BytesIO(b"12345"), max_bytes=4)
    assert not (tmp_path / "objects" / "tenant" / "large.bin").exists()


def test_workspace_runtime_files_are_private(settings):
    from lingbot_map.workspace.service import WorkspaceService

    settings.data_dir.mkdir(parents=True, mode=0o755)
    settings.data_dir.chmod(0o755)
    service = WorkspaceService(settings)
    service.initialize()
    service.write_runtime_manifest()

    assert stat.S_IMODE(settings.data_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(service.store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(service.work_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(service.database.path.stat().st_mode) == 0o600
    assert stat.S_IMODE((settings.data_dir / "runtime-manifest.json").stat().st_mode) == 0o600
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{service.database.path}{suffix}")
        if sidecar.exists():
            assert stat.S_IMODE(sidecar.stat().st_mode) == 0o600


def test_checkpoint_requires_exact_digest_and_safe_file(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"tensor-weights")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    record = verify_checkpoint(checkpoint, digest, 1024)
    assert record["sha256"] == digest

    sidecar = tmp_path / "model.pt.sha256"
    sidecar.write_text(f"{digest}  model.pt\n", encoding="utf-8")
    assert expected_digest(checkpoint) == digest
    sidecar.chmod(0o620)
    with pytest.raises(CheckpointRejected, match="group- or world-writable"):
        expected_digest(checkpoint)
    sidecar.chmod(0o600)
    with pytest.raises(CheckpointRejected, match="does not match"):
        verify_checkpoint(checkpoint, "0" * 64, 1024)

    checkpoint.chmod(0o606)
    with pytest.raises(CheckpointRejected, match="world-writable"):
        verify_checkpoint(checkpoint, digest, 1024)
    checkpoint.chmod(0o600)
    link = tmp_path / "linked.pt"
    link.symlink_to(checkpoint)
    with pytest.raises(CheckpointRejected, match="non-symlink"):
        verify_checkpoint(link, digest, 1024)

    checkpoint.chmod(0o620)
    with pytest.raises(CheckpointRejected, match="group- or world-writable"):
        verify_checkpoint(checkpoint, digest, 1024)


def test_checkpoint_is_materialized_to_private_immutable_copy(tmp_path):
    checkpoint = tmp_path / "operator-model.pt"
    checkpoint.write_bytes(b"pinned model bytes")
    checkpoint.chmod(0o600)
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    record = materialize_verified_checkpoint(checkpoint, digest, 1024, tmp_path / "private-cache")
    private = Path(record["path"])
    assert private != checkpoint
    assert private.read_bytes() == b"pinned model bytes"
    assert stat.S_IMODE(private.stat().st_mode) == 0o400

    checkpoint.chmod(0o600)
    checkpoint.write_bytes(b"operator path changed later")
    assert private.read_bytes() == b"pinned model bytes"

    redirected = tmp_path / "redirected-cache"
    redirected.mkdir()
    cache_link = tmp_path / "cache-link"
    cache_link.symlink_to(redirected, target_is_directory=True)
    with pytest.raises(CheckpointRejected, match="non-symlink directory"):
        materialize_verified_checkpoint(checkpoint, digest, 1024, cache_link)


def test_production_settings_require_long_secure_token(tmp_path):
    with pytest.raises(ValueError, match="32 characters"):
        Settings(
            data_dir=tmp_path,
            environment="production",
            bootstrap_token="too-short-token",
            cookie_secure=True,
        ).validate()
    with pytest.raises(ValueError, match="secure"):
        Settings(
            data_dir=tmp_path,
            environment="production",
            bootstrap_token="x" * 32,
            cookie_secure=False,
        ).validate()
    with pytest.raises(ValueError, match="ALLOWED_HOSTS"):
        Settings(
            data_dir=tmp_path,
            environment="production",
            bootstrap_token="x" * 32,
            cookie_secure=True,
        ).validate()
    with pytest.raises(ValueError, match="HTTPS origin"):
        Settings(
            data_dir=tmp_path,
            environment="production",
            bootstrap_token="x" * 32,
            cookie_secure=True,
            public_base_url="https://user:pass@scenes.example.com/path",
            allowed_hosts=("scenes.example.com",),
        ).validate()


def test_runtime_settings_reject_unsafe_ranges(settings):
    from dataclasses import replace

    for field, value, message in (
        ("max_video_frames", 0, "MAX_VIDEO_FRAMES"),
        ("worker_poll_seconds", 0, "WORKER_POLL_SECONDS"),
        ("worker_poll_seconds", float("nan"), "WORKER_POLL_SECONDS"),
        ("readiness_probe_ttl_seconds", float("nan"), "READINESS_PROBE_TTL_SECONDS"),
        ("storage_min_free_bytes", -1, "MIN_FREE_BYTES"),
        ("max_job_attempts", 11, "must not exceed 10"),
        ("global_max_inflight_objects", 0, "GLOBAL_MAX_INFLIGHT_OBJECTS"),
    ):
        with pytest.raises(ValueError, match=message):
            replace(settings, **{field: value}).validate()
    with pytest.raises(ValueError, match="tenant in-flight"):
        replace(
            settings,
            global_max_inflight_objects=1,
            tenant_max_inflight_objects=2,
        ).validate()


def test_research_engine_stays_closed_without_all_gates(settings):
    from lingbot_map.workspace.engines import EngineUnavailable, LingbotResearchEngine

    descriptor = LingbotResearchEngine(settings).descriptor
    assert descriptor.research_only is True
    assert descriptor.commercially_cleared is False
    assert descriptor.available is False
    assert "research-only acknowledgement is missing" in descriptor.unavailable_reasons
    with pytest.raises(EngineUnavailable, match="sky masking requires"):
        LingbotResearchEngine(settings).estimate_units(
            {"frames": 30}, {"maxFrames": 30, "maskSky": True}
        )


def test_research_adapter_persists_only_sanitized_provenance(settings, tmp_path, monkeypatch):
    import shlex
    import sys
    from dataclasses import replace

    from lingbot_map.workspace.config import RESEARCH_ACKNOWLEDGEMENT
    from lingbot_map.workspace.engines import (
        EngineContext,
        LingbotResearchEngine,
        cleanup_result,
    )

    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"verified test weights")
    checkpoint_digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    scene_template = tmp_path / "template.glb"
    scene_template.write_bytes(build_synthetic_scene().glb)
    runner = tmp_path / "runner.py"
    runner.write_text(
        f"""\
import json
import os
from pathlib import Path

output = Path(os.environ["LINGBOT_OUTPUT_DIR"])
(output / "scene.glb").write_bytes(Path({str(scene_template)!r}).read_bytes())
(output / "report.json").write_text(json.dumps({{
    "frames": 30,
    "inferenceSeconds": 1.25,
    "internalPath": "/secret/runner/path",
    "warnings": ["secret leaked"] if os.environ.get("LINGBOT_BOOTSTRAP_TOKEN") else [],
}}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    monkeypatch.setenv("LINGBOT_BOOTSTRAP_TOKEN", "must-not-reach-runner")
    gated = replace(
        settings,
        research_acknowledgement=RESEARCH_ACKNOWLEDGEMENT,
        research_command=shlex.join([sys.executable, str(runner)]),
        checkpoint_path=checkpoint,
        checkpoint_sha256=checkpoint_digest,
    )
    result = LingbotResearchEngine(gated).run(
        EngineContext(
            job_id="job_" + "a" * 32,
            tenant_id="ten_" + "b" * 32,
            params={"maxFrames": 30, "maskSky": False},
            source_path=source,
            source_metadata={"frames": 30},
            work_root=tmp_path,
        ),
        lambda _stage, _progress: None,
        lambda: False,
    )
    try:
        manifest = next(item for item in result.artifacts if item.kind == "manifest")
        assert manifest.payload
        public = json.loads(manifest.payload)
        assert "tenantId" not in public
        assert "sourcePath" not in public
        assert "path" not in public["checkpoint"]
        assert result.report == {"frames": 30, "inferenceSeconds": 1.25, "warnings": []}
    finally:
        cleanup_result(result)


def test_modal_research_runner_keeps_sky_masking_opt_in():
    source = (Path(__file__).parents[1] / "modal_app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    reconstruct = next(
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "reconstruct"
    )
    keyword_defaults = dict(
        zip(
            (argument.arg for argument in reconstruct.args.kwonlyargs),
            reconstruct.args.kw_defaults,
            strict=True,
        )
    )
    mask_sky = keyword_defaults["mask_sky"]
    assert isinstance(mask_sky, ast.Constant)
    assert mask_sky.value is False
    assert "requirements/modal.lock" in source
    assert "--require-hashes" in source


def test_modal_reference_imports_without_credentials_and_remains_disabled():
    import modal

    import modal_app

    assert modal.__version__ == "1.5.5"
    assert modal_app.MODAL_REFERENCE_ENABLED is False
    with pytest.raises(RuntimeError, match="disabled pending"):
        modal_app._acknowledge(modal_app.RESEARCH_ACK)


def test_every_direct_torch_loader_uses_a_private_verified_path():
    root = Path(__file__).parents[1]
    candidates = [
        root / "demo.py",
        root / "demo_render" / "demo.py",
        root / "benchmark" / "methods" / "lingbot_map.py",
        root / "lingbot_map" / "aggregator" / "base.py",
    ]
    for candidate in candidates:
        module = ast.parse(candidate.read_text(encoding="utf-8"))
        loads = [
            node
            for node in ast.walk(module)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "torch"
            and node.func.attr == "load"
        ]
        assert loads, candidate
        assert all(
            call.args and isinstance(call.args[0], ast.Name) and call.args[0].id == "load_path"
            for call in loads
        ), candidate


def test_every_direct_onnx_loader_uses_a_private_verified_path():
    root = Path(__file__).parents[1]
    candidates = [
        root / "lingbot_map" / "vis" / "sky_segmentation.py",
        root / "demo_render" / "rgbd_render" / "data" / "sky.py",
        root / "benchmark" / "sky_seg" / "seg_sky.py",
        root / "benchmark" / "benchmark" / "utils" / "sky_segmentation.py",
    ]
    for candidate in candidates:
        module = ast.parse(candidate.read_text(encoding="utf-8"))
        loads = [
            node
            for node in ast.walk(module)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "InferenceSession"
        ]
        assert loads, candidate
        for node in loads:
            first_arg = node.args[0]
            assert isinstance(first_arg, ast.Call), candidate
            assert isinstance(first_arg.func, ast.Name) and first_arg.func.id == "str", candidate
            assert isinstance(first_arg.args[0], ast.Name), candidate
            assert first_arg.args[0].id == "load_path", candidate
