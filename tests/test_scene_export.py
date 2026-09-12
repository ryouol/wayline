import json
import struct
from pathlib import Path

import cv2
import numpy as np
import pytest

from lingbot_map.workspace.capture import extract_capture
from lingbot_map.workspace.modal_engine import ModalLingbotEngine
from lingbot_map.workspace.scene_export import export_reconstruction
from lingbot_map.workspace.service import VideoInspector


def fixture_predictions():
    camera_to_world = np.tile(np.eye(4), (3, 1, 1))
    camera_to_world[:, 0, 3] = [0, 1, 2]
    return {
        "images": np.full((3, 3, 4, 4), 0.5),
        "depth": np.full((3, 4, 4, 1), 2.0),
        "depth_conf": np.ones((3, 4, 4)),
        "extrinsic": np.linalg.inv(camera_to_world)[:, :3],
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


@pytest.mark.parametrize("use_world_points", [False, True])
def test_moving_rotated_cameras_reconstruct_one_shared_world_landmark(tmp_path, use_world_points):
    predictions = fixture_predictions()
    landmark = np.array([1.0, 0.25, 4.0])
    depths = [2.0, 3.0, 4.0]
    camera_to_world = np.tile(np.eye(4), (3, 1, 1))
    for index, (yaw, pitch) in enumerate(
        [(0, 0), (np.pi / 4, np.pi / 6), (-np.pi / 6, -np.pi / 5)]
    ):
        cy, sy, cx, sx = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
        rotate_y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        rotate_x = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        rotation = rotate_y @ rotate_x
        camera_to_world[index, :3, :3] = rotation
        # Each physical camera sees the same landmark at its center pixel.
        camera_to_world[index, :3, 3] = landmark - rotation @ [0, 0, depths[index]]
        predictions["depth"][index] = depths[index]
    predictions["extrinsic"] = np.linalg.inv(camera_to_world)[:, :3]
    if use_world_points:
        predictions["world_points"] = np.broadcast_to(landmark, (3, 4, 4, 3)).copy()
        predictions["world_points_conf"] = np.ones((3, 4, 4))

    path = tmp_path / "shared-landmark.glb"
    report = export_reconstruction(predictions, [0.0, 1.0, 2.0], path)
    document, binary = parse_glb(path)
    points = np.frombuffer(binary, dtype="<f4", count=report["pointCount"] * 3).reshape(-1, 3)
    expected = landmark * [1, -1, -1]
    selected = points if use_world_points else points[[10, 26, 42]]
    np.testing.assert_allclose(selected, np.broadcast_to(expected, selected.shape), atol=1e-6)
    for frame, physical_camera in zip(
        document["extras"]["wayline"]["frames"], camera_to_world, strict=True
    ):
        np.testing.assert_allclose(
            frame["position"], physical_camera[:3, 3] * [1, -1, -1], atol=1e-6
        )
        np.testing.assert_allclose(frame["right"], physical_camera[:3, 0] * [1, -1, -1], atol=1e-6)
        np.testing.assert_allclose(frame["up"], physical_camera[:3, 1] * [-1, 1, 1], atol=1e-6)
        np.testing.assert_allclose(
            frame["forward"], physical_camera[:3, 2] * [1, -1, -1], atol=1e-6
        )


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


def test_fractional_frame_rate_does_not_underreserve(settings, tmp_path):
    source = tmp_path / "fractional.avi"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 60000 / 1001, (64, 48))
    assert writer.isOpened()
    for _ in range(1019):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()
    metadata = VideoInspector().inspect(source)
    engine = ModalLingbotEngine(settings)
    times = extract_capture(source, tmp_path / "frames")
    assert len(times) == 52
    assert engine.estimate_units(metadata, {}) == len(times)
    legacy = {**metadata, "durationSeconds": round(metadata["durationSeconds"], 3)}
    del legacy["samplingDurationSeconds"]
    assert engine.estimate_units(legacy, {}) >= len(times)


@pytest.mark.parametrize("origin", [-0.001667, 2.5])
def test_capture_normalizes_start_offset_and_preserves_variable_timing(
    tmp_path, monkeypatch, origin
):
    source = Path(__file__).parent / "fixtures" / "vfr-test-pattern.mp4"
    decoder = cv2.VideoCapture(str(source))

    class OffsetCapture:
        def __getattr__(self, name):
            return getattr(decoder, name)

        def get(self, key):
            value = decoder.get(key)
            return value + origin * 1000 if key == cv2.CAP_PROP_POS_MSEC else value

    monkeypatch.setattr(cv2, "VideoCapture", lambda path: OffsetCapture())
    timestamps = extract_capture(source, tmp_path / "frames", max_frames=10, sample_fps=15)
    assert timestamps == [0, 0.1, 0.2, 0.3, 0.4, 0.5, 1, 1.5, 2, 2.5]
    assert not decoder.isOpened()


@pytest.mark.parametrize("bad_time", [float("nan"), 0.0, -1.0])
def test_capture_still_rejects_invalid_timing(tmp_path, monkeypatch, bad_time):
    source = Path(__file__).parent / "fixtures" / "vfr-test-pattern.mp4"
    decoder = cv2.VideoCapture(str(source))

    class InvalidCapture:
        reads = 0

        def __getattr__(self, name):
            return getattr(decoder, name)

        def read(self):
            self.reads += 1
            return decoder.read()

        def get(self, key):
            if key == cv2.CAP_PROP_POS_MSEC and self.reads > 1:
                return bad_time
            return decoder.get(key)

    monkeypatch.setattr(cv2, "VideoCapture", lambda path: InvalidCapture())
    with pytest.raises(ValueError, match="presentation timestamps"):
        extract_capture(source, tmp_path / "frames", max_frames=10, sample_fps=15)
    assert not decoder.isOpened()
