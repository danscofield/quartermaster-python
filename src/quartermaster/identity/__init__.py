"""Identity source implementations."""

from quartermaster.identity.aws import AWSIdentitySource
from quartermaster.identity.base import IdentitySource, WorkloadCredential
from quartermaster.identity.gcp import GCPIdentitySource
from quartermaster.identity.static import StaticIdentitySource

__all__ = [
    "AWSIdentitySource",
    "GCPIdentitySource",
    "IdentitySource",
    "StaticIdentitySource",
    "WorkloadCredential",
]

try:
    from quartermaster.identity.spire import SPIREIdentitySource

    __all__.append("SPIREIdentitySource")
except ImportError:
    pass
