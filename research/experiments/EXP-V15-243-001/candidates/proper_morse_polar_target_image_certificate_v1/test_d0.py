from run_d0 import run


def test_generated_d0():
    result = run()
    assert result["passed"] == result["total"]
    assert result["records"]["circle_target_x_rejection"] == (
        "TARGET_DIFFERENTIAL_NONZERO_ON_SMOOTH_STRATUM"
    )
