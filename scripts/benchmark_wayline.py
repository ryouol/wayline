"""Bounded, operator-invoked benchmark through normal Wayline admission.

Requires WAYLINE_BENCHMARK_TOKEN and a manifest of 1–3 explicitly licensed local
videos. Never retries a submission automatically. Outputs contain no credentials
or source paths. Scenes remain private for the fixed-view quality review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlparse
import uuid

import requests


def validate_manifest(manifest, directory):
    scenes = manifest["scenes"]
    if not 1 <= len(scenes) <= 3:
        raise ValueError("Use a fixed set of one to three scenes")
    seen = set()
    for scene in scenes:
        if (
            scene["id"] in seen
            or not scene["license"]
            or scene.get("providerProcessingAllowed") is not True
        ):
            raise ValueError("Scene IDs must be unique and processing rights must be explicit")
        seen.add(scene["id"])
        source = directory / scene["path"]
        if not source.is_file() or source.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("Scene is missing or exceeds 64 MiB")
        if hashlib.sha256(source.read_bytes()).hexdigest() != scene["sha256"]:
            raise ValueError("Scene differs from its fixed reference hash")
    return scenes


def summarize(rows):
    successful = sum(row.get("state") == "ready" for row in rows)
    result = {
        "attempts": len(rows),
        "successfulScenes": successful,
        "failures": sum(row.get("state") == "failed" for row in rows),
    }
    for key in ("estimatedCostUsd", "billedCostUsd"):
        costs = [row.get(key) for row in rows]
        result[key + "PerSuccess"] = (
            sum(costs) / successful
            if successful and all(isinstance(x, (int, float)) and x >= 0 for x in costs)
            else None
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true", help="Submit up to six billable GPU attempts")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    scenes = validate_manifest(manifest, args.manifest.parent)
    if not args.run:
        print(
            json.dumps(
                {
                    "validatedScenes": len(scenes),
                    "maximumAttempts": 2 * len(scenes),
                    "singleChangedVariable": "extractFps: 3 versus 2",
                }
            )
        )
        return
    url = urlparse(args.base_url)
    if url.scheme != "https" and not (
        url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"}
    ):
        raise ValueError("Use HTTPS or a loopback test service")
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    session = requests.Session()
    session.headers["Authorization"] = "Bearer " + os.environ["WAYLINE_BENCHMARK_TOKEN"]
    rows = []

    def save():
        target = args.output / "results.json"
        temp = target.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                {
                    "researchOnly": True,
                    "upstream": "LingBot-Map",
                    "runs": rows,
                    "summary": summarize(rows),
                },
                indent=2,
            )
        )
        temp.chmod(0o600)
        temp.replace(target)

    def request(method, path, **kwargs):
        response = session.request(
            method, args.base_url.rstrip("/") + path, timeout=120, allow_redirects=False, **kwargs
        )
        response.raise_for_status()
        if not 200 <= response.status_code < 300:
            raise RuntimeError("Unexpected API redirect")
        return response.json()

    for scene in scenes:
        with (args.manifest.parent / scene["path"]).open("rb") as video:
            asset = request(
                "POST", "/api/assets", files={"file": ("benchmark.mp4", video, "video/mp4")}
            )
        for fps in (3, 2):
            row = {
                "sceneId": scene["id"],
                "sourceSha256": scene["sha256"],
                "license": scene["license"],
                "sourceMetadata": asset["metadata"],
                "extractFps": fps,
                "maxFrames": 120,
                "state": "submitting",
                "submissionKey": uuid.uuid4().hex,
                "estimatedCostUsd": None,
                "billedCostUsd": None,
                "browserReadiness": None,
                "qualityReview": None,
                "providerQueueSeconds": None,
                "containerStartupSeconds": None,
            }
            rows.append(row)
            save()
            try:
                job = request(
                    "POST",
                    "/api/jobs/research",
                    headers={"Idempotency-Key": row["submissionKey"]},
                    json={"assetId": asset["id"], "maxFrames": 120, "extractFps": fps},
                )
                row["jobId"] = job["id"]
                save()
                deadline = time.monotonic() + 1800
                while job["state"] not in {"ready", "failed", "cancelled"}:
                    if time.monotonic() > deadline:
                        request("POST", f"/api/jobs/{job['id']}/cancel")
                        raise TimeoutError("Cancelled after benchmark observation deadline")
                    time.sleep(2)
                    job = request("GET", f"/api/jobs/{job['id']}")
                row["state"] = job["state"]
                row["queueWaitSeconds"] = (
                    job["startedAt"] - job["createdAt"] if job["startedAt"] else None
                )
                row["serverCompletionSeconds"] = job["finishedAt"] - job["createdAt"]
                row["artifacts"] = [
                    {"id": a["id"], "sha256": a["sha256"], "metadata": a["metadata"]}
                    for a in job.get("artifacts", [])
                ]
            except BaseException as error:
                # A transport error is not proof of provider failure or termination.
                row["state"] = "observation_interrupted"
                row["errorType"] = type(error).__name__
                save()
                raise
            save()
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
