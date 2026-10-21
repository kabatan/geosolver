from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import (
    RefinedCandidate,
    RefinementBatchResult,
)
from geosolver.engine.standard.orchestration.run_refinement import merge_refinement_results


def _batch(candidate_id: int) -> RefinementBatchResult:
    candidate = RefinedCandidate(
        x_hp=(mp.mpf(candidate_id),),
        residual_norm_hp=mp.mpf("0"),
        answer_hp=mp.mpf(candidate_id),
        refinement_status="target_reached",
        phase_history=("fixture",),
        candidate_id=candidate_id,
        hard_feasible=True,
    )
    return RefinementBatchResult(
        candidates=(candidate,),
        converged_count=1,
        attempted_count=1,
        hard_feasible_count=1,
    )


def test_rescue_refinement_appends_only_new_batch() -> None:
    original = _batch(1)
    rescued = _batch(2)

    merged = merge_refinement_results(original, rescued)

    assert [candidate.candidate_id for candidate in merged.candidates] == [1, 2]
    assert merged.attempted_count == 2
    assert merged.converged_count == 2
