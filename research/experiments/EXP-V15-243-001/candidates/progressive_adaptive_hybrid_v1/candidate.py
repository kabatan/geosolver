"""Truth-blind progressive probe followed by original-depth hybrid handoff.

The frozen v15 local kernel is opaque and cannot resume a tranche.  Therefore
this policy uses one bounded 64-callback probe per original start, then sends
selected ambiguous/improving, original-order baseline, and counter-Cauchy
insurance starts directly to a fresh original 600-callback service.  A deep
service has no local wall cap unless its probe demonstrated starvation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Callable, Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE.parent / "progressive_local_budget_v1" / "candidate.py"
BASE_SHA256 = "931d1a338e068306c5ad9515f8f111a65df94961d32054a72688775830f53c4d"


def _load_base():
    payload = BASE_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != BASE_SHA256:
        raise RuntimeError("hash-bound progressive scheduler base changed")
    name = "geotarget_progressive_adaptive_hybrid_base"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, BASE_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(BASE_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load_base()
Assessment = BASE.Assessment
StartSpec = BASE.StartSpec
RungOutcome = BASE.RungOutcome
ServiceRecord = BASE.ServiceRecord
RetainedEndpoint = BASE.RetainedEndpoint
SchedulerResult = BASE.SchedulerResult
INSURANCE_SOURCE = BASE.INSURANCE_SOURCE
INSURANCE_PERIOD = BASE.INSURANCE_PERIOD

SCHEMA = "geotarget.exp-v15-243.progressive-adaptive-hybrid/v1"
PROFILE = "64-600-adaptive-hybrid"
RUNG_CALLBACK_CAPS = (64, 600)
RUNG_PROFILES = {PROFILE: RUNG_CALLBACK_CAPS}
PROBE_CALLBACK_CAP = RUNG_CALLBACK_CAPS[0]
ORIGINAL_CALLBACK_CAP = RUNG_CALLBACK_CAPS[-1]
MAX_ATTEMPT_WALL_SECONDS = 4.0
STARVATION_CAP_FRACTION = 0.9
HANDOFF_FRACTION = 0.5
BASELINE_HANDOFF_FRACTION = 0.25
INSURANCE_HANDOFF_FRACTION = 0.25
PROBE_BLOCK_SIZE = 8

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
    first_completed: bool = False
    first_endpoint_evidence: bool = False
    demonstrated_starvation: bool = False
    handoff_reason: str | None = None


def set_active_profile(profile: str) -> None:
    if profile != PROFILE:
        raise ValueError(f"unknown adaptive hybrid profile: {profile!r}")


def proposal_prefix_digest(starts: Sequence[StartSpec]) -> str:
    return BASE.proposal_prefix_digest(starts)


def attempt_wall_cap(remaining_seconds: float, unserved_starts: int) -> float:
    return BASE.attempt_wall_cap(remaining_seconds, unserved_starts)


def _quality_key(state: _State) -> tuple[float, ...]:
    assessment = state.assessment
    if assessment is None:
        return (3.0, math.inf, math.inf, math.inf, float(state.spec.ordinal))
    ratio = state.model_ratio if state.model_ratio is not None else -math.inf
    stability = (
        state.rank_stability if state.rank_stability is not None else -math.inf
    )
    return (
        float(assessment.feasibility_tier),
        assessment.merit,
        -state.reward,
        -max(-1.0e6, min(1.0e6, ratio + stability)),
        float(state.spec.ordinal),
    )


def _is_improving(state: _State) -> bool:
    assessment = state.assessment
    return bool(
        state.first_endpoint_evidence
        and assessment is not None
        and (
            (assessment.finite and assessment.semantics_valid)
            or state.reward > 0.0
            or (state.model_ratio is not None and state.model_ratio > 0.0)
            or (state.rank_stability is not None and state.rank_stability > 0.5)
        )
    )


def _is_ambiguous(state: _State) -> bool:
    return bool(
        state.first_endpoint_evidence
        and (state.model_ratio is None or state.rank_stability is None)
    )


def _handoff_cohort(
    states: Sequence[_State],
) -> tuple[tuple[_State, ...], Mapping[str, int]]:
    """Build disjoint adaptive, baseline, and counter-Cauchy quotas."""

    desired_count = min(
        len(states), max(1, math.ceil(HANDOFF_FRACTION * len(states)))
    )
    viable = [
        state
        for state in states
        if state.first_completed or state.first_endpoint_evidence
    ]
    if not viable:
        return (), {
            "handoff_selected_count": 0,
            "adaptive_handoff_selected": 0,
            "baseline_handoff_selected": 0,
            "insurance_handoff_selected": 0,
            "ambiguous_or_improving_selected": 0,
        }
    insurance_quota = min(
        sum(state.spec.insurance for state in states),
        math.ceil(INSURANCE_HANDOFF_FRACTION * desired_count),
    )
    regular_count = sum(not state.spec.insurance for state in viable)
    baseline_quota = min(
        regular_count,
        math.ceil(BASELINE_HANDOFF_FRACTION * desired_count),
        desired_count - insurance_quota,
    )

    insurance = sorted(
        (state for state in states if state.spec.insurance), key=_quality_key
    )[:insurance_quota]
    selected = {state.spec.ordinal for state in insurance}
    for state in insurance:
        state.handoff_reason = "COUNTER_CAUCHY_INSURANCE"

    baseline = []
    for state in sorted(viable, key=lambda item: item.spec.ordinal):
        if len(baseline) >= baseline_quota:
            break
        if state.spec.insurance or state.spec.ordinal in selected:
            continue
        baseline.append(state)
        selected.add(state.spec.ordinal)
        state.handoff_reason = "ORIGINAL_ORDER_BASELINE"

    adaptive_pool = sorted(
        (
            state
            for state in viable
            if state.spec.ordinal not in selected
            and (_is_improving(state) or _is_ambiguous(state))
        ),
        key=_quality_key,
    )
    filler = sorted(
        (state for state in viable if state.spec.ordinal not in selected),
        key=_quality_key,
    )
    adaptive = []
    for state in (*adaptive_pool, *filler):
        if len(selected) >= desired_count:
            break
        if state.spec.ordinal in selected:
            continue
        adaptive.append(state)
        selected.add(state.spec.ordinal)
        state.handoff_reason = (
            "AMBIGUOUS_OR_IMPROVING"
            if _is_improving(state) or _is_ambiguous(state)
            else "QUALITY_FILL"
        )
        if len(selected) >= desired_count:
            break

    handoff_count = len(selected)

    # One insurance service first preserves the global >=25% service floor.
    # Thereafter each four-slot cycle is insurance/adaptive/baseline/adaptive.
    queues = {
        "insurance": list(insurance),
        "adaptive": list(adaptive),
        "baseline": list(baseline),
    }
    pattern = ("insurance", "adaptive", "baseline", "adaptive")
    ordered: list[_State] = []
    while any(queues.values()):
        progressed = False
        for category in pattern:
            queue = queues[category]
            if queue:
                ordered.append(queue.pop(0))
                progressed = True
            else:
                alternatives = [item for item in queues.values() if item]
                if alternatives:
                    ordered.append(alternatives[0].pop(0))
                    progressed = True
            if len(ordered) >= handoff_count:
                break
        if not progressed or len(ordered) >= handoff_count:
            break
    if len(ordered) != handoff_count or len({id(state) for state in ordered}) != len(
        ordered
    ):
        raise AssertionError("adaptive handoff cohort construction failed")
    return tuple(ordered), {
        "handoff_selected_count": handoff_count,
        "adaptive_handoff_selected": len(adaptive),
        "baseline_handoff_selected": len(baseline),
        "insurance_handoff_selected": len(insurance),
        "ambiguous_or_improving_selected": sum(
            state.handoff_reason == "AMBIGUOUS_OR_IMPROVING" for state in ordered
        ),
    }


def _snapshot(
    *,
    prefix_sha256: str,
    states: Sequence[_State],
    records: Sequence[ServiceRecord],
    callbacks: int,
    callback_cap: int,
    stop_reason: str,
) -> dict[str, object]:
    payload = BASE._snapshot(
        profile=RUNG_CALLBACK_CAPS,
        prefix_sha256=prefix_sha256,
        states=states,
        records=records,
        callbacks=callbacks,
        callback_cap=callback_cap,
        stop_reason=stop_reason,
    )
    payload["schema_version"] = f"{SCHEMA}.telemetry/v1"
    payload["handoff_reasons"] = {
        str(state.spec.ordinal): state.handoff_reason
        for state in states
        if state.handoff_reason is not None
    }
    return payload


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
    """Probe every start, then directly hand selected starts to original depth."""

    del cohort_size
    BASE._validate_starts(starts)
    if callback_cap < 1:
        raise ValueError("callback cap must be positive")
    if not math.isfinite(hard_deadline):
        raise ValueError("hard deadline must be finite")
    if finalize_reserve_seconds < 0.0:
        raise ValueError("finalize reserve must be nonnegative")
    if max_service_wall_seconds <= 0.0:
        raise ValueError("maximum service wall must be positive")

    prefix_sha256 = proposal_prefix_digest(starts)
    states = [_State(spec) for spec in starts]
    records: list[ServiceRecord] = []
    callbacks = 0
    insurance_services = 0
    stop_reason = "COMPLETE"
    handoff_counts: Mapping[str, int] = {
        "handoff_selected_count": 0,
        "adaptive_handoff_selected": 0,
        "baseline_handoff_selected": 0,
        "insurance_handoff_selected": 0,
        "ambiguous_or_improving_selected": 0,
    }

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
        if phase == "ORDINAL_FIRST_SERVICE":
            cap = min(
                max_service_wall_seconds,
                attempt_wall_cap(wall_before, unserved),
            )
        elif state.demonstrated_starvation:
            cap = min(max_service_wall_seconds, wall_before)
        else:
            # A fast completed probe earns the same remaining wall horizon as
            # the original 600-callback service; tranche end alone cannot cut it.
            cap = wall_before
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
        ratio = BASE._finite_signal(outcome.promotion_signals, "model_ratio")
        stability = BASE._finite_signal(
            outcome.promotion_signals, "rank_stability"
        )
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
        if phase == "ORDINAL_FIRST_SERVICE":
            state.first_completed = deadline_met
            state.first_endpoint_evidence = endpoint_evidence
            state.demonstrated_starvation = bool(
                not deadline_met
                or elapsed >= STARVATION_CAP_FRACTION * max(1.0e-12, cap)
            )
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

    accumulated_handoffs = dict(handoff_counts)
    for offset in range(0, len(states), PROBE_BLOCK_SIZE):
        block = states[offset : offset + PROBE_BLOCK_SIZE]
        for state in block:
            if not service(state, PROBE_CALLBACK_CAP, "ORDINAL_FIRST_SERVICE"):
                break
            if stop_reason != "COMPLETE":
                break
        if stop_reason != "COMPLETE":
            break
        handoffs, block_counts = _handoff_cohort(block)
        for key, value in block_counts.items():
            accumulated_handoffs[key] += value
        for state in handoffs:
            if not service(state, ORIGINAL_CALLBACK_CAP, "ADAPTIVE_HANDOFF"):
                break
            if stop_reason != "COMPLETE":
                break
        if stop_reason != "COMPLETE":
            break
    handoff_counts = accumulated_handoffs

    after_sha256 = proposal_prefix_digest(starts)
    if prefix_sha256 != after_sha256:
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
        state.spec.source
        for state in states
        if state.deepest_rung >= ORIGINAL_CALLBACK_CAP
    }
    first_service_count = sum(state.services > 0 for state in states)
    deep_records = [
        record for record in records if record.phase == "ADAPTIVE_HANDOFF"
    ]
    activation = {
        "schema_version": SCHEMA,
        "rungs": list(RUNG_CALLBACK_CAPS),
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
            not records or INSURANCE_PERIOD * insurance_services >= len(records)
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
        "probe_callback_cap": PROBE_CALLBACK_CAP,
        "original_handoff_callback_cap": ORIGINAL_CALLBACK_CAP,
        "direct_probe_to_original_depth": True,
        "probe_block_size": PROBE_BLOCK_SIZE,
        "demonstrated_starvation_count": sum(
            state.demonstrated_starvation for state in states
        ),
        "uncapped_handoff_services": sum(
            not state.demonstrated_starvation
            for state in states
            if any(
                record.start_ordinal == state.spec.ordinal
                and record.phase == "ADAPTIVE_HANDOFF"
                for record in deep_records
            )
        ),
        "starvation_capped_handoff_services": sum(
            state.demonstrated_starvation
            for state in states
            if any(
                record.start_ordinal == state.spec.ordinal
                and record.phase == "ADAPTIVE_HANDOFF"
                for record in deep_records
            )
        ),
        "probe_wall_cap_formula": "max(0.5,min(4,2*remaining/unserved))",
        "handoff_wall_policy": (
            "remaining global horizon unless probe demonstrated starvation; "
            "demonstrated starvation remains capped at 4 seconds"
        ),
        "truth_blind_promotion": True,
        "promotion_inputs": [
            "source_semantic_validity",
            "source_residual_rank",
            "source_guard_violation",
            "model_ratio_if_exposed",
            "rank_stability_if_exposed",
            "charged_callbacks",
            "measured_wall",
            "probe_completion_or_starvation",
            "original_ordinal_baseline_quota",
            "counter_cauchy_insurance_quota",
        ],
        "permanent_pruning": False,
        "case_family_truth_target_inputs": False,
        **dict(handoff_counts),
    }
    final_snapshot = _snapshot(
        prefix_sha256=prefix_sha256,
        states=states,
        records=records,
        callbacks=callbacks,
        callback_cap=callback_cap,
        stop_reason=stop_reason,
    )
    final_snapshot["activation"] = activation
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
        "mechanism": (
            "bounded ordinal probe blocks with truth-blind direct original-depth "
            "handoff after each block"
        ),
        "profile": list(RUNG_CALLBACK_CAPS),
        "base_scheduler_sha256": BASE_SHA256,
        "probe_wall_cap_formula": "max(0.5,min(4,2*remaining/unserved))",
        "handoff_wall_policy": (
            "global remaining horizon for completed probes; 4-second cap only "
            "after demonstrated starvation"
        ),
        "handoff_fraction": HANDOFF_FRACTION,
        "probe_block_size": PROBE_BLOCK_SIZE,
        "original_order_baseline_handoff_fraction": BASELINE_HANDOFF_FRACTION,
        "counter_cauchy_handoff_fraction": INSURANCE_HANDOFF_FRACTION,
        "promotion": (
            "semantic validity, residual/guard rank, optional model ratio/rank "
            "stability, cost, ambiguity, and probe completion"
        ),
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
    "MAX_ATTEMPT_WALL_SECONDS",
    "PROFILE",
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
