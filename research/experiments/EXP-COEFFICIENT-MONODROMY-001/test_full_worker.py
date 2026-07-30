from __future__ import annotations

import hashlib
import json
from pathlib import Path

import full_worker
from run_full_worker_smoke import run

HERE = Path(__file__).resolve().parent


def test_three_source_only_full_worker_smokes(tmp_path: Path) -> None:
    result = run(tmp_path)
    assert result["gate"]["passed"] is True
    assert result["truth_scorer_case_outcome_or_holdout_read"] is False


def test_arm_binds_runner_compatible_full_worker() -> None:
    arm = json.loads((HERE / "arm.json").read_text())
    assert arm["entrypoint"] == "full_worker.py"
    assert (
        hashlib.sha256((HERE / "full_worker.py").read_bytes()).hexdigest()
        == arm["mechanism_hash"]
    )


def test_current_adaptive_and_thin_dependencies_are_hash_bound() -> None:
    full_worker._verify_dependencies()
    assert full_worker.BASELINE_FLOOR == 0.75
    assert full_worker.ADAPTIVE_ENTRYPOINT_SHA256 == (
        "7d6f168d8679732c672842e6b7a44573d190449ad0fbe4cc09a7b9112ddc9500"
    )
