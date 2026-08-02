"""Compose event-refreshed direct Broyden with public-gate HP stopping.

This disposable candidate changes only the numerical step implementation used
by the existing high-precision refiner.  The two independently initialized
512/768 prefix lanes and any relation-corrective strict stages use the v16
event-refreshed direct-good-Broyden model.  The v16 public-gate candidate still
owns stopping, lane construction, and the resumable corrective session.  The
unchanged adapter owns original-DSL replay and numerical-v3 authority.

No source, equation, variable, bound, gauge, symmetry, or parameterization
transform is introduced here.
"""

from __future__ import annotations

from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys
from typing import Mapping, Sequence


HERE = Path(__file__).resolve().parent
PUBLIC_PATH = HERE.parent / "public_gate_progressive_hp_v16/candidate.py"
QUASI_NEWTON_PATH = HERE.parent / "hp_quasi_newton_v16/integrated_candidate.py"


def _load(name: str, path: Path):
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


PUBLIC = _load("geotarget_exp008_combined_v17_public", PUBLIC_PATH)
QUASI_NEWTON = _load("geotarget_exp008_combined_v17_broyden", QUASI_NEWTON_PATH)

# Both candidates deliberately load the same frozen evaluator/refiner engine.
# A split engine would make monkey-patching silently ineffective, so fail
# closed instead of running a partially composed algorithm.
if PUBLIC.FROZEN is not QUASI_NEWTON.FROZEN:
    raise RuntimeError("public-gate and Broyden candidates use different frozen engines")
if PUBLIC.SEMISMOOTH is not QUASI_NEWTON.SEMISMOOTH:
    raise RuntimeError("public-gate and Broyden candidates use different semismooth engines")
if PUBLIC.REVIEWED.BASE is not QUASI_NEWTON.CONTROL.BASE:
    raise RuntimeError("public-gate and Broyden candidates use different prefix engines")

FROZEN = PUBLIC.FROZEN
SEMISMOOTH = PUBLIC.SEMISMOOTH
VARIANT = PUBLIC.VARIANT
VARIANTS = PUBLIC.VARIANTS
PUBLIC_GATE = PUBLIC.PUBLIC_GATE
POSTPOLISH_STAGE_COUNT = 0
CONFIGURATION = QUASI_NEWTON.EVENT_REFRESHED

_PREFIX_PHASES: list[dict[str, object]] = []
_CORRECTIVE_STATE = None


def _phase_rows() -> list[dict[str, object]]:
    rows = [dict(row) for row in _PREFIX_PHASES]
    if _CORRECTIVE_STATE is not None:
        rows.append(_CORRECTIVE_STATE.summary())
    return rows


def _decorate(result: Mapping[str, object]) -> dict[str, object]:
    decorated = dict(result)
    stability = result.get("stability_counters")
    stability = dict(stability) if isinstance(stability, Mapping) else {}
    phases = _phase_rows()
    stability.update(
        {
            "hp_quasi_newton_configuration": CONFIGURATION,
            "hp_quasi_newton_phases": phases,
            "public_gate_progressive_stopping": True,
        }
    )
    decorated["stability_counters"] = stability
    decorated["hp_quasi_newton"] = {
        "configuration": CONFIGURATION,
        "policy": asdict(QUASI_NEWTON._policy()),
        "phases": phases,
        "mechanism": QUASI_NEWTON.KERNEL.mechanism_manifest(),
        "checkpointable": True,
        "checkpoint_scope": "in_process_public_relation_corrective_only",
    }
    decorated["combined_refiner"] = {
        "event_refreshed_direct_good_broyden": True,
        "public_gate_progressive_stopping": True,
        "private_1e_195_stability_required": False,
        "source_or_problem_modified": False,
        "variables_or_equations_changed": False,
        "bounds_added_or_inferred": False,
        "gauge_or_symmetry_reduction": False,
        "coordinate_reparameterization": False,
        "case_family_truth_or_known_target_count_read": False,
    }
    decorated["source_or_problem_modified"] = False
    decorated["variables_or_equations_changed"] = False
    decorated["bounds_added_or_inferred"] = False
    decorated["gauge_or_symmetry_reduction"] = False
    decorated["coordinate_reparameterization"] = False
    return decorated


def refine_endpoint(
    evaluator,
    endpoint: Sequence[float],
    *,
    variant: str = VARIANT,
    deadline_seconds: float = 23.0,
):
    """Run the public-gate schedule with Broyden prefix stages."""

    if CONFIGURATION != QUASI_NEWTON.EVENT_REFRESHED:
        raise ValueError("only the frozen event-refreshed configuration is supported")
    global _CORRECTIVE_STATE
    _CORRECTIVE_STATE = None
    _PREFIX_PHASES.clear()
    QUASI_NEWTON._PHASE_SUMMARIES.clear()
    QUASI_NEWTON.CONFIGURATION = QUASI_NEWTON.EVENT_REFRESHED
    QUASI_NEWTON._ACTIVE_STATE = None
    PUBLIC.POSTPOLISH_STAGE_COUNT = 0

    original_two_prefix = PUBLIC.REVIEWED._two_prefix_lanes
    original_base_stage = PUBLIC.REVIEWED.BASE._run_stage
    PUBLIC.REVIEWED._two_prefix_lanes = QUASI_NEWTON._two_prefix_lanes
    PUBLIC.REVIEWED.BASE._run_stage = QUASI_NEWTON._prefix_stage
    try:
        result = PUBLIC.refine_endpoint(
            evaluator,
            endpoint,
            variant=variant,
            deadline_seconds=deadline_seconds,
        )
    finally:
        PUBLIC.REVIEWED._two_prefix_lanes = original_two_prefix
        PUBLIC.REVIEWED.BASE._run_stage = original_base_stage
        QUASI_NEWTON._ACTIVE_STATE = None

    _PREFIX_PHASES.extend(dict(row) for row in QUASI_NEWTON._PHASE_SUMMARIES)
    if result.get("numeric_v3_ready") is True:
        _CORRECTIVE_STATE = QUASI_NEWTON._ModelState(
            phase="common-anchor-public-relation-corrective"
        )
    return _decorate(result)


def continue_relation_corrective(*, deadline_seconds: float) -> dict[str, object]:
    """Resume the public relation correction with one persistent Broyden model."""

    state = _CORRECTIVE_STATE
    if state is None:
        raise RuntimeError("no Broyden public-prefix session is available")
    original_strict_stage = FROZEN._strict_stage
    QUASI_NEWTON._ACTIVE_STATE = state
    FROZEN._strict_stage = QUASI_NEWTON._strict_stage
    try:
        result = PUBLIC.continue_relation_corrective(
            deadline_seconds=deadline_seconds
        )
    finally:
        FROZEN._strict_stage = original_strict_stage
        QUASI_NEWTON._ACTIVE_STATE = None
    return _decorate(result)


def last_session_raw_evaluator():
    return PUBLIC.last_session_raw_evaluator()


__all__ = [
    "CONFIGURATION",
    "POSTPOLISH_STAGE_COUNT",
    "PUBLIC_GATE",
    "VARIANT",
    "VARIANTS",
    "continue_relation_corrective",
    "last_session_raw_evaluator",
    "refine_endpoint",
]
