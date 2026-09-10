"""Bounded GLB export with source-frame and camera trace from LingBot predictions.

The input extrinsics are camera-to-world, as returned by demo.postprocess.
All points and poses receive the same OpenCV-to-glTF basis change.
"""

from __future__ import annotations

import base64
import json
import math
import struct
from pathlib import Path
from typing import Any

import cv2
import numpy as np

BASIS = np.diag([1.0, -1.0, -1.0])
MAX_POINTS = 750_000
MAX_FRAMES = 120


def encode_point_glb(points: np.ndarray, colors: np.ndarray, trace: dict[str, Any]) -> bytes:
    points = np.asarray(points, dtype="<f4")
    colors = np.asarray(colors, dtype=np.uint8)
    if points.ndim != 2 or points.shape[1] != 3 or colors.shape != points.shape:
        raise ValueError("Expected matching Nx3 points and colors")
    if not 1 <= len(points) <= MAX_POINTS or not np.isfinite(points).all():
        raise ValueError("The scene has no usable points or exceeds the point limit")
    positions = points.tobytes()
    # glTF vertex attributes require a four-byte aligned stride, including uint8 colors.
    color_bytes = np.column_stack((colors, np.full(len(colors), 255, dtype=np.uint8))).tobytes()
    binary = positions + color_bytes
    document = {
        "asset": {"version": "2.0", "generator": "Wayline / LingBot-Map"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "COLOR_0": 1}, "mode": 0}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(positions), "target": 34962},
            {
                "buffer": 0,
                "byteOffset": len(positions),
                "byteLength": len(color_bytes),
                "target": 34962,
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(points),
                "type": "VEC3",
                "min": points.min(axis=0).tolist(),
                "max": points.max(axis=0).tolist(),
            },
            {
                "bufferView": 1,
                "componentType": 5121,
                "count": len(points),
                "type": "VEC4",
                "normalized": True,
            },
        ],
        "extras": {"wayline": trace, "license": "NOASSERTION", "model": "LingBot-Map"},
    }
    metadata = json.dumps(document, separators=(",", ":"), allow_nan=False).encode()
    metadata += b" " * (-len(metadata) % 4)
    length = 12 + 8 + len(metadata) + 8 + len(binary)
    return (
        struct.pack("<III", 0x46546C67, 2, length)
        + struct.pack("<II", len(metadata), 0x4E4F534A)
        + metadata
        + struct.pack("<II", len(binary), 0x004E4942)
        + binary
    )


def export_reconstruction(
    predictions: dict[str, Any],
    timestamps: list[float],
    output: Path,
    *,
    max_points: int = MAX_POINTS,
) -> dict[str, Any]:
    images = np.asarray(predictions["images"])
    if images.ndim != 4 or images.shape[1] != 3:
        raise ValueError("Expected Sx3xHxW model images")
    frames, _, height, width = images.shape
    if not 2 <= frames <= MAX_FRAMES or len(timestamps) != frames:
        raise ValueError("Frame count and timestamps do not match")
    if not all(math.isfinite(t) and t >= 0 for t in timestamps) or any(
        a >= b for a, b in zip(timestamps, timestamps[1:], strict=False)
    ):
        raise ValueError("Timestamps must be finite and strictly increasing")
    if not frames <= max_points <= MAX_POINTS:
        raise ValueError("Invalid point budget")
    poses = np.asarray(predictions["extrinsic"], dtype=np.float64)
    intrinsics = np.asarray(predictions["intrinsic"], dtype=np.float64)
    if poses.shape != (frames, 3, 4) or intrinsics.shape != (frames, 3, 3):
        raise ValueError("Camera matrices do not match the source frames")
    if not np.isfinite(poses).all() or not np.isfinite(intrinsics).all():
        raise ValueError("Non-finite camera matrix")
    if not np.isfinite(images).all():
        raise ValueError("Non-finite source image")
    world = predictions.get("world_points")
    if world is not None:
        world = np.asarray(world)
        if world.shape != (frames, height, width, 3):
            raise ValueError("Point map does not match source images")
    depth = np.asarray(predictions.get("depth", []))
    if world is None and depth.shape not in ((frames, height, width), (frames, height, width, 1)):
        raise ValueError("Missing or invalid depth map")
    confidence_value = predictions.get("world_points_conf" if world is not None else "depth_conf")
    confidence = np.asarray(confidence_value) if confidence_value is not None else None
    if confidence is not None and confidence.shape != (frames, height, width):
        raise ValueError("Confidence map does not match source images")
    rows, columns = np.mgrid[:height, :width]
    points, colors, trace_frames = [], [], []
    point_count = 0
    for index in range(frames):
        camera = poses[index]
        intrinsic = intrinsics[index]
        fx, fy = intrinsic[0, 0], intrinsic[1, 1]
        if min(fx, fy) <= 0:
            raise ValueError("Camera focal length must be positive")
        rotation = camera[:, :3]
        if (
            not np.allclose(rotation.T @ rotation, np.eye(3), atol=0.05)
            or np.linalg.det(rotation) < 0.9
        ):
            raise ValueError("Camera rotation is not a rigid transform")
        if world is None:
            z = depth[index].reshape(height, width)
            camera_points = np.stack(
                [(columns - intrinsic[0, 2]) * z / fx, (rows - intrinsic[1, 2]) * z / fy, z],
                axis=-1,
            )
            frame_points = camera_points @ rotation.T + camera[:, 3]
            valid_depth = z.reshape(-1) > 0
        else:
            frame_points = world[index]
            valid_depth = np.ones(height * width, dtype=bool)
        frame_points = frame_points.reshape(-1, 3)
        conf = (
            confidence[index].reshape(-1)
            if confidence is not None
            else np.ones(height * width, dtype=np.float32)
        )
        valid = np.isfinite(frame_points).all(axis=1) & np.isfinite(conf) & valid_depth
        eligible = np.flatnonzero(valid)
        if len(eligible):
            eligible = eligible[conf[eligible] >= np.percentile(conf[eligible], 40)]
            budget = max_points // frames
            if len(eligible) > budget:
                eligible = eligible[np.linspace(0, len(eligible) - 1, budget, dtype=int)]
        rgb = np.clip(images[index].transpose(1, 2, 0) * 255, 0, 255).astype(np.uint8)
        points.append(frame_points[eligible] @ BASIS)
        colors.append(rgb.reshape(-1, 3)[eligible])
        point_count += len(eligible)
        thumb = cv2.resize(rgb, (160, max(1, round(height / width * 160))))
        ok, jpeg = cv2.imencode(
            ".jpg", cv2.cvtColor(thumb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 70]
        )
        if not ok:
            raise ValueError("Could not create a source-frame preview")
        trace_frames.append(
            {
                "time": timestamps[index],
                "pointEnd": point_count,
                "position": (BASIS @ camera[:, 3]).tolist(),
                "right": (BASIS @ rotation[:, 0]).tolist(),
                "up": (BASIS @ -rotation[:, 1]).tolist(),
                "forward": (BASIS @ rotation[:, 2]).tolist(),
                "fov": 2 * math.atan(height / (2 * fy)),
                "intrinsics": [
                    float(fx),
                    float(fy),
                    float(intrinsic[0, 2]),
                    float(intrinsic[1, 2]),
                ],
                "imageSize": [width, height],
                "thumbnail": "data:image/jpeg;base64," + base64.b64encode(jpeg.tobytes()).decode(),
            }
        )
    trace = {
        "version": 1,
        "coordinateSystem": "gltf-y-up",
        "kind": "reconstruction",
        "frames": trace_frames,
        "pointCount": point_count,
    }
    payload = encode_point_glb(np.concatenate(points), np.concatenate(colors), trace)
    output.write_bytes(payload)
    output.chmod(0o600)
    return {"pointCount": point_count, "frames": frames, "artifactBytes": len(payload)}
