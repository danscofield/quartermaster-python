"""Low-level Quartermaster broker API client."""

from __future__ import annotations

from typing import Any

import httpx

from quartermaster.config import Settings
from quartermaster.constants import GRANT_TYPE_TOKEN_EXCHANGE
from quartermaster.exceptions import APIError
from quartermaster.http_util import build_http_client, parse_error_response
from quartermaster.identity.base import WorkloadCredential
from quartermaster.models import BilletDiscovery, TokenExchange


class QuartermasterClient:
    """HTTP client for the Quartermaster credential vending API."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._owns_client = http_client is None
        self._client = http_client or build_http_client(tls=self._settings.tls)

    @property
    def base_url(self) -> str:
        return self._settings.quartermaster_url.rstrip("/")

    def discover_billets(
        self,
        identity: WorkloadCredential | None = None,
    ) -> BilletDiscovery:
        """POST /billets/me — discover entitled billets without issuing a token."""
        data = _identity_form(identity)
        resp = self._client.post(
            f"{self.base_url}/billets/me",
            data=data,
        )
        return _parse_billet_discovery(_check_response(resp))

    def exchange_token(
        self,
        *,
        audience: str,
        identity: WorkloadCredential | None = None,
        billets: list[str] | None = None,
        grant_type: str = GRANT_TYPE_TOKEN_EXCHANGE,
    ) -> TokenExchange:
        """POST /token — RFC 8693 token exchange."""
        data: dict[str, str] = {
            "grant_type": grant_type,
            "audience": audience,
        }
        data.update(_identity_form(identity))
        if billets:
            data["billets"] = ",".join(billets)

        resp = self._client.post(f"{self.base_url}/token", data=data)
        return _parse_token_exchange(_check_response(resp))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> QuartermasterClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _identity_form(identity: WorkloadCredential | None) -> dict[str, str]:
    if identity is None:
        return {}
    return {
        "subject_token": identity.subject_token,
        "subject_token_type": identity.subject_token_type,
    }


def _check_response(resp: httpx.Response) -> dict[str, Any]:
    if resp.is_success:
        body = resp.json()
        if not isinstance(body, dict):
            raise APIError(
                "unexpected response body",
                status_code=resp.status_code,
            )
        return body

    error, description = parse_error_response(resp)
    message = description or error or resp.text or f"HTTP {resp.status_code}"
    raise APIError(
        message,
        status_code=resp.status_code,
        error=error,
        error_description=description,
    )


def _parse_billet_discovery(body: dict[str, Any]) -> BilletDiscovery:
    return BilletDiscovery(
        billets=_as_str_list(body.get("billets")),
        implicit_billets=_as_str_list(body.get("implicit_billets")),
        cedar_billets=_as_str_list(body.get("cedar_billets")),
    )


def _parse_token_exchange(body: dict[str, Any]) -> TokenExchange:
    try:
        return TokenExchange(
            access_token=str(body["access_token"]),
            token_type=str(body.get("token_type", "Bearer")),
            issued_token_type=str(body["issued_token_type"]),
            expires_in=int(body["expires_in"]),
            certificate_chain=body.get("certificate_chain"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise APIError("invalid token exchange response") from exc


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
