"""Thin DiGS portal in front of the current adaptive local arm.

Only start coordinates may change.  The source program, source tags, callback
ledger, local kernel, deadline and final replay stay owned by the current arm.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys
import time
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE.parent / "progressive_adaptive_hybrid_v1" / "search_adapter.py"
BASE_SHA256 = "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea"
PORTAL_PATH = HERE.parent / "diffusive_gibbs_portal_g1_prospective" / "portal.py"
PORTAL_SHA256 = "7cb8acd0cf867e4adf19d0b5b969c8839cf34215b97b03a9e1a47dd11cba068d"
CONTROL = "progressive_adaptive_hybrid_64_600"
CANDIDATE = "progressive_adaptive_hybrid_64_600_plus_digs_portal"
ARMS = (CONTROL, CANDIDATE)
SCOUT_FRACTION = 0.25
MIN_BASELINE_FRACTION = 0.75
MAX_REPLACEMENTS = 4
MAX_SCOUT_CALLBACKS = 64
MIN_SCOUT_CALLBACKS = 12
LOCAL_RESERVE_SECONDS = 3.5


def _load(name: str, path: Path, expected: str):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"hash-bound DiGS integration dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load("geotarget_digs_adaptive_base", BASE_PATH, BASE_SHA256)
PORTAL = _load("geotarget_digs_adaptive_portal", PORTAL_PATH, PORTAL_SHA256)
PRECISION_RUNTIME = BASE.PRECISION_RUNTIME


def build_literal_prefix(document, base_case, base_policy):
    return BASE.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm not in ARMS:
        raise ValueError(f"unknown DiGS integration arm: {arm!r}")
    return BASE.compile_program(BASE.CANDIDATE, document)


def set_partial_output(path: Path | None) -> None:
    BASE.set_partial_output(path)


def _same_bytes(left: Sequence[float], right: Sequence[float]) -> bool:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    return a.shape == b.shape and a.tobytes() == b.tobytes()


def _replacement_ordinals(count: int) -> tuple[int, ...]:
    allowance = min(MAX_REPLACEMENTS, int(math.floor(SCOUT_FRACTION * count)))
    # Zero-mod-4 is the registered counter-Cauchy insurance stream.
    eligible = [ordinal for ordinal in range(count) if ordinal % 4 != 0]
    return tuple(eligible[-allowance:]) if allowance else ()


def _mixed_prefix(prefix: object, proposals: Sequence[Sequence[float]]):
    original = tuple(getattr(prefix, "points"))
    sources = tuple(getattr(prefix, "sources"))
    ordinals = _replacement_ordinals(len(original))[: len(proposals)]
    points = [np.asarray(point, dtype=float).copy() for point in original]
    for ordinal, proposal in zip(ordinals, proposals, strict=True):
        points[ordinal] = np.asarray(proposal, dtype=float).copy()

    identical = sum(_same_bytes(left, right) for left, right in zip(original, points))
    changed = len(original) - identical
    insurance_identical = all(
        _same_bytes(original[index], points[index])
        for index in range(0, len(original), 4)
    )
    if (
        tuple(getattr(prefix, "sources")) != sources
        or identical < math.ceil(MIN_BASELINE_FRACTION * len(original))
        or changed > math.floor(SCOUT_FRACTION * len(original))
        or not insurance_identical
    ):
        raise AssertionError("DiGS prefix insurance contract failed")
    return (
        SimpleNamespace(points=tuple(points), sources=sources),
        {
            "digs_prefix_points": len(original),
            "digs_prefix_byte_identical": identical,
            "digs_prefix_changed": changed,
            "digs_source_tags_exact": int(tuple(getattr(prefix, "sources")) == sources),
            "digs_zero_mod4_insurance_exact": int(insurance_identical),
        },
    )


def _seed(prefix: object) -> int:
    # run_local_arm receives no worker seed.  A domain-separated fixed value is
    # preferable to hashing coordinates, which would break affine covariance.
    del prefix
    return 170_011


def _annotate(outcome, statuses: Counter, counters: Counter):
    merged_statuses = Counter(
        {str(key): int(value) for key, value in outcome.statuses.items()}
    )
    merged_statuses.update(statuses)
    merged_counters = Counter(
        {str(key): int(value) for key, value in outcome.counters.items()}
    )
    merged_counters.update(counters)
    return replace(
        outcome,
        statuses=dict(merged_statuses),
        counters=dict(merged_counters),
    )


def run_local_arm(arm: str, **kwargs):
    if arm == CONTROL:
        return BASE.run_local_arm(BASE.CANDIDATE, **kwargs)
    if arm != CANDIDATE:
        raise ValueError(f"unknown DiGS integration arm: {arm!r}")

    prefix = kwargs["literal_prefix"]
    points = tuple(getattr(prefix, "points"))
    budget = kwargs["budget"]
    callback_cap = int(kwargs["callback_cap"])
    deadline = float(kwargs["deadline_monotonic"])
    statuses: Counter[str] = Counter()
    counters: Counter[str] = Counter()
    counters["digs_prefix_points"] = len(points)
    counters["digs_prefix_byte_identical"] = len(points)
    counters["digs_prefix_changed"] = 0
    counters["digs_source_tags_exact"] = 1
    counters["digs_zero_mod4_insurance_exact"] = 1

    replacement_count = len(_replacement_ordinals(len(points)))
    remaining = max(0, callback_cap - int(getattr(budget, "callbacks", 0)))
    scout_cap = min(
        MAX_SCOUT_CALLBACKS,
        int(math.floor(SCOUT_FRACTION * callback_cap)),
        remaining,
    )
    chart = PORTAL.affine_chart(points) if replacement_count else None
    if (
        replacement_count == 0
        or scout_cap < MIN_SCOUT_CALLBACKS
        or chart is None
        or time.monotonic() + LOCAL_RESERVE_SECONDS >= deadline
    ):
        statuses["digs_portal_ineligible_fallback"] += 1
        outcome = BASE.run_local_arm(BASE.CANDIDATE, **kwargs)
        return _annotate(outcome, statuses, counters)

    calls_before = int(getattr(budget, "callbacks", 0))
    configuration = PORTAL.KERNEL.Configuration(
        maximum_calls=scout_cap,
        proposal_count=replacement_count,
    )
    # Reuse the current scheduler's process isolation and ledger reconciliation:
    # a single opaque callback therefore cannot monopolize the case deadline.
    deep = BASE.BASE.DEEP
    before = deep._budget_state(budget)
    telemetry = deep._SharedTelemetry(int(kwargs["base_case"].dimension), before)

    def isolated_scout():
        original_charge = getattr(budget, "_charge", None)
        if callable(original_charge):
            def tracked_charge() -> None:
                original_charge()
                telemetry.update_budget(budget)
            setattr(budget, "_charge", tracked_charge)

        def evaluate(point):
            try:
                return kwargs["base_case"].evaluate(np.asarray(point, dtype=float))
            finally:
                telemetry.update_budget(budget)

        result = PORTAL.KERNEL.propose(
            evaluate,
            points[:4],
            chart,
            seed=_seed(prefix),
            configuration=configuration,
        )
        telemetry.update_budget(budget)
        return {"result": result, "budget_after": telemetry.budget_state()}

    now = time.monotonic()
    useful_wall = max(0.05, deadline - LOCAL_RESERVE_SECONDS - now)
    portal_deadline = now + min(2.0, 0.25 * useful_wall)
    isolated = deep.ISOLATION.run_preemptible(
        isolated_scout,
        absolute_deadline=portal_deadline,
    )
    payload = isolated.payload if isinstance(isolated.payload, Mapping) else None
    after = (
        payload["budget_after"]
        if payload is not None and isinstance(payload.get("budget_after"), deep._BudgetState)
        else telemetry.budget_state()
    )
    calls_used = deep._apply_child_budget(
        budget,
        before=before,
        after=after,
        allowance=scout_cap,
        callback_cap=callback_cap,
    )
    result = payload["result"] if payload is not None else None
    counters["digs_child_timed_out"] = int(isolated.timed_out)
    counters["digs_child_terminated"] = int(isolated.terminated)
    counters["digs_child_killed"] = int(isolated.killed)
    counters["digs_child_error"] = int(isolated.error is not None)
    counters["digs_child_reaped"] = int(not isolated.child_alive_after_join)
    if isolated.timed_out:
        statuses["digs_portal_deadline_preempted"] += 1
    elif isolated.error is not None:
        statuses["digs_portal_child_error"] += 1
    counters["digs_scout_callbacks"] = max(0, calls_used)
    counters["digs_scout_callback_cap"] = scout_cap
    if calls_used > scout_cap or calls_used > math.floor(SCOUT_FRACTION * callback_cap):
        raise AssertionError("DiGS scout exceeded registered callback share")

    proposals = () if result is None else tuple(result.proposals)
    dimension = int(kwargs["base_case"].dimension)
    lower = np.asarray(kwargs["base_case"].lower, dtype=float)
    upper = np.asarray(kwargs["base_case"].upper, dtype=float)
    proposals = tuple(
        np.asarray(point, dtype=float).copy()
        for point in proposals
        if np.asarray(point, dtype=float).shape == (dimension,)
        and np.all(np.isfinite(np.asarray(point, dtype=float)))
        and np.all(np.asarray(point, dtype=float) >= lower)
        and np.all(np.asarray(point, dtype=float) <= upper)
    )
    counters["digs_proposals"] = len(proposals)
    if result is not None:
        counters["digs_metropolis_accepts"] = int(result.accepted)
        counters["digs_semantic_rejections"] = int(result.semantic_rejections)
        statuses[f"digs_kernel:{result.status}"] += 1

    delegated = dict(kwargs)
    if proposals and time.monotonic() + LOCAL_RESERVE_SECONDS < deadline:
        mixed, audit = _mixed_prefix(prefix, proposals)
        counters.update(audit)
        delegated["literal_prefix"] = mixed
        statuses["digs_portal_active"] += 1
    else:
        statuses["digs_portal_no_proposal_fallback"] += 1
    outcome = BASE.run_local_arm(BASE.CANDIDATE, **delegated)
    total_delta = int(getattr(budget, "callbacks", 0)) - calls_before
    counters["digs_total_callback_delta"] = total_delta
    counters["digs_scheduler_callbacks"] = sum(outcome.lane_callbacks)
    counters["digs_callback_accounting_exact"] = int(
        total_delta == calls_used + sum(outcome.lane_callbacks)
    )
    if int(getattr(budget, "callbacks", 0)) > callback_cap:
        raise AssertionError("DiGS integration exceeded aggregate callback cap")
    return _annotate(outcome, statuses, counters)


def configuration_manifest() -> Mapping[str, object]:
    payload: dict[str, object] = {
        "schema_version": "geotarget.exp-v15-243.digs-adaptive-thin-binding/v1",
        "arms": list(ARMS),
        "control": CONTROL,
        "candidate": CANDIDATE,
        "base_adaptive_adapter_sha256": BASE_SHA256,
        "portal_sha256": PORTAL_SHA256,
        "kernel_sha256": PORTAL.FROZEN_CANDIDATE_SHA256,
        "scout_callback_fraction_max": SCOUT_FRACTION,
        "baseline_prefix_fraction_min": MIN_BASELINE_FRACTION,
        "maximum_replacements": MAX_REPLACEMENTS,
        "zero_mod4_insurance_exact": True,
        "source_tags_exact": True,
        "source_problem_modified": False,
        "canonical_source_replay_modified": False,
        "hp_reservoir_and_final_authority_modified": False,
        "case_family_truth_target_or_previous_outcome_routing": False,
    }
    payload["configuration_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


BINDING_RECORD = configuration_manifest()
