"""Tests for the sidecar credential provider."""

from __future__ import annotations

import httpx
import pytest
import respx

from quartermaster.config import Settings
from quartermaster.credentials import CredentialManager
from quartermaster.providers.sidecar import (
    SidecarProvider,
    sanitize_name,
    subscription_id,
)
from quartermaster.secrets import SecretsClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        sidecar_url="http://127.0.0.1:8765",
        secrets_url="https://gringotts.test",
        secrets_audience="gringotts.test",
    )


def test_subscription_id_matches_sidecar_format() -> None:
    assert subscription_id(["payments", "analytics"], "https://api.example.com") == (
        "analytics__payments__aud__https_api.example.com"
    )
    assert sanitize_name("my-app/config") == "my-app_config"


@respx.mock
def test_sidecar_provider_issues_token(settings: Settings) -> None:
    respx.get("http://127.0.0.1:8765/manifest.json").mock(
        return_value=httpx.Response(
            200,
            json={"available": ["team-a", "team-b"], "updated_at": "2026-06-22T00:00:00Z"},
        )
    )
    respx.post("http://127.0.0.1:8765/subscriptions").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "team-a__aud__gringotts.test",
                "billets": ["team-a"],
                "audience": "gringotts.test",
                "status": "ready",
                "expires_at": "2026-06-22T01:00:00Z",
                "token_path": "/subscriptions/team-a__aud__gringotts.test/token",
            },
        )
    )
    respx.get(
        "http://127.0.0.1:8765/subscriptions/team-a__aud__gringotts.test/token"
    ).mock(return_value=httpx.Response(200, text="sidecar-jwt"))

    with SidecarProvider(settings=settings) as provider:
        token = provider.issue_token(
            audience="gringotts.test",
            billets=["team-a"],
        )

    assert token.access_token == "sidecar-jwt"


@respx.mock
def test_sidecar_provider_waits_for_pending_subscription(settings: Settings) -> None:
    respx.get("http://127.0.0.1:8765/manifest.json").mock(
        return_value=httpx.Response(
            200,
            json={"available": ["team-a"], "updated_at": "2026-06-22T00:00:00Z"},
        )
    )
    respx.post("http://127.0.0.1:8765/subscriptions").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "team-a__aud__gringotts.test",
                "billets": ["team-a"],
                "audience": "gringotts.test",
                "status": "pending",
                "token_path": "/subscriptions/team-a__aud__gringotts.test/token",
            },
        )
    )
    respx.get("http://127.0.0.1:8765/subscriptions/team-a__aud__gringotts.test").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "id": "team-a__aud__gringotts.test",
                    "billets": ["team-a"],
                    "audience": "gringotts.test",
                    "status": "pending",
                    "token_path": "/subscriptions/team-a__aud__gringotts.test/token",
                },
            ),
            httpx.Response(
                200,
                json={
                    "id": "team-a__aud__gringotts.test",
                    "billets": ["team-a"],
                    "audience": "gringotts.test",
                    "status": "ready",
                    "expires_at": "2026-06-22T01:00:00Z",
                    "token_path": "/subscriptions/team-a__aud__gringotts.test/token",
                },
            ),
        ]
    )
    respx.get(
        "http://127.0.0.1:8765/subscriptions/team-a__aud__gringotts.test/token"
    ).mock(return_value=httpx.Response(200, text="ready-jwt"))

    provider = SidecarProvider(settings=settings, poll_interval=0.01, poll_timeout=1.0)
    try:
        token = provider.issue_token(audience="gringotts.test", billets=["team-a"])
    finally:
        provider.close()

    assert token.access_token == "ready-jwt"


@respx.mock
def test_credential_manager_from_sidecar(settings: Settings) -> None:
    respx.get("http://127.0.0.1:8765/manifest.json").mock(
        return_value=httpx.Response(
            200,
            json={"available": ["team-a"], "updated_at": "2026-06-22T00:00:00Z"},
        )
    )
    respx.post("http://127.0.0.1:8765/subscriptions").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "team-a__aud__gringotts.test",
                "billets": ["team-a"],
                "audience": "gringotts.test",
                "status": "ready",
                "expires_at": "2026-06-22T01:00:00Z",
                "token_path": "/subscriptions/team-a__aud__gringotts.test/token",
            },
        )
    )
    respx.get(
        "http://127.0.0.1:8765/subscriptions/team-a__aud__gringotts.test/token"
    ).mock(return_value=httpx.Response(200, text="secrets-jwt"))
    respx.get("https://gringotts.test/secrets/my-app/config").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "my-app/config",
                "owners": ["team-a"],
                "retrievers": [],
                "value1": "green",
                "value2": "blue",
                "last_updated": "2026-06-21T14:30:00Z",
                "can_update": False,
            },
        )
    )

    with CredentialManager.from_sidecar(settings=settings) as creds:
        with SecretsClient(creds, settings) as secrets:
            secret = secrets.get_secret("my-app/config")

    assert secret.value1 == "green"
