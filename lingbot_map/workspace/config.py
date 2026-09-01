"""Runtime configuration with production-safe defaults."""

from __future__ import annotations

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
    max_video_seconds: int = 5 * 60
    max_video_frames: int = 9_000
    max_video_dimension: int = 4_096
    tenant_quota_units: int = 10_000
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
            max_video_seconds=int(os.getenv("LINGBOT_MAX_VIDEO_SECONDS", str(5 * 60))),
            max_video_frames=int(os.getenv("LINGBOT_MAX_VIDEO_FRAMES", "9000")),
            max_video_dimension=int(os.getenv("LINGBOT_MAX_VIDEO_DIMENSION", "4096")),
            tenant_quota_units=int(os.getenv("LINGBOT_TENANT_QUOTA_UNITS", "10000")),
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
            generated_bootstrap_token=generated,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
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
        if self.max_upload_bytes <= 0 or self.max_video_seconds <= 0:
            raise ValueError("upload limits must be positive")
        if self.max_job_attempts < 1:
            raise ValueError("max job attempts must be at least one")
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
