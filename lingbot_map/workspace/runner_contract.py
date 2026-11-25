"""Dependency-free contract shared by the web client and private GPU deployment."""

import math

MODAL_APP = "wayline-reconstruction"
WEIGHTS_VOLUME = "wayline-model-weights"
CAPTURE_VOLUME = "wayline-capture-jobs"
REMOTE_TIMEOUT = 600
MAX_FRAMES = 120
MODEL_REVISION = "204754b72bb24f561f8d7e7e1e4e4cd9e809adf9"
MODEL_SHA256 = "ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72"
MODEL_BYTES = 4_632_303_465


def sampled_frame_count(
    duration: float, source_frames: int, max_frames: int, sample_fps: int
) -> int:
    if (
        not math.isfinite(duration)
        or duration <= 0
        or source_frames < 2
        or not 2 <= max_frames <= MAX_FRAMES
        or not 1 <= sample_fps <= 15
    ):
        raise ValueError("Invalid capture sampling limits")
    return min(max_frames, source_frames, max(2, math.ceil(duration * sample_fps)))
