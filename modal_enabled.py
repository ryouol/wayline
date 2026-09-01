"""Explicitly selected research-only Modal runner using durable object references.

The default release module is inert.  This separate deployment module checks
the source-controlled compile gate before importing the Modal SDK or constructing
any resource.  It uploads this checkout's source rather than cloning a moving
upstream branch, uses per-job temporary directories, validates archive members,
verifies model digests, and writes GLB output to a Volume instead of returning a
large RPC payload.

Install the pinned client with ``pip install modal==1.5.5``. No paid GPU call is
made by installation or import.
"""

from __future__ import annotations

from modal_app import LINGBOT_RESEARCH_RUNNER_COMPILED

if not LINGBOT_RESEARCH_RUNNER_COMPILED:
    raise RuntimeError(
        "the Modal research runner is not compiled into this release; "
        "deploying modal_enabled.py is disabled"
    )

import re  # noqa: E402

import modal  # noqa: E402

RESEARCH_ACK = "I understand LingBot is research-only"
MODEL_REVISION = "204754b72bb24f561f8d7e7e1e4e4cd9e809adf9"
MODEL_SHA256 = "ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72"
SKYSEG_SHA256 = "b09c0f6cf79e1caa2591b946b659487bd7c8208caddd3f80680cbb169617e378"
SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

app = modal.App("lingbot-map-research", include_source=False)
weights = modal.Volume.from_name("lingbot-research-weights", create_if_missing=True)
jobs = modal.Volume.from_name("lingbot-research-jobs", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0", "libgomp1")
    .add_local_file(
        "requirements/modal.lock",
        remote_path="/opt/lingbot-map/requirements/modal.lock",
        copy=True,
    )
    .run_commands(
        "python -m pip install --require-hashes -r /opt/lingbot-map/requirements/modal.lock"
    )
    .pip_install(
        "torch==2.8.0",
        "torchvision==0.23.0",
        index_url="https://download.pytorch.org/whl/cu128",
    )
    .add_local_dir("lingbot_map", remote_path="/opt/lingbot-map/lingbot_map", copy=True)
    .add_local_file("demo.py", remote_path="/opt/lingbot-map/demo.py", copy=True)
    .env({"PYTHONPATH": "/opt/lingbot-map"})
)


def _acknowledge(value: str) -> None:
    if value != RESEARCH_ACK:
        raise ValueError(
            "LingBot commercial rights are unresolved; pass the exact research acknowledgement"
        )


@app.function(image=image, volumes={"/weights": weights}, timeout=1800)
def fetch_weights(research_ack: str) -> list[dict[str, object]]:
    """Download pinned research assets and verify their exact content digests."""

    import shutil
    from pathlib import Path

    from huggingface_hub import hf_hub_download

    from lingbot_map.checkpoints import verify_checkpoint

    _acknowledge(research_ack)
    records = []
    for filename, expected_sha, expected_size in (
        ("lingbot-map.pt", MODEL_SHA256, 4_632_303_465),
        ("skyseg_batch.onnx", SKYSEG_SHA256, 175_997_119),
    ):
        target = Path("/weights") / filename
        if not target.exists():
            downloaded = hf_hub_download(
                repo_id="robbyant/lingbot-map",
                filename=filename,
                revision=MODEL_REVISION,
            )
            temporary = target.with_suffix(target.suffix + ".part")
            shutil.copyfile(downloaded, temporary)
            temporary.chmod(0o600)
            temporary.replace(target)
        record = verify_checkpoint(target, expected_sha, expected_size)
        if record["sizeBytes"] != expected_size:
            raise RuntimeError(f"unexpected byte length for {filename}")
        records.append({"file": filename, **record})
    weights.commit()
    return records


def _safe_extract_images(archive_path, destination):
    """Extract a flat image archive with count, size, ratio, and path limits."""

    import zipfile
    from pathlib import Path, PurePosixPath

    extensions = {".jpg", ".jpeg", ".png"}
    total = 0
    with zipfile.ZipFile(archive_path) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if not 2 <= len(members) <= 2_000:
            raise ValueError("image archive must contain between 2 and 2,000 files")
        for member in members:
            path = PurePosixPath(member.filename)
            if len(path.parts) != 1 or path.name != member.filename:
                raise ValueError("image archive must be flat and cannot contain paths")
            if Path(path.name).suffix.lower() not in extensions:
                raise ValueError("image archive contains a non-image extension")
            if member.file_size <= 0 or member.file_size > 25 * 1024 * 1024:
                raise ValueError("an image is empty or exceeds 25 MiB")
            if member.compress_size and member.file_size / member.compress_size > 100:
                raise ValueError("archive compression ratio exceeds the safety limit")
            total += member.file_size
            if total > 500 * 1024 * 1024:
                raise ValueError("uncompressed archive exceeds 500 MiB")
            target = destination / path.name
            with archive.open(member) as source, target.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)


@app.function(
    image=image,
    gpu="L4",
    volumes={"/weights": weights, "/jobs": jobs},
    timeout=3600,
)
def reconstruct(
    *,
    job_id: str,
    input_zip_key: str,
    research_ack: str,
    frames: int | None = None,
    confidence_percentile: float = 40.0,
    mask_sky: bool = False,
) -> dict[str, object]:
    """Write a research GLB to ``/jobs/artifacts/<job_id>/scene.glb``."""

    import json
    import shutil
    import sys
    import tempfile
    import time
    from pathlib import Path
    from types import SimpleNamespace

    import torch

    from lingbot_map.checkpoints import verify_checkpoint

    _acknowledge(research_ack)
    if not SAFE_KEY.fullmatch(job_id) or not SAFE_KEY.fullmatch(input_zip_key):
        raise ValueError("job and input keys must be opaque 1-64 character identifiers")
    if frames is not None and not 2 <= frames <= 2_000:
        raise ValueError("frames must be between 2 and 2,000")
    if not 0 <= confidence_percentile <= 100:
        raise ValueError("confidence percentile must be between 0 and 100")

    checkpoint = Path("/weights/lingbot-map.pt")
    skyseg = Path("/weights/skyseg_batch.onnx")
    verify_checkpoint(checkpoint, MODEL_SHA256, 4_632_303_465)
    verify_checkpoint(skyseg, SKYSEG_SHA256, 175_997_119)
    input_archive = Path("/jobs/inbox") / f"{input_zip_key}.zip"
    if input_archive.is_symlink() or not input_archive.is_file():
        raise FileNotFoundError("input archive is not present in the jobs volume")

    sys.path.insert(0, "/opt/lingbot-map")
    import demo
    from lingbot_map.vis.glb_export import predictions_to_glb

    with tempfile.TemporaryDirectory(prefix=f"lingbot-{job_id}-") as temporary:
        temporary_path = Path(temporary)
        image_folder = temporary_path / "images"
        image_folder.mkdir(mode=0o700)
        _safe_extract_images(input_archive, image_folder)
        output_folder = temporary_path / "output"
        output_folder.mkdir(mode=0o700)

        device = torch.device("cuda")
        dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
        args = SimpleNamespace(
            image_size=518,
            patch_size=14,
            enable_3d_rope=True,
            max_frame_num=1024,
            kv_cache_sliding_window=64,
            num_scale_frames=8,
            use_sdpa=True,
            camera_num_iterations=4,
            mode="streaming",
            model_path=str(checkpoint),
            model_sha256=MODEL_SHA256,
        )
        started = time.monotonic()
        images, _, _ = demo.load_images(
            image_folder=str(image_folder),
            first_k=frames,
            image_size=args.image_size,
            patch_size=args.patch_size,
        )
        model = demo.load_model(args, device)
        model.aggregator = model.aggregator.to(dtype=dtype)
        images = images.to(device)
        keyframe_interval = 1 if images.shape[0] <= 320 else -(-images.shape[0] // 320)
        torch.cuda.reset_peak_memory_stats()
        inference_started = time.monotonic()
        with torch.no_grad(), torch.amp.autocast("cuda", dtype=dtype):
            predictions = model.inference_streaming(
                images,
                num_scale_frames=args.num_scale_frames,
                keyframe_interval=keyframe_interval,
                output_device=None,
            )
        torch.cuda.synchronize()
        inference_seconds = time.monotonic() - inference_started
        predictions, images_cpu = demo.postprocess(predictions, images)
        visualization = demo.prepare_for_visualization(predictions, images_cpu)
        scene = predictions_to_glb(
            visualization,
            conf_thres=confidence_percentile,
            show_cam=True,
            mask_sky=mask_sky,
            target_dir=str(output_folder),
            skyseg_model_path=str(skyseg),
            skyseg_sha256=SKYSEG_SHA256,
            sky_mask_dir=str(temporary_path / "sky-masks"),
        )
        local_output = output_folder / "scene.glb"
        scene.export(local_output)
        if local_output.stat().st_size > 100 * 1024 * 1024:
            raise RuntimeError("GLB exceeds the 100 MiB workspace artifact limit")

        durable_dir = Path("/jobs/artifacts") / job_id
        if durable_dir.exists():
            shutil.rmtree(durable_dir)
        durable_dir.mkdir(parents=True, mode=0o700)
        durable_output = durable_dir / "scene.glb"
        shutil.copyfile(local_output, durable_output)
        report = {
            "jobId": job_id,
            "artifactKey": f"artifacts/{job_id}/scene.glb",
            "researchOnly": True,
            "commerciallyCleared": False,
            "license": "NOASSERTION",
            "sourceRevision": MODEL_REVISION,
            "checkpointSha256": MODEL_SHA256,
            "frames": int(images.shape[0]),
            "inferenceSeconds": round(inference_seconds, 3),
            "totalSeconds": round(time.monotonic() - started, 3),
            "peakVramBytes": int(torch.cuda.max_memory_allocated()),
            "artifactBytes": durable_output.stat().st_size,
        }
        (durable_dir / "report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        jobs.commit()
        return report


@app.local_entrypoint()
def main(job_id: str, input_zip_key: str, research_ack: str) -> None:
    """Submit an already-uploaded volume object; returns only a small manifest."""

    import json

    report = reconstruct.remote(
        job_id=job_id,
        input_zip_key=input_zip_key,
        research_ack=research_ack,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
