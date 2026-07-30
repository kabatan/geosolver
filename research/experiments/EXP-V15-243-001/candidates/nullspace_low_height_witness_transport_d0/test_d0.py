"""Fixed aggregate assertions for nullspace low-height transport D0."""

from run_d0 import run_campaign


def test_d0_gate() -> None:
    result = run_campaign()
    assert result["trace_count"] == 1280
    assert result["aggregate"]["primary_improved_family_count"] == 3
    assert result["aggregate"]["residual_guard_regression_count"] == 0
    assert result["aggregate"]["shared_baseline_mismatch_count"] == 0
    assert result["aggregate"]["fallback_mismatch_count"] == 0
    assert result["aggregate"]["transform_invariance_failure_count"] == 0
    assert result["aggregate"]["decision"] == "ADVANCE"
