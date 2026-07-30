import run_d0


def test_mechanism_preflight():
    original = run_d0.SCENARIOS
    try:
        run_d0.SCENARIOS = 2
        result = run_d0.run_campaign()
    finally:
        run_d0.SCENARIOS = original
    aggregate = result["aggregate"]
    assert aggregate["pm_positive_family_count"] == 3
    assert aggregate["pm_gain_over_krawczyk_family_count"] == 2
    assert aggregate["negative_emit_count"] == 0
    assert aggregate["false_authority_count"] == 0
    assert aggregate["metamorphic_failure_count"] == 0
    assert aggregate["subdivision_count"] == 0
    assert aggregate["max_face_coefficient_height"] <= 4096
    assert aggregate["singular_det_interval_pm_success_count"] >= 1
