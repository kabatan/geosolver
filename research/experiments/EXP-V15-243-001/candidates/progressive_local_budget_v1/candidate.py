"""Truth-blind progressive budget allocator for the frozen v15 local kernel.

This module owns scheduling only.  It neither evaluates a target nor changes a
source problem, proposal, bound, residual, guard, or canonical verifier.  The
binding supplies an opaque local-kernel runner and charges every callback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import struct
import time
from typing import Callable, Mapping, Sequence

import numpy as np


SCHEMA = "geotarget.exp-v15-243.progressive-local-budget/v1"
INSURANCE_PERIOD = 4
INSURANCE_SOURCE = "counter_product_cauchy"
RUNG_PROFILES = {
    "64-192-600": (64, 192, 600),
    "96-300-600": (96, 300, 600),
}
RUNG_CALLBACK_CAPS = RUNG_PROFILES["64-192-600"]
MIN_ATTEMPT_WALL_SECONDS = 0.5
MAX_ATTEMPT_WALL_SECONDS = 4.0
ATTEMPT_FAIRNESS_MULTIPLIER = 2.0


@dataclass(frozen=True)
class Assessment:
    finite: bool
    semantics_valid: bool
    residual_inf: float
    violation_inf: float

    def validate(self) -> None:
        if self.finite:
            if not math.isfinite(self.residual_inf) or self.residual_inf < 0.0:
                raise ValueError("finite assessment has invalid residual")
            if not math.isfinite(self.violation_inf) or self.violation_inf < 0.0:
                raise ValueError("finite assessment has invalid violation")

    @property
    def feasibility_tier(self) -> int:
        if self.finite and self.semantics_valid:
            return 0
        if self.finite:
            return 1
        return 2

    @property
    def residual_digits(self) -> float:
        if not self.finite:
            return -300.0
        if self.residual_inf == 0.0:
            return 300.0
        return max(-300.0, min(300.0, -math.log10(self.residual_inf)))

    @property
    def merit(self) -> float:
        if not self.finite:
            return math.inf
        return (
            16.0 * self.feasibility_tier
            + math.log1p(min(1.0e300, self.residual_inf))
            + 4.0 * math.log1p(min(1.0e300, self.violation_inf))
        )


@dataclass(frozen=True)
class StartSpec:
    ordinal: int
    source: str
    point: np.ndarray
    insurance: bool


@dataclass(frozen=True)
class RungOutcome:
    endpoint: np.ndarray
    assessment: Assessment
    callbacks_used: int
    status: str
    checkpoint: object | None = None
    checkpoint_resumable: bool = False
    completed_before_deadline: bool = True
    endpoint_observed_before_deadline: bool = True
    promotion_signals: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ServiceRecord:
    service_ordinal: int
    start_ordinal: int
    source: str
    insurance: bool
    phase: str
    rung_callback_cap: int
    callbacks_used: int
    aggregate_callbacks_after: int
    remaining_seconds_before: float
    unserved_starts_before: int
    attempt_wall_cap_seconds: float
    service_deadline_monotonic: float
    measured_wall_seconds: float
    assessment: Assessment
    residual_digit_gain: float
    violation_improvement: float
    model_ratio: float | None
    rank_stability: float | None
    cost_adjusted_reward: float
    checkpoint_supplied: bool
    checkpoint_returned: bool
    checkpoint_resumable: bool
    completed_before_deadline: bool
    endpoint_observed_before_deadline: bool
    status: str


@dataclass(frozen=True)
class RetainedEndpoint:
    start_ordinal: int
    source: str
    point: np.ndarray
    assessment: Assessment
    deepest_rung: int


@dataclass(frozen=True)
class SchedulerResult:
    endpoints: tuple[RetainedEndpoint, ...]
    records: tuple[ServiceRecord, ...]
    callbacks_used: int
    callback_cap: int
    stop_reason: str
    activation: Mapping[str, object]


Runner = Callable[[StartSpec, int, float, object | None], RungOutcome]
Clock = Callable[[], float]
CheckpointSink = Callable[[Mapping[str, object]], None]


@dataclass
class _State:
    spec: StartSpec
    assessment: Assessment | None = None
    endpoint: np.ndarray | None = None
    deepest_rung: int = 0
    checkpoint: object | None = None
    checkpoint_resumable: bool = False
    reward: float = 0.0
    services: int = 0
    model_ratio: float | None = None
    rank_stability: float | None = None


def set_active_profile(profile: str) -> None:
    """Select one preregistered arm before a single-process worker run."""

    global RUNG_CALLBACK_CAPS
    if profile not in RUNG_PROFILES:
        raise ValueError(f"unknown progressive profile: {profile!r}")
    RUNG_CALLBACK_CAPS = RUNG_PROFILES[profile]


def proposal_prefix_digest(starts: Sequence[StartSpec]) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack("<Q", len(starts)))
    for start in starts:
        point = np.asarray(start.point, dtype="<f8")
        source = start.source.encode("utf-8")
        digest.update(struct.pack("<Q?Q", start.ordinal, start.insurance, len(source)))
        digest.update(source)
        digest.update(struct.pack("<Q", point.size))
        digest.update(point.tobytes())
    return digest.hexdigest()


def attempt_wall_cap(remaining_seconds: float, unserved_starts: int) -> float:
    """The preregistered local-attempt cap, independent of problem identity."""

    if unserved_starts < 1:
        unserved_starts = 1
    return max(
        MIN_ATTEMPT_WALL_SECONDS,
        min(
            MAX_ATTEMPT_WALL_SECONDS,
            ATTEMPT_FAIRNESS_MULTIPLIER
            * max(0.0, float(remaining_seconds))
            / unserved_starts,
        ),
    )


def _validate_starts(starts: Sequence[StartSpec]) -> None:
    if not starts:
        raise ValueError("at least one start is required")
    if [item.ordinal for item in starts] != list(range(len(starts))):
        raise ValueError("proposal ordinals must be a dense original prefix")
    shape = np.asarray(starts[0].point).shape
    for start in starts:
        point = np.asarray(start.point, dtype=float)
        if point.ndim != 1 or point.shape != shape or not np.all(np.isfinite(point)):
            raise ValueError("proposal points must be finite same-shape vectors")
        if start.insurance != (start.ordinal % INSURANCE_PERIOD == 0):
            raise ValueError("every fourth proposal must be the insurance lane")
        if start.insurance and start.source != INSURANCE_SOURCE:
            raise ValueError("insurance proposal lost its counter-Cauchy source")
    for size in range(1, len(starts) + 1):
        insured = sum(item.insurance for item in starts[:size])
        if INSURANCE_PERIOD * insured < size:
            raise ValueError("counter-Cauchy prefix fraction fell below 25%")


def _quality_key(state: _State) -> tuple[float, ...]:
    assessment = state.assessment
    if assessment is None:
        return (3.0, math.inf, math.inf, math.inf, float(state.spec.ordinal))
    ratio = state.model_ratio if state.model_ratio is not None else -math.inf
    stability = state.rank_stability if state.rank_stability is not None else -math.inf
    return (
        float(assessment.feasibility_tier),
        assessment.merit,
        -state.reward,
        -max(-1.0e6, min(1.0e6, ratio + stability)),
        float(state.spec.ordinal),
    )


def _select_promotions(states: Sequence[_State], count: int) -> tuple[_State, ...]:
    """Select a temporary next-rung cohort; no lane is permanently suppressed."""

    count = min(max(1, count), len(states))
    ranked = sorted(states, key=_quality_key)
    insurance = [state for state in ranked if state.spec.insurance]
    required = min(len(insurance), math.ceil(count / INSURANCE_PERIOD))
    selected = list(insurance[:required])
    selected_ids = {state.spec.ordinal for state in selected}
    selected.extend(
        state for state in ranked if state.spec.ordinal not in selected_ids
    )
    return tuple(selected[:count])


def _dispatch_order(
    states: Sequence[_State], *, services: int, insurance_services: int
) -> tuple[_State, ...]:
    regular = sorted(
        (state for state in states if not state.spec.insurance),
        key=lambda state: state.spec.ordinal,
    )
    insurance = sorted(
        (state for state in states if state.spec.insurance),
        key=lambda state: state.spec.ordinal,
    )
    ordered: list[_State] = []
    while regular or insurance:
        insurance_due = INSURANCE_PERIOD * insurance_services < services + 1
        if insurance_due and insurance:
            state = insurance.pop(0)
            insurance_services += 1
        elif regular:
            state = regular.pop(0)
        else:
            state = insurance.pop(0)
            insurance_services += 1
        ordered.append(state)
        services += 1
    return tuple(ordered)


def _finite_signal(signals: Mapping[str, float], name: str) -> float | None:
    try:
        value = float(signals[name])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _snapshot(
    *,
    profile: tuple[int, ...],
    prefix_sha256: str,
    states: Sequence[_State],
    records: Sequence[ServiceRecord],
    callbacks: int,
    callback_cap: int,
    stop_reason: str,
) -> dict[str, object]:
    return {
        "schema_version": f"{SCHEMA}.telemetry/v1",
        "profile": list(profile),
        "proposal_prefix_sha256": prefix_sha256,
        "callbacks_used": callbacks,
        "callback_cap": callback_cap,
        "first_service_count": sum(state.services > 0 for state in states),
        "start_count": len(states),
        "stop_reason": stop_reason,
        "services": [
            {
                "service_ordinal": row.service_ordinal,
                "start_ordinal": row.start_ordinal,
                "insurance": row.insurance,
                "phase": row.phase,
                "rung_callback_cap": row.rung_callback_cap,
                "callbacks_used": row.callbacks_used,
                "remaining_seconds_before": row.remaining_seconds_before,
                "unserved_starts_before": row.unserved_starts_before,
                "attempt_wall_cap_seconds": row.attempt_wall_cap_seconds,
                "measured_wall_seconds": row.measured_wall_seconds,
                "feasibility_tier": row.assessment.feasibility_tier,
                "residual_inf": (
                    row.assessment.residual_inf if row.assessment.finite else None
                ),
                "violation_inf": (
                    row.assessment.violation_inf if row.assessment.finite else None
                ),
                "residual_digit_gain": row.residual_digit_gain,
                "violation_improvement": row.violation_improvement,
                "model_ratio": row.model_ratio,
                "rank_stability": row.rank_stability,
                "promotion_reward": row.cost_adjusted_reward,
                "completed_before_deadline": row.completed_before_deadline,
                "endpoint_observed_before_deadline": (
                    row.endpoint_observed_before_deadline
                ),
                "status": row.status,
            }
            for row in records
        ],
        "endpoints": [
            {
                "start_ordinal": state.spec.ordinal,
                "source": state.spec.source,
                "deepest_rung": state.deepest_rung,
                "endpoint": (
                    None
                    if state.endpoint is None
                    else [float(value) for value in state.endpoint]
                ),
            }
            for state in states
            if state.endpoint is not None
        ],
    }


def run_rung_scheduler(
    starts: Sequence[StartSpec],
    *,
    callback_cap: int,
    hard_deadline: float,
    run_rung: Runner,
    clock: Clock = time.monotonic,
    finalize_reserve_seconds: float = 3.0,
    max_service_wall_seconds: float = MAX_ATTEMPT_WALL_SECONDS,
    cohort_size: int | None = None,
    checkpoint_sink: CheckpointSink | None = None,
) -> SchedulerResult:
    """Breadth-first first service followed by truth-blind progressive racing."""

    del cohort_size
    _validate_starts(starts)
    if callback_cap < 1:
        raise ValueError("callback cap must be positive")
    if not math.isfinite(hard_deadline):
        raise ValueError("hard deadline must be finite")
    if finalize_reserve_seconds < 0.0:
        raise ValueError("finalize reserve must be nonnegative")
    if max_service_wall_seconds <= 0.0:
        raise ValueError("maximum service wall must be positive")

    profile = tuple(RUNG_CALLBACK_CAPS)
    prefix_sha256 = proposal_prefix_digest(starts)
    states = [_State(spec) for spec in starts]
    records: list[ServiceRecord] = []
    callbacks = 0
    insurance_services = 0
    stop_reason = "COMPLETE"

    def remaining() -> float:
        return hard_deadline - finalize_reserve_seconds - clock()

    def service(state: _State, rung: int, phase: str) -> bool:
        nonlocal callbacks, insurance_services, stop_reason
        wall_before = remaining()
        if wall_before <= 0.0:
            stop_reason = "FINALIZE_RESERVE_REACHED"
            return False
        if callbacks >= callback_cap:
            stop_reason = "CALLBACK_CAP"
            return False
        allowance = min(rung, callback_cap - callbacks)
        if allowance < 2:
            stop_reason = "CALLBACK_TAIL_TOO_SMALL"
            return False
        unserved = sum(item.services == 0 for item in states)
        cap = min(
            max_service_wall_seconds,
            attempt_wall_cap(wall_before, unserved),
        )
        service_deadline = min(
            hard_deadline - finalize_reserve_seconds,
            clock() + cap,
        )
        supplied = state.checkpoint if state.checkpoint_resumable else None
        prior = state.assessment
        started = clock()
        outcome = run_rung(state.spec, allowance, service_deadline, supplied)
        finished = clock()
        elapsed = max(1.0e-12, finished - started)
        deadline_met = bool(
            outcome.completed_before_deadline and finished <= service_deadline
        )
        endpoint_evidence = bool(
            finished <= service_deadline
            and (deadline_met or outcome.endpoint_observed_before_deadline)
        )
        assessment = outcome.assessment
        endpoint = np.asarray(outcome.endpoint, dtype=float)
        status = str(outcome.status)
        if not endpoint_evidence:
            assessment = prior or Assessment(False, False, math.inf, 1.0e300)
            endpoint = (
                state.endpoint.copy()
                if state.endpoint is not None
                else np.asarray(state.spec.point, dtype=float).copy()
            )
            status = f"DEADLINE_REJECTED:{status}"
        elif not deadline_met:
            status = f"INCOMPLETE_PREDEADLINE_EVIDENCE:{status}"
        assessment.validate()
        if endpoint.shape != np.asarray(state.spec.point).shape or not np.all(
            np.isfinite(endpoint)
        ):
            raise ValueError("rung returned a malformed endpoint")
        used = int(outcome.callbacks_used)
        if used < 0 or used > allowance or (used == 0 and deadline_met):
            raise ValueError("rung callback charge is outside its allowance")

        digit_gain = (
            0.0
            if prior is None
            else max(0.0, assessment.residual_digits - prior.residual_digits)
        )
        violation_gain = (
            0.0
            if prior is None
            else max(0.0, prior.violation_inf - assessment.violation_inf)
        )
        tier_gain = (
            0.0
            if prior is None
            else max(0, prior.feasibility_tier - assessment.feasibility_tier)
        )
        ratio = _finite_signal(outcome.promotion_signals, "model_ratio")
        stability = _finite_signal(outcome.promotion_signals, "rank_stability")
        signal_bonus = 0.0
        if ratio is not None:
            signal_bonus += 0.1 * max(0.0, min(10.0, ratio))
        if stability is not None:
            signal_bonus += 0.1 * max(0.0, min(1.0, stability))
        reward = (
            digit_gain + 4.0 * violation_gain + 8.0 * tier_gain + signal_bonus
        ) / (max(1, used) * elapsed)

        callbacks += used
        if endpoint_evidence:
            state.assessment = assessment
            state.endpoint = endpoint.copy()
            state.model_ratio = ratio
            state.rank_stability = stability
        if deadline_met:
            state.deepest_rung = max(state.deepest_rung, rung)
            state.checkpoint = outcome.checkpoint
            state.checkpoint_resumable = bool(outcome.checkpoint_resumable)
        else:
            state.checkpoint = None
            state.checkpoint_resumable = False
        state.reward = 0.6 * state.reward + 0.4 * reward if state.services else reward
        state.services += 1
        if state.spec.insurance:
            insurance_services += 1
        records.append(
            ServiceRecord(
                len(records),
                state.spec.ordinal,
                state.spec.source,
                state.spec.insurance,
                phase,
                rung,
                used,
                callbacks,
                wall_before,
                unserved,
                cap,
                service_deadline,
                elapsed,
                assessment,
                digit_gain,
                violation_gain,
                ratio,
                stability,
                state.reward,
                supplied is not None,
                deadline_met and outcome.checkpoint is not None,
                deadline_met and bool(outcome.checkpoint_resumable),
                deadline_met,
                endpoint_evidence,
                status,
            )
        )
        if checkpoint_sink is not None:
            checkpoint_sink(
                _snapshot(
                    profile=profile,
                    prefix_sha256=prefix_sha256,
                    states=states,
                    records=records,
                    callbacks=callbacks,
                    callback_cap=callback_cap,
                    stop_reason="IN_PROGRESS",
                )
            )
        if remaining() <= 0.0:
            stop_reason = "FINALIZE_RESERVE_REACHED_AFTER_ATOMIC_RUNG"
        return True

    # Minimum service: original proposal order, with no promotion or screening.
    active: tuple[_State, ...] = tuple(states)
    for rung_index, rung in enumerate(profile):
        if rung_index:
            active = _select_promotions(active, math.ceil(len(active) / 2))
            ordered = _dispatch_order(
                active,
                services=len(records),
                insurance_services=insurance_services,
            )
            phase = "TRUTH_BLIND_PROMOTION"
        else:
            ordered = active
            phase = "ORDINAL_FIRST_SERVICE"
        for state in ordered:
            if not service(state, rung, phase) or stop_reason != "COMPLETE":
                break
        if stop_reason != "COMPLETE":
            break

    after_sha256 = proposal_prefix_digest(starts)
    if after_sha256 != prefix_sha256:
        raise AssertionError("scheduler mutated the proposal prefix")
    endpoints = tuple(
        RetainedEndpoint(
            state.spec.ordinal,
            state.spec.source,
            state.endpoint.copy(),
            state.assessment,
            state.deepest_rung,
        )
        for state in states
        if state.endpoint is not None and state.assessment is not None
    )
    all_sources = {state.spec.source for state in states}
    deep_sources = {
        state.spec.source for state in states if state.deepest_rung >= profile[-1]
    }
    first_service_count = sum(state.services > 0 for state in states)
    activation = {
        "schema_version": SCHEMA,
        "rungs": list(profile),
        "proposal_prefix_sha256_before": prefix_sha256,
        "proposal_prefix_sha256_after": after_sha256,
        "proposal_points_modified": False,
        "original_first_launch_order_preserved": True,
        "first_service_count": first_service_count,
        "start_count": len(states),
        "minimum_service_complete": first_service_count == len(states),
        "insurance_service_count": insurance_services,
        "insurance_service_fraction": (
            insurance_services / len(records) if records else 0.0
        ),
        "counter_cauchy_service_floor_holds": (
            not records
            or INSURANCE_PERIOD * insurance_services >= len(records)
        ),
        "source_stream_count": len(all_sources),
        "source_streams_with_deep_solve": len(deep_sources),
        "each_source_stream_has_deep_solve": deep_sources == all_sources,
        "checkpoint_services": sum(row.checkpoint_supplied for row in records),
        "prefix_reexecution_services": sum(
            not row.checkpoint_supplied for row in records
        ),
        "partial_checkpoint_emissions": len(records) if checkpoint_sink else 0,
        "completed_before_deadline_services": sum(
            row.completed_before_deadline for row in records
        ),
        "deadline_rejected_services": sum(
            not row.completed_before_deadline for row in records
        ),
        "attempt_wall_cap_formula": "max(0.5,min(4,2*remaining/unserved))",
        "truth_blind_promotion": True,
        "promotion_inputs": [
            "source_semantic_validity",
            "source_residual_progress",
            "source_guard_violation_progress",
            "model_ratio_if_exposed",
            "rank_stability_if_exposed",
            "charged_callbacks",
            "measured_wall",
        ],
        "permanent_pruning": False,
        "case_family_truth_target_inputs": False,
    }
    final_snapshot = _snapshot(
        profile=profile,
        prefix_sha256=prefix_sha256,
        states=states,
        records=records,
        callbacks=callbacks,
        callback_cap=callback_cap,
        stop_reason=stop_reason,
    )
    if checkpoint_sink is not None:
        checkpoint_sink(final_snapshot)
    return SchedulerResult(
        endpoints,
        tuple(records),
        callbacks,
        callback_cap,
        stop_reason,
        activation,
    )


def configuration_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA,
        "mechanism": "dense minimum service then truth-blind progressive racing",
        "profiles": {key: list(value) for key, value in RUNG_PROFILES.items()},
        "active_profile": list(RUNG_CALLBACK_CAPS),
        "attempt_wall_cap_formula": "max(0.5,min(4,2*remaining/unserved))",
        "minimum_service": "every original-prefix start before any promotion",
        "promotion": (
            "semantic feasibility, residual/guard progress, optional model ratio "
            "and rank stability, charged callbacks and measured wall"
        ),
        "counter_cauchy_proposal_and_service_floor": 0.25,
        "hard_pruning": False,
        "source_problem_or_coordinates_modified": False,
        "case_family_truth_target_or_previous_outcome_inputs": False,
        "canonical_verifier_modified": False,
    }
    payload["configuration_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


__all__ = [
    "Assessment",
    "INSURANCE_SOURCE",
    "RUNG_CALLBACK_CAPS",
    "RUNG_PROFILES",
    "RetainedEndpoint",
    "RungOutcome",
    "SchedulerResult",
    "ServiceRecord",
    "StartSpec",
    "attempt_wall_cap",
    "configuration_manifest",
    "proposal_prefix_digest",
    "run_rung_scheduler",
    "set_active_profile",
]
