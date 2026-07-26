"""Contract dataclasses for exact identification and final pipeline output."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver._internal.pipeline.contracts.candidate_record import FloatCandidate, RefinedCandidate
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


@dataclass(frozen=True)
class ExactIdentificationResult:
    """Exact-identification result for one accepted candidate."""

    exact_status: str
    identification_method: str
    input_precision_dps: int
    minimal_polynomial: tuple[int, ...] | None
    polynomial_degree: int | None
    selected_exact_value: str | None
    verification_residual: MPFloat | None
    numeric_fallback_value: MPFloat | None


@dataclass(frozen=True)
class ExternalPipelineResult:
    """Top-level contract returned by external pipeline orchestration.

    The ``summary`` payload is expected to include stable top-level keys:
    ``phase0``, ``phasea``, ``phaseb``, ``phasec``, ``phase_rescue``,
    ``phase_integer_fallback``, and ``debug_candidates``.
    """

    status: str
    selected_answer: MPFloat | None
    accepted_answers: tuple[MPFloat, ...]
    float_candidates: tuple[FloatCandidate, ...]
    refined_candidates: tuple[RefinedCandidate, ...]
    exact_results: tuple[ExactIdentificationResult, ...]
    summary: dict[str, object]
    accepted_candidate_ids: tuple[int, ...] = ()

