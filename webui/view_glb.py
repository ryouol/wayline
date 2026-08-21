"""Serve a GLB point cloud in viser.

  .venv/bin/python webui/view_glb.py outputs/courthouse_gpu.glb [--port 8090]
"""

import argparse
from pathlib import Path

import numpy as np
import trimesh
import viser


def load_points(path: Path):
    """Pull every point cloud and mesh vertex set out of a GLB scene."""
    loaded = trimesh.load(str(path))
    scenes = loaded.geometry.values() if isinstance(loaded, trimesh.Scene) else [loaded]

    # Only the point clouds: the small Trimesh entries are camera frusta, which
    # read as scattered red noise once reduced to bare vertices.
    xyz, rgb = [], []
    for geom in scenes:
        if not isinstance(geom, trimesh.PointCloud):
            continue
        pts = np.asarray(geom.vertices, dtype=np.float32)
        colors = getattr(geom, "colors", None)
        if colors is None or len(colors) == 0:
            colors = getattr(getattr(geom, "visual", None), "vertex_colors", None)
        if pts.size == 0:
            continue
        if colors is None or len(colors) != len(pts):
            colors = np.full((len(pts), 3), 200, dtype=np.uint8)
        xyz.append(pts)
        rgb.append(np.asarray(colors, dtype=np.uint8)[:, :3])

    if not xyz:
        raise SystemExit(f"No point data found in {path}")
    return np.concatenate(xyz), np.concatenate(rgb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("glb", type=Path)
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--point_size", type=float, default=0.004)
    args = ap.parse_args()

    xyz, rgb = load_points(args.glb)
    print(f"{len(xyz):,} points from {args.glb.name}")

    # Centre on the median so the orbit control starts somewhere useful, and
    # drop far outliers that would otherwise flatten the scene to a speck.
    centre = np.median(xyz, axis=0)
    centred = xyz - centre
    keep = np.linalg.norm(centred, axis=1) < np.percentile(np.linalg.norm(centred, axis=1), 99)
    centred, rgb = centred[keep], rgb[keep]
    print(f"{len(centred):,} points after outlier trim")

    # Scene units are arbitrary, so size points and place the camera relative
    # to the cloud's own extent rather than with fixed constants.
    extent = float(np.percentile(np.linalg.norm(centred, axis=1), 95))
    point_size = args.point_size if args.point_size > 0 else extent / 900

    server = viser.ViserServer(port=args.port)
    server.gui.configure_theme(dark_mode=True, show_logo=False)
    server.scene.add_point_cloud(
        "/cloud", points=centred, colors=rgb, point_size=point_size
    )

    @server.on_client_connect
    def _(client: viser.ClientHandle) -> None:
        client.camera.position = (extent * 1.6, -extent * 1.2, extent * 1.1)
        client.camera.look_at = (0.0, 0.0, 0.0)

    print(f"extent {extent:.2f} · point size {point_size:.5f}")
    print(f"viewer → http://localhost:{args.port}")
    import time
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
