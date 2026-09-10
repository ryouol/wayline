"""Exercise streamed bodies through FastAPI, including multipart spool cleanup."""

import asyncio
import json
import shutil
from dataclasses import replace

import httpx2 as httpx
import pytest
import starlette.formparsers
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect

from lingbot_map.workspace.app import create_app

from .conftest import BOOTSTRAP_TOKEN


def streamed_post(app, path, chunks, headers):
    consumed = []

    async def request():
        async def body():
            for chunk in chunks:
                consumed.append(len(chunk))
                yield chunk

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.post(path, content=body(), headers=headers)

    return asyncio.run(request()), consumed


@pytest.mark.parametrize("declared_length", [None, "1"])
def test_json_stream_limit_stops_reading_before_parse(client, declared_length):
    headers = {"Content-Type": "application/json"}
    if declared_length is not None:
        headers["Content-Length"] = declared_length
    response, consumed = streamed_post(
        client.app,
        "/api/session",
        [b" " * (64 * 1024), b" ", b"unread remainder"],
        headers,
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert consumed == [64 * 1024, 1]


@pytest.mark.parametrize("declared_length", [None, "1"])
def test_multipart_stream_limit_closes_spooled_files(client, monkeypatch, declared_length):
    opened = []
    original = starlette.formparsers.SpooledTemporaryFile

    def track_spool(*args, **kwargs):
        spool = original(*args, **kwargs)
        opened.append(spool)
        return spool

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", track_spool)
    prefix = (
        b'--capture\r\nContent-Disposition: form-data; name="file"; filename="large.mp4"\r\n'
        b"Content-Type: video/mp4\r\n\r\n"
    )
    headers = {
        "Content-Type": "multipart/form-data; boundary=capture",
        "Authorization": f"Bearer {BOOTSTRAP_TOKEN}",
    }
    if declared_length is not None:
        headers["Content-Length"] = declared_length
    # The fixture allows a 1 MiB file plus 1 MiB multipart overhead. Roll the
    # actual parser spool to disk, then cross that total before the last chunk.
    block = b"x" * (1100 * 1024)
    response, consumed = streamed_post(
        client.app, "/api/assets", [prefix, block, block, b"\r\n--capture--\r\n"], headers
    )
    assert response.status_code == 413
    assert len(consumed) == 3
    assert len(opened) == 1 and opened[0]._rolled and opened[0].closed
    assert response.headers["x-frame-options"] == "DENY"


def test_streamed_json_at_limit_keeps_normal_login(client):
    body = json.dumps({"token": BOOTSTRAP_TOKEN}).encode()
    response, _ = streamed_post(
        client.app,
        "/api/session",
        [body[:10], body[10:], b" " * (64 * 1024 - len(body))],
        {"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["accountType"] == "operator"


def test_small_chunked_multipart_keeps_normal_upload(client):
    response, _ = streamed_post(
        client.app,
        "/api/assets",
        [
            b'--capture\r\nContent-Disposition: form-data; name="file"; filename="small.mp4"\r\n',
            b"Content-Type: video/mp4\r\n\r\n",
            b"\x00\x00\x00\x18ftypisom" + b"\x00" * 52,
            b"\r\n--capture--\r\n",
        ],
        {
            "Content-Type": "multipart/form-data; boundary=capture",
            "Authorization": f"Bearer {BOOTSTRAP_TOKEN}",
        },
    )
    assert response.status_code == 201
    assert response.json()["sizeBytes"] == 64


def test_upload_authentication_and_guest_rejection_precede_spooling(client, monkeypatch):
    def unexpected_spool(*args, **kwargs):
        pytest.fail("Rejected principal must not allocate multipart files")

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", unexpected_spool)
    assert client.post("/api/assets", files={"file": ("clip.mp4", b"x")}).status_code == 401
    trial = client.post("/api/trial")
    assert trial.status_code == 200
    client.headers["X-CSRF-Token"] = trial.json()["csrfToken"]
    assert client.post("/api/assets", files={"file": ("clip.mp4", b"x")}).status_code == 403


def test_extra_multipart_files_are_rejected_and_closed(authenticated_client, monkeypatch):
    opened = []
    original = starlette.formparsers.SpooledTemporaryFile

    def track_spool(*args, **kwargs):
        spool = original(*args, **kwargs)
        opened.append(spool)
        return spool

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", track_spool)
    response = authenticated_client.post(
        "/api/assets",
        files=[("file", ("a.mp4", b"a" * 1024)), ("file", ("b.mp4", b"b" * 1024))],
    )
    assert response.status_code == 400
    assert len(opened) == 1 and opened[0].closed
    # Parser failure releases admission for the next request.
    assert authenticated_client.post("/api/assets").status_code == 422


def test_upload_request_rate_is_checked_before_spooling(settings, service, monkeypatch):
    limited = replace(settings, upload_rate_per_minute=1)
    with TestClient(create_app(limited, service=service, start_worker=False)) as client:
        client.headers["Authorization"] = f"Bearer {BOOTSTRAP_TOKEN}"
        assert client.post("/api/assets").status_code == 422

        def unexpected_spool(*args, **kwargs):
            pytest.fail("Rate-limited request must not allocate multipart files")

        monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", unexpected_spool)
        assert client.post("/api/assets", files={"file": ("clip.mp4", b"x")}).status_code == 429


def test_upload_admission_bounds_concurrent_parsers(client):
    async def concurrent_uploads():
        parsing = asyncio.Event()
        release = asyncio.Event()

        async def first_body():
            yield (
                b'--clip\r\nContent-Disposition: form-data; name="file"; filename="a.mp4"\r\n'
                b"Content-Type: video/mp4\r\n\r\n"
            )
            parsing.set()
            await release.wait()
            yield b"\x00\x00\x00\x18ftypisom" + b"\x00" * 52 + b"\r\n--clip--\r\n"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client.app), base_url="http://testserver"
        ) as peer:
            peer.headers["Authorization"] = f"Bearer {BOOTSTRAP_TOKEN}"
            first = asyncio.create_task(
                peer.post(
                    "/api/assets",
                    content=first_body(),
                    headers={"Content-Type": "multipart/form-data; boundary=clip"},
                )
            )
            try:
                await asyncio.wait_for(parsing.wait(), 5)
                rejected = await peer.post("/api/assets", files={"file": ("b.mp4", b"x")})
                assert rejected.status_code == 429
                assert rejected.headers["retry-after"] == "5"
            finally:
                release.set()
            assert (await asyncio.wait_for(first, 5)).status_code == 201
            assert (await peer.post("/api/assets")).status_code == 422

    asyncio.run(concurrent_uploads())


@pytest.mark.parametrize("disconnect", [False, True])
def test_interrupted_upload_closes_files_and_releases_admission(
    settings, service, monkeypatch, disconnect
):
    opened = []
    original = starlette.formparsers.SpooledTemporaryFile

    def track_spool(*args, **kwargs):
        spool = original(*args, **kwargs)
        opened.append(spool)
        return spool

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", track_spool)
    app = create_app(
        replace(settings, upload_timeout_seconds=1), service=service, start_worker=False
    )

    async def exercise():
        async def interrupted_body():
            yield (
                b'--clip\r\nContent-Disposition: form-data; name="file"; filename="a.mp4"\r\n'
                b"Content-Type: video/mp4\r\n\r\n" + b"x" * (1100 * 1024)
            )
            if disconnect:
                raise ClientDisconnect()
            await asyncio.Event().wait()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as peer:
            peer.headers["Authorization"] = f"Bearer {BOOTSTRAP_TOKEN}"
            request = peer.post(
                "/api/assets",
                content=interrupted_body(),
                headers={"Content-Type": "multipart/form-data; boundary=clip"},
            )
            if disconnect:
                assert (await request).status_code == 400
            else:
                assert (await asyncio.wait_for(request, 5)).status_code == 408
            assert len(opened) == 1 and opened[0]._rolled and opened[0].closed
            assert (await peer.post("/api/assets")).status_code == 422

    asyncio.run(exercise())


def test_temporary_storage_floor_precedes_spooling_and_recovers(
    authenticated_client, settings, monkeypatch
):
    required = settings.max_upload_bytes + settings.storage_min_free_bytes
    free = required - 1
    monkeypatch.setattr(shutil, "disk_usage", lambda _: type("Usage", (), {"free": free})())
    original = starlette.formparsers.SpooledTemporaryFile

    def unexpected_spool(*args, **kwargs):
        pytest.fail("Storage rejection must precede multipart allocation")

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", unexpected_spool)
    files = {"file": ("small.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 52, "video/mp4")}
    assert authenticated_client.post("/api/assets", files=files).status_code == 507
    free = required
    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", original)
    assert authenticated_client.post("/api/assets", files=files).status_code == 201


def test_upload_openapi_retains_required_file(client):
    body = client.app.openapi()["paths"]["/api/assets"]["post"]["requestBody"]
    assert body["required"] is True
    schema = body["content"]["multipart/form-data"]["schema"]
    assert schema["required"] == ["file"]
    assert schema["properties"]["file"] == {"type": "string", "format": "binary"}
