"""Workload identity sources for Quartermaster token exchange."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class WorkloadCredential:
    """Upstream identity proof presented to Quartermaster."""

    subject_token: str
    subject_token_type: str


@runtime_checkable
class IdentitySource(Protocol):
    """Obtains workload identity for Quartermaster token exchange."""

    def credential(self) -> WorkloadCredential:
        """Return the current workload identity proof."""
        ...

    def close(self) -> None:
        """Release any held resources."""
        ...
