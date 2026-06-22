"""Client for qm-secrets (Gringotts) secret retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from quartermaster.config import Settings
from quartermaster.credentials import CredentialManager
from quartermaster.exceptions import APIError
from quartermaster.http_util import build_http_client, parse_error_response
from quartermaster.models import PollEntry, Secret, SecretSummary


class SecretsClient:
    """
    Retrieve secrets from qm-secrets using Quartermaster-issued tokens.

    Tokens are obtained via CredentialManager with the configured
    secrets_audience (default: gringotts.dscof.dev).
    """

    def __init__(
        self,
        credentials: CredentialManager,
        settings: Settings | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._credentials = credentials
        self._settings = settings or credentials.settings
        self._owns_client = http_client is None
        self._client = http_client or build_http_client(tls=self._settings.tls)

    @property
    def base_url(self) -> str:
        return self._settings.secrets_url.rstrip("/")

    def list_secrets(self) -> list[SecretSummary]:
        """GET /secrets — list accessible secret metadata."""
        resp = self._authorized_request("GET", "/secrets")
        body = _check_response(resp)
        if not isinstance(body, list):
            raise APIError("unexpected list secrets response")
        return [_parse_secret_summary(item) for item in body]

    def get_secret(self, name: str) -> Secret:
        """GET /secrets/{name} — retrieve full secret with values."""
        resp = self._authorized_request("GET", f"/secrets/{name}")
        return _parse_secret(_check_response(resp))

    def poll_secrets(self, entries: list[PollEntry]) -> list[SecretSummary]:
        """POST /secrets/poll — detect secrets updated since last known state."""
        payload = {
            "secrets": [
                {
                    "name": entry.name,
                    "last_updated": _format_datetime(entry.last_updated),
                }
                for entry in entries
            ]
        }
        resp = self._authorized_request("POST", "/secrets/poll", json=payload)
        body = _check_response(resp)
        if not isinstance(body, dict):
            raise APIError("unexpected poll response")
        updated = body.get("updated", [])
        if not isinstance(updated, list):
            raise APIError("unexpected poll response")
        return [_parse_secret_summary(item) for item in updated]

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> SecretsClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _authorized_request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        billets: list[str] | None = None,
    ) -> httpx.Response:
        token = self._credentials.get_secrets_token(billets=billets)
        headers = {"Authorization": f"Bearer {token}"}
        return self._client.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            json=json,
        )


def _check_response(resp: httpx.Response) -> Any:
    if resp.is_success:
        if resp.status_code == 204:
            return None
        return resp.json()

    error, description = parse_error_response(resp)
    message = description or error or resp.text or f"HTTP {resp.status_code}"
    raise APIError(
        message,
        status_code=resp.status_code,
        error=error,
        error_description=description,
    )


def _parse_secret_summary(body: dict[str, Any]) -> SecretSummary:
    return SecretSummary(
        name=str(body["name"]),
        owners=_as_str_list(body.get("owners")),
        retrievers=_as_str_list(body.get("retrievers")),
        last_updated=_parse_datetime(body["last_updated"]),
        can_update=bool(body.get("can_update", False)),
    )


def _parse_secret(body: dict[str, Any]) -> Secret:
    summary = _parse_secret_summary(body)
    return Secret(
        name=summary.name,
        owners=summary.owners,
        retrievers=summary.retrievers,
        last_updated=summary.last_updated,
        can_update=summary.can_update,
        value1=body.get("value1"),
        value2=body.get("value2"),
    )


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise APIError(f"invalid datetime: {value!r}")
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
