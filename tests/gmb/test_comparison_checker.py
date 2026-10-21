"""Artificial, independent fixtures; no official case is solved or scored here."""

from __future__ import annotations

import ast
import copy
import importlib
import sys
from pathlib import Path

import mpmath
import pytest

from tests.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))
try:
    checker = importlib.import_module("benchmarks.gmb_comparison.checker")
    geometry = importlib.import_module("benchmarks.gmb_comparison.checker_geometry")
finally:
    sys.path.pop(0)
CHECKER_POLICY = checker.CHECKER_POLICY
check_configuration = checker.check_configuration
inspect_gmbl = checker.inspect_gmbl
parse_gmbl = checker.parse_gmbl
witness_from_gmb_model = checker.witness_from_gmb_model
CheckError = geometry.CheckError


def witness(points=None, lines=None, circles=None, choices=None):
    return {
        "points": points or {},
        "lines": lines or {},
        "circles": circles or {},
        "choices": choices or {},
    }


def codes(result):
    return {clause.get("code") for clause in result["assumptions"]}


def test_parser_is_independent_preserves_decimal_tokens_and_comments():
    source = "; comment\n(param A point) (assert (= 1.0000000000000000001 1)) ; ignored"
    assert parse_gmbl(source)[1][1][1] == "1.0000000000000000001"
    with pytest.raises(CheckError):
        parse_gmbl("(param A point")


@pytest.mark.parametrize(
    "source",
    [
        "(param A point) (assert (magic A))",
        "(param A point) (assert (on-line A unknown))",
        "(param A point) (define A point (midp A A))",
        "(assert (= 1))",
        "(param A point) (eval (unknown A))",
    ],
)
def test_unsupported_or_malformed_source_cannot_pass(source):
    result = check_configuration(source, witness({"A": [0, 0]}))
    assert not result["valid"]
    assert not inspect_gmbl(source)["supported"]


def test_all_official_inputs_have_static_opcode_coverage_without_running_them():
    directory = Path("benchmarks/gmb/.runtime/source/problems/IMO")
    if not directory.is_dir():
        pytest.skip("pinned optional GMB checkout is not installed")
    sources = list(directory.glob("*.smt2"))
    assert len(sources) == 36
    for path in sources:
        result = inspect_gmbl(path.read_text())
        assert result["supported"], (path, result["issues"])
        assert result["declarations"]


def test_definition_is_checked_instead_of_silently_recomputed():
    source = "(param (A B C) triangle) (define M point (midp A B))"
    data = witness({"A": [0, 0], "B": [2, 0], "C": [1, 2], "M": [1, 0]})
    assert check_configuration(source, data)["valid"]
    data["points"]["M"] = ["1.1", 0]
    result = check_configuration(source, data)
    assert not result["valid"]
    assert result["assumptions"][1]["checks"][0]["label"] == "defined_object_consistency"


def test_goal_cannot_repair_or_reject_assumptions_and_scope_is_explicit():
    source = "(param (A B C) triangle) (eval (cong A B A C))"
    result = check_configuration(source, witness({"A": [0, 0], "B": [3, 0], "C": [0, 4]}))
    assert result["valid"] and not result["goals_valid"]
    assert result["original_problem_valid"] is None
    assert result["existence_proved"] is False


def test_unknown_goal_opcode_locks_evaluation_instead_of_skipping_it():
    result = check_configuration("(param A point) (eval (banana A))", witness({"A": [0, 0]}))
    assert not result["valid"] and result["status"] == "unsupported"


def test_no_global_distinctness_is_added_and_extra_points_cannot_affect_scale():
    source = "(param (A B C) triangle) (define H point (orthocenter A B C))"
    data = witness({"A": [0, 0], "B": [4, 0], "C": [0, 3], "H": [0, 0]})
    result = check_configuration(source, data)
    assert result["valid"]  # H=A is a legitimate right triangle.
    data["points"]["UNDECLARED"] = ["1e200", "1e200"]
    assert check_configuration(source, data) == result


def test_missing_declared_object_is_not_rebuilt():
    result = check_configuration(
        "(param A point) (define M point (midp A A))", witness({"A": [0, 0]})
    )
    assert not result["valid"] and result["code"] == "missing_witness_object"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {"nonfinite": "nan"}, True])
def test_nonfinite_or_boolean_coordinates_never_pass(bad):
    assert not check_configuration("(param A point)", witness({"A": [bad, 0]}))["valid"]


@pytest.mark.parametrize("radius", [0, -1])
def test_nonpositive_circle_radius_rejected(radius):
    result = check_configuration(
        "(param C circle)", witness(circles={"C": {"center": [0, 0], "radius": radius}})
    )
    assert not result["valid"] and result["code"] == "nonpositive_radius"


def test_triangle_and_circle_degeneracy_cannot_pass():
    source = "(param (A B C) triangle) (define O point (circumcenter A B C))"
    result = check_configuration(
        source, witness({"A": [0, 0], "B": [1, 0], "C": [2, 0], "O": [0, 0]})
    )
    assert not result["valid"]
    assert "collinear_triangle" in codes(result)


def test_centers_foot_arcs_and_named_circle_consistency():
    source = """
    (param (A B C) triangle)
    (define O point (circumcenter A B C))
    (define H point (orthocenter A B C))
    (define I point (incenter A B C))
    (define J point (excenter A B C))
    (define K point (centroid A B C))
    (define F point (foot C (line A B)))
    (define U point (amidp-opp A B C))
    (define V point (amidp-same A B C))
    (define omega circle (incircle A B C))
    (define Gamma circle (circumcircle A B C))
    (assert (right A C B))
    """
    data = witness(
        {
            "A": [0, 0],
            "B": [4, 0],
            "C": [0, 3],
            "O": [2, "1.5"],
            "H": [0, 0],
            "I": [1, 1],
            "J": [6, 6],
            "K": ["1.333333333333333333333", 1],
            "F": [0, 0],
            "U": [2, -1],
            "V": [2, 4],
        },
        circles={
            "omega": {"center": [1, 1], "radius": 1},
            "Gamma": {"center": [2, "1.5"], "radius": "2.5"},
        },
    )
    # Right angle is at A, not C: this must fail only the intentionally broken assertion.
    result = check_configuration(source, data)
    assert [clause["status"] for clause in result["assumptions"][:-1]] == ["passed"] * 11
    assert not result["valid"]
    assert check_configuration(source.replace("(right A C B)", "(right B A C)"), data)["valid"]


@pytest.mark.parametrize("factor", ["1e-200", "1", "1e200"])
def test_translation_rotation_uniform_scale_preserve_acceptance(factor):
    ctx = mpmath.mp.clone()
    ctx.dps = 90
    scale = ctx.mpf(factor)
    source = "(param (A B C) triangle) (define M point (midp A B)) (assert (right B A C))"
    points = {"A": (0, 0), "B": (4, 0), "C": (0, 3), "M": (2, 0)}
    transformed = {
        name: [str(scale * (-ctx.mpf(y) + 7)), str(scale * (ctx.mpf(x) - 13))]
        for name, (x, y) in points.items()
    }
    result = check_configuration(source, witness(transformed))
    assert result["valid"], result
    transformed["M"][0] = str(ctx.mpf(transformed["M"][0]) + scale / 10)
    assert not check_configuration(source, witness(transformed))["valid"]


def test_closed_and_open_segment_semantics_and_negation():
    base = "(param A point) (param B point) "
    data = witness({"A": [0, 0], "B": [1, 0], "P": [0, 0]})
    assert not check_configuration(base + "(param P point (on-seg A B))", data)["valid"]
    assert check_configuration(base + "(param P point) (assert (on-seg P A B))", data)["valid"]
    data["points"]["P"] = ["0.01", 0]
    assert check_configuration(base + "(param P point (on-seg A B))", data)["valid"]
    # No artificial 20% central segment restriction.
    assert check_configuration(base + "(param P point) (assert (on-seg P A B))", data)["valid"]
    data["points"]["P"] = [2, 0]
    assert check_configuration(base + "(param P point) (assert (not (on-seg P A B)))", data)[
        "valid"
    ]
    data["points"]["P"] = ["-1e-8", 0]
    result = check_configuration(base + "(param P point) (assert (not (on-seg P A B)))", data)
    assert not result["valid"] and result["status"] == "unresolved"


def test_strict_constraints_are_not_equality_tolerances():
    data = witness({"A": [0, 0]})
    for source, expected in [
        ("(assert (gt 1 1))", "failed"),
        ("(assert (gt 1.00000001 1))", "unresolved"),
        ("(assert (gte 1 1))", "passed"),
        ("(assert (lt 1 2))", "passed"),
        ("(assert (not (= 1.00000001 1)))", "unresolved"),
    ]:
        result = check_configuration("(param A point)" + source, data)
        assert result["status"] == expected


def test_opposite_ray_origin_and_direction():
    source = "(param A point) (param B point) (param P point (on-ray-opp A B))"
    data = witness({"A": [0, 0], "B": [1, 0], "P": [-2, 0]})
    assert check_configuration(source, data)["valid"]
    for bad in [[0, 0], [2, 0], [-2, 1]]:
        data["points"]["P"] = bad
        assert not check_configuration(source, data)["valid"]


def test_convex_polygon_order_and_strict_inside():
    source = "(param (A B C D) polygon) (param P point (in-poly A B C D))"
    data = witness({"A": [0, 0], "B": [2, 0], "C": [2, 2], "D": [0, 2], "P": [1, 1]})
    assert check_configuration(source, data)["valid"]
    reflected = copy.deepcopy(data)
    for p in reflected["points"].values():
        p[1] = -p[1]
    assert check_configuration(source, reflected)["valid"]
    data["points"]["P"] = [0, 1]
    assert not check_configuration(source, data)["valid"]
    data["points"]["P"] = [1, 1]
    data["points"]["B"], data["points"]["C"] = data["points"]["C"], data["points"]["B"]
    assert not check_configuration(source, data)["valid"]  # bow-tie order


def test_acute_triangle_checks_all_angles_not_sampler_shape_limits():
    source = "(param (A B C) acute-tri)"
    assert check_configuration(source, witness({"A": [0, 0], "B": [4, 0], "C": [2, 3]}))["valid"]
    assert not check_configuration(source, witness({"A": [0, 0], "B": [4, 0], "C": [2, 1]}))[
        "valid"
    ]


def test_named_right_vertex_and_equilateral():
    source = "(param (A B C) (right-tri C))"
    data = witness({"A": [3, 0], "B": [0, 4], "C": [0, 0]})
    assert check_configuration(source, data)["valid"]
    assert not check_configuration(source.replace("right-tri C", "right-tri A"), data)["valid"]
    data = witness({"A": [0, 0], "B": [2, 0], "C": [1, "1.732050807568877293527"]})
    assert check_configuration("(param (A B C) equi-tri)", data)["valid"]


def intersection_fixture(selector="rs-arbitrary"):
    source = (
        "(param A point) (param B point) (param O circle) "
        f"(define X point (inter-lc (line A B) O {selector}))"
    )
    data = witness(
        {"A": [-2, 0], "B": [2, 0], "X": [1, 0]}, circles={"O": {"center": [0, 0], "radius": 1}}
    )
    return source, data


def test_arbitrary_named_intersection_accepts_both_real_branches():
    source, data = intersection_fixture()
    assert check_configuration(source, data)["valid"]
    data["points"]["X"] = [-1, 0]
    assert check_configuration(source, data)["valid"]
    data["points"]["X"] = [0, 0]
    assert not check_configuration(source, data)["valid"]


def test_nonintersections_and_tangent_are_not_fabricated():
    source, data = intersection_fixture()
    for point in data["points"].values():
        point[1] = 1
    data["points"]["X"] = [0, 1]
    assert check_configuration(source, data)["valid"]
    for point in data["points"].values():
        point[1] = 2
    result = check_configuration(source, data)
    assert not result["valid"] and "no_real_intersection" in codes(result)


def test_exclude_selector_checks_excluded_point_is_a_root():
    source, data = intersection_fixture("(rs-neq A)")
    data["points"]["A"] = [-1, 0]
    assert check_configuration(source, data)["valid"]
    data["points"]["X"] = [-1, 0]
    assert not check_configuration(source, data)["valid"]
    data["points"]["A"] = [-2, 0]
    result = check_configuration(source, data)
    assert not result["valid"] and "ambiguous_exclusion" in codes(result)


def test_nearest_selector_and_tie_are_not_arbitrarily_chosen():
    source, data = intersection_fixture("(rs-closer-to-p B)")
    assert check_configuration(source, data)["valid"]
    data["points"]["B"] = [0, 0]
    result = check_configuration(source, data)
    assert not result["valid"] and result["status"] == "unresolved"
    assert "selector_tie" in codes(result)


def test_opposite_side_selector():
    source = """
    (param A point) (param B point) (param R point) (param S point)
    (param O circle)
    (define X point (inter-lc (line A B) O (rs-opp-sides B (line R S))))
    """
    data = witness(
        {"A": [-2, 0], "B": [2, 0], "R": [0, -1], "S": [0, 1], "X": [-1, 0]},
        circles={"O": {"center": [0, 0], "radius": 1}},
    )
    assert check_configuration(source, data)["valid"]
    data["points"]["X"] = [1, 0]
    assert not check_configuration(source, data)["valid"]


def test_unnamed_multivalued_expression_needs_checked_choice():
    source, data = intersection_fixture()
    source = (
        source[: source.index("(define")]
        + "(assert (on-circ (inter-lc (line A B) O rs-arbitrary) O))"
    )
    data["points"].pop("X")
    result = check_configuration(source, data)
    assert not result["valid"] and "missing_unnamed_branch" in codes(result)
    data["choices"] = {"commands/3/condition/0": [1, 0]}
    assert check_configuration(source, data)["valid"]
    data["choices"]["commands/3/condition/0"] = ["0.5", 0]
    result = check_configuration(source, data)
    assert not result["valid"] and "invalid_explicit_choice" in codes(result)


def test_circle_circle_branches_and_concentric_rejection():
    source = "(param U circle) (param V circle) (define X point (inter-cc U V rs-arbitrary))"
    data = witness(
        {"X": [3, 4]},
        circles={"U": {"center": [0, 0], "radius": 5}, "V": {"center": [6, 0], "radius": 5}},
    )
    assert check_configuration(source, data)["valid"]
    data["points"]["X"] = [3, -4]
    assert check_configuration(source, data)["valid"]
    data["circles"]["V"]["center"] = [0, 0]
    result = check_configuration(source, data)
    assert not result["valid"] and "concentric_circles" in codes(result)


def test_minor_arc_order_and_boundary():
    source = "(param O circle) (param A point) (param B point) (param P point (on-minor-arc O A B))"
    data = witness(
        {"A": [1, 0], "B": [0, 1], "P": ["0.6", "0.8"]},
        circles={"O": {"center": [0, 0], "radius": 1}},
    )
    assert check_configuration(source, data)["valid"]
    data["points"]["P"] = ["-0.6", "-0.8"]
    assert not check_configuration(source, data)["valid"]
    data["points"]["P"] = [1, 0]
    assert not check_configuration(source, data)["valid"]
    data["points"]["B"] = [-1, 0]
    assert not check_configuration(source, data)["valid"]


def test_line_reflection_parallelism_perpendicularity_and_sign_normalization():
    source = """
    (param A point) (param B point) (param C point)
    (define l line (line A B))
    (define mirror line (line A C))
    (define reflected line (reflect-ll l mirror))
    (assert (eq l reflected))
    (assert (perp l mirror))
    """
    data = witness(
        {"A": [3, 4], "B": [5, 4], "C": [3, 6]},
        lines={"l": [0, 2, -8], "mirror": [1, 0, -3], "reflected": [0, -5, 20]},
    )
    assert check_configuration(source, data)["valid"]
    data["lines"]["reflected"] = [0, 1, -5]
    assert not check_configuration(source, data)["valid"]


def test_equal_lines_and_infinite_intersection_are_different_conditions():
    source = "(param l line) (param m line) (define X point (inter-ll l m))"
    data = witness({"X": [0, 0]}, lines={"l": [1, 0, 0], "m": [2, 0, 0]})
    assert not check_configuration(source, data)["valid"]


def test_tangent_circles_do_not_include_coincident_or_zero_radius():
    source = "(param U circle) (param V circle) (assert (tangent-cc U V))"
    data = witness(
        circles={"U": {"center": [0, 0], "radius": 2}, "V": {"center": [3, 0], "radius": 1}}
    )
    assert check_configuration(source, data)["valid"]
    data["circles"]["V"] = {"center": [1, 0], "radius": 1}
    assert check_configuration(source, data)["valid"]
    data["circles"]["V"] = copy.deepcopy(data["circles"]["U"])
    assert not check_configuration(source, data)["valid"]


def test_internal_bisector_ray_not_external_line():
    source = "(param (A B C) triangle) (param X point) (assert (i-bisector X B A C))"
    data = witness({"A": [0, 0], "B": [3, 0], "C": [0, 4], "X": [1, 1]})
    assert check_configuration(source, data)["valid"]
    data["points"]["X"] = [-1, -1]
    assert not check_configuration(source, data)["valid"]


def test_scalar_equations_scale_factors_and_decimal_source():
    source = "(param A point) (assert (= (mul FACTOR 2) (mul FACTOR 3)))"
    for factor in ["1e-200", "1", "1e200"]:
        result = check_configuration(source.replace("FACTOR", factor), witness({"A": [0, 0]}))
        assert not result["valid"]
    result = check_configuration(
        "(param A point) (assert (> 1.0000000000000000001 1))",
        witness({"A": [0, 0]}),
        tolerance="1e-30",
    )
    assert result["valid"]


def test_gmb_adapter_uses_actual_line_offset_sign_and_not_losses():
    model = {
        "named_points": {"A": {"x": 2, "y": 3}},
        "named_lines": {"l": {"n": {"x": 0, "y": 1}, "r": "3.0000000000000000001"}},
        "named_circles": {"O": {"center": {"x": 0, "y": 0}, "radius": 1}},
        "ndgs": {"lie": 0},
        "goals": {"lie": True},
    }
    converted = witness_from_gmb_model(model)
    assert converted["lines"]["l"] == [0, 1, "-3.0000000000000000001"]
    assert converted["points"]["A"] == [2, 3]
    assert set(converted) == {"points", "lines", "circles"}
    result = check_configuration(
        "(param A point) (param l line) (param O circle) (assert (on-line A l))", converted
    )
    assert result["valid"]


def test_private_precision_and_no_solver_geometry_imports():
    before = mpmath.mp.dps
    assert check_configuration("(param A point)", witness({"A": [0, 0]}), dps=120)["valid"]
    assert mpmath.mp.dps == before
    for filename in ["checker.py", "checker_geometry.py"]:
        tree = ast.parse((Path("benchmarks/gmb_comparison") / filename).read_text())
        imported = [
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ]
        assert not any(
            name.startswith("geosolver") or name.startswith("tensorflow") for name in imported
        )
    assert not CHECKER_POLICY["independent_existence_proof"]


def test_parallel_perpendicular_bisector_and_line_intersection_constructions():
    source = """
    (param (A B C) triangle)
    (define P point (inter-ll (para-at C (line A B)) (para-at B (line A C))))
    (define M point (midp A B))
    (define Q point (midp-from M A))
    (define l line (perp-at C (line A B)))
    (define m line (perp-bis A B))
    (assert (eq Q B))
    (assert (para l m))
    (assert (on-line M m))
    (eval (concur (line A P) (line B C) (line M (midp C P))))
    """
    data = witness(
        {"A": [0, 0], "B": [4, 0], "C": [0, 3], "P": [4, 3], "M": [2, 0], "Q": [4, 0]},
        lines={"l": [1, 0, 0], "m": [1, 0, -2]},
    )
    result = check_configuration(source, data)
    assert result["valid"] and result["goals_valid"]


def test_circle_constructors_cyclic_and_numeric_measures():
    source = """
    (param (A B C D) polygon)
    (define X circle (diam A B))
    (define Y circle (coa A B))
    (define M point (origin X))
    (assert (cycl A B C D))
    (assert (= (radius X) (div (dist A B) 2)))
    (assert (= (diam X) (dist A B)))
    (assert (= (area A B D) 6))
    (assert (= (uangle B A D) (div pi 2)))
    (assert (eq-ratio A B A D B A D A))
    (assert (midp M A B))
    (assert (right-tri A B D))
    """
    data = witness(
        {"A": [0, 0], "B": [4, 0], "C": [4, 3], "D": [0, 3], "M": [2, 0]},
        circles={"X": {"center": [2, 0], "radius": 2}, "Y": {"center": [0, 0], "radius": 4}},
    )
    result = check_configuration(source, data)
    assert result["valid"], result
    data["points"]["C"] = [4, 4]
    assert not check_configuration(source, data)["valid"]


def test_absolute_scalar_lengths_are_not_changed_by_internal_normalization():
    source = """
    (param A point) (param B point)
    (define O circle (coa A B))
    (assert (= (dist A B) 4)) (assert (= (radius O) 4))
    """
    data = witness({"A": [2, 3], "B": [6, 3]}, circles={"O": {"center": [2, 3], "radius": 4}})
    assert check_configuration(source, data)["valid"]
    assert not check_configuration(source.replace("B) 4", "B) 1"), data)["valid"]


def test_tangent_parameterization_and_same_side_strictness():
    source = """
    (param A point) (param B point)
    (param O circle)
    (param l line (tangent-lc O))
    (param U circle (tangent-cl l))
    (assert (tangent-lc l U))
    (assert (same-side A B l))
    """
    data = witness(
        {"A": [0, 0], "B": [1, 0]},
        lines={"l": [0, 1, -2]},
        circles={"O": {"center": [0, 0], "radius": 2}, "U": {"center": [5, 0], "radius": 2}},
    )
    assert check_configuration(source, data)["valid"]
    data["points"]["B"] = [1, 2]
    assert not check_configuration(source, data)["valid"]


@pytest.mark.parametrize(
    "formula,valid",
    [
        ("(= (sqrt 9) 3)", True),
        ("(= (neg 1) (sub 1 2))", True),
        ("(= (pow 2 3) 8)", True),
        ("(= (div 1 0) 0)", False),
        ("(= (sqrt -1) 0)", False),
        ("(= (pow -1 0.5) 1)", False),
    ],
)
def test_scalar_operations_and_domains(formula, valid):
    result = check_configuration("(param A point) (assert " + formula + ")", witness({"A": [0, 0]}))
    assert result["valid"] == valid


def test_assertion_center_uses_first_point_as_candidate():
    source = """
    (param (A B C) triangle) (param I point) (param O point) (param H point)
    (assert (incenter I A B C)) (assert (circumcenter O A B C))
    (assert (orthocenter H A B C))
    """
    data = witness(
        {"A": [0, 0], "B": [4, 0], "C": [0, 3], "I": [1, 1], "O": [2, "1.5"], "H": [0, 0]}
    )
    assert check_configuration(source, data)["valid"]
    data["points"]["I"] = [6, 6]
    assert not check_configuration(source, data)["valid"]  # excenter is not incenter.


def test_reflected_point_and_on_line_param():
    source = """
    (param A point) (param B point) (param P point (on-line (line A B)))
    (define Q point (reflect-pl A (perp-bis A B)))
    (assert (eq Q B))
    """
    data = witness({"A": [0, 0], "B": [4, 0], "P": [-10, 0], "Q": [4, 0]})
    assert check_configuration(source, data)["valid"]


def test_unrecognized_branch_paths_do_not_silently_pass():
    source, data = intersection_fixture()
    data["choices"] = {"misspelled/path": [1, 0]}
    result = check_configuration(source, data)
    assert not result["valid"] and "unused_branch_choice" in codes(result)


def test_identical_expression_keeps_one_arbitrary_branch():
    source, data = intersection_fixture()
    source += "(define Y point (inter-lc (line A B) O rs-arbitrary))"
    data["points"]["Y"] = [-1, 0]
    assert not check_configuration(source, data)["valid"]
    data["points"]["Y"] = [1, 0]
    assert check_configuration(source, data)["valid"]


def test_gmb_sequence_adapter_does_not_negate_the_normal():
    converted = witness_from_gmb_model(
        {
            "named_points": {"P": [0, -3]},
            "named_lines": {"l": [[0, -1], "+3.0000000000000000001"]},
            "named_circles": {"C": [[0, 0], 2]},
        }
    )
    assert converted["lines"]["l"] == [0, -1, "-3.0000000000000000001"]
    assert check_configuration(
        "(param P point) (param l line) (param C circle) (assert (on-line P l))", converted
    )["valid"]


@pytest.mark.parametrize("factor", ["1e-200", "1", "1e200"])
def test_intersection_branch_and_line_circle_normalization_under_similarity(factor):
    ctx = mpmath.mp.clone()
    ctx.dps = 90
    scale = ctx.mpf(factor)
    co, si = ctx.mpf(3) / 5, ctx.mpf(4) / 5
    translation = [7 * scale, -13 * scale]

    def transform(point):
        x, y = map(ctx.mpf, point)
        return [
            str(scale * (co * x - si * y) + translation[0]),
            str(scale * (si * x + co * y) + translation[1]),
        ]

    source = """
    (param A point) (param B point) (param O circle)
    (define l line (line A B))
    (define X point (inter-lc l O (rs-closer-to-p B)))
    (assert (on-circ X O))
    """
    normal = [-si, co]
    line = [
        str(normal[0]),
        str(normal[1]),
        str(-sum(n * t for n, t in zip(normal, translation, strict=True))),
    ]
    data = witness(
        {"A": transform([-2, 0]), "B": transform([2, 0]), "X": transform([1, 0])},
        lines={"l": line},
        circles={"O": {"center": transform([0, 0]), "radius": factor}},
    )
    result = check_configuration(source, data)
    assert result["valid"], result
    data["points"]["X"] = transform([-1, 0])
    assert not check_configuration(source, data)["valid"]


def test_circle_circle_nonintersection_and_tangent_singleton():
    source = "(param U circle) (param V circle) (define X point (inter-cc U V rs-arbitrary))"
    data = witness(
        {"X": [5, 0]},
        circles={"U": {"center": [0, 0], "radius": 5}, "V": {"center": [10, 0], "radius": 5}},
    )
    assert check_configuration(source, data)["valid"]
    data["circles"]["V"]["center"] = [11, 0]
    result = check_configuration(source, data)
    assert not result["valid"] and "no_real_intersection" in codes(result)


@pytest.mark.parametrize("factor", ["1e-200", "1", "1e200"])
def test_long_line_must_not_dilute_intersection_circle_membership(factor):
    ctx = mpmath.mp.clone()
    ctx.dps = 90
    scale = ctx.mpf(factor)
    source, data = intersection_fixture()
    data["points"] = {
        "A": [str(-scale * 10**12), 0],
        "B": [str(scale * 10**12), 0],
        "X": [str(scale * 100), 0],
    }
    data["circles"]["O"]["radius"] = factor
    result = check_configuration(source, data)
    assert not result["valid"] and "invalid_intersection_witness" in codes(result)
    # Adding the redundant mathematical membership cannot change acceptance.
    assert not check_configuration(source + "(assert (on-circ X O))", data)["valid"]
    data["points"]["X"] = [factor, 0]
    assert check_configuration(source, data)["valid"]
    # A point close to the circle but noticeably off the line must also fail:
    # radial error is quadratic in its perpendicular displacement.
    data["points"]["X"] = [factor, str(scale * ctx.mpf("1e-4"))]
    assert not check_configuration(source, data)["valid"]


def test_named_line_keeps_its_defining_scale_under_unrelated_long_baseline():
    source = "(param D point) (param E point) (param A point) (param B point) (param P point)"
    data = witness(
        {"D": [0, 0], "E": ["1e12", 0], "A": [0, 1], "B": [1, 1], "P": [0, 2]},
        lines={"l": [0, 1, -1]},
    )
    inline = check_configuration(source + "(assert (on-line P (line A B)))", data)
    named = check_configuration(source + "(define l line (line A B)) (assert (on-line P l))", data)
    assert not inline["valid"] and not named["valid"]
    assert (
        inline["assumptions"][-1]["checks"][0]["error"]
        == named["assumptions"][-1]["checks"][0]["error"]
    )
    data["points"]["P"] = ["0.5", 1]
    assert check_configuration(source + "(define l line (line A B)) (assert (on-line P l))", data)[
        "valid"
    ]


@pytest.mark.parametrize("factor", ["1e-200", "1", "1e200"])
@pytest.mark.parametrize("operation", ["foot", "reflect-pl", "inter-ll"])
def test_point_construction_local_conditions_cannot_be_diluted(operation, factor):
    ctx = mpmath.mp.clone()
    ctx.dps = 90
    scale = ctx.mpf(factor)
    source = "(param A point) (param B point) (param P point) "
    if operation == "inter-ll":
        source += "(define F point (inter-ll (line A B) (line A P)))"
        false_point, correct_point = [100, 100], [0, 0]
    else:
        source += f"(define F point ({operation} P (line A B)))"
        false_point = [0, 100] if operation == "foot" else [100, -(10**12)]
        correct_point = [0, 0] if operation == "foot" else [0, -(10**12)]
    data = witness(
        {
            name: [str(scale * x), str(scale * y)]
            for name, (x, y) in {
                "A": [0, 0],
                "B": [1, 0],
                "P": [0, 10**12],
                "F": false_point,
            }.items()
        }
    )
    assert not check_configuration(source, data)["valid"]
    if operation != "reflect-pl":
        assert not check_configuration(source + "(assert (on-line F (line A B)))", data)["valid"]
    data["points"]["F"] = [str(scale * x) for x in correct_point]
    assert check_configuration(source, data)["valid"]
    if operation == "foot":
        data["points"]["F"] = [str(scale * 100), 0]
        assert not check_configuration(source, data)["valid"]


@pytest.mark.parametrize("factor", ["1e-200", "1", "1e200"])
@pytest.mark.parametrize("swap", [False, True])
def test_tangency_uses_the_smaller_circle_feature_scale(factor, swap):
    ctx = mpmath.mp.clone()
    ctx.dps = 90
    scale = ctx.mpf(factor)
    large = {"center": [0, 0], "radius": str(scale * 10**12)}
    small = {"center": [str(scale * 10**12), 0], "radius": factor}
    source = "(param U circle) (param V circle) (assert (tangent-cc U V))"
    names = ["V", "U"] if swap else ["U", "V"]
    data = witness(circles=dict(zip(names, [large, small], strict=True)))
    assert not check_configuration(source, data)["valid"]
    small["center"] = [str(scale * (10**12 + 1)), 0]
    assert check_configuration(source, data)["valid"]
    small["center"] = [str(scale * (10**12 - 1)), 0]
    assert check_configuration(source, data)["valid"]


@pytest.mark.parametrize("angle_error,expected", [("1e-8", True), ("1e-4", False)])
def test_line_consistency_does_not_depend_on_an_unrelated_chart_origin(angle_error, expected):
    source = "(param A point) (param B point) (define l line (line A B))"
    data = witness({"A": [0, 0], "B": [1, 0]}, lines={"l": [angle_error, 1, 0]})
    assert check_configuration(source, data)["valid"] == expected
    shifted = copy.deepcopy(data)
    shifted["points"].update({"D": ["1e12", 0], "E": ["1000000000001", 0]})
    other_chart = "(param D point) (param E point) " + source
    assert check_configuration(other_chart, shifted)["valid"] == expected


@pytest.mark.parametrize("construction", ["para-at", "perp-at"])
def test_line_offset_checks_use_local_constructing_point_not_distant_origin(construction):
    source = f"""
    (param A point) (param B point) (param P point)
    (define l line ({construction} P (line A B)))
    """
    actual = [0, 1, "-999999999900"] if construction == "para-at" else [1, 0, -100]
    correct = [0, 1, "-1000000000000"] if construction == "para-at" else [1, 0, 0]
    data = witness({"A": [0, 0], "B": [1, 0], "P": [0, "1e12"]}, lines={"l": actual})
    assert not check_configuration(source, data)["valid"]
    data["lines"]["l"] = correct
    assert check_configuration(source, data)["valid"]


def test_point_on_small_circle_cannot_pass_incidence_with_distant_line_endpoints():
    source = """
    (param A point) (param B point) (param O circle)
    (param P point (on-circ O)) (assert (on-line P (line A B)))
    """
    data = witness(
        {"A": ["-1e12", 0], "B": ["1e12", 0], "P": [0, 1]},
        circles={"O": {"center": [0, 0], "radius": 1}},
    )
    assert not check_configuration(source, data)["valid"]
    data["points"]["P"] = [1, 0]
    assert check_configuration(source, data)["valid"]


@pytest.mark.parametrize(
    "operation",
    [
        "circumcenter",
        "orthocenter",
        "centroid",
        "incenter",
        "excenter",
        "amidp-opp",
        "amidp-same",
        "midp",
        "midp-from",
    ],
)
@pytest.mark.parametrize("distant_origin", [False, True])
def test_all_point_construction_scales_survive_long_or_unrelated_features(
    operation, distant_origin
):
    ctx = mpmath.mp.clone()
    ctx.dps = 90
    length = ctx.mpf(10**5)
    diagonal = ctx.sqrt(length**2 + 1)
    radius = diagonal / 2
    inc = (length + 1 - diagonal) / 2
    exc = (length + 1 + diagonal) / 2
    expected = {
        "circumcenter": [length / 2, ctx.mpf("0.5")],
        "orthocenter": [0, 0],
        "centroid": [length / 3, ctx.mpf(1) / 3],
        "incenter": [inc, inc],
        "excenter": [exc, exc],
        "amidp-opp": [length / 2, ctx.mpf("0.5") - radius],
        "amidp-same": [length / 2, ctx.mpf("0.5") + radius],
        "midp": [length / 2, 0],
        "midp-from": [-length, 0],
    }[operation]
    arguments = "A B" if operation in {"midp", "midp-from"} else "A B C"
    source = f"(param (A B C) triangle) (define X point ({operation} {arguments}))"
    data = witness(
        {"A": [0, 0], "B": [str(length), 0], "C": [0, 1], "X": [str(v) for v in expected]}
    )
    if distant_origin:
        source = "(param D point) (param E point) " + source
        data["points"].update({"D": ["1e12", 0], "E": ["1000000000001", 0]})
    result = check_configuration(source, data)
    assert result["valid"], result
    data["points"]["X"][0] = str(ctx.mpf(data["points"]["X"][0]) + ctx.mpf("0.001"))
    assert not check_configuration(source, data)["valid"]


def test_large_circumcircle_definition_keeps_small_triangle_feature_scale():
    ctx = mpmath.mp.clone()
    ctx.dps = 90
    length = ctx.mpf(10**5)
    radius = ctx.sqrt(length**2 + 1) / 2
    # Free declarations also have to pick up the triangle's own small side,
    # not only triangles declared by the joint parameterization.
    source = "(param A point) (param B point) (param C point) (define O circle (circ A B C))"
    data = witness(
        {"A": [0, 0], "B": [str(length), 0], "C": [0, 1]},
        circles={"O": {"center": [str(length / 2), "0.5"], "radius": str(radius)}},
    )
    assert check_configuration(source, data)["valid"]
    data["circles"]["O"]["center"][0] = str(length / 2 + ctx.mpf("0.001"))
    assert not check_configuration(source, data)["valid"]


def test_small_feature_line_incidence_matches_inline_named_and_collinear_forms():
    source = """
    (param A point) (param B point) (param O circle) (param P point (on-circ O))
    """
    data = witness(
        {"A": ["-1e12", 0], "B": ["1e12", 0], "P": [0, 1]},
        lines={"l": [0, 1, 0]},
        circles={"O": {"center": [0, 0], "radius": 1}},
    )
    for clause in [
        "(assert (coll P A B))",
        "(assert (on-line P (line A B)))",
        "(define l line (line A B)) (assert (on-line P l))",
        "(assert (on-seg P A B))",
    ]:
        assert not check_configuration(source + clause, data)["valid"]


def test_reflection_uses_actual_line_equation_not_approximately_inherited_anchor():
    source = """
    (param A point) (param B point) (param C point) (param D point)
    (define l line (line A B)) (define m line (line C D))
    (define r line (reflect-ll l m))
    """
    data = witness(
        {"A": [0, 0], "B": ["1e12", 0], "C": [0, 0], "D": [0, 1]},
        lines={"l": [0, 1, -100], "m": [1, 0, 0], "r": [0, 1, 0]},
    )
    assert not check_configuration(source, data)["valid"]
    data["lines"]["r"] = [0, 1, -100]
    result = check_configuration(source, data)
    assert result["valid"], result
    assert check_configuration(source + "(assert (eq l r))", data)["valid"]


def test_equal_reported_lines_remain_equal_with_distinct_reference_anchors():
    source = """
    (param A point) (param B point) (param P point) (param Q point)
    (define l line (line A B)) (define m line (line P Q)) (assert (eq l m))
    """
    data = witness(
        {"A": [0, 0], "B": ["1e12", 0], "P": [0, 100], "Q": [1, 100]},
        lines={"l": [0, 1, -100], "m": [0, 1, -100]},
    )
    assert check_configuration(source, data)["valid"]


def test_error_metadata_cannot_change_physical_geometry_constructions():
    g = geometry.Geometry("1e-9", 100)
    p = g.point([2, 3])
    a, b, c = g.point([0, 0]), g.point([4, 0]), g.point([0, 3])
    line = g.coefficients([3, 4, -7])
    mirror = g.coefficients([4, -3, -2])
    circle = g.circle(g.point([0, 0]), g.scalar(5))
    other_circle = g.circle(g.point([6, 0]), g.scalar(5))

    def changed(value):
        if isinstance(value, geometry.Point):
            return geometry.Point(value.x, value.y, g.scalar("1e-30"))
        if isinstance(value, geometry.Line):
            return geometry.Line(value.n, value.c, g.scalar("1e30"), g.point(["1e50", "-1e50"]))
        return geometry.Circle(value.center, value.radius, g.scalar("1e-30"))

    def physical(value):
        if isinstance(value, geometry.Point):
            return value.x, value.y
        if isinstance(value, geometry.Line):
            return value.n.x, value.n.y, value.c
        if isinstance(value, geometry.Circle):
            return value.center.x, value.center.y, value.radius
        return tuple(item for child in value for item in physical(child))

    operations = [
        (g.through, [a, b]),
        (g.parallel_at, [p, line]),
        (g.perpendicular_at, [p, line]),
        (g.foot, [p, line]),
        (g.reflect_point, [p, line]),
        (g.reflect_line, [line, mirror]),
        (g.intersect_lines, [line, mirror]),
        (g.bisector, [a, b, c]),
        (g.circumcenter, [a, b, c]),
        (g.arc_midpoint, [a, b, c]),
        (g.line_circle, [line, circle]),
        (g.circle_circle, [circle, other_circle]),
    ]
    for kind in ["circumcenter", "orthocenter", "incenter", "excenter", "centroid"]:
        operations.append((lambda *pts, k=kind: g.center(k, *pts), [a, b, c]))
    for kind in ["circ", "circumcircle", "incircle", "excircle"]:
        operations.append((lambda *pts, k=kind: g.triangle_circle(k, *pts), [a, b, c]))
    for operation, args in operations:
        original = physical(operation(*args))
        metadata_changed = physical(operation(*(changed(arg) for arg in args)))
        assert original == metadata_changed, operation
