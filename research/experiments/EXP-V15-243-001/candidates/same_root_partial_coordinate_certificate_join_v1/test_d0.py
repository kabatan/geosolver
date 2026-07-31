from run_d0 import run


def test_generated_d0():
    result = run()
    assert result["passed"] == result["total"]
    assert result["positive_work"]["proposal_count"] == 1
    assert result["positive_work"]["fresh_krawczyk_pass_count"] == 1
