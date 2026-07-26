"""Protocol for exact-identification adapters."""

from __future__ import annotations

from typing import Protocol

from .candidate_record import RefinedCandidate
from .pipeline_result import ExactIdentificationResult


class ExactIdentifierPort(Protocol):
    """Exact-identification contract."""

    def identify_exact(
        self,
        *,
        candidates: tuple[RefinedCandidate, ...],
        precision_dps: int,
    ) -> tuple[ExactIdentificationResult, ...]:
        """Run exact identification for refined candidates."""

