"""GCP workload identity via metadata server."""

from __future__ import annotations

import httpx

from quartermaster.constants import TOKEN_TYPE_GCP_IDENTITY
from quartermaster.identity.base import WorkloadCredential


class GCPIdentitySource:
    """Obtain identity from the GCE metadata identity endpoint."""

    def __init__(
        self,
        *,
        audience: str,
        metadata_host: str = "metadata.google.internal",
        subject_token_type: str = TOKEN_TYPE_GCP_IDENTITY,
        timeout: float = 30.0,
    ) -> None:
        self._audience = audience
        self._metadata_host = metadata_host
        self._subject_token_type = subject_token_type
        self._client = httpx.Client(timeout=timeout)

    def credential(self) -> WorkloadCredential:
        url = (
            f"http://{self._metadata_host}/computeMetadata/v1/"
            f"instance/service-accounts/default/identity"
            f"?audience={self._audience}&format=full"
        )
        resp = self._client.get(url, headers={"Metadata-Flavor": "Google"})
        resp.raise_for_status()
        return WorkloadCredential(
            subject_token=resp.text,
            subject_token_type=self._subject_token_type,
        )

    def close(self) -> None:
        self._client.close()
