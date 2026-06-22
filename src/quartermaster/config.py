"""Configuration for Quartermaster and secrets clients."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta


DEFAULT_QUARTERMASTER_URL = "https://quartermaster.dscof.dev"
DEFAULT_SECRETS_URL = "https://gringotts.dscof.dev"
DEFAULT_SECRETS_AUDIENCE = "gringotts.dscof.dev"
DEFAULT_SIDECAR_URL = "http://127.0.0.1:8765"


@dataclass
class TLSConfig:
    """Optional mTLS settings for Quartermaster connections."""

    ca_file: str | None = None
    cert_file: str | None = None
    key_file: str | None = None


@dataclass
class Settings:
    """Client configuration with sensible defaults for dscof.dev deployments."""

    quartermaster_url: str = DEFAULT_QUARTERMASTER_URL
    secrets_url: str = DEFAULT_SECRETS_URL
    secrets_audience: str = DEFAULT_SECRETS_AUDIENCE
    sidecar_url: str = DEFAULT_SIDECAR_URL
    refresh_margin: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    tls: TLSConfig = field(default_factory=TLSConfig)

    @classmethod
    def from_env(cls) -> Settings:
        """Load settings from environment variables."""
        margin_secs = os.environ.get("QM_REFRESH_MARGIN_SECS")
        refresh_margin = (
            timedelta(seconds=int(margin_secs))
            if margin_secs
            else timedelta(minutes=5)
        )
        return cls(
            quartermaster_url=os.environ.get(
                "QM_QUARTERMASTER_URL", DEFAULT_QUARTERMASTER_URL
            ),
            secrets_url=os.environ.get("QM_SECRETS_URL", DEFAULT_SECRETS_URL),
            secrets_audience=os.environ.get(
                "QM_SECRETS_AUDIENCE", DEFAULT_SECRETS_AUDIENCE
            ),
            sidecar_url=os.environ.get("QM_SIDECAR_URL", DEFAULT_SIDECAR_URL),
            refresh_margin=refresh_margin,
            tls=TLSConfig(
                ca_file=os.environ.get("QM_CA_FILE"),
                cert_file=os.environ.get("QM_CERT_FILE"),
                key_file=os.environ.get("QM_KEY_FILE"),
            ),
        )
