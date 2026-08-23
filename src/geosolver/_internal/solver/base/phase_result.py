"""Standardized phase execution result type."""

from dataclasses import dataclass, field
from typing import Any

from .failure_reason import SolverFailureReason


@dataclass
class PhaseResult:
    """Result object returned by each solver phase."""

    success: bool
    phase: str
    payload: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    failure_reason: SolverFailureReason | None = None
