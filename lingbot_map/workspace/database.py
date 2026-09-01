"""Small SQLite repository with explicit tenant and job invariants."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


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


class Database:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
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

    def initialize(self) -> None:
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
                """
            )
            version = connection.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
            if version is None:
                connection.execute("INSERT INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
            elif version[0] != SCHEMA_VERSION:
                raise RuntimeError(
                    f"database schema {version[0]} is unsupported; expected {SCHEMA_VERSION}"
                )

    def bootstrap(self, *, token: str, tenant_name: str, quota_units: int) -> dict[str, str]:
        digest = token_digest(token)
        now = time.time()
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT tenant_id, user_id FROM api_tokens WHERE token_hash = ?", (digest,)
            ).fetchone()
            if existing:
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
                    "INSERT INTO tenants VALUES (?, ?, ?, 0, 0, ?)",
                    (tenant_id, tenant_name, quota_units, now),
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
                "INSERT INTO api_tokens VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (_id("key"), tenant_id, user_id, "bootstrap", digest, now),
            )
        return {"tenant_id": tenant_id, "user_id": user_id}

    def provision_tenant(self, *, token: str, tenant_name: str, quota_units: int) -> dict[str, str]:
        """Create a distinct tenant for an operator-managed high-entropy token."""

        digest = token_digest(token)
        now = time.time()
        tenant_id, user_id = _id("ten"), _id("usr")
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO tenants VALUES (?, ?, ?, 0, 0, ?)",
                (tenant_id, tenant_name, quota_units, now),
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
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    _id("ses"),
                    principal["tenant_id"],
                    principal["user_id"],
                    token_digest(session_token),
                    token_digest(csrf_token),
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

    def rotate_csrf(self, session_id: str) -> str:
        csrf_token = secrets.token_urlsafe(24)
        with self.transaction() as connection:
            changed = connection.execute(
                "UPDATE sessions SET csrf_hash = ? WHERE id = ? AND expires_at > ?",
                (token_digest(csrf_token), session_id, time.time()),
            ).rowcount
        if changed != 1:
            raise KeyError(session_id)
        return csrf_token

    def quota(self, tenant_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT quota_units, reserved_units, consumed_units FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        if row is None:
            raise KeyError(tenant_id)
        result = dict(row)
        result["available_units"] = (
            result["quota_units"] - result["reserved_units"] - result["consumed_units"]
        )
        return result

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
    ) -> dict[str, Any]:
        asset_id, now = _id("ast"), time.time()
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        return self.get_asset(tenant_id, asset_id)

    def get_asset(self, tenant_id: str, asset_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            result = _row(
                connection.execute(
                    "SELECT * FROM assets WHERE id = ? AND tenant_id = ?", (asset_id, tenant_id)
                ).fetchone()
            )
        if result is None:
            raise KeyError(asset_id)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def delete_asset_record(self, tenant_id: str, asset_id: str) -> str:
        with self.transaction() as connection:
            asset = connection.execute(
                "SELECT object_key FROM assets WHERE id = ? AND tenant_id = ?",
                (asset_id, tenant_id),
            ).fetchone()
            if asset is None:
                raise KeyError(asset_id)
            referenced = connection.execute(
                "SELECT 1 FROM jobs WHERE source_asset_id = ? AND tenant_id = ? LIMIT 1",
                (asset_id, tenant_id),
            ).fetchone()
            if referenced:
                raise InvalidTransition("assets referenced by jobs cannot be deleted directly")
            connection.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        return str(asset["object_key"])

    def create_job(
        self,
        *,
        tenant_id: str,
        engine_id: str,
        source_asset_id: str | None,
        params: dict[str, Any],
        provenance: dict[str, Any],
        reserve_units: int,
    ) -> dict[str, Any]:
        job_id, now = _id("job"), time.time()
        with self.transaction() as connection:
            tenant = connection.execute(
                "SELECT quota_units, reserved_units, consumed_units FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
            if tenant is None:
                raise KeyError(tenant_id)
            available = tenant["quota_units"] - tenant["reserved_units"] - tenant["consumed_units"]
            if reserve_units > available:
                raise QuotaExceeded(f"job needs {reserve_units} units; {available} remain")
            if source_asset_id:
                source = connection.execute(
                    "SELECT id FROM assets WHERE id = ? AND tenant_id = ?",
                    (source_asset_id, tenant_id),
                ).fetchone()
                if source is None:
                    raise KeyError(source_asset_id)
            connection.execute(
                "UPDATE tenants SET reserved_units = reserved_units + ? WHERE id = ?",
                (reserve_units, tenant_id),
            )
            connection.execute(
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
            connection.execute(
                "INSERT INTO usage_ledger VALUES (?, ?, ?, 'reserve', ?, ?, ?)",
                (_id("led"), tenant_id, job_id, reserve_units, "job capacity reservation", now),
            )
        return self.get_job(tenant_id, job_id)

    def _decode_job(self, value: dict[str, Any]) -> dict[str, Any]:
        value["params"] = json.loads(value.pop("params_json"))
        value["provenance"] = json.loads(value.pop("provenance_json"))
        value["cancellation_requested"] = bool(value["cancellation_requested"])
        return value

    def get_job(self, tenant_id: str, job_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            value = _row(
                connection.execute(
                    "SELECT * FROM jobs WHERE id = ? AND tenant_id = ?", (job_id, tenant_id)
                ).fetchone()
            )
        if value is None:
            raise KeyError(job_id)
        value = self._decode_job(value)
        value["artifacts"] = self.list_artifacts(tenant_id, job_id)
        return value

    def list_jobs(self, tenant_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
        return [self._decode_job(dict(row)) for row in rows]

    def claim_next_job(self, *, lease_seconds: int, max_attempts: int) -> dict[str, Any] | None:
        now = time.time()
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
                    started_at = COALESCE(started_at, ?),
                    updated_at = ?
                WHERE id = ? AND state = 'queued'
                """,
                (now + lease_seconds, now, now, candidate["id"]),
            ).rowcount
            if changed != 1:
                return None
        return self.get_job(candidate["tenant_id"], candidate["id"])

    def update_job_progress(
        self, tenant_id: str, job_id: str, *, stage: str, progress: float, lease_seconds: int
    ) -> None:
        now = time.time()
        with self.transaction() as connection:
            changed = connection.execute(
                """
                UPDATE jobs SET stage = ?, progress = ?, lease_expires_at = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ? AND state = 'running'
                """,
                (stage, min(0.99, max(0.0, progress)), now + lease_seconds, now, job_id, tenant_id),
            ).rowcount
        if changed != 1:
            raise InvalidTransition(f"cannot update non-running job {job_id}")

    def cancellation_requested(self, tenant_id: str, job_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT cancellation_requested FROM jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
        return bool(row and row[0])

    def request_cancellation(self, tenant_id: str, job_id: str) -> str:
        now = time.time()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT state, reserved_units FROM jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["state"] in {"ready", "failed", "cancelled"}:
                raise InvalidTransition("only queued or running jobs can be cancelled")
            if row["state"] == "queued":
                connection.execute(
                    """
                    UPDATE jobs SET state='cancelled', stage='cancelled', cancellation_requested=1,
                        finished_at=?, updated_at=? WHERE id=?
                    """,
                    (now, now, job_id),
                )
                self._release_reservation(
                    connection, tenant_id, job_id, row["reserved_units"], "cancel"
                )
                return "cancelled"
            connection.execute(
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

    def finish_job(self, tenant_id: str, job_id: str, *, used_units: int) -> None:
        now = time.time()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT state, reserved_units FROM jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
            if row is None or row["state"] != "running":
                raise InvalidTransition("only a running job can finish")
            if used_units < 0 or used_units > row["reserved_units"]:
                raise ValueError("used units must fit within the reservation")
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
                    lease_expires_at=NULL, finished_at=?, updated_at=? WHERE id=?
                """,
                (used_units, now, now, job_id),
            )

    def fail_job(
        self,
        tenant_id: str,
        job_id: str,
        *,
        code: str,
        message: str,
        cancelled: bool = False,
    ) -> None:
        now = time.time()
        state = "cancelled" if cancelled else "failed"
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT state, reserved_units FROM jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["state"] in {"ready", "failed", "cancelled"}:
                return
            self._release_reservation(connection, tenant_id, job_id, row["reserved_units"], state)
            connection.execute(
                """
                UPDATE jobs SET state=?, stage=?, error_code=?, error_message=?,
                    lease_expires_at=NULL, finished_at=?, updated_at=? WHERE id=?
                """,
                (state, state, code, message[:1000], now, now, job_id),
            )

    def recover_jobs(self, *, max_attempts: int) -> dict[str, int]:
        now = time.time()
        recovered = failed = 0
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT id, tenant_id, attempt, reserved_units FROM jobs WHERE state='running'"
            ).fetchall()
            for row in rows:
                if row["attempt"] < max_attempts:
                    connection.execute(
                        """
                        UPDATE jobs SET state='queued', stage='recovered', progress=0,
                            lease_expires_at=NULL, updated_at=? WHERE id=?
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
                            lease_expires_at=NULL, finished_at=?, updated_at=? WHERE id=?
                        """,
                        (now, now, row["id"]),
                    )
                    failed += 1
        return {"requeued": recovered, "failed": failed}

    def create_artifact(
        self,
        *,
        tenant_id: str,
        job_id: str,
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
                "SELECT id FROM jobs WHERE id = ? AND tenant_id = ?", (job_id, tenant_id)
            ).fetchone()
            if job is None:
                raise KeyError(job_id)
            connection.execute(
                "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    now,
                ),
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

    def list_artifacts(self, tenant_id: str, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM artifacts WHERE tenant_id = ? AND job_id = ? ORDER BY created_at",
                (tenant_id, job_id),
            ).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["metadata"] = json.loads(value.pop("metadata_json"))
            values.append(value)
        return values

    def delete_artifacts_for_job(self, tenant_id: str, job_id: str) -> list[str]:
        with self.transaction() as connection:
            keys = [
                row[0]
                for row in connection.execute(
                    "SELECT object_key FROM artifacts WHERE job_id = ? AND tenant_id = ?",
                    (job_id, tenant_id),
                ).fetchall()
            ]
            connection.execute(
                "DELETE FROM artifacts WHERE job_id = ? AND tenant_id = ?", (job_id, tenant_id)
            )
        return keys

    def delete_artifacts_for_incomplete_jobs(self) -> list[str]:
        """Discard records left between artifact storage and a durable job finish."""

        with self.transaction() as connection:
            keys = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT a.object_key
                    FROM artifacts a JOIN jobs j ON j.id = a.job_id
                    WHERE j.state != 'ready'
                    """
                ).fetchall()
            ]
            connection.execute(
                """
                DELETE FROM artifacts
                WHERE job_id IN (SELECT id FROM jobs WHERE state != 'ready')
                """
            )
        return keys

    def delete_job_records(self, tenant_id: str, job_id: str) -> tuple[list[str], str | None]:
        with self.transaction() as connection:
            job = connection.execute(
                "SELECT state, source_asset_id FROM jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
            if job is None:
                raise KeyError(job_id)
            if job["state"] not in {"ready", "failed", "cancelled"}:
                raise InvalidTransition("finish or cancel the job before deleting it")
            keys = [
                row[0]
                for row in connection.execute(
                    "SELECT object_key FROM artifacts WHERE job_id = ? AND tenant_id = ?",
                    (job_id, tenant_id),
                ).fetchall()
            ]
            source_id = job["source_asset_id"]
            connection.execute(
                "DELETE FROM jobs WHERE id = ? AND tenant_id = ?", (job_id, tenant_id)
            )
            source_key = None
            if source_id:
                still_used = connection.execute(
                    "SELECT 1 FROM jobs WHERE source_asset_id = ? LIMIT 1", (source_id,)
                ).fetchone()
                if not still_used:
                    source = connection.execute(
                        "SELECT object_key FROM assets WHERE id = ? AND tenant_id = ?",
                        (source_id, tenant_id),
                    ).fetchone()
                    if source:
                        source_key = source["object_key"]
                        connection.execute("DELETE FROM assets WHERE id = ?", (source_id,))
        return keys, source_key

    def create_share(
        self, tenant_id: str, artifact_id: str, *, ttl_seconds: int
    ) -> tuple[dict[str, Any], str]:
        raw_token = secrets.token_urlsafe(32)
        now = time.time()
        with self.transaction() as connection:
            artifact = connection.execute(
                "SELECT id FROM artifacts WHERE id = ? AND tenant_id = ?",
                (artifact_id, tenant_id),
            ).fetchone()
            if artifact is None:
                raise KeyError(artifact_id)
            share_id = _id("shr")
            connection.execute(
                "INSERT INTO shares VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (share_id, tenant_id, artifact_id, token_digest(raw_token), now + ttl_seconds, now),
            )
        return {
            "id": share_id,
            "artifact_id": artifact_id,
            "expires_at": now + ttl_seconds,
        }, raw_token

    def resolve_share(self, raw_token: str) -> dict[str, Any] | None:
        now = time.time()
        with self.connect() as connection:
            result = _row(
                connection.execute(
                    """
                    SELECT s.id AS share_id, s.expires_at, a.*
                    FROM shares s JOIN artifacts a ON a.id = s.artifact_id
                    WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
                    """,
                    (token_digest(raw_token), now),
                ).fetchone()
            )
        if result:
            result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def revoke_share(self, tenant_id: str, share_id: str) -> None:
        with self.transaction() as connection:
            changed = connection.execute(
                """
                UPDATE shares SET revoked_at = ?
                WHERE id = ? AND tenant_id = ? AND revoked_at IS NULL
                """,
                (time.time(), share_id, tenant_id),
            ).rowcount
        if changed != 1:
            raise KeyError(share_id)

    def ledger(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM usage_ledger WHERE tenant_id = ? ORDER BY created_at",
                    (tenant_id,),
                ).fetchall()
            ]
