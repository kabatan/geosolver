import run_d0


def test_all_mechanism_families_and_metamorphics():
    original = run_d0.SCENARIOS
    try:
        run_d0.SCENARIOS = 1
        result = run_d0.run_campaign()
    finally:
        run_d0.SCENARIOS = original

    assert result["instance_count"] == 32
    assert result["trace_count"] == 64
    assert result["aggregate"] == {
        "baseline_quota": 0.75,
        "decision": "ADVANCE",
        "fallback_mismatch_count": 0,
        "false_authority_count": 0,
        "metamorphic_failure_count": 0,
        "primary_gain_family_count": 3,
        "shared_baseline_mismatch_count": 0,
        "side_quota": 0.25,
    }
