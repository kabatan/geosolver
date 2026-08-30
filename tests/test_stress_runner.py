from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path


def test_stress_selection_and_slots(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "benchmarks"))
    spec = importlib.util.spec_from_file_location(
        "stress_runner", root / "benchmarks/stress_runner.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    records = module.runner._load_cases()
    first = module.select_cases(records)
    assert [r.identifier for r in first] == [
        r.identifier for r in module.select_cases(records[::-1])
    ]
    assert len(first) == len({module.natural_key(r) for r in first}) == 60
    assert {r.identifier for r in first} >= module.ANCHORS
    assert all(r.runnable and r.truth_status == "verified" for r in first)
    assert Counter(r.identifier.upper().split("-")[0] for r in first) == module.QUOTAS
    assert Counter(module.cpu_slots(list(range(8)), 16)) == {cpu: 2 for cpu in range(8)}
    assert module.cpu_slots([2, 4, 6], 2) == [2, 4]
