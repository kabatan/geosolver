import run_d0


def test_fixed_gate():
    original = run_d0.SCENARIOS
    try:
        run_d0.SCENARIOS = 1
        result = run_d0.run_campaign()
    finally:
        run_d0.SCENARIOS = original
    aggregate = result["aggregate"]
    assert result["instance_count"] == 40
    assert aggregate["decision"] == "ADVANCE"
    assert aggregate["positive_gain_family_count"] == 3
    assert aggregate["radical_only_recovery_families"] == ["squared-generator-radical-only"]
    assert aggregate["negative_emit_count"] == 0
    assert aggregate["false_authority_count"] == 0
    assert aggregate["metamorphic_failure_count"] == 0
    assert aggregate["kll_contract_failure_count"] == 0
