from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from lingbot_map.workspace import identity
from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.identity import IdentityStore


def test_trial_is_isolated_and_cannot_upload_or_spend(client, service):
    response = client.post("/api/trial")
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrfToken"]
    first = client.get("/api/me").json()
    assert first["user"]["accountType"] == "trial"
    created = client.post("/api/jobs/sample")
    assert created.status_code == 202
    assert service._worker_iteration()
    completed = client.get("/api/jobs/" + created.json()["id"]).json()
    assert completed["state"] == "ready"
    assert len(completed["artifacts"]) == 2
    assert (
        client.post(
            "/api/assets", files={"file": ("capture.mp4", b"video", "video/mp4")}
        ).status_code
        == 403
    )
    assert client.post("/api/jobs/research", json={"assetId": "ast_" + "a" * 32}).status_code == 403
    assert client.post("/api/trial").status_code == 409
    assert client.delete("/api/session").status_code == 204
    assert client.post("/api/trial").status_code == 200
    assert client.get("/api/jobs").json()["jobs"] == []


def test_trial_origin_and_limits(client, service, monkeypatch):
    assert (
        client.post("/api/trial", headers={"Origin": "https://attacker.example"}).status_code == 403
    )
    assert client.post("/api/trial", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    identities = IdentityStore(service.database)
    first = identities.create_workspace(
        subject="google-1", name="First", guest=False, max_accounts=1, quota=120
    )
    again = identities.create_workspace(
        subject="google-1", name="Changed", guest=False, max_accounts=1, quota=999
    )
    assert first == again
    assert service.database.quota(first["tenant_id"])["quota_units"] == 120
    import pytest

    with pytest.raises(ValueError, match="capacity"):
        identities.create_workspace(
            subject="google-2", name="Other", guest=False, max_accounts=1, quota=120
        )


def test_oauth_state_is_bound_single_use_and_expires(service):
    store = IdentityStore(service.database)
    state, nonce, verifier = store.begin("browser-one")
    assert store.consume(state, "browser-two") is None
    assert store.consume(state, "browser-one") == {"nonce": nonce, "verifier": verifier}
    assert store.consume(state, "browser-one") is None
    state, _, _ = store.begin("browser-one")
    with service.database.transaction() as connection:
        connection.execute("UPDATE oauth_attempts SET expires_at=0")
    assert store.consume(state, "browser-one") is None


def test_google_flow_provisions_once_and_blocks_replay(settings, monkeypatch):
    configured = replace(
        settings,
        signup_enabled=True,
        google_client_id="test-client",
        google_client_secret="test-secret",
        public_base_url="http://testserver",
    )
    claims = {"sub": "google-123", "given_name": "Ada"}
    exchanges = []

    def exchange(**values):
        exchanges.append(values)
        return claims

    monkeypatch.setattr(identity, "exchange_google_code", exchange)
    with TestClient(create_app(configured, start_worker=False)) as browser:
        assert browser.get("/api/config").json()["googleSignIn"] is True
        start = browser.get("/auth/google/start", follow_redirects=False)
        params = parse_qs(urlsplit(start.headers["location"]).query)
        assert params["code_challenge_method"] == ["S256"]
        assert params["scope"] == ["openid email profile"]
        assert "httponly" in start.headers["set-cookie"].lower()
        state = params["state"][0]
        done = browser.get(
            "/auth/google/callback",
            params={"state": state, "code": "one-use-code"},
            follow_redirects=False,
        )
        assert done.status_code == 303
        me = browser.get("/api/me").json()
        assert me["user"]["displayName"] == "Ada"
        assert me["quota"]["available_units"] == 120
        assert exchanges[0]["nonce"] == params["nonce"][0]
        assert len(exchanges[0]["verifier"]) >= 43
        assert (
            browser.get(
                "/auth/google/callback", params={"state": state, "code": "one-use-code"}
            ).status_code
            == 400
        )
        assert len(exchanges) == 1
        # Signing in again retains the same workspace instead of minting new free usage.
        start = browser.get("/auth/google/start", follow_redirects=False)
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        browser.get("/auth/google/callback", params={"state": state, "code": "second-code"})
        assert browser.get("/api/me").json()["quota"] == me["quota"]


def test_google_unconfigured_and_no_identity_leak(client):
    assert client.get("/api/config").json()["googleSignIn"] is False
    assert client.get("/auth/google/start").status_code == 503
    assert client.get("/api/me").status_code == 401


def test_expired_trial_releases_capacity_and_deletes_objects(client, service, tenant_id):
    response = client.post("/api/trial")
    client.headers["X-CSRF-Token"] = response.json()["csrfToken"]
    client.post("/api/jobs/sample")
    assert service.process_next_job()
    assert len(service.store.iter_keys("tenants")) == 2
    with service.database.transaction() as connection:
        connection.execute("UPDATE identities SET created_at=0 WHERE provider='trial'")
    assert service.run_retention()["expiredTrials"] == 1
    assert client.get("/api/me").status_code == 401
    service.drain_deletions()
    assert service.store.iter_keys("tenants") == []
    assert service.database.quota(tenant_id)
    assert client.post("/api/trial").status_code == 200


def test_expired_trial_cancels_work_before_removing_tenant(service):
    store = IdentityStore(service.database)
    principal = store.create_workspace(
        subject="old-trial", name="Explorer", guest=True, max_accounts=1, quota=1
    )
    job = service.submit_sample(principal["tenant_id"])
    with service.database.transaction() as connection:
        connection.execute("UPDATE identities SET created_at=0 WHERE provider='trial'")
        connection.execute("UPDATE jobs SET state='running' WHERE id=?", (job["id"],))
    assert store.expire_trials() == 0
    assert service.database.cancellation_requested(principal["tenant_id"], job["id"])
    with service.database.transaction() as connection:
        connection.execute("UPDATE jobs SET state='cancelled' WHERE id=?", (job["id"],))
    assert store.expire_trials() == 1


def test_oauth_pending_attempts_are_bounded(service, monkeypatch):
    import pytest

    monkeypatch.setattr(identity, "MAX_OAUTH_ATTEMPTS", 2)
    store = IdentityStore(service.database)
    store.begin("first-browser")
    state, _, _ = store.begin("second-browser")
    with pytest.raises(ValueError, match="Sign-in is busy"):
        store.begin("third-browser")
    assert store.consume(state, "second-browser")
    store.begin("third-browser")


def test_google_preview_limits_survive_scene_deletion(service):
    import pytest

    principal = IdentityStore(service.database).create_workspace(
        subject="preview-user", name="Explorer", guest=False, max_accounts=10, quota=120
    )
    tenant = principal["tenant_id"]

    def submit():
        return service.database.create_job(
            tenant_id=tenant,
            engine_id="lingbot-research-v1",
            source_asset_id=None,
            params={},
            provenance={},
            reserve_units=30,
        )

    first = submit()
    with pytest.raises(ValueError, match="already in progress"):
        submit()
    for job in [first, None, None]:
        current = job or submit()
        service.database.request_cancellation(tenant, current["id"])
        service.database.queue_delete_job(tenant, current["id"])
    with pytest.raises(ValueError, match="three reconstruction attempts"):
        submit()
    with service.database.transaction() as connection:
        connection.execute("UPDATE usage_ledger SET created_at=0 WHERE tenant_id=?", (tenant,))
    completed = submit()
    attempt = service.database.claim_next_job(
        worker_id="test-worker", lease_seconds=30, max_attempts=1
    )
    assert service.database.finish_job(
        tenant,
        completed["id"],
        attempt_token=attempt["attempt_token"],
        worker_id="test-worker",
        used_units=30,
    )
    service.database.queue_delete_job(tenant, completed["id"])
    with pytest.raises(ValueError, match="included reconstruction has been used"):
        submit()
