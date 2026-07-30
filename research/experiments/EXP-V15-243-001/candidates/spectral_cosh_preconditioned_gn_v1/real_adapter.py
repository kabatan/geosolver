"""Thin 75% frozen champion / 25% spectral-cosh local-start adapter."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
FROZEN_ROOT = Path(os.environ.get(
    "GEOTARGET_FROZEN_REPOSITORY", "/home/kabatan/work/solver-experiment-runtime/solver"
)).resolve()
FROZEN_ADAPTER_PATH = (
    FROZEN_ROOT / "research/experiments/EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
    "corrective_nearroot_strict_restart_v2/adapter.py"
)
FROZEN_ADAPTER_SHA256 = "cda4e348ce1bb848af84afaba062c931ec5f1ebf882bdb8cf122df0366e75dc2"


def _load(name: str, path: Path, expected: str | None = None):
    if expected is not None and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"hash-bound dependency changed: {path}")
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FROZEN = _load("geotarget_spectral_cosh_frozen_adapter", FROZEN_ADAPTER_PATH, FROZEN_ADAPTER_SHA256)
CANDIDATE_MODULE = _load("geotarget_spectral_cosh_real_candidate", HERE / "real_candidate.py")
CONTROL = FROZEN.CANDIDATE
CANDIDATE = CANDIDATE_MODULE.REFERENCE_NAME
ARMS = (CONTROL, CANDIDATE)
PRECISION_RUNTIME = FROZEN.PRECISION_RUNTIME


def build_literal_prefix(document, base_case, base_policy):
    return FROZEN.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm == CONTROL:
        return FROZEN.V2.compile_program(document)
    if arm == CANDIDATE:
        return CANDIDATE_MODULE.compile_program(document)
    raise ValueError(f"unknown spectral-cosh arm: {arm!r}")


def _solve_one(module, lane_case, program, start, scale, lower, upper, cap, deadline):
    return module.solve_local(
        lane_case, program, module.REFERENCE, start,
        per_start_scale=scale,
        source_lower=lower,
        source_upper=upper,
        max_callbacks=cap,
        deadline_monotonic=deadline,
    )


def run_local_arm(
    arm: str,
    *,
    base_case: object,
    budget: object,
    program: object,
    literal_prefix: object,
    callback_cap: int,
    callbacks_per_start: int,
    deadline_monotonic: float,
):
    """Reuse the frozen loop, changing only every fourth candidate lane."""
    if arm not in ARMS:
        raise ValueError(f"unknown spectral-cosh arm: {arm!r}")
    base = FROZEN.V1.BASE
    endpoints = []
    statuses: Counter[str] = Counter()
    counters: Counter[str] = Counter()
    lane_callbacks = []
    for lane, raw_start in enumerate(literal_prefix.points):
        if int(budget.callbacks) >= callback_cap or time.monotonic() >= deadline_monotonic:
            statuses["global_stop_before_lane"] += 1
            break
        start = np.asarray(raw_start, dtype=float)
        scale = np.maximum(1.0, np.abs(start))
        lane_cap = min(callbacks_per_start, callback_cap - int(budget.callbacks))
        quota = base.LaneQuota(base_case, budget, lane_cap)
        lane_case = replace(
            base_case, evaluate=quota.evaluate, progressive_residual=quota.progressive
        )
        module = FROZEN.V2
        if arm == CANDIDATE and lane % 4 == 3:
            module = CANDIDATE_MODULE
            counters["spectral_cosh_side_lanes"] += 1
        else:
            counters["frozen_baseline_lanes"] += 1
        try:
            outcome = _solve_one(
                module, lane_case, program, start, scale, base_case.lower,
                base_case.upper, lane_cap, deadline_monotonic,
            )
            statuses[str(getattr(outcome, "status", "unknown"))] += 1
            counters.update(base._counter_map(getattr(outcome, "counters", {})))
            endpoint = np.asarray(getattr(outcome, "endpoint"), dtype=float)
            if endpoint.shape == (base_case.dimension,) and np.all(np.isfinite(endpoint)):
                endpoints.append((lane, endpoint.copy()))
        except Exception as error:
            statuses[f"exception:{type(error).__name__}"] += 1
            counters["lane_exceptions"] += 1
        lane_callbacks.append(quota.used)
    return base.LocalScreenOutcome(
        endpoints=tuple(endpoints), statuses=dict(statuses), counters=dict(counters),
        lane_callbacks=tuple(lane_callbacks),
    )


def configuration_manifest():
    payload = {
        "schema_version": "geotarget.spectral-cosh-quarter-lane/v1",
        "arms": list(ARMS),
        "control": CONTROL,
        "candidate": CANDIDATE,
        "candidate_manifest": dict(CANDIDATE_MODULE.configuration_manifest()),
        "baseline_lane_rule": "lane_ordinal_mod_4_in_0_1_2",
        "candidate_lane_rule": "lane_ordinal_mod_4_equals_3",
        "baseline_minimum_share": 0.75,
        "same_literal_prefix_callback_caps_deadline_and_replay": True,
        "case_family_truth_target_or_outcome_routing": False,
    }
    payload["configuration_digest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


BINDING_RECORD = configuration_manifest()

