"""Local control console for LingBot-Map.

Wraps demo.py in a small FastAPI service so a video can be dropped in, run with
sane defaults, watched frame by frame, and paused or stopped mid-flight.

Run:  .venv/bin/python webui/server.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

REPO = Path(__file__).resolve().parent.parent
UPLOADS = REPO / "webui" / "uploads"
STATIC = REPO / "webui" / "static"
PYTHON = REPO / ".venv" / "bin" / "python"
CHECKPOINT = REPO / "lingbot-map.pt"

UPLOADS.mkdir(parents=True, exist_ok=True)

# Measured on this machine: CPU fp32, 286-frame courthouse run averaged ~5.0 s/frame.
# Used only for the pre-flight estimate; the live figure replaces it once running.
BASELINE_SEC_PER_FRAME = 5.0

# tqdm reports progress with \r, so lines are split on either carriage return or
# newline rather than read with readline().
RE_INFER = re.compile(
    r"Streaming inference:\s+\d+%\|[^|]*\|\s*(\d+)/(\d+)\s*\[([\d:]+)<([\d:?]+),\s*([\d.]+)(s/it|it/s)"
)
RE_EXTRACT = re.compile(r"Extracting frames:\s+\d+%\|[^|]*\|\s*(\d+)/(\d+)")
RE_EXTRACTED = re.compile(r"Extracted (\d+) frames")
RE_LOADING = re.compile(r"Loading (\d+) images")
RE_LOAD_TIME = re.compile(r"Total load time: ([\d.]+)s")
RE_INFER_DONE = re.compile(r"Inference done in ([\d.]+)s")
RE_VISER = re.compile(r"(?:HTTP|http)://(?:localhost|127\.0\.0\.1):(\d+)")

STAGES = ["queued", "extracting", "loading", "inference", "finishing", "ready"]


@dataclass
class Run:
    id: str
    video: str
    params: dict
    port: int
    stage: str = "queued"
    frame: int = 0
    total: int = 0
    sec_per_frame: float | None = None
    eta: str | None = None
    elapsed_label: str | None = None
    inference_seconds: float | None = None
    load_seconds: float | None = None
    masks_done: int = 0
    masks_total: int = 0
    viewer_url: str | None = None
    error: str | None = None
    paused: bool = False
    started_at: float = field(default_factory=time.time)
    paused_at: float | None = None
    paused_total: float = 0.0
    proc: subprocess.Popen | None = None
    log: list = field(default_factory=list)
    version: int = 0
    frames_dir: Path | None = None

    def snapshot(self) -> dict:
        wall = time.time() - self.started_at - self.paused_total
        if self.paused and self.paused_at:
            wall -= time.time() - self.paused_at
        return {
            "id": self.id,
            "stage": self.stage,
            "paused": self.paused,
            "frame": self.frame,
            "total": self.total,
            "secPerFrame": self.sec_per_frame,
            "eta": self.eta,
            "elapsed": max(0, wall),
            "inferenceSeconds": self.inference_seconds,
            "loadSeconds": self.load_seconds,
            "masksDone": self.masks_done,
            "masksTotal": self.masks_total,
            "viewerUrl": self.viewer_url,
            "error": self.error,
            "video": os.path.basename(self.video),
            "params": self.params,
            "log": self.log[-200:],
            "version": self.version,
        }


RUNS: dict[str, Run] = {}
_next_port = [8101]
_lock = threading.Lock()

app = FastAPI(title="LingBot-Map console")


def probe(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise HTTPException(400, "Could not open that file as video. Try transcoding to H.264 mp4.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    if count <= 0 or fps <= 0:
        raise HTTPException(400, "No decodable frames found. iPhone HEVC often needs transcoding to H.264.")
    return {
        "fps": round(fps, 2),
        "frames": count,
        "duration": count / fps,
        "width": width,
        "height": height,
    }


def _emit(run: Run, line: str) -> None:
    run.log.append(line)
    if len(run.log) > 400:
        del run.log[:-400]


def _handle_line(run: Run, line: str) -> None:
    line = line.rstrip()
    if not line:
        return

    m = RE_EXTRACT.search(line)
    if m:
        run.stage = "extracting"
        run.frame, run.total = int(m.group(1)), int(m.group(2))
        run.version += 1
        return

    m = RE_INFER.search(line)
    if m:
        run.stage = "inference"
        run.frame, run.total = int(m.group(1)), int(m.group(2))
        run.elapsed_label = m.group(3)
        run.eta = m.group(4)
        rate = float(m.group(5))
        run.sec_per_frame = rate if m.group(6) == "s/it" else (1.0 / rate if rate else None)
        run.version += 1
        return

    if RE_EXTRACTED.search(line) or RE_LOADING.search(line):
        run.stage = "loading"
        m2 = RE_EXTRACTED.search(line) or RE_LOADING.search(line)
        run.total = int(m2.group(1))
        run.frame = 0
        _emit(run, line)
        run.version += 1
        return

    m = RE_LOAD_TIME.search(line)
    if m:
        run.load_seconds = float(m.group(1))
        _emit(run, line)
        run.version += 1
        return

    m = RE_INFER_DONE.search(line)
    if m:
        run.inference_seconds = float(m.group(1))
        run.stage = "finishing"
        run.masks_total = run.total
        _emit(run, line)
        run.version += 1
        return

    m = RE_VISER.search(line)
    if m:
        run.viewer_url = f"http://localhost:{m.group(1)}"
        run.stage = "ready"
        _emit(run, f"viewer ready at {run.viewer_url}")
        run.version += 1
        return

    if "Traceback" in line or "Error" in line or "error:" in line:
        _emit(run, line)
        run.version += 1
        return

    # Skip tqdm noise that carries no state we surface.
    if "it/s]" in line or "frame/s]" in line:
        return
    _emit(run, line)
    run.version += 1


def _watch_masks(run: Run) -> None:
    """Sky segmentation writes one file per frame; the count is the only progress signal.

    Runs for the whole life of the process: the directory does not exist yet when
    this thread starts, and masks are only written after inference finishes.
    """
    if not run.frames_dir:
        return
    mask_dir = Path(str(run.frames_dir) + "_sky_masks")
    while run.proc and run.proc.poll() is None:
        if mask_dir.is_dir():
            n = sum(1 for f in mask_dir.iterdir() if f.suffix in (".png", ".jpg", ".npy"))
            if n != run.masks_done:
                run.masks_done = n
                run.masks_total = run.masks_total or run.total
                run.version += 1
        time.sleep(1.5)


def _reader(run: Run) -> None:
    fd = run.proc.stdout.fileno()
    buf = ""
    while True:
        try:
            data = os.read(fd, 8192)
        except OSError:
            break
        if not data:
            break
        buf += data.decode("utf-8", "replace")
        parts = re.split(r"[\r\n]", buf)
        buf = parts.pop()
        for line in parts:
            _handle_line(run, line)

    code = run.proc.wait()
    if run.stage != "ready":
        if code == 0:
            run.stage = "ready"
        elif run.error is None and code not in (-signal.SIGTERM, -signal.SIGKILL):
            tail = " · ".join(run.log[-3:]) or f"exit code {code}"
            run.error = tail
            run.stage = "failed"
        elif run.stage != "failed":
            run.stage = "stopped"
    run.version += 1


def build_command(run: Run) -> list[str]:
    p = run.params
    cmd = [
        str(PYTHON), "-u", "demo.py",
        "--model_path", str(CHECKPOINT),
        "--video_path", run.video,
        "--fps", str(p["extractFps"]),
        "--use_sdpa",
        "--port", str(run.port),
    ]
    if p.get("maxFrames"):
        cmd += ["--first_k", str(p["maxFrames"])]
    if p.get("rotate"):
        cmd += ["--rotate_clockwise_90"]
    if p.get("maskSky"):
        cmd += ["--mask_sky"]
    if p.get("memoryGuard", True):
        cmd += [
            "--kv_cache_sliding_window", "32",
            "--camera_num_iterations", "1",
            "--num_scale_frames", "2",
        ]
    if p.get("mode") == "windowed":
        cmd += ["--mode", "windowed", "--window_size", "64"]
    return cmd


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or "clip.mp4").suffix or ".mp4"
    dest = UPLOADS / f"{uuid.uuid4().hex[:8]}{suffix}"
    with dest.open("wb") as out:
        while chunk := await file.read(1 << 20):
            out.write(chunk)
    try:
        meta = probe(dest)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    return {"path": str(dest), "name": file.filename, "sizeBytes": dest.stat().st_size, **meta}


@app.post("/api/runs")
async def start_run(payload: dict):
    if not CHECKPOINT.exists():
        raise HTTPException(400, "lingbot-map.pt is missing. Run ./download_weights.sh first.")
    video = payload.get("video")
    if not video or not Path(video).exists():
        raise HTTPException(400, "That video is no longer on disk. Upload it again.")

    with _lock:
        port = _next_port[0]
        _next_port[0] += 1

    run = Run(
        id=uuid.uuid4().hex[:12],
        video=video,
        port=port,
        params={
            "extractFps": int(payload.get("extractFps", 3)),
            "maxFrames": int(payload["maxFrames"]) if payload.get("maxFrames") else None,
            "rotate": bool(payload.get("rotate")),
            "maskSky": bool(payload.get("maskSky", True)),
            "memoryGuard": bool(payload.get("memoryGuard", True)),
            "mode": payload.get("mode", "streaming"),
        },
    )
    run.frames_dir = Path(video).parent / f"{Path(video).stem}_frames"
    RUNS[run.id] = run

    run.proc = subprocess.Popen(
        build_command(run),
        cwd=str(REPO),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    threading.Thread(target=_reader, args=(run,), daemon=True).start()
    threading.Thread(target=_watch_masks, args=(run,), daemon=True).start()
    return {"id": run.id}


def _signal_run(run: Run, sig: int) -> None:
    if not run.proc or run.proc.poll() is not None:
        raise HTTPException(409, "That run already finished.")
    os.killpg(os.getpgid(run.proc.pid), sig)


@app.post("/api/runs/{run_id}/pause")
async def pause(run_id: str):
    run = RUNS.get(run_id) or _missing()
    _signal_run(run, signal.SIGSTOP)
    run.paused = True
    run.paused_at = time.time()
    run.version += 1
    return {"paused": True}


@app.post("/api/runs/{run_id}/resume")
async def resume(run_id: str):
    run = RUNS.get(run_id) or _missing()
    _signal_run(run, signal.SIGCONT)
    if run.paused_at:
        run.paused_total += time.time() - run.paused_at
    run.paused = False
    run.paused_at = None
    run.version += 1
    return {"paused": False}


@app.post("/api/runs/{run_id}/stop")
async def stop(run_id: str):
    run = RUNS.get(run_id) or _missing()
    if run.paused:
        try:
            _signal_run(run, signal.SIGCONT)
        except HTTPException:
            pass
        run.paused = False
    _signal_run(run, signal.SIGTERM)
    run.stage = "stopped"
    run.version += 1
    return {"stopped": True}


def _missing():
    raise HTTPException(404, "No such run.")


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    run = RUNS.get(run_id) or _missing()
    return run.snapshot()


@app.get("/api/runs/{run_id}/stream")
async def stream(run_id: str):
    run = RUNS.get(run_id) or _missing()

    async def gen():
        last = -1
        while True:
            if run.version != last:
                last = run.version
                yield f"data: {json.dumps(run.snapshot())}\n\n"
            elif run.stage in ("inference", "extracting"):
                yield f"data: {json.dumps(run.snapshot())}\n\n"
            if run.stage in ("ready", "failed", "stopped") and (
                not run.proc or run.proc.poll() is not None
            ):
                yield f"data: {json.dumps(run.snapshot())}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/baseline")
async def baseline():
    return {"secPerFrame": BASELINE_SEC_PER_FRAME, "hasCheckpoint": CHECKPOINT.exists()}


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


if __name__ == "__main__":
    import uvicorn

    print("LingBot-Map console → http://localhost:7860")
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning")
