"""Seconds-scale search-adapter checks; deliberately never imports exact_outer."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import time

import numpy as np


HERE = Path(__file__).resolve().parent
EXACT_OUTER = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/exact_outer_decorator/worker.py"
)
AUTHORITY_BOUNDARY = EXACT_OUTER.parent / "authority_boundary.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_adapter():
    path = HERE / "search_adapter.py"
    specification = importlib.util.spec_from_file_location(
        "geotarget_guard_billiard_current_search_smoke", path
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class FakeCase:
    dimension: int
    lower: np.ndarray
    upper: np.ndarray
    evaluate: object
    progressive_residual: object


@dataclass
class FakeBudget:
    callbacks: int = 0


@dataclass(frozen=True)
class FakeOutcome:
    endpoints: tuple
    statuses: dict
    counters: dict
    lane_callbacks: tuple


class FakeLaneQuota:
    def __init__(self, _base_case, budget, cap):
        self.budget = budget
        self.cap = int(cap)
        self.used = 0

    def evaluate(self, *_args, **_kwargs):
        assert self.used < self.cap
        self.used += 1
        self.budget.callbacks += 1

    def progressive(self, *_args, **_kwargs):
        return self.evaluate()


def test_current_adapter_retains_quota_and_lane_binding(monkeypatch) -> None:
    adapter = _load_adapter()
    monkeypatch.setattr(adapter.BASE.BASE, "LaneQuota", FakeLaneQuota)
    monkeypatch.setattr(adapter.BASE.BASE, "LocalScreenOutcome", FakeOutcome)
    monkeypatch.setattr(adapter.BASE.BASE, "_counter_map", lambda value: value)
    monkeypatch.setattr(adapter.CANDIDATE, "_initial_counters", Counter)
    deadlines = []
    portal_calls = []

    def fake_solve(case, _program, start, _scale, _lower, _upper, cap, deadline):
        deadlines.append(deadline)
        for _ in range(cap):
            case.evaluate(None)
        point = np.asarray(start, dtype=float)
        secondary = bool(point[0] >= 100.0)
        return SimpleNamespace(
            status="safe_root" if secondary else "primary_endpoint",
            endpoint=point + 0.25,
            counters={},
        )

    def fake_portal(case, _program, start, endpoint, _scale, _counters):
        case.evaluate(None)
        portal_calls.append((np.asarray(start).copy(), np.asarray(endpoint).copy()))
        return np.asarray(start, dtype=float) + 100.0, 1

    monkeypatch.setattr(adapter, "_solve", fake_solve)
    monkeypatch.setattr(adapter, "_portal", fake_portal)
    points = tuple(np.asarray((float(index), float(10 * index))) for index in range(8))
    base_case = FakeCase(2, np.full(2, -np.inf), np.full(2, np.inf), None, None)
    budget = FakeBudget()
    deadline = time.monotonic() + 10.0
    outcome = adapter.run_local_arm(
        adapter.ARM,
        base_case=base_case,
        budget=budget,
        program=object(),
        literal_prefix=SimpleNamespace(points=points),
        callback_cap=64,
        callbacks_per_start=8,
        deadline_monotonic=deadline,
    )

    assert outcome.counters["guard_billiard_baseline_ordinal_count"] == 6
    assert outcome.counters["guard_billiard_side_ordinal_count"] == 2
    assert outcome.lane_callbacks == (8,) * 8
    assert budget.callbacks == 64
    assert all(value == deadline for value in deadlines)
    assert len(portal_calls) == 2
    for ordinal, (start, endpoint) in zip((2, 6), portal_calls):
        assert np.array_equal(start, points[ordinal])
        assert np.array_equal(endpoint, points[ordinal] + 0.25)

    expired_budget = FakeBudget()
    expired = adapter.run_local_arm(
        adapter.ARM,
        base_case=base_case,
        budget=expired_budget,
        program=object(),
        literal_prefix=SimpleNamespace(points=points),
        callback_cap=64,
        callbacks_per_start=8,
        deadline_monotonic=0.0,
    )
    assert expired_budget.callbacks == 0
    assert expired.lane_callbacks == ()


def test_unsupported_guard_fails_closed_before_billiard(monkeypatch) -> None:
    adapter = _load_adapter()

    def unsupported(*_args, **_kwargs):
        raise RuntimeError("unsupported analytic source-margin derivative")

    def forbidden_billiard(*_args, **_kwargs):
        raise AssertionError("unsupported guard reached billiard")

    monkeypatch.setattr(adapter.CANDIDATE.CORE.CORE, "_make_state", unsupported)
    monkeypatch.setattr(adapter.FROZEN, "_billiard", forbidden_billiard)
    proposal, reflections = adapter._portal(
        object(), object(), np.zeros(2), np.ones(2), np.ones(2), Counter()
    )
    assert proposal is None
    assert reflections == 0


def test_exact_terminal_binding_is_textually_unchanged_without_importing_it() -> None:
    worker = (HERE / "worker.py").read_text(encoding="utf-8")
    arm = json.loads((HERE / "arm.json").read_text(encoding="utf-8"))
    assert _sha(EXACT_OUTER) == "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7"
    assert _sha(AUTHORITY_BOUNDARY) == "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9"
    assert '"GEOTARGET_EXACT_OUTER_MODE", "CONFIRM_ALL_AUTHORITIES"' in worker
    assert '"approximate_guard_or_endpoint_is_authority": False' in worker
    assert arm["mechanism_hash"] == _sha(HERE / arm["entrypoint"])
