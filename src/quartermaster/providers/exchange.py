"""Direct Quartermaster token exchange via workload identity."""

from __future__ import annotations

from quartermaster.client import QuartermasterClient
from quartermaster.config import Settings
from quartermaster.identity.base import IdentitySource
from quartermaster.providers.base import IssuedToken


class ExchangeProvider:
    """Exchange workload identity for Quartermaster JWTs."""

    def __init__(
        self,
        identity: IdentitySource,
        settings: Settings | None = None,
        *,
        client: QuartermasterClient | None = None,
        configured_billets: list[str] | None = None,
    ) -> None:
        self._identity = identity
        self._settings = settings or Settings()
        self._client = client or QuartermasterClient(self._settings)
        self._owns_client = client is None
        self._configured_billets = configured_billets
        self._discovered_billets: list[str] | None = None

    @property
    def settings(self) -> Settings:
        return self._settings

    def discover_billets(self) -> list[str]:
        if self._configured_billets is not None:
            return list(self._configured_billets)

        if self._discovered_billets is not None:
            return list(self._discovered_billets)

        identity = self._identity.credential()
        discovery = self._client.discover_billets(identity)
        self._discovered_billets = discovery.all_billets
        return list(self._discovered_billets)

    def issue_token(
        self,
        *,
        audience: str,
        billets: list[str] | None = None,
    ) -> IssuedToken:
        if billets is not None:
            resolved_billets = list(billets)
        else:
            resolved_billets = self.discover_billets()

        identity = self._identity.credential()
        exchange = self._client.exchange_token(
            audience=audience,
            identity=identity,
            billets=resolved_billets or None,
        )
        return IssuedToken(
            access_token=exchange.access_token,
            expires_at=exchange.expires_at,
        )

    def invalidate(self) -> None:
        self._discovered_billets = None

    def close(self) -> None:
        self._identity.close()
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ExchangeProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
