"""Quartermaster credential vending and secrets client library."""

from quartermaster.client import QuartermasterClient
from quartermaster.config import Settings
from quartermaster.credentials import CredentialManager
from quartermaster.exceptions import QuartermasterError
from quartermaster.providers import (
    CredentialProvider,
    ExchangeProvider,
    SidecarProvider,
)
from quartermaster.secrets import SecretsClient

__all__ = [
    "CredentialManager",
    "CredentialProvider",
    "ExchangeProvider",
    "QuartermasterClient",
    "QuartermasterError",
    "SecretsClient",
    "Settings",
    "SidecarProvider",
]

__version__ = "0.1.0"
