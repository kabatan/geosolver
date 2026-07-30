from __future__ import annotations

from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import run_generated_d0  # noqa: E402


def test_generated_d0_gate_and_safety_contract() -> None:
    result = run_generated_d0.run()
    assert result["gate"]["passed"]
    assert result["gate"]["status"] == "UNKNOWN"
    assert result["aggregate"]["descriptor_losses"] == 0
    assert result["aggregate"]["false_or_extra"] == 0
    assert result["aggregate"]["work_mismatch"] == 0
    assert result["policy"]["baseline_fraction"] >= 0.75
    assert result["policy"]["canonical_exact_source_replay_required"]
    assert not result["policy"]["completeness_claim"]


def test_repeated_root_counter_is_ineligible() -> None:
    result = run_generated_d0.run()
    row = result["by_family"]["repeated_root"]
    assert row["eligible_cases"] == 0
    assert row["descriptor_gains"] == 0
