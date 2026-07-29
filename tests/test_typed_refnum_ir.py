from __future__ import annotations

import math
import random
import struct
import sys
import time
from pathlib import Path

import pytest
from scipy.optimize import least_squares

from geotarget.continuation import _load_frozen
from geotarget.typed_refnum_ir import (
    TypedRefNumResidualEvaluator,
    UnsupportedTypedRefNumIR,
    compile_typed_refnum_program,
    dispatch_typed_refnum_program,
)


def _build(document):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_typed_ir_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )
    return evaluator


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _unknown_problem(identifier: str = "unseen-random-composition") -> dict:
    return {
        "task": "solve",
        "id": identifier,
        "variables": {"names": ["cx", "cy", "t", "ux", "uy"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "X", "expr": "Point(cx, cy)"},
            {"name": "U", "expr": "Point(ux, uy)"},
            {"name": "gamma", "expr": "Circle(O, 4)"},
            {"name": "Q", "expr": "PointOnCircle(gamma, t)"},
            {"name": "ell", "expr": "Line(O, X)"},
            {"name": "axis", "expr": "Line(0, 1, 0)"},
        ],
        "constraints": [
            {"def": "Distance(Q, X)", "value": "Distance(U, ell)"},
            {"def": "Distance(Q, axis)", "value": 1},
            {"def": "Area(O, X, U)", "value": 3},
            {"def": "Angle(Q, O, X)", "value": "pi/3"},
            {"def": "Angle(ell, axis)", "value": "pi/4"},
        ],
        "guards": [],
        "answer": "Distance(Q, U)",
        "post_process": "",
    }


def test_unknown_composed_problem_is_residual_norm_and_branch_bit_exact() -> None:
    reference = _build(_unknown_problem())
    program = compile_typed_refnum_program(reference.bundle)
    rng = random.Random(20260729)
    probes = [
        [3.0, 4.0, 0.0, -2.0, 5.0],
        [3.0, 4.0, 0.25, -2.0, 5.0],  # exact cos(pi/2) branch
        [3.0, 4.0, 0.5, -2.0, 5.0],
        [3.0, 4.0, math.nextafter(0.25, 0.0), -2.0, 5.0],
        [3.0, 4.0, math.nextafter(0.25, 1.0), -2.0, 5.0],
    ]
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-4, 4),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        ]
        for _ in range(128)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values)
        observed_vector = program.evaluate(values)
        assert [_bits(value) for value in observed_vector] == [
            _bits(value) for value in expected.residual_vector
        ]
        from geosolver._internal.autosolve.execution.interpreter_helpers import _residual_norm

        if all(math.isfinite(value) for value in observed_vector):
            assert _bits(_residual_norm(observed_vector)) == _bits(expected.residual_norm_float)


def test_admission_is_identity_free_and_uses_typed_semantic_keys() -> None:
    first = compile_typed_refnum_program(_build(_unknown_problem("alpha")).bundle)
    second = compile_typed_refnum_program(_build(_unknown_problem("totally-different-id")).bundle)
    first_trace, second_trace = first.admission_trace(), second.admission_trace()
    assert first_trace["case_specific_routing"] is False
    assert first_trace["problem_identity_read"] is False
    assert first_trace["fallback_scope"] == "whole_problem"
    assert first_trace["support_key_sha256"] == second_trace["support_key_sha256"]
    assert first.support_keys == second.support_keys


def test_constructor_faults_match_reference_all_constraint_failure() -> None:
    circle_problem = _unknown_problem()
    circle_problem["construction"][3] = {"name": "gamma", "expr": "Circle(O, cx)"}
    reference = _build(circle_problem)
    program = compile_typed_refnum_program(reference.bundle)
    expected = reference.evaluate_float_residual([-1.0, 2.0, 0.1, 3.0, 4.0])
    observed = program.evaluate([-1.0, 2.0, 0.1, 3.0, 4.0])
    assert all(math.isnan(value) for value in expected.residual_vector)
    assert all(math.isnan(value) for value in observed)

    line_problem = _unknown_problem()
    reference = _build(line_problem)
    program = compile_typed_refnum_program(reference.bundle)
    expected = reference.evaluate_float_residual([0.0, 0.0, 0.1, 3.0, 4.0])
    observed = program.evaluate([0.0, 0.0, 0.1, 3.0, 4.0])
    assert [_bits(value) for value in observed] == [
        _bits(value) for value in expected.residual_vector
    ]


def test_bool_or_unsupported_residual_node_rejects_whole_problem() -> None:
    problem = _unknown_problem()
    problem["construction"][0] = {"name": "O", "expr": "Point(True, 0)"}
    with pytest.raises(UnsupportedTypedRefNumIR, match="bool"):
        compile_typed_refnum_program(_build(problem).bundle)

    problem = _unknown_problem()
    problem["construction"].append({"name": "M", "expr": "Mystery(O, X)"})
    with pytest.raises(UnsupportedTypedRefNumIR, match="not exported"):
        compile_typed_refnum_program(_build(problem).bundle)


def test_resource_gates_fail_closed() -> None:
    bundle = _build(_unknown_problem()).bundle
    with pytest.raises(UnsupportedTypedRefNumIR, match="resource limit"):
        compile_typed_refnum_program(bundle, max_ast_nodes=1)
    with pytest.raises(ValueError, match="resource gate"):
        compile_typed_refnum_program(bundle, max_compile_seconds=float("inf"))


def test_dispatcher_exposes_real_identity_free_admission_and_no_partial_fallback() -> None:
    supported_bundle = _build(_unknown_problem("dispatcher-must-ignore-this-id")).bundle
    accepted = dispatch_typed_refnum_program(supported_bundle)
    assert accepted.supported
    assert accepted.trace["admitted"] is True
    assert accepted.trace["problem_identity_read"] is False
    assert "PointOnCircle" in accepted.trace["attempted_ast_opcodes"]

    unsupported = _unknown_problem("also-ignored")
    unsupported["construction"].append({"name": "M", "expr": "Mystery(O, X)"})
    rejected = dispatch_typed_refnum_program(_build(unsupported).bundle)
    assert rejected.supported is False
    assert rejected.program is None
    assert rejected.trace["admitted"] is False
    assert rejected.trace["partial_program_exposed"] is False
    assert rejected.trace["fallback_scope"] == "whole_problem"
    assert "Mystery" in rejected.trace["attempted_ast_opcodes"]


def test_guards_and_hard_feasibility_remain_frozen_reference_authorities() -> None:
    problem = _unknown_problem("unseen-with-guards")
    problem["guards"] = ["AssumeNe(cx, 0)", "AssumeGt(Distance(Q, X), 0)"]
    reference = _build(problem)
    dispatch = dispatch_typed_refnum_program(reference.bundle)
    assert dispatch.program is not None, dispatch.fallback_reason
    candidate = TypedRefNumResidualEvaluator(reference, dispatch.program)
    rng = random.Random(8675309)
    for _ in range(64):
        values = [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-2, 2),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        ]
        expected = reference.evaluate_float_residual(values)
        observed = candidate.evaluate_float_residual(values)
        assert [_bits(value) for value in observed.residual_vector] == [
            _bits(value) for value in expected.residual_vector
        ]
        assert _bits(observed.residual_norm_float) == _bits(expected.residual_norm_float)
        assert candidate.evaluate_guard(values) == reference.evaluate_guard(values)
        assert candidate.evaluate_float_hard_feasibility(
            values
        ) == reference.evaluate_float_hard_feasibility(values)
    assert dispatch.trace["guard_authority"] == "frozen_reference_delegate"
    assert dispatch.trace["delegated_guard_opcodes"] == ["AssumeGt", "AssumeNe", "Distance"]


def test_real_scipy_optimizer_callback_trace_and_endpoint_are_bit_exact() -> None:
    reference = _build(_unknown_problem("optimizer-trace-unseen"))
    dispatch = dispatch_typed_refnum_program(reference.bundle)
    assert dispatch.program is not None, dispatch.fallback_reason
    candidate = TypedRefNumResidualEvaluator(reference, dispatch.program)

    def run(evaluator):
        trace: list[tuple[bytes, ...]] = []

        def residual(values):
            trace.append(tuple(_bits(value) for value in values))
            return evaluator.evaluate_float_residual(list(values)).residual_vector

        result = least_squares(
            residual,
            [3.0, 4.0, 0.17, -2.0, 5.0],
            bounds=([-10.0] * 5, [10.0] * 5),
            max_nfev=64,
            method="trf",
        )
        return trace, result

    reference_trace, reference_result = run(reference)
    candidate_trace, candidate_result = run(candidate)
    assert candidate_trace == reference_trace
    assert candidate_result.status == reference_result.status
    assert candidate_result.nfev == reference_result.nfev
    assert [_bits(value) for value in candidate_result.x] == [
        _bits(value) for value in reference_result.x
    ]
    assert [_bits(value) for value in candidate_result.fun] == [
        _bits(value) for value in reference_result.fun
    ]
    assert _bits(candidate_result.cost) == _bits(reference_result.cost)


def test_extended_general_v15_primitives_are_bit_exact_in_unseen_composition() -> None:
    problem = {
        "task": "solve",
        "id": "unseen-extended-primitive-composition",
        "variables": {"names": ["bx", "by", "cx", "cy", "t"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(bx, by)"},
            {"name": "C", "expr": "Point(cx, cy)"},
            {"name": "M", "expr": "Midpoint(A, B)"},
            {"name": "G", "expr": "Centroid(A, B, C)"},
            {"name": "O", "expr": "Circumcenter(A, B, C)"},
            {"name": "omega", "expr": "Circumcircle(A, B, C)"},
            {"name": "H", "expr": "Orthocenter(A, B, C)"},
            {"name": "I", "expr": "Incenter(A, B, C)"},
            {"name": "Q", "expr": "PointOnSegment(B, C, t)"},
            {"name": "ell", "expr": "Line(A, B)"},
            {"name": "F", "expr": "FootOfPerpendicular(ell, C)"},
            {"name": "parallel", "expr": "ParallelLine(ell, C)"},
            {"name": "perpendicular", "expr": "PerpendicularLine(C, ell)"},
        ],
        "constraints": [
            {"def": "Distance(M, G)", "value": "Distance(O, H)"},
            {"def": "Distance(I, Q)", "value": "Distance(C, F)"},
            {"def": "Distance(C, parallel)", "value": 0},
            {"def": "Distance(C, perpendicular)", "value": 0},
            {"def": "Distance(omega.center, A)", "value": "omega.radius"},
            {"def": "cos(t)", "value": "abs(t)"},
        ],
        "guards": [],
        "answer": "Distance(G, I)",
        "post_process": "",
    }
    reference = _build(problem)
    program = compile_typed_refnum_program(reference.bundle)
    rng = random.Random(10101)
    probes = [[3.0, 0.0, 1.0, 4.0, 0.25]]
    probes.extend(
        [
            rng.uniform(1.0, 8.0),
            rng.uniform(-2.0, 2.0),
            rng.uniform(-2.0, 2.0),
            rng.uniform(2.0, 8.0),
            rng.uniform(-1.0, 1.0),
        ]
        for _ in range(64)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values)
        observed = program.evaluate(values)
        assert [_bits(value) for value in observed] == [
            _bits(value) for value in expected.residual_vector
        ]

    # Collinearity exercises exact infinities/non-finite constraint results.
    # Match the frozen per-component fault scope rather than assuming every
    # degenerate construction raises at the construction boundary.
    degenerate = [2.0, 0.0, 4.0, 0.0, 0.5]
    expected_degenerate = reference.evaluate_float_residual(degenerate).residual_vector
    observed_degenerate = program.evaluate(degenerate)
    assert [_bits(value) for value in observed_degenerate] == [
        _bits(value) for value in expected_degenerate
    ]


def test_extended_predicates_and_line_constructions_are_unknown_problem_bit_exact() -> None:
    problem = {
        "task": "solve",
        "id": "unknown-predicate-and-line-composition",
        "variables": {"names": ["bx", "by", "cx", "cy", "t"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(bx, by)"},
            {"name": "C", "expr": "Point(cx, cy)"},
            {"name": "ell", "expr": "Line(A, B)"},
            {"name": "omega", "expr": "Incircle(A, B, C)"},
            {"name": "Q", "expr": "PointOnLine(ell, t)"},
            {"name": "M", "expr": "Midpoint(A, B)"},
            {"name": "bisector", "expr": "AngleBisector(A, B, C)"},
            {"name": "perpBisector", "expr": "PerpendicularBisector(A, B)"},
            {"name": "R", "expr": "Reflect(C, A)"},
            {"name": "S", "expr": "Reflect(C, ell)"},
            {"name": "T", "expr": "ContactPoint(omega, ell)"},
        ],
        "constraints": [
            {"def": "OnCircle(T, omega)", "value": 0},
            {"def": "OnLine(Q, ell)", "value": 0},
            {"def": "OnLine(Q, A, B)", "value": 0},
            {"def": "OnSegment(M, A, B)", "value": 0},
            {"def": "Parallel(ell, bisector)", "value": 0},
            {"def": "Perpendicular(ell, perpBisector)", "value": 0},
            {"def": "IsTangent(ell, omega)", "value": 0},
            {"def": "Distance(R, S)", "value": "Distance(C, T)"},
        ],
        "guards": [],
        "answer": "Distance(Q, T)",
        "post_process": "",
    }
    reference = _build(problem)
    program = compile_typed_refnum_program(reference.bundle)
    rng = random.Random(424242)
    for _ in range(96):
        values = [
            rng.uniform(2.0, 8.0),
            rng.uniform(-1.0, 1.0),
            rng.uniform(-2.0, 2.0),
            rng.uniform(2.0, 8.0),
            rng.uniform(-3.0, 3.0),
        ]
        expected = reference.evaluate_float_residual(values)
        observed = program.evaluate(values)
        assert [_bits(value) for value in observed] == [
            _bits(value) for value in expected.residual_vector
        ]


@pytest.mark.parametrize(
    "construction_expression",
    [
        "Foot(ell, P)",
        "Collinear(P, ell)",
        "ContactPoint(A, B, C, side='AB')",
    ],
)
def test_typed_admission_never_invents_frozen_alias_arity_or_keyword(
    construction_expression: str,
) -> None:
    problem = {
        "task": "solve",
        "id": "unknown-invalid-call-contract",
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(3, 0)"},
            {"name": "C", "expr": "Point(0, 4)"},
            {"name": "P", "expr": "Point(x, y)"},
            {"name": "ell", "expr": "Line(A, B)"},
            {"name": "X", "expr": construction_expression},
        ],
        "constraints": [{"def": "Distance(P, A)", "value": 1}],
        "guards": [],
        "answer": "Distance(P, B)",
        "post_process": "",
    }
    reference = _build(problem)
    dispatch = dispatch_typed_refnum_program(reference.bundle)
    assert dispatch.program is None
    assert dispatch.trace["fallback_scope"] == "whole_problem"
    assert dispatch.trace["partial_program_exposed"] is False
    assert all(
        math.isnan(value) for value in reference.evaluate_float_residual([1.0, 2.0]).residual_vector
    )


@pytest.mark.parametrize(
    "invalid_expression",
    [
        "Projection(ell, P)",
        "PerpendicularFoot(ell, P)",
        "Collinear(P)",
        "Collinear(P, A, B, P, A)",
        "Distance(P, A, unsupported=True)",
        "Point(x=x, z=y)",
    ],
)
def test_randomized_unknown_alias_arity_and_keyword_contracts_fail_closed(
    invalid_expression: str,
) -> None:
    problem = {
        "task": "solve",
        "id": f"unknown-negative-contract-{hash(invalid_expression)}",
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(2, 0)"},
            {"name": "P", "expr": "Point(x, y)"},
            {"name": "ell", "expr": "Line(A, B)"},
            {"name": "bad", "expr": invalid_expression},
        ],
        "constraints": [{"def": "Distance(P, A)", "value": 1}],
        "guards": [],
        "answer": "Distance(P, B)",
        "post_process": "",
    }
    dispatch = dispatch_typed_refnum_program(_build(problem).bundle)
    assert dispatch.supported is False
    assert dispatch.program is None
    assert dispatch.fallback_reason is not None


@pytest.mark.parametrize("shadowed_name", ["pi", "sqrt", "Distance", "Point"])
@pytest.mark.parametrize("declaration_kind", ["variable", "construction"])
def test_frozen_namespace_shadowing_fails_closed(shadowed_name: str, declaration_kind: str) -> None:
    variable_names = ["x"] + ([shadowed_name] if declaration_kind == "variable" else [])
    construction = [
        {"name": "A", "expr": "Point(x, 0)"},
        {"name": "B", "expr": "Point(0, 0)"},
    ]
    if declaration_kind == "construction":
        construction.append({"name": shadowed_name, "expr": "Point(1, 1)"})
    problem = {
        "task": "solve",
        "id": "unknown-source-order-shadowing",
        "variables": {"names": variable_names},
        "construction": construction,
        "constraints": [{"def": "Distance(A, B)", "value": 1}],
        "guards": [],
        "answer": "Distance(A, B)",
        "post_process": "",
    }
    dispatch = dispatch_typed_refnum_program(_build(problem).bundle)
    assert dispatch.program is None
    assert "namespace shadowing" in str(dispatch.fallback_reason)
