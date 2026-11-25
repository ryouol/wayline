import hashlib
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "benchmark_wayline", Path(__file__).parents[1] / "scripts/benchmark_wayline.py"
)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_cost_per_success_includes_failed_attempts_and_unknown_is_not_zero():
    rows = [
        {"state": "ready", "estimatedCostUsd": 2, "billedCostUsd": None},
        {"state": "failed", "estimatedCostUsd": 1, "billedCostUsd": None},
    ]
    result = benchmark.summarize(rows)
    assert result["estimatedCostUsdPerSuccess"] == 3
    assert result["billedCostUsdPerSuccess"] is None
    assert result["failures"] == 1
    assert benchmark.summarize(rows[1:])["estimatedCostUsdPerSuccess"] is None


def test_manifest_refuses_changed_or_unlicensed_inputs_before_submission(tmp_path):
    source = tmp_path / "scene.mp4"
    source.write_bytes(b"fixed scene")
    scene = {
        "id": "scene-01",
        "path": "scene.mp4",
        "license": "owned",
        "providerProcessingAllowed": True,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    assert benchmark.validate_manifest({"scenes": [scene]}, tmp_path) == [scene]
    scene["providerProcessingAllowed"] = False
    with pytest.raises(ValueError, match="rights"):
        benchmark.validate_manifest({"scenes": [scene]}, tmp_path)
    scene["providerProcessingAllowed"] = True
    source.write_bytes(b"changed scene")
    with pytest.raises(ValueError, match="hash"):
        benchmark.validate_manifest({"scenes": [scene]}, tmp_path)
