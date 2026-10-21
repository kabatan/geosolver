from __future__ import annotations

from mpmath import mp

from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle


def _evaluator(constraint: str):
    bundle = load_problem_bundle(
        {
            "id": "final-verifier",
            "task": "solve",
            "variables": {"names": ["x"]},
            "bounds": [[-1, 1]],
            "construction": [],
            "constraints": [{"def": constraint, "value": 0}],
            "guards": [],
            "answer": "x",
        }
    )
    return build_ir_evaluator(bundle)


def test_equation_scaling_does_not_change_final_acceptance() -> None:
    value = (mp.mpf("1e-20"),)
    plain = verify_final_candidate(evaluator=_evaluator("x"), values=value)
    scaled = verify_final_candidate(evaluator=_evaluator("1e200 * x"), values=value)

    # Final verification now improves coordinates; both equations reach exact 0.
    assert plain.verified and plain.values == (mp.mpf(0),)
    assert scaled.verified and scaled.values == (mp.mpf(0),)
    assert mp.almosteq(plain.normalized_residual, scaled.normalized_residual)


def test_small_normalized_residual_is_accepted_at_final_precision() -> None:
    result = verify_final_candidate(
        evaluator=_evaluator("1e-200 * x"),
        values=(mp.mpf("1e-40"),),
    )

    assert result.verified
    assert result.precision_dps == 180
    assert result.normalized_residual <= mp.mpf("1e-30")


def test_explicit_bounds_are_a_final_hard_gate() -> None:
    result = verify_final_candidate(
        evaluator=_evaluator("x - 2"),
        values=(mp.mpf("2"),),
    )

    assert not result.verified
    assert result.status == "bounds_violation"
