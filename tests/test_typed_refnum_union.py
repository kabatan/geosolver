from __future__ import annotations

import math
import random
import struct
import sys
import time
from pathlib import Path

from scipy.optimize import least_squares

from geotarget.continuation import _load_frozen
from geotarget.typed_refnum_ir import (
    TypedRefNumResidualEvaluator,
    compile_typed_refnum_program,
    dispatch_typed_refnum_program,
)


def _build(document):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_union_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )
    return evaluator


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _problem(*, construction_consumer: bool, optimizer: bool = False) -> dict:
    variables = ["ex", "ey"]
    construction = [
        {"name": "O", "expr": "Point(0, 0)"},
        {"name": "A", "expr": "Point(-10, 0)"},
        {"name": "B", "expr": "Point(10, 0)"},
        {"name": "E", "expr": "Point(ex, ey)"},
        {"name": "axis", "expr": "Line(A, B)"},
        {"name": "omega", "expr": "Circle(O, 5)"},
        {"name": "P", "expr": "Intersect(axis, omega, exclude=E)"},
    ]
    constraints = [
        {"def": "Distance(P, O)", "value": 5},
        {"def": "Distance(A, B)", "value": 20},
    ]
    if construction_consumer:
        construction.append({"name": "Q", "expr": "Midpoint(P, O)"})
        constraints[0] = {"def": "Distance(Q, O)", "value": "5/2"}
    if optimizer:
        variables.append("u")
        construction.append({"name": "U", "expr": "Point(u, 0)"})
        constraints.append({"def": "Distance(U, O)", "value": 2})
    return {
        "task": "solve",
        "id": "identity-must-not-affect-union-admission",
        "variables": {"names": variables},
        "construction": construction,
        "constraints": constraints,
        "guards": [],
        "answer": "Distance(A, B)",
        "post_process": "",
    }


def _nested_selector_problem(*, ordinal: bool, construction_consumer: bool) -> dict:
    problem = _problem(construction_consumer=False)
    suffix = ", n=1" if ordinal else ""
    problem["construction"].append(
        {
            "name": "R",
            "expr": f"Intersect(axis, omega, exclude=P{suffix})",
        }
    )
    problem["constraints"][0] = {"def": "Distance(R, O)", "value": 5}
    if construction_consumer:
        problem["construction"].append({"name": "Q", "expr": "Midpoint(R, O)"})
        problem["constraints"][0] = {"def": "Distance(Q, O)", "value": "5/2"}
    return problem


def _assert_vector_bits(observed: list[float], expected: list[float]) -> None:
    assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_exclude_only_union_is_admitted_and_support_key_retains_union_and_selector_type() -> None:
    reference = _build(_problem(construction_consumer=False))
    program = compile_typed_refnum_program(reference.bundle)
    intersect = next(key for key in program.support_keys if key.opcode == "Intersect")
    assert intersect.result_type == "point_or_list"
    assert intersect.operand_types == ("line2", "circle2", "exclude:point2")
    assert any(
        key.opcode == "DistancePP"
        and key.operand_types == ("point_or_list", "point2")
        for key in program.support_keys
    )


def test_union_constraint_consumer_fault_is_component_local() -> None:
    reference = _build(_problem(construction_consumer=False))
    program = compile_typed_refnum_program(reference.bundle)
    for values in ([5.0, 0.0], [-5.0, 0.0], [50.0, 50.0]):
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = program.evaluate(values)
        _assert_vector_bits(observed, expected)
    nonmatching = program.evaluate([50.0, 50.0])
    assert math.isnan(nonmatching[0])
    assert nonmatching[1] == 0.0


def test_union_construction_consumer_fault_invalidates_all_constraints() -> None:
    reference = _build(_problem(construction_consumer=True))
    program = compile_typed_refnum_program(reference.bundle)
    for values in ([5.0, 0.0], [-5.0, 0.0], [50.0, 50.0]):
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = program.evaluate(values)
        _assert_vector_bits(observed, expected)
    assert all(math.isnan(value) for value in program.evaluate([50.0, 50.0]))


def test_union_random_and_exclusion_tolerance_boundaries_are_reference_bit_exact() -> None:
    reference = _build(_problem(construction_consumer=False))
    program = compile_typed_refnum_program(reference.bundle)
    probes = [
        [5.0, 0.0],
        [math.nextafter(5.0, -math.inf), 0.0],
        [math.nextafter(5.0, math.inf), 0.0],
        [5.0 + 5e-6, 0.0],
        [5.0 + 2e-5, 0.0],
        [-5.0 - 5e-6, 0.0],
        [-5.0 - 2e-5, 0.0],
    ]
    rng = random.Random(20260729)
    probes.extend([rng.uniform(-50, 50), rng.uniform(-50, 50)] for _ in range(128))
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = program.evaluate(values)
        _assert_vector_bits(observed, expected)


def test_union_optimizer_callback_trace_and_endpoint_are_reference_bit_exact() -> None:
    reference = _build(_problem(construction_consumer=False, optimizer=True))
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
            [5.0, 0.0, 3.0],
            bounds=([-10.0] * 3, [10.0] * 3),
            max_nfev=64,
            method="trf",
        )
        return trace, result

    reference_trace, reference_result = run(reference)
    candidate_trace, candidate_result = run(candidate)
    assert candidate_trace == reference_trace
    assert candidate_result.status == reference_result.status
    assert candidate_result.nfev == reference_result.nfev
    _assert_vector_bits(list(candidate_result.x), list(reference_result.x))
    _assert_vector_bits(list(candidate_result.fun), list(reference_result.fun))
    assert _bits(candidate_result.cost) == _bits(reference_result.cost)


def test_nested_union_selector_preserves_frozen_list_and_ordinal_semantics() -> None:
    for ordinal in (False, True):
        reference = _build(
            _nested_selector_problem(ordinal=ordinal, construction_consumer=False)
        )
        program = compile_typed_refnum_program(reference.bundle)
        assert any(
            key.opcode == "Intersect" and "exclude:point_or_list" in key.operand_types
            for key in program.support_keys
        )
        for values in ([5.0, 0.0], [-5.0, 0.0], [50.0, 50.0]):
            expected = reference.evaluate_float_residual(values).residual_vector
            observed = program.evaluate(values)
            _assert_vector_bits(observed, expected)


def test_nested_union_selector_fault_scope_is_construction_wide_only_at_consumer() -> None:
    reference = _build(
        _nested_selector_problem(ordinal=False, construction_consumer=True)
    )
    program = compile_typed_refnum_program(reference.bundle)
    for values in ([5.0, 0.0], [50.0, 50.0]):
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = program.evaluate(values)
        _assert_vector_bits(observed, expected)
    assert all(math.isnan(value) for value in program.evaluate([50.0, 50.0]))
