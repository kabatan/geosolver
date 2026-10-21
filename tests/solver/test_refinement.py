"""Refinement contracts and numerical regressions."""

from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver import GeometryProblem, SolveOptions, solve
from geosolver.engine.standard.contracts.branch_box import BranchBox
from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
    SearchBatchResult,
)
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.contracts.runtime_budget import RuntimeBudget
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.orchestration.run_refinement import merge_refinement_results
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement import analytic_jacobian as analytic
from geosolver.engine.standard.refinement import mpmath_refiner as implementation
from geosolver.engine.standard.refinement import mpmath_refiner as refiner
from geosolver.engine.standard.refinement.mpmath_refiner import (
    MpmathRefiner,
    _run_rank_aware_findroot,
)
from geosolver.runtime import symbolic
from geosolver.runtime.deadline import runtime_session


def test_tangent_boundary_is_not_rejected_by_derivative():
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.problem.ir.schema import IRConstruction, IRSpec, IRVariableSpec

    spec = IRSpec(
        task="solve",
        variables=IRVariableSpec(names=["x"]),
        bounds=[(0, 2)],
        construction=[
            IRConstruction("Q", "Intersect(Line(Point(-1,0),Point(1,0)),Circle(Point(0,x),1),n=1)")
        ],
        constraints=["x"],
        v=[1],
        answer_expr="Q.x",
    )
    result = verify_final_candidate(
        evaluator=build_ir_evaluator(load_problem_bundle(spec)), values=(mp.mpf(1),)
    )
    assert result.verified


def _closure_evaluator():
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["u", "v"]},
                "constraints": ["u*u-2", "v*v-3"],
                "answer": "u+v",
            }
        )
    )


def closure(ev, point, **kwargs):
    return implementation._run_findroot_closure(
        evaluator=ev,
        start_point=point,
        bounds=((None, None), (None, None)),
        dps=120,
        target_residual=mp.mpf("1e-80"),
        max_steps=12,
        **kwargs,
    )


def test_original_target_is_checked_before_newton_and_preserves_all_input_bits(monkeypatch):
    ev = _closure_evaluator()
    with mp.workdps(240):
        point = [mp.sqrt(2), mp.sqrt(3)]
        original_bits = [x._mpf_ for x in point]

    def forbidden(*args, **kwargs):
        raise AssertionError("an already certified original residual needs no Newton iteration")

    monkeypatch.setattr(mp, "findroot", forbidden)
    result = closure(ev, point)
    assert result is not None
    assert [x._mpf_ for x in result[0]] == original_bits
    assert result[1] <= mp.mpf("1e-80")


def test_unfinished_start_is_rounded_to_newtons_working_precision(monkeypatch):
    ev = _closure_evaluator()
    with mp.workdps(240):
        point = [mp.sqrt(2) + mp.mpf("1e-40"), mp.sqrt(3)]
    original = mp.findroot
    calls = []

    def inspect_precision(function, initial, **kwargs):
        calls.append(tuple(x._mpf_[3] for x in initial))
        assert all(x._mpf_[3] <= mp.prec for x in initial)
        return original(function, initial, **kwargs)

    monkeypatch.setattr(mp, "findroot", inspect_precision)
    result = closure(ev, point, solver_tolerance=mp.mpf("1e-160"))
    assert calls and result is not None
    assert result[1] <= mp.mpf("1e-80")


def test_optimizer_residual_cannot_bypass_original_full_residual_certification(monkeypatch):
    ev = _closure_evaluator()
    with mp.workdps(240):
        point = [mp.mpf(2), mp.mpf(3)]

    def unchanged(function, initial, **kwargs):
        return mp.matrix(initial)

    monkeypatch.setattr(mp, "findroot", unchanged)
    assert closure(ev, point, residual_fn=lambda p, dps: [mp.mpf(0), mp.mpf(0)]) is None


def test_rank_aware_refinement_preserves_high_precision_gauge_coordinate():
    with mp.workdps(100):
        gauge = mp.sqrt(2)
        start = [mp.mpf(0), gauge]
        tolerance = mp.mpf("1e-80")
    with mp.workdps(15):
        result = _run_rank_aware_findroot(
            evaluate_residuals=lambda point: (point[0] - 1,),
            start_point=start,
            dps=100,
            target_residual=tolerance,
            max_steps=20,
        )
    assert result is not None
    assert result[1] == gauge


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


def _derivative_evaluator(aliases=0):
    construction = []
    source = "x+y"
    if aliases:
        construction = [{"name": "a0", "expr": "x"}] + [
            {"name": f"a{i}", "expr": f"a{i - 1}"} for i in range(1, aliases)
        ]
        source = f"a{aliases - 1}+y"
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "construction": construction,
                "constraints": [source, "x-y"],
                "v": [3, 1],
                "answer": "x*y",
            }
        )
    )


def assert_original_system_closes(ev):
    with mp.workdps(150), high_precision_mode():
        result = refiner._run_findroot_closure(
            evaluator=ev,
            start_point=[mp.mpf("1.99"), mp.mpf("1.01")],
            bounds=((None, None),) * 2,
            dps=120,
            target_residual=mp.mpf("1e-90"),
            max_steps=10,
        )
        assert result is not None
        assert max(
            abs(value - wanted) for value, wanted in zip(result[0], (2, 1), strict=True)
        ) < mp.mpf("1e-90")
        checked = ev.evaluate_hp_residual(result[0], precision=120)
        assert len(checked.residual_vector) == 2
        assert max(map(abs, checked.residual_vector)) < mp.mpf("1e-90")


@pytest.mark.parametrize("worker", [False, True])
def test_valid_alias_chain_exceeding_optional_recursion_capacity_keeps_numerical_closure(worker):
    # The numerical construction evaluator visits aliases iteratively in DSL
    # order; the optional symbolic geometry compiler recursively expands them.
    analytic._plan.cache_clear()
    ev = _derivative_evaluator(aliases=600)
    with runtime_session(None) if worker else nullcontext():
        assert analytic.derivative_plan(ev.bundle) is None
        assert_original_system_closes(ev)
    analytic._plan.cache_clear()


@pytest.mark.parametrize(
    "error", [ValueError, TypeError, ArithmeticError, KeyError, RecursionError]
)
def test_optional_compile_error_keeps_original_closure_and_caches_unsupported(monkeypatch, error):
    analytic._plan.cache_clear()
    calls = []

    def failed(*args, **kwargs):
        calls.append((args, kwargs))
        raise error("independent optional compiler rejection")

    monkeypatch.setattr(symbolic, "request", failed)
    ev = _derivative_evaluator()
    assert_original_system_closes(ev)
    assert len(calls) == 1
    assert analytic.derivative_plan(ev.bundle) is None
    assert len(calls) == 1
    analytic._plan.cache_clear()


def test_solve_deadline_from_optional_plan_still_propagates(monkeypatch):
    analytic._plan.cache_clear()

    def expired(*args, **kwargs):
        raise TimeoutError("independent global deadline")

    monkeypatch.setattr(symbolic, "request", expired)
    with pytest.raises(TimeoutError, match="global deadline"):
        assert_original_system_closes(_derivative_evaluator())
    analytic._plan.cache_clear()


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


def test_rescue_shares_time_and_rolls_unused_time_forward(monkeypatch):
    import geosolver.engine.standard.orchestration.run_rescue_search as module

    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    boxes = tuple(BranchBox(i, (0.0,), (-1.0,), (1.0,), (), 1, "search_rescue") for i in range(6))
    monkeypatch.setattr(module, "select_rescue_boxes", lambda *args: boxes)
    deadlines = []

    def optimize(adapter, *args):
        deadlines.append(adapter.deadline_monotonic)
        if len(deadlines) == 1:
            clock[0] += 0.5  # first box returns before its one-second allocation
        else:
            clock[0] = adapter.deadline_monotonic
        point = SimpleNamespace(size=lambda: 1, get_coord=lambda i: 0, setBBO=lambda b: None)
        if clock[0] >= adapter.deadline_monotonic:
            assert adapter(point) == 0  # callback stops even for sub-second MAX_TIME

    monkeypatch.setattr(
        module,
        "_import_pynomad",
        lambda: SimpleNamespace(setSeed=lambda seed: None, optimize=optimize),
    )
    config = replace(
        ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=20),
        rescue_time_budget_sec=6,
    )
    result = module.run_rescue_search(
        bundle=None,
        evaluator=None,
        bounds=[(-1, 1)],
        search_result=SearchBatchResult((), 0, 0),
        pipeline_config=config,
        runtime_budget=RuntimeBudget(20, started_at_monotonic=0),
    )
    assert len(result.box_runs) == 6
    assert result.box_runs[0]["quota_seconds"] == 1
    assert result.box_runs[1]["quota_seconds"] == pytest.approx(1.1)
    assert deadlines[-1] == pytest.approx(6)


def problem_with_value(value: int | float | str = 1) -> GeometryProblem:
    return GeometryProblem(
        id="positive-dimensional",
        variables=["x"],
        constructions=[],
        conditions=[{"left": "x", "operator": "=", "right": value}],
        target="x",
    )


def options() -> SolveOptions:
    return SolveOptions(time_limit_seconds=180, cores=1)


def test_positive_dimensional_search_closure_finds_x_equals_one() -> None:
    result = solve(problem_with_value(), options())

    assert result.status == "solved"
    assert result.completeness == "unknown"
    assert result.answers[0].kind == "algebraic"
    assert result.answers[0].minimal_polynomial == ["1", "-1"]
