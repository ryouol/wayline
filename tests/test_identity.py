from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from fastapi.testclient import TestClient

from lingbot_map.workspace import identity
from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.identity import IdentityStore

from .test_workspace_api import fake_mp4


@pytest.mark.parametrize(
    "scenario",
    [
        "valid",
        "nonce",
        "unverified",
        "subject",
        "missing_token",
        "provider",
        "timeout",
        "signature",
        "certificate_timeout",
    ],
)
def test_google_exchange_validates_provider_response_and_identity(monkeypatch, scenario):
    claims = {"sub": "google-123", "nonce": "browser-nonce", "email_verified": True}
    if scenario == "nonce":
        claims["nonce"] = "another-browser"
    elif scenario == "unverified":
        claims["email_verified"] = "true"
    elif scenario == "subject":
        claims["sub"] = ""
    calls = []

    class ProviderSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append("closed")

        def post(self, url, *, data, timeout):
            assert url == "https://oauth2.googleapis.com/token"
            assert data["code_verifier"] == "pkce-verifier"
            assert data["redirect_uri"] == "https://wayline.example/auth/google/callback"
            assert timeout == 15
            if scenario == "timeout":
                raise requests.Timeout("provider timed out")
            return self

        status_code = 503 if scenario == "provider" else 200

        def json(self):
            return {} if scenario == "missing_token" else {"id_token": "signed-identity"}

    def verify(token, request, audience):
        assert token == "signed-identity"
        assert audience == "client-id"
        if scenario == "signature":
            raise ValueError("invalid signature")
        request(url="https://www.googleapis.com/oauth2/v1/certs", timeout=999)
        return claims

    def certificate_request(*, session):
        assert isinstance(session, ProviderSession)

        def request(*, url, timeout):
            assert url == "https://www.googleapis.com/oauth2/v1/certs"
            assert timeout == 15
            if scenario == "certificate_timeout":
                raise requests.Timeout("certificate fetch timed out")

        return request

    monkeypatch.setattr(identity.requests, "Session", ProviderSession)
    monkeypatch.setattr(identity, "verify_oauth2_token", verify)
    monkeypatch.setattr(identity, "GoogleRequest", certificate_request)

    def exchange():
        return identity.exchange_google_code(
            client_id="client-id",
            client_secret="client-secret",
            redirect_uri="https://wayline.example/auth/google/callback",
            code="one-use-code",
            verifier="pkce-verifier",
            nonce="browser-nonce",
        )

    if scenario == "valid":
        assert exchange() == claims
    else:
        with pytest.raises(
            requests.Timeout if scenario in {"timeout", "certificate_timeout"} else ValueError
        ):
            exchange()
    assert calls == ["closed"]


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
        signup_max_accounts=1,
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
        assert browser.get("/api/config").json()["newAccountsAvailable"] is True
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
        assert me["reconstructionAllowance"]["state"] == "available"
        config = browser.get("/api/config").json()
        assert config["googleSignIn"] is True and config["newAccountsAvailable"] is False
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
    assert client.get("/api/config").json()["newAccountsAvailable"] is False
    assert client.get("/auth/google/start").status_code == 503
    assert client.get("/api/me").status_code == 401


def test_full_signup_redirects_to_product_without_creating_an_identity(settings, monkeypatch):
    configured = replace(
        settings,
        signup_enabled=True,
        signup_max_accounts=1,
        google_client_id="test-client",
        google_client_secret="test-secret",
        public_base_url="http://testserver",
    )
    application = create_app(configured, start_worker=False)
    with TestClient(application) as browser:
        workspace = application.state.workspace
        identities = IdentityStore(workspace.database)
        identities.create_workspace(
            subject="existing-user", name="Existing", guest=False, max_accounts=1, quota=120
        )
        monkeypatch.setattr(
            identity, "exchange_google_code", lambda **_: {"sub": "new-user", "given_name": "New"}
        )
        start = browser.get("/auth/google/start", follow_redirects=False)
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        response = browser.get(
            "/auth/google/callback",
            params={"state": state, "code": "valid-new-account-code"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/?signin=capacity"
        assert "wayline_oauth_browser" not in browser.cookies
        assert browser.get("/api/me").status_code == 401
        assert browser.get(response.headers["location"]).status_code == 200
        with workspace.database.connect() as connection:
            assert connection.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM oauth_attempts").fetchone()[0] == 0
        # Full Google signup must not close the independent synthetic playground.
        assert browser.post("/api/trial").status_code == 200


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


def test_google_preview_limits_survive_scene_deletion(service, client, monkeypatch):
    import pytest

    principal = IdentityStore(service.database).create_workspace(
        subject="preview-user", name="Explorer", guest=False, max_accounts=10, quota=120
    )
    tenant = principal["tenant_id"]
    session, csrf = service.database.create_session(principal, 3600)
    client.cookies.set("scene_workspace_session", session)
    client.headers["X-CSRF-Token"] = csrf

    def check_allowance(expected):
        from starlette.requests import Request

        allowance = client.get("/api/me").json()["reconstructionAllowance"]
        assert allowance["state"] == expected
        if expected != "available":

            async def forbidden_parser(*args, **kwargs):
                pytest.fail("Blocked reconstruction must be rejected before spooling an upload")

            with monkeypatch.context() as patch:
                patch.setattr(Request, "form", forbidden_parser)
                response = client.post("/api/assets", content=b"must-not-be-spooled")
            assert response.status_code == 409
            assert response.json()["detail"] == allowance["message"]

    check_allowance("available")

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
    check_allowance("processing")
    with pytest.raises(ValueError, match="already in progress"):
        submit()
    for index, job in enumerate([first, None, None]):
        current = job or submit()
        if index == 1:
            attempt = service.database.claim_next_job(
                worker_id="test-worker", lease_seconds=30, max_attempts=1
            )
            service.database.fail_job(
                tenant,
                current["id"],
                attempt_token=attempt["attempt_token"],
                worker_id="test-worker",
                code="test_failure",
                message="Simulated reconstruction failure",
            )
        else:
            service.database.request_cancellation(tenant, current["id"])
        service.database.queue_delete_job(tenant, current["id"])
        if index < 2:
            check_allowance("available")
    check_allowance("retry_later")
    with pytest.raises(ValueError, match="three reconstruction attempts"):
        submit()
    with service.database.transaction() as connection:
        connection.execute("UPDATE usage_ledger SET created_at=0 WHERE tenant_id=?", (tenant,))
    check_allowance("available")
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
    check_allowance("used")
    with pytest.raises(ValueError, match="included reconstruction has been used"):
        submit()


def test_operator_does_not_receive_a_one_video_preview_allowance(authenticated_client):
    assert authenticated_client.get("/api/me").json()["reconstructionAllowance"] is None


@pytest.fixture
def google_upload(service, client):
    principal = IdentityStore(service.database).create_workspace(
        subject="upload-replay-user", name="Explorer", guest=False, max_accounts=10, quota=120
    )
    session, csrf = service.database.create_session(principal, 3600)
    client.cookies.set("scene_workspace_session", session)
    client.headers["X-CSRF-Token"] = csrf
    headers = {"Idempotency-Key": "google-upload-replay-key"}
    files = {"file": ("walkthrough.mp4", fake_mp4(), "video/mp4")}
    first = client.post("/api/assets", files=files, headers=headers)
    assert first.status_code == 201
    return principal["tenant_id"], headers, files, first.json()


def block_google_upload(service, tenant, asset_id, state="used"):
    for _ in range(3 if state == "retry_later" else 1):
        job = service.database.create_job(
            tenant_id=tenant,
            engine_id="lingbot-research-v1",
            source_asset_id=asset_id,
            params={},
            provenance={},
            reserve_units=30,
        )
        if state == "processing":
            break
        if state == "retry_later":
            service.database.request_cancellation(tenant, job["id"])
        else:
            attempt = service.database.claim_next_job(
                worker_id="upload-replay-worker", lease_seconds=30, max_attempts=1
            )
            service.database.finish_job(
                tenant,
                job["id"],
                attempt_token=attempt["attempt_token"],
                worker_id="upload-replay-worker",
                used_units=30,
            )
    assert service.database.reconstruction_allowance(tenant)["state"] == state


@pytest.mark.parametrize("state", ["processing", "used", "retry_later"])
def test_completed_upload_replays_after_allowance_changes(service, client, google_upload, state):
    tenant, headers, files, first = google_upload
    block_google_upload(service, tenant, first["id"], state)
    replay = client.post("/api/assets", files=files, headers=headers)
    assert replay.status_code == 201
    assert replay.json() == first
    conflict = client.post(
        "/api/assets",
        files={"file": ("walkthrough.mp4", fake_mp4(128), "video/mp4")},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    assert len(client.get("/api/assets").json()["assets"]) == 1
    assert len(list((service.settings.data_dir / "objects").rglob("*.mp4"))) == 1
    with service.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM object_claims").fetchone()[0] == 0


@pytest.mark.parametrize(
    "candidate", ["missing", "fresh", "expired", "wrong_scope", "wrong_tenant", "in_progress"]
)
def test_blocked_upload_only_parses_a_completed_replay_candidate(
    service, client, google_upload, tenant_id, monkeypatch, candidate
):
    from starlette.requests import Request

    tenant, headers, files, first = google_upload
    block_google_upload(service, tenant, first["id"])
    with service.database.transaction() as connection:
        if candidate == "expired":
            connection.execute(
                "UPDATE idempotency_keys SET expires_at=0 WHERE tenant_id=?", (tenant,)
            )
        elif candidate == "wrong_scope":
            connection.execute(
                "UPDATE idempotency_keys SET scope='POST:/api/jobs/sample' WHERE tenant_id=?",
                (tenant,),
            )
        elif candidate == "wrong_tenant":
            connection.execute(
                "UPDATE idempotency_keys SET tenant_id=? WHERE tenant_id=?", (tenant_id, tenant)
            )
        elif candidate == "in_progress":
            connection.execute(
                "UPDATE idempotency_keys SET state='in_progress' WHERE tenant_id=?", (tenant,)
            )
    if candidate == "missing":
        headers = {}
    elif candidate == "fresh":
        headers = {"Idempotency-Key": "unused-upload-key"}

    async def forbidden_parser(*args, **kwargs):
        pytest.fail("A blocked fresh upload must not reach the multipart parser")

    monkeypatch.setattr(Request, "form", forbidden_parser)
    response = client.post("/api/assets", files=files, headers=headers)
    assert response.status_code == 409
    assert "included reconstruction has been used" in response.json()["detail"]
    assert len(list((service.settings.data_dir / "objects").rglob("*.mp4"))) == 1


@pytest.mark.parametrize("race", ["allowance_used", "key_expired", "key_removed"])
def test_upload_admission_is_rechecked_before_creating_an_asset(
    service, client, google_upload, monkeypatch, race
):
    from starlette.requests import Request

    tenant, headers, files, first = google_upload
    if race == "allowance_used":
        headers = {"Idempotency-Key": "fresh-upload-racing-allowance"}
    else:
        block_google_upload(service, tenant, first["id"])
    original_form = Request.form

    async def change_state_after_admission(request, **kwargs):
        form = await original_form(request, **kwargs)
        if race == "allowance_used":
            block_google_upload(service, tenant, first["id"])
        else:
            with service.database.transaction() as connection:
                if race == "key_expired":
                    connection.execute(
                        "UPDATE idempotency_keys SET expires_at=0 WHERE tenant_id=?", (tenant,)
                    )
                else:
                    connection.execute("DELETE FROM idempotency_keys WHERE tenant_id=?", (tenant,))
        return form

    monkeypatch.setattr(Request, "form", change_state_after_admission)
    response = client.post("/api/assets", files=files, headers=headers)
    assert response.status_code == 409
    assert "included reconstruction has been used" in response.json()["detail"]
    assert len(client.get("/api/assets").json()["assets"]) == 1
    assert len(list((service.settings.data_dir / "objects").rglob("*.mp4"))) == 1
    with service.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM object_claims").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM idempotency_keys WHERE state='in_progress'"
            ).fetchone()[0]
            == 0
        )
