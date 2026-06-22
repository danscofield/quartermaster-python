"""Static identity for testing or pre-obtained tokens."""

from __future__ import annotations

from quartermaster.identity.base import WorkloadCredential


class StaticIdentitySource:
    """Use a fixed subject token (useful for tests or custom integrations)."""

    def __init__(self, subject_token: str, subject_token_type: str) -> None:
        self._credential = WorkloadCredential(
            subject_token=subject_token,
            subject_token_type=subject_token_type,
        )

    def credential(self) -> WorkloadCredential:
        return self._credential

    def close(self) -> None:
        pass
