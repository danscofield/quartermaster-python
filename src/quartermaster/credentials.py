"""Credential manager — unified interface over pluggable providers."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from quartermaster.client import QuartermasterClient
from quartermaster.config import Settings
from quartermaster.identity.base import IdentitySource
from quartermaster.providers.base import CredentialProvider, IssuedToken
from quartermaster.providers.exchange import ExchangeProvider
from quartermaster.providers.sidecar import SidecarProvider


@dataclass
class _CachedToken:
    issued: IssuedToken


class CredentialManager:
    """
    Obtain and cache Quartermaster JWTs within your Python process.

    Accepts any :class:`~quartermaster.providers.CredentialProvider`, including
    direct token exchange (workload identity) and the qm-agentd sidecar.
    """

    def __init__(
        self,
        provider: CredentialProvider | IdentitySource,
        settings: Settings | None = None,
        *,
        client: QuartermasterClient | None = None,
        configured_billets: list[str] | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._configured_billets = configured_billets

        if isinstance(provider, IdentitySource):
            self._provider: CredentialProvider = ExchangeProvider(
                provider,
                self._settings,
                client=client,
                configured_billets=configured_billets,
            )
        else:
            self._provider = provider

        self._lock = threading.Lock()
        self._cache: dict[tuple[tuple[str, ...], str], _CachedToken] = {}

    @classmethod
    def from_identity(
        cls,
        identity: IdentitySource,
        settings: Settings | None = None,
        **kwargs: object,
    ) -> CredentialManager:
        """Create a manager that exchanges workload identity via Quartermaster."""
        return cls(identity, settings, **kwargs)  # type: ignore[arg-type]

    @classmethod
    def from_sidecar(
        cls,
        url: str | None = None,
        settings: Settings | None = None,
    ) -> CredentialManager:
        """Create a manager that reads tokens from a running qm-agentd sidecar."""
        resolved = settings or Settings()
        return cls(SidecarProvider(url, resolved), resolved)

    @property
    def settings(self) -> Settings:
        if hasattr(self._provider, "settings"):
            return self._provider.settings  # type: ignore[no-any-return]
        return self._settings

    def discover_billets(self, *, refresh: bool = False) -> list[str]:
        """Return entitled billets from the active provider."""
        if self._configured_billets is not None:
            return list(self._configured_billets)

        if refresh:
            self.invalidate()

        return self._provider.discover_billets()

    def get_token(
        self,
        *,
        audience: str | None = None,
        billets: list[str] | None = None,
    ) -> str:
        """
        Return a cached or freshly issued access token.

        Args:
            audience: JWT audience for the issued token. Defaults to
                quartermaster_url for general use.
            billets: Optional billet scope. When omitted, uses all entitled
                billets from the provider.
        """
        resolved_audience = audience or self._settings.quartermaster_url
        if billets is not None:
            resolved_billets = tuple(sorted(billets))
        else:
            resolved_billets = tuple(sorted(self.discover_billets()))
        cache_key = (resolved_billets, resolved_audience)

        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and not self._is_expired(cached.issued.expires_at):
                return cached.issued.access_token

            issued = self._provider.issue_token(
                audience=resolved_audience,
                billets=list(resolved_billets) if resolved_billets else None,
            )
            self._cache[cache_key] = _CachedToken(issued=issued)
            return issued.access_token

    def get_secrets_token(self, *, billets: list[str] | None = None) -> str:
        """Return a token with audience configured for qm-secrets (Gringotts)."""
        return self.get_token(
            audience=self._settings.secrets_audience,
            billets=billets,
        )

    def invalidate(self) -> None:
        """Clear cached tokens and any provider-side discovery state."""
        with self._lock:
            self._cache.clear()
        if hasattr(self._provider, "invalidate"):
            self._provider.invalidate()  # type: ignore[attr-defined]

    def close(self) -> None:
        self._provider.close()

    def __enter__(self) -> CredentialManager:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _is_expired(self, expires_at: datetime) -> bool:
        margin = self._settings.refresh_margin.total_seconds()
        now = datetime.now(timezone.utc)
        return (expires_at - now).total_seconds() <= margin
