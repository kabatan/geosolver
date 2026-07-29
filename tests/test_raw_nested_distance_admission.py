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
from geotarget.raw_libmp_backend import (
    UnsupportedRawLibmpBackend,
    compile_raw_libmp_program,
)
from geotarget.typed_refnum_ir import compile_typed_refnum_program


def _build(document):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_nested_distance_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )
    return evaluator


def _problem(left: str) -> dict:
    return {
        "task": "solve",
        "id": "unknown-distance-composition",
        "variables": {"names": ["bx", "by", "px", "py", "radius"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(bx, by)"},
            {"name": "P", "expr": "Point(px, py)"},
            {"name": "ell", "expr": "Line(O, B)"},
            {"name": "omega", "expr": "Circle(O, abs(radius))"},
        ],
        "constraints": [{"def": left, "value": 1}],
        "guards": [],
        "answer": "px",
        "post_process": "",
    }


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _assert_bit_exact(reference, raw, probes) -> None:
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_distance_derived_point_to_on_circle_fault_scope_fails_closed() -> None:
    problem = _problem("OnCircle(X, omega)")
    problem["construction"].append(
        {
            "name": "X",
            "expr": (
                "Point(B.x + (2/Distance(B,P))*(P.x-B.x), "
                "B.y + (2/Distance(B,P))*(P.y-B.y))"
            ),
        }
    )
    typed = compile_typed_refnum_program(_build(problem).bundle)
    with pytest.raises(UnsupportedRawLibmpBackend, match="fault-scope-qualified"):
        compile_raw_libmp_program(typed)


@pytest.mark.parametrize(
    "expression",
    [
        "Distance(P, B) + 1",
        "2 * Distance(P, ell)",
        "1 / Distance(P, omega)",
        "Distance(ell, P) + Distance(omega, P)",
    ],
)
def test_nested_distance_consumers_are_bit_exact_without_problem_identity(
    expression: str,
) -> None:
    reference = _build(_problem(expression))
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(2026072905)
    probes = [
        [3.0, 4.0, -2.0, 5.0, 6.0],
        [0.0, 0.0, -2.0, 5.0, 6.0],  # degenerate source line
        [3.0, 4.0, 3.0, 4.0, 0.0],  # coincident points/zero radius
        [math.ulp(0.0), -math.ulp(0.0), 1.0, -1.0, math.ulp(0.0)],
    ]
    probes.extend(
        [
            rng.uniform(0.5, 8),
            rng.uniform(0.5, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        ]
        for _ in range(512)
    )
    _assert_bit_exact(reference, raw, probes)


def test_distance_used_in_derived_point_then_on_circle_fails_closed() -> None:
    problem = _problem("OnCircle(X, omega)")
    problem["construction"].append(
        {
            "name": "X",
            "expr": (
                "Point(O.x + (7/Distance(O, B))*(B.x-O.x), O.y + (7/Distance(O, B))*(B.y-O.y))"
            ),
        }
    )
    typed = compile_typed_refnum_program(_build(problem).bundle)
    with pytest.raises(UnsupportedRawLibmpBackend, match="fault-scope-qualified"):
        compile_raw_libmp_program(typed)


def test_nested_distance_optimizer_trace_and_endpoint_are_bit_exact() -> None:
    problem = _problem(
        "Distance(P, B) + 2*Distance(P, ell) + Distance(P, omega)"
    )
    problem["constraints"].append(
        {"def": "Distance(B, O) + Distance(P, O)", "value": 9}
    )
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))

    def run(function):
        trace: list[tuple[bytes, ...]] = []

        def residual(values):
            trace.append(tuple(_bits(value) for value in values))
            return function(list(values))

        result = least_squares(
            residual,
            [3.0, 4.0, -2.0, 5.0, 6.0],
            bounds=([-10.0] * 5, [10.0] * 5),
            max_nfev=64,
            method="trf",
        )
        return trace, result

    expected_trace, expected = run(
        lambda values: reference.evaluate_float_residual(values).residual_vector
    )
    observed_trace, observed = run(raw.evaluate)
    assert observed_trace == expected_trace
    assert observed.status == expected.status
    assert observed.nfev == expected.nfev
    assert [_bits(value) for value in observed.x] == [_bits(value) for value in expected.x]
    assert [_bits(value) for value in observed.fun] == [_bits(value) for value in expected.fun]
    assert _bits(observed.cost) == _bits(expected.cost)


def test_constraint_side_root_distances_remain_qualified_and_bit_exact() -> None:
    problem = _problem("Distance(P, B)")
    problem["constraints"].extend(
        [
            {"def": "Distance(P, ell)", "value": 2},
            {"def": "Distance(P, omega)", "value": 3},
            {"def": "Distance(ell, P)", "value": 4},
            {"def": "Distance(omega, P)", "value": 5},
        ]
    )
    reference = _build(problem)
    typed = compile_typed_refnum_program(reference.bundle)
    raw = compile_raw_libmp_program(typed)
    probes = [[3.0, 4.0, -2.0, 5.0, 6.0]]
    rng = random.Random(20260729)
    probes.extend(
        [
            rng.uniform(0.5, 8),
            rng.uniform(0.5, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        ]
        for _ in range(64)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]
