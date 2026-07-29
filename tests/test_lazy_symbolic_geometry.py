from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest
from sympy import Float, Symbol

from geotarget.lazy_symbolic_geometry import (
    LazyCircle,
    LazyCompilationLimits,
    LazyGeometryState,
    build_lazy_geometry_context,
    expand_bundle_symbolically,
    lazy_geometry_manifest,
    try_expand_bundle_symbolically,
)


def _install_frozen_geosolver() -> None:
    runtime = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    path = str(runtime / "geosolver/src")
    if path not in sys.path:
        sys.path.insert(0, path)


def _bundle(problem: dict):
    _install_frozen_geosolver()
    from geosolver._internal.pipeline.problem.load_problem_bundle import (
        load_problem_bundle,
    )

    return load_problem_bundle(problem)


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def test_symbolic_circle_defers_radius_validation() -> None:
    radius = Symbol("radius", real=True)
    context, state = build_lazy_geometry_context(LazyGeometryState())

    circle = context["Circle"](context["Point"](0, 0), radius)

    assert isinstance(circle, LazyCircle)
    assert circle.radius == radius
    assert [(item.kind, item.expression, item.source) for item in state.validations] == [
        ("nonnegative", radius, "Circle.radius")
    ]


def test_unseen_composition_expands_and_matches_reference_bits() -> None:
    problem = {
        "task": "solve",
        "id": "unseen-composition-do-not-route-by-id",
        "variables": {"names": ["x", "y", "t"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(x, y)"},
            {"name": "omega", "expr": "CircleThroughPoint(A, B)"},
            {"name": "P", "expr": "PointOnCircle(omega, t)"},
            {"name": "ell", "expr": "Line(A, B)"},
            {"name": "F", "expr": "FootOfPerpendicular(ell, P)"},
        ],
        # This unseen composition deliberately exercises lazy Circle/Line and
        # projection construction while keeping a source-boundary identity as
        # its residual.  More aggressive global symbolic cancellation is only
        # shadow-qualified and is not asserted as production-safe here.
        "constraints": [{"def": "Radius(omega)", "value": "Distance(A, B)"}],
        "guards": [],
        "answer": "Distance(A, P)",
        "post_process": "",
    }
    bundle = _bundle(problem)
    expansion = expand_bundle_symbolically(bundle)
    assert expansion.semantic_abi.startswith("geotarget.lazy-symbolic-geometry/")
    assert expansion.validations

    from geosolver._internal.pipeline.evaluator.evaluate_float_residual import (
        evaluate_float_residual,
    )

    for values in ([3.0, 4.0, 0.125], [-2.5, 7.0, 0.333], [1e-6, -9.0, 0.75]):
        substitutions = {
            symbol: Float(value) for symbol, value in zip(expansion.symbols, values, strict=True)
        }
        observed = [
            float(left.evalf(subs=substitutions)) - float(right.evalf(subs=substitutions))
            for left, right in expansion.sides
        ]
        expected = evaluate_float_residual(bundle=bundle, values=list(values))
        assert [_bits(value) for value in observed] == [
            _bits(value) for value in expected.residual_vector
        ]


def test_intersection_fails_closed_for_the_whole_problem() -> None:
    problem = {
        "task": "solve",
        "id": "generic-intersection-fallback",
        "variables": {"names": ["x"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(1, x)"},
            {"name": "C", "expr": "Point(0, 1)"},
            {"name": "D", "expr": "Point(1, 0)"},
            {
                "name": "P",
                "expr": "Intersect(Line(A, B), Line(C, D), exclude=A)",
            },
        ],
        "constraints": [{"def": "Distance(A, P)", "value": 1}],
        "guards": [],
        "answer": "Distance(A, P)",
        "post_process": "",
    }

    result = try_expand_bundle_symbolically(_bundle(problem))

    assert not result.supported
    assert result.expansion is None
    assert "exclude selection requires the selector-trace semantic ABI" in str(
        result.fallback_reason
    )


@pytest.mark.parametrize(
    ("intersection", "values"),
    [
        ("Intersect(Line(A, B), Line(C, D))", [2.0]),
        ("Intersect(ell, omega, n=1)", [3.0]),
        ("Intersect(omega, ell, n=2)", [4.0]),
        ("Intersect(ell, omega, near=R)", [3.0]),
        ("Intersect(ell, omega, far=R)", [4.0]),
        ("Intersect(omega, gamma, n=1)", [6.0]),
    ],
)
def test_unseen_intersection_selectors_match_reference_bits(
    intersection: str, values: list[float]
) -> None:
    line_line = "Line(A, B), Line(C, D)" in intersection
    construction = (
        [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(1, x)"},
            {"name": "C", "expr": "Point(0, 1)"},
            {"name": "D", "expr": "Point(1, 0)"},
        ]
        if line_line
        else [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "omega", "expr": "Circle(O, 5)"},
            {"name": "A", "expr": "Point(-10, x)"},
            {"name": "B", "expr": "Point(10, x)"},
            {"name": "ell", "expr": "Line(A, B)"},
            {"name": "R", "expr": "Point(9, 0)"},
            {"name": "Q", "expr": "Point(x, 0)"},
            {"name": "gamma", "expr": "Circle(Q, 5)"},
        ]
    )
    construction.append({"name": "P", "expr": intersection})
    problem = {
        "task": "solve",
        "id": "synthetic-selector-not-a-routing-key",
        "variables": {"names": ["x"]},
        "construction": construction,
        "constraints": [
            {"def": "P.x", "value": 0},
            {"def": "P.y", "value": 0},
        ],
        "guards": [],
        "answer": "Distance(P, Point(0, 0))",
        "post_process": "",
    }
    bundle = _bundle(problem)
    expansion = expand_bundle_symbolically(bundle)

    from geosolver._internal.pipeline.evaluator.evaluate_float_residual import (
        evaluate_float_residual,
    )

    substitutions = {
        symbol: Float(value) for symbol, value in zip(expansion.symbols, values, strict=True)
    }
    observed = [
        float(left.evalf(subs=substitutions)) - float(right.evalf(subs=substitutions))
        for left, right in expansion.sides
    ]
    expected = evaluate_float_residual(bundle=bundle, values=values)
    assert [_bits(value) for value in observed] == [
        _bits(value) for value in expected.residual_vector
    ]

    if any(token in intersection for token in ("n=", "near=", "far=")):
        assert expansion.selectors


def test_manifest_excludes_identity_and_corpus_routing() -> None:
    manifest = lazy_geometry_manifest()

    assert manifest["case_specific_routing"] is False
    assert manifest["support_inputs"] == [
        "ast_opcode",
        "operand_type",
        "selector_kind",
        "semantic_abi",
    ]
    assert manifest["intersection_policy"] == "LL_LC_CL_CC_n_near_far; exclude_fails_closed"


def test_compile_node_budget_falls_back_without_problem_identity() -> None:
    problem = {
        "task": "solve",
        "id": "identity-must-not-appear-in-limit-reason",
        "variables": {"names": ["x"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(x, 1)"},
        ],
        "constraints": [{"def": "Distance(A, B)", "value": 1}],
        "guards": [],
        "answer": "Distance(A, B)",
        "post_process": "",
    }
    result = try_expand_bundle_symbolically(
        _bundle(problem), limits=LazyCompilationLimits(max_dag_nodes=1)
    )

    assert not result.supported
    assert "operator=construction" in str(result.fallback_reason)
    assert "nodes=" in str(result.fallback_reason)
    assert "limit=1" in str(result.fallback_reason)
    assert problem["id"] not in str(result.fallback_reason)


def test_compile_wall_budget_falls_back_without_problem_identity() -> None:
    problem = {
        "task": "solve",
        "id": "identity-must-not-appear-in-deadline-reason",
        "variables": {"names": ["x"]},
        "construction": [{"name": "A", "expr": "Point(x, 0)"}],
        "constraints": [{"def": "Distance(A)", "value": 1}],
        "guards": [],
        "answer": "Distance(A)",
        "post_process": "",
    }
    result = try_expand_bundle_symbolically(
        _bundle(problem), limits=LazyCompilationLimits(wall_seconds=1e-9)
    )

    assert not result.supported
    assert "compile wall limit exceeded" in str(result.fallback_reason)
    assert "operator=" in str(result.fallback_reason)
    assert problem["id"] not in str(result.fallback_reason)
