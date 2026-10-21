"""Finite search contracts and numerical regressions."""

import importlib
import itertools
import math
import time
from fractions import Fraction
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    SearchBatchResult,
    assert_candidate_key_consistency,
)
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import IREvaluator, build_ir_evaluator
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.orchestration.run_initial_probe import InitialProbeResult
from geosolver.engine.standard.orchestration.run_search import _merge_search_batch_results
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
from geosolver.engine.standard.search import finite_guard_search as finite
from geosolver.engine.standard.search import scipy_multistart_backend as search
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.engine.standard.search.scalar_branch_scan import scan_scalar_branches
from geosolver.problem.logical_equalities import LogicalEqualityPlan
from geosolver.runtime.deadline import deadline_scope, runtime_session


def test_zero_and_expired_scipy_budgets_never_enter_optimizer(monkeypatch):
    from geosolver.engine.standard.search.nomad_config import NomadConfig
    from geosolver.engine.standard.search.scipy_multistart_backend import ScipyMultistartBackend

    def forbidden(*args, **kwargs):
        pytest.fail("optimizer entered with no time budget")

    monkeypatch.setattr("scipy.optimize.least_squares", forbidden)
    for budget, deadline in ((0, None), (10, time.monotonic() - 1)):
        with runtime_session(deadline):
            result = ScipyMultistartBackend(
                NomadConfig(max_time_sec=budget, max_bb_eval=10), ([0],)
            ).run_search(bundle=SimpleNamespace(), evaluator=SimpleNamespace(), bounds=[(-1, 1)])
        assert result.evaluation_count == 0


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


def evaluator(names=("x", "y"), guards=("Or(x==1,x==2)",), constraints=("x+y-5",), construction=()):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": list(names)},
                "constraints": list(constraints),
                "guards": list(guards),
                "construction": list(construction),
                "answer": "*".join(names),
            }
        )
    )


def _finite_guard_search(ev, *, config=None, initial=None):
    return finite.search_finite_guards(
        bundle=ev.bundle,
        evaluator=ev,
        bounds=[(-20.0, 20.0)] * len(ev.bundle.var_names),
        initial_probe_result=initial or InitialProbeResult((), {}),
        config=config or NomadConfig(max_bb_eval=200, max_time_sec=5, seed_values=(13,)),
    )


@pytest.mark.parametrize("names", [("x", "y"), ("second", "first"), ("v7", "v3")])
@pytest.mark.parametrize("scale,shift", [(1, 0), (3, 2), (-2, 7)])
def test_renamed_scaled_reordered_affine_alternatives(names, scale, shift):
    fixed, free = names
    clauses = [f"({fixed}-{shift})/{scale}=={value}" for value in (1, 4, 2)]
    ev = evaluator(
        names=tuple(reversed(names)),
        guards=(f"Or({','.join(clauses)})",),
        constraints=(f"{fixed}+{free}-9",),
    )
    expected = {Fraction(shift + scale * value) for value in (1, 2, 4)}
    assignments = finite.finite_assignments(ev.bundle)
    assert {dict(a)[1] for a in assignments} == expected
    assert all(set(dict(a)) == {1} for a in assignments)


def test_named_cartesian_coordinate_and_midpoint_are_resolved_without_polynomial(monkeypatch):
    import sympy as sp

    def forbidden(*args, **kwargs):
        pytest.fail("finite affine extraction must not expand a polynomial")

    monkeypatch.setattr(sp, "Poly", forbidden)
    ev = evaluator(
        guards=("Or(M.y==3,M.y==5)",),
        construction=(
            {"name": "P", "expr": "Point(0,x)"},
            {"name": "Q", "expr": "Point(0,2)"},
            {"name": "M", "expr": "Midpoint(P,Q)"},
        ),
    )
    assert finite.finite_assignments(ev.bundle) == (((0, Fraction(4)),), ((0, Fraction(8)),))
    nonlinear = evaluator(guards=("Or((x+1)**1000==1,(x+1)**1000==2)",))
    assert finite.finite_assignments(nonlinear.bundle) == ()


def test_all_different_pairwise_guards_prune_only_fully_fixed_affine_comparisons():
    names = ("p", "q", "r")
    guards = [f"Or({name}==1,{name}==2,{name}==3)" for name in names]
    # AllDifferent is represented by its original pairwise inequality guards.
    guards.append("And(p!=q,p!=r,q!=r)")
    ev = evaluator(names=names, guards=guards, constraints=("p+q+r-6",))
    actual = {tuple(value for _, value in a) for a in finite.finite_assignments(ev.bundle)}
    assert actual == set(itertools.permutations(map(Fraction, (1, 2, 3))))
    contradictory = evaluator(guards=("Or(x==1,x==2)", "Or(x==3,x==4)"))
    assert finite.finite_assignments(contradictory.bundle) == ()


@pytest.mark.parametrize(
    "clauses",
    [
        (("x*x-1",), ("x*x-4",)),
        (("x+y-1",), ("x+y-2",)),
        (("x-1",), ("y-2",)),
        (("x-1", "y-1"), ("x-2", "y-2")),
        (("x-1",), ("0",)),
        (("x-1/0",), ("x-2",)),
        (("x-10**1000",), ("x-2",)),
    ],
)
def test_nonaffine_nonfinite_or_non_single_coordinate_sources_fall_back(clauses):
    bundle = SimpleNamespace(
        var_names=("x", "y"),
        spec=SimpleNamespace(
            construction=(), guards=(), logical_plans=(LogicalEqualityPlan(clauses),)
        ),
    )
    assert finite.finite_assignments(bundle) == ()


def test_unsupported_geometry_result_is_cached_without_repeating_symbolic_work(monkeypatch):
    from geosolver.problem.scalar_geometry import ScalarGeometry

    finite._finite_assignments.cache_clear()
    ev = evaluator(guards=("Or(sin(x)==1,sin(x)==2)",))
    calls = []
    original = ScalarGeometry.scalar

    def counted(self, node):
        calls.append(node)
        return original(self, node)

    monkeypatch.setattr(ScalarGeometry, "scalar", counted)
    assert finite.finite_assignments(ev.bundle) == ()
    first_calls = len(calls)
    assert first_calls > 0
    assert finite.finite_assignments(ev.bundle) == ()
    assert len(calls) == first_calls


def test_assignment_cap_and_no_disjunction_keep_ordinary_search():
    ev = evaluator(guards=("Or(x==1,x==2)", "Or(y==3,y==4)"))
    assert finite.finite_assignments(ev.bundle, cap=3) == ()
    ev = evaluator(guards=("x>0",))
    assert _finite_guard_search(ev) is None
    ev = evaluator()
    assert _finite_guard_search(ev, config=NomadConfig(max_bb_eval=0)) is None
    assert _finite_guard_search(ev, config=NomadConfig(max_bb_eval=200, max_time_sec=0)) is None


def test_search_counts_every_residual_request_and_keeps_final_high_precision_confirmation(
    monkeypatch,
):
    ev = evaluator()
    calls = []
    original = IREvaluator.evaluate_float_residual

    def counted(self, values):
        calls.append(tuple(values))
        return original(self, values)

    monkeypatch.setattr(IREvaluator, "evaluate_float_residual", counted)
    with runtime_session(None) as telemetry:
        result = _finite_guard_search(ev)
    assert result.evaluation_count == len(calls)
    assert result.evaluation_count == telemetry.counters["finite_guard_residual_evaluations"]
    assert result.failed_evaluations == 0
    assert {round(c.x_float[0]) for c in result.candidates} == {1, 2}
    assert all(c.hard_feasible and c.guard_ok for c in result.candidates)
    assert_candidate_key_consistency(result.candidates)
    with mp.workdps(180):
        refined = MpmathRefiner().refine_candidates(
            bundle=ev.bundle, evaluator=ev, candidates=result.candidates
        )
        exact = assemble_exact_results(refined_candidates=refined.candidates, evaluator=ev)
    assert set(exact.answer_values) == {"4", "6"}
    assert all(len(c.verification_history) >= 2 for c in exact.accepted_candidates)


@pytest.mark.parametrize("failure", ["exception", "nonfinite", "failed"])
def test_invalid_residuals_are_counted_as_failures_without_emitting_candidates(failure):
    ev = evaluator(names=("x",), constraints=())
    calls = []

    def evaluate(point):
        calls.append(point)
        if failure == "exception":
            raise ValueError("independent generated invalid evaluation")
        return SimpleNamespace(
            evaluation_status=EvaluationStatus.OK
            if failure == "nonfinite"
            else EvaluationStatus.EVALUATION_FAILED,
            is_finite=failure == "nonfinite",
            residual_norm_float=math.nan,
            residual_vector=[math.nan],
        )

    proxy = SimpleNamespace(bundle=ev.bundle, evaluate_float_residual=evaluate)
    result = _finite_guard_search(proxy)
    assert result.candidates == ()
    assert result.evaluation_count == result.failed_evaluations == len(calls) == 4
    assert result.failure_ratio == 1


def test_solve_deadlines_propagate_before_extraction_cache_hits_and_during_evaluation():
    ev = evaluator(names=("x",), constraints=())
    finite.finite_assignments(ev.bundle)
    with deadline_scope(0), pytest.raises(TimeoutError):
        finite.finite_assignments(ev.bundle)
    with deadline_scope(0), pytest.raises(TimeoutError):
        _finite_guard_search(ev)

    def expired(point):
        raise TimeoutError("generated mid-evaluation deadline")

    with pytest.raises(TimeoutError, match="mid-evaluation"):
        _finite_guard_search(SimpleNamespace(bundle=ev.bundle, evaluate_float_residual=expired))


def test_wrapper_preserves_every_baseline_candidate_ledger_and_failure_count(monkeypatch):
    module = importlib.import_module("geosolver.engine.standard.orchestration.run_search")
    ev = evaluator()
    candidate = FloatCandidate((1.0, 4.0), 0.0, 0.0, True, EvaluationStatus.OK, 0, 0)
    original = SearchBatchResult(
        (candidate,), 7, 2 / 7, (candidate,), (candidate,), {"original": 1}, 2
    )
    extra = FloatCandidate((2.0, 3.0), 0.0, 0.0, True, EvaluationStatus.OK, 1, 0)
    supplemental = SearchBatchResult((extra,), 5, 1 / 5, (extra,), (), {"finite": 1}, 1)
    received = []
    monkeypatch.setattr(finite, "search_finite_guards", lambda **kwargs: supplemental)

    def baseline(**kwargs):
        received.append(kwargs)
        return original

    monkeypatch.setattr(module, "_run_search_baseline", baseline)
    result = module.run_search(
        bundle=ev.bundle,
        evaluator=ev,
        bounds=[(-20, 20)] * 2,
        initial_probe_result=InitialProbeResult((), {}),
        config=NomadConfig(max_bb_eval=200, max_time_sec=5),
        constraint_scales=(3.0, 4.0),
        search_mode="scipy_multistart",
    )
    assert result.candidates == (extra, candidate)
    assert result.all_records == (extra, candidate)
    assert result.guard_feasible_ledger == (candidate,)
    assert result.evaluation_count == 12 and result.failed_evaluations == 3
    assert result.failure_ratio == 0.25
    assert result.search_diagnostics["original"] == result.search_diagnostics["finite"] == 1
    assert received[0]["constraint_scales"] == (3.0, 4.0)
    assert received[0]["search_mode"] == "scipy_multistart"
    assert 0 <= received[0]["config"].max_time_sec <= 5
    assert received[0]["_skip_integer_squares"] is False
    monkeypatch.setattr(finite, "search_finite_guards", lambda **kwargs: None)
    public_arguments = {
        key: value for key, value in received[0].items() if not key.startswith("_skip_")
    }
    assert (
        module.run_search(**(public_arguments | {"config": NomadConfig(max_bb_eval=200)}))
        is original
    )


def test_optional_local_deadline_keeps_baseline_search_available(monkeypatch):
    import scipy.optimize

    ev = evaluator()

    def expired(*args, **kwargs):
        raise finite._LocalBudget

    monkeypatch.setattr(scipy.optimize, "least_squares", expired)
    result = _finite_guard_search(ev)
    assert not result.candidates
    assert result.search_diagnostics["finite_guard_local"]["local_timeouts"] == 4
    assert result.evaluation_count == 0


def test_local_brent_deadline_returns_control_but_global_timeout_propagates(monkeypatch):
    def expire(*args, **kwargs):
        raise search._SearchDeadlineExceeded()

    monkeypatch.setattr(search, "brentq", expire)
    kwargs = dict(
        evaluator=None,
        left=0,
        right=1,
        f_left=-1,
        f_right=1,
        telemetry=None,
        deadline_monotonic=None,
    )
    assert search._safe_brentq_root(**kwargs) is None

    def outer_timeout(*args, **kwargs):
        raise TimeoutError()

    monkeypatch.setattr(search, "brentq", outer_timeout)
    with pytest.raises(TimeoutError):
        search._safe_brentq_root(**kwargs)


def test_merged_failures_count_evaluations_including_discarded_probes():
    first = SearchBatchResult((), 100, 0.75, search_diagnostics={"scan": 1})
    second = SearchBatchResult((), 20, 0.25, search_diagnostics={"other": 2})
    merged = _merge_search_batch_results(first, second)
    assert merged.evaluation_failure_count == 80
    assert merged.failure_ratio == 80 / 120
    assert merged.search_diagnostics["scan"] == 1
    assert merged.search_diagnostics["other"] == 2


def scalar_scan(function, bounds):
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    from geosolver.engine.standard.search.nomad_config import NomadConfig

    def evaluate(point):
        return SimpleNamespace(
            residual_vector=function(point[0]),
            evaluation_status=EvaluationStatus.OK,
            is_finite=True,
        )

    return search._run_one_dimensional_search(
        evaluator=SimpleNamespace(evaluate_float_residual=evaluate),
        bounds=[bounds],
        config=NomadConfig(max_bb_eval=100),
        deadline_monotonic=None,
        telemetry=search._SearchTelemetry(),
    )[0]


def test_scalar_scan_preserves_closed_endpoints_and_nearby_roots():
    points = scalar_scan(lambda x: [x * (x - 5e-11) * (x - 1e-10)], (0, 1e-10))
    assert (0.0,) in points
    assert (1e-10,) in points
    assert any(abs(x[0] - 5e-11) < 1e-16 for x in points)


def test_scalar_scan_brackets_equations_after_redundant_first_equation():
    points = scalar_scan(lambda x: [0.0, (x - 0.123456789) * (x + 0.234567891)], (-1, 1))
    for root in [0.123456789, -0.234567891]:
        assert any(abs(x[0] - root) < 1e-14 for x in points)


def test_scalar_scan_separates_tangent_root_basins():
    points = scalar_scan(lambda x: [(x - 0.123456789) ** 2 * (x + 0.534567891) ** 2], (-1, 1))
    for root in [0.123456789, -0.534567891]:
        assert any(abs(x[0] - root) < 1e-7 for x in points)


@pytest.mark.parametrize("entry", ["residual", "guard", "hard"])
def test_scipy_evaluation_helpers_do_not_swallow_solve_deadline(entry):
    import numpy as np

    from geosolver.engine.standard.search import scipy_multistart_backend as backend

    def timed_out(*args, **kwargs):
        raise TimeoutError("injected solve deadline")

    ev = SimpleNamespace(
        evaluate_float_residual=timed_out,
        evaluate_guard=timed_out,
        evaluate_float_hard_feasibility=timed_out,
    )
    with pytest.raises(TimeoutError):
        if entry == "residual":
            backend._evaluate_float_residual_norm(
                evaluator=ev, values=np.array([0.0]), telemetry=backend._SearchTelemetry()
            )
        elif entry == "hard":
            backend._evaluate_hard_feasibility_penalty(evaluator=ev, values=np.array([0.0]))
        else:
            ev.evaluate_float_residual = lambda *args: SimpleNamespace(
                evaluation_status=EvaluationStatus.OK, is_finite=True, residual_vector=[0.0]
            )
            backend._rank_bounded_trf_starts(
                evaluator=ev, starts=[np.array([0.0])], telemetry=backend._SearchTelemetry()
            )
