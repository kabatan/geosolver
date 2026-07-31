import run_d0


def test_fixed_synthetic_gate():
    original = run_d0.SCENARIOS
    try:
        run_d0.SCENARIOS = 1
        result = run_d0.run_campaign()
    finally:
        run_d0.SCENARIOS = original
    assert result["instances"] == 40
    assert result["gate"] == "SYNTHETIC_D0_PASS"
    assert result["failure_count"] == 0
    assert result["false_authority_count"] == 0
    assert result["negative_join_count"] == 0
    assert result["metamorphic_failure_count"] == 0
    assert len(result["primary_recovery"]) == 3
    for family in result["primary_recovery"].values():
        assert family == {
            "join_rate": 1.0,
            "direct_membership_rate": 0.0,
            "square_membership_rate": 0.0,
        }
    complex_only = result["families"]["complex_only_no_existence_join"]
    assert complex_only["identity_ready"] == complex_only["trials"]
    assert complex_only["join_ready"] == 0
    assert result["families"]["unit_ideal"]["identity_ready"] == 0
