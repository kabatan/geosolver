from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent


def _worker():
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    return importlib.import_module("champion_v2_poc_direct_exact_preloaded")


def test_direct_exact_is_the_only_rebound_hp_seam(tmp_path: Path) -> None:
    worker = _worker()

    assert worker.BASE is worker.CHAMPION.CHAMPION.BASE
    assert worker.BASE._geotarget_direct_exact_first_installed is True
    assert worker.BASE._run_hp_candidate is worker.INSTALLATION.run
    assert (
        worker.BASE._run_restoration_candidate
        is worker.INSTALLATION.restoration
    )
    assert worker.RESOURCE.RESOURCE_BUSY_STATUSES == frozenset(
        ("LOCK_BUSY_DEFERRED", "MEMORY_BUSY_DEFERRED")
    )

    # Invalid allocation must fail before reading source or launching a child.
    result = worker.BASE._run_hp_candidate(
        candidate={},
        source=tmp_path / "absent.json",
        source_sha256="0" * 64,
        timeout_seconds=0.0,
        cpu=0,
        output=tmp_path / "attempt",
    )
    assert result["status"] == "DIRECT_EXACT_INVALID_ALLOCATION"
    assert not (tmp_path / "attempt").exists()


def test_dry_plan_keeps_source_only_global_arm(tmp_path: Path) -> None:
    worker = _worker()
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps({"variables": {"names": []}}), encoding="utf-8"
    )
    plan = worker.BASE._plan(
        source=source,
        source_sha256="0" * 64,
        total_seconds=180.0,
        search_seconds=146.0,
        starts=256,
        callbacks_per_start=600,
        aggregate_callback_cap=153600,
        seed=0,
        cpu=0,
        output=tmp_path / "output",
    )

    assert plan["direct_exact_first_arm_is_global_not_case_routed"] is True
    assert plan["case_family_truth_target_count_routing"] is False
    assert plan["ordinary_hp_calls"] == 0
    assert plan["ordinary_restoration_disabled"] is True
    assert plan["target_set_completeness_claim"] is False
    assert plan["execution_route"] == "source_exact_zero_dimensional"
