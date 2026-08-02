"""Adaptive-precision escalation for a stalled semismooth HP corrector.

This disposable candidate wraps the already-tested semismooth pseudo-transient
corrector.  A precision stage is allowed to hand its current point to the next
stage even when it misses that stage's internal gate, but only after an opaque
numerical trigger is exercised: the endpoint must remain semantically valid,
the residual must have fallen by at least eight orders of magnitude during the
stage, it must still be above the public replay target, and the local method
must have stopped for lack of descent or iteration budget.  Case identity,
family, truth, geometry primitives, and source-derived bounds are not inputs.

The final authority is unchanged: three independently initialized lanes and an
untouched original 512/768/1024 replay are still required by the worker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Sequence

from mpmath import mp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SEMISMOOTH_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-005/nearroot_semismooth_hp/candidate.py"
)


def _load_semismooth():
    name = "geotarget_exp006_adaptive_hp_semismooth_base"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    specification = importlib.util.spec_from_file_location(name, SEMISMOOTH_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(f"cannot load {SEMISMOOTH_PATH}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load_semismooth()

FIXED_PRECISION = "FIXED_PRECISION_SEMISMOOTH_CONTROL"
ADAPTIVE_ESCALATION = "RATIO_TRIGGERED_ADAPTIVE_PRECISION_ESCALATION"
VARIANTS = (FIXED_PRECISION, ADAPTIVE_ESCALATION)

# Public, dimensionless trigger.  It is deliberately coarser than the observed
# failing-stage reduction and is not fitted to a case or a source family.
MIN_REDUCTION_RATIO = mp.mpf("1e8")
PUBLIC_RESIDUAL_GATE = mp.mpf("1e-100")
ESCALATABLE_FAILURES = frozenset(
    {"NO_SEMISMOOTH_DESCENT", "ITERATION_LIMIT"}
)


@dataclass
class EscalationCounters:
    stages_considered: int = 0
    stages_escalated: int = 0
    insufficient_reduction: int = 0
    already_authority_ready: int = 0
    ineligible_status: int = 0
    semantic_replay_rejections: int = 0


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "_mpf_"):
        return mp.nstr(value, 150)
    return value


def _initial_residual(problem, z, dps, counters):
    with mp.workdps(int(dps)):
        if not BASE._semantic(problem, z, dps, counters):
            return None
        return BASE._norm_inf(BASE._residual(problem, z, dps, counters))


def _should_escalate(
    problem,
    z,
    record,
    *,
    stage_initial_residual,
    dps,
    counters,
    escalation_counters,
):
    """Return a public numerical decision and its reduction ratio."""

    escalation_counters.stages_considered += 1
    if record.status not in ESCALATABLE_FAILURES:
        escalation_counters.ineligible_status += 1
        return False, None
    if record.residual_inf is None or stage_initial_residual is None:
        escalation_counters.insufficient_reduction += 1
        return False, None
    with mp.workdps(int(dps)):
        before = mp.mpf(stage_initial_residual)
        after = mp.mpf(record.residual_inf)
        if not (mp.isfinite(before) and mp.isfinite(after)) or after <= 0:
            escalation_counters.insufficient_reduction += 1
            return False, None
        if after <= PUBLIC_RESIDUAL_GATE:
            escalation_counters.already_authority_ready += 1
            return False, before / after
        ratio = before / after
        if ratio < MIN_REDUCTION_RATIO:
            escalation_counters.insufficient_reduction += 1
            return False, ratio
        # The failed stage may have moved the point.  Recheck the untouched
        # semantic callback before allowing its state into a higher precision.
        if not BASE._semantic(problem, z, dps, counters):
            escalation_counters.semantic_replay_rejections += 1
            return False, ratio
    escalation_counters.stages_escalated += 1
    return True, ratio


def _refine_lane(problem, lane, variant, deadline, counters, escalation_counters):
    bits, nominal_dps, stages = lane
    started = time.monotonic()
    with mp.workdps(stages[0]):
        z = [
            (mp.mpf(problem.start_text[index]) - mp.mpf(problem.origin_text[index]))
            / mp.mpf(problem.scale_text[index])
            for index in range(len(problem.start_text))
        ]
    records = []
    escalation_events = []
    status = "REFINEMENT_INCOMPLETE"
    residual_inf = None
    try:
        for index, dps in enumerate(stages):
            initial = _initial_residual(problem, z, dps, counters)
            status, z, record = BASE._run_stage(
                problem,
                z,
                dps=dps,
                final=index == len(stages) - 1,
                variant=BASE.CORRECTIVE,
                counters=counters,
                deadline=deadline,
                max_iterations=128,
            )
            records.append(record)
            residual_inf = record.residual_inf
            if status == "SUCCESS":
                continue
            may_escalate = variant == ADAPTIVE_ESCALATION and index + 1 < len(stages)
            if may_escalate:
                decision, ratio = _should_escalate(
                    problem,
                    z,
                    record,
                    stage_initial_residual=initial,
                    dps=dps,
                    counters=counters,
                    escalation_counters=escalation_counters,
                )
                escalation_events.append(
                    {
                        "from_dps": int(dps),
                        "to_dps": int(stages[index + 1]),
                        "failure_status": status,
                        "initial_residual_inf": initial,
                        "stalled_residual_inf": residual_inf,
                        "reduction_ratio": ratio,
                        "escalated": bool(decision),
                    }
                )
                if decision:
                    status = "ESCALATED_TO_HIGHER_PRECISION"
                    continue
            break
        if status == "SUCCESS":
            with mp.workdps(stages[-1]):
                point = BASE._external(problem, z)
                answer = mp.mpf(problem.evaluator.answer(point, stages[-1]))
            lane_record = BASE.LaneRecord(
                bits,
                nominal_dps,
                status,
                point,
                answer,
                residual_inf,
                records,
                time.monotonic() - started,
            )
            return lane_record, escalation_events
    except BASE._Failure as error:
        status = error.status
    except Exception:
        status = "CALLBACK_OR_NUMERIC_EXCEPTION"
    lane_record = BASE.LaneRecord(
        bits,
        nominal_dps,
        status,
        None,
        None,
        residual_inf,
        records,
        time.monotonic() - started,
    )
    return lane_record, escalation_events


def refine_endpoint(
    evaluator,
    endpoint: Sequence[float],
    *,
    variant: str = ADAPTIVE_ESCALATION,
    deadline_seconds: float = 24.0,
) -> dict[str, object]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    values = tuple(float(value) for value in endpoint)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("endpoint must be finite and nonempty")
    problem = BASE.BASE.Problem(
        evaluator,
        BASE.BASE.canonical_float64_endpoint(values),
        tuple("0" for _ in values),
        tuple(repr(max(1.0, abs(value))) for value in values),
    )
    deadline = time.monotonic() + max(0.03, float(deadline_seconds))
    counters = BASE.Counters()
    escalation_counters = EscalationCounters()
    lanes = []
    events = []
    for lane in BASE.LANES:
        if time.monotonic() >= deadline:
            break
        record, lane_events = _refine_lane(
            problem,
            lane,
            variant,
            deadline,
            counters,
            escalation_counters,
        )
        lanes.append(record)
        events.append(
            {
                "bits": int(lane[0]),
                "events": lane_events,
            }
        )
        if record.status != "SUCCESS":
            break

    coordinate_disagreement = None
    target_512_768 = None
    target_768_1024 = None
    if len(lanes) >= 2 and all(row.status == "SUCCESS" for row in lanes[:2]):
        with mp.workdps(350):
            coordinate_disagreement = max(
                (
                    abs(left - right)
                    for left, right in zip(
                        lanes[0].point, lanes[1].point, strict=True
                    )
                ),
                default=mp.mpf("0"),
            )
            target_512_768 = abs(lanes[0].answer - lanes[1].answer)
    if len(lanes) == 3 and all(row.status == "SUCCESS" for row in lanes[1:]):
        with mp.workdps(350):
            target_768_1024 = abs(lanes[1].answer - lanes[2].answer)
    ready = bool(
        len(lanes) == 3
        and all(row.status == "SUCCESS" for row in lanes)
        and coordinate_disagreement is not None
        and coordinate_disagreement <= BASE.AGREEMENT_GATE
        and target_512_768 is not None
        and target_512_768 <= BASE.AGREEMENT_GATE
        and target_768_1024 is not None
        and target_768_1024 <= BASE.AGREEMENT_GATE
    )
    return {
        "variant": variant,
        "status": "NUMERIC_V3_READY" if ready else "HIGH_PRECISION_REFINEMENT_FAILED",
        "numeric_v3_ready": ready,
        "lanes": [_jsonable(asdict(row)) for row in lanes],
        "configuration_512_768_disagreement_inf": _jsonable(
            coordinate_disagreement
        ),
        "target_512_768_disagreement": _jsonable(target_512_768),
        "target_768_1024_disagreement": _jsonable(target_768_1024),
        "independent_lane_initialization": bool(len(lanes) == 3),
        "semismooth_counters": asdict(counters),
        "escalation_counters": asdict(escalation_counters),
        "escalation_events": _jsonable(events),
        "trigger": {
            "minimum_reduction_ratio": str(MIN_REDUCTION_RATIO),
            "public_residual_gate": str(PUBLIC_RESIDUAL_GATE),
            "eligible_failure_statuses": sorted(ESCALATABLE_FAILURES),
        },
        "case_identity_read": False,
        "family_read": False,
        "truth_read": False,
        "known_target_count_read": False,
        "coordinate_fixing_or_gauge": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
    }


__all__ = [
    "ADAPTIVE_ESCALATION",
    "BASE",
    "FIXED_PRECISION",
    "VARIANTS",
    "refine_endpoint",
]
