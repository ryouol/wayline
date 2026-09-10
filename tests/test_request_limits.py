"""Exercise streamed bodies through FastAPI, including multipart spool cleanup."""

import asyncio
import json

import httpx2 as httpx
import pytest
import starlette.formparsers

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
