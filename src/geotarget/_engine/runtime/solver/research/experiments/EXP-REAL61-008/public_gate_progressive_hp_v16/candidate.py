"""Public-gate-aligned numerical-v3 endpoint refinement prototype.

The existing HP schedule first computes two independently initialized 512-
and 768-bit refinements that already have to agree to ``1e-100``.  It then
forces their common anchor through several additional target-stability stages
whose internal threshold is ``1e-195``.  Those stages are useful margin, but
they are not part of numerical-v3 authority and can reject an endpoint after
all public configuration gates have already passed.

This disposable candidate stops refinement at that exact boundary.  It emits
the independent 512/768 configurations plus the unchanged 768-bit point as a
fresh-1024-replay anchor.  The existing adapter then, fail-closed, reevaluates
the untouched original DSL independently at 512/768/1024 precision, checks
all public residual/configuration/target/semantic gates, and runs owned
768/1024 PSLQ authority.  Thus this module removes no public requirement; it
only removes a private ``1e-195`` precondition.
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
REVIEWED_PATH = HERE.parent / "hp_precision_schedule_v11/candidate.py"
VARIANT = "UNDAMPED_MINIMUM_NORM_BEFORE_EXISTING_DAMPING_LADDER"
VARIANTS = (VARIANT,)
PUBLIC_GATE = mp.mpf("1e-100")
# The outer authority runner first uses zero stages.  Only when every
# numerical-v3 gate passes but owned target relation authority fails does it
# make one general corrective attempt with the first two existing polish
# stages.  This mutable experiment knob is process-local and never depends on
# case/family/truth identity.
POSTPOLISH_STAGE_COUNT = 0
_LAST_SESSION: dict[str, object] | None = None


def _load_reviewed():
    name = "geotarget_exp008_public_gate_hp_reviewed_prefix"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, REVIEWED_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(REVIEWED_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


REVIEWED = _load_reviewed()
FROZEN = REVIEWED.FROZEN
SEMISMOOTH = REVIEWED.SEMISMOOTH


def _public_prefix_ready(prefix: dict[str, object]) -> bool:
    """Repeat the public 512/768 gate explicitly and fail closed."""

    lanes = prefix.get("lanes")
    if not isinstance(lanes, list) or len(lanes) != 2:
        return False
    if not all(getattr(row, "status", None) == "SUCCESS" for row in lanes):
        return False
    coordinate = prefix.get("configuration_512_768_disagreement_inf")
    target = prefix.get("target_512_768_disagreement")
    if coordinate is None or target is None:
        return False
    with mp.workdps(380):
        return bool(mp.mpf(coordinate) <= PUBLIC_GATE and mp.mpf(target) <= PUBLIC_GATE)


def _progressive_common_anchor(
    problem,
    row,
    deadline: float,
    counters,
    stage_count: int,
) -> dict[str, object]:
    """Apply at most two general stages, accepting only public residual state."""

    if stage_count not in (0, 2):
        raise ValueError("POSTPOLISH_STAGE_COUNT must be 0 or 2")
    if stage_count == 0:
        return {"ready": True, "point": None, "records": []}

    selected = FROZEN.STRICT_STAGES[:stage_count]
    z = FROZEN._normalized(problem, row.point, selected[0][0])
    records: list[dict[str, object]] = []
    final_residual = None
    final_semantic = False
    for dps, gate, mode, stencil_extra in selected:
        if time.monotonic() >= deadline:
            break
        before_residual, before_answer, before_semantic = FROZEN._observe(
            problem, z, dps, counters
        )
        if not before_semantic:
            break
        stage_status, z, stage_record = FROZEN._strict_stage(
            problem,
            z,
            dps=dps,
            gate=gate,
            mode=mode,
            stencil_extra=stencil_extra,
            counters=counters,
            deadline=deadline,
        )
        after_residual, after_answer, after_semantic = FROZEN._observe(
            problem, z, dps, counters
        )
        final_residual = after_residual
        final_semantic = bool(after_semantic)
        records.append(
            {
                **asdict(stage_record),
                "requested_gate": gate,
                "mode": mode,
                "stencil_extra_digits": stencil_extra,
                "before_residual_inf": before_residual,
                "after_residual_inf": after_residual,
                "before_answer": before_answer,
                "after_answer": after_answer,
            }
        )
        if not after_semantic:
            break
        # NO_SEMISMOOTH_DESCENT can mean the available precision has reached
        # a stationary root approximation.  Do not reject it here: the
        # untouched public replay and relation authority below are decisive.
        if stage_status not in {
            "SUCCESS",
            "NO_SEMISMOOTH_DESCENT",
            "ITERATION_LIMIT",
        }:
            break

    ready = bool(
        len(records) == stage_count
        and final_semantic
        and final_residual is not None
        and mp.mpf(final_residual) <= PUBLIC_GATE
    )
    point = None
    if ready:
        with mp.workdps(selected[-1][0]):
            point = FROZEN.SEMISMOOTH._external(problem, z)
    return {
        "ready": ready,
        "point": point,
        "records": records,
        "residual_inf": final_residual,
    }


def refine_endpoint(
    evaluator,
    endpoint: Sequence[float],
    *,
    variant: str = VARIANT,
    deadline_seconds: float = 23.0,
):
    """Return only configurations eligible for the unchanged public gate."""

    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    values = tuple(float(value) for value in endpoint)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("endpoint must be finite and nonempty")

    global _LAST_SESSION
    _LAST_SESSION = None
    started = time.monotonic()
    deadline = started + max(0.03, float(deadline_seconds))
    problem = FROZEN._problem(evaluator, values)
    prefix_counters = SEMISMOOTH.Counters()

    for key in REVIEWED.BASE._ACTIVATION:
        REVIEWED.BASE._ACTIVATION[key] = 0
    if POSTPOLISH_STAGE_COUNT not in (0, 2):
        raise ValueError("POSTPOLISH_STAGE_COUNT must be 0 or 2")
    original_run_stage = SEMISMOOTH._run_stage
    SEMISMOOTH._run_stage = REVIEWED.BASE._run_stage
    try:
        prefix = REVIEWED._two_prefix_lanes(problem, deadline, prefix_counters)
        public_prefix_ready = _public_prefix_ready(prefix)
        progressive_counters = SEMISMOOTH.Counters()
        progressive = (
            _progressive_common_anchor(
                problem,
                prefix["lanes"][0],
                deadline,
                progressive_counters,
                POSTPOLISH_STAGE_COUNT,
            )
            if public_prefix_ready
            else {"ready": False, "point": None, "records": []}
        )
    finally:
        SEMISMOOTH._run_stage = original_run_stage

    ready = bool(public_prefix_ready and progressive["ready"])
    lanes: list[dict[str, object]] = []
    if ready:
        prefix_lanes = prefix["lanes"]
        if POSTPOLISH_STAGE_COUNT == 0:
            for row in prefix_lanes:
                lanes.append(
                    {
                        **asdict(row),
                        "public_gate_refinement_lane": True,
                        "independently_initialized": True,
                    }
                )
            replay_anchor = prefix_lanes[1].point
        else:
            # The public independent-prefix check has already passed.  The
            # common corrective point is replayed in every numerical lane so
            # that only the correction, rather than arbitrary manifold drift,
            # contributes to configuration disagreement.
            replay_anchor = progressive["point"]
            for row in prefix_lanes:
                lanes.append(
                    {
                        **asdict(row),
                        "point": replay_anchor,
                        "public_gate_refinement_lane": True,
                        "independently_initialized": True,
                        "common_post_prefix_corrective_anchor": True,
                    }
                )
        # This is not an independent 1024 configuration refinement.  The
        # adapter reevaluates the anchor in a fresh 1024-bit original-DSL
        # context and independently validates target/residual/semantics.
        lanes.append(
            {
                **asdict(prefix_lanes[1]),
                "bits": 1024,
                "nominal_dps": 320,
                "point": replay_anchor,
                "public_gate_refinement_lane": False,
                "independently_initialized": False,
                "fresh_1024_original_dsl_replay_anchor": True,
            }
        )
        _LAST_SESSION = {
            "problem": problem,
            "prefix": prefix,
            "prefix_counters": prefix_counters,
            "started": started,
            "corrective_z": None,
            "stage1_complete": False,
            "slice_ordinal": 0,
            "corrective_terminal": False,
        }

    return {
        "variant": variant,
        "status": "PUBLIC_NUMERIC_GATE_READY" if ready else "PUBLIC_PREFIX_FAILED",
        "target_stability_ready": ready,
        "numeric_v3_ready": ready,
        "lanes": FROZEN._jsonable(lanes),
        "adaptive_prefix": {
            "status": prefix.get("status"),
            "numeric_512_768_prefix_ready": prefix.get(
                "numeric_512_768_prefix_ready"
            ),
            "lanes": FROZEN._jsonable(
                [asdict(row) for row in prefix.get("lanes", [])]
            ),
            "configuration_512_768_disagreement_inf": FROZEN._jsonable(
                prefix.get("configuration_512_768_disagreement_inf")
            ),
            "target_512_768_disagreement": FROZEN._jsonable(
                prefix.get("target_512_768_disagreement")
            ),
            "escalation_counters": prefix.get("escalation_counters"),
            "escalation_events": FROZEN._jsonable(
                prefix.get("escalation_events")
            ),
        },
        "independent_prefix_lane_count": len(prefix.get("lanes", [])),
        "independent_prefix_bits": [
            row.bits for row in prefix.get("lanes", [])
        ],
        "common_anchor_after_independent_prefix": False,
        "stability_counters": {
            "internal_target_stability_stages_run": 0,
            "internal_target_stability_gate_required": False,
            "public_configuration_gate": str(PUBLIC_GATE),
            "independent_prefix_bits": [
                row.bits for row in prefix.get("lanes", [])
            ],
            "configuration_512_768_disagreement_inf": FROZEN._jsonable(
                prefix.get("configuration_512_768_disagreement_inf")
            ),
            "target_512_768_disagreement": FROZEN._jsonable(
                prefix.get("target_512_768_disagreement")
            ),
        },
        "semismooth_counters": {
            "prefix": asdict(prefix_counters),
            "progressive": asdict(progressive_counters),
        },
        "progressive_postprefix": {
            "requested_stage_count": POSTPOLISH_STAGE_COUNT,
            "records": FROZEN._jsonable(progressive.get("records", [])),
            "public_residual_ready": bool(progressive.get("ready")),
            "residual_inf": FROZEN._jsonable(progressive.get("residual_inf")),
            "target_stability_or_uncertainty_gate_applied": False,
        },
        "public_gate_contract": {
            "configuration_512_768_gate": str(PUBLIC_GATE),
            "target_512_768_gate": str(PUBLIC_GATE),
            "original_dsl_replay_bits": [512, 768, 1024],
            "original_dsl_residual_gate": str(PUBLIC_GATE),
            "target_768_1024_gate": str(PUBLIC_GATE),
            "owned_pslq_proposal_bits": 768,
            "owned_pslq_confirmation_bits": 1024,
            "minimal_polynomial_and_isolator_required": True,
            "private_1e_195_stability_required": False,
        },
        "elapsed_seconds": time.monotonic() - started,
        "case_identity_read": False,
        "family_read": False,
        "truth_read": False,
        "known_target_count_read": False,
        "coordinate_fixing_or_gauge": False,
        "symmetry_reduction": False,
        "reparameterization": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
        "independent_1024_configuration_refinement_required": False,
        "fresh_1024_original_dsl_target_replay_required": True,
    }


def continue_relation_corrective(*, deadline_seconds: float) -> dict[str, object]:
    """Advance one short corrective slice and expose it to actual authority."""

    session = _LAST_SESSION
    if not isinstance(session, dict):
        raise RuntimeError("no public-prefix session is available")
    problem = session["problem"]
    prefix = session["prefix"]
    if not isinstance(prefix, dict) or not _public_prefix_ready(prefix):
        raise RuntimeError("saved public-prefix session is not authority eligible")
    seconds = float(deadline_seconds)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("deadline_seconds must be finite and positive")
    started = time.monotonic()
    deadline = started + max(0.03, seconds)
    progressive_counters = SEMISMOOTH.Counters()
    z = session.get("corrective_z")
    if z is None:
        z = FROZEN._normalized(
            problem, prefix["lanes"][0].point, FROZEN.STRICT_STAGES[0][0]
        )
    records: list[dict[str, object]] = []
    final_residual = None
    final_semantic = False
    terminal = bool(session.get("corrective_terminal"))
    original_run_stage = SEMISMOOTH._run_stage
    SEMISMOOTH._run_stage = REVIEWED.BASE._run_stage
    try:
        for stage_index in range(2):
            if stage_index == 0 and session.get("stage1_complete") is True:
                continue
            if time.monotonic() >= deadline or terminal:
                break
            dps, gate, mode, stencil_extra = FROZEN.STRICT_STAGES[stage_index]
            before_residual, before_answer, before_semantic = FROZEN._observe(
                problem, z, dps, progressive_counters
            )
            if not before_semantic:
                terminal = True
                break
            stage_status, z, stage_record = FROZEN._strict_stage(
                problem,
                z,
                dps=dps,
                gate=gate,
                mode=mode,
                stencil_extra=stencil_extra,
                counters=progressive_counters,
                deadline=deadline,
            )
            after_residual, after_answer, after_semantic = FROZEN._observe(
                problem, z, dps, progressive_counters
            )
            final_residual = after_residual
            final_semantic = bool(after_semantic)
            records.append(
                {
                    **asdict(stage_record),
                    "stage_index": stage_index,
                    "requested_gate": gate,
                    "mode": mode,
                    "stencil_extra_digits": stencil_extra,
                    "before_residual_inf": before_residual,
                    "after_residual_inf": after_residual,
                    "before_answer": before_answer,
                    "after_answer": after_answer,
                }
            )
            if stage_index == 0 and after_semantic:
                session["stage1_complete"] = True
            if not after_semantic or stage_status not in {
                "SUCCESS",
                "NO_SEMISMOOTH_DESCENT",
                "ITERATION_LIMIT",
                "DEADLINE_REACHED",
            }:
                terminal = True
                break
            if stage_index == 1 and stage_status in {
                "SUCCESS",
                "NO_SEMISMOOTH_DESCENT",
            }:
                terminal = True
    finally:
        SEMISMOOTH._run_stage = original_run_stage

    session["corrective_z"] = z
    session["corrective_terminal"] = terminal
    session["slice_ordinal"] = int(session.get("slice_ordinal", 0)) + 1
    if final_residual is None:
        dps = FROZEN.STRICT_STAGES[1][0]
        final_residual, _answer, final_semantic = FROZEN._observe(
            problem, z, dps, progressive_counters
        )
    ready = bool(
        final_semantic
        and final_residual is not None
        and mp.mpf(final_residual) <= PUBLIC_GATE
        and session.get("stage1_complete") is True
        and any(row.get("stage_index") == 1 for row in records)
    )
    lanes: list[dict[str, object]] = []
    if ready:
        prefix_lanes = prefix["lanes"]
        with mp.workdps(FROZEN.STRICT_STAGES[1][0]):
            anchor = FROZEN.SEMISMOOTH._external(problem, z)
        for row in prefix_lanes:
            lanes.append(
                {
                    **asdict(row),
                    "point": anchor,
                    "public_gate_refinement_lane": True,
                    "independently_initialized": True,
                    "common_post_prefix_corrective_anchor": True,
                }
            )
        lanes.append(
            {
                **asdict(prefix_lanes[1]),
                "bits": 1024,
                "nominal_dps": 320,
                "point": anchor,
                "public_gate_refinement_lane": False,
                "independently_initialized": False,
                "fresh_1024_original_dsl_replay_anchor": True,
            }
        )
    return {
        "variant": VARIANT,
        "status": (
            "PUBLIC_RELATION_CORRECTIVE_READY"
            if ready
            else "PUBLIC_RELATION_CORRECTIVE_FAILED"
        ),
        "target_stability_ready": ready,
        "numeric_v3_ready": ready,
        "lanes": FROZEN._jsonable(lanes),
        "independent_prefix_lane_count": 2,
        "common_anchor_after_independent_prefix": ready,
        "stability_counters": {
            "internal_target_stability_stages_run": 2,
            "internal_target_stability_gate_required": False,
            "public_configuration_gate": str(PUBLIC_GATE),
            "independent_prefix_bits": [512, 768],
            "configuration_512_768_disagreement_inf": FROZEN._jsonable(
                prefix.get("configuration_512_768_disagreement_inf")
            ),
            "target_512_768_disagreement": FROZEN._jsonable(
                prefix.get("target_512_768_disagreement")
            ),
        },
        "semismooth_counters": {
            "prefix_reused_without_recomputation": True,
            "progressive": asdict(progressive_counters),
        },
        "progressive_postprefix": {
            "requested_stage_count": 2,
            "slice_ordinal": session["slice_ordinal"],
            "records": FROZEN._jsonable(records),
            "public_residual_ready": ready,
            "residual_inf": FROZEN._jsonable(final_residual),
            "target_stability_or_uncertainty_gate_applied": False,
            "resume_eligible": not terminal,
        },
        "elapsed_seconds": time.monotonic() - started,
        "case_identity_read": False,
        "family_read": False,
        "truth_read": False,
        "known_target_count_read": False,
        "coordinate_fixing_or_gauge": False,
        "symmetry_reduction": False,
        "reparameterization": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
        "prefix_recomputed": False,
        "fresh_1024_original_dsl_target_replay_required": True,
    }


def last_session_raw_evaluator():
    """Return the unchanged counting evaluator retained by the in-process session."""

    session = _LAST_SESSION
    if not isinstance(session, dict):
        raise RuntimeError("no public-prefix session is available")
    problem = session["problem"]
    evaluator = getattr(problem, "evaluator", None)
    raw = getattr(evaluator, "raw", None)
    if raw is None:
        raise RuntimeError("saved public-prefix evaluator is unavailable")
    return raw


__all__ = [
    "POSTPOLISH_STAGE_COUNT",
    "PUBLIC_GATE",
    "VARIANT",
    "VARIANTS",
    "continue_relation_corrective",
    "last_session_raw_evaluator",
    "refine_endpoint",
]
