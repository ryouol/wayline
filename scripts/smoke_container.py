"""Exercise a disposable production container without external identity or GPU calls."""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import requests


def smoke(image: str, port: int) -> None:
    name = "wayline-smoke-" + secrets.token_hex(5)
    token = secrets.token_urlsafe(40)
    descriptor, environment_file = tempfile.mkstemp(prefix="wayline-smoke-env-")
    with os.fdopen(descriptor, "w") as stream:
        stream.write(
            f"LINGBOT_BOOTSTRAP_TOKEN={token}\n"
            "LINGBOT_PUBLIC_BASE_URL=https://wayline-test.example\n"
            "LINGBOT_ALLOWED_HOSTS=wayline-test.example\nPORT=10000\n"
            "LINGBOT_MAX_UPLOAD_BYTES=67108864\n"
            "LINGBOT_MAX_ARTIFACT_BYTES=41943040\n"
        )
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--read-only",
                "--memory",
                "512m",
                "--memory-swap",
                "512m",
                "--cpus",
                "0.5",
                "--mount",
                "type=volume,destination=/tmp",
                "--mount",
                "type=volume,destination=/data",
                "--publish",
                f"127.0.0.1:{port}:10000",
                "--env-file",
                environment_file,
                image,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    finally:
        Path(environment_file).unlink()
    base = f"http://127.0.0.1:{port}"
    try:
        with requests.Session() as session:
            session.headers.update(
                {"Host": "wayline-test.example", "Authorization": "Bearer " + token}
            )
            for _ in range(40):
                try:
                    if session.get(base + "/healthz", timeout=2).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.25)
            else:
                raise AssertionError("Container never became ready")
            assert (
                requests.get(
                    base + "/api/me", headers={"Host": "wayline-test.example"}, timeout=3
                ).status_code
                == 401
            )
            assert (
                requests.get(
                    base + "/healthz", headers={"Host": "wrong.example"}, timeout=3
                ).status_code
                == 400
            )
            assert session.get(base + "/api/config", timeout=3).json()["googleSignIn"] is False
            print("Production health, host and authentication checks passed")
            source = Path(__file__).resolve().parents[1] / "tests/fixtures/vfr-test-pattern.mp4"
            with source.open("rb") as capture:
                uploaded = session.post(
                    base + "/api/assets",
                    files={"file": ("generated-test-pattern.mp4", capture, "video/mp4")},
                    timeout=15,
                )
            assert uploaded.status_code == 201, "Generated capture inspection failed"
            assert uploaded.json()["metadata"]["frames"] == 10
            assert (
                session.delete(base + "/api/assets/" + uploaded.json()["id"], timeout=3).status_code
                == 202
            )
            print("Authenticated multipart upload, video inspection and deletion passed")
            for _ in range(2):
                response = session.post(base + "/api/jobs/sample", timeout=5)
                assert response.status_code == 202, "Sample submission failed"
                job_id = response.json()["id"]
                for _ in range(60):
                    job = session.get(base + "/api/jobs/" + job_id, timeout=3).json()
                    if job["state"] in {"ready", "failed", "cancelled"}:
                        break
                    time.sleep(0.15)
                assert job["state"] == "ready", "Sample did not reach ready"
            print("Two sequential sample jobs reached ready")
            scene = next(item for item in job["artifacts"] if item["kind"] == "scene")
            content = session.get(base + "/api/artifacts/" + scene["id"] + "/download", timeout=3)
            assert content.status_code == 200 and content.content[:4] == b"glTF"
            shared = session.post(
                base + "/api/artifacts/" + scene["id"] + "/shares",
                json={"ttlSeconds": 300},
                timeout=3,
            )
            assert shared.status_code == 201, "Share creation failed"
            share = shared.json()
            public = {
                "Host": "wayline-test.example",
                "Authorization": "Bearer " + urlsplit(share["url"]).fragment,
            }
            assert (
                requests.get(base + "/api/public/share", headers=public, timeout=3).status_code
                == 200
            )
            assert (
                requests.get(base + "/api/public/share/content", headers=public, timeout=3).content
                == content.content
            )
            # Pad the owned synthetic fixture to the deployed upload ceiling.
            # Issue scene requests alongside the client upload task; server overlap
            # is not synchronized. Small decoded dimensions do not establish
            # worst-case decoder memory.
            with tempfile.TemporaryFile() as capture, ThreadPoolExecutor(max_workers=1) as pool:
                capture.write(source.read_bytes())
                capture.truncate(64 * 1024 * 1024)
                capture.seek(0)
                upload = pool.submit(
                    requests.post,
                    base + "/api/assets",
                    headers=dict(session.headers),
                    files={"file": ("padded-test-pattern.mp4", capture, "video/mp4")},
                    timeout=60,
                )
                for _ in range(3):
                    response = requests.get(
                        base + "/api/public/share/content", headers=public, timeout=10
                    )
                    assert response.status_code == 200 and response.content == content.content
                padded = upload.result(timeout=65)
            assert padded.status_code == 201, "Maximum-size generated upload failed"
            assert padded.json()["sizeBytes"] == 64 * 1024 * 1024
            assert padded.json()["metadata"]["frames"] == 10
            assert (
                session.delete(base + "/api/assets/" + padded.json()["id"], timeout=3).status_code
                == 202
            )
            print("64 MiB multipart upload and shared scene delivery passed")
            revoked = session.delete(base + "/api/shares/" + share["id"], timeout=3)
            assert revoked.status_code == 202, "Share revocation was not accepted"
            assert (
                requests.get(base + "/api/public/share", headers=public, timeout=3).status_code
                == 404
            )
            print("GLB download, header-authenticated sharing and revocation passed")
            peak = subprocess.check_output(
                ["docker", "exec", name, "cat", "/sys/fs/cgroup/memory.peak"], text=True
            ).strip()
            print(f"512 MiB / 0.5 CPU smoke peak memory: {int(peak) / 1024**2:.1f} MiB")
    finally:
        subprocess.run(["docker", "stop", name], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="wayline:local")
    parser.add_argument("--port", type=int, default=17860)
    arguments = parser.parse_args()
    smoke(arguments.image, arguments.port)
