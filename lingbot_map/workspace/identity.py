"""Google identities and short-lived OAuth attempts; credentials stay server-side."""

from __future__ import annotations

import hashlib
import secrets
import time
from base64 import urlsafe_b64encode
from typing import Any
from urllib.parse import urlencode

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_oauth2_token

from .database import Database, QuotaExceeded, _id, token_digest

GOOGLE_ISSUER = "https://accounts.google.com"
TRIAL_TTL_SECONDS = 3600
MAX_OAUTH_ATTEMPTS = 1000


class IdentityStore:
    def __init__(self, database: Database):
        self.database = database

    def has_google_capacity(self, max_accounts: int) -> bool:
        if max_accounts == 0:
            return True
        with self.database.connect() as connection:
            return (
                connection.execute(
                    "SELECT COUNT(*) FROM identities WHERE provider='google'"
                ).fetchone()[0]
                < max_accounts
            )

    def create_workspace(
        self, *, subject: str, name: str, guest: bool, max_accounts: int, quota: int
    ) -> dict[str, Any]:
        """Link by Google's immutable subject, never by an email address."""
        provider = "trial" if guest else "google"
        now = time.time()
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT u.id AS user_id, u.tenant_id, u.display_name, t.name AS tenant_name "
                "FROM identities i JOIN users u ON u.id=i.user_id "
                "JOIN tenants t ON t.id=u.tenant_id WHERE i.provider=? AND i.subject=?",
                (provider, subject),
            ).fetchone()
            if row:
                return dict(row)
            if guest or max_accounts != 0:
                count = connection.execute(
                    "SELECT COUNT(*) FROM identities WHERE provider=?", (provider,)
                ).fetchone()[0]
                if count >= max_accounts:
                    raise QuotaExceeded("This beta is at capacity. Please try again later.")
            tenant_id, user_id = _id("ten"), _id("usr")
            display = name.strip()[:80] or "Explorer"
            tenant_name = "Sample playground" if guest else f"{display}'s spaces"
            connection.execute(
                "INSERT INTO tenants (id,name,quota_units,storage_limit_bytes,asset_limit,"
                "unattached_asset_limit,job_limit,artifact_limit,share_limit,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    tenant_id,
                    tenant_name,
                    1 if guest else quota,
                    5 * 1024 * 1024 if guest else 512 * 1024 * 1024,
                    0 if guest else 3,
                    0 if guest else 1,
                    3 if guest else 10,
                    9 if guest else 40,
                    0 if guest else 10,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO users VALUES (?,?,?,?)", (user_id, tenant_id, display, now)
            )
            connection.execute(
                "INSERT INTO identities(provider,subject,user_id,created_at) VALUES (?,?,?,?)",
                (provider, subject, user_id, now),
            )
            return {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "display_name": display,
                "tenant_name": tenant_name,
            }

    def account_type(self, user_id: str) -> str:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT provider FROM identities WHERE user_id=?", (user_id,)
            ).fetchone()
            return row[0] if row else "operator"

    def is_guest(self, user_id: str) -> bool:
        return self.account_type(user_id) == "trial"

    def expire_trials(self) -> int:
        """Retire expired playgrounds without racing an active artifact write."""
        removed = 0
        with self.database.transaction() as connection:
            tenants = connection.execute(
                "SELECT u.tenant_id FROM identities i JOIN users u ON u.id=i.user_id "
                "WHERE i.provider='trial' AND i.created_at<=? LIMIT 100",
                (time.time() - TRIAL_TTL_SECONDS,),
            ).fetchall()
            for tenant in tenants:
                tenant_id = tenant["tenant_id"]
                connection.execute("DELETE FROM sessions WHERE tenant_id=?", (tenant_id,))
                jobs = connection.execute(
                    "SELECT id,state FROM jobs WHERE tenant_id=?", (tenant_id,)
                ).fetchall()
                for job in jobs:
                    if job["state"] in {"queued", "running"}:
                        self.database.request_cancellation(
                            tenant_id, job["id"], connection=connection
                        )
                if (
                    any(job["state"] == "running" for job in jobs)
                    or connection.execute(
                        "SELECT 1 FROM object_claims WHERE tenant_id=? LIMIT 1", (tenant_id,)
                    ).fetchone()
                ):
                    continue
                for job in jobs:
                    self.database.queue_delete_job(tenant_id, job["id"], connection=connection)
                connection.execute("DELETE FROM idempotency_keys WHERE tenant_id=?", (tenant_id,))
                connection.execute("DELETE FROM tenants WHERE id=?", (tenant_id,))
                removed += 1
        return removed

    def begin(self, browser_token: str) -> tuple[str, str, str]:
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        now = time.time()
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM oauth_attempts WHERE expires_at<=?", (now,))
            if (
                connection.execute("SELECT COUNT(*) FROM oauth_attempts").fetchone()[0]
                >= MAX_OAUTH_ATTEMPTS
            ):
                raise QuotaExceeded("Sign-in is busy. Please try again in a few minutes.")
            connection.execute(
                "INSERT INTO oauth_attempts VALUES (?,?,?,?,?)",
                (token_digest(state), token_digest(browser_token), nonce, verifier, now + 600),
            )
        return state, nonce, verifier

    def consume(self, state: str, browser_token: str) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "DELETE FROM oauth_attempts WHERE state_hash=? AND browser_hash=? "
                "AND expires_at>? RETURNING nonce,verifier",
                (token_digest(state), token_digest(browser_token), time.time()),
            ).fetchone()
            return dict(row) if row else None


def authorization_url(
    client_id: str, redirect_uri: str, state: str, nonce: str, verifier: str
) -> str:
    challenge = urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return (
        GOOGLE_ISSUER
        + "/o/oauth2/v2/auth?"
        + urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
    )


def exchange_google_code(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    verifier: str,
    nonce: str,
) -> dict[str, Any]:
    with requests.Session() as session:
        response = session.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
            timeout=15,
        )
        if response.status_code != 200:
            raise ValueError("Google sign-in could not be completed. Please try again.")
        token = response.json().get("id_token")
        if not isinstance(token, str) or len(token) > 16_384:
            raise ValueError("Google did not return a valid identity token.")

        def bounded_request(*args, **kwargs):
            kwargs["timeout"] = 15
            return GoogleRequest(session=session)(*args, **kwargs)

        claims = verify_oauth2_token(token, bounded_request, client_id)
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise ValueError("Google sign-in did not match this browser session.")
    if claims.get("email_verified") is not True:
        raise ValueError("A verified Google account is required.")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
        raise ValueError("Google did not return a valid account identifier.")
    return claims
