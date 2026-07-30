"""One-shot regression assertion for the fixed generated adversary suite."""

from run_generated import run


def test_no_false_authority_or_required_positive_loss() -> None:
    aggregate = run()["aggregate"]
    assert aggregate["case_count"] == 54
    assert aggregate["false_authority_count"] == 0
    assert aggregate["candidate_false_certificate_count"] == 0
    assert aggregate["missed_required_positive_count"] == 0
    assert aggregate["out_of_subset_uncaught_exception_count"] == 1
