"""Verification contracts and numerical regressions."""

from collections import OrderedDict
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver import GeometryProblem, solve
from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.snapshots import evaluation_session
from geosolver.engine.standard.evaluation.verification_domains import DomainVerifier
from geosolver.engine.standard.evaluation.verification_numerics import differentiate, linearization
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.runtime.deadline import deadline_scope, runtime_session


def _precision_evaluator(constraints, *, construction=(), guards=(), answer="x"):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": list(construction),
                "constraints": list(constraints),
                "guards": list(guards),
                "answer": answer,
            }
        )
    )


@pytest.mark.parametrize("precision", [180, 350, 500])
def test_stationary_smooth_derivative_has_finite_absolute_error(precision):
    with mp.workdps(precision):
        result = differentiate(
            lambda p: (1 + p[0] ** 2 + p[0] ** 3, ()), (mp.mpf(0),), 0, mp.mpf(1), precision
        )
        assert result is not None
        value, error = result
        assert abs(value) <= error and error < mp.mpf("1e-30")


def test_cusp_is_not_misidentified_as_a_stationary_smooth_point():
    with mp.workdps(350):
        result = differentiate(lambda p: (abs(p[0]), ()), (mp.mpf("1e-250"),), 0, mp.mpf(1), 350)
        assert result is None or abs(result[0] - 1) <= result[1]


def test_positive_nonsmooth_margin_uses_bounded_one_sided_variation():
    from geosolver.engine.standard.evaluation.verification_domains import DomainVerifier

    with mp.workdps(350):
        domain = DomainVerifier(None, (mp.mpf(0),), (mp.mpf("1e-100"),), (mp.mpf(1),), 350)
        value, error = domain.measure(lambda p: (1 - abs(p[0]), ()), "piecewise margin")
        assert value > 100 * error and error >= mp.mpf("1e-100")


def test_discontinuous_margin_cannot_use_the_nonsmooth_slope_bound():
    with mp.workdps(350):
        result = differentiate(
            lambda p: (mp.mpf(1) if p[0] >= 0 else mp.mpf(2), ()),
            (mp.mpf(0),),
            0,
            mp.mpf(1),
            350,
            allow_nonsmooth=True,
        )
        assert result is None


def test_verification_keeps_high_precision_input_and_rejects_a_wrong_circle():
    construction = [
        {"name": "O", "expr": "Point(0,0)"},
        {"name": "P", "expr": "Point(cos(x),sin(x))"},
        {"name": "omega", "expr": "Circle(O,1)"},
    ]
    with mp.workdps(180), runtime_session(None):
        point = (mp.sqrt(2),)
        ev = _precision_evaluator(["x*x-2", "OnCircle(P,omega)"], construction=construction)
        original = abs(point[0] - mp.sqrt(2))
        result = verify_final_candidate(evaluator=ev, values=point)
        assert result.verified and abs(result.values[0] - mp.sqrt(2)) <= original + mp.mpf("1e-175")
        bad = _precision_evaluator(["x*x-2", "OnCircle(P,omega)-0.01"], construction=construction)
        assert not verify_final_candidate(evaluator=bad, values=point).verified


def test_discovery_precision_does_not_override_final_error_bound():
    from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer

    with mp.workdps(350):
        result = identify_answer(
            answer_hp=mp.sqrt(2) + mp.mpf("1e-110"),
            tier="strict",
            input_precision_dps=350,
            answer_uncertainty=mp.mpf("1e-120"),
        )
        assert result.selected_exact_value != "sqrt(2)"
        result = identify_answer(
            answer_hp=mp.sqrt(2) + mp.mpf("1e-100"),
            tier="strict",
            input_precision_dps=350,
            answer_uncertainty=mp.mpf("1e-99"),
        )
        assert result.selected_exact_value == "sqrt(2)"


@pytest.mark.parametrize("offset", ["1e100", "1e1000"])
def test_constant_contradiction_never_publishes_an_answer(offset):
    result = solve(
        GeometryProblem(
            id="contradiction",
            variables=[],
            constructions=[],
            conditions=[{"left": offset, "operator": "=", "right": offset + "+1"}],
            target="42",
        )
    )
    assert not result.answers


def test_common_offset_cannot_hide_variable_contradiction():
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.problem.ir.schema import IRSpec, IRVariableSpec

    spec = IRSpec(
        task="solve",
        variables=IRVariableSpec(names=["x"]),
        constraints=["1e1000+x"],
        v=["1e1000+x+1"],
        answer_expr="x",
    )
    result = verify_final_candidate(
        evaluator=build_ir_evaluator(load_problem_bundle(spec)), values=(mp.mpf(1),)
    )
    assert not result.verified


def _final_evaluator(constraint: str):
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
    plain = verify_final_candidate(evaluator=_final_evaluator("x"), values=value)
    scaled = verify_final_candidate(evaluator=_final_evaluator("1e200 * x"), values=value)

    # Final verification now improves coordinates; both equations reach exact 0.
    assert plain.verified and plain.values == (mp.mpf(0),)
    assert scaled.verified and scaled.values == (mp.mpf(0),)
    assert mp.almosteq(plain.normalized_residual, scaled.normalized_residual)


def test_small_normalized_residual_is_accepted_at_final_precision() -> None:
    result = verify_final_candidate(
        evaluator=_final_evaluator("1e-200 * x"),
        values=(mp.mpf("1e-40"),),
    )

    assert result.verified
    assert result.precision_dps == 180
    assert result.normalized_residual <= mp.mpf("1e-30")


def test_explicit_bounds_are_a_final_hard_gate() -> None:
    result = verify_final_candidate(
        evaluator=_final_evaluator("x - 2"),
        values=(mp.mpf("2"),),
    )

    assert not result.verified
    assert result.status == "bounds_violation"


def _finalization_evaluator(constraints, *, guards=(), answer="x+y"):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "construction": [],
                "constraints": list(constraints),
                "guards": list(guards),
                "answer": answer,
            }
        )
    )


@pytest.mark.parametrize("factor", ["1", "1e-200", "1e200"])
def test_unresolved_cusp_coordinate_is_not_an_exact_free_parameter(factor):
    ev = _finalization_evaluator(
        [f"{factor}*Distance(Point(x,y),Point(0,y))", "y-7"], guards=["x>0"]
    )
    with mp.workdps(600), runtime_session(None):
        result = verify_final_candidate(evaluator=ev, values=(mp.mpf("1e-502"), mp.mpf(7)))
    assert not result.verified
    assert result.coordinate_uncertainty[0] > 0


@pytest.mark.parametrize(
    "constraints,point,guards",
    [
        (["y-7"], ("1e-600", "7"), ["x>0"]),
        (["y-x", "2*y-2*x"], ("1e-600", "1e-600"), ["x>0"]),
        (["x*x+y*y-25"], ("3", "4"), ["x>0", "y>0"]),
        (["x*x", "y-7"], ("0", "7"), []),
        (["x-1e-40", "y-7"], ("1e-40", "7"), ["x>0"]),
    ],
)
def test_true_freedom_tangent_and_tiny_positive_values_survive(constraints, point, guards):
    with mp.workdps(600), runtime_session(None):
        result = verify_final_candidate(
            evaluator=_finalization_evaluator(constraints, guards=guards),
            values=tuple(mp.mpf(x) for x in point),
        )
    assert result.verified, result.hard_failure_tags


def test_unresolved_coordinate_uncertainty_reaches_selected_coordinates():
    from geosolver.engine.standard.evaluation.verification_numerics import correction

    with mp.workdps(180):
        _, uncertainty = correction(
            [mp.mpf(0)],
            [[mp.mpf(1), mp.mpf(2)]],
            [[mp.mpf(0), mp.mpf(0)]],
            [mp.mpf(1), mp.mpf(1)],
            180,
            evaluation_scales=[mp.mpf(3)],
        )
        # The selected y column solves x+2y=0. Uncertainty in x must reach y.
        assert uncertainty[0] > 0
        assert uncertainty[1] >= uncertainty[0] / 2


@pytest.mark.parametrize("coordinate", ["nan", "inf", "-inf"])
def test_interrupted_record_with_nonfinite_coordinates_is_not_a_candidate(coordinate):
    candidate = RefinedCandidate(
        x_hp=(mp.mpf(coordinate), mp.mpf(2)),
        residual_norm_hp=mp.inf,
        answer_hp=None,
        refinement_status="deadline_reached",
        phase_history=(),
        candidate_id=18,
    )
    result = assemble_exact_results(
        refined_candidates=(candidate,), evaluator=_finalization_evaluator(["x-1", "y-2"])
    )
    assert not result.answer_values
    assert result.rejection_tags == ("coordinate_non_finite",)


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


def test_only_completed_success_at_identical_coordinates_and_schedule_is_shared(monkeypatch):
    import importlib

    assembly = importlib.import_module(
        "geosolver.engine.standard.orchestration.assemble_exact_results"
    )
    evaluator = SimpleNamespace(
        final_verification_cache=OrderedDict(), verified_coordinate_cache=OrderedDict()
    )
    candidate = SimpleNamespace(candidate_key="a", revision=0, x_hp=(mp.mpf(1),))
    calls = []
    success = SimpleNamespace(verified=True)

    def verify(**kwargs):
        calls.append(kwargs)
        return success

    monkeypatch.setattr(assembly, "verify_final_candidate", verify)
    assert assembly._verify_revision(evaluator, candidate) is success
    other = SimpleNamespace(**(vars(candidate) | {"candidate_key": "b"}))
    assert assembly._verify_revision(evaluator, other) is success
    assert len(calls) == 1
    assembly._verify_revision(evaluator, other, precision_schedule=(250, 350, 500))
    assert len(calls) == 2
    with mp.workdps(200):
        close = SimpleNamespace(**(vars(other) | {"x_hp": (mp.mpf(1) + mp.mpf("1e-150"),)}))
    assembly._verify_revision(evaluator, close)
    assert len(calls) == 3
    with deadline_scope(0), pytest.raises(TimeoutError):
        assembly._verify_revision(evaluator, other)


@pytest.mark.parametrize("interrupted", [False, True])
def test_unresolved_or_interrupted_results_are_not_shared_between_candidates(
    monkeypatch, interrupted
):
    import importlib

    assembly = importlib.import_module(
        "geosolver.engine.standard.orchestration.assemble_exact_results"
    )
    evaluator = SimpleNamespace(
        final_verification_cache=OrderedDict(), verified_coordinate_cache=OrderedDict()
    )
    calls = []

    def verify(**kwargs):
        calls.append(kwargs)
        if interrupted:
            raise TimeoutError("fixture")
        return SimpleNamespace(verified=False)

    monkeypatch.setattr(assembly, "verify_final_candidate", verify)
    for key in ("a", "b"):
        candidate = SimpleNamespace(candidate_key=key, revision=0, x_hp=(mp.mpf(1),))
        if interrupted:
            with pytest.raises(TimeoutError):
                assembly._verify_revision(evaluator, candidate)
        else:
            assembly._verify_revision(evaluator, candidate)
    assert len(calls) == 2
    assert not evaluator.verified_coordinate_cache


def _dependency_evaluator(extra=()):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y", "z"]},
                "construction": [
                    {"name": "O", "expr": "Point(0,0)"},
                    {"name": "P", "expr": "Point(x,0)"},
                    {"name": "Q", "expr": "Point(y,0)"},
                    {"name": "R", "expr": "Midpoint(P,Q)"},
                    *extra,
                ],
                "constraints": ["x-2", "y-3", "z-4"],
                "guards": ["x>0", "y>0", "z>0"],
                "answer": "Distance(O,P)",
            }
        )
    )


def test_coordinate_dependencies_include_transitive_construction_leaves():
    plan = _dependency_evaluator().evaluation_store.plan
    assert plan.variable_dependencies(("Distance(O,P)",)) == frozenset({0})
    assert plan.variable_dependencies(("Distance(O,R)",)) == frozenset({0, 1})
    assert plan.variable_dependencies(("Distance(O,R)+z",)) == frozenset({0, 1, 2})
    assert plan.variable_dependencies(("Distance(O,O)",)) == frozenset()


def test_independent_coordinates_need_no_finite_difference(monkeypatch):
    from geosolver.engine.standard.evaluation import verification_domains

    differentiate = verification_domains.differentiate
    columns = []

    def recorded(function, point, index, *args, **kwargs):
        columns.append(index)
        return differentiate(function, point, index, *args, **kwargs)

    monkeypatch.setattr(verification_domains, "differentiate", recorded)
    with mp.workdps(120), high_precision_mode():
        point = tuple(map(mp.mpf, (2, 3, 4)))
        error = mp.mpf("1e-30")
        domain = DomainVerifier(
            _dependency_evaluator(), point, (error,) * 3, (mp.mpf(10),) * 3, 120
        )
        value, uncertainty = domain.measure(domain.scalar("Distance(O,P)"), "distance")
        assert value == 2
        assert error <= uncertainty < 2 * error
        assert columns == [0]


def test_scalar_slice_keeps_unrelated_construction_out_of_difference_evaluations():
    ev = _dependency_evaluator()
    with mp.workdps(120), high_precision_mode():
        point = tuple(map(mp.mpf, (2, 3, 4)))
        domain = DomainVerifier(ev, point, (mp.mpf("1e-30"),) * 3, (mp.mpf(10),) * 3, 120)
        value, calls, trace, margins = domain.expression_snapshot(point, "Distance(O,P)")
        assert value == 2 and not trace
        snapshots = tuple(ev.evaluation_store.snapshots.values())
        assert len(snapshots) == 1
        assert set(snapshots[0].completed) == {"O", "P"}


def test_final_verification_still_rejects_unrelated_invalid_construction():
    ev = _dependency_evaluator(extra=({"name": "bad", "expr": "Circle(O,0)"},))
    with mp.workdps(180):
        result = verify_final_candidate(evaluator=ev, values=tuple(map(mp.mpf, (2, 3, 4))))
    assert not result.verified


def _contract_evaluator(constraints=("x*x-1", "y-2"), guards=("x>0",)):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "bounds": [[-3, 3], [-3, 3]],
                "construction": [{"name": "P", "expr": "Point(x,y)"}],
                "constraints": list(constraints),
                "guards": list(guards),
                "answer": "x+y",
            }
        )
    )


@pytest.mark.parametrize("precision", [80, 180, 500])
@pytest.mark.parametrize(
    "constraints",
    [
        ("x*x-1", "y-2", "x+y-3"),
        ("abs(x)", "min(abs(x),abs(y))", "Distance(P,Point(0,0))"),
        ("Distance(Intersect(Line(Point(-3,y),Point(3,y)),Circle(Point(0,0),2),n=1),P)-1", "x-y"),
        ("sqrt(x)", "sqrt(-x)", "y"),
    ],
)
def test_batched_linearization_matches_scalar_values_errors_and_traces(precision, constraints):
    ev = _contract_evaluator(constraints)
    with mp.workdps(precision), high_precision_mode(), evaluation_session(ev):
        point = (mp.mpf("0.2"), mp.mpf("0.4"))
        bases_a, bases_b = [], []
        args = (ev.verification_equations, point, ev.bundle.var_names, (mp.mpf(3),) * 2, precision)
        a = linearization(*args, batch=False, base_samples=bases_a)
        b = linearization(*args, batch=True, base_samples=bases_b)

        def same(left, right):
            if isinstance(left, list | tuple):
                return len(left) == len(right) and all(
                    same(x, y) for x, y in zip(left, right, strict=True)
                )
            if isinstance(left, mp.mpf) and mp.isnan(left):
                return mp.isnan(right)
            return left == right

        assert same(a, b)
        assert same(bases_a, bases_b)
