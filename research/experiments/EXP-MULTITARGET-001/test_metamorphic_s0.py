from __future__ import annotations

import run_metamorphic_s0 as metamorphic


def test_truth_free_metamorphic_and_counterexample_panel() -> None:
    result = metamorphic.run()
    assert result["truth_or_gold_input"] is False
    assert result["target_affine_trace_or_descriptor_mismatches"] == 0
    assert result["variable_permutation_trace_or_descriptor_mismatches"] == 0
    assert result["residual_permutation_trace_or_descriptor_mismatches"] == 0


def test_deadline_tail_and_same_target_invariants() -> None:
    result = metamorphic.run()
    assert result["deadline_tail"]["deadline_overrun"] is False
    assert result["deadline_tail"]["minimum_attempt_seconds_held"] is True
    assert result["same_target_multiple_configurations"][
        "same_target_candidate_suppression"
    ] is False


def test_no_case_specific_conditional_branch() -> None:
    result = metamorphic.run()
    assert result["case_specific_branch_audit"]["forbidden_condition_hits"] == []
