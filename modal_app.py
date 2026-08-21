"""Run LingBot-Map on a Modal GPU and bring the geometry back as a GLB.

The local CPU run had to trade quality for memory. On a GPU none of that is
necessary: bf16 halves the KV cache, so the full 64-frame attention window,
8 scale frames and 4 camera-refinement iterations all fit.

  .venv/bin/modal run modal_app.py::fetch_weights     # once, ~4.5 GB into a volume
  .venv/bin/modal run modal_app.py --scene courthouse
"""

import modal

app = modal.App("lingbot-map")

weights = modal.Volume.from_name("lingbot-weights", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "libgl1", "libglib2.0-0", "libgomp1")
    .pip_install(
        "torch==2.8.0",
        "torchvision==0.23.0",
        index_url="https://download.pytorch.org/whl/cu128",
    )
    .pip_install(
        "numpy<2",
        "Pillow",
        "huggingface_hub",
        "hf_transfer",
        "einops",
        "safetensors",
        "opencv-python-headless",
        "tqdm",
        "scipy",
        "trimesh",
        # 3.9 removed matplotlib.cm.get_cmap, which this repo still calls.
        "matplotlib<3.9",
        "onnxruntime",
        "requests",
        # Unused headlessly, but lingbot_map.vis.__init__ imports the viser
        # viewer before glb_export is reachable.
        "viser",
    )
    .run_commands(
        "git clone --depth 1 https://github.com/Robbyant/lingbot-map.git /root/lingbot-map",
        "cd /root/lingbot-map && pip install -e . --no-deps",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)


@app.function(image=image, volumes={"/weights": weights}, timeout=3600)
def fetch_weights():
    """Pull the checkpoint and sky model into a volume so runs start instantly."""
    import shutil
    from pathlib import Path
    from huggingface_hub import hf_hub_download

    dest = Path("/weights")
    for repo, fn, out in [
        ("robbyant/lingbot-map", "lingbot-map.pt", "lingbot-map.pt"),
        ("JianyuanWang/skyseg", "skyseg.onnx", "skyseg.onnx"),
    ]:
        target = dest / out
        if target.exists():
            print(f"{out} already present ({target.stat().st_size/1e9:.2f} GB)")
            continue
        print(f"downloading {out} …")
        p = hf_hub_download(repo_id=repo, filename=fn)
        shutil.copy(p, target)
        print(f"  {out}: {target.stat().st_size/1e9:.2f} GB")

    weights.commit()
    return sorted(f.name for f in dest.iterdir())


@app.function(
    image=image,
    gpu="L4",
    volumes={"/weights": weights},
    timeout=3600,
)
def reconstruct(
    scene: str = "courthouse",
    frames: int | None = None,
    conf_percentile: float = 40.0,
    mask_sky: bool = True,
    images_zip: bytes | None = None,
):
    """Reconstruct a scene at full quality and return (glb_bytes, report)."""
    import io
    import sys
    import time
    import zipfile
    from pathlib import Path
    from types import SimpleNamespace

    import torch

    sys.path.insert(0, "/root/lingbot-map")
    import demo  # noqa: E402  — load_images / load_model / postprocess live here
    from lingbot_map.vis.glb_export import predictions_to_glb  # noqa: E402

    # Either one of the repo's bundled scenes, or frames the caller shipped up.
    if images_zip:
        folder = Path("/tmp/scene")
        folder.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(images_zip)) as z:
            z.extractall(folder)
        image_folder = str(folder)
    else:
        image_folder = f"/root/lingbot-map/example/{scene}"

    device = torch.device("cuda")
    cap = torch.cuda.get_device_capability()[0]
    dtype = torch.bfloat16 if cap >= 8 else torch.float16
    gpu_name = torch.cuda.get_device_name(0)
    print(f"{gpu_name} · capability {cap}.x · {dtype}")

    # Full-quality settings — the defaults the README ships, none of the
    # memory-guard reductions the 24 GB CPU box needed.
    args = SimpleNamespace(
        image_size=518,
        patch_size=14,
        enable_3d_rope=True,
        max_frame_num=1024,
        kv_cache_sliding_window=64,
        num_scale_frames=8,
        use_sdpa=True,            # FlashInfer would need an nvcc toolchain to JIT
        camera_num_iterations=4,
        mode="streaming",
        model_path="/weights/lingbot-map.pt",
    )

    t_load = time.time()
    images, _paths, resolved = demo.load_images(
        image_folder=image_folder,
        video_path=None,
        fps=10,
        first_k=frames,
        stride=1,
        image_size=args.image_size,
        patch_size=args.patch_size,
    )
    model = demo.load_model(args, device)
    model.aggregator = model.aggregator.to(dtype=dtype)
    load_seconds = time.time() - t_load

    images = images.to(device)
    n = images.shape[0]
    print(f"{n} frames, {tuple(images.shape)}")

    keyframe_interval = 1 if n <= 320 else -(-n // 320)

    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    with torch.no_grad(), torch.amp.autocast("cuda", dtype=dtype):
        predictions = model.inference_streaming(
            images,
            num_scale_frames=args.num_scale_frames,
            keyframe_interval=keyframe_interval,
            output_device=None,
        )
    torch.cuda.synchronize()
    infer_seconds = time.time() - t0
    peak_gb = torch.cuda.max_memory_allocated() / 1e9

    print(f"inference {infer_seconds:.1f}s · {infer_seconds/n:.3f} s/frame · peak {peak_gb:.1f} GB")

    predictions, images_cpu = demo.postprocess(predictions, images)
    vis = demo.prepare_for_visualization(predictions, images_cpu)

    scene_obj = predictions_to_glb(
        vis,
        conf_thres=conf_percentile,
        show_cam=True,
        mask_sky=mask_sky,
        target_dir="/tmp/glb",
        skyseg_model_path="/weights/skyseg.onnx",
        sky_mask_dir="/tmp/sky_masks",
    )

    out = "/tmp/scene.glb"
    scene_obj.export(out)
    glb = Path(out).read_bytes()

    report = {
        "gpu": gpu_name,
        "dtype": str(dtype),
        "frames": n,
        "loadSeconds": round(load_seconds, 1),
        "inferenceSeconds": round(infer_seconds, 1),
        "secPerFrame": round(infer_seconds / n, 3),
        "peakVramGb": round(peak_gb, 2),
        "keyframeInterval": keyframe_interval,
        "confPercentile": conf_percentile,
        "glbMb": round(len(glb) / 1e6, 1),
    }
    print(report)
    return glb, report


@app.local_entrypoint()
def main(scene: str = "courthouse", frames: int = 0, conf: float = 40.0, out: str = ""):
    import json
    from pathlib import Path

    glb, report = reconstruct.remote(
        scene=scene,
        frames=frames or None,
        conf_percentile=conf,
    )
    target = Path(out or f"outputs/{scene}_gpu.glb")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(glb)
    print(json.dumps(report, indent=2))
    print(f"\nwrote {target}  ({len(glb)/1e6:.1f} MB)")
