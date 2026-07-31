"""25% current-search guard-billiard overlay; 75% baseline ordinals untouched."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import time
from typing import Mapping

import numpy as np


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get("GEOTARGET_EXPERIMENT_RUNTIME", "/home/kabatan/work/solver-experiment-runtime/solver")
).resolve()
BASE_ADAPTER = RUNTIME_ROOT / "research/experiments/EXP-REAL61-008/dev41_restoration_filter_v3/adapter.py"
BASE_CANDIDATE = RUNTIME_ROOT / "research/experiments/EXP-REAL61-008/dev41_restoration_filter_v3/candidate.py"
PORTAL_CONNECTOR = HERE.parent / "exact_replayed_guard_billiard_portal_v2/candidate.py"
EXPECTED = {
    BASE_ADAPTER: "0e37b244f428a1953ab5074ad52d2cf9d6bfa41b6ba6798f1acbcc66cf635983",
    BASE_CANDIDATE: "61ade7133531d6a74675896deea2e1ca8cd833238005595b50ac044cf86cf29d",
    PORTAL_CONNECTOR: "6bcbbceb511c2d8fcf4b9b217f56a43163da7e357bd9a483ea1393617386fc79",
}

CONTROL = "source_literal_lexicographic_restoration_filter_rrqr"
ARM = "source_literal_guard_billiard_exact_terminal_25pct_v2"
ARMS = (CONTROL, ARM)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    expected = EXPECTED[path]
    if not path.is_file() or _sha(path) != expected:
        raise RuntimeError(f"guard-billiard dependency changed: {path.name}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    if Path(module.__file__).resolve() != path.resolve():
        raise RuntimeError("loaded guard-billiard dependency identity changed")
    return module


for _path, _expected in EXPECTED.items():
    if not _path.is_file() or _sha(_path) != _expected:
        raise RuntimeError(f"guard-billiard dependency changed: {_path}")

BASE = _load("geotarget_guard_billiard_current_base_adapter", BASE_ADAPTER)
CANDIDATE = BASE.CANDIDATE_MODULE
PORTAL = _load("geotarget_guard_billiard_exact_terminal_connector", PORTAL_CONNECTOR)
FROZEN = PORTAL.FROZEN
PRECISION_RUNTIME = BASE.BASE.PRECISION_RUNTIME if hasattr(BASE.BASE, "PRECISION_RUNTIME") else None


def build_literal_prefix(document, base_case, base_policy):
    return BASE.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm not in ARMS:
        raise ValueError(f"unknown guard-billiard arm: {arm!r}")
    return CANDIDATE.compile_program(document)


def _lane_case(base_case, quota):
    return replace(
        base_case,
        evaluate=quota.evaluate,
        progressive_residual=quota.progressive,
    )


def _solve(case, program, start, scale, lower, upper, cap, deadline):
    return CANDIDATE.solve_local(
        case,
        program,
        CANDIDATE.CONFIGURATION,
        start,
        per_start_scale=scale,
        source_lower=lower,
        source_upper=upper,
        max_callbacks=max(2, cap),
        deadline_monotonic=deadline,
    )


def _guard_view(lane_case, program, scale, counters):
    def guards(point):
        try:
            state = CANDIDATE.CORE.CORE._make_state(
                lane_case,
                program,
                np.asarray(point, dtype=float),
                CANDIDATE.CONFIGURATION,
                counters,
            )
            margins = np.asarray(state.margins, dtype=float)
            gradients = np.asarray(state.margin_jacobian_x, dtype=float)
            supported = bool(
                state.semantics_valid
                and margins.ndim == 1
                and gradients.shape == (margins.size, scale.size)
                and np.all(np.isfinite(margins))
                and np.all(np.isfinite(gradients))
            )
            # Riesz vectors for <v,w> = (v/scale).(w/scale).
            normals = tuple(scale * scale * row for row in gradients)
            return FROZEN.GuardObservation(margins, normals, supported)
        except Exception:
            return FROZEN.GuardObservation(np.asarray([-1.0]), (np.zeros_like(scale),), False)

    return FROZEN.SolverView(
        lambda value: np.asarray(value, dtype=float),
        guards,
        lambda _value: FROZEN.Replay(False, None),
        lambda left, right: float((np.asarray(left) / scale) @ (np.asarray(right) / scale)),
    )


def _portal(lane_case, program, start, endpoint, scale, counters):
    if endpoint.shape != start.shape or not np.all(np.isfinite(endpoint)):
        return None, 0
    velocity = endpoint - start
    if not np.all(np.isfinite(velocity)) or float(np.linalg.norm(velocity / scale)) <= 1.0e-10:
        return None, 0
    view = _guard_view(lane_case, program, scale, counters)
    launch_guard = FROZEN._guard(view, FROZEN.Ledger(8), start)
    endpoint_guard = FROZEN._guard(view, FROZEN.Ledger(8), endpoint)
    if not FROZEN._inside(launch_guard) or endpoint_guard is None or FROZEN._inside(endpoint_guard):
        return None, 0
    return FROZEN._billiard(
        view,
        FROZEN.Ledger(256),
        start,
        velocity,
        path_length=1.30,
        step_length=0.13,
        max_reflections=4,
    )


def run_local_arm(
    arm: str,
    *,
    base_case,
    budget,
    program,
    literal_prefix,
    callback_cap: int,
    callbacks_per_start: int,
    deadline_monotonic: float,
):
    if arm not in ARMS:
        raise ValueError(f"unknown guard-billiard arm: {arm!r}")
    endpoints = []
    statuses = Counter()
    counters = Counter()
    lane_callbacks = []
    for lane, raw_start in enumerate(literal_prefix.points):
        if int(budget.callbacks) >= callback_cap or time.monotonic() >= deadline_monotonic:
            statuses["global_stop_before_lane"] += 1
            break
        lane_begin = int(budget.callbacks)
        start = np.asarray(raw_start, dtype=float)
        scale = np.maximum(1.0, np.abs(start))
        lane_cap = min(callbacks_per_start, callback_cap - lane_begin)
        side = arm == ARM and lane % 4 == 2 and lane_cap >= 4
        primary_cap = max(2, lane_cap // 2) if side else lane_cap
        primary_quota = BASE.BASE.LaneQuota(base_case, budget, primary_cap)
        try:
            primary = _solve(
                _lane_case(base_case, primary_quota), program, start, scale,
                base_case.lower, base_case.upper, primary_cap, deadline_monotonic,
            )
            statuses[str(primary.status)] += 1
            counters.update(BASE.BASE._counter_map(primary.counters))
            selected = np.asarray(primary.endpoint, dtype=float)
        except Exception as error:
            statuses[f"exception:{type(error).__name__}"] += 1
            counters["lane_exceptions"] += 1
            selected = np.asarray(start, dtype=float)

        if side and time.monotonic() < deadline_monotonic:
            remaining = lane_cap - (int(budget.callbacks) - lane_begin)
            if remaining >= 2:
                side_quota = BASE.BASE.LaneQuota(base_case, budget, remaining)
                side_case = _lane_case(base_case, side_quota)
                portal_counters = CANDIDATE._initial_counters()
                proposal, reflections = _portal(
                    side_case, program, start, selected, scale, portal_counters
                )
                counters["guard_billiard_side_lane"] += 1
                counters["guard_billiard_reflections"] += int(reflections)
                counters.update(
                    {f"guard_billiard_provenance:{key}": value for key, value in portal_counters.items()}
                )
                if proposal is not None:
                    remaining_after_portal = lane_cap - (int(budget.callbacks) - lane_begin)
                    if remaining_after_portal >= 2:
                        try:
                            secondary = _solve(
                                side_case, program, np.asarray(proposal), scale,
                                base_case.lower, base_case.upper,
                                remaining_after_portal, deadline_monotonic,
                            )
                            statuses[f"portal:{secondary.status}"] += 1
                            counters.update(BASE.BASE._counter_map(secondary.counters))
                            if str(secondary.status) == "safe_root":
                                selected = np.asarray(secondary.endpoint, dtype=float)
                                counters["guard_billiard_safe_handoff"] += 1
                        except Exception as error:
                            statuses[f"portal_exception:{type(error).__name__}"] += 1
                            counters["guard_billiard_portal_exceptions"] += 1

        if selected.shape == (base_case.dimension,) and np.all(np.isfinite(selected)):
            endpoints.append((lane, selected.copy()))
        lane_callbacks.append(int(budget.callbacks) - lane_begin)

    baseline_lanes = (
        sum(index % 4 != 2 for index in range(len(lane_callbacks)))
        if arm == ARM
        else len(lane_callbacks)
    )
    counters["guard_billiard_baseline_ordinal_count"] += baseline_lanes
    counters["guard_billiard_side_ordinal_count"] += len(lane_callbacks) - baseline_lanes
    return BASE.BASE.LocalScreenOutcome(
        endpoints=tuple(endpoints),
        statuses=dict(statuses),
        counters=dict(counters),
        lane_callbacks=tuple(lane_callbacks),
    )


def configuration_manifest() -> Mapping[str, object]:
    return {
        "schema_version": "geotarget.guard-billiard-current-search-v2/v1",
        "arms": list(ARMS),
        "baseline_fraction_lower_bound": 0.75,
        "side_route_fraction_upper_bound": 0.25,
        "side_route_ordinal": "2 mod 4",
        "baseline_ordinal_solver_and_budget_unchanged": True,
        "side_route": "half-budget evidence, analytic source-margin billiard, remaining-budget solve",
        "unsupported_guard_derivative_fallback": "original primary endpoint",
        "exact_terminal": "existing exact_outer exact-coordinate and canonical source replay",
        "source_problem_modified": False,
        "truth_case_family_target_count_outcome_routing": False,
        "dependency_sha256": {str(path): digest for path, digest in EXPECTED.items()},
    }


BINDING_RECORD = configuration_manifest()
