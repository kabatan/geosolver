"""Repair A: current adaptive baseline followed only by an additive DiGS tail."""

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
CANDIDATE = "progressive_adaptive_hybrid_plus_additive_digs_tail"
ARMS = (CONTROL, CANDIDATE)
MAX_SCOUT_CALLBACKS = 64
MAX_PROPOSALS = 4
MIN_SCOUT_CALLBACKS = 12
TAIL_START_RESERVE_SECONDS = 3.25
SCOUT_MAX_WALL_SECONDS = 1.0
PORTAL_SOURCE = "diffusive_gibbs_additive_tail"


def _load(name: str, path: Path, expected: str):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"hash-bound additive DiGS dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load("geotarget_additive_digs_current_adaptive", BASE_PATH, BASE_SHA256)
PORTAL = _load("geotarget_additive_digs_portal", PORTAL_PATH, PORTAL_SHA256)
PRECISION_RUNTIME = BASE.PRECISION_RUNTIME


def build_literal_prefix(document, base_case, base_policy):
    return BASE.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm not in ARMS:
        raise ValueError(f"unknown additive DiGS arm: {arm!r}")
    return BASE.compile_program(BASE.CANDIDATE, document)


def set_partial_output(path: Path | None) -> None:
    BASE.set_partial_output(path)


def _same_point(left: Sequence[float], right: Sequence[float]) -> bool:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    return a.shape == b.shape and a.tobytes() == b.tobytes()


def _anchors(baseline, prefix: object, dimension: int) -> tuple[np.ndarray, ...]:
    values: list[np.ndarray] = []
    seen: set[bytes] = set()
    for raw in (
        *tuple(getattr(prefix, "points")),
        *(endpoint for _lane, endpoint in baseline.endpoints),
    ):
        point = np.asarray(raw, dtype=float)
        if point.shape != (dimension,) or not np.all(np.isfinite(point)):
            continue
        key = point.tobytes()
        if key in seen:
            continue
        seen.add(key)
        values.append(point.copy())
    return tuple(values)


def _isolated_portal(
    *,
    base_case: object,
    budget: object,
    callback_cap: int,
    deadline: float,
    anchors: Sequence[Sequence[float]],
    scout_cap: int,
):
    deep = BASE.BASE.DEEP
    before = deep._budget_state(budget)
    telemetry = deep._SharedTelemetry(int(base_case.dimension), before)
    chart = PORTAL.affine_chart(anchors)
    if chart is None:
        return None, 0, None

    def child():
        original_charge = getattr(budget, "_charge", None)
        if callable(original_charge):
            def tracked_charge() -> None:
                original_charge()
                telemetry.update_budget(budget)
            setattr(budget, "_charge", tracked_charge)

        def evaluate(point):
            try:
                return base_case.evaluate(np.asarray(point, dtype=float))
            finally:
                telemetry.update_budget(budget)

        result = PORTAL.KERNEL.propose(
            evaluate,
            anchors[:4],
            chart,
            seed=270_019,
            configuration=PORTAL.KERNEL.Configuration(
                maximum_calls=scout_cap,
                proposal_count=MAX_PROPOSALS,
            ),
        )
        telemetry.update_budget(budget)
        return {"result": result, "budget_after": telemetry.budget_state()}

    now = time.monotonic()
    useful = deadline - TAIL_START_RESERVE_SECONDS - now
    if useful <= 0.1:
        return None, 0, None
    isolated = deep.ISOLATION.run_preemptible(
        child,
        absolute_deadline=now + min(SCOUT_MAX_WALL_SECONDS, 0.25 * useful),
    )
    payload = isolated.payload if isinstance(isolated.payload, Mapping) else None
    after = (
        payload["budget_after"]
        if payload is not None and isinstance(payload.get("budget_after"), deep._BudgetState)
        else telemetry.budget_state()
    )
    used = deep._apply_child_budget(
        budget,
        before=before,
        after=after,
        allowance=scout_cap,
        callback_cap=callback_cap,
    )
    return (payload["result"] if payload is not None else None), used, isolated


def _annotate(baseline, statuses: Counter, counters: Counter, *, tail=None, offset=0):
    merged_statuses = Counter({str(key): int(value) for key, value in baseline.statuses.items()})
    merged_statuses.update(statuses)
    merged_counters = Counter({str(key): int(value) for key, value in baseline.counters.items()})
    merged_counters.update(counters)
    endpoints = tuple(baseline.endpoints)
    lane_callbacks = tuple(baseline.lane_callbacks)
    if tail is not None:
        endpoints += tuple((offset + int(lane), point) for lane, point in tail.endpoints)
        lane_callbacks += tuple(tail.lane_callbacks)
        merged_statuses.update({f"digs_tail:{key}": int(value) for key, value in tail.statuses.items()})
        merged_counters.update({f"digs_tail:{key}": int(value) for key, value in tail.counters.items()})
    return replace(
        baseline,
        endpoints=endpoints,
        lane_callbacks=lane_callbacks,
        statuses=dict(merged_statuses),
        counters=dict(merged_counters),
    )


def run_local_arm(arm: str, **kwargs):
    if arm not in ARMS:
        raise ValueError(f"unknown additive DiGS arm: {arm!r}")
    baseline = BASE.run_local_arm(BASE.CANDIDATE, **kwargs)
    if arm == CONTROL:
        return baseline

    budget = kwargs["budget"]
    callback_cap = int(kwargs["callback_cap"])
    deadline = float(kwargs["deadline_monotonic"])
    remaining = max(0, callback_cap - int(getattr(budget, "callbacks", 0)))
    # Exact fallback: no object reconstruction, no status/counter mutation.
    if remaining < MIN_SCOUT_CALLBACKS + 2 or time.monotonic() + TAIL_START_RESERVE_SECONDS >= deadline:
        return baseline

    dimension = int(kwargs["base_case"].dimension)
    anchors = _anchors(baseline, kwargs["literal_prefix"], dimension)
    if len(anchors) < max(4, dimension + 1):
        return baseline
    scout_cap = min(MAX_SCOUT_CALLBACKS, max(MIN_SCOUT_CALLBACKS, remaining // 4))
    result, scout_used, isolated = _isolated_portal(
        base_case=kwargs["base_case"],
        budget=budget,
        callback_cap=callback_cap,
        deadline=deadline,
        anchors=anchors,
        scout_cap=scout_cap,
    )
    statuses: Counter[str] = Counter()
    counters: Counter[str] = Counter({
        "digs_additive_baseline_endpoints": len(baseline.endpoints),
        "digs_additive_baseline_lanes": len(baseline.lane_callbacks),
        "digs_additive_scout_callbacks": scout_used,
    })
    if isolated is not None:
        counters["digs_additive_child_reaped"] = int(not isolated.child_alive_after_join)
        counters["digs_additive_child_timed_out"] = int(isolated.timed_out)
        counters["digs_additive_child_terminated"] = int(isolated.terminated)
    if result is None:
        statuses["digs_additive_no_scout_result"] += 1
        return _annotate(baseline, statuses, counters)

    lower = np.asarray(kwargs["base_case"].lower, dtype=float)
    upper = np.asarray(kwargs["base_case"].upper, dtype=float)
    proposals = tuple(
        point
        for raw in result.proposals
        if (point := np.asarray(raw, dtype=float)).shape == (dimension,)
        and np.all(np.isfinite(point))
        and np.all(point >= lower)
        and np.all(point <= upper)
        and not any(_same_point(point, old) for _lane, old in baseline.endpoints)
    )[:MAX_PROPOSALS]
    counters["digs_additive_raw_proposals"] = len(result.proposals)
    counters["digs_additive_admissible_proposals"] = len(proposals)
    counters["digs_additive_metropolis_accepts"] = int(result.accepted)
    if not proposals:
        statuses["digs_additive_no_admissible_proposal"] += 1
        return _annotate(baseline, statuses, counters)

    # The current adaptive scheduler's safety contract requires a dense cohort
    # of at least four starts with ordinal zero carrying its insurance source.
    # Cycling only already-admissible DiGS proposals satisfies that contract;
    # it does not borrow or replace any baseline start.
    tail_points = tuple(proposals[index % len(proposals)] for index in range(4))
    tail_sources = (
        BASE.POLICY.INSURANCE_SOURCE,
        PORTAL_SOURCE,
        PORTAL_SOURCE,
        PORTAL_SOURCE,
    )
    remaining = max(0, callback_cap - int(getattr(budget, "callbacks", 0)))
    if remaining < 2 * len(tail_points) or time.monotonic() + TAIL_START_RESERVE_SECONDS >= deadline:
        statuses["digs_additive_no_tail_budget"] += 1
        return _annotate(baseline, statuses, counters)
    delegated = dict(kwargs)
    delegated["literal_prefix"] = SimpleNamespace(
        points=tail_points,
        sources=tail_sources,
    )
    delegated["callbacks_per_start"] = min(
        int(kwargs["callbacks_per_start"]),
        max(2, remaining // len(tail_points)),
    )
    try:
        tail = BASE.run_local_arm(BASE.CANDIDATE, **delegated)
    except Exception as error:
        statuses[f"digs_additive_tail_exception:{type(error).__name__}"] += 1
        return _annotate(baseline, statuses, counters)
    statuses["digs_additive_tail_active"] += 1
    counters["digs_additive_tail_endpoints"] = len(tail.endpoints)
    counters["digs_additive_tail_lanes"] = len(tail.lane_callbacks)
    output = _annotate(
        baseline,
        statuses,
        counters,
        tail=tail,
        offset=len(getattr(kwargs["literal_prefix"], "points")),
    )
    endpoint_prefix_exact = all(
        old_lane == new_lane and _same_point(old_point, new_point)
        for (old_lane, old_point), (new_lane, new_point)
        in zip(
            baseline.endpoints,
            output.endpoints[: len(baseline.endpoints)],
            strict=True,
        )
    )
    if not endpoint_prefix_exact:
        raise AssertionError("additive DiGS suppressed or reordered a baseline endpoint")
    if output.lane_callbacks[: len(baseline.lane_callbacks)] != baseline.lane_callbacks:
        raise AssertionError("additive DiGS suppressed baseline lane work")
    if int(getattr(budget, "callbacks", 0)) > callback_cap:
        raise AssertionError("additive DiGS exceeded aggregate callback cap")
    return output


def configuration_manifest() -> Mapping[str, object]:
    payload: dict[str, object] = {
        "schema_version": "geotarget.exp-v15-243.digs-additive-tail-repair-a/v1",
        "control": CONTROL,
        "candidate": CANDIDATE,
        "base_adaptive_adapter_sha256": BASE_SHA256,
        "portal_sha256": PORTAL_SHA256,
        "kernel_sha256": PORTAL.FROZEN_CANDIDATE_SHA256,
        "baseline_runs_first_exactly_once": True,
        "baseline_endpoints_and_lane_work_are_union_prefix": True,
        "zero_surplus_returns_identical_outcome_object": True,
        "tail_uses_only_unused_callback_and_deadline": True,
        "canonical_source_replay_modified": False,
        "hp_reservoir_final_authority_modified": False,
        "truth_case_family_id_previous_outcome_routing": False,
    }
    payload["configuration_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


BINDING_RECORD = configuration_manifest()
