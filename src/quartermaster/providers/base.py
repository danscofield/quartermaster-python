"""Credential provider abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class IssuedToken:
    """A Quartermaster-issued access token and its expiry."""

    access_token: str
    expires_at: datetime


@runtime_checkable
class CredentialProvider(Protocol):
    """
    Obtains Quartermaster JWTs from some backend.

    Implementations include direct token exchange (workload identity) and
    the qm-agentd sidecar HTTP API.
    """

    def discover_billets(self) -> list[str]:
        """Return entitled billet names."""
        ...

    def issue_token(
        self,
        *,
        audience: str,
        billets: list[str] | None = None,
    ) -> IssuedToken:
        """Obtain an access token for the given audience and billet scope."""
        ...

    def close(self) -> None:
        """Release any held resources."""
        ...
