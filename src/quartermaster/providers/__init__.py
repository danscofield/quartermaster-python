"""Pluggable credential providers."""

from quartermaster.providers.base import CredentialProvider, IssuedToken
from quartermaster.providers.exchange import ExchangeProvider
from quartermaster.providers.sidecar import (
    DEFAULT_SIDECAR_URL,
    SidecarProvider,
    sanitize_name,
    subscription_id,
)

__all__ = [
    "CredentialProvider",
    "DEFAULT_SIDECAR_URL",
    "ExchangeProvider",
    "IssuedToken",
    "SidecarProvider",
    "sanitize_name",
    "subscription_id",
]
