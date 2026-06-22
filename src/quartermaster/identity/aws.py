"""AWS workload identity via presigned STS GetCallerIdentity."""

from __future__ import annotations

from quartermaster.constants import TOKEN_TYPE_AWS_PRESIGNED_STS
from quartermaster.identity.base import WorkloadCredential


class AWSIdentitySource:
    """Obtain identity from AWS STS presigned GetCallerIdentity URL."""

    def __init__(
        self,
        *,
        region: str | None = None,
        subject_token_type: str = TOKEN_TYPE_AWS_PRESIGNED_STS,
    ) -> None:
        self._region = region
        self._subject_token_type = subject_token_type

    def credential(self) -> WorkloadCredential:
        try:
            import boto3
        except ImportError as exc:
            raise ImportError(
                "boto3 is required for AWS identity. "
                "Install with: pip install quartermaster[aws]"
            ) from exc

        session = boto3.Session(region_name=self._region)
        sts = session.client("sts")
        presigned = sts.generate_presigned_url(
            "get_caller_identity",
            Params={},
            ExpiresIn=60,
            HttpMethod="GET",
        )
        return WorkloadCredential(
            subject_token=presigned,
            subject_token_type=self._subject_token_type,
        )

    def close(self) -> None:
        pass
