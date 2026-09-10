"""Wayline's explicitly deployed, private Modal GPU worker for original LingBot-Map.

Deploy: modal deploy modal_app.py
Prepare the pinned checkpoint once: modal run modal_app.py
No HTTP endpoint is registered. Only authenticated Modal clients can submit work.
"""

from __future__ import annotations

import re

import modal

from lingbot_map.workspace.config import RESEARCH_ACKNOWLEDGEMENT
from lingbot_map.workspace.runner_contract import (
    CAPTURE_VOLUME,
    MAX_FRAMES,
    MODAL_APP,
    MODEL_BYTES,
    MODEL_REVISION,
    MODEL_SHA256,
    REMOTE_TIMEOUT,
    WEIGHTS_VOLUME,
)

SAFE_ATTEMPT = re.compile(r"^[0-9a-f]{32}$")
app = modal.App(MODAL_APP, include_source=False)
weights = modal.Volume.from_name(WEIGHTS_VOLUME, create_if_missing=True)
jobs = modal.Volume.from_name(CAPTURE_VOLUME, create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0", "libgomp1")
    .add_local_file("requirements/modal.lock", "/opt/wayline/requirements.txt", copy=True)
    .run_commands("python -m pip install --require-hashes -r /opt/wayline/requirements.txt")
    .pip_install(
        "torch==2.8.0", "torchvision==0.23.0", index_url="https://download.pytorch.org/whl/cu128"
    )
    .add_local_dir("lingbot_map", "/opt/wayline/lingbot_map", copy=True)
    .add_local_file("demo.py", "/opt/wayline/demo.py", copy=True)
    .add_local_file("modal_app.py", "/opt/wayline/modal_app.py", copy=True)
    .env({"PYTHONPATH": "/opt/wayline"})
    .run_commands(
        "python -c 'import modal_app; import demo; "
        "from lingbot_map.models.gct_stream import GCTStream'"
    )
)


def acknowledge(value: str) -> None:
    if value != RESEARCH_ACKNOWLEDGEMENT:
        raise ValueError("This runner is for the explicitly acknowledged LingBot research preview")


@app.function(image=image, volumes={"/weights": weights}, timeout=1200, retries=0)
def prepare_weights(research_ack: str) -> dict:
    import shutil
    from pathlib import Path

    from huggingface_hub import hf_hub_download

    from lingbot_map.checkpoints import verify_checkpoint

    acknowledge(research_ack)
    target = Path("/weights/lingbot-map.pt")
    if not target.exists():
        source = hf_hub_download("robbyant/lingbot-map", "lingbot-map.pt", revision=MODEL_REVISION)
        temporary = target.with_suffix(".part")
        shutil.copyfile(source, temporary)
        temporary.chmod(0o600)
        verify_checkpoint(temporary, MODEL_SHA256, MODEL_BYTES)
        temporary.replace(target)
    result = verify_checkpoint(target, MODEL_SHA256, MODEL_BYTES)
    weights.commit()
    return {"sha256": result["sha256"], "sizeBytes": result["sizeBytes"]}


@app.function(
    image=image,
    gpu="A100-80GB",
    volumes={"/weights": weights, "/jobs": jobs},
    timeout=REMOTE_TIMEOUT,
    retries=0,
    max_containers=1,
    scaledown_window=30,
)
def reconstruct(
    *,
    attempt_id: str,
    research_ack: str,
    expires_at: float,
    max_frames: int = 120,
    extract_fps: int = 3,
) -> dict:
    import json
    import tempfile
    import time
    from pathlib import Path
    from types import SimpleNamespace

    import torch

    import demo
    from lingbot_map.workspace.capture import extract_capture
    from lingbot_map.workspace.scene_export import export_reconstruction

    acknowledge(research_ack)
    if not 0 < expires_at - time.time() <= 3600:
        raise ValueError("Capture submission has expired or has an invalid deadline")
    if (
        not SAFE_ATTEMPT.fullmatch(attempt_id)
        or not 2 <= max_frames <= MAX_FRAMES
        or not 1 <= extract_fps <= 15
    ):
        raise ValueError("Invalid capture job parameters")
    jobs.reload()
    root = Path("/jobs") / attempt_id
    source = root / "source.video"
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 250 * 1024 * 1024:
        raise ValueError("Missing or oversized source capture")
    checkpoint = Path("/weights/lingbot-map.pt")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="wayline-") as directory:
        folder = Path(directory) / "frames"
        timestamps = extract_capture(source, folder, max_frames=max_frames, sample_fps=extract_fps)
        args = SimpleNamespace(
            image_size=518,
            patch_size=14,
            enable_3d_rope=True,
            max_frame_num=1024,
            kv_cache_sliding_window=64,
            num_scale_frames=min(8, len(timestamps)),
            use_sdpa=True,
            camera_num_iterations=4,
            mode="streaming",
            model_path=str(checkpoint),
            model_sha256=MODEL_SHA256,
        )
        device = torch.device("cuda")
        dtype = torch.bfloat16
        images, _, _ = demo.load_images(image_folder=str(folder), image_size=518, patch_size=14)
        model = demo.load_model(args, device)
        model.aggregator = model.aggregator.to(dtype=dtype)
        images = images.to(device)
        torch.cuda.reset_peak_memory_stats()
        if time.time() >= expires_at:
            raise ValueError("Capture expired before model inference")
        inference_started = time.monotonic()
        with torch.no_grad(), torch.amp.autocast("cuda", dtype=dtype):
            predictions = model.inference_streaming(
                images,
                num_scale_frames=args.num_scale_frames,
                keyframe_interval=1,
                output_device="cpu",
            )
        torch.cuda.synchronize()
        inference_seconds = time.monotonic() - inference_started
        predictions, images_cpu = demo.postprocess(predictions, images)
        visualization = demo.prepare_for_visualization(predictions, images_cpu)
        report = export_reconstruction(visualization, timestamps, root / "scene.glb")
        report.update(
            inferenceSeconds=inference_seconds,
            totalSeconds=time.monotonic() - started,
            peakVramBytes=torch.cuda.max_memory_allocated(),
            sourceRevision=MODEL_REVISION,
            checkpointSha256=MODEL_SHA256,
            researchOnly=True,
            commerciallyCleared=False,
        )
        (root / "report.json").write_text(json.dumps(report, allow_nan=False))
        (root / "report.json").chmod(0o600)
        jobs.commit()
    return report


@app.local_entrypoint()
def main():
    """An explicit operator action to prepare the original model, without a GPU job."""
    print(prepare_weights.remote(RESEARCH_ACKNOWLEDGEMENT))
