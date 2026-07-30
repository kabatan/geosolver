"""Direct assertions for the fixed proof-SBFE oracle."""

from oracle import self_test


def test_fixed_oracle() -> None:
    result = self_test()
    assert result["fixed_candidate_runs"] == 11
    assert result["oracle_negative_mutations_rejected"] == 3
    assert result["decision"] == "ORACLE_SELF_TEST_PASS"
