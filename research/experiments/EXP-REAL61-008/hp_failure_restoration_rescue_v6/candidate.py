"""Aging, HP-failure-gated restoration restart supplement.

The default row-equilibrated search and its high-precision authority attempt
have already completed before this module is eligible.  A Float64 endpoint is
admitted only when untouched-source replay says it is semantic-valid and
low-residual, yet the numerical-v3 authority fails at high precision or at an
adjacent-precision agreement gate.  The endpoint then receives one bounded
bundle of dyadic basin-boundary restarts through the already tested
row-equilibrated restoration/filter kernel.

The bundle consumes caller-owned leftover callbacks and wall time only.  It
does not alter, reserve, replace, or lower any default-search or HP work.  All
points remain in the original source coordinates; no bound, gauge, equation,
variable, or parameterization is introduced.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
EXP008 = HERE.parent
RESTORATION_PATH = EXP008 / "dev41_row_restoration_v4/candidate.py"
RESTORATION_SHA256 = "4a9eacaa3f592ea78992c174a4c37e7a0562273655ca9ba72c34575ee599485c"

LOW_RESIDUAL_INF = 1.0e-6
RESTART_RADII = (0.5, 0.25)
MAX_WALSH_BASE_DIRECTIONS = 2
MAX_RESCUE_CALLBACKS = 600
MAX_CALLBACKS_PER_RESTART = 75

_ADJACENT_PRECISION_FAILURES = frozenset(
    {
        "configuration_512_768_disagreement_inf",
        "target_512_768_disagreement",
        "target_768_1024_disagreement",
        "precision_lane_set",
    }
)
_HP_REPLAY_FAILURES = frozenset(
    {
        "numeric_v3_not_ready",
        "original_dsl_hp_replay",
        "original_numerical_replay",
    }
)


def _load_restoration():
    observed = hashlib.sha256(RESTORATION_PATH.read_bytes()).hexdigest()
    if observed != RESTORATION_SHA256:
        raise RuntimeError("tested row-restoration kernel changed")
    name = "geotarget_exp008_hp_failure_restoration_kernel"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, RESTORATION_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(RESTORATION_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


RESTORATION = _load_restoration()


class BudgetExceeded(RuntimeError):
    """Lane-local cap signal recognized by the frozen kernel by class name."""


@dataclass(frozen=True)
class TriggerDecision:
    eligible: bool
    reason: str
    residual_inf: float | None
    observed_failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RescueItem:
    source_sha256: str
    endpoint_sha256: str
    endpoint: tuple[float, ...]
    enqueue_tick: int
    enqueue_ordinal: int
    residual_inf: float


@dataclass(frozen=True)
class RestartProposal:
    point: np.ndarray
    radius: float
    walsh_row: int
    antithetic: bool


@dataclass(frozen=True)
class RescueOutcome:
    endpoints: tuple[np.ndarray, ...]
    statuses: Mapping[str, int]
    counters: Mapping[str, int]
    callbacks: int
    proposals_started: int


def _final_result(authority_artifact: Mapping[str, object]) -> Mapping[str, object] | None:
    nested = authority_artifact.get("final_result")
    if isinstance(nested, Mapping):
        return nested
    if authority_artifact.get("schema_version") == "geotarget.exp008-dev41-target-hp-adapter/v1":
        return authority_artifact
    return None


def classify_hp_failure(authority_artifact: Mapping[str, object]) -> TriggerDecision:
    """Admit only a low-residual semantic endpoint rejected by numerical-v3.

    The decision intentionally does not inspect failure subtype beyond the
    public HP-replay/agreement gates, and has no case/family/truth input.
    """

    final = _final_result(authority_artifact)
    if final is None:
        return TriggerDecision(False, "malformed_authority_artifact", None, ())
    if authority_artifact.get("authority_pass") is True or final.get("authority_pass") is True:
        return TriggerDecision(False, "authority_already_passed", None, ())

    transformations = final.get("problem_transformations")
    if not isinstance(transformations, Mapping) or any(
        value is not False for value in transformations.values()
    ):
        return TriggerDecision(False, "source_contract_not_clean", None, ())
    contract = final.get("input_contract")
    if not isinstance(contract, Mapping) or any(
        contract.get(name) is not False
        for name in ("truth", "known_target_count", "case_id", "family")
    ):
        return TriggerDecision(False, "identity_or_truth_contract_not_clean", None, ())

    replay = final.get("float64_replay")
    if not isinstance(replay, Mapping):
        return TriggerDecision(False, "missing_float64_replay", None, ())
    if any(
        replay.get(name) is not True
        for name in ("semantic_valid", "hard_feasible", "guard_ok", "intrinsic_domain_ok")
    ):
        return TriggerDecision(False, "float64_endpoint_not_semantic_safe", None, ())
    try:
        residual = float(replay.get("residual_inf"))
    except (TypeError, ValueError, OverflowError):
        residual = math.inf
    if not math.isfinite(residual) or residual > LOW_RESIDUAL_INF:
        return TriggerDecision(False, "float64_endpoint_not_low_residual", residual, ())

    raw_failures = final.get("failure_reasons")
    failures = tuple(
        str(item)
        for item in raw_failures
        if isinstance(item, str)
    ) if isinstance(raw_failures, Sequence) and not isinstance(raw_failures, (str, bytes)) else ()
    observed = frozenset(failures)
    if not observed.intersection(_ADJACENT_PRECISION_FAILURES | _HP_REPLAY_FAILURES):
        return TriggerDecision(False, "failure_is_not_hp_replay_or_agreement", residual, failures)
    return TriggerDecision(True, "semantic_low_residual_hp_authority_failure", residual, failures)


class AgingRescueQueue:
    """At-most-once queue whose oldest waiting endpoint always wins."""

    def __init__(self) -> None:
        self._pending: dict[tuple[str, str], RescueItem] = {}
        self._served: set[tuple[str, str]] = set()
        self._next_ordinal = 0

    def enqueue(
        self,
        *,
        source_sha256: str,
        endpoint_sha256: str,
        endpoint: Sequence[float],
        authority_artifact: Mapping[str, object],
        tick: int,
    ) -> TriggerDecision:
        decision = classify_hp_failure(authority_artifact)
        if not decision.eligible:
            return decision
        key = (source_sha256, endpoint_sha256)
        if key in self._pending or key in self._served:
            return TriggerDecision(
                False,
                "endpoint_already_pending_or_served",
                decision.residual_inf,
                decision.observed_failure_reasons,
            )
        point = tuple(float(value) for value in endpoint)
        if not point or not all(math.isfinite(value) for value in point):
            return TriggerDecision(
                False,
                "endpoint_vector_invalid",
                decision.residual_inf,
                decision.observed_failure_reasons,
            )
        self._pending[key] = RescueItem(
            source_sha256=source_sha256,
            endpoint_sha256=endpoint_sha256,
            endpoint=point,
            enqueue_tick=int(tick),
            enqueue_ordinal=self._next_ordinal,
            residual_inf=float(decision.residual_inf),
        )
        self._next_ordinal += 1
        return decision

    def pop(self, *, tick: int) -> tuple[RescueItem, int] | None:
        if not self._pending:
            return None
        now = int(tick)
        # Maximum age first; enqueue ordinal makes equal-age service stable.
        item = min(
            self._pending.values(),
            key=lambda queued: (-(now - queued.enqueue_tick), queued.enqueue_ordinal),
        )
        key = (item.source_sha256, item.endpoint_sha256)
        del self._pending[key]
        self._served.add(key)
        return item, max(0, now - item.enqueue_tick)

    def __len__(self) -> int:
        return len(self._pending)


def restart_proposals(endpoint: Sequence[float]) -> tuple[RestartProposal, ...]:
    """Return a small fixed dyadic/Walsh boundary-restart bundle.

    The points are proposals only.  They are not clipped and do not install a
    finite search box.  Literal source bounds, when present, remain owned by
    the unchanged restoration kernel.
    """

    center = np.asarray(endpoint, dtype=float)
    if center.ndim != 1 or center.size < 1 or not np.all(np.isfinite(center)):
        raise ValueError("endpoint must be a nonempty finite vector")
    dimension = int(center.size)
    scale = np.maximum(1.0, np.abs(center))
    base_count = min(MAX_WALSH_BASE_DIRECTIONS, dimension)
    proposals: list[RestartProposal] = []
    for radius in RESTART_RADII:
        for row in range(base_count):
            if row == 0:
                signs = np.ones(dimension, dtype=float)
            else:
                signs = np.asarray(
                    [1.0 if ((column >> (row - 1)) & 1) == 0 else -1.0 for column in range(dimension)],
                    dtype=float,
                )
            direction = signs / math.sqrt(dimension)
            for antithetic in (False, True):
                signed = -direction if antithetic else direction
                point = center + float(radius) * scale * signed
                if np.all(np.isfinite(point)):
                    proposals.append(
                        RestartProposal(point.copy(), float(radius), row, antithetic)
                    )
    return tuple(proposals)


class _LaneQuota:
    def __init__(self, case: object, budget: object, cap: int) -> None:
        self._evaluate = case.evaluate
        self._progressive = case.progressive_residual
        self._budget = budget
        self._begin = int(budget.callbacks)
        self._cap = int(cap)

    @property
    def used(self) -> int:
        return int(self._budget.callbacks) - self._begin

    def _check(self) -> None:
        if self.used >= self._cap:
            raise BudgetExceeded("hp_failure_restoration_lane_cap")

    def evaluate(self, point: Sequence[float]):
        self._check()
        return self._evaluate(np.asarray(point, dtype=float))

    def progressive(self, point: Sequence[float]):
        self._check()
        return self._progressive(np.asarray(point, dtype=float))


def run_restoration_rescue(
    *,
    base_case: object,
    budget: object,
    document: Mapping[str, object],
    failed_endpoint: Sequence[float],
    leftover_callback_cap: int,
    deadline_monotonic: float,
) -> RescueOutcome:
    """Spend only the explicitly supplied residual work on one rescue item."""

    cap = min(int(leftover_callback_cap), MAX_RESCUE_CALLBACKS)
    if cap < 2:
        return RescueOutcome((), {"insufficient_leftover": 1}, {}, 0, 0)
    begin = int(budget.callbacks)
    program = RESTORATION.compile_program(document)
    statuses: Counter[str] = Counter()
    counters: Counter[str] = Counter()
    endpoints: list[np.ndarray] = []
    started = 0
    for proposal in restart_proposals(failed_endpoint):
        if time.monotonic() >= deadline_monotonic:
            statuses["deadline_before_restart"] += 1
            break
        remaining = cap - (int(budget.callbacks) - begin)
        if remaining < 2:
            statuses["callback_cap_before_restart"] += 1
            break
        lane_cap = min(MAX_CALLBACKS_PER_RESTART, remaining)
        quota = _LaneQuota(base_case, budget, lane_cap)
        lane_case = replace(
            base_case,
            evaluate=quota.evaluate,
            progressive_residual=quota.progressive,
        )
        started += 1
        try:
            outcome = RESTORATION.solve_local(
                lane_case,
                program,
                RESTORATION.CONFIGURATION,
                proposal.point,
                per_start_scale=np.maximum(1.0, np.abs(proposal.point)),
                source_lower=base_case.lower,
                source_upper=base_case.upper,
                max_callbacks=lane_cap,
                deadline_monotonic=deadline_monotonic,
            )
        except Exception as error:
            statuses[f"exception:{type(error).__name__}"] += 1
            continue
        statuses[str(outcome.status)] += 1
        raw_counters = outcome.counters if isinstance(outcome.counters, Mapping) else vars(outcome.counters)
        counters.update(
            {
                str(name): int(value)
                for name, value in raw_counters.items()
                if isinstance(value, (bool, int, np.integer))
            }
        )
        endpoint = np.asarray(outcome.endpoint, dtype=float)
        if endpoint.shape == np.asarray(failed_endpoint, dtype=float).shape and np.all(np.isfinite(endpoint)):
            endpoints.append(endpoint.copy())
    return RescueOutcome(
        endpoints=tuple(endpoints),
        statuses=dict(statuses),
        counters=dict(counters),
        callbacks=int(budget.callbacks) - begin,
        proposals_started=started,
    )


def mechanism_manifest() -> Mapping[str, object]:
    return {
        "name": "hp_failure_aged_dyadic_restoration_rescue_v6",
        "trigger": "semantic-valid low-residual endpoint fails numerical-v3 HP replay/agreement",
        "low_residual_inf": LOW_RESIDUAL_INF,
        "queue": "at-most-once oldest-age-first",
        "restart_radii": list(RESTART_RADII),
        "restart_directions": "two Walsh rows with antithetics, original coordinates",
        "restoration_kernel_sha256": RESTORATION_SHA256,
        "maximum_rescue_callbacks": MAX_RESCUE_CALLBACKS,
        "maximum_callbacks_per_restart": MAX_CALLBACKS_PER_RESTART,
        "default_or_hp_work_reserved_or_replaced": False,
        "caller_supplies_leftover_work_only": True,
        "source_problem_modified": False,
        "variables_or_equations_changed": False,
        "bounds_added_or_inferred": False,
        "gauge_or_symmetry_reduction": False,
        "reparameterization": False,
        "case_family_source_series_truth_target_count_inputs": False,
    }


__all__ = [
    "AgingRescueQueue",
    "RescueItem",
    "RescueOutcome",
    "RestartProposal",
    "TriggerDecision",
    "classify_hp_failure",
    "mechanism_manifest",
    "restart_proposals",
    "run_restoration_rescue",
]
