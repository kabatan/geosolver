"""General numerical counterexamples from the performance review."""

from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import SearchBatchResult
from geosolver.engine.standard.evaluation.float_expressions import residual_norm
from geosolver.engine.standard.orchestration.run_search import _merge_search_batch_results
from geosolver.engine.standard.refinement.finite_difference_jacobian import (
    compute_finite_difference_jacobian,
)
from geosolver.engine.standard.refinement.mpmath_refiner import _run_rank_aware_findroot
from geosolver.engine.standard.search import scipy_multistart_backend as search
from geosolver.problem import domain_bounds


def test_zero_distance_retains_precision_for_exact_algebraic_answer():
    from geosolver import GeometryProblem, SolveOptions, solve

    # Answer stability at 250 digits is insufficient for the later domain
    # boundary/uncertainty check, even though x+y already looks unchanged.
    problem = GeometryProblem(
        id="zero-distance-precision",
        variables=["x", "y"],
        constructions=[
            {"name": "P", "expression": "Point(x,y)"},
            {"name": "Q", "expression": "Point(2,sqrt(2))"},
        ],
        conditions=[
            {"left": "Distance(P,Q)", "operator": "=", "right": 0},
            {"left": "x", "operator": ">", "right": 0},
            {"left": "y", "operator": ">", "right": 0},
        ],
        target="x+y",
    )
    result = solve(problem, SolveOptions(time_limit_seconds=180, cores=1, seed=0))
    assert result.status == "solved"
    assert len(result.answers) == 1
    answer = result.answers[0]
    assert answer.kind == "algebraic"
    assert answer.minimal_polynomial == ["1", "-4", "2"]
    assert answer.real_root_index == 1


@pytest.mark.parametrize("scale", [1e300, 1e-300])
def test_residual_norm_avoids_intermediate_overflow_and_underflow(scale):
    assert residual_norm([3 * scale, 4 * scale]) == pytest.approx(5 * scale, abs=0)


def test_residual_norm_retains_ordinary_search_rounding_and_rescues_subnormals():
    assert residual_norm([0.1, 0.2, 0.3]) == 0.37416573867739417
    assert residual_norm([3e-162, 4e-162]) == pytest.approx(5e-162, abs=0)


def test_shared_dependency_dag_is_expanded_once(monkeypatch):
    construction = [SimpleNamespace(name="c0", expr="x+100")]
    construction.extend(
        SimpleNamespace(name=f"c{i}", expr=f"c{i - 1}+c{i - 1}") for i in range(1, 45)
    )
    spec = SimpleNamespace(
        variables=SimpleNamespace(resolved_names=lambda: ["x"]),
        construction=construction,
        constraints=["c44"],
        v=[0],
        logical_plans=(),
    )
    monkeypatch.setattr(
        domain_bounds,
        "mathematical_bounds",
        lambda spec: {"x": SimpleNamespace(lower=None, upper=None)},
    )
    calls = 0
    original = domain_bounds.ast.parse

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(domain_bounds.ast, "parse", counted)
    assert domain_bounds.search_bounds(spec) == [(-200, 200)]
    assert calls <= 50


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


def test_jacobian_base_evaluation_uses_requested_precision():
    observed = []

    def residual(point, dps):
        observed.append(mp.dps)
        return [point[0] ** 2]

    with mp.workdps(15):
        jacobian = compute_finite_difference_jacobian(
            point=[mp.mpf(2)],
            dps=100,
            residual_fn=residual,
        )
    assert min(observed) == 100
    with mp.workdps(100):
        assert abs(jacobian[0][0] - 4) < mp.mpf("1e-65")


@pytest.mark.parametrize("sign", [-1, 1])
def test_one_sided_jacobian_at_domain_boundary(sign):
    def residual(point, dps):
        x = point[0]
        return None if sign * x < 0 else [3 * x + x * x]

    jacobian = compute_finite_difference_jacobian(
        point=[mp.mpf(0)],
        dps=100,
        residual_fn=residual,
    )
    assert jacobian is not None
    with mp.workdps(100):
        assert abs(jacobian[0][0] - 3) < mp.mpf("1e-65")


def test_rank_selection_is_invariant_to_equation_and_coordinate_units():
    from geosolver.engine.standard.refinement.mpmath_refiner import (
        _select_rank_revealing_subsystem,
    )

    with mp.workdps(100):
        matrix = [[mp.mpf("1e-80"), 0], [0, mp.mpf("1e80")]]
    rows, columns = _select_rank_revealing_subsystem(matrix, dps=100)
    assert set(rows) == set(columns) == {0, 1}


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


def test_explicit_verification_rank_error_bound_is_not_rescaled():
    from geosolver.engine.standard.refinement.mpmath_refiner import (
        _select_rank_revealing_subsystem,
    )

    with mp.workdps(100):
        matrix = [[1, 0], [0, mp.mpf("1e-80")]]
        selected = _select_rank_revealing_subsystem(
            matrix,
            dps=100,
            relative_tolerance=mp.mpf("1e-10"),
        )
    assert selected == ((0,), (0,))


def test_sparse_differences_reduce_evaluations_without_changing_derivatives():
    calls = []

    def residual(point, dps):
        calls.append(tuple(point))
        return [value * value for value in point]

    point = [mp.mpf(i + 1) for i in range(8)]
    grouped = compute_finite_difference_jacobian(
        point=point,
        dps=100,
        residual_fn=residual,
        row_dependencies=tuple(frozenset((i,)) for i in range(8)),
    )
    assert len(calls) == 3
    calls.clear()
    dense = compute_finite_difference_jacobian(point=point, dps=100, residual_fn=residual)
    assert len(calls) == 17
    assert grouped == dense


def test_sparse_differences_fall_back_at_one_sided_boundaries():
    def residual(point, dps):
        return [3 * point[0], 5 * point[1]] if point[0] >= 0 else None

    result = compute_finite_difference_jacobian(
        point=[mp.mpf(0), mp.mpf(1)],
        dps=100,
        residual_fn=residual,
        row_dependencies=(frozenset((0,)), frozenset((1,))),
    )
    assert result is not None
    with mp.workdps(100):
        assert abs(result[0][0] - 3) < mp.mpf("1e-65")
        assert abs(result[1][1] - 5) < mp.mpf("1e-65")
        assert result[0][1] == result[1][0] == 0


def test_static_residual_dependencies_include_targets_and_shared_constructions():
    from geosolver.engine.standard.problem.analysis_plan import ProblemAnalysisPlan

    spec = SimpleNamespace(
        construction=[SimpleNamespace(name="A", expr="x+x"), SimpleNamespace(name="B", expr="A+3")],
        constraints=["B-y", "z"],
        v=[0, "x"],
        logical_plans=(),
    )
    plan = ProblemAnalysisPlan(SimpleNamespace(spec=spec, var_names=("x", "y", "z")))
    assert plan.residual_variable_dependencies == (frozenset((0, 1)), frozenset((0, 2)))


def test_scaled_score_handles_extreme_finite_residuals_without_exception():
    import math

    from geosolver.engine.standard.evaluation.scaled_score import scaled_score

    assert scaled_score([3e300, 4e300], [1e300, 1e300]) == 25
    assert math.isinf(scaled_score([1e300]))


def test_scaled_score_preserves_exactly_representable_sum_for_search_ordering():
    from geosolver.engine.standard.evaluation.scaled_score import scaled_score

    # hypot(1, 1)**2 is 2.0000000000000004 and changes ordinary score ties.
    assert scaled_score([1.0, 1.0]) == 2.0


def test_pslq_does_not_repeat_the_unscaled_trial(monkeypatch):
    from geosolver.exact import polynomial_search

    calls = []

    def search_polynomial(value, degree, precision, **kwargs):
        calls.append((value, degree))
        return None

    monkeypatch.setattr(polynomial_search, "_find_polynomial_pslq", search_polynomial)
    monkeypatch.setattr(polynomial_search, "scale_candidates_for_value", lambda value: [1, 10])
    assert polynomial_search.find_minimal_polynomial(mp.mpf(7), max_degree=3) is None
    assert len(calls) == 6
    assert sum(value == 7 for value, degree in calls) == 3


@pytest.mark.parametrize("move_first", [False, True])
def test_jacobian_reuse_invalidates_when_the_point_changes(monkeypatch, move_first):
    from geosolver.engine.standard.refinement import mpmath_refiner as module
    from geosolver.engine.standard.refinement.refiner_config import RefinerConfig

    jacobian_points, trial_count = [], 0

    def jacobian(*, point, **kwargs):
        jacobian_points.append(tuple(point))
        return [[mp.mpf(1)]]

    def trial(*, point, **kwargs):
        nonlocal trial_count
        trial_count += 1
        if move_first and trial_count == 1:
            return [mp.mpf(1)], [mp.mpf(1)], True
        return point, [point[0]], False

    monkeypatch.setattr(module, "compute_finite_difference_jacobian", jacobian)
    monkeypatch.setattr(module, "run_line_search", trial)
    monkeypatch.setattr(module, "_problem_contains_call", lambda spec, name: False)
    refiner = module.MpmathRefiner(RefinerConfig(line_search_failure_limit=3))
    refiner._run_stage(
        bundle=SimpleNamespace(spec=None),
        evaluator=None,
        start_point=[mp.mpf(2)],
        bounds=((None, None),),
        dps=100,
        target_residual=mp.mpf("1e-50"),
        preserve_hard_feasibility=False,
        residual_fn=lambda point, dps: list(point),
    )
    assert jacobian_points == ([(mp.mpf(2),), (mp.mpf(1),)] if move_first else [(mp.mpf(2),)])


@pytest.mark.parametrize("precision", [30, 100])
@pytest.mark.parametrize("scale", ["1e-100", "1", "1e100"])
@pytest.mark.parametrize(
    "vertices,convex,crossed",
    [
        ([(0, 0), (2, 0), (2, 2), (0, 2)], True, False),
        ([(0, 0), (2, 2), (2, 0), (0, 2)], False, True),
        ([(0, 0), (2, 0), (1, 1), (2, 2), (0, 2)], False, False),
        ([(0, 0), (2, 0), (2, 2), (0, 0)], False, True),
    ],
)
def test_polygon_predicate_reuse_preserves_scaled_degeneracy_and_topology(
    precision, scale, vertices, convex, crossed
):
    from geosolver.geometry.mp.mp_core_types import MPPoint
    from geosolver.geometry.mp.mp_polygon_checks import mp_has_self_intersection, mp_is_convex

    with mp.workdps(precision):
        factor = mp.mpf(scale)
        points = [MPPoint(x * factor, y * factor) for x, y in vertices]
        for _ in range(2):
            assert mp_is_convex(*points) is convex
            assert mp_has_self_intersection(*points) is crossed


def test_polygon_predicate_reuse_invalidates_precision_and_exact_coordinate_changes():
    from geosolver.geometry.mp.mp_core_types import MPPoint
    from geosolver.geometry.mp.mp_polygon_checks import mp_is_convex

    with mp.workdps(100):
        points = [MPPoint(0, 0), MPPoint(1, 0), MPPoint(1, mp.mpf("1e-70"))]
        assert mp_is_convex(*points) is True
    with mp.workdps(40):
        assert mp_is_convex(*points) is False
    with mp.workdps(100):
        assert mp_is_convex(*points) is True
        # Reusing a mutable point object cannot return its previous answer.
        points[2].y = mp.mpf(0)
        assert mp_is_convex(*points) is False
        points[2].y = mp.mpf("1e-70")
        assert mp_is_convex(*points) is True
