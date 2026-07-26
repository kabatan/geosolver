"""Contract dataclasses for search/refinement candidates."""

from __future__ import annotations

from dataclasses import dataclass, field

from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import EvaluationStatus
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


@dataclass(frozen=True)
class FloatCandidate:
    """Candidate record in float search space."""

    x_float: tuple[float, ...]
    score: float
    residual_norm_float: float
    guard_ok: bool
    evaluation_status: EvaluationStatus
    origin_seed: int
    origin_start_point_index: int
    candidate_id: int = -1
    hard_feasible: bool = False
    hard_violation_tags: tuple[str, ...] = ()
    validity_margin_float: float | None = None


@dataclass(frozen=True)
class RefinedCandidate:
    """Candidate record in high-precision refinement space."""

    x_hp: tuple[MPFloat, ...]
    residual_norm_hp: MPFloat
    answer_hp: MPFloat | None
    refinement_status: str
    phase_history: tuple[str, ...]
    source: FloatCandidate | None = None
    candidate_id: int = -1
    hard_feasible: bool = False
    hard_violation_tags: tuple[str, ...] = ()
    validity_margin_hp: MPFloat | None = None


@dataclass(frozen=True)
class SearchBatchResult:
    """Batch result returned by global search."""

    candidates: tuple[FloatCandidate, ...]
    evaluation_count: int
    failure_ratio: float
    all_records: tuple[FloatCandidate, ...] = ()
    guard_feasible_ledger: tuple[FloatCandidate, ...] = ()
    search_diagnostics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RefinementBatchResult:
    """Batch result returned by local refinement."""

    candidates: tuple[RefinedCandidate, ...]
    converged_count: int
    attempted_count: int
    solver_name: str = "mpmath_refiner"
    hard_feasible_count: int = 0
    attempted_box_count: int = 0

