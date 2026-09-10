"""Release-envelope, anonymous-access and privacy regression tests."""

from pathlib import Path

import pytest

from .conftest import BOOTSTRAP_TOKEN

JOB = "job_" + "a" * 32
ASSET = "ast_" + "a" * 32
ARTIFACT = "art_" + "a" * 32
SHARE = "shr_" + "a" * 32


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/api/me", None),
        ("DELETE", "/api/session", None),
        ("GET", "/api/engines", None),
        ("GET", "/api/assets", None),
        ("POST", "/api/assets", None),
        ("DELETE", f"/api/assets/{ASSET}", None),
        ("POST", "/api/jobs/sample", None),
        ("POST", "/api/jobs/research", {"assetId": ASSET}),
        ("GET", "/api/jobs", None),
        ("GET", f"/api/jobs/{JOB}", None),
        ("POST", f"/api/jobs/{JOB}/cancel", None),
        ("DELETE", f"/api/jobs/{JOB}", None),
        ("GET", f"/api/artifacts/{ARTIFACT}/content", None),
        ("GET", f"/api/artifacts/{ARTIFACT}/download", None),
        ("POST", f"/api/artifacts/{ARTIFACT}/shares", {"ttlSeconds": 300}),
        ("GET", "/api/shares", None),
        ("DELETE", f"/api/shares/{SHARE}", None),
        ("POST", "/api/bulk-delete", {"jobIds": [JOB]}),
    ],
)
def test_every_private_endpoint_rejects_anonymous(client, method, path, payload):
    response = client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_validation_never_echoes_workspace_token(client):
    secret = "short-secret"
    response = client.post("/api/session", json={"token": secret})
    assert response.status_code == 422
    assert secret not in response.text
    assert all("input" not in entry for entry in response.json()["detail"])


def test_login_normalizes_accidental_whitespace(client):
    assert client.post("/api/session", json={"token": f"  {BOOTSTRAP_TOKEN}\n"}).status_code == 200


def test_cross_site_logout_is_rejected(authenticated_client):
    response = authenticated_client.delete(
        "/api/session", headers={"Origin": "https://attacker.invalid"}
    )
    assert response.status_code == 403
    assert authenticated_client.get("/api/me").status_code == 200
    assert (
        authenticated_client.delete(
            "/api/session", headers={"Sec-Fetch-Site": "cross-site"}
        ).status_code
        == 403
    )
    assert (
        authenticated_client.delete(
            "/api/session", headers={"Origin": "http://testserver"}
        ).status_code
        == 204
    )


@pytest.mark.parametrize(
    "path,title",
    [
        ("/", "Wayline"),
        ("/privacy", "Privacy"),
        ("/terms", "Terms"),
        ("/contact", "Contact"),
    ],
)
def test_public_support_metadata_and_assets(client, path, title):
    response = client.get(path)
    assert response.status_code == 200
    assert title in response.text
    assert 'name="description"' in response.text
    assert 'property="og:image"' in response.text
    assert 'name="twitter:card"' in response.text
    assert 'rel="manifest"' in response.text
    assert 'src="/static/site.js?v=' in response.text
    assert response.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    for file in (
        "favicon.ico",
        "favicon-16.png",
        "favicon-32.png",
        "apple-touch-icon.png",
        "site.webmanifest",
        "icon-192.png",
        "icon-512.png",
        "social-preview.png",
    ):
        assert client.get(f"/static/{file}").status_code == 200


def test_private_workspace_is_not_enumerated_for_crawlers(client):
    assert "Disallow: /" in client.get("/robots.txt").text
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "<url>" not in sitemap.text
    assert "/s/" not in sitemap.text


def test_custom_not_found_preserves_api_json(client):
    browser = client.get("/missing-page", headers={"Accept": "text/html"})
    assert browser.status_code == 404
    assert "Page unavailable" in browser.text
    assert 'href="/"' in browser.text
    api = client.get("/api/missing-page", headers={"Accept": "text/html"})
    assert api.status_code == 404
    assert api.json() == {"detail": "Not Found"}


def test_errors_redact_capability_paths(client, caplog):
    def fail():
        raise RuntimeError("Synthetic regression failure")

    path = "/s/" + "a" * 32 + "/failure"
    client.app.add_api_route(path, fail)
    browser = client.get(path, headers={"Accept": "text/html"})
    assert browser.status_code == 500
    assert "Something went wrong" in browser.text
    assert "Synthetic regression failure" not in browser.text
    assert path not in caplog.text
    assert browser.headers["cache-control"] == "no-store"


def test_consent_is_fail_closed_and_never_tracks_share_paths():
    source = (Path(__file__).parents[1] / "lingbot_map/workspace/static/site.js").read_text()
    assert 'measurementId: "", endpoint: ""' in source
    assert 'readConsent() !== "accepted"' in source
    assert "endpoint.origin !== location.origin" in source
    assert 'credentials: "omit"' in source
    assert 'includes(path) ? path : "other"' in source
    assert ".innerHTML" not in source
