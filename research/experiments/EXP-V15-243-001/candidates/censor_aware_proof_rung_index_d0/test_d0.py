"""Fixed synthetic acceptance assertions for the stopped D0."""

from run_d0 import run_campaign


def test_campaign_gate_and_safety() -> None:
    result = run_campaign()
    assert result["trace_count"] == 1280
    assert result["aggregate"]["baseline_loss"] is False
    assert result["aggregate"]["future_leak_count"] == 0
    assert result["aggregate"]["safety_failure_count"] == 0
    assert result["aggregate"]["improved_family_count"] == 1
    assert result["aggregate"]["decision"] == "STOP"
