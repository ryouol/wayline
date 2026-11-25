"""Public asset caching must invalidate on release without caching private data."""

import re
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from lingbot_map.workspace import app, pages

IMMUTABLE = "public, max-age=31536000, immutable"


def versioned(name, content):
    return f"/static/{name}?v={sha256(content).hexdigest()[:12]}"


@pytest.mark.parametrize("name", ["app.js", "styles.css", "landing-scene.glb", "icons/sun.svg"])
def test_versioned_public_assets_are_cacheable(client, name):
    content = (pages.STATIC / name).read_bytes()
    url = versioned(name, content)
    response = client.get(url)
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["cache-control"] == IMMUTABLE
    assert client.head(url).headers["cache-control"] == IMMUTABLE
    cached = client.get(url, headers={"If-None-Match": response.headers["etag"]})
    assert cached.status_code == 304
    assert cached.content == b""
    assert cached.headers["cache-control"] == IMMUTABLE
    partial = client.get(url, headers={"Range": "bytes=0-7"})
    assert partial.status_code == 206
    assert partial.content == content[:8]
    assert partial.headers["cache-control"] == IMMUTABLE


def test_unversioned_and_incorrect_versions_revalidate(client):
    correct = versioned("app.js", (pages.STATIC / "app.js").read_bytes())
    for url in ["/static/app.js", "/static/app.js?v=stale", correct + "&v=stale"]:
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
        cached = client.get(url, headers={"If-None-Match": response.headers["etag"]})
        assert cached.status_code == 304
        assert cached.headers["cache-control"] == "no-cache"
    missing = client.get("/static/missing.js?v=123456789abc")
    assert missing.status_code == 404
    assert "immutable" not in missing.headers.get("cache-control", "")


def test_html_revalidates_and_landing_scene_has_current_fingerprint(client):
    for url in ["/", "/privacy", "/terms", "/contact"]:
        response = client.get(url)
        assert response.headers["cache-control"] == "no-cache"
    for name in ["index.html", "share.html"]:
        response = client.get(versioned(name, (pages.STATIC / name).read_bytes()))
        assert response.headers["cache-control"] == "no-cache"
    expected = versioned("landing-scene.glb", (pages.STATIC / "landing-scene.glb").read_bytes())
    assert f'data-scene-url="{expected}"' in client.get("/").text


def test_release_changes_asset_url_and_does_not_cache_old_url_as_new_bytes(
    settings, service, tmp_path, monkeypatch
):
    static = tmp_path / "public"
    static.mkdir()
    (static / "index.html").write_text('<script src="/static/app.js"></script>')
    script = static / "app.js"
    script.write_bytes(b"old release")
    monkeypatch.setattr(app, "STATIC_DIR", static)
    monkeypatch.setattr(pages, "STATIC", static)
    with TestClient(app.create_app(settings, service=service, start_worker=False)) as client:
        old_url = re.search(r'src="([^"]+)"', client.get("/").text)[1]
        assert client.get(old_url).headers["cache-control"] == IMMUTABLE
        script.write_bytes(b"a new release")
        new_url = re.search(r'src="([^"]+)"', client.get("/").text)[1]
        assert new_url != old_url
        assert client.get(new_url).content == b"a new release"
        assert client.get(new_url).headers["cache-control"] == IMMUTABLE
        assert client.get(old_url).headers["cache-control"] == "no-cache"


def test_private_and_shared_routes_never_inherit_public_caching(authenticated_client, service):
    client = authenticated_client
    job = client.post("/api/jobs/sample").json()
    service.process_next_job()
    detail_url = f"/api/jobs/{job['id']}"
    artifact = next(
        item for item in client.get(detail_url).json()["artifacts"] if item["kind"] == "scene"
    )
    share = client.post(f"/api/artifacts/{artifact['id']}/shares", json={"ttlSeconds": 300})
    assert share.status_code == 201
    for url in ["/api/me", detail_url, artifact["viewUrl"], artifact["downloadUrl"], "/s"]:
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
    token = share.json()["url"].split("#", 1)[1]
    for url in ["/api/public/share", "/api/public/share/content"]:
        response = client.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
