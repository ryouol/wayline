"""Runtime configuration with production-safe defaults."""

from __future__ import annotations

import math
import os
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

RESEARCH_ACKNOWLEDGEMENT = "I understand LingBot is research-only"
HOST_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _allowed_hosts(value: str, public_base_url: str) -> tuple[str, ...]:
    configured = tuple(host.strip().lower() for host in value.split(",") if host.strip())
    if configured:
        return configured
    parsed = urlsplit(public_base_url)
    return (parsed.hostname.lower(),) if parsed.hostname else ()


@dataclass(frozen=True, slots=True)
class Settings:
    """Workspace settings.

    ``bootstrap_token`` is generated for an explicit development run, but is
    mandatory and at least 32 characters long in production. There is no
    shipped password or anonymous production mode.
    """

    data_dir: Path
    environment: str = "production"
    bootstrap_token: str | None = None
    bootstrap_tenant_name: str = "Local workspace"
    cookie_secure: bool = True
    session_ttl_seconds: int = 12 * 60 * 60
    max_upload_bytes: int = 250 * 1024 * 1024
    upload_timeout_seconds: int = 900
    max_artifact_bytes: int = 100 * 1024 * 1024
    global_storage_bytes: int = 20 * 1024 * 1024 * 1024
    scene_delivery_budget_bytes: int = 2_000_000_000
    storage_min_free_bytes: int = 1024 * 1024 * 1024
    global_max_inflight_objects: int = 8
    tenant_max_inflight_objects: int = 3
    max_video_seconds: int = 5 * 60
    max_video_frames: int = 9_000
    max_video_dimension: int = 4_096
    tenant_quota_units: int = 10_000
    tenant_storage_bytes: int = 5 * 1024 * 1024 * 1024
    tenant_max_assets: int = 100
    tenant_max_unattached_assets: int = 10
    tenant_max_jobs: int = 500
    tenant_max_artifacts: int = 1_500
    tenant_max_shares: int = 250
    upload_rate_per_minute: int = 10
    job_rate_per_minute: int = 30
    share_rate_per_minute: int = 30
    terminal_job_retention_seconds: int = 30 * 24 * 60 * 60
    unattached_asset_retention_seconds: int = 24 * 60 * 60
    idempotency_ttl_seconds: int = 24 * 60 * 60
    shutdown_timeout_seconds: int = 30
    readiness_probe_ttl_seconds: float = 2.0
    worker_poll_seconds: float = 0.25
    job_timeout_seconds: int = 60 * 60
    max_job_attempts: int = 2
    public_base_url: str = ""
    allowed_hosts: tuple[str, ...] = ()
    research_acknowledgement: str = ""
    research_command: str = ""
    checkpoint_path: Path | None = None
    checkpoint_sha256: str = ""
    checkpoint_max_bytes: int = 6 * 1024 * 1024 * 1024
    skyseg_path: Path | None = None
    skyseg_sha256: str = ""
    skyseg_max_bytes: int = 512 * 1024 * 1024
    modal_enabled: bool = False
    modal_gpu_seconds_budget: int = 14_400
    google_client_id: str = ""
    google_client_secret: str = ""
    signup_enabled: bool = False
    trial_enabled: bool = True
    signup_max_accounts: int = 100
    trial_max_accounts: int = 100
    signup_quota_units: int = 120
    generated_bootstrap_token: bool = field(default=False, compare=False)

    @classmethod
    def from_env(cls, *, development: bool = False) -> Settings:
        environment = os.getenv("LINGBOT_ENV", "development" if development else "production")
        environment = environment.strip().lower()
        token = os.getenv("LINGBOT_BOOTSTRAP_TOKEN")
        generated = False
        if environment == "development" and not token:
            token = secrets.token_urlsafe(32)
            generated = True

        checkpoint = os.getenv("LINGBOT_CHECKPOINT_PATH")
        skyseg = os.getenv("LINGBOT_SKYSEG_PATH")
        public_base_url = os.getenv("LINGBOT_PUBLIC_BASE_URL", "").rstrip("/")
        settings = cls(
            data_dir=Path(os.getenv("LINGBOT_DATA_DIR", ".lingbot-workspace"))
            .expanduser()
            .resolve(),
            environment=environment,
            bootstrap_token=token,
            bootstrap_tenant_name=os.getenv("LINGBOT_TENANT_NAME", "Local workspace"),
            cookie_secure=_bool_env("LINGBOT_COOKIE_SECURE", environment == "production"),
            session_ttl_seconds=int(os.getenv("LINGBOT_SESSION_TTL_SECONDS", str(12 * 60 * 60))),
            max_upload_bytes=int(os.getenv("LINGBOT_MAX_UPLOAD_BYTES", str(250 * 1024 * 1024))),
            upload_timeout_seconds=int(os.getenv("LINGBOT_UPLOAD_TIMEOUT_SECONDS", "900")),
            max_artifact_bytes=int(os.getenv("LINGBOT_MAX_ARTIFACT_BYTES", str(100 * 1024 * 1024))),
            global_storage_bytes=int(
                os.getenv("LINGBOT_GLOBAL_STORAGE_BYTES", str(20 * 1024 * 1024 * 1024))
            ),
            scene_delivery_budget_bytes=int(
                os.getenv("WAYLINE_SCENE_DELIVERY_BUDGET_BYTES", "2000000000")
            ),
            storage_min_free_bytes=int(
                os.getenv("LINGBOT_STORAGE_MIN_FREE_BYTES", str(1024 * 1024 * 1024))
            ),
            global_max_inflight_objects=int(os.getenv("LINGBOT_GLOBAL_MAX_INFLIGHT_OBJECTS", "8")),
            tenant_max_inflight_objects=int(os.getenv("LINGBOT_TENANT_MAX_INFLIGHT_OBJECTS", "3")),
            max_video_seconds=int(os.getenv("LINGBOT_MAX_VIDEO_SECONDS", str(5 * 60))),
            max_video_frames=int(os.getenv("LINGBOT_MAX_VIDEO_FRAMES", "9000")),
            max_video_dimension=int(os.getenv("LINGBOT_MAX_VIDEO_DIMENSION", "4096")),
            tenant_quota_units=int(os.getenv("LINGBOT_TENANT_QUOTA_UNITS", "10000")),
            tenant_storage_bytes=int(
                os.getenv("LINGBOT_TENANT_STORAGE_BYTES", str(5 * 1024 * 1024 * 1024))
            ),
            tenant_max_assets=int(os.getenv("LINGBOT_TENANT_MAX_ASSETS", "100")),
            tenant_max_unattached_assets=int(
                os.getenv("LINGBOT_TENANT_MAX_UNATTACHED_ASSETS", "10")
            ),
            tenant_max_jobs=int(os.getenv("LINGBOT_TENANT_MAX_JOBS", "500")),
            tenant_max_artifacts=int(os.getenv("LINGBOT_TENANT_MAX_ARTIFACTS", "1500")),
            tenant_max_shares=int(os.getenv("LINGBOT_TENANT_MAX_SHARES", "250")),
            upload_rate_per_minute=int(os.getenv("LINGBOT_UPLOAD_RATE_PER_MINUTE", "10")),
            job_rate_per_minute=int(os.getenv("LINGBOT_JOB_RATE_PER_MINUTE", "30")),
            share_rate_per_minute=int(os.getenv("LINGBOT_SHARE_RATE_PER_MINUTE", "30")),
            terminal_job_retention_seconds=int(
                os.getenv("LINGBOT_TERMINAL_JOB_RETENTION_SECONDS", str(30 * 24 * 60 * 60))
            ),
            unattached_asset_retention_seconds=int(
                os.getenv("LINGBOT_UNATTACHED_ASSET_RETENTION_SECONDS", str(24 * 60 * 60))
            ),
            idempotency_ttl_seconds=int(
                os.getenv("LINGBOT_IDEMPOTENCY_TTL_SECONDS", str(24 * 60 * 60))
            ),
            shutdown_timeout_seconds=int(os.getenv("LINGBOT_SHUTDOWN_TIMEOUT_SECONDS", "30")),
            readiness_probe_ttl_seconds=float(
                os.getenv("LINGBOT_READINESS_PROBE_TTL_SECONDS", "2")
            ),
            worker_poll_seconds=float(os.getenv("LINGBOT_WORKER_POLL_SECONDS", "0.25")),
            job_timeout_seconds=int(os.getenv("LINGBOT_JOB_TIMEOUT_SECONDS", "3600")),
            max_job_attempts=int(os.getenv("LINGBOT_MAX_JOB_ATTEMPTS", "2")),
            public_base_url=public_base_url,
            allowed_hosts=_allowed_hosts(os.getenv("LINGBOT_ALLOWED_HOSTS", ""), public_base_url),
            research_acknowledgement=os.getenv("LINGBOT_RESEARCH_ACK", ""),
            research_command=os.getenv("LINGBOT_RESEARCH_COMMAND", ""),
            checkpoint_path=Path(checkpoint).expanduser().resolve() if checkpoint else None,
            checkpoint_sha256=os.getenv("LINGBOT_CHECKPOINT_SHA256", "").lower(),
            checkpoint_max_bytes=int(
                os.getenv("LINGBOT_CHECKPOINT_MAX_BYTES", str(6 * 1024 * 1024 * 1024))
            ),
            skyseg_path=Path(skyseg).expanduser().resolve() if skyseg else None,
            skyseg_sha256=os.getenv("LINGBOT_SKYSEG_SHA256", "").lower(),
            skyseg_max_bytes=int(os.getenv("LINGBOT_SKYSEG_MAX_BYTES", str(512 * 1024 * 1024))),
            modal_enabled=_bool_env("WAYLINE_MODAL_ENABLED"),
            modal_gpu_seconds_budget=int(os.getenv("WAYLINE_GPU_SECONDS_BUDGET", "14400")),
            google_client_id=os.getenv("WAYLINE_GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("WAYLINE_GOOGLE_CLIENT_SECRET", ""),
            signup_enabled=_bool_env("WAYLINE_SIGNUP_ENABLED"),
            trial_enabled=_bool_env("WAYLINE_TRIAL_ENABLED", True),
            signup_max_accounts=int(os.getenv("WAYLINE_SIGNUP_MAX_ACCOUNTS", "100")),
            trial_max_accounts=int(os.getenv("WAYLINE_TRIAL_MAX_ACCOUNTS", "100")),
            signup_quota_units=int(os.getenv("WAYLINE_SIGNUP_QUOTA_UNITS", "120")),
            generated_bootstrap_token=generated,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.modal_enabled and self.job_timeout_seconds > 3600:
            raise ValueError("Modal jobs require LINGBOT_JOB_TIMEOUT_SECONDS <= 3600")
        if self.modal_gpu_seconds_budget < 600:
            raise ValueError("GPU budget must permit at least one bounded job")
        if min(self.signup_max_accounts, self.trial_max_accounts, self.signup_quota_units) < 1:
            raise ValueError("Wayline account and usage limits must be positive")
        if self.signup_enabled and not (
            self.google_client_id and self.google_client_secret and self.public_base_url
        ):
            raise ValueError("Google sign-up requires client credentials and a public base URL")
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("LINGBOT_ENV must be development, test, or production")
        if self.environment == "production":
            if not self.bootstrap_token or len(self.bootstrap_token) < 32:
                raise ValueError("LINGBOT_BOOTSTRAP_TOKEN must contain at least 32 characters")
            if not self.cookie_secure:
                raise ValueError("production cookies must be secure")
            if self.public_base_url:
                public_url = urlsplit(self.public_base_url)
                public_hostname = public_url.hostname
                if (
                    public_url.scheme != "https"
                    or not public_hostname
                    or public_url.username
                    or public_url.password
                    or public_url.path not in {"", "/"}
                    or public_url.query
                    or public_url.fragment
                ):
                    raise ValueError("production public base URL must be an HTTPS origin")
                if public_hostname.lower() not in self.allowed_hosts:
                    raise ValueError("public base URL host must be in LINGBOT_ALLOWED_HOSTS")
            if not self.allowed_hosts:
                raise ValueError(
                    "production requires LINGBOT_ALLOWED_HOSTS or LINGBOT_PUBLIC_BASE_URL"
                )
        for host in self.allowed_hosts:
            if host == "*" or not HOST_PATTERN.fullmatch(host):
                raise ValueError("allowed hosts must be explicit DNS names or IP addresses")
        if self.bootstrap_token and len(self.bootstrap_token) < 16:
            raise ValueError("bootstrap tokens must contain at least 16 characters")
        bounded_runtime_values = {
            "LINGBOT_SESSION_TTL_SECONDS": self.session_ttl_seconds,
            "LINGBOT_MAX_UPLOAD_BYTES": self.max_upload_bytes,
            "LINGBOT_UPLOAD_TIMEOUT_SECONDS": self.upload_timeout_seconds,
            "LINGBOT_MAX_ARTIFACT_BYTES": self.max_artifact_bytes,
            "LINGBOT_GLOBAL_STORAGE_BYTES": self.global_storage_bytes,
            "WAYLINE_SCENE_DELIVERY_BUDGET_BYTES": self.scene_delivery_budget_bytes,
            "LINGBOT_MAX_VIDEO_SECONDS": self.max_video_seconds,
            "LINGBOT_MAX_VIDEO_FRAMES": self.max_video_frames,
            "LINGBOT_MAX_VIDEO_DIMENSION": self.max_video_dimension,
            "LINGBOT_GLOBAL_MAX_INFLIGHT_OBJECTS": self.global_max_inflight_objects,
            "LINGBOT_TENANT_MAX_INFLIGHT_OBJECTS": self.tenant_max_inflight_objects,
            "LINGBOT_JOB_TIMEOUT_SECONDS": self.job_timeout_seconds,
            "LINGBOT_MAX_JOB_ATTEMPTS": self.max_job_attempts,
            "LINGBOT_CHECKPOINT_MAX_BYTES": self.checkpoint_max_bytes,
            "LINGBOT_SKYSEG_MAX_BYTES": self.skyseg_max_bytes,
        }
        if any(value <= 0 for value in bounded_runtime_values.values()):
            invalid = next(name for name, value in bounded_runtime_values.items() if value <= 0)
            raise ValueError(f"{invalid} must be positive")
        if self.storage_min_free_bytes < 0:
            raise ValueError("LINGBOT_STORAGE_MIN_FREE_BYTES must not be negative")
        if self.upload_timeout_seconds > 900:
            raise ValueError("LINGBOT_UPLOAD_TIMEOUT_SECONDS must not exceed 900")
        if self.max_artifact_bytes > self.global_storage_bytes:
            raise ValueError("artifact limit cannot exceed the global storage limit")
        if self.max_upload_bytes > self.global_storage_bytes:
            raise ValueError("upload limit cannot exceed the global storage limit")
        if self.max_artifact_bytes > self.tenant_storage_bytes:
            raise ValueError("artifact limit cannot exceed the tenant storage limit")
        if self.max_upload_bytes > self.tenant_storage_bytes:
            raise ValueError("upload limit cannot exceed the tenant storage limit")
        if self.tenant_max_inflight_objects > self.global_max_inflight_objects:
            raise ValueError("tenant in-flight limit cannot exceed the global in-flight limit")
        if self.max_job_attempts > 10:
            raise ValueError("LINGBOT_MAX_JOB_ATTEMPTS must not exceed 10")
        if (
            not math.isfinite(self.worker_poll_seconds)
            or self.worker_poll_seconds <= 0
            or self.worker_poll_seconds > 60
        ):
            raise ValueError("LINGBOT_WORKER_POLL_SECONDS must be greater than 0 and at most 60")
        bounded_values = {
            "LINGBOT_TENANT_STORAGE_BYTES": self.tenant_storage_bytes,
            "LINGBOT_TENANT_MAX_ASSETS": self.tenant_max_assets,
            "LINGBOT_TENANT_MAX_UNATTACHED_ASSETS": self.tenant_max_unattached_assets,
            "LINGBOT_TENANT_MAX_JOBS": self.tenant_max_jobs,
            "LINGBOT_TENANT_MAX_ARTIFACTS": self.tenant_max_artifacts,
            "LINGBOT_TENANT_MAX_SHARES": self.tenant_max_shares,
            "LINGBOT_UPLOAD_RATE_PER_MINUTE": self.upload_rate_per_minute,
            "LINGBOT_JOB_RATE_PER_MINUTE": self.job_rate_per_minute,
            "LINGBOT_SHARE_RATE_PER_MINUTE": self.share_rate_per_minute,
            "LINGBOT_TERMINAL_JOB_RETENTION_SECONDS": self.terminal_job_retention_seconds,
            "LINGBOT_UNATTACHED_ASSET_RETENTION_SECONDS": self.unattached_asset_retention_seconds,
            "LINGBOT_IDEMPOTENCY_TTL_SECONDS": self.idempotency_ttl_seconds,
            "LINGBOT_SHUTDOWN_TIMEOUT_SECONDS": self.shutdown_timeout_seconds,
        }
        if any(value <= 0 for value in bounded_values.values()):
            invalid = next(name for name, value in bounded_values.items() if value <= 0)
            raise ValueError(f"{invalid} must be positive")
        if self.tenant_max_unattached_assets > self.tenant_max_assets:
            raise ValueError("unattached asset limit cannot exceed the asset limit")
        if (
            not math.isfinite(self.readiness_probe_ttl_seconds)
            or self.readiness_probe_ttl_seconds < 0
            or self.readiness_probe_ttl_seconds > 30
        ):
            raise ValueError("LINGBOT_READINESS_PROBE_TTL_SECONDS must be between 0 and 30")
        for name, digest in (
            ("LINGBOT_CHECKPOINT_SHA256", self.checkpoint_sha256),
            ("LINGBOT_SKYSEG_SHA256", self.skyseg_sha256),
        ):
            if digest and (
                len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")

    @property
    def research_gate_open(self) -> bool:
        return bool(
            self.research_acknowledgement == RESEARCH_ACKNOWLEDGEMENT
            and self.research_command
            and self.checkpoint_path
            and self.checkpoint_sha256
        )
