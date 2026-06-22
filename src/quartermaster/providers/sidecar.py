"""qm-agentd sidecar credential provider."""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from quartermaster.config import Settings
from quartermaster.exceptions import APIError
from quartermaster.providers.base import IssuedToken

_UNSAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
DEFAULT_SIDECAR_URL = "http://127.0.0.1:8765"


def sanitize_name(name: str) -> str:
    """Match qm-agentd path sanitization for billet and audience names."""
    trimmed = name.strip()
    if not trimmed:
        return "_"
    return _UNSAFE_NAME.sub("_", trimmed)


def subscription_id(billets: list[str], audience: str) -> str:
    """Compute the sidecar subscription id for a billet set and audience."""
    parts = [sanitize_name(b) for b in sorted(billets)]
    sub_id = "__".join(parts)
    sanitized_audience = sanitize_name(audience)
    if sanitized_audience:
        sub_id += f"__aud__{sanitized_audience}"
    return sub_id


class SidecarProvider:
    """
    Obtain Quartermaster JWTs from a running qm-agentd sidecar.

    Uses the sidecar subscription API so tokens can be requested with an
    arbitrary audience (e.g. gringotts.dscof.dev for secrets access).
    """

    def __init__(
        self,
        url: str | None = None,
        settings: Settings | None = None,
        *,
        http_client: httpx.Client | None = None,
        poll_interval: float = 0.25,
        poll_timeout: float = 30.0,
    ) -> None:
        self._settings = settings or Settings()
        self._base_url = (url or self._settings.sidecar_url).rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=30.0)
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout

    @property
    def settings(self) -> Settings:
        return self._settings

    def discover_billets(self) -> list[str]:
        manifest = self._get_manifest()
        available = manifest.get("available", [])
        if not isinstance(available, list):
            raise APIError("invalid sidecar manifest: available is not a list")
        return [str(name) for name in available]

    def issue_token(
        self,
        *,
        audience: str,
        billets: list[str] | None = None,
    ) -> IssuedToken:
        resolved_billets = billets or self.discover_billets()
        if not resolved_billets:
            raise APIError("no billets available from sidecar")

        subscription = self._ensure_subscription(resolved_billets, audience)
        token = self._fetch_subscription_token(str(subscription["id"]))
        expires_at = _parse_expires_at(subscription.get("expires_at"))
        return IssuedToken(access_token=token, expires_at=expires_at)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> SidecarProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _get_manifest(self) -> dict[str, Any]:
        resp = self._client.get(f"{self._base_url}/manifest.json")
        return _check_json_response(resp)

    def _ensure_subscription(
        self,
        billets: list[str],
        audience: str,
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"{self._base_url}/subscriptions",
            json={"billets": billets, "audience": audience},
        )
        subscription = _check_json_response(resp)
        if not isinstance(subscription, dict) or "id" not in subscription:
            raise APIError("invalid sidecar subscription response")

        if subscription.get("status") == "ready":
            return subscription

        return self._wait_for_subscription(str(subscription["id"]))

    def _wait_for_subscription(self, sub_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._poll_timeout
        while time.monotonic() < deadline:
            resp = self._client.get(f"{self._base_url}/subscriptions/{sub_id}")
            subscription = _check_json_response(resp)
            if subscription.get("status") == "ready":
                return subscription
            time.sleep(self._poll_interval)

        raise APIError(
            f"sidecar subscription {sub_id!r} not ready after {self._poll_timeout}s",
            error="subscription_not_ready",
        )

    def _fetch_subscription_token(self, sub_id: str) -> str:
        resp = self._client.get(f"{self._base_url}/subscriptions/{sub_id}/token")
        if not resp.is_success:
            error, description = _parse_plain_error(resp)
            message = description or error or resp.text or f"HTTP {resp.status_code}"
            raise APIError(message, status_code=resp.status_code, error=error)
        return resp.text


def _check_json_response(resp: httpx.Response) -> dict[str, Any]:
    if not resp.is_success:
        error, description = _parse_plain_error(resp)
        message = description or error or resp.text or f"HTTP {resp.status_code}"
        raise APIError(message, status_code=resp.status_code, error=error)

    body = resp.json()
    if not isinstance(body, dict):
        raise APIError("unexpected sidecar response body")
    return body


def _parse_plain_error(resp: httpx.Response) -> tuple[str | None, str | None]:
    text = resp.text.strip()
    if not text:
        return None, None
    try:
        body = resp.json()
    except ValueError:
        return None, text
    if isinstance(body, dict):
        error = body.get("error")
        return (
            str(error) if error is not None else None,
            str(error) if error is not None else text,
        )
    return None, text


def _parse_expires_at(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    # Sidecar should always return expires_at; fall back to a short TTL.
    return datetime.now(timezone.utc) + timedelta(hours=1)
