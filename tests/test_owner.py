from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from lingbot_map.workspace import identity
from lingbot_map.workspace.app import create_app
from lingbot_map.workspace.database import QuotaExceeded
from lingbot_map.workspace.identity import IdentityStore
from lingbot_map.workspace.service import WorkspaceService


@pytest.mark.parametrize(
    ("email", "verified", "expected"),
    [
        ("OWNER@example.test", True, "owner"),
        ("other@example.test", True, "google"),
        ("owner@example.test", False, "google"),
        ("owner@example.test", "true", "google"),
        ("", True, "google"),
    ],
)
def test_owner_requires_exact_verified_google_email(
    settings, monkeypatch, email, verified, expected
):
    settings = replace(
        settings,
        signup_enabled=True,
        owner_email="owner@example.test",
        google_client_id="client",
        google_client_secret="secret",
        public_base_url="http://testserver",
    )
    workspace = WorkspaceService(settings)
    workspace.initialize()
    identities = IdentityStore(workspace.database)
    prior = identities.create_workspace(
        subject="returning", name="Existing", guest=False, max_accounts=0, quota=240
    )
    tenant = prior["tenant_id"]
    old_session, _ = workspace.database.create_session(prior, 3600)
    with workspace.database.transaction() as connection:
        connection.execute(
            "UPDATE tenants SET successful_reconstructions=2,consumed_units=240 WHERE id=?",
            (tenant,),
        )
    claims = {
        "sub": "returning",
        "given_name": "Existing",
        "email": email,
        "email_verified": verified,
        "owner": True,
    }
    monkeypatch.setattr(identity, "exchange_google_code", lambda **kwargs: claims)
    with TestClient(create_app(settings, service=workspace, start_worker=False)) as browser:

        def login():
            start = browser.get("/auth/google/start", follow_redirects=False)
            state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
            response = browser.get(
                "/auth/google/callback",
                params={"state": state, "code": "test"},
                follow_redirects=False,
            )
            assert response.status_code == 303
            return browser.get("/api/me").json()

        me = login()
        assert me["user"]["accountType"] == expected
        assert me["quota"]["consumed_units"] == 240
        assert workspace.database.authenticate_session(old_session)["tenant_id"] == tenant
        assert "owner_email" not in browser.get("/api/config").json()
        if expected == "owner":
            assert me["reconstructionAllowance"] is None
            assert me["quota"]["available_units"] is None
            assert me["quota"]["storage_limit_bytes"] is None
            claims["email"] = "other@example.test"
            demoted = login()
            assert demoted["user"]["accountType"] == "google"
            assert demoted["reconstructionAllowance"]["remaining"] == 0
        else:
            assert me["reconstructionAllowance"]["remaining"] == 0


def test_owner_processing_and_inventory_are_unlimited_but_storage_safeguards_remain(service):
    db = service.database
    owner = IdentityStore(db).create_workspace(
        subject="owner", name="Owner", guest=False, max_accounts=0, quota=0, owner=True
    )
    tenant = owner["tenant_id"]
    with db.transaction() as connection:
        connection.execute(
            "UPDATE tenants SET storage_limit_bytes=0,asset_limit=0,"
            "unattached_asset_limit=0,job_limit=0,artifact_limit=0,share_limit=0 "
            "WHERE id=?",
            (tenant,),
        )
    asset = db.create_asset(
        tenant_id=tenant,
        object_key="owner-source",
        original_name="video.mp4",
        media_type="video/mp4",
        size_bytes=10,
        sha256="a" * 64,
        metadata={},
    )
    for index in range(4):
        job = db.create_job(
            tenant_id=tenant,
            engine_id="lingbot-research-v1",
            source_asset_id=asset["id"],
            params={},
            provenance={},
            reserve_units=120,
        )
        claim = db.claim_next_job(worker_id="owner-test", lease_seconds=30, max_attempts=1)
        artifact = db.create_artifact(
            tenant_id=tenant,
            job_id=job["id"],
            attempt_token=claim["attempt_token"],
            worker_id="owner-test",
            kind="scene",
            object_key=f"owner-scene-{index}",
            filename="scene.glb",
            media_type="model/gltf-binary",
            size_bytes=1,
            sha256="b" * 64,
            license_id="NOASSERTION",
            metadata={},
        )
        assert db.finish_job(
            tenant,
            job["id"],
            attempt_token=claim["attempt_token"],
            worker_id="owner-test",
            used_units=120,
        )
        db.create_share(
            tenant, artifact["id"], raw_token="a-test-share-token-" + str(index), ttl_seconds=3600
        )
    assert db.quota(tenant)["consumed_units"] == 480
    assert db.quota(tenant)["available_units"] is None
    assert db.reconstruction_allowance(tenant) is None
    with pytest.raises(QuotaExceeded, match="global storage"):
        db.claim_object(
            tenant, "too-large", ttl_seconds=60, reserve_bytes=20, global_storage_bytes=20
        )
    db.claim_object(tenant, "allowed", ttl_seconds=60, reserve_bytes=5, global_storage_bytes=20)
    db.size_object_claim(tenant, "allowed", 5)
    with pytest.raises(QuotaExceeded, match="pre-I/O"):
        db.size_object_claim(tenant, "allowed", 6)
    other = IdentityStore(db).create_workspace(
        subject="other", name="Other", guest=False, max_accounts=0, quota=240
    )
    with pytest.raises(KeyError):
        db.get_job(other["tenant_id"], job["id"])
    assert db.reconstruction_allowance(other["tenant_id"])["remaining"] == 2


def test_schema_six_migration_preserves_usage_without_granting_owner(service):
    db = service.database
    principal = IdentityStore(db).create_workspace(
        subject="existing", name="Existing", guest=False, max_accounts=0, quota=240
    )
    token, _ = db.create_session(principal, 3600)
    with db.transaction() as connection:
        connection.execute(
            "UPDATE tenants SET successful_reconstructions=2,consumed_units=90 WHERE id=?",
            (principal["tenant_id"],),
        )
        connection.execute("ALTER TABLE tenants DROP COLUMN is_owner")
        connection.execute("UPDATE schema_meta SET version=6")
    db.initialize()
    assert db.authenticate_session(token)
    assert IdentityStore(db).account_type(principal["user_id"]) == "google"
    assert db.reconstruction_allowance(principal["tenant_id"])["remaining"] == 0
    assert db.quota(principal["tenant_id"])["consumed_units"] == 90


@pytest.mark.parametrize("replacement", ["", "replacement@example.test"])
def test_changing_owner_configuration_revokes_existing_sessions_exemption(settings, replacement):
    settings = replace(settings, owner_email="owner@example.test")
    workspace = WorkspaceService(settings)
    workspace.initialize()
    identities = IdentityStore(workspace.database)
    principal = identities.create_workspace(
        subject="original-owner", name="Owner", guest=False, max_accounts=0, quota=240, owner=True
    )
    session, _ = workspace.database.create_session(principal, 3600)
    unchanged = WorkspaceService(replace(settings, owner_email="OWNER@EXAMPLE.TEST"))
    unchanged.initialize()
    assert IdentityStore(unchanged.database).account_type(principal["user_id"]) == "owner"
    changed = WorkspaceService(replace(settings, owner_email=replacement))
    changed.initialize()
    current = changed.database.authenticate_session(session)
    assert current is not None
    assert IdentityStore(changed.database).account_type(current["user_id"]) == "google"
    assert changed.database.reconstruction_allowance(current["tenant_id"])["remaining"] == 2
