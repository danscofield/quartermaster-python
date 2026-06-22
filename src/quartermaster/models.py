"""Data models for Quartermaster and secrets API responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class BilletDiscovery:
    """Response from POST /billets/me."""

    billets: list[str]
    implicit_billets: list[str]
    cedar_billets: list[str]

    @property
    def all_billets(self) -> list[str]:
        """Union of explicit, implicit, and Cedar-derived billets."""
        seen: set[str] = set()
        result: list[str] = []
        for name in self.billets + self.implicit_billets + self.cedar_billets:
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result


@dataclass(frozen=True)
class TokenExchange:
    """Response from POST /token."""

    access_token: str
    token_type: str
    issued_token_type: str
    expires_in: int
    certificate_chain: str | None = None

    @property
    def expires_at(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(seconds=self.expires_in)


@dataclass(frozen=True)
class SecretSummary:
    """Metadata for a secret (no values)."""

    name: str
    owners: list[str]
    retrievers: list[str]
    last_updated: datetime
    can_update: bool


@dataclass(frozen=True)
class Secret(SecretSummary):
    """Full secret including value1/value2."""

    value1: str | None = None
    value2: str | None = None


@dataclass(frozen=True)
class PollEntry:
    """Client state for POST /secrets/poll."""

    name: str
    last_updated: datetime
