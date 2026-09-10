import json
import struct
from pathlib import Path

import cv2
import numpy as np
import pytest

from lingbot_map.workspace.capture import extract_capture
from lingbot_map.workspace.scene_export import export_reconstruction


def fixture_predictions():
    poses = np.tile(np.eye(4)[:3], (3, 1, 1))
    poses[:, 0, 3] = [0, 1, 2]
    return {
        "images": np.full((3, 3, 4, 4), 0.5),
        "depth": np.full((3, 4, 4, 1), 2.0),
        "depth_conf": np.ones((3, 4, 4)),
        "extrinsic": poses,
        "intrinsic": np.tile(np.array([[2.0, 0, 2], [0, 2, 2], [0, 0, 1]]), (3, 1, 1)),
    }


def parse_glb(path):
    payload = path.read_bytes()
    assert struct.unpack("<III", payload[:12]) == (0x46546C67, 2, len(payload))
    length, kind = struct.unpack("<II", payload[12:20])
    assert kind == 0x4E4F534A
    return json.loads(payload[20 : 20 + length]), payload[28 + length :]


def test_depth_points_and_camera_trace_share_a_coordinate_system(tmp_path):
    path = tmp_path / "scene.glb"
    report = export_reconstruction(fixture_predictions(), [0.0, 1.0, 2.0], path)
    document, binary = parse_glb(path)
    points = np.frombuffer(binary, dtype="<f4", count=report["pointCount"] * 3).reshape(-1, 3)
    frames = document["extras"]["wayline"]["frames"]
    assert report["pointCount"] == 48
    assert [frame["pointEnd"] for frame in frames] == [16, 32, 48]
    assert [frame["position"] for frame in frames] == [[0, 0, 0], [1, 0, 0], [2, 0, 0]]
    assert frames[0]["forward"] == [0, 0, -1]
    assert frames[0]["imageSize"] == [4, 4]
    assert frames[0]["intrinsics"] == [2, 2, 2, 2]
    # Center pixel, depth 2, camera translated one unit on X.
    assert points[16 + 10].tolist() == [1, 0, -2]
    assert frames[-1]["time"] == 2.0
    assert frames[-1]["thumbnail"].startswith("data:image/jpeg;base64,")
    color_accessor = document["accessors"][1]
    assert color_accessor["type"] == "VEC4"
    color_view = document["bufferViews"][color_accessor["bufferView"]]
    assert color_view["byteOffset"] % 4 == 0
    colors = np.frombuffer(binary[color_view["byteOffset"] :], dtype=np.uint8).reshape(-1, 4)
    assert len(colors) == report["pointCount"]
    assert np.all(colors[:, 3] == 255)


def test_export_bounds_points_and_rejects_bad_poses(tmp_path):
    path = tmp_path / "scene.glb"
    predictions = fixture_predictions()
    assert (
        export_reconstruction(predictions, [0.0, 1.0, 2.0], path, max_points=9)["pointCount"] == 9
    )
    predictions["extrinsic"][0, 0, 0] = 5
    with pytest.raises(ValueError, match="rigid"):
        export_reconstruction(predictions, [0.0, 1.0, 2.0], path)
    with pytest.raises(ValueError, match="timestamps"):
        export_reconstruction(fixture_predictions(), [0.0, 1.0], path)
    with pytest.raises(ValueError, match="increasing"):
        export_reconstruction(fixture_predictions(), [0.0, 0.0, 1.0], path)


def test_capture_sampling_keeps_first_and_last_frames(tmp_path):
    path = tmp_path / "test.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    assert writer.isOpened()
    for index in range(20):
        writer.write(np.full((48, 64, 3), index * 10, dtype=np.uint8))
    writer.release()
    times = extract_capture(path, tmp_path / "frames", max_frames=4, sample_fps=3)
    assert times == [0.0, 0.6, 1.2, 1.9]
    assert len(list((tmp_path / "frames").glob("*.jpg"))) == 4
    assert cv2.imread(str(tmp_path / "frames/000003.jpg")).mean() > 180


def test_capture_uses_presentation_timestamps_for_variable_frame_rate(tmp_path):
    source = Path(__file__).parent / "fixtures" / "vfr-test-pattern.mp4"
    timestamps = extract_capture(source, tmp_path / "frames", max_frames=10, sample_fps=15)
    assert timestamps == [0, 0.1, 0.2, 0.3, 0.4, 0.5, 1, 1.5, 2, 2.5]
    assert len(list((tmp_path / "frames").glob("*.jpg"))) == 10
