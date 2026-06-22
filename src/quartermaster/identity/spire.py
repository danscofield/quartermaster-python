"""SPIRE workload identity via the SPIFFE Workload API."""

from __future__ import annotations

from quartermaster.constants import TOKEN_TYPE_SPIRE_JWT
from quartermaster.identity.base import WorkloadCredential


class SPIREIdentitySource:
    """Obtain JWT SVID from a local SPIRE agent."""

    def __init__(
        self,
        *,
        jwt_audience: str,
        socket_path: str = "unix:///tmp/spire-agent/public/api.sock",
    ) -> None:
        try:
            from pyspiffe.workloadapi import WorkloadApiClient
        except ImportError as exc:
            raise ImportError(
                "pyspiffe is required for SPIRE identity. "
                "Install with: pip install quartermaster[spire]"
            ) from exc

        self._jwt_audience = jwt_audience
        self._client = WorkloadApiClient(socket_path)

    def credential(self) -> WorkloadCredential:
        svid = self._client.fetch_jwt_svid(audience=[self._jwt_audience])
        return WorkloadCredential(
            subject_token=svid.token,
            subject_token_type=TOKEN_TYPE_SPIRE_JWT,
        )

    def close(self) -> None:
        self._client.close()
