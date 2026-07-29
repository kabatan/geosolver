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
    runtime = base._load_module("geotarget_periodic_closure_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )
    return evaluator


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _measurement_problem() -> dict:
    return {
        "task": "solve",
        "id": "unknown-periodic-measurement-closure",
        "variables": {"names": ["cx", "cy", "radius", "t", "ax", "ay"]},
        "construction": [
            {"name": "O", "expr": "Point(cx,cy)"},
            {"name": "A", "expr": "Point(ax,ay)"},
            {"name": "gamma", "expr": "Circle(O,abs(radius))"},
            {"name": "Q", "expr": "PointOnCircle(gamma,t)"},
        ],
        "constraints": [
            {"def": "Distance(Q,A)", "value": 3},
            {"def": "Area(O,Q,A)", "value": 2},
        ],
        "guards": [],
        "answer": "Distance(Q,A)",
        "post_process": "",
    }


def _derived_geometry_problem() -> dict:
    problem = _measurement_problem()
    problem["construction"].extend(
        [
            {"name": "X", "expr": "Point(Q.x+A.x,Q.y-A.y)"},
            {"name": "M", "expr": "Midpoint(Q,A)"},
            {"name": "ell", "expr": "Line(Q,A)"},
            {"name": "delta", "expr": "Circle(Q,Distance(Q,A))"},
        ]
    )
    problem["constraints"] = [
        {"def": "Distance(X,M)", "value": "delta.radius"},
        {"def": "Area(O,X,delta.center)", "value": 2},
        {"def": "Distance(delta.center,Q)", "value": 0},
    ]
    return problem


def _deep_geometry_chain_problem() -> dict:
    return {
        "task": "solve",
        "id": "unknown-periodic-deep-producer-consumer-chain",
        "variables": {"names": ["radius", "t", "ax", "ay", "bx", "by"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "A", "expr": "Point(ax,ay)"},
            {"name": "B", "expr": "Point(bx,by)"},
            {"name": "M", "expr": "Midpoint(O,A)"},
            {"name": "gamma", "expr": "Circle(M,abs(radius)+1)"},
            {"name": "Q", "expr": "PointOnCircle(gamma,(t+1)/5)"},
            {"name": "X", "expr": "Point(Q.x+B.x,Q.y-B.y)"},
            {"name": "ell", "expr": "Line(Q,A)"},
            {"name": "perp", "expr": "PerpendicularLine(Q,ell)"},
            {"name": "omega", "expr": "Circumcircle(Q,A,B)"},
            {"name": "R", "expr": "Reflect(X,ell)"},
            {"name": "P", "expr": "Intersect(perp,omega,exclude=Q,n=1)"},
            {"name": "S", "expr": "Reflect(P,ell)"},
        ],
        "constraints": [
            {"def": "Distance(P,S)", "value": "Distance(Q,R)"},
            {"def": "OnCircle(P,omega)", "value": 0},
        ],
        "guards": [],
        "answer": "Distance(P,S)",
        "post_process": "",
    }


def _assert_bit_exact(reference, raw, probes) -> None:
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_periodic_distance_and_area_closure_is_bit_exact_at_numeric_boundaries() -> None:
    reference = _build(_measurement_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    periodic = [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
        math.nextafter(0.25, 0.0),
        math.nextafter(0.25, 1.0),
        math.nextafter(0.5, 0.0),
        math.nextafter(0.5, 1.0),
        math.ulp(0.0),
        -math.ulp(0.0),
        float(2**52),
        -float(2**52),
        1e100,
        -1e100,
        float.fromhex("0x1.fffffffffffffp+1023"),
    ]
    probes = [[1.0, -2.0, 4.0, parameter, 3.0, 5.0] for parameter in periodic]
    for base in (-0.37, 0.13, 0.25, math.nextafter(0.25, 1.0)):
        probes.extend(
            [1.0, -2.0, 4.0, base + shift, 3.0, 5.0]
            for shift in (-1_000_000, -2, -1, 0, 1, 2, 1_000_000)
        )
    rng = random.Random(2026072907)
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-1e6, 1e6),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        ]
        for _ in range(2048)
    )
    _assert_bit_exact(reference, raw, probes)


def test_periodic_derived_point_line_circle_and_fault_scope_are_bit_exact() -> None:
    reference = _build(_derived_geometry_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    probes = [
        [0.0, 0.0, 5.0, 0.0, -3.0, 4.0],
        [0.0, 0.0, 5.0, 0.25, 0.0, 5.0],  # Q=A: derived Line faults globally
        [0.0, 0.0, 0.0, 0.75, 0.0, 0.0],  # zero circle and coincident points
        [math.ulp(0.0), 0.0, math.ulp(0.0), -math.ulp(0.0), 1.0, -1.0],
    ]
    rng = random.Random(2026072908)
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(0, 8),
            rng.uniform(-16, 16),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        ]
        for _ in range(1024)
    )
    _assert_bit_exact(reference, raw, probes)

    negative_radius_problem = _measurement_problem()
    negative_radius_problem["construction"][2] = {
        "name": "gamma",
        "expr": "Circle(O,radius)",
    }
    negative_reference = _build(negative_radius_problem)
    negative_raw = compile_raw_libmp_program(
        compile_typed_refnum_program(negative_reference.bundle)
    )
    _assert_bit_exact(
        negative_reference,
        negative_raw,
        [[0.0, 0.0, -1.0, 0.2, 3.0, 4.0]],
    )
    assert all(math.isnan(value) for value in negative_raw.evaluate([0, 0, -1, 0.2, 3, 4]))


def test_periodic_deep_geometry_chain_fails_closed_until_rounding_qualified() -> None:
    typed = compile_typed_refnum_program(_build(_deep_geometry_chain_problem()).bundle)
    with pytest.raises(UnsupportedRawLibmpBackend, match="rounding edge"):
        compile_raw_libmp_program(typed)


def test_periodic_measurement_optimizer_trace_and_endpoint_are_bit_exact() -> None:
    problem = _measurement_problem()
    problem["construction"][2] = {
        "name": "gamma",
        "expr": "Circle(Midpoint(O,A),abs(radius)+1)",
    }
    problem["construction"][3] = {
        "name": "Q",
        "expr": "PointOnCircle(gamma,(t+1)/5)",
    }
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))

    def run(function):
        trace: list[tuple[bytes, ...]] = []

        def residual(values):
            trace.append(tuple(_bits(value) for value in values))
            return function(list(values))

        result = least_squares(
            residual,
            [0.5, -0.25, 4.0, 0.17, 3.0, 4.0],
            bounds=([-10.0] * 6, [10.0] * 6),
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


@pytest.mark.parametrize(
    ("circle_expression", "parameter_expression"),
    [
        ("Circle(Midpoint(O,A),abs(radius))", "t"),
        ("Circle(O,1/(2*sin(pi/7)))", "t"),
        ("Circle(O,abs(radius))", "t/5"),
    ],
)
def test_periodic_derived_circle_and_parameter_producers_are_bit_exact(
    circle_expression: str, parameter_expression: str
) -> None:
    problem = _measurement_problem()
    problem["construction"][2] = {"name": "gamma", "expr": circle_expression}
    problem["construction"][3] = {
        "name": "Q",
        "expr": f"PointOnCircle(gamma,{parameter_expression})",
    }
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(circle_expression + parameter_expression)
    probes = [
        [1.0, -2.0, 4.0, parameter, 3.0, 5.0]
        for parameter in (
            0.0,
            0.25,
            math.nextafter(0.25, 0.0),
            math.nextafter(0.25, 1.0),
            math.ulp(0.0),
            -math.ulp(0.0),
            float(2**52),
        )
    ]
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(0.1, 8),
            rng.uniform(-1e4, 1e4),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        ]
        for _ in range(512)
    )
    _assert_bit_exact(reference, raw, probes)
