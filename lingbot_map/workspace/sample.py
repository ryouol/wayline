"""Deterministic synthetic point-cloud sample authored for this workspace."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass

SAMPLE_LICENSE_ID = "CC0-1.0"
SAMPLE_VERSION = "synthetic-studio-v1"


@dataclass(frozen=True, slots=True)
class SyntheticScene:
    glb: bytes
    point_count: int
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]


def _surface_box(
    points: list[tuple[float, float, float]],
    colors: list[tuple[int, int, int]],
    *,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    color: tuple[int, int, int],
    steps: int,
) -> None:
    """Append a sparse, deterministic cuboid surface."""

    cx, cy, cz = center
    sx, sy, sz = size
    for face in range(6):
        axis = face // 2
        sign = -1 if face % 2 == 0 else 1
        for row in range(steps + 1):
            for column in range(steps + 1):
                values = [
                    (column / steps - 0.5) * sx,
                    (row / steps - 0.5) * sy,
                    (row / steps - 0.5) * sz,
                ]
                if axis == 0:
                    values = [sign * sx / 2, (column / steps - 0.5) * sy, (row / steps - 0.5) * sz]
                elif axis == 1:
                    values = [(column / steps - 0.5) * sx, sign * sy / 2, (row / steps - 0.5) * sz]
                else:
                    values = [(column / steps - 0.5) * sx, (row / steps - 0.5) * sy, sign * sz / 2]
                points.append((cx + values[0], cy + values[1], cz + values[2]))
                shade = 0.82 + 0.18 * ((row + column + face) % 4) / 3
                colors.append(
                    (
                        min(255, round(color[0] * shade)),
                        min(255, round(color[1] * shade)),
                        min(255, round(color[2] * shade)),
                    )
                )


def build_synthetic_scene() -> SyntheticScene:
    """Build a compact studio-like point cloud without source imagery or model inference."""

    points: list[tuple[float, float, float]] = []
    colors: list[tuple[int, int, int]] = []

    # Floor grid, with a neutral color and a highlighted circulation path.
    for xi in range(-30, 31):
        for yi in range(-22, 23):
            x, y = xi / 5, yi / 5
            z = 0.025 * math.sin(x * 1.7) * math.cos(y * 1.3)
            points.append((x, y, z))
            on_path = abs(y) < 0.55 and -5.2 < x < 5.2
            colors.append((56, 189, 163) if on_path else (100, 116, 139))

    _surface_box(
        points,
        colors,
        center=(-3.7, -1.7, 1.0),
        size=(1.9, 1.5, 2.0),
        color=(83, 119, 159),
        steps=10,
    )
    _surface_box(
        points,
        colors,
        center=(0.0, 1.55, 0.6),
        size=(3.2, 1.1, 1.2),
        color=(189, 140, 73),
        steps=12,
    )
    _surface_box(
        points,
        colors,
        center=(3.75, -1.45, 1.4),
        size=(1.4, 1.4, 2.8),
        color=(126, 102, 163),
        steps=10,
    )

    # A curved overhead feature makes orbiting and depth changes obvious.
    for ring in range(17):
        x = -2.4 + ring * 0.3
        for segment in range(41):
            angle = math.pi * segment / 40
            y = 2.7 * math.cos(angle)
            z = 1.0 + 2.7 * math.sin(angle)
            points.append((x, y, z))
            colors.append((218, 226, 235))

    minimum = (
        min(point[0] for point in points),
        min(point[1] for point in points),
        min(point[2] for point in points),
    )
    maximum = (
        max(point[0] for point in points),
        max(point[1] for point in points),
        max(point[2] for point in points),
    )
    position_data = b"".join(struct.pack("<fff", *point) for point in points)
    # Each vertex color needs a four-byte stride, not only an aligned buffer end.
    color_data = b"".join(struct.pack("BBBB", *color, 255) for color in colors)
    while len(position_data) % 4:
        position_data += b"\0"
    while len(color_data) % 4:
        color_data += b"\0"
    binary = position_data + color_data

    document = {
        "asset": {"version": "2.0", "generator": "LingBot Scene Workspace synthetic sample"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "Synthetic studio"}],
        "meshes": [
            {
                "name": "Synthetic studio point cloud",
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "COLOR_0": 1},
                        "mode": 0,
                    }
                ],
            }
        ],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(position_data), "target": 34962},
            {
                "buffer": 0,
                "byteOffset": len(position_data),
                "byteLength": len(color_data),
                "target": 34962,
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(points),
                "type": "VEC3",
                "min": list(minimum),
                "max": list(maximum),
            },
            {
                "bufferView": 1,
                "componentType": 5121,
                "count": len(colors),
                "type": "VEC4",
                "normalized": True,
            },
        ],
        "extras": {
            "sampleVersion": SAMPLE_VERSION,
            "license": SAMPLE_LICENSE_ID,
            "source": "deterministically generated; no source imagery and no model inference",
        },
    }
    json_chunk = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary)
    glb = (
        struct.pack("<III", 0x46546C67, 2, total_length)
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
        + struct.pack("<II", len(binary), 0x004E4942)
        + binary
    )
    return SyntheticScene(glb=glb, point_count=len(points), bounds=(minimum, maximum))


def sample_manifest(scene: SyntheticScene) -> bytes:
    return (
        json.dumps(
            {
                "id": SAMPLE_VERSION,
                "kind": "synthetic_point_cloud",
                "pointCount": scene.point_count,
                "bounds": scene.bounds,
                "license": SAMPLE_LICENSE_ID,
                "provenance": {
                    "sourceImages": False,
                    "modelInference": False,
                    "generator": "lingbot_map.workspace.sample.build_synthetic_scene",
                },
                "limitations": [
                    "This sample demonstrates the workspace, artifact, viewer, "
                    "and sharing flow only.",
                    "It is not evidence of LingBot reconstruction quality or performance.",
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
