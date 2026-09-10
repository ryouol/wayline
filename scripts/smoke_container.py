"""Exercise a disposable production container without external identity or GPU calls."""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import tempfile
import time
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
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=512m",
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
            revoked = session.delete(base + "/api/shares/" + share["id"], timeout=3)
            assert revoked.status_code == 202, "Share revocation was not accepted"
            assert (
                requests.get(base + "/api/public/share", headers=public, timeout=3).status_code
                == 404
            )
            print("GLB download, header-authenticated sharing and revocation passed")
    finally:
        subprocess.run(["docker", "stop", name], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="wayline:local")
    parser.add_argument("--port", type=int, default=17860)
    arguments = parser.parse_args()
    smoke(arguments.image, arguments.port)
