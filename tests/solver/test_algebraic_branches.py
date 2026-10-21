"""Algebraic branches contracts and numerical regressions."""

import itertools
import re

import pytest
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import algebraic_branches, scale_chart
from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches
from geosolver.problem.adapter import to_engine_document
from geosolver.runtime.deadline import runtime_session
from geosolver.runtime.symbolic import OptionalSymbolicTimeout
from tests.helpers.capabilities import requires_cpu_timer


def reciprocal_family(count, reverse=False, repeated=False):
    names = [f"coordinate_{i}" for i in range(count)]
    parameter = names[-1]
    equations = [f"({i + 2})*({v}*{parameter}-1)" for i, v in enumerate(names[:-1])]
    equations.append(f"{parameter}**2-2")
    if repeated:
        equations = [f"({e})**2" for e in equations]
    if reverse:
        names.reverse()
        equations.reverse()
    return {
        "variables": names,
        "construction": [],
        "constraints": equations,
        "targets": [0] * len(equations),
    }


@requires_cpu_timer
@pytest.mark.parametrize("count,reverse", [(4, False), (5, True), (6, False), (7, True)])
def test_coupled_reciprocal_family_preserves_both_roots(count, reverse):
    payload = reciprocal_family(count, reverse=reverse)
    data = discover_polynomial_branches(payload)
    assert data is not None
    parameter = f"coordinate_{count - 1}"
    expected = [
        [sign * (2**0.5 if name == parameter else 2**-0.5) for name in payload["variables"]]
        for sign in (-1, 1)
    ]
    assert sorted(tuple(map(float, p)) for p in data["points"]) == pytest.approx(
        sorted(map(tuple, expected))
    )


@requires_cpu_timer
def test_squarefree_consequences_preserve_both_repeated_coupled_roots():
    data = discover_polynomial_branches(reciprocal_family(4, repeated=True))
    assert data is not None
    assert len(data["points"]) == 2


def test_eight_coupled_variables_remain_outside_optional_budget_gate():
    assert discover_polynomial_branches(reciprocal_family(8)) is None


def test_positive_dimensional_seven_variable_system_declines_without_fixing_gauge():
    payload = reciprocal_family(7)
    payload["constraints"].pop()
    payload["targets"].pop()
    assert discover_polynomial_branches(payload) is None


def test_root_product_overflow_does_not_return_a_truncated_subset():
    names = [f"q{i}" for i in range(7)]
    equations = [f"{v}**2-2" for v in names]
    equations.append("+".join(f"{v}**2" for v in names) + "-14")
    payload = {
        "variables": names,
        "construction": [],
        "constraints": equations,
        "targets": [0] * len(equations),
    }
    assert discover_polynomial_branches(payload) is None


def _family(names=("s", "a", "b", "c"), unit=1):
    replacement = dict(zip(("s", "a", "b", "c"), names, strict=True))

    def rename(source):
        return re.sub(r"\b(s|a|b|c)\b", lambda m: replacement[m[0]], source)

    equalities = [("a+b", "3*s"), ("a*b", "s*s"), ("c", "a+2*b")]
    problem = GeometryProblem.model_validate(
        {
            "id": "generated-triangular-scale",
            "variables": list(names),
            "constructions": [],
            "conditions": [
                {
                    "left": rename(f"{unit}*({left})"),
                    "operator": "=",
                    "right": rename(f"{unit}*({right})"),
                }
                for left, right in equalities
            ]
            + [{"left": names[0], "operator": ">", "right": "0"}],
            "target": rename("a/s"),
        }
    )
    return load_problem_bundle(to_engine_document(problem))


@requires_cpu_timer
@pytest.mark.parametrize("names", [("s", "a", "b", "c"), ("scale", "u", "v", "w")])
@pytest.mark.parametrize("unit", [1, 11])
@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_triangular_reconstruction_preserves_all_irrational_scale_shapes(names, unit, order):
    bundle = _family(names, unit)
    active = [names[i + 1] for i in order]
    data = algebraic_branches.discover_polynomial_branches(
        {
            "variables": active,
            "construction": [(names[0], "1")],
            "constraints": bundle.spec.constraints,
            "targets": bundle.targets,
            "guards": bundle.spec.guards,
            "report_work": True,
        }
    )
    assert data["work_telemetry"]["stop_reason"] is None
    branches = data["result"]
    assert branches is not None and len(branches["points"]) == 2
    evaluator = build_ir_evaluator(bundle)
    with mp.workdps(180):
        answers = []
        for point in branches["points"]:
            values = {names[0]: mp.mpf(7)} | {
                name: 7 * mp.mpf(value) for name, value in zip(active, point, strict=True)
            }
            result = verify_final_candidate(
                evaluator=evaluator, values=tuple(values[name] for name in names)
            )
            assert result.verified
            answers.append(result.answer_hp)
        assert sorted(answers) == pytest.approx(
            [(3 - mp.sqrt(5)) / 2, (3 + mp.sqrt(5)) / 2], rel=mp.mpf("1e-150")
        )


@requires_cpu_timer
def test_inner_timeout_retains_interrupted_phase_and_declines(monkeypatch):
    from geosolver.engine.standard.search.cartesian_polynomials import CartesianPolynomials

    def interrupt(*args):
        raise algebraic_branches.AlgebraicWorkLimit("generated interruption")

    monkeypatch.setattr(CartesianPolynomials, "scalar", interrupt)
    data = algebraic_branches.discover_polynomial_branches(
        {
            "variables": ["a"],
            "construction": [],
            "constraints": ["a"],
            "targets": ["1"],
            "report_work": True,
        }
    )
    assert data["result"] is None
    work = data["work_telemetry"]
    assert work["stop_reason"] == "inner_cpu_timeout"
    assert work["interrupted_phase"] == "polynomial_conversion"
    assert all(v >= 0 for values in work["phases"].values() for v in values.values())


def test_outer_timeout_keeps_fallback_and_has_distinct_counter(monkeypatch):
    bundle = _family()

    def interrupt(*args, **kwargs):
        raise OptionalSymbolicTimeout("generated outer interruption")

    monkeypatch.setattr(scale_chart, "request", interrupt)
    with runtime_session(None) as telemetry:
        assert (
            scale_chart.search_positive_scale_chart(
                bundle=bundle, evaluator=build_ir_evaluator(bundle)
            )
            is None
        )
    assert telemetry.counters["positive_scale_chart_outer_wall_timeout"] == 1


def test_inner_timeout_counter_includes_phase_without_admitting_candidates(monkeypatch):
    bundle = _family()
    monkeypatch.setattr(
        scale_chart,
        "request",
        lambda *args, **kwargs: {
            "result": None,
            "work_telemetry": {
                "stop_reason": "inner_cpu_timeout",
                "interrupted_phase": "branch_boxes",
                "phases": {"branch_boxes": {"wall_seconds": 0.1, "cpu_seconds": 0.09}},
            },
        },
    )
    with runtime_session(None) as telemetry:
        assert (
            scale_chart.search_positive_scale_chart(
                bundle=bundle, evaluator=build_ir_evaluator(bundle)
            )
            is None
        )
    assert telemetry.counters["positive_scale_chart_stop_inner_cpu_timeout"] == 1
    assert telemetry.counters["positive_scale_chart_interrupted_branch_boxes"] == 1
    assert telemetry.counters["positive_scale_chart_branch_boxes_wall_microseconds"] == 100000
    assert telemetry.counters["positive_scale_chart_branch_boxes_cpu_microseconds"] == 90000


def test_cpu_work_budget_does_not_charge_scheduler_or_idle_time():
    import signal
    import time

    if not hasattr(signal, "ITIMER_PROF"):
        pytest.skip("process CPU timer unavailable")
    with algebraic_branches._bounded_symbolic_work(0.02) as supported:
        assert supported
        time.sleep(0.06)
    started = time.process_time()
    with (
        pytest.raises(algebraic_branches.AlgebraicWorkLimit),
        algebraic_branches._bounded_symbolic_work(0.02),
    ):
        while time.process_time() - started < 1:
            pass
    assert time.process_time() - started < 0.2


def test_cpu_work_timer_leaves_an_independent_wall_timer_active():
    import signal
    import time

    if not hasattr(signal, "ITIMER_PROF"):
        pytest.skip("process CPU timer unavailable")
    alarms = []
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    try:
        signal.signal(signal.SIGALRM, lambda *_: alarms.append(True))
        signal.setitimer(signal.ITIMER_REAL, 0.02)
        with algebraic_branches._bounded_symbolic_work(0.5):
            deadline = time.monotonic() + 2
            while not alarms and time.monotonic() < deadline:
                time.sleep(0.01)
        assert alarms == [True]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def test_optional_work_does_not_replace_an_enclosing_cpu_timer():
    import signal

    if not hasattr(signal, "ITIMER_PROF"):
        pytest.skip("process CPU timer unavailable")
    previous_handler = signal.getsignal(signal.SIGPROF)
    previous_timer = signal.getitimer(signal.ITIMER_PROF)

    def handler(*_):
        pass

    try:
        signal.signal(signal.SIGPROF, handler)
        signal.setitimer(signal.ITIMER_PROF, 1)
        with algebraic_branches._bounded_symbolic_work(0.5) as supported:
            assert not supported
            assert signal.getsignal(signal.SIGPROF) is handler
            remaining = signal.getitimer(signal.ITIMER_PROF)[0]
            assert 0 < remaining <= 1.01
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
        signal.signal(signal.SIGPROF, previous_handler)
        signal.setitimer(signal.ITIMER_PROF, *previous_timer)


def discover(names, equations, targets=None, constructions=()):
    return discover_polynomial_branches(
        {
            "variables": names,
            "construction": constructions,
            "constraints": equations,
            "targets": [0] * len(equations) if targets is None else targets,
        }
    )


@requires_cpu_timer
@pytest.mark.parametrize("r,s,scale", [(2, -3, 1), (5, -7, -11), (-11, 4, 1000)])
def test_repeated_roots_are_all_preserved_under_equation_scaling(r, s, scale):
    data = discover(["z"], [f"{scale}*(z-({r}))**2*(z-({s}))**2", "0"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == sorted([r, s])


@requires_cpu_timer
@pytest.mark.parametrize("offset,radius", [(1, 5), (4, 10), (-2, 13)])
def test_affine_elimination_preserves_both_circle_line_branches(offset, radius):
    data = discover(["u", "v"], [f"u-v-{offset}", f"u*u+v*v-{radius}"])
    assert data is not None
    import sympy as sp

    t = sp.Symbol("t")
    expected = sorted(float(r) for r in sp.real_roots((t - offset) ** 2 + t * t - radius))
    assert sorted(float(p[0]) for p in data["points"]) == pytest.approx(expected)


@requires_cpu_timer
def test_distance_squaring_retains_both_signs_as_proposals():
    data = discover(["x"], ["Distance(A,B)"], ["7"], [("A", "Point(x,0)"), ("B", "Point(0,0)")])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-7, 7]


@requires_cpu_timer
def test_radical_norm_sign_proves_extra_branch_invalid():
    data = discover(["x"], ["sqrt(x+1)+x-1"])
    assert data is not None
    # x=3 violates the necessary real norm sign a*b<=0.
    assert sorted(float(p[0]) for p in data["points"]) == [0]
    assert data["proved_norm_sign_exclusions"] == 1


@requires_cpu_timer
def test_denominator_clearing_never_promises_original_domain_validity():
    data = discover(["x"], ["(x*x-1)/(x-1)"])
    assert data is not None
    # SymPy may cancel x=1. Either conservative superset is permitted.
    assert -1 in [float(p[0]) for p in data["points"]]


def test_shape_position_division_does_not_lose_a_singular_branch():
    # At y=0, xy=0 leaves a continuum; dividing by y would lose it.
    assert discover(["x", "y"], ["x*y", "y*(y-1)"]) is None


def test_positive_dimensional_system_keeps_numerical_search():
    assert discover(["x", "y"], ["x+y-1"]) is None


def test_unsupported_transcendental_keeps_numerical_search():
    assert discover(["x"], ["sin(x)"]) is None


@requires_cpu_timer
def test_close_roots_keep_distinct_high_precision_starting_coordinates():
    data = discover(["x"], ["(x-1)**2*(x-1-1/100000000000000000000)**2"])
    assert data is not None
    assert len(data["points"]) == 2
    assert data["points"][0] != data["points"][1]


@requires_cpu_timer
def test_area_shoelace_retains_both_orientation_branches():
    data = discover(["h"], ["Area(Point(0,0),Point(6,0),Point(1,h))"], [12])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-4, 4]


@requires_cpu_timer
def test_circle_incidence_has_exact_quadratic_relaxation():
    data = discover(["h"], ["OnCircle(Point(3,h),Circle(Point(0,0),5))"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-4, 4]


@requires_cpu_timer
def test_exact_algebraic_constant_coefficients():
    data = discover(["x"], ["x*x-sqrt(2)"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == pytest.approx([-(2**0.25), 2**0.25])


@requires_cpu_timer
def test_line_intersection_coordinates_are_rational():
    constructions = [
        ("L", "Line(Point(0,0),Point(4,2))"),
        ("M", "Line(Point(0,3),Point(3,0))"),
        ("P", "Intersect(L,M)"),
    ]
    data = discover(["x"], ["x-P.x"], constructions=constructions)
    assert data is not None
    assert float(data["points"][0][0]) == 2


@requires_cpu_timer
def test_circumcenter_uses_exact_translated_cartesian_coordinates():
    data = discover(
        ["x", "y"],
        ["x-O.x", "y-O.y"],
        constructions=[("O", "Circumcenter(Point(0,0),Point(6,0),Point(0,8))")],
    )
    assert data is not None
    assert list(map(float, data["points"][0])) == [3, 4]


@requires_cpu_timer
def test_nonzero_perpendicular_measure_retains_normalization():
    data = discover(["x"], ["Perpendicular(Line(1,0,0),Line(1,x,0))"], ["1/sqrt(2)"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-1, 1]


@requires_cpu_timer
def test_internal_and_external_circle_tangencies_all_survive_relaxation():
    data = discover(["x"], ["IsTangent(Circle(Point(x,0),2),Circle(Point(0,0),3))"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-5, -1, 1, 5]


@requires_cpu_timer
def test_only_proved_false_original_guards_exclude_relaxation_roots():
    data = discover_polynomial_branches(
        {
            "variables": ["x"],
            "construction": [],
            "constraints": ["x*x-1"],
            "targets": [0],
            "guards": ["AssumeGt(x,0)", "UnknownPrimitive(x)"],
        }
    )
    assert data is not None
    assert [float(p[0]) for p in data["points"]] == [1]
    assert data["proved_guard_exclusions"] == 1
    assert data["false_original_guard_counts"] == {"0": 1}


@requires_cpu_timer
def test_undefined_guard_expression_stays_unresolved():
    data = discover_polynomial_branches(
        {
            "variables": ["x"],
            "construction": [],
            "constraints": ["x*x-1"],
            "targets": [0],
            "guards": ["AssumeEq(1/(x-1),0)"],
        }
    )
    assert data is not None
    # The pole at 1 is unresolved, not misclassified as a false equality.
    assert [float(p[0]) for p in data["points"]] == [1]
    assert data["false_original_guard_counts"] == {"0": 1}


def test_optional_symbolic_timeout_does_not_become_a_geometry_failure(monkeypatch):
    from geosolver.engine.standard.search.algebraic_branches import AlgebraicWorkLimit
    from geosolver.engine.standard.search.cartesian_polynomials import CartesianPolynomials

    def interrupted(*_):
        raise AlgebraicWorkLimit("test timeout")

    monkeypatch.setattr(CartesianPolynomials, "scalar", interrupted)
    assert discover(["x"], ["x*x-1"]) is None


@requires_cpu_timer
@pytest.mark.parametrize("shift,scale", [(0, 1), (3, -7), (-5, 13)])
def test_two_radical_sum_keeps_unique_real_domain_root_under_transformations(shift, scale):
    # sqrt(z)+sqrt(z+1)=3 has exactly z=16/9 on its real domain.
    z = f"(x-({shift}))"
    data = discover(["x"], [f"{scale}*(sqrt({z})+sqrt({z}+1)-3)"])
    assert data is not None
    assert [float(p[0]) for p in data["points"]] == pytest.approx([shift + 16 / 9])


@requires_cpu_timer
def test_two_distance_radicals_retain_both_geometric_branches():
    data = discover(["x"], ["sqrt(x*x+1)+sqrt(x*x+4)"], [5])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == pytest.approx(
        [-4 * 6**0.5 / 5, 4 * 6**0.5 / 5]
    )


@requires_cpu_timer
def test_two_absolute_values_retain_both_exterior_branches():
    data = discover(["x"], ["abs(x-2)+abs(x+3)"], [9])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-5, 4]


@requires_cpu_timer
def test_nested_radical_norm_sign_keeps_original_domain_branch():
    data = discover(["x"], ["sqrt(x+sqrt(x+1))"], [2])
    assert data is not None
    # The other root contradicts an exactly proved necessary norm sign.
    assert sorted(float(p[0]) for p in data["points"]) == pytest.approx([(9 - 21**0.5) / 2])


@requires_cpu_timer
def test_three_radical_sum_never_loses_original_root():
    data = discover(["x"], ["sqrt(x+1)+sqrt(x+4)+sqrt(x+9)"], [6])
    assert data is not None
    assert any(abs(float(p[0])) < 1e-30 for p in data["points"])


@requires_cpu_timer
def test_multiradical_denominator_pole_does_not_lose_valid_root():
    data = discover(["x"], ["sqrt(x+1)/(x-1)+sqrt(x+4)"], [1])
    assert data is not None
    assert any(abs(float(p[0])) < 1e-30 for p in data["points"])


def test_multiradical_identity_retains_numerical_fallback():
    assert discover(["x"], ["sqrt(x*x)-abs(x)"]) is None


@requires_cpu_timer
@pytest.mark.parametrize("scale,reverse", [(1, False), (-7, True), (1000, False)])
def test_disconnected_univariate_components_preserve_full_cartesian_product(scale, reverse):
    equations = [f"{scale}*(x*x-4)", "y*y-9"]
    if reverse:
        equations.reverse()
    data = discover(["x", "y"], equations)
    assert data is not None
    assert data["method"] == "cartesian_component_univariate_isolation"
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-2, -3),
        (-2, 3),
        (2, -3),
        (2, 3),
    ]


@requires_cpu_timer
def test_disconnected_bivariate_components_avoid_global_variable_gate():
    data = discover(["a", "b", "c", "d"], ["a*b-1", "b*b-4", "c-d*d", "d*d-9"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-0.5, -2, 9, -3),
        (-0.5, -2, 9, 3),
        (0.5, 2, 9, -3),
        (0.5, 2, 9, 3),
    ]


@requires_cpu_timer
def test_components_are_found_after_coupling_affine_elimination():
    data = discover(["x", "y", "u", "v"], ["x+y-1", "u-v-2", "x*x-4", "u*u-9"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-2, 3, -3, -5),
        (-2, 3, 3, 1),
        (2, -1, -3, -5),
        (2, -1, 3, 1),
    ]


@requires_cpu_timer
def test_original_guard_couples_components_only_after_complete_product():
    data = discover_polynomial_branches(
        {
            "variables": ["x", "y"],
            "construction": [],
            "constraints": ["x*x-4", "y*y-9"],
            "targets": [0, 0],
            "guards": ["AssumeGt(x*y,0)"],
        }
    )
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [(-2, -3), (2, 3)]
    assert data["proved_guard_exclusions"] == 2


def test_any_positive_dimensional_component_retains_baseline():
    assert discover(["x", "y", "z"], ["x*x-4", "y*z-1"]) is None


def test_unused_coordinate_is_not_arbitrarily_fixed_even_if_target_could_be_invariant():
    assert discover(["x", "unused"], ["x*x-4"]) is None


def test_component_product_budget_declines_without_truncating_root_set():
    names = ["a", "b", "c", "d", "e"]
    assert discover(names, [f"{v}*{v}-1" for v in names]) is None


@requires_cpu_timer
def test_boundary_product_budget_retains_all_sixteen_configurations():
    names = ["a", "b", "c", "d"]
    data = discover(names, [f"{v}*{v}-1" for v in names])
    assert data is not None
    assert len(data["points"]) == 16
    assert len({tuple(p) for p in data["points"]}) == 16


@requires_cpu_timer
def test_basis_can_expose_components_hidden_by_equation_mixing():
    data = discover(["x", "y"], ["x*x+y*y-5", "x*x-y*y-3"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-2, -1),
        (-2, 1),
        (2, -1),
        (2, 1),
    ]


def test_hidden_component_product_over_budget_keeps_baseline():
    # Mixing preserves the same 5x5 independent root set, exceeding16 candidates.
    a = "(x-1)*(x-2)*(x-3)*(x-4)*(x-5)"
    b = "(y-1)*(y-2)*(y-3)*(y-4)*(y-5)"
    assert discover(["x", "y"], [f"{a}+{b}", f"{a}-{b}"]) is None


@requires_cpu_timer
@pytest.mark.parametrize("scale,ordering", [(1, ["x", "y"]), (-11, ["y", "x"])])
def test_separating_form_recovers_all_axis_intersections(scale, ordering):
    data = discover(ordering, [f"{scale}*(x*x+y*y-1)", "x*y"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-1, 0),
        (0, -1),
        (0, 1),
        (1, 0),
    ]


@requires_cpu_timer
def test_squarefree_parameter_constraint_removes_multiplicity_without_losing_roots():
    data = discover(["x", "y"], ["(x*x+y*y-1)**2", "x*y"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-1, 0),
        (0, -1),
        (0, 1),
        (1, 0),
    ]


def test_nonseparating_all_bounded_forms_declines_without_root_truncation():
    # Four roots: (1,0),(2,0),(3,0),(0,1). Every tried T=x+k*y,
    # k=1,2,3, aliases two configurations; no partial parametrization is valid.
    assert discover(["x", "y"], ["x*y", "(x-1)*(x-2)*(x-3)+6*y"]) is None


@requires_cpu_timer
def test_exact_squarefree_consequences_remove_noncyclic_nilpotents():
    data = discover(["x", "y"], ["x*x", "x*y", "y*y"])
    assert data is not None
    assert [list(map(float, point)) for point in data["points"]] == [[0, 0]]


def test_separating_form_does_not_make_positive_dimensional_system_finite():
    assert discover(["x", "y"], ["x*x+y*y-1"]) is None


@requires_cpu_timer
def test_complex_only_variety_never_generates_real_coordinate_proposals():
    data = discover(["x", "y"], ["x*x+y*y+1", "x*y"])
    assert data is not None
    assert data["points"] == []


def test_distinct_roots_below_decimal_proposal_resolution_keep_baseline():
    assert discover(["x"], ["(x-1)*(x-1-1/10**200)"]) is None
