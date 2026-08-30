"""Contract dataclasses for search/refinement candidates."""

from __future__ import annotations

from dataclasses import dataclass, field

from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


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
    origin_phase: str = "search"
    origin_backend: str = "unknown"
    origin_attempt: int = 0
    origin_box_index: int | None = None
    origin_evaluation_index: int | None = None

    @property
    def candidate_uid(self) -> str:
        """Return the deterministic, human-readable provenance identity."""

        box = "-" if self.origin_box_index is None else str(self.origin_box_index)
        evaluation = (
            "-" if self.origin_evaluation_index is None else str(self.origin_evaluation_index)
        )
        return "/".join(
            (
                self.origin_phase,
                self.origin_backend,
                str(self.origin_attempt),
                box,
                str(self.origin_seed),
                str(self.origin_start_point_index),
                evaluation,
            )
        )


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
    revision: int = 0
    # Working precision, not a claim that every stored digit is accurate.
    # The corresponding uncertainty fields carry the accuracy estimates.
    coordinate_precision_dps: int = 0
    answer_precision_dps: int = 0
    coordinate_uncertainty: tuple[MPFloat, ...] = ()
    answer_uncertainty: MPFloat | None = None
    branch_trace: tuple[object, ...] = ()
    verification_history: tuple[dict[str, object], ...] = ()

    @property
    def candidate_uid(self) -> str:
        if self.source is not None:
            return self.source.candidate_uid
        return f"refinement/direct/0/-/-1/{self.candidate_id}/-"


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


def assert_candidate_id_consistency(candidates: tuple[FloatCandidate, ...]) -> None:
    """Reject integer-ID collisions that refer to different candidate records."""

    by_id: dict[int, tuple[tuple[float, ...], str]] = {}
    for candidate in candidates:
        candidate_id = int(candidate.candidate_id)
        previous = by_id.get(candidate_id)
        current = (tuple(candidate.x_float), candidate.candidate_uid)
        if previous is not None and previous != current:
            raise RuntimeError(
                "candidate ID collision: "
                f"{candidate_id} identifies both {previous!r} and {current!r}"
            )
        by_id[candidate_id] = current
