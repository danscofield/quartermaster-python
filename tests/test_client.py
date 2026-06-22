"""Tests for the Quartermaster client library."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from quartermaster.client import QuartermasterClient
from quartermaster.config import Settings
from quartermaster.credentials import CredentialManager
from quartermaster.identity.static import StaticIdentitySource
from quartermaster.models import PollEntry
from quartermaster.secrets import SecretsClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        quartermaster_url="https://quartermaster.test",
        secrets_url="https://gringotts.test",
        secrets_audience="gringotts.test",
    )


@pytest.fixture
def identity() -> StaticIdentitySource:
    return StaticIdentitySource(
        subject_token="upstream-token",
        subject_token_type="urn:ietf:params:oauth:token-type:jwt",
    )


@respx.mock
def test_discover_billets(settings: Settings, identity: StaticIdentitySource) -> None:
    respx.post("https://quartermaster.test/billets/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "billets": ["team-a"],
                "implicit_billets": ["team-b"],
                "cedar_billets": ["team-a"],
            },
        )
    )

    with QuartermasterClient(settings) as client:
        discovery = client.discover_billets(identity.credential())

    assert discovery.all_billets == ["team-a", "team-b"]


@respx.mock
def test_exchange_token(settings: Settings, identity: StaticIdentitySource) -> None:
    route = respx.post("https://quartermaster.test/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "issued-jwt",
                "token_type": "Bearer",
                "issued_token_type": "urn:ietf:params:oauth:token-type:jwt",
                "expires_in": 3600,
            },
        )
    )

    with QuartermasterClient(settings) as client:
        token = client.exchange_token(
            audience="gringotts.test",
            identity=identity.credential(),
            billets=["team-a"],
        )

    assert token.access_token == "issued-jwt"
    assert route.calls.last.request.url.path == "/token"
    body = route.calls.last.request.content.decode()
    assert "audience=gringotts.test" in body
    assert "billets=team-a" in body


@respx.mock
def test_credential_manager_caches_tokens(
    settings: Settings, identity: StaticIdentitySource
) -> None:
    route = respx.post("https://quartermaster.test/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "cached-jwt",
                "token_type": "Bearer",
                "issued_token_type": "urn:ietf:params:oauth:token-type:jwt",
                "expires_in": 3600,
            },
        )
    )

    with CredentialManager(identity, settings, configured_billets=["team-a"]) as creds:
        first = creds.get_secrets_token()
        second = creds.get_secrets_token()

    assert first == "cached-jwt"
    assert second == "cached-jwt"
    assert len(route.calls) == 1


@respx.mock
def test_get_secret(settings: Settings, identity: StaticIdentitySource) -> None:
    respx.post("https://quartermaster.test/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "secrets-jwt",
                "token_type": "Bearer",
                "issued_token_type": "urn:ietf:params:oauth:token-type:jwt",
                "expires_in": 3600,
            },
        )
    )
    respx.get("https://gringotts.test/secrets/my-app/config").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "my-app/config",
                "owners": ["team-a"],
                "retrievers": ["team-b"],
                "value1": "green",
                "value2": "blue",
                "last_updated": "2026-06-21T14:30:00Z",
                "can_update": False,
            },
        )
    )

    with CredentialManager(identity, settings, configured_billets=["team-a"]) as creds:
        with SecretsClient(creds, settings) as secrets:
            secret = secrets.get_secret("my-app/config")

    assert secret.value1 == "green"
    assert secret.value2 == "blue"


@respx.mock
def test_poll_secrets(settings: Settings, identity: StaticIdentitySource) -> None:
    respx.post("https://quartermaster.test/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "secrets-jwt",
                "token_type": "Bearer",
                "issued_token_type": "urn:ietf:params:oauth:token-type:jwt",
                "expires_in": 3600,
            },
        )
    )
    respx.post("https://gringotts.test/secrets/poll").mock(
        return_value=httpx.Response(
            200,
            json={
                "updated": [
                    {
                        "name": "my-app/config",
                        "owners": ["team-a"],
                        "retrievers": [],
                        "last_updated": "2026-06-21T15:00:00Z",
                        "can_update": True,
                    }
                ]
            },
        )
    )

    with CredentialManager(identity, settings, configured_billets=["team-a"]) as creds:
        with SecretsClient(creds, settings) as secrets:
            updated = secrets.poll_secrets(
                [
                    PollEntry(
                        name="my-app/config",
                        last_updated=datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc),
                    )
                ]
            )

    assert len(updated) == 1
    assert updated[0].name == "my-app/config"
