"""Small SQLite repository with explicit tenant and job invariants."""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import sqlite3
import time
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class QuotaExceeded(ValueError):
    pass


class InvalidTransition(RuntimeError):
    pass


class StaleAttempt(InvalidTransition):
    pass


class RateLimitExceeded(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


class IdempotencyInProgress(RuntimeError):
    pass


def encode_cursor(created_at: float, item_id: str) -> str:
    payload = json.dumps([created_at, item_id], separators=(",", ":")).encode("utf-8")
    return urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(value: str) -> tuple[float, str]:
    try:
        payload = value + "=" * (-len(value) % 4)
        created_at, item_id = json.loads(urlsafe_b64decode(payload).decode("utf-8"))
        if (
            not isinstance(created_at, (int, float))
            or isinstance(created_at, bool)
            or not math.isfinite(float(created_at))
            or float(created_at) < 0
            or not isinstance(item_id, str)
            or not 1 <= len(item_id) <= 128
        ):
            raise ValueError
        return float(created_at), item_id
    except Exception as error:
        raise ValueError("invalid pagination cursor") from error


class Database:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        for candidate in (
            self.path,
            Path(f"{self.path}-wal"),
            Path(f"{self.path}-shm"),
        ):
            if candidate.exists():
                os.chmod(candidate, 0o600)
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    @contextmanager
    def transaction_or(
        self, connection: sqlite3.Connection | None = None
    ) -> Iterator[sqlite3.Connection]:
        """Join a caller-owned transaction or open one for a standalone operation."""

        if connection is not None:
            yield connection
            return
        with self.transaction() as owned:
            yield owned

    def initialize(self) -> None:
        existing_version: int | None = None
        if self.path.exists():
            # Inspect compatibility through a read-only handle before connect()
            # can enable WAL or create sidecars. An older binary must leave a
            # future database byte-for-byte untouched.
            with sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True) as inspection:
                schema_table = inspection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_meta'"
                ).fetchone()
                version_row = (
                    inspection.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
                    if schema_table
                    else None
                )
                existing_version = int(version_row[0]) if version_row is not None else None
        if existing_version is not None and existing_version not in {1, 2, SCHEMA_VERSION}:
            raise RuntimeError(
                f"database schema {existing_version} is unsupported; expected {SCHEMA_VERSION}"
            )

        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    quota_units INTEGER NOT NULL CHECK (quota_units >= 0),
                    reserved_units INTEGER NOT NULL DEFAULT 0 CHECK (reserved_units >= 0),
                    consumed_units INTEGER NOT NULL DEFAULT 0 CHECK (consumed_units >= 0),
                    storage_limit_bytes INTEGER NOT NULL DEFAULT 5368709120,
                    asset_limit INTEGER NOT NULL DEFAULT 100,
                    unattached_asset_limit INTEGER NOT NULL DEFAULT 10,
                    job_limit INTEGER NOT NULL DEFAULT 500,
                    artifact_limit INTEGER NOT NULL DEFAULT 1500,
                    share_limit INTEGER NOT NULL DEFAULT 250,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    display_name TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS api_tokens (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL,
                    revoked_at REAL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL UNIQUE,
                    csrf_hash TEXT NOT NULL,
                    csrf_token TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    object_key TEXT NOT NULL UNIQUE,
                    original_name TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                    sha256 TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    source_asset_id TEXT REFERENCES assets(id) ON DELETE RESTRICT,
                    engine_id TEXT NOT NULL,
                    state TEXT NOT NULL
                        CHECK (state IN ('queued','running','ready','failed','cancelled')),
                    stage TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 1),
                    params_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    reserved_units INTEGER NOT NULL CHECK (reserved_units >= 0),
                    used_units INTEGER NOT NULL DEFAULT 0 CHECK (used_units >= 0),
                    cancellation_requested INTEGER NOT NULL DEFAULT 0,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    attempt_token TEXT,
                    worker_id TEXT,
                    lease_expires_at REAL,
                    error_code TEXT,
                    error_message TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_tenant_created
                    ON jobs(tenant_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(state, created_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_source_asset
                    ON jobs(tenant_id, source_asset_id);
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    object_key TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                    sha256 TEXT NOT NULL,
                    license_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    attempt_token TEXT NOT NULL DEFAULT 'legacy',
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_artifacts_job ON artifacts(job_id);
                CREATE TABLE IF NOT EXISTS shares (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at REAL NOT NULL,
                    revoked_at REAL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usage_ledger (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
                    event TEXT NOT NULL,
                    units INTEGER NOT NULL,
                    note TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS deletion_outbox (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    object_key TEXT NOT NULL UNIQUE,
                    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at REAL NOT NULL,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_deletion_due
                    ON deletion_outbox(next_attempt_at, created_at);
                CREATE TABLE IF NOT EXISTS object_claims (
                    object_key TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
                    materialized INTEGER NOT NULL DEFAULT 0
                        CHECK (materialized IN (0,1)),
                    purpose TEXT NOT NULL DEFAULT 'legacy'
                        CHECK (purpose IN ('upload','artifact','legacy')),
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_object_claim_expiry
                    ON object_claims(expires_at);
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    tenant_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('in_progress','complete')),
                    status_code INTEGER,
                    response_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (tenant_id, scope, key_hash)
                );
                CREATE INDEX IF NOT EXISTS idx_idempotency_expiry
                    ON idempotency_keys(expires_at);
                CREATE TABLE IF NOT EXISTS rate_buckets (
                    tenant_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    bucket_start INTEGER NOT NULL,
                    count INTEGER NOT NULL CHECK (count >= 0),
                    PRIMARY KEY (tenant_id, scope, bucket_start)
                );
                """
            )
            if existing_version is None:
                connection.execute("INSERT INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
            elif existing_version < SCHEMA_VERSION:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    if existing_version == 1:
                        migrations = (
                            "ALTER TABLE tenants ADD COLUMN storage_limit_bytes "
                            "INTEGER NOT NULL DEFAULT 5368709120",
                            "ALTER TABLE tenants ADD COLUMN asset_limit "
                            "INTEGER NOT NULL DEFAULT 100",
                            "ALTER TABLE tenants ADD COLUMN unattached_asset_limit "
                            "INTEGER NOT NULL DEFAULT 10",
                            "ALTER TABLE tenants ADD COLUMN job_limit INTEGER NOT NULL DEFAULT 500",
                            "ALTER TABLE tenants ADD COLUMN artifact_limit "
                            "INTEGER NOT NULL DEFAULT 1500",
                            "ALTER TABLE tenants ADD COLUMN share_limit "
                            "INTEGER NOT NULL DEFAULT 250",
                            "ALTER TABLE jobs ADD COLUMN attempt_token TEXT",
                            "ALTER TABLE jobs ADD COLUMN worker_id TEXT",
                            "ALTER TABLE artifacts ADD COLUMN attempt_token "
                            "TEXT NOT NULL DEFAULT 'legacy'",
                        )
                        for statement in migrations:
                            connection.execute(statement)
                    session_columns = {
                        row[1] for row in connection.execute("PRAGMA table_info(sessions)")
                    }
                    if "csrf_token" not in session_columns:
                        connection.execute(
                            "ALTER TABLE sessions ADD COLUMN csrf_token TEXT NOT NULL DEFAULT ''"
                        )
                        # Legacy sessions retained only the token hash, so they
                        # cannot safely recover a stable browser CSRF value.
                        connection.execute("DELETE FROM sessions")
                    claim_columns = {
                        row[1] for row in connection.execute("PRAGMA table_info(object_claims)")
                    }
                    if "materialized" not in claim_columns:
                        connection.execute(
                            "ALTER TABLE object_claims ADD COLUMN materialized "
                            "INTEGER NOT NULL DEFAULT 0"
                        )
                    if "purpose" not in claim_columns:
                        connection.execute(
                            "ALTER TABLE object_claims ADD COLUMN purpose "
                            "TEXT NOT NULL DEFAULT 'legacy'"
                        )
                    connection.execute("UPDATE schema_meta SET version = ?", (SCHEMA_VERSION,))
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise

    def bootstrap(
        self,
        *,
        token: str,
        tenant_name: str,
        quota_units: int,
        storage_limit_bytes: int = 5 * 1024 * 1024 * 1024,
        asset_limit: int = 100,
        unattached_asset_limit: int = 10,
        job_limit: int = 500,
        artifact_limit: int = 1_500,
        share_limit: int = 250,
    ) -> dict[str, str]:
        digest = token_digest(token)
        now = time.time()
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT tenant_id,user_id,revoked_at FROM api_tokens WHERE token_hash=?",
                (digest,),
            ).fetchone()
            if existing:
                if existing["revoked_at"] is not None:
                    raise RuntimeError(
                        "the configured bootstrap token was previously revoked; provision a new one"
                    )
                connection.execute(
                    """
                    UPDATE tenants SET quota_units=?,storage_limit_bytes=?,asset_limit=?,
                        unattached_asset_limit=?,job_limit=?,artifact_limit=?,share_limit=?
                    WHERE id=?
                    """,
                    (
                        quota_units,
                        storage_limit_bytes,
                        asset_limit,
                        unattached_asset_limit,
                        job_limit,
                        artifact_limit,
                        share_limit,
                        existing["tenant_id"],
                    ),
                )
                return {"tenant_id": existing["tenant_id"], "user_id": existing["user_id"]}
            tenant = connection.execute(
                "SELECT id FROM tenants ORDER BY created_at LIMIT 1"
            ).fetchone()
            if tenant:
                tenant_id = tenant["id"]
                user = connection.execute(
                    "SELECT id FROM users WHERE tenant_id = ? ORDER BY created_at LIMIT 1",
                    (tenant_id,),
                ).fetchone()
                if not user:
                    raise RuntimeError("bootstrap tenant has no user")
                user_id = user["id"]
            else:
                tenant_id, user_id = _id("ten"), _id("usr")
                connection.execute(
                    """
                    INSERT INTO tenants (
                        id, name, quota_units, reserved_units, consumed_units,
                        storage_limit_bytes, asset_limit, unattached_asset_limit,
                        job_limit, artifact_limit, share_limit, created_at
                    ) VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tenant_id,
                        tenant_name,
                        quota_units,
                        storage_limit_bytes,
                        asset_limit,
                        unattached_asset_limit,
                        job_limit,
                        artifact_limit,
                        share_limit,
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?)",
                    (user_id, tenant_id, "Workspace owner", now),
                )
            # Treat a changed bootstrap secret as a rotation: previous bootstrap
            # credentials and browser sessions stop working immediately.
            connection.execute(
                """
                UPDATE api_tokens SET revoked_at = ?
                WHERE tenant_id = ? AND name = 'bootstrap' AND revoked_at IS NULL
                """,
                (now, tenant_id),
            )
            connection.execute("DELETE FROM sessions WHERE tenant_id = ?", (tenant_id,))
            connection.execute(
                """
                UPDATE tenants SET quota_units=?, storage_limit_bytes=?, asset_limit=?,
                    unattached_asset_limit=?, job_limit=?, artifact_limit=?, share_limit=?
                WHERE id=?
                """,
                (
                    quota_units,
                    storage_limit_bytes,
                    asset_limit,
                    unattached_asset_limit,
                    job_limit,
                    artifact_limit,
                    share_limit,
                    tenant_id,
                ),
            )
            connection.execute(
                "INSERT INTO api_tokens VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (_id("key"), tenant_id, user_id, "bootstrap", digest, now),
            )
        return {"tenant_id": tenant_id, "user_id": user_id}

    def provision_tenant(
        self,
        *,
        token: str,
        tenant_name: str,
        quota_units: int,
        storage_limit_bytes: int = 5 * 1024 * 1024 * 1024,
        asset_limit: int = 100,
        unattached_asset_limit: int = 10,
        job_limit: int = 500,
        artifact_limit: int = 1_500,
        share_limit: int = 250,
    ) -> dict[str, str]:
        """Create a distinct tenant for an operator-managed high-entropy token."""

        digest = token_digest(token)
        now = time.time()
        tenant_id, user_id = _id("ten"), _id("usr")
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO tenants (
                    id, name, quota_units, reserved_units, consumed_units,
                    storage_limit_bytes, asset_limit, unattached_asset_limit,
                    job_limit, artifact_limit, share_limit, created_at
                ) VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    tenant_name,
                    quota_units,
                    storage_limit_bytes,
                    asset_limit,
                    unattached_asset_limit,
                    job_limit,
                    artifact_limit,
                    share_limit,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?)",
                (user_id, tenant_id, "Workspace owner", now),
            )
            connection.execute(
                "INSERT INTO api_tokens VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (_id("key"), tenant_id, user_id, "provisioned", digest, now),
            )
        return {"tenant_id": tenant_id, "user_id": user_id}

    def authenticate_api_token(self, token: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            return _row(
                connection.execute(
                    """
                    SELECT t.tenant_id, t.user_id, u.display_name, n.name AS tenant_name
                    FROM api_tokens t
                    JOIN users u ON u.id = t.user_id
                    JOIN tenants n ON n.id = t.tenant_id
                    WHERE t.token_hash = ? AND t.revoked_at IS NULL
                    """,
                    (token_digest(token),),
                ).fetchone()
            )

    def create_session(self, principal: dict[str, Any], ttl_seconds: int) -> tuple[str, str]:
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        now = time.time()
        with self.transaction() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            stale = connection.execute(
                """
                SELECT id FROM sessions WHERE user_id = ?
                ORDER BY created_at DESC LIMIT -1 OFFSET 19
                """,
                (principal["user_id"],),
            ).fetchall()
            if stale:
                connection.executemany("DELETE FROM sessions WHERE id = ?", stale)
            connection.execute(
                """
                INSERT INTO sessions(
                    id,tenant_id,user_id,token_hash,csrf_hash,csrf_token,expires_at,created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _id("ses"),
                    principal["tenant_id"],
                    principal["user_id"],
                    token_digest(session_token),
                    token_digest(csrf_token),
                    csrf_token,
                    now + ttl_seconds,
                    now,
                ),
            )
        return session_token, csrf_token

    def authenticate_session(self, token: str) -> dict[str, Any] | None:
        now = time.time()
        with self.connect() as connection:
            return _row(
                connection.execute(
                    """
                    SELECT s.id AS session_id, s.tenant_id, s.user_id, s.csrf_hash,
                           s.csrf_token,
                           u.display_name, n.name AS tenant_name
                    FROM sessions s
                    JOIN users u ON u.id = s.user_id
                    JOIN tenants n ON n.id = s.tenant_id
                    WHERE s.token_hash = ? AND s.expires_at > ?
                    """,
                    (token_digest(token), now),
                ).fetchone()
            )

    def delete_session(self, session_id: str) -> None:
        with self.transaction() as connection:
            connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def session_csrf(self, session_id: str) -> str:
        """Return the stable per-session CSRF value without invalidating peer tabs."""

        with self.connect() as connection:
            row = connection.execute(
                "SELECT csrf_token FROM sessions WHERE id=? AND expires_at>?",
                (session_id, time.time()),
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return str(row["csrf_token"])

    def quota(self, tenant_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
            usage = self._resource_usage(connection, tenant_id)
        if row is None:
            raise KeyError(tenant_id)
        result = {key: row[key] for key in ("quota_units", "reserved_units", "consumed_units")}
        result["available_units"] = (
            result["quota_units"] - result["reserved_units"] - result["consumed_units"]
        )
        result.update(usage)
        result.update(
            {
                "storage_limit_bytes": row["storage_limit_bytes"],
                "asset_limit": row["asset_limit"],
                "unattached_asset_limit": row["unattached_asset_limit"],
                "job_limit": row["job_limit"],
                "artifact_limit": row["artifact_limit"],
                "share_limit": row["share_limit"],
            }
        )
        return result

    @staticmethod
    def _resource_usage(connection: sqlite3.Connection, tenant_id: str) -> dict[str, int]:
        row = connection.execute(
            """
            SELECT
                (SELECT COALESCE(SUM(size_bytes), 0) FROM assets WHERE tenant_id=?) +
                (SELECT COALESCE(SUM(size_bytes), 0) FROM artifacts WHERE tenant_id=?) +
                (SELECT COALESCE(SUM(size_bytes), 0) FROM deletion_outbox WHERE tenant_id=?) +
                (SELECT COALESCE(SUM(size_bytes), 0) FROM object_claims WHERE tenant_id=?)
                    AS stored_bytes,
                (SELECT COUNT(*) FROM assets WHERE tenant_id=?) AS asset_count,
                (SELECT COUNT(*) FROM assets a WHERE a.tenant_id=? AND NOT EXISTS (
                    SELECT 1 FROM jobs j WHERE j.source_asset_id=a.id
                )) AS unattached_asset_count,
                (SELECT COUNT(*) FROM jobs WHERE tenant_id=?) AS job_count,
                (SELECT COUNT(*) FROM artifacts WHERE tenant_id=?) AS artifact_count,
                (SELECT COUNT(*) FROM shares WHERE tenant_id=? AND revoked_at IS NULL
                    AND expires_at>?) AS share_count
            """,
            (tenant_id,) * 9 + (time.time(),),
        ).fetchone()
        # sqlite3.Row iterates values, so its mapping-specific keys() API is required.
        return {key: int(row[key]) for key in row.keys()}  # noqa: SIM118

    @staticmethod
    def _tenant(connection: sqlite3.Connection, tenant_id: str) -> sqlite3.Row:
        tenant = connection.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
        if tenant is None:
            raise KeyError(tenant_id)
        return tenant

    @staticmethod
    def _consume_rate(
        connection: sqlite3.Connection,
        tenant_id: str,
        scope: str,
        *,
        limit: int | None,
        window_seconds: int,
        now: float,
    ) -> None:
        if limit is None:
            return
        bucket = int(now // window_seconds) * window_seconds
        row = connection.execute(
            "SELECT count FROM rate_buckets WHERE tenant_id=? AND scope=? AND bucket_start=?",
            (tenant_id, scope, bucket),
        ).fetchone()
        count = int(row[0]) if row else 0
        if count >= limit:
            raise RateLimitExceeded(f"{scope} rate limit exceeded; retry later")
        connection.execute(
            """
            INSERT INTO rate_buckets(tenant_id,scope,bucket_start,count) VALUES(?,?,?,1)
            ON CONFLICT(tenant_id,scope,bucket_start) DO UPDATE SET count=count+1
            """,
            (tenant_id, scope, bucket),
        )
        connection.execute(
            "DELETE FROM rate_buckets WHERE tenant_id=? AND bucket_start<?",
            (tenant_id, bucket - 2 * window_seconds),
        )

    def consume_rate(
        self,
        tenant_id: str,
        scope: str,
        *,
        limit: int | None,
        window_seconds: int = 60,
    ) -> None:
        """Durably count an accepted request start before expensive processing."""

        with self.transaction() as connection:
            self._tenant(connection, tenant_id)
            self._consume_rate(
                connection,
                tenant_id,
                scope,
                limit=limit,
                window_seconds=window_seconds,
                now=time.time(),
            )

    def create_asset(
        self,
        *,
        tenant_id: str,
        object_key: str,
        original_name: str,
        media_type: str,
        size_bytes: int,
        sha256: str,
        metadata: dict[str, Any],
        rate_limit: int | None = None,
        rate_window_seconds: int = 60,
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        asset_id, now = _id("ast"), time.time()
        with self.transaction_or(connection) as active:
            tenant = self._tenant(active, tenant_id)
            usage = self._resource_usage(active, tenant_id)
            claim = active.execute(
                "SELECT size_bytes FROM object_claims WHERE object_key=? AND tenant_id=?",
                (object_key, tenant_id),
            ).fetchone()
            claimed_bytes = int(claim["size_bytes"]) if claim else 0
            if usage["stored_bytes"] - claimed_bytes + size_bytes > tenant["storage_limit_bytes"]:
                raise QuotaExceeded("tenant storage byte limit exceeded")
            if usage["asset_count"] >= tenant["asset_limit"]:
                raise QuotaExceeded("tenant asset count limit exceeded")
            if usage["unattached_asset_count"] >= tenant["unattached_asset_limit"]:
                raise QuotaExceeded("delete or use an unattached upload before adding another")
            self._consume_rate(
                active,
                tenant_id,
                "upload",
                limit=rate_limit,
                window_seconds=rate_window_seconds,
                now=now,
            )
            active.execute(
                """
                INSERT INTO assets(
                    id,tenant_id,object_key,original_name,media_type,size_bytes,
                    sha256,metadata_json,created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    tenant_id,
                    object_key,
                    original_name,
                    media_type,
                    size_bytes,
                    sha256,
                    json.dumps(metadata, separators=(",", ":"), sort_keys=True),
                    now,
                ),
            )
            active.execute(
                "DELETE FROM object_claims WHERE object_key=? AND tenant_id=?",
                (object_key, tenant_id),
            )
            return self._get_asset(active, tenant_id, asset_id)

    @staticmethod
    def _get_asset(connection: sqlite3.Connection, tenant_id: str, asset_id: str) -> dict[str, Any]:
        result = _row(
            connection.execute(
                """
                SELECT a.*,(SELECT COUNT(*) FROM jobs j
                    WHERE j.source_asset_id=a.id AND j.tenant_id=a.tenant_id
                ) AS linked_job_count
                FROM assets a WHERE a.id=? AND a.tenant_id=?
                """,
                (asset_id, tenant_id),
            ).fetchone()
        )
        if result is None:
            raise KeyError(asset_id)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def get_asset(self, tenant_id: str, asset_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            return self._get_asset(connection, tenant_id, asset_id)

    def existing_asset_ids(
        self,
        tenant_id: str,
        asset_ids: list[str],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> set[str]:
        """Return the tenant-owned IDs that exist in the caller's transaction snapshot."""

        if not asset_ids:
            return set()
        placeholders = ",".join("?" for _ in asset_ids)
        with self.transaction_or(connection) as active:
            rows = active.execute(
                f"SELECT id FROM assets WHERE tenant_id=? AND id IN ({placeholders})",
                [tenant_id, *asset_ids],
            ).fetchall()
        return {str(row["id"]) for row in rows}

    def page_assets(
        self, tenant_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        limit = min(100, max(1, limit))
        parameters: list[Any] = [tenant_id]
        predicate = "a.tenant_id=?"
        if cursor:
            created_at, item_id = decode_cursor(cursor)
            predicate += " AND (a.created_at<? OR (a.created_at=? AND a.id<?))"
            parameters.extend([created_at, created_at, item_id])
        parameters.append(limit + 1)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT a.*,(SELECT COUNT(*) FROM jobs j
                    WHERE j.source_asset_id=a.id AND j.tenant_id=a.tenant_id
                ) AS linked_job_count
                FROM assets a WHERE {predicate}
                ORDER BY a.created_at DESC,a.id DESC LIMIT ?""",
                parameters,
            ).fetchall()
        more = len(rows) > limit
        values = []
        for row in rows[:limit]:
            value = dict(row)
            value["metadata"] = json.loads(value.pop("metadata_json"))
            values.append(value)
        next_cursor = (
            encode_cursor(values[-1]["created_at"], values[-1]["id"]) if more and values else None
        )
        return values, next_cursor

    def create_job(
        self,
        *,
        tenant_id: str,
        engine_id: str,
        source_asset_id: str | None,
        params: dict[str, Any],
        provenance: dict[str, Any],
        reserve_units: int,
        rate_limit: int | None = None,
        rate_window_seconds: int = 60,
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        job_id, now = _id("job"), time.time()
        with self.transaction_or(connection) as active:
            tenant = active.execute(
                "SELECT quota_units, reserved_units, consumed_units FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
            if tenant is None:
                raise KeyError(tenant_id)
            limits = active.execute(
                "SELECT job_limit FROM tenants WHERE id=?", (tenant_id,)
            ).fetchone()
            usage = self._resource_usage(active, tenant_id)
            if usage["job_count"] >= limits["job_limit"]:
                raise QuotaExceeded("tenant job count limit exceeded; delete retained jobs")
            self._consume_rate(
                active,
                tenant_id,
                "job",
                limit=rate_limit,
                window_seconds=rate_window_seconds,
                now=now,
            )
            available = tenant["quota_units"] - tenant["reserved_units"] - tenant["consumed_units"]
            if reserve_units > available:
                raise QuotaExceeded(f"job needs {reserve_units} units; {available} remain")
            if source_asset_id:
                source = active.execute(
                    "SELECT id FROM assets WHERE id = ? AND tenant_id = ?",
                    (source_asset_id, tenant_id),
                ).fetchone()
                if source is None:
                    raise KeyError(source_asset_id)
            active.execute(
                "UPDATE tenants SET reserved_units = reserved_units + ? WHERE id = ?",
                (reserve_units, tenant_id),
            )
            active.execute(
                """
                INSERT INTO jobs (
                    id, tenant_id, source_asset_id, engine_id, state, stage, progress,
                    params_json, provenance_json, reserved_units, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'queued', 'queued', 0, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    tenant_id,
                    source_asset_id,
                    engine_id,
                    json.dumps(params, separators=(",", ":"), sort_keys=True),
                    json.dumps(provenance, separators=(",", ":"), sort_keys=True),
                    reserve_units,
                    now,
                    now,
                ),
            )
            active.execute(
                "INSERT INTO usage_ledger VALUES (?, ?, ?, 'reserve', ?, ?, ?)",
                (_id("led"), tenant_id, job_id, reserve_units, "job capacity reservation", now),
            )
            return self._get_job(active, tenant_id, job_id)

    def _decode_job(self, value: dict[str, Any]) -> dict[str, Any]:
        value["params"] = json.loads(value.pop("params_json"))
        value["provenance"] = json.loads(value.pop("provenance_json"))
        value["cancellation_requested"] = bool(value["cancellation_requested"])
        return value

    def get_job(self, tenant_id: str, job_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            return self._get_job(connection, tenant_id, job_id)

    def _get_job(
        self, connection: sqlite3.Connection, tenant_id: str, job_id: str
    ) -> dict[str, Any]:
        value = _row(
            connection.execute(
                "SELECT * FROM jobs WHERE id = ? AND tenant_id = ?", (job_id, tenant_id)
            ).fetchone()
        )
        if value is None:
            raise KeyError(job_id)
        value = self._decode_job(value)
        value["artifacts"] = self._list_artifacts(connection, tenant_id, job_id)
        return value

    def list_jobs(self, tenant_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
        return [self._decode_job(dict(row)) for row in rows]

    def page_jobs(
        self, tenant_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        limit = min(100, max(1, limit))
        parameters: list[Any] = [tenant_id]
        predicate = "tenant_id=?"
        if cursor:
            created_at, item_id = decode_cursor(cursor)
            predicate += " AND (created_at<? OR (created_at=? AND id<?))"
            parameters.extend([created_at, created_at, item_id])
        parameters.append(limit + 1)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM jobs WHERE {predicate} ORDER BY created_at DESC,id DESC LIMIT ?",
                parameters,
            ).fetchall()
        more = len(rows) > limit
        values = [self._decode_job(dict(row)) for row in rows[:limit]]
        next_cursor = (
            encode_cursor(values[-1]["created_at"], values[-1]["id"]) if more and values else None
        )
        return values, next_cursor

    def claim_next_job(
        self, *, worker_id: str, lease_seconds: int, max_attempts: int
    ) -> dict[str, Any] | None:
        now = time.time()
        attempt_token = secrets.token_urlsafe(24)
        with self.transaction() as connection:
            candidate = connection.execute(
                """
                SELECT id, tenant_id FROM jobs
                WHERE state = 'queued' AND cancellation_requested = 0 AND attempt < ?
                ORDER BY created_at LIMIT 1
                """,
                (max_attempts,),
            ).fetchone()
            if candidate is None:
                return None
            changed = connection.execute(
                """
                UPDATE jobs SET state = 'running', stage = 'validating', progress = 0.05,
                    attempt = attempt + 1, lease_expires_at = ?,
                    attempt_token = ?, worker_id = ?,
                    started_at = COALESCE(started_at, ?),
                    updated_at = ?
                WHERE id = ? AND state = 'queued'
                """,
                (now + lease_seconds, attempt_token, worker_id, now, now, candidate["id"]),
            ).rowcount
            if changed != 1:
                return None
        return self.get_job(candidate["tenant_id"], candidate["id"])

    def update_job_progress(
        self,
        tenant_id: str,
        job_id: str,
        *,
        attempt_token: str,
        worker_id: str,
        stage: str,
        progress: float,
        lease_seconds: int,
    ) -> None:
        now = time.time()
        with self.transaction() as connection:
            changed = connection.execute(
                """
                UPDATE jobs SET stage = ?, progress = ?, lease_expires_at = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ? AND state = 'running'
                    AND attempt_token = ? AND worker_id = ?
                """,
                (
                    stage,
                    min(0.99, max(0.0, progress)),
                    now + lease_seconds,
                    now,
                    job_id,
                    tenant_id,
                    attempt_token,
                    worker_id,
                ),
            ).rowcount
        if changed != 1:
            raise StaleAttempt(f"attempt no longer owns job {job_id}")

    def cancellation_requested(self, tenant_id: str, job_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT cancellation_requested FROM jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
        return bool(row and row[0])

    def attempt_cancelled(
        self, tenant_id: str, job_id: str, *, attempt_token: str, worker_id: str
    ) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT state,cancellation_requested,attempt_token,worker_id FROM jobs
                WHERE id=? AND tenant_id=?
                """,
                (job_id, tenant_id),
            ).fetchone()
        return bool(
            row is None
            or row["state"] != "running"
            or row["cancellation_requested"]
            or row["attempt_token"] != attempt_token
            or row["worker_id"] != worker_id
        )

    def request_cancellation(
        self,
        tenant_id: str,
        job_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> str:
        now = time.time()
        with self.transaction_or(connection) as active:
            row = active.execute(
                "SELECT state, reserved_units FROM jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["state"] in {"ready", "failed", "cancelled"}:
                raise InvalidTransition("only queued or running jobs can be cancelled")
            if row["state"] == "queued":
                active.execute(
                    """
                    UPDATE jobs SET state='cancelled', stage='cancelled', cancellation_requested=1,
                        finished_at=?, updated_at=? WHERE id=?
                    """,
                    (now, now, job_id),
                )
                self._release_reservation(
                    active, tenant_id, job_id, row["reserved_units"], "cancel"
                )
                return "cancelled"
            active.execute(
                """
                UPDATE jobs SET cancellation_requested=1, stage='cancelling', updated_at=?
                WHERE id=?
                """,
                (now, job_id),
            )
            return "cancelling"

    def _release_reservation(
        self,
        connection: sqlite3.Connection,
        tenant_id: str,
        job_id: str,
        units: int,
        event: str,
    ) -> None:
        connection.execute(
            "UPDATE tenants SET reserved_units = MAX(0, reserved_units - ?) WHERE id = ?",
            (units, tenant_id),
        )
        connection.execute(
            "INSERT INTO usage_ledger VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_id("led"), tenant_id, job_id, event, -units, "reservation released", time.time()),
        )

    def finish_job(
        self,
        tenant_id: str,
        job_id: str,
        *,
        attempt_token: str,
        worker_id: str,
        used_units: int,
    ) -> bool:
        """Atomically settle a result unless a committed cancellation won the race."""

        now = time.time()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT state,reserved_units,cancellation_requested,attempt_token,worker_id "
                "FROM jobs "
                "WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
            if (
                row is None
                or row["state"] != "running"
                or row["attempt_token"] != attempt_token
                or row["worker_id"] != worker_id
            ):
                raise StaleAttempt("attempt no longer owns this job")
            if used_units < 0 or used_units > row["reserved_units"]:
                raise ValueError("used units must fit within the reservation")
            if row["cancellation_requested"]:
                self._release_reservation(
                    connection, tenant_id, job_id, row["reserved_units"], "cancelled"
                )
                connection.execute(
                    """
                    UPDATE jobs SET state='cancelled', stage='cancelled',
                        error_code='cancelled', error_message='Job cancelled.',
                        lease_expires_at=NULL, attempt_token=NULL, worker_id=NULL,
                        finished_at=?, updated_at=? WHERE id=?
                        AND attempt_token=? AND worker_id=?
                    """,
                    (now, now, job_id, attempt_token, worker_id),
                )
                return False
            self._release_reservation(
                connection, tenant_id, job_id, row["reserved_units"], "release"
            )
            if used_units:
                connection.execute(
                    "UPDATE tenants SET consumed_units = consumed_units + ? WHERE id = ?",
                    (used_units, tenant_id),
                )
                connection.execute(
                    "INSERT INTO usage_ledger VALUES (?, ?, ?, 'consume', ?, ?, ?)",
                    (_id("led"), tenant_id, job_id, used_units, "completed job usage", now),
                )
            connection.execute(
                """
                UPDATE jobs SET state='ready', stage='ready', progress=1, used_units=?,
                    lease_expires_at=NULL, attempt_token=NULL, worker_id=NULL,
                    finished_at=?, updated_at=? WHERE id=?
                    AND attempt_token=? AND worker_id=?
                """,
                (used_units, now, now, job_id, attempt_token, worker_id),
            )
        return True

    def fail_job(
        self,
        tenant_id: str,
        job_id: str,
        *,
        attempt_token: str,
        worker_id: str,
        code: str,
        message: str,
        cancelled: bool = False,
    ) -> None:
        now = time.time()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT state,reserved_units,cancellation_requested,attempt_token,worker_id "
                "FROM jobs "
                "WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
            if (
                row is None
                or row["state"] != "running"
                or row["attempt_token"] != attempt_token
                or row["worker_id"] != worker_id
            ):
                raise StaleAttempt("attempt no longer owns this job")
            cancelled = cancelled or bool(row["cancellation_requested"])
            state = "cancelled" if cancelled else "failed"
            if cancelled:
                code, message = "cancelled", "Job cancelled."
            self._release_reservation(connection, tenant_id, job_id, row["reserved_units"], state)
            connection.execute(
                """
                UPDATE jobs SET state=?, stage=?, error_code=?, error_message=?,
                    lease_expires_at=NULL, attempt_token=NULL, worker_id=NULL,
                    finished_at=?, updated_at=? WHERE id=?
                    AND attempt_token=? AND worker_id=?
                """,
                (
                    state,
                    state,
                    code,
                    message[:1000],
                    now,
                    now,
                    job_id,
                    attempt_token,
                    worker_id,
                ),
            )

    def interrupt_attempt(
        self, tenant_id: str, job_id: str, *, attempt_token: str, worker_id: str
    ) -> str:
        """Release a cooperative shutdown attempt without charging a retry."""

        now = time.time()
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT attempt_token,worker_id,state,cancellation_requested,
                       reserved_units FROM jobs
                WHERE id=? AND tenant_id=?
                """,
                (job_id, tenant_id),
            ).fetchone()
            if (
                row is None
                or row["state"] != "running"
                or row["attempt_token"] != attempt_token
                or row["worker_id"] != worker_id
            ):
                raise StaleAttempt("attempt no longer owns this job")
            self._enqueue_attempt_artifacts(connection, tenant_id, job_id, attempt_token)
            if row["cancellation_requested"]:
                self._release_reservation(
                    connection,
                    tenant_id,
                    job_id,
                    row["reserved_units"],
                    "cancelled",
                )
                connection.execute(
                    """
                    UPDATE jobs SET state='cancelled',stage='cancelled',
                        error_code='cancelled',error_message='Job cancelled.',
                        attempt_token=NULL,worker_id=NULL,lease_expires_at=NULL,
                        finished_at=?,updated_at=? WHERE id=? AND tenant_id=?
                    """,
                    (now, now, job_id, tenant_id),
                )
                return "cancelled"
            connection.execute(
                """
                UPDATE jobs SET state='queued',stage='interrupted',progress=0,
                    attempt=MAX(0,attempt-1),attempt_token=NULL,worker_id=NULL,
                    lease_expires_at=NULL,updated_at=? WHERE id=? AND tenant_id=?
                """,
                (now, job_id, tenant_id),
            )
            return "queued"

    def recover_jobs(self, *, max_attempts: int) -> dict[str, int]:
        now = time.time()
        recovered = failed = cancelled = 0
        with self.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id,tenant_id,attempt,reserved_units,attempt_token,
                       cancellation_requested FROM jobs
                WHERE state='running' AND (lease_expires_at IS NULL OR lease_expires_at<=?)
                """,
                (now,),
            ).fetchall()
            for row in rows:
                if row["attempt_token"]:
                    self._enqueue_attempt_artifacts(
                        connection, row["tenant_id"], row["id"], row["attempt_token"]
                    )
                if row["cancellation_requested"]:
                    self._release_reservation(
                        connection,
                        row["tenant_id"],
                        row["id"],
                        row["reserved_units"],
                        "cancelled_recovery",
                    )
                    connection.execute(
                        """
                        UPDATE jobs SET state='cancelled',stage='cancelled',
                            error_code='cancelled',error_message='Job cancelled.',
                            attempt_token=NULL,worker_id=NULL,lease_expires_at=NULL,
                            finished_at=?,updated_at=? WHERE id=?
                        """,
                        (now, now, row["id"]),
                    )
                    cancelled += 1
                    continue
                if row["attempt"] < max_attempts:
                    connection.execute(
                        """
                        UPDATE jobs SET state='queued', stage='recovered', progress=0,
                            attempt_token=NULL,worker_id=NULL,lease_expires_at=NULL,
                            updated_at=? WHERE id=?
                        """,
                        (now, row["id"]),
                    )
                    recovered += 1
                else:
                    self._release_reservation(
                        connection,
                        row["tenant_id"],
                        row["id"],
                        row["reserved_units"],
                        "recovery_failed",
                    )
                    connection.execute(
                        """
                        UPDATE jobs SET state='failed', stage='failed', error_code='worker_lost',
                            error_message='Worker stopped before the job completed.',
                            attempt_token=NULL,worker_id=NULL,lease_expires_at=NULL,
                            finished_at=?, updated_at=? WHERE id=?
                        """,
                        (now, now, row["id"]),
                    )
                    failed += 1
        return {"requeued": recovered, "failed": failed, "cancelled": cancelled}

    def create_artifact(
        self,
        *,
        tenant_id: str,
        job_id: str,
        attempt_token: str,
        worker_id: str,
        kind: str,
        object_key: str,
        filename: str,
        media_type: str,
        size_bytes: int,
        sha256: str,
        license_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        artifact_id, now = _id("art"), time.time()
        with self.transaction() as connection:
            job = connection.execute(
                """
                SELECT id,state,attempt_token,worker_id FROM jobs
                WHERE id=? AND tenant_id=?
                """,
                (job_id, tenant_id),
            ).fetchone()
            if (
                job is None
                or job["state"] != "running"
                or job["attempt_token"] != attempt_token
                or job["worker_id"] != worker_id
            ):
                raise StaleAttempt("attempt no longer owns this job")
            tenant = self._tenant(connection, tenant_id)
            usage = self._resource_usage(connection, tenant_id)
            if usage["artifact_count"] >= tenant["artifact_limit"]:
                raise QuotaExceeded("tenant artifact count limit exceeded")
            claim = connection.execute(
                "SELECT size_bytes FROM object_claims WHERE object_key=? AND tenant_id=?",
                (object_key, tenant_id),
            ).fetchone()
            claimed_bytes = int(claim["size_bytes"]) if claim else 0
            if usage["stored_bytes"] - claimed_bytes + size_bytes > tenant["storage_limit_bytes"]:
                raise QuotaExceeded("tenant storage byte limit exceeded")
            connection.execute(
                """
                INSERT INTO artifacts(
                    id,tenant_id,job_id,kind,object_key,filename,media_type,size_bytes,
                    sha256,license_id,metadata_json,attempt_token,created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    tenant_id,
                    job_id,
                    kind,
                    object_key,
                    filename,
                    media_type,
                    size_bytes,
                    sha256,
                    license_id,
                    json.dumps(metadata, separators=(",", ":"), sort_keys=True),
                    attempt_token,
                    now,
                ),
            )
            connection.execute(
                "DELETE FROM object_claims WHERE object_key=? AND tenant_id=?",
                (object_key, tenant_id),
            )
        return self.get_artifact(tenant_id, artifact_id)

    def get_artifact(self, tenant_id: str, artifact_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            result = _row(
                connection.execute(
                    "SELECT * FROM artifacts WHERE id = ? AND tenant_id = ?",
                    (artifact_id, tenant_id),
                ).fetchone()
            )
        if result is None:
            raise KeyError(artifact_id)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def get_published_artifact(self, tenant_id: str, artifact_id: str) -> dict[str, Any]:
        """Return only artifacts belonging to a successfully completed job."""

        with self.connect() as connection:
            result = _row(
                connection.execute(
                    """
                    SELECT a.* FROM artifacts a JOIN jobs j ON j.id=a.job_id
                    WHERE a.id=? AND a.tenant_id=? AND j.tenant_id=? AND j.state='ready'
                    """,
                    (artifact_id, tenant_id, tenant_id),
                ).fetchone()
            )
        if result is None:
            raise KeyError(artifact_id)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def list_artifacts(self, tenant_id: str, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return self._list_artifacts(connection, tenant_id, job_id)

    @staticmethod
    def _list_artifacts(
        connection: sqlite3.Connection, tenant_id: str, job_id: str
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT a.* FROM artifacts a JOIN jobs j ON j.id=a.job_id
            WHERE a.tenant_id=? AND a.job_id=? AND j.tenant_id=? AND j.state='ready'
            ORDER BY a.created_at
            """,
            (tenant_id, job_id, tenant_id),
        ).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["metadata"] = json.loads(value.pop("metadata_json"))
            values.append(value)
        return values

    @staticmethod
    def _enqueue_object(
        connection: sqlite3.Connection,
        tenant_id: str,
        object_key: str,
        size_bytes: int,
        *,
        now: float | None = None,
    ) -> None:
        timestamp = time.time() if now is None else now
        connection.execute(
            """
            INSERT INTO deletion_outbox(
                id,tenant_id,object_key,size_bytes,attempts,next_attempt_at,
                last_error,created_at,updated_at
            ) VALUES(?,?,?,?,0,?,NULL,?,?)
            ON CONFLICT(object_key) DO NOTHING
            """,
            (
                _id("del"),
                tenant_id,
                object_key,
                max(0, int(size_bytes)),
                timestamp,
                timestamp,
                timestamp,
            ),
        )

    def _enqueue_attempt_artifacts(
        self,
        connection: sqlite3.Connection,
        tenant_id: str,
        job_id: str,
        attempt_token: str,
    ) -> int:
        rows = connection.execute(
            """
            SELECT id,object_key,size_bytes FROM artifacts
            WHERE tenant_id=? AND job_id=? AND attempt_token=?
            """,
            (tenant_id, job_id, attempt_token),
        ).fetchall()
        for row in rows:
            self._enqueue_object(connection, tenant_id, row["object_key"], row["size_bytes"])
        connection.executemany("DELETE FROM artifacts WHERE id=?", [(row["id"],) for row in rows])
        return len(rows)

    def queue_attempt_artifacts(self, tenant_id: str, job_id: str, *, attempt_token: str) -> int:
        with self.transaction() as connection:
            return self._enqueue_attempt_artifacts(connection, tenant_id, job_id, attempt_token)

    def queue_incomplete_artifacts(self) -> int:
        """Queue artifacts from attempts that no longer have an active owner."""

        queued = 0
        with self.transaction() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT a.tenant_id,a.job_id,a.attempt_token
                FROM artifacts a JOIN jobs j ON j.id=a.job_id
                WHERE j.state!='ready' AND j.state!='running'
                """
            ).fetchall()
            for row in rows:
                queued += self._enqueue_attempt_artifacts(
                    connection, row["tenant_id"], row["job_id"], row["attempt_token"]
                )
        return queued

    def queue_delete_asset(
        self,
        tenant_id: str,
        asset_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        with self.transaction_or(connection) as active:
            asset = active.execute(
                "SELECT object_key,size_bytes FROM assets WHERE id=? AND tenant_id=?",
                (asset_id, tenant_id),
            ).fetchone()
            if asset is None:
                raise KeyError(asset_id)
            if active.execute(
                "SELECT 1 FROM jobs WHERE source_asset_id=? AND tenant_id=? LIMIT 1",
                (asset_id, tenant_id),
            ).fetchone():
                raise InvalidTransition("assets referenced by jobs cannot be deleted directly")
            self._enqueue_object(active, tenant_id, asset["object_key"], asset["size_bytes"])
            active.execute("DELETE FROM assets WHERE id=?", (asset_id,))

    def queue_delete_job(
        self,
        tenant_id: str,
        job_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        with self.transaction_or(connection) as active:
            job = active.execute(
                "SELECT state,source_asset_id FROM jobs WHERE id=? AND tenant_id=?",
                (job_id, tenant_id),
            ).fetchone()
            if job is None:
                raise KeyError(job_id)
            if job["state"] not in {"ready", "failed", "cancelled"}:
                raise InvalidTransition("finish or cancel the job before deleting it")
            artifacts = active.execute(
                "SELECT object_key,size_bytes FROM artifacts WHERE job_id=? AND tenant_id=?",
                (job_id, tenant_id),
            ).fetchall()
            for artifact in artifacts:
                self._enqueue_object(
                    active, tenant_id, artifact["object_key"], artifact["size_bytes"]
                )
            source_id = job["source_asset_id"]
            active.execute("DELETE FROM jobs WHERE id=? AND tenant_id=?", (job_id, tenant_id))
            if (
                source_id
                and not active.execute(
                    "SELECT 1 FROM jobs WHERE source_asset_id=? LIMIT 1", (source_id,)
                ).fetchone()
            ):
                source = active.execute(
                    "SELECT object_key,size_bytes FROM assets WHERE id=? AND tenant_id=?",
                    (source_id, tenant_id),
                ).fetchone()
                if source:
                    self._enqueue_object(
                        active, tenant_id, source["object_key"], source["size_bytes"]
                    )
                    active.execute("DELETE FROM assets WHERE id=?", (source_id,))

    def queue_orphan_object(self, tenant_id: str, object_key: str, size_bytes: int) -> None:
        with self.transaction() as connection:
            self._enqueue_object(connection, tenant_id, object_key, size_bytes)

    @staticmethod
    def _global_stored_bytes(connection: sqlite3.Connection) -> int:
        row = connection.execute(
            """
            SELECT
                (SELECT COALESCE(SUM(size_bytes),0) FROM assets) +
                (SELECT COALESCE(SUM(size_bytes),0) FROM artifacts) +
                (SELECT COALESCE(SUM(size_bytes),0) FROM deletion_outbox) +
                (SELECT COALESCE(SUM(size_bytes),0) FROM object_claims)
            """
        ).fetchone()
        return int(row[0])

    def claim_object(
        self,
        tenant_id: str,
        object_key: str,
        *,
        ttl_seconds: int,
        reserve_bytes: int = 0,
        purpose: str = "legacy",
        global_storage_bytes: int | None = None,
        physical_free_bytes: int | None = None,
        min_free_bytes: int = 0,
        global_inflight_limit: int | None = None,
        tenant_inflight_limit: int | None = None,
    ) -> None:
        """Reserve storage bytes and an in-flight slot before object I/O."""

        if reserve_bytes < 0:
            raise ValueError("object reservation must not be negative")
        if purpose not in {"upload", "artifact", "legacy"}:
            raise ValueError("unsupported object-claim purpose")
        now = time.time()
        with self.transaction() as connection:
            tenant = self._tenant(connection, tenant_id)
            usage = self._resource_usage(connection, tenant_id)
            if usage["stored_bytes"] + reserve_bytes > tenant["storage_limit_bytes"]:
                raise QuotaExceeded("tenant storage byte limit exceeded")
            global_used = self._global_stored_bytes(connection)
            if (
                global_storage_bytes is not None
                and global_used + reserve_bytes > global_storage_bytes
            ):
                raise QuotaExceeded("global storage byte limit exceeded")
            inflight_global = int(
                connection.execute("SELECT COUNT(*) FROM object_claims").fetchone()[0]
            )
            inflight_tenant = int(
                connection.execute(
                    "SELECT COUNT(*) FROM object_claims WHERE tenant_id=?", (tenant_id,)
                ).fetchone()[0]
            )
            if global_inflight_limit is not None and inflight_global >= global_inflight_limit:
                raise QuotaExceeded("global in-flight storage-write limit exceeded")
            if tenant_inflight_limit is not None and inflight_tenant >= tenant_inflight_limit:
                raise QuotaExceeded("tenant in-flight storage-write limit exceeded")
            if physical_free_bytes is not None:
                unmaterialized = int(
                    connection.execute(
                        "SELECT COALESCE(SUM(size_bytes),0) FROM object_claims WHERE materialized=0"
                    ).fetchone()[0]
                )
                if physical_free_bytes - unmaterialized - reserve_bytes < min_free_bytes:
                    raise QuotaExceeded("storage minimum-free-space budget would be breached")
            connection.execute(
                """
                INSERT INTO object_claims(
                    object_key,tenant_id,size_bytes,materialized,purpose,expires_at,created_at
                ) VALUES(?,?,?,0,?,?,?)
                """,
                (object_key, tenant_id, reserve_bytes, purpose, now + ttl_seconds, now),
            )

    def size_object_claim(self, tenant_id: str, object_key: str, size_bytes: int) -> None:
        """Transactionally charge stored in-flight bytes before validation/commit."""

        if size_bytes < 0:
            raise ValueError("object claim size must not be negative")
        with self.transaction() as connection:
            tenant = self._tenant(connection, tenant_id)
            usage = self._resource_usage(connection, tenant_id)
            claim = connection.execute(
                "SELECT size_bytes FROM object_claims WHERE object_key=? AND tenant_id=?",
                (object_key, tenant_id),
            ).fetchone()
            if claim is None:
                raise KeyError(object_key)
            current = int(claim["size_bytes"])
            if current and size_bytes > current:
                raise QuotaExceeded("object exceeded its pre-I/O storage reservation")
            if usage["stored_bytes"] - current + size_bytes > tenant["storage_limit_bytes"]:
                raise QuotaExceeded("tenant storage byte limit exceeded")
            connection.execute(
                """
                UPDATE object_claims SET size_bytes=?,materialized=1
                WHERE object_key=? AND tenant_id=?
                """,
                (size_bytes, object_key, tenant_id),
            )

    def object_claims_due(self, *, force: bool = False) -> list[dict[str, Any]]:
        predicate = "1=1" if force else "expires_at<=?"
        parameters: tuple[Any, ...] = () if force else (time.time(),)
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    f"SELECT * FROM object_claims WHERE {predicate} ORDER BY created_at",
                    parameters,
                ).fetchall()
            ]

    def recover_object_claim(
        self,
        tenant_id: str,
        object_key: str,
        *,
        actual_size: int | None,
    ) -> bool:
        """Reconcile one abandoned claim using a measured object size."""

        with self.transaction() as connection:
            claim = connection.execute(
                "SELECT 1 FROM object_claims WHERE object_key=? AND tenant_id=?",
                (object_key, tenant_id),
            ).fetchone()
            if claim is None:
                return False
            active = connection.execute(
                """
                SELECT 1 FROM assets WHERE object_key=?
                UNION SELECT 1 FROM artifacts WHERE object_key=? LIMIT 1
                """,
                (object_key, object_key),
            ).fetchone()
            if active is None and actual_size is not None:
                self._enqueue_object(connection, tenant_id, object_key, actual_size)
            connection.execute("DELETE FROM object_claims WHERE object_key=?", (object_key,))
            return True

    def release_object_claim(self, tenant_id: str, object_key: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "DELETE FROM object_claims WHERE object_key=? AND tenant_id=?",
                (object_key, tenant_id),
            )

    def known_object_keys(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT object_key FROM assets UNION SELECT object_key FROM artifacts
                UNION SELECT object_key FROM deletion_outbox
                UNION SELECT object_key FROM object_claims
                """
            ).fetchall()
        return {str(row[0]) for row in rows}

    def active_object_keys(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT object_key FROM assets UNION SELECT object_key FROM artifacts"
            ).fetchall()
        return {str(row[0]) for row in rows}

    def due_deletions(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM deletion_outbox WHERE next_attempt_at<=?
                    ORDER BY created_at LIMIT ?
                    """,
                    (time.time(), min(500, max(1, limit))),
                ).fetchall()
            ]

    def complete_deletion(self, deletion_id: str) -> None:
        with self.transaction() as connection:
            connection.execute("DELETE FROM deletion_outbox WHERE id=?", (deletion_id,))

    def fail_deletion(self, deletion_id: str, error: str) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT attempts FROM deletion_outbox WHERE id=?", (deletion_id,)
            ).fetchone()
            if row is None:
                return
            attempts = int(row["attempts"]) + 1
            delay = min(3600, 2 ** min(attempts, 10))
            connection.execute(
                """
                UPDATE deletion_outbox SET attempts=?,next_attempt_at=?,last_error=?,updated_at=?
                WHERE id=?
                """,
                (attempts, time.time() + delay, error[:500], time.time(), deletion_id),
            )

    def pending_deletion_count(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM deletion_outbox").fetchone()[0])

    def create_share(
        self,
        tenant_id: str,
        artifact_id: str,
        *,
        ttl_seconds: int,
        rate_limit: int | None = None,
        rate_window_seconds: int = 60,
        raw_token: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], str]:
        raw_token = raw_token or secrets.token_urlsafe(32)
        now = time.time()
        with self.transaction_or(connection) as active:
            artifact = active.execute(
                """
                SELECT a.id FROM artifacts a JOIN jobs j ON j.id=a.job_id
                WHERE a.id=? AND a.tenant_id=? AND j.tenant_id=? AND j.state='ready'
                    AND a.kind='scene' AND a.media_type='model/gltf-binary'
                """,
                (artifact_id, tenant_id, tenant_id),
            ).fetchone()
            if artifact is None:
                raise KeyError(artifact_id)
            tenant = self._tenant(active, tenant_id)
            usage = self._resource_usage(active, tenant_id)
            if usage["share_count"] >= tenant["share_limit"]:
                raise QuotaExceeded("tenant active share limit exceeded")
            self._consume_rate(
                active,
                tenant_id,
                "share",
                limit=rate_limit,
                window_seconds=rate_window_seconds,
                now=now,
            )
            share_id = _id("shr")
            active.execute(
                """
                INSERT INTO shares(
                    id,tenant_id,artifact_id,token_hash,expires_at,revoked_at,created_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?)
                """,
                (share_id, tenant_id, artifact_id, token_digest(raw_token), now + ttl_seconds, now),
            )
        return {
            "id": share_id,
            "artifact_id": artifact_id,
            "expires_at": now + ttl_seconds,
        }, raw_token

    def page_shares(
        self, tenant_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        limit = min(100, max(1, limit))
        parameters: list[Any] = [tenant_id]
        predicate = "s.tenant_id=?"
        if cursor:
            created_at, item_id = decode_cursor(cursor)
            predicate += " AND (s.created_at<? OR (s.created_at=? AND s.id<?))"
            parameters.extend([created_at, created_at, item_id])
        parameters.append(limit + 1)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT s.id,s.artifact_id,s.expires_at,s.revoked_at,s.created_at,
                       a.filename,a.kind,a.metadata_json
                FROM shares s JOIN artifacts a ON a.id=s.artifact_id
                JOIN jobs j ON j.id=a.job_id
                WHERE {predicate} AND j.state='ready' AND j.tenant_id=s.tenant_id
                ORDER BY s.created_at DESC,s.id DESC LIMIT ?
                """,
                parameters,
            ).fetchall()
        more = len(rows) > limit
        values = []
        for row in rows[:limit]:
            value = dict(row)
            value["metadata"] = json.loads(value.pop("metadata_json"))
            values.append(value)
        next_cursor = (
            encode_cursor(values[-1]["created_at"], values[-1]["id"]) if more and values else None
        )
        return values, next_cursor

    def resolve_share(self, raw_token: str) -> dict[str, Any] | None:
        now = time.time()
        with self.connect() as connection:
            result = _row(
                connection.execute(
                    """
                    SELECT s.id AS share_id, s.expires_at, a.*
                    FROM shares s JOIN artifacts a ON a.id = s.artifact_id
                    JOIN jobs j ON j.id=a.job_id
                    WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
                        AND j.state='ready' AND j.tenant_id=s.tenant_id
                    """,
                    (token_digest(raw_token), now),
                ).fetchone()
            )
        if result:
            result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def share_token_matches(self, tenant_id: str, share_id: str, raw_token: str) -> bool:
        """Check replay material without changing expiry or revocation semantics."""

        with self.connect() as connection:
            row = connection.execute(
                "SELECT token_hash FROM shares WHERE id=? AND tenant_id=?",
                (share_id, tenant_id),
            ).fetchone()
        return bool(row and secrets.compare_digest(str(row["token_hash"]), token_digest(raw_token)))

    def revoke_share(
        self,
        tenant_id: str,
        share_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        with self.transaction_or(connection) as active:
            changed = active.execute(
                """
                UPDATE shares SET revoked_at = ?
                WHERE id = ? AND tenant_id = ? AND revoked_at IS NULL
                """,
                (time.time(), share_id, tenant_id),
            ).rowcount
        if changed != 1:
            raise KeyError(share_id)

    def begin_idempotency(
        self,
        tenant_id: str,
        scope: str,
        raw_key: str | None,
        request_hash: str,
        *,
        ttl_seconds: int,
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Claim a route-scoped key or return its completed response."""

        if not raw_key:
            return None
        if len(raw_key) > 200 or len(raw_key) < 8:
            raise ValueError("Idempotency-Key must contain 8 to 200 characters")
        key_hash = token_digest(raw_key)
        now = time.time()
        with self.transaction_or(connection) as active:
            existing = active.execute(
                """
                SELECT * FROM idempotency_keys
                WHERE tenant_id=? AND scope=? AND key_hash=?
                """,
                (tenant_id, scope, key_hash),
            ).fetchone()
            if existing and existing["expires_at"] <= now:
                active.execute(
                    "DELETE FROM idempotency_keys WHERE tenant_id=? AND scope=? AND key_hash=?",
                    (tenant_id, scope, key_hash),
                )
                existing = None
            if existing:
                if existing["request_hash"] != request_hash:
                    raise IdempotencyConflict(
                        "Idempotency-Key was already used with a different request"
                    )
                if existing["state"] == "in_progress":
                    raise IdempotencyInProgress("the matching request is still in progress")
                return {
                    "status_code": int(existing["status_code"]),
                    "response": json.loads(existing["response_json"]),
                }
            active.execute(
                """
                INSERT INTO idempotency_keys(
                    tenant_id,scope,key_hash,request_hash,state,status_code,response_json,
                    created_at,updated_at,expires_at
                ) VALUES(?,?,?,?,'in_progress',NULL,NULL,?,?,?)
                """,
                (tenant_id, scope, key_hash, request_hash, now, now, now + ttl_seconds),
            )
        return None

    def complete_idempotency(
        self,
        tenant_id: str,
        scope: str,
        raw_key: str | None,
        request_hash: str,
        *,
        status_code: int,
        response: dict[str, Any],
        connection: sqlite3.Connection | None = None,
    ) -> None:
        if not raw_key:
            return
        with self.transaction_or(connection) as active:
            changed = active.execute(
                """
                UPDATE idempotency_keys
                SET state='complete',status_code=?,response_json=?,updated_at=?
                WHERE tenant_id=? AND scope=? AND key_hash=? AND request_hash=?
                    AND state='in_progress'
                """,
                (
                    status_code,
                    json.dumps(response, separators=(",", ":"), sort_keys=True),
                    time.time(),
                    tenant_id,
                    scope,
                    token_digest(raw_key),
                    request_hash,
                ),
            ).rowcount
        if changed != 1:
            raise IdempotencyConflict("idempotency claim was lost before completion")

    def abandon_idempotency(
        self,
        tenant_id: str,
        scope: str,
        raw_key: str | None,
        request_hash: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        if not raw_key:
            return
        with self.transaction_or(connection) as active:
            active.execute(
                """
                DELETE FROM idempotency_keys WHERE tenant_id=? AND scope=? AND key_hash=?
                    AND request_hash=? AND state='in_progress'
                """,
                (tenant_id, scope, token_digest(raw_key), request_hash),
            )

    def run_retention(self, *, terminal_before: float, unattached_before: float) -> dict[str, int]:
        now = time.time()
        with self.transaction() as connection:
            expired_shares = connection.execute(
                """
                DELETE FROM shares
                WHERE expires_at<=? OR (revoked_at IS NOT NULL AND revoked_at<=?)
                """,
                (now, terminal_before),
            ).rowcount
            connection.execute("DELETE FROM idempotency_keys WHERE expires_at<=?", (now,))
            connection.execute("DELETE FROM rate_buckets WHERE bucket_start<?", (int(now) - 3600,))
            job_ids = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT id FROM jobs WHERE state IN ('ready','failed','cancelled')
                    AND COALESCE(finished_at,updated_at)<?
                    """,
                    (terminal_before,),
                ).fetchall()
            ]
            asset_ids = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT a.id FROM assets a WHERE a.created_at<? AND NOT EXISTS(
                        SELECT 1 FROM jobs j WHERE j.source_asset_id=a.id
                    )
                    """,
                    (unattached_before,),
                ).fetchall()
            ]
        deleted_jobs = deleted_assets = 0
        for job_id in job_ids:
            try:
                tenant = self._tenant_for_job(job_id)
                self.queue_delete_job(tenant, job_id)
                deleted_jobs += 1
            except (KeyError, InvalidTransition):
                pass
        for asset_id in asset_ids:
            try:
                tenant = self._tenant_for_asset(asset_id)
                self.queue_delete_asset(tenant, asset_id)
                deleted_assets += 1
            except (KeyError, InvalidTransition):
                pass
        with self.transaction() as connection:
            expired_ledger = connection.execute(
                "DELETE FROM usage_ledger WHERE job_id IS NULL AND created_at<?",
                (terminal_before,),
            ).rowcount
        return {
            "jobs": deleted_jobs,
            "assets": deleted_assets,
            "shares": int(expired_shares),
            "ledger": int(expired_ledger),
        }

    def _tenant_for_job(self, job_id: str) -> str:
        with self.connect() as connection:
            row = connection.execute("SELECT tenant_id FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return str(row[0])

    def _tenant_for_asset(self, asset_id: str) -> str:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT tenant_id FROM assets WHERE id=?", (asset_id,)
            ).fetchone()
        if row is None:
            raise KeyError(asset_id)
        return str(row[0])

    def ledger(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM usage_ledger WHERE tenant_id = ? ORDER BY created_at",
                    (tenant_id,),
                ).fetchall()
            ]
