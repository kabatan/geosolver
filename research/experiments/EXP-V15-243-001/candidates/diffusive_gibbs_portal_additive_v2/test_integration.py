from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent


def _load():
    name = "test_additive_digs_adapter"
    spec = importlib.util.spec_from_file_location(name, HERE / "search_adapter.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class Outcome:
    endpoints: tuple
    statuses: dict
    counters: dict
    lane_callbacks: tuple


def test_zero_surplus_returns_exact_baseline_object(monkeypatch) -> None:
    adapter = _load()
    baseline = Outcome(((0, np.array([1.0, 2.0])),), {"base": 1}, {"x": 2}, (8,))
    calls = []

    def current(*args, **kwargs):
        calls.append((args, kwargs))
        return baseline

    monkeypatch.setattr(adapter.BASE, "run_local_arm", current)
    result = adapter.run_local_arm(
        adapter.CANDIDATE,
        budget=SimpleNamespace(callbacks=10),
        callback_cap=10,
        deadline_monotonic=time.monotonic() + 30.0,
    )
    assert result is baseline
    assert len(calls) == 1


def test_union_keeps_baseline_endpoints_and_work_as_exact_prefix() -> None:
    adapter = _load()
    baseline = Outcome(
        ((0, np.array([1.0])), (7, np.array([2.0]))),
        {"base": 2},
        {"base_work": 11},
        (5, 6),
    )
    tail = Outcome(
        ((0, np.array([3.0])),),
        {"tail": 1},
        {"tail_work": 3},
        (3,),
    )
    output = adapter._annotate(
        baseline,
        adapter.Counter({"repair": 1}),
        adapter.Counter({"repair_work": 2}),
        tail=tail,
        offset=64,
    )
    assert output.lane_callbacks[:2] == baseline.lane_callbacks
    assert len(output.endpoints) == 3
    for old, new in zip(baseline.endpoints, output.endpoints[:2], strict=True):
        assert old[0] == new[0]
        assert old[1].tobytes() == new[1].tobytes()
    assert output.endpoints[2][0] == 64
    assert output.statuses["base"] == 2
    assert output.statuses["digs_tail:tail"] == 1


def test_manifest_freezes_repair_a_contract() -> None:
    adapter = _load()
    manifest = adapter.BINDING_RECORD
    assert manifest["baseline_runs_first_exactly_once"] is True
    assert manifest["baseline_endpoints_and_lane_work_are_union_prefix"] is True
    assert manifest["zero_surplus_returns_identical_outcome_object"] is True
    assert manifest["canonical_source_replay_modified"] is False


def test_arm_and_full_wrapper_hash_chain() -> None:
    arm = json.loads((HERE / "arm.json").read_text())
    assert hashlib.sha256((HERE / arm["entrypoint"]).read_bytes()).hexdigest() == arm[
        "mechanism_hash"
    ]
    wrapper_sha = hashlib.sha256((HERE / "full_wrapper.py").read_bytes()).hexdigest()
    assert wrapper_sha in (HERE / "full_worker.py").read_text()
