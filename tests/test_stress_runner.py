from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

import pytest


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
    requested = [r.identifier for r in records[:3]]
    first = module.select_cases(records, requested)
    assert [r.identifier for r in first] == sorted(requested)
    assert first == module.select_cases(records[::-1], requested[::-1])
    assert all(r.runnable and r.truth_status == "verified" for r in first)
    for invalid in ([], ["missing"], [requested[0], "missing"]):
        with pytest.raises(module.runner.CampaignError):
            module.select_cases(records, invalid)
    assert Counter(module.cpu_slots(list(range(8)), 16)) == {cpu: 2 for cpu in range(8)}
    assert module.cpu_slots([2, 4, 6], 2) == [2, 4]
