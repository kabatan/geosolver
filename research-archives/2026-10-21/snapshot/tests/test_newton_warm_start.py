from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement import mpmath_refiner as implementation
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner


def fixture():
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "constraints": ["x*x+y*y-25", "x+y-7"],
                "guards": ["x>y", "y>0"],
                "answer": "x-y",
            }
        )
    )
    candidate = FloatCandidate(
        x_float=(3.99999, 3.00001),
        score=4e-10,
        residual_norm_float=2e-5,
        guard_ok=True,
        evaluation_status=EvaluationStatus.OK,
        hard_feasible=True,
        origin_seed=0,
        origin_start_point_index=0,
        candidate_id=1,
    )
    return ev, candidate


def test_newton_warm_start_keeps_all_precision_stages_and_final_verification(monkeypatch):
    ev, candidate = fixture()
    stages = []
    original = MpmathRefiner._run_stage

    def recorded(self, **kwargs):
        stages.append(kwargs["dps"])
        return original(self, **kwargs)

    monkeypatch.setattr(MpmathRefiner, "_run_stage", recorded)
    with mp.workdps(180):
        result = MpmathRefiner().refine_candidates(
            bundle=ev.bundle, evaluator=ev, candidates=(candidate,)
        )
        refined = result.candidates[0]
        assert any(":warm_newton:" in item for item in refined.phase_history)
        assert stages == [50, 100, 120]
        assert refined.residual_norm_hp < mp.mpf("1e-80")
        exact = assemble_exact_results(refined_candidates=result.candidates, evaluator=ev)
    assert exact.answer_values == ("1",)
    assert len(exact.accepted_candidates) == 1
    assert len(exact.accepted_candidates[0].verification_history) >= 2


def test_failed_newton_warm_start_falls_back_to_original_lm(monkeypatch):
    ev, candidate = fixture()
    original = implementation._run_findroot_closure
    attempts = 0

    def fail_warm(**kwargs):
        nonlocal attempts
        if kwargs["max_steps"] == implementation._WARM_NEWTON_MAX_STEPS:
            attempts += 1
            return None
        return original(**kwargs)

    monkeypatch.setattr(implementation, "_run_findroot_closure", fail_warm)
    with mp.workdps(180):
        result = MpmathRefiner().refine_candidates(
            bundle=ev.bundle, evaluator=ev, candidates=(candidate,)
        )
        assert attempts == 1
        assert not any(":warm_newton:" in h for h in result.candidates[0].phase_history)
        exact = assemble_exact_results(refined_candidates=result.candidates, evaluator=ev)
    assert exact.answer_values == ("1",)
