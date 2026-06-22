# quartermaster-py

Python library for obtaining Quartermaster credentials and fetching secrets from qm-secrets (Gringotts) — an in-process alternative to the [qm-agent](https://github.com/dscof/qm-agent) credential sidecar.

## Installation

```bash
pip install -e ".[dev]"        # core + dev tools
pip install -e ".[aws]"          # AWS workload identity
pip install -e ".[spire]"        # SPIRE JWT identity
```

## Quick start

### Obtain credentials (sidecar replacement)

```python
from quartermaster import CredentialManager, Settings
from quartermaster.identity import AWSIdentitySource

settings = Settings(
    quartermaster_url="https://quartermaster.dscof.dev",
    secrets_url="https://gringotts.dscof.dev",
    secrets_audience="gringotts.dscof.dev",
)

with CredentialManager(AWSIdentitySource(), settings) as creds:
    # Token for calling qm-secrets
    token = creds.get_secrets_token()

    # Token for another audience (e.g. downstream API)
    api_token = creds.get_token(audience="https://api.example.com")
```

### Fetch secrets from Gringotts

```python
from quartermaster import CredentialManager, SecretsClient, Settings
from quartermaster.identity import GCPIdentitySource

settings = Settings.from_env()

identity = GCPIdentitySource(audience=settings.quartermaster_url)

with CredentialManager(identity, settings) as creds:
    with SecretsClient(creds, settings) as secrets:
        secret = secrets.get_secret("my-app/config")
        print(secret.value1, secret.value2)
```

### Use with a running qm-agentd sidecar

When `qm-agentd` is already running alongside your workload, use it as the credential provider instead of exchanging identity in-process:

```python
from quartermaster import CredentialManager, SecretsClient, Settings

settings = Settings.from_env()

with CredentialManager.from_sidecar(settings=settings) as creds:
    with SecretsClient(creds, settings) as secrets:
        secret = secrets.get_secret("my-app/config")
```

Or plug the provider in directly:

```python
from quartermaster import SidecarProvider, CredentialManager

provider = SidecarProvider("http://127.0.0.1:8765")
with CredentialManager(provider) as creds:
    token = creds.get_secrets_token(billets=["team-a"])
```

The sidecar provider uses `POST /subscriptions` so tokens can be requested with any audience (e.g. `gringotts.dscof.dev` for secrets).

## Configuration

All settings are configurable via `Settings` or environment variables:

| Setting | Env var | Default |
|---------|---------|---------|
| Quartermaster URL | `QM_QUARTERMASTER_URL` | `https://quartermaster.dscof.dev` |
| Secrets URL | `QM_SECRETS_URL` | `https://gringotts.dscof.dev` |
| Secrets token audience | `QM_SECRETS_AUDIENCE` | `gringotts.dscof.dev` |
| Sidecar URL | `QM_SIDECAR_URL` | `http://127.0.0.1:8765` |
| Refresh margin (seconds) | `QM_REFRESH_MARGIN_SECS` | `300` |
| CA file | `QM_CA_FILE` | — |
| Client cert | `QM_CERT_FILE` | — |
| Client key | `QM_KEY_FILE` | — |

```python
settings = Settings.from_env()
```

## Identity sources

The library supports the same upstream identity proofs as qm-agent:

| Source | Class | Extra dependency |
|--------|-------|------------------|
| AWS | `AWSIdentitySource` | `boto3` |
| GCP | `GCPIdentitySource` | — |
| SPIRE JWT | `SPIREIdentitySource` | `pyspiffe` |
| Static (tests) | `StaticIdentitySource` | — |
| qm-agentd sidecar | `SidecarProvider` | — |

## Credential providers

Modular backends implement `CredentialProvider`:

| Provider | Class | Use when |
|----------|-------|----------|
| Direct exchange | `ExchangeProvider` | Python obtains workload identity itself |
| Sidecar | `SidecarProvider` | `qm-agentd` is running locally |

`CredentialManager` accepts any provider, or an `IdentitySource` for backward compatibility (wrapped as `ExchangeProvider`).

**AWS example:**

```python
from quartermaster.identity import AWSIdentitySource

identity = AWSIdentitySource(region="us-east-1")
```

**GCP example:**

```python
from quartermaster.identity import GCPIdentitySource

identity = GCPIdentitySource(audience="https://quartermaster.dscof.dev")
```

**SPIRE example:**

```python
from quartermaster.identity import SPIREIdentitySource

identity = SPIREIdentitySource(
    jwt_audience="quartermaster.dscof.dev",
    socket_path="unix:///tmp/spire-agent/public/api.sock",
)
```

## How it works

1. **Identity** — obtain a workload proof (AWS presigned STS URL, GCP metadata token, SPIRE JWT, etc.)
2. **Billet discovery** — `POST /billets/me` on Quartermaster (skipped if billets are configured explicitly)
3. **Token exchange** — `POST /token` with `audience=gringotts.dscof.dev` for secrets access
4. **Secrets retrieval** — `GET /secrets/{name}` on Gringotts with `Authorization: Bearer <token>`

Tokens are cached and refreshed automatically before expiry (default: 5 minutes before).

## API reference

### `CredentialManager`

- `discover_billets()` — list entitled billets
- `get_token(audience=..., billets=...)` — exchange and cache a JWT
- `get_secrets_token(billets=...)` — shortcut with `secrets_audience`
- `invalidate()` — clear cache

### `SecretsClient`

- `list_secrets()` — metadata only
- `get_secret(name)` — full secret with `value1` / `value2`
- `poll_secrets(entries)` — detect changed secrets since last known `last_updated`

### `QuartermasterClient`

Low-level client for direct API access (`discover_billets`, `exchange_token`).

## Development

```bash
pip install -e ".[dev]"
pytest
```
