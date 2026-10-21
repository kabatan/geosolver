"""The primary scalar search must expose multiple branches to final verification."""

import pytest

from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.engine.standard.search.scalar_branch_scan import scan_scalar_branches


@pytest.mark.parametrize("guard, expected", [(None, (-3, 2)), ("x>0", (2,))])
def test_scalar_branch_scan_preserves_roots_and_original_guards(guard, expected):
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [],
                "constraints": ["0", "(x-2)*(x+3)"],
                "guards": [] if guard is None else [guard],
                "answer": "x",
            }
        )
    )
    result = scan_scalar_branches(
        evaluator=evaluator,
        bounds=[(-6, 6)],
        config=NomadConfig(max_bb_eval=100),
        prefix_count=20,
    )
    for root in expected:
        assert any(abs(candidate.x_float[0] - root) < 1e-10 for candidate in result.candidates)
    assert all(
        any(abs(candidate.x_float[0] - root) < 1e-6 for root in expected)
        for candidate in result.candidates
    )
    assert result.evaluation_count >= len(result.all_records)


@pytest.mark.parametrize("root, guard", [("0", "x>=0"), ("1e-12", "x>0")])
def test_scalar_branch_scan_does_not_impose_an_interior_margin(root, guard):
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [],
                "constraints": [f"x-({root})"],
                "guards": [guard],
                "answer": "x",
            }
        )
    )
    result = scan_scalar_branches(
        evaluator=evaluator,
        bounds=[(0, 1e-10)],
        config=NomadConfig(max_bb_eval=100),
        prefix_count=20,
    )
    assert any(abs(candidate.x_float[0] - float(root)) < 1e-25 for candidate in result.candidates)


def test_primary_scalar_search_discovers_both_branches_before_local_backend(monkeypatch):
    import importlib
    from types import SimpleNamespace

    orchestration = importlib.import_module("geosolver.engine.standard.orchestration.run_search")
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [],
                "constraints": ["(x-2)*(x+3)"],
                "guards": [],
                "answer": "x",
            }
        )
    )
    monkeypatch.setattr(orchestration, "select_search_start_points", lambda **kwargs: [[0.0]])

    def unexpected_backend(**kwargs):
        pytest.fail("Scalar branch candidates should precede the local NOMAD backend")

    monkeypatch.setattr(orchestration, "_build_search_backend", unexpected_backend)
    result = orchestration.run_search(
        bundle=evaluator.bundle,
        evaluator=evaluator,
        bounds=[(-6, 6)],
        initial_probe_result=SimpleNamespace(candidates=()),
        config=NomadConfig(max_bb_eval=100),
    )
    for root in (-3, 2):
        assert any(abs(candidate.x_float[0] - root) < 1e-10 for candidate in result.candidates)


def test_scalar_branch_scan_with_no_budget_performs_no_evaluations():
    result = scan_scalar_branches(
        evaluator=None,
        bounds=[(-1, 1)],
        config=NomadConfig(max_bb_eval=100, max_time_sec=0),
        prefix_count=20,
    )
    assert not result.candidates
    assert result.evaluation_count == result.failed_evaluations == 0


@pytest.mark.parametrize("left_root, right_root", [(3, 5), (8, 13), (2, 17)])
def test_redundant_scalar_equation_preserves_the_precision_scaled_iteration_budget(
    left_root, right_root
):
    from types import SimpleNamespace

    from mpmath import mp

    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    from geosolver.engine.standard.refinement.mpmath_refiner import _run_findroot_closure

    def residuals(point, dps):
        with mp.workdps(dps):
            return [mp.mpf(0), -7 * (point[0] - left_root) ** 2 * (point[0] + right_root) ** 2]

    evaluator = SimpleNamespace(
        evaluate_hp_residual=lambda point, precision: SimpleNamespace(
            evaluation_status=EvaluationStatus.OK, residual_vector=residuals(point, precision)
        )
    )
    with mp.workdps(120):
        result = _run_findroot_closure(
            evaluator=evaluator,
            start_point=[mp.mpf(left_root) + mp.mpf("1.381124666555186e-11")],
            bounds=((None, None),),
            dps=120,
            target_residual=mp.mpf("1e-80"),
            max_steps=240,
            residual_fn=residuals,
        )
        assert result is not None
        assert result[1] <= mp.mpf("1e-80")
        assert abs(result[0][0] - left_root) < mp.mpf("1e-35")
