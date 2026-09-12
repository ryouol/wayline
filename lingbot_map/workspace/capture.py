"""Bounded temporal sampling, including the last frame of a captured video."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from .runner_contract import MAX_FRAMES, sampled_frame_count


def extract_capture(
    source: Path, output: Path, *, max_frames: int = MAX_FRAMES, sample_fps: int = 3
) -> list[float]:
    if not 2 <= max_frames <= MAX_FRAMES or not 1 <= sample_fps <= 15:
        raise ValueError("Invalid frame sampling limits")
    capture = cv2.VideoCapture(str(source))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width, height = (
            capture.get(cv2.CAP_PROP_FRAME_WIDTH),
            capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
        )
        if (
            not capture.isOpened()
            or not math.isfinite(fps)
            or fps <= 0
            or count < 2
            or count / fps > 300
            or not 1 <= min(width, height) <= max(width, height) <= 4096
        ):
            raise ValueError("This capture cannot be decoded within the beta limits")
        length = sampled_frame_count(count / fps, count, max_frames, sample_fps)
        indices = np.linspace(0, count - 1, length, dtype=int)
        output.mkdir(mode=0o700, parents=True, exist_ok=True)
        timestamps: list[float] = []
        time_origin: float | None = None
        for index, source_frame in enumerate(indices):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(source_frame))
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError("The capture contains an unreadable frame")
            presentation_time = float(capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000
            if time_origin is None:
                # Container edit lists can place the first decoded frame before zero.
                time_origin = presentation_time
            timestamp = round(presentation_time - time_origin, 6)
            if (
                not math.isfinite(timestamp)
                or timestamp < 0
                or timestamp > 300
                or (timestamps and timestamp <= timestamps[-1])
            ):
                raise ValueError(
                    "The capture has missing or non-increasing presentation timestamps"
                )
            if max(frame.shape[:2]) > 1600:
                scale = 1600 / max(frame.shape[:2])
                frame = cv2.resize(
                    frame, (round(frame.shape[1] * scale), round(frame.shape[0] * scale))
                )
            path = output / f"{index:06d}.jpg"
            if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92]):
                raise ValueError("The capture frame could not be saved")
            path.chmod(0o600)
            timestamps.append(timestamp)
        return timestamps
    finally:
        capture.release()
