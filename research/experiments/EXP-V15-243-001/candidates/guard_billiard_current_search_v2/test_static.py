from __future__ import annotations

import ast
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def test_sources_parse() -> None:
    for name in ("search_adapter.py", "search_worker.py", "scheduler_shim.py", "worker.py"):
        ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)


def test_quota_and_terminal_are_explicit() -> None:
    adapter = (HERE / "search_adapter.py").read_text(encoding="utf-8")
    worker = (HERE / "worker.py").read_text(encoding="utf-8")
    assert "lane % 4 == 2" in adapter
    assert "baseline_fraction_lower_bound" in adapter
    assert "side_route_fraction_upper_bound" in adapter
    assert "exact_outer" in worker
    assert '"approximate_guard_or_endpoint_is_authority": False' in worker


def test_arm_binds_frozen_entrypoint() -> None:
    arm = json.loads((HERE / "arm.json").read_text(encoding="utf-8"))
    assert arm["mechanism_hash"] == "40badc9869b3b3181e5ca638852e23b174ad53caacf6d241ac8db621113ba993"
