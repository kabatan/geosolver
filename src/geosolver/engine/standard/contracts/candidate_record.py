"""Contract dataclasses for search/refinement candidates."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, replace
from functools import cached_property

from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat

_attempt = ContextVar("candidate_attempt", default=0)


@contextmanager
def candidate_attempt(index):
    token = _attempt.set(index)
    try:
        yield
    finally:
        _attempt.reset(token)


@dataclass(frozen=True)
class CandidateKey:
    """Exact provenance identity; integer display IDs are never identity keys."""

    phase: str
    backend: str
    attempt: int
    box: int | None
    seed: int
    start: int
    evaluation: int | None
    family: str = ""
    derivation: str = ""
    constraints: tuple[int, ...] = ()
    targets: tuple[int, ...] = ()
    parent: CandidateKey | None = None

    def derived(self, kind, constraints=(), targets=()):
        return replace(
            self,
            derivation=kind,
            constraints=tuple(constraints),
            targets=tuple(targets),
            parent=self,
        )

    @property
    def uid(self):
        parts = (
            self.phase,
            self.backend,
            str(self.attempt),
            "-" if self.box is None else str(self.box),
            str(self.seed),
            str(self.start),
            "-" if self.evaluation is None else str(self.evaluation),
        )
        base = "/".join(parts)
        if self.family or self.derivation:
            return (
                base
                + "/"
                + json.dumps(
                    (
                        self.family,
                        self.derivation,
                        self.constraints,
                        self.targets,
                        self.parent.uid if self.parent is not None else None,
                    ),
                    separators=(",", ":"),
                )
            )
        return base


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
    hard_feasible: bool | None = None
    hard_violation_tags: tuple[str, ...] = ()
    validity_margin_float: float | None = None
    origin_phase: str = "search"
    origin_backend: str = "unknown"
    origin_attempt: int | None = None
    origin_box_index: int | None = None
    origin_evaluation_index: int | None = None
    origin_family: str = ""
    # Fresh algebraic proposals retain digits lost by their float telemetry.
    # These remain untrusted initial coordinates for the ordinary HP verifier.
    initial_point_decimal: tuple[str, ...] = ()
    # Exact rational bounds containing this configuration and disjoint from
    # all other retained algebraic branches; admission still uses the verifier.
    originating_branch_box: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        if self.origin_attempt is None:
            object.__setattr__(self, "origin_attempt", _attempt.get())

    @cached_property
    def candidate_key(self):
        return CandidateKey(
            self.origin_phase,
            self.origin_backend,
            self.origin_attempt,
            self.origin_box_index,
            self.origin_seed,
            self.origin_start_point_index,
            self.origin_evaluation_index,
            self.origin_family,
        )

    @property
    def candidate_uid(self) -> str:
        """Return the deterministic, human-readable provenance identity."""

        return self.candidate_key.uid


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
    hard_feasible: bool | None = None
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
    derivation_kind: str = ""
    constraint_indices: tuple[int, ...] = ()
    target_integers: tuple[int, ...] = ()
    origin_key: CandidateKey | None = None

    @cached_property
    def candidate_key(self):
        if self.origin_key is not None:
            return self.origin_key
        base = (
            self.source.candidate_key
            if self.source is not None
            else CandidateKey("refinement", "direct", 0, None, -1, self.candidate_id, None)
        )
        if self.derivation_kind:
            return base.derived(self.derivation_kind, self.constraint_indices, self.target_integers)
        if self.source is not None and self.candidate_id != self.source.candidate_id:
            return base.derived("closure")
        return base

    @property
    def candidate_uid(self) -> str:
        return self.candidate_key.uid


@dataclass(frozen=True)
class SearchBatchResult:
    """Batch result returned by global search."""

    candidates: tuple[FloatCandidate, ...]
    evaluation_count: int
    failure_ratio: float
    all_records: tuple[FloatCandidate, ...] = ()
    guard_feasible_ledger: tuple[FloatCandidate, ...] = ()
    search_diagnostics: dict[str, object] = field(default_factory=dict)

    # None preserves older producers; their ratio still describes evaluations.
    evaluation_failure_count: int | None = None

    @property
    def failed_evaluations(self) -> int:
        if self.evaluation_failure_count is not None:
            return self.evaluation_failure_count
        return round(self.failure_ratio * self.evaluation_count)


@dataclass(frozen=True)
class RefinementBatchResult:
    """Batch result returned by local refinement."""

    candidates: tuple[RefinedCandidate, ...]
    converged_count: int
    attempted_count: int
    solver_name: str = "mpmath_refiner"
    hard_feasible_count: int = 0


def candidate_record(candidate):
    """Include derived identity when converting a candidate to audit evidence."""
    record = asdict(candidate)
    record.update(
        candidate_uid=candidate.candidate_uid, candidate_key=asdict(candidate.candidate_key)
    )
    if isinstance(candidate, RefinedCandidate) and candidate.source is not None:
        record["source"] = candidate_record(candidate.source)
    return record


def assert_candidate_key_consistency(candidates: tuple[FloatCandidate, ...]) -> None:
    """An identical origin must not identify different generated coordinates."""

    by_key = {}
    for candidate in candidates:
        previous = by_key.setdefault(candidate.candidate_key, candidate.x_float)
        if previous != candidate.x_float:
            raise RuntimeError(f"candidate key collision: {candidate.candidate_uid}")


def assert_candidate_id_consistency(candidates: tuple[FloatCandidate, ...]) -> None:
    """Legacy diagnostic only; production identity uses CandidateKey."""

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
