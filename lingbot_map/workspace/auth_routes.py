"""Same-origin onboarding with private, separately provisioned workspaces."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from . import identity
from .config import Settings
from .database import QuotaExceeded
from .service import WorkspaceService

OAUTH_COOKIE = "wayline_oauth_browser"


def register_auth_routes(
    app: FastAPI, workspace: WorkspaceService, runtime: Settings, limiter, session_cookie: str
) -> None:
    identities = identity.IdentityStore(workspace.database)
    redirect_uri = runtime.public_base_url + "/auth/google/callback"

    def rate_limit(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(429, "Too many sign-in attempts. Please wait a minute.")

    def finish(principal: dict, request: Request, *, trial: bool = False):
        previous = request.cookies.get(session_cookie)
        old = workspace.database.authenticate_session(previous) if previous else None
        if old:
            workspace.database.delete_session(old["session_id"])
        ttl = (
            min(runtime.session_ttl_seconds, identity.TRIAL_TTL_SECONDS)
            if trial
            else runtime.session_ttl_seconds
        )
        session, csrf = workspace.database.create_session(principal, ttl)
        response = (
            JSONResponse(
                {
                    "csrfToken": csrf,
                    "user": {
                        "displayName": principal["display_name"],
                        "tenantName": principal["tenant_name"],
                        "accountType": "trial" if trial else "google",
                    },
                }
            )
            if trial
            else RedirectResponse("/", status_code=303)
        )
        response.set_cookie(
            session_cookie,
            session,
            httponly=True,
            secure=runtime.cookie_secure,
            samesite="strict",
            max_age=ttl,
            path="/",
        )
        response.delete_cookie(
            OAUTH_COOKIE,
            path="/auth/google",
            secure=runtime.cookie_secure,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get("/api/config")
    def public_config():
        return {
            "name": "Wayline",
            "googleSignIn": runtime.signup_enabled,
            "newAccountsAvailable": runtime.signup_enabled
            and identities.has_google_capacity(runtime.signup_max_accounts),
            "trialEnabled": runtime.trial_enabled,
            "maxUploadBytes": runtime.max_upload_bytes,
            "maxVideoSeconds": runtime.max_video_seconds,
            "analytics": (
                {"propertyId": runtime.analytics_property_id, "endpoint": "/analytics/page-view"}
                if runtime.analytics_enabled
                else None
            ),
        }

    @app.post("/api/trial")
    def trial(request: Request):
        if not runtime.trial_enabled:
            raise HTTPException(404, "The sample playground is unavailable.")
        expected = runtime.public_base_url or str(request.base_url).rstrip("/")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            request.headers.get("origin") not in (None, expected)
        ):
            raise HTTPException(403, "Open Wayline to start a sample session.")
        rate_limit(request)
        current_token = request.cookies.get(session_cookie)
        current = workspace.database.authenticate_session(current_token) if current_token else None
        if current:
            raise HTTPException(409, "You are already signed in. Open your workspace.")
        principal = identities.create_workspace(
            subject=secrets.token_urlsafe(32),
            name="Explorer",
            guest=True,
            max_accounts=runtime.trial_max_accounts,
            quota=1,
        )
        return finish(principal, request, trial=True)

    @app.get("/auth/google/start")
    def google_start(request: Request):
        if not runtime.signup_enabled:
            raise HTTPException(503, "Google sign-in is not configured for this deployment yet.")
        rate_limit(request)
        browser_token = secrets.token_urlsafe(32)
        state, nonce, verifier = identities.begin(browser_token)
        response = RedirectResponse(
            identity.authorization_url(
                runtime.google_client_id, redirect_uri, state, nonce, verifier
            ),
            status_code=303,
        )
        response.set_cookie(
            OAUTH_COOKIE,
            browser_token,
            max_age=600,
            httponly=True,
            secure=runtime.cookie_secure,
            samesite="lax",
            path="/auth/google",
        )
        return response

    @app.get("/auth/google/callback")
    def google_callback(
        request: Request,
        state: Annotated[str, Query(min_length=16, max_length=128)],
        code: Annotated[str | None, Query(max_length=4096)] = None,
        error: Annotated[str | None, Query(max_length=128)] = None,
    ):
        if not runtime.signup_enabled:
            raise HTTPException(503, "Google sign-in is unavailable.")
        rate_limit(request)
        attempt = identities.consume(state, request.cookies.get(OAUTH_COOKIE, ""))
        if not attempt:
            raise HTTPException(
                400, "This sign-in expired or belongs to another browser. Try again."
            )
        if error or not code:
            return RedirectResponse("/?signin=cancelled", status_code=303)
        try:
            claims = identity.exchange_google_code(
                client_id=runtime.google_client_id,
                client_secret=runtime.google_client_secret,
                redirect_uri=redirect_uri,
                code=code,
                verifier=attempt["verifier"],
                nonce=attempt["nonce"],
            )
        except Exception:
            # Provider responses can contain credentials. Never log or return them.
            raise HTTPException(401, "Google sign-in failed. Please start again.") from None
        try:
            principal = identities.create_workspace(
                subject=claims["sub"],
                name=str(claims.get("given_name") or "Explorer"),
                guest=False,
                max_accounts=runtime.signup_max_accounts,
                quota=runtime.signup_quota_units,
            )
        except QuotaExceeded:
            response = RedirectResponse("/?signin=capacity", status_code=303)
            response.delete_cookie(
                OAUTH_COOKIE,
                path="/auth/google",
                secure=runtime.cookie_secure,
                httponly=True,
                samesite="lax",
            )
            return response
        return finish(principal, request)
