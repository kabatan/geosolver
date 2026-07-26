"""Two-prefix numerical-v3 refinement schedule prototype.

The frozen refiner independently repeats a 512-, 768-, and 1024-bit prefix,
then discards all but one common anchor before the strict polish.  Numerical-v3
requires independent 512/768 configuration and target agreement; 1024 bits is
needed for the independent target replay/PSLQ confirmation, not for a third
configuration refinement.  This prototype therefore runs two independent
prefixes, preserves their unchanged 1e-100 agreement gates, and leaves the
original 512/768/1024 DSL replay and 768/1024 target authority untouched.

``STRICT_STAGE_COUNT`` is an experiment-only frozen configuration.  Four
stages retain the existing 1e-195 target-stability/uncertainty gates; six is a
control that changes only the redundant third prefix.
"""

from __future__ import annotations

from dataclasses import asdict
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Sequence

from mpmath import mp


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE.parent / "hp_undamped_first_candidate/candidate.py"
VARIANT = "UNDAMPED_MINIMUM_NORM_BEFORE_EXISTING_DAMPING_LADDER"
VARIANTS = (VARIANT,)
STRICT_STAGE_COUNT = 4


def _load_base():
    name = "geotarget_exp008_hp_precision_schedule_undamped_base"
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
FROZEN = BASE.FROZEN
ADAPTIVE = FROZEN.ADAPTIVE
SEMISMOOTH = FROZEN.SEMISMOOTH


def _two_prefix_lanes(problem, deadline, counters):
    escalation_counters = ADAPTIVE.EscalationCounters()
    lanes = []
    events = []
    for lane in SEMISMOOTH.LANES[:2]:
        if time.monotonic() >= deadline:
            break
        record, lane_events = ADAPTIVE._refine_lane(
            problem,
            lane,
            ADAPTIVE.ADAPTIVE_ESCALATION,
            deadline,
            counters,
            escalation_counters,
        )
        lanes.append(record)
        events.append({"bits": int(lane[0]), "events": lane_events})
        if record.status != "SUCCESS":
            break

    coordinate_disagreement = None
    target_512_768 = None
    if len(lanes) == 2 and all(row.status == "SUCCESS" for row in lanes):
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
    ready = bool(
        len(lanes) == 2
        and all(row.status == "SUCCESS" for row in lanes)
        and coordinate_disagreement is not None
        and coordinate_disagreement <= SEMISMOOTH.AGREEMENT_GATE
        and target_512_768 is not None
        and target_512_768 <= SEMISMOOTH.AGREEMENT_GATE
    )
    return {
        "status": "NUMERIC_512_768_PREFIX_READY" if ready else "PREFIX_FAILED",
        "numeric_512_768_prefix_ready": ready,
        "lanes": lanes,
        "configuration_512_768_disagreement_inf": coordinate_disagreement,
        "target_512_768_disagreement": target_512_768,
        "escalation_counters": asdict(escalation_counters),
        "escalation_events": events,
    }


def refine_endpoint(
    evaluator,
    endpoint: Sequence[float],
    *,
    variant: str = VARIANT,
    deadline_seconds: float = 23.0,
):
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    values = tuple(float(value) for value in endpoint)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("endpoint must be finite and nonempty")
    if STRICT_STAGE_COUNT not in (4, 6):
        raise ValueError("STRICT_STAGE_COUNT must be 4 or 6")

    started = time.monotonic()
    deadline = started + max(0.03, float(deadline_seconds))
    problem = FROZEN._problem(evaluator, values)
    prefix_counters = SEMISMOOTH.Counters()
    stability_counters = FROZEN.StabilityCounters()
    strict_counters = SEMISMOOTH.Counters()
    lanes = []

    original_run_stage = SEMISMOOTH._run_stage
    original_strict_stages = FROZEN.STRICT_STAGES
    original_minimum = FROZEN.MIN_STRICT_STAGES
    for key in BASE._ACTIVATION:
        BASE._ACTIVATION[key] = 0
    SEMISMOOTH._run_stage = BASE._run_stage
    FROZEN.STRICT_STAGES = original_strict_stages[:STRICT_STAGE_COUNT]
    FROZEN.MIN_STRICT_STAGES = STRICT_STAGE_COUNT
    try:
        prefix = _two_prefix_lanes(problem, deadline, prefix_counters)
        prefix_lanes = prefix["lanes"]
        if prefix["numeric_512_768_prefix_ready"] is True:
            polished = FROZEN._postpolish_lane(
                problem,
                asdict(prefix_lanes[0]),
                deadline,
                strict_counters,
                stability_counters,
            )
            if polished["status"] == "TARGET_STABILITY_REACHED":
                for bits, nominal_dps, _ in SEMISMOOTH.LANES:
                    lanes.append(
                        {
                            **polished,
                            "bits": bits,
                            "nominal_dps": nominal_dps,
                            "common_anchor_after_independent_512_768_prefix": True,
                        }
                    )
    finally:
        SEMISMOOTH._run_stage = original_run_stage
        FROZEN.STRICT_STAGES = original_strict_stages
        FROZEN.MIN_STRICT_STAGES = original_minimum

    ready = bool(
        len(lanes) == 3
        and all(row["status"] == "TARGET_STABILITY_REACHED" for row in lanes)
    )
    return {
        "variant": variant,
        "status": "TARGET_STABILITY_READY" if ready else "TARGET_STABILITY_FAILED",
        "target_stability_ready": ready,
        "numeric_v3_ready": ready,
        "lanes": FROZEN._jsonable(lanes),
        "adaptive_prefix": {
            "status": prefix["status"],
            "numeric_512_768_prefix_ready": prefix[
                "numeric_512_768_prefix_ready"
            ],
            "lanes": FROZEN._jsonable([asdict(row) for row in prefix["lanes"]]),
            "configuration_512_768_disagreement_inf": FROZEN._jsonable(
                prefix["configuration_512_768_disagreement_inf"]
            ),
            "target_512_768_disagreement": FROZEN._jsonable(
                prefix["target_512_768_disagreement"]
            ),
            "escalation_counters": prefix["escalation_counters"],
            "escalation_events": FROZEN._jsonable(prefix["escalation_events"]),
        },
        "independent_prefix_lane_count": len(prefix["lanes"]),
        "independent_prefix_bits": [row.bits for row in prefix["lanes"]],
        "common_anchor_after_independent_prefix": bool(
            prefix["numeric_512_768_prefix_ready"]
        ),
        "stability_counters": {
            **asdict(stability_counters),
            "independent_prefix_bits": [row.bits for row in prefix["lanes"]],
            "configuration_512_768_disagreement_inf": FROZEN._jsonable(
                prefix["configuration_512_768_disagreement_inf"]
            ),
            "target_512_768_disagreement": FROZEN._jsonable(
                prefix["target_512_768_disagreement"]
            ),
            "strict_stage_count": STRICT_STAGE_COUNT,
        },
        "semismooth_counters": {
            "prefix": asdict(prefix_counters),
            "strict": asdict(strict_counters),
        },
        "strict_stage_count": STRICT_STAGE_COUNT,
        "strict_configuration": {
            "stages": [
                {
                    "dps": dps,
                    "residual_gate": str(gate),
                    "mode": mode,
                    "stencil_extra_digits": stencil_extra,
                }
                for dps, gate, mode, stencil_extra in original_strict_stages[
                    :STRICT_STAGE_COUNT
                ]
            ],
            "minimum_strict_stages": STRICT_STAGE_COUNT,
            "target_stability_gate": str(FROZEN.TARGET_STABILITY_GATE),
            "predicted_target_uncertainty_gate": str(
                FROZEN.TARGET_UNCERTAINTY_GATE
            ),
        },
        "elapsed_seconds": time.monotonic() - started,
        "case_identity_read": False,
        "family_read": False,
        "truth_read": False,
        "known_target_count_read": False,
        "coordinate_fixing_or_gauge": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
        "independent_1024_configuration_prefix_required": False,
        "independent_1024_original_dsl_target_replay_required": True,
    }


__all__ = ["STRICT_STAGE_COUNT", "VARIANT", "VARIANTS", "refine_endpoint"]
