from __future__ import annotations

import math
import random
import struct
import sys
import time
from pathlib import Path

import pytest
from mpmath.libmp.libmpf import to_float
from scipy.optimize import least_squares

from geotarget.continuation import _load_frozen
from geotarget.raw_libmp_backend import (
    RawLibmpRuntimeFault,
    UnsupportedRawLibmpBackend,
    compile_raw_libmp_program,
    evaluate_raw_intersect,
)
from geotarget.typed_refnum_intersections import (
    compile_intersect_extension,
    evaluate_intersect_extension,
)
from geotarget.typed_refnum_ir import compile_typed_refnum_program


def _build(document):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_raw_libmp_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )
    return evaluator


def _problem() -> dict:
    return {
        "task": "solve",
        "id": "identity-is-not-an-admission-input",
        "variables": {"names": ["cx", "cy", "ux", "uy", "qx", "qy", "t", "radius"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "X", "expr": "Point(cx, cy)"},
            {"name": "U", "expr": "Point(ux, uy)"},
            {"name": "Q", "expr": "Point(qx, qy)"},
            {"name": "gamma", "expr": "Circle(O, radius)"},
            {"name": "ell", "expr": "Line(O, X)"},
            {"name": "axis", "expr": "Line(0, 1, 0)"},
        ],
        "constraints": [
            {"def": "Distance(Q, X)", "value": "Distance(U, ell)"},
            {"def": "Distance(Q, axis)", "value": 1},
            {"def": "Area(O, X, U)", "value": 3},
            {"def": "Angle(Q, O, X)", "value": "pi/3"},
            {"def": "Angle(ell, axis)", "value": "pi/4"},
            {"def": "cos(t)", "value": "abs(t)"},
            {"def": "sin(t)", "value": "sqrt(abs(t))"},
        ],
        "guards": [],
        "answer": "Distance(Q, U)",
        "post_process": "",
    }


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def test_general_nonperiodic_geometry_is_bit_exact() -> None:
    reference = _build(_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(0xBF53)
    probes = [
        [3.0, 4.0, -2.0, 5.0, 1.0, -3.0, 0.0, 4.0],
        [math.nextafter(3.0, 0.0), 4.0, 0.0, 0.0, -1.0, 2.0, 0.25, 0.0],
    ]
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-4, 4),
            rng.uniform(0, 8),
        ]
        for _ in range(512)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_construction_fault_invalidates_all_constraints() -> None:
    reference = _build(_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    values = [3.0, 4.0, -2.0, 5.0, 1.0, -3.0, 0.2, -1.0]
    expected = reference.evaluate_float_residual(values).residual_vector
    observed = raw.evaluate(values)
    assert all(math.isnan(value) for value in expected)
    assert all(math.isnan(value) for value in observed)


def test_parallel_line_intersection_none_preserves_frozen_distance_asymmetry() -> None:
    problem = {
        "task": "solve",
        "id": "generic-degenerate-line-intersection",
        "variables": {"names": ["s", "dx", "h"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(s, 0)"},
            {"name": "D", "expr": "Point(dx, h)"},
            {"name": "C", "expr": "Point(dx + 1, h)"},
            {"name": "P", "expr": "Intersect(Line(A, C), Line(B, D))"},
        ],
        "constraints": [
            {"def": "Distance(A, P)", "value": 4},
            {"def": "Distance(P, A)", "value": 4},
            {"def": "Distance(B, P)", "value": 5},
            {"def": "Distance(A, C)", "value": 1},
        ],
        "guards": [],
        "answer": "Distance(A, B)",
        "post_process": "",
    }
    reference = _build(problem)
    typed = compile_typed_refnum_program(reference.bundle)
    raw = compile_raw_libmp_program(typed)
    probes = [
        [0.0, 0.0, 0.0],
        [2**-26, 0.0, 0.0],
        [0.0, 2**-26, 0.0],
        [0.0, 0.0, 2**-26],
    ]
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        assert [_bits(value) for value in typed.evaluate(values)] == [
            _bits(value) for value in expected
        ]
        assert [_bits(value) for value in raw.evaluate(values)] == [
            _bits(value) for value in expected
        ]

    parallel = raw.evaluate([2**-26, 0.0, 0.0])
    assert parallel[0] == -4.0
    assert math.isnan(parallel[1])
    assert parallel[2] == -5.0 + 2**-26
    assert parallel[3] == 0.0


def test_concentric_circle_intersection_is_a_construction_wide_fault() -> None:
    problem = {
        "task": "solve",
        "id": "generic-concentric-circle-intersection",
        "variables": {"names": ["cx", "cy"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "X", "expr": "Point(cx, cy)"},
            {"name": "A", "expr": "Point(3, 4)"},
            {"name": "first", "expr": "Circle(O, 2)"},
            {"name": "second", "expr": "Circle(X, 3)"},
            {"name": "P", "expr": "Intersect(first, second, n=1)"},
        ],
        "constraints": [
            {"def": "Distance(P, O)", "value": 2},
            {"def": "Distance(A, O)", "value": 5},
        ],
        "guards": [],
        "answer": "Distance(A, O)",
        "post_process": "",
    }
    reference = _build(problem)
    typed = compile_typed_refnum_program(reference.bundle)
    raw = compile_raw_libmp_program(typed)
    expected = reference.evaluate_float_residual([0.0, 0.0]).residual_vector
    assert [_bits(value) for value in typed.evaluate([0.0, 0.0])] == [
        _bits(value) for value in expected
    ]
    assert [_bits(value) for value in raw.evaluate([0.0, 0.0])] == [
        _bits(value) for value in expected
    ]
    assert all(math.isnan(value) for value in expected)


@pytest.mark.parametrize(
    ("producer", "construction"),
    [
        (
            "IntersectLL",
            [
                {"name": "B", "expr": "Point(1, 0)"},
                {"name": "D", "expr": "Point(0, u)"},
                {"name": "C", "expr": "Point(1, 2*u)"},
                {"name": "N", "expr": "Intersect(Line(O, B), Line(D, C))"},
            ],
        ),
        (
            "Circumcenter",
            [
                {"name": "B", "expr": "Point(1, 0)"},
                {"name": "C", "expr": "Point(2, u)"},
                {"name": "N", "expr": "Circumcenter(O, B, C)"},
            ],
        ),
        (
            "Orthocenter",
            [
                {"name": "B", "expr": "Point(1, 0)"},
                {"name": "C", "expr": "Point(2, u)"},
                {"name": "N", "expr": "Orthocenter(O, B, C)"},
            ],
        ),
        (
            "AngleBisector",
            [
                {"name": "B", "expr": "Point(u, 0)"},
                {"name": "C", "expr": "Point(0, 1)"},
                {"name": "N", "expr": "AngleBisector(B, O, C)"},
            ],
        ),
        (
            "Circumcircle",
            [
                {"name": "B", "expr": "Point(1, 0)"},
                {"name": "C", "expr": "Point(2, u)"},
                {"name": "N", "expr": "Circumcircle(O, B, C)"},
            ],
        ),
    ],
)
def test_point_first_distance_uses_runtime_none_rule_for_all_static_types(
    producer: str, construction: list[dict[str, str]]
) -> None:
    problem = {
        "task": "solve",
        "id": f"unknown-nullable-{producer}",
        "variables": {"names": ["u"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "A", "expr": "Point(3, 4)"},
            *construction,
        ],
        "constraints": [
            {"def": "Distance(A, N)", "value": 5},
            {"def": "Distance(N, A)", "value": 5},
            {"def": "Distance(O, A)", "value": 5},
        ],
        "guards": [],
        "answer": "Distance(O, A)",
        "post_process": "",
    }
    reference = _build(problem)
    typed = compile_typed_refnum_program(reference.bundle)
    raw = compile_raw_libmp_program(typed)
    for values in ([0.0], [0.25]):
        expected = reference.evaluate_float_residual(values).residual_vector
        assert [_bits(value) for value in typed.evaluate(values)] == [
            _bits(value) for value in expected
        ]
        assert [_bits(value) for value in raw.evaluate(values)] == [
            _bits(value) for value in expected
        ]
    nullable = raw.evaluate([0.0])
    assert nullable[0] == 0.0
    assert math.isnan(nullable[1])
    assert nullable[2] == 0.0


def test_scipy_callback_trace_and_endpoint_are_bit_exact() -> None:
    reference = _build(_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))

    def run(function):
        trace: list[tuple[bytes, ...]] = []

        def residual(values):
            trace.append(tuple(_bits(value) for value in values))
            return function(list(values))

        result = least_squares(
            residual,
            [3.0, 4.0, -2.0, 5.0, 1.0, -3.0, 0.2, 4.0],
            bounds=([-10.0] * 7 + [0.0], [10.0] * 8),
            max_nfev=64,
            method="trf",
        )
        return trace, result

    reference_trace, reference_result = run(
        lambda values: reference.evaluate_float_residual(values).residual_vector
    )
    raw_trace, raw_result = run(raw.evaluate)
    assert raw_trace == reference_trace
    assert raw_result.status == reference_result.status
    assert raw_result.nfev == reference_result.nfev
    assert [_bits(value) for value in raw_result.x] == [
        _bits(value) for value in reference_result.x
    ]
    assert [_bits(value) for value in raw_result.fun] == [
        _bits(value) for value in reference_result.fun
    ]
    assert _bits(raw_result.cost) == _bits(reference_result.cost)


def test_point_on_circle_general_effect_closure_is_qualified() -> None:
    problem = _problem()
    problem["construction"][3] = {"name": "Q", "expr": "PointOnCircle(gamma, t)"}
    # Move gamma before Q so this is a valid typed V15 construction.
    problem["construction"][3], problem["construction"][4] = (
        problem["construction"][4],
        problem["construction"][3],
    )
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(2026072912)
    probes = [
        [3.0, 4.0, -2.0, 5.0, 0.0, 0.0, parameter, 4.0]
        for parameter in (
            0.0,
            0.25,
            math.nextafter(0.25, 0.0),
            math.nextafter(0.25, 1.0),
            math.ulp(0.0),
        )
    ]
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            0.0,
            0.0,
            rng.uniform(-16, 16),
            rng.uniform(0, 8),
        ]
        for _ in range(256)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [
            _bits(value) for value in expected
        ]


@pytest.mark.parametrize(
    ("problem", "probes"),
    [
        (
            {
                "task": "solve",
                "id": "raw-unknown-centers-and-lines",
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
                ],
                "guards": [],
                "answer": "Distance(G, I)",
                "post_process": "",
            },
            [[3.0, 0.0, 1.0, 4.0, 0.25]],
        ),
        (
            {
                "task": "solve",
                "id": "raw-unknown-predicates-and-reflections",
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
            },
            [],
        ),
    ],
)
def test_extended_nonperiodic_opcodes_are_bit_exact_in_unknown_compositions(
    problem: dict, probes: list[list[float]]
) -> None:
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(0xA11CE)
    probes.extend(
        [
            rng.uniform(2.0, 8.0),
            rng.uniform(-1.0, 1.0),
            rng.uniform(-2.0, 2.0),
            rng.uniform(2.0, 8.0),
            rng.uniform(-1.0, 1.0),
        ]
        for _ in range(128)
    )
    # A collinear boundary exercises the frozen per-component fault/NaN scope.
    probes.append([2.0, 0.0, 4.0, 0.0, 0.5])
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def _extended_problem() -> dict:
    return {
        "task": "solve",
        "id": "unseen-composition-not-a-routing-key",
        "variables": {"names": ["bx", "by", "cx", "cy", "t"]},
        "construction": [
            {"name": "A", "expr": "Point(0,0)"},
            {"name": "B", "expr": "Point(bx,by)"},
            {"name": "C", "expr": "Point(cx,cy)"},
            {"name": "M", "expr": "Midpoint(A,B)"},
            {"name": "G", "expr": "Centroid(A,B,C)"},
            {"name": "O", "expr": "Circumcenter(A,B,C)"},
            {"name": "omega", "expr": "Circumcircle(A,B,C)"},
            {"name": "H", "expr": "Orthocenter(A,B,C)"},
            {"name": "I", "expr": "Incenter(A,B,C)"},
            {"name": "inc", "expr": "Incircle(A,B,C)"},
            {"name": "Q", "expr": "PointOnSegment(B,C,t)"},
            {"name": "ell", "expr": "Line(A,B)"},
            {"name": "F", "expr": "FootOfPerpendicular(ell,C)"},
            {"name": "parallel", "expr": "ParallelLine(ell,C)"},
            {"name": "perpendicular", "expr": "PerpendicularLine(C,ell)"},
            {"name": "onell", "expr": "PointOnLine(ell,t)"},
            {"name": "bis", "expr": "AngleBisector(A,B,C)"},
            {"name": "pb", "expr": "PerpendicularBisector(A,B)"},
            {"name": "R", "expr": "Reflect(C,A)"},
            {"name": "S", "expr": "Reflect(C,ell)"},
            {"name": "T", "expr": "ContactPoint(inc,ell)"},
        ],
        "constraints": [
            {"def": "Distance(M,G)", "value": "Distance(O,H)"},
            {"def": "Distance(I,Q)", "value": "Distance(C,F)"},
            {"def": "Distance(C,parallel)", "value": 0},
            {"def": "Distance(C,perpendicular)", "value": 0},
            {"def": "Distance(omega.center,A)", "value": "omega.radius"},
            {"def": "OnCircle(T,inc)", "value": 0},
            {"def": "OnLine(onell,ell)", "value": 0},
            {"def": "OnLine(onell,A,B)", "value": 0},
            {"def": "OnSegment(M,A,B)", "value": 0},
            {"def": "Parallel(ell,bis)", "value": 0},
            {"def": "Perpendicular(ell,pb)", "value": 0},
            {"def": "IsTangent(ell,inc)", "value": 0},
            {"def": "Distance(R,S)", "value": "Distance(C,T)"},
            {"def": "O.x + O.y", "value": "inc.center.x + inc.center.y"},
        ],
        "guards": [],
        "answer": "Distance(Q,T)",
        "post_process": "",
    }


def _external_center_problem() -> dict:
    return {
        "task": "solve",
        "id": "another-unseen-composition",
        "variables": {"names": ["bx", "by", "cx", "cy", "t"]},
        "construction": [
            {"name": "A", "expr": "Point(0,0)"},
            {"name": "B", "expr": "Point(bx,by)"},
            {"name": "C", "expr": "Point(cx,cy)"},
            {"name": "EA", "expr": "Excenter(A,B,C,vertex='A')"},
            {"name": "EB", "expr": "Excenter(A,B,C,vertex='B')"},
            {"name": "EC", "expr": "Excenter(A,B,C,vertex='C')"},
            {"name": "eA", "expr": "Excircle(A,B,C,vertex='A')"},
            {"name": "eB", "expr": "Excircle(A,B,C,vertex='B')"},
            {"name": "eC", "expr": "Excircle(A,B,C,vertex='C')"},
            {"name": "inc", "expr": "Incircle(A,B,C)"},
            {"name": "TA", "expr": "IncircleContactPoint(A,B,C,side='BC')"},
            {"name": "TB", "expr": "IncircleContactPoint(A,B,C,side='CA')"},
            {"name": "TC", "expr": "IncircleContactPoint(A,B,C,side='AB')"},
            {"name": "Q", "expr": "PointOnSegment(B,C,t)"},
        ],
        "constraints": [
            {"def": "Distance(EA,eA.center)", "value": 0},
            {"def": "Distance(EB,eB.center)", "value": 0},
            {"def": "Distance(EC,Q)", "value": "eA.radius"},
            {"def": "Distance(EC,eC.center)", "value": 0},
            {"def": "eC.radius", "value": "Distance(eC.center,A)"},
            {"def": "OnCircle(TA,inc)", "value": 0},
            {"def": "OnLine(TA,B,C)", "value": 0},
            {"def": "OnLine(TB,C,A)", "value": 0},
            {"def": "OnLine(TC,A,B)", "value": 0},
            {"def": "Distance(Q,eA)", "value": "Distance(Q,eB)"},
        ],
        "guards": [],
        "answer": "Distance(EA,EB)",
        "post_process": "",
    }


def test_extended_nonperiodic_unknown_composition_is_bit_exact() -> None:
    reference = _build(_extended_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(2026072902)
    probes = [
        [3.0, 0.0, 0.0, 4.0, 0.25],
        [3.0, 0.0, 6.0, 0.0, 0.5],  # collinear/degenerate centers
        [0.0, 0.0, 0.0, 4.0, 0.0],  # invalid source line
        [math.nextafter(3.0, 0.0), math.ulp(1.0), -2.0, 5.0, -1.0],
    ]
    probes.extend(
        [
            rng.uniform(2, 8),
            rng.uniform(-1, 1),
            rng.uniform(-2, 2),
            rng.uniform(2, 8),
            rng.uniform(-1, 2),
        ]
        for _ in range(256)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_external_centers_and_circles_are_bit_exact_across_all_vertices() -> None:
    reference = _build(_external_center_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(2026072904)
    probes = [
        [3.0, 0.0, 0.0, 4.0, 0.25],
        [3.0, 0.0, 6.0, 0.0, 0.5],  # collinear with a zero A-exradius
        [0.0, 0.0, 0.0, 4.0, 0.0],  # repeated A/B point
        [0.0, 0.0, 0.0, 0.0, -1.0],  # all points coincide
        [1.0, 0.0, 2.0, math.ulp(1.0), 2.0],  # nearly degenerate
        [math.nextafter(1.0, 0.0), math.ulp(1.0), -2.0, 5.0, -2.0],
    ]
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-2, 2),
        ]
        for _ in range(1024)
    )
    for values in probes:
        try:
            expected = reference.evaluate_float_residual(values).residual_vector
        except (ValueError, ZeroDivisionError):
            with pytest.raises((RawLibmpRuntimeFault, ZeroDivisionError)):
                raw.evaluate(values)
            continue
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def _intersection_problem(kind: str, selector: str) -> dict:
    second = {
        "ll": "other",
        "lc": "circle1",
        "cl": "ell",
        "cc": "circle2",
    }[kind]
    first = {"ll": "ell", "lc": "ell", "cl": "circle1", "cc": "circle1"}[kind]
    return {
        "task": "solve",
        "id": "unseen-intersection-composition",
        "variables": {"names": ["ax", "ay", "bx", "by", "ox", "oy", "r", "s"]},
        "construction": [
            {"name": "A", "expr": "Point(ax,ay)"},
            {"name": "B", "expr": "Point(bx,by)"},
            {"name": "O", "expr": "Point(ox,oy)"},
            {"name": "R", "expr": "Point(ox+3,oy-2)"},
            {"name": "ell", "expr": "Line(A,B)"},
            {"name": "other", "expr": "Line(O,R)"},
            {"name": "circle1", "expr": "Circle(O,r)"},
            {"name": "circle2", "expr": "Circle(A,s)"},
            {"name": "E", "expr": "Intersect(ell,circle1,n=1)"},
            {"name": "P", "expr": f"Intersect({first},{second},{selector})"},
        ],
        "constraints": [
            {"def": "Distance(P,O)", "value": 1},
            {"def": "P.x+P.y", "value": 0},
        ],
        "guards": [],
        "answer": "Distance(P,A)",
        "post_process": "",
    }


@pytest.mark.parametrize("kind", ["ll", "lc", "cl", "cc"])
@pytest.mark.parametrize("selector", ["n=1", "n=2", "near=R", "far=R", "exclude=E,n=1"])
def test_raw_intersections_are_bit_exact_in_unknown_compositions(kind: str, selector: str) -> None:
    if kind == "ll" and selector != "n=1":
        pytest.skip("a line-line intersection has one candidate")
    reference = _build(_intersection_problem(kind, selector))
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(f"{kind}:{selector}")
    probes = [
        [-10.0, 5.0, 10.0, 5.0, 0.0, 0.0, 5.0, 5.0],  # tangent
        [-10.0, 6.0, 10.0, 6.0, 0.0, 0.0, 5.0, 5.0],  # disjoint clamp
        [0.0, 0.0, 1.0, 2.0, 0.0, 0.0, 5.0, 5.0],
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 5.0, 5.0],  # invalid/coincident
    ]
    probes.extend(
        [
            rng.uniform(-5, 5),
            rng.uniform(-5, 5),
            rng.uniform(-5, 5),
            rng.uniform(-5, 5),
            rng.uniform(-5, 5),
            rng.uniform(-5, 5),
            rng.uniform(0.1, 8),
            rng.uniform(0.1, 8),
        ]
        for _ in range(128)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


@pytest.mark.parametrize("selector_kind", ["n", "near", "far", "exclude+n"])
def test_raw_intersection_branch_trace_matches_typed(selector_kind: str) -> None:
    selector_spec = {"n": 2}
    selector_types = None
    selector_values = {}
    if selector_kind in {"near", "far"}:
        selector_spec = {selector_kind: object()}
        selector_types = {selector_kind: "point2"}
        selector_values = {selector_kind: (9, 0)}
    elif selector_kind == "exclude+n":
        selector_spec = {"exclude": object(), "n": 1}
        selector_types = {"exclude": "point2", "n": "exact_int"}
        selector_values = {"exclude": (5, 0)}
    plan = compile_intersect_extension(
        ("line2", "circle2"), selector_spec, selector_operand_types=selector_types
    )
    raw_point, raw_trace = evaluate_raw_intersect(
        plan,
        (0, 1, 0),
        ((0, 0), 5),
        selector_values=selector_values,
    )

    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    from geosolver.geometry import Circle, Line, Point

    typed_values = {name: Point(*value) for name, value in selector_values.items()}
    typed = evaluate_intersect_extension(
        plan,
        Line(0, 1, 0),
        Circle(Point(0, 0), 5),
        point_factory=Point,
        **typed_values,
    )
    assert [
        _bits(to_float(value) if isinstance(value, tuple) else value) for value in raw_point
    ] == [
        _bits(typed.value.x),
        _bits(typed.value.y),
    ]
    assert raw_trace == typed.trace


def test_raw_intersection_optimizer_trace_is_bit_exact() -> None:
    reference = _build(_intersection_problem("lc", "near=R"))
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))

    def run(function):
        trace: list[tuple[bytes, ...]] = []

        def residual(values):
            trace.append(tuple(_bits(value) for value in values))
            return function(list(values))

        result = least_squares(
            residual,
            [-4.0, 1.0, 4.0, 1.0, 0.0, 0.0, 5.0, 3.0],
            bounds=([-10.0] * 6 + [0.1, 0.1], [10.0] * 8),
            max_nfev=48,
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


def _exact_unary_scalar_problem() -> dict:
    return {
        "task": "solve",
        "id": "unseen-exact-scalar-composition",
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "A", "expr": "Point(x,y)"},
        ],
        "constraints": [
            {"def": "Distance(O,A)", "value": "sqrt(17)"},
            {"def": "x+y", "value": "sin(1)+cos(1)"},
            {"def": "x*y", "value": "sqrt(1/2)"},
            {"def": "Area(O,A,Point(1,0))", "value": "cos(2)"},
            {"def": "sin(2)+x", "value": "sqrt(29)"},
        ],
        "guards": [],
        "answer": "Distance(O,A)",
        "post_process": "",
    }


def test_exact_unary_scalar_dag_is_bit_exact() -> None:
    reference = _build(_exact_unary_scalar_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(2026072903)
    probes = [
        [0.0, 0.0],
        [math.nextafter(0.0, 1.0), math.nextafter(0.0, -1.0)],
        [math.nextafter(1.0, 0.0), math.nextafter(-1.0, 0.0)],
    ]
    probes.extend([rng.uniform(-8, 8), rng.uniform(-8, 8)] for _ in range(512))
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_exact_unary_geometry_flow_is_admitted_without_identity_routing() -> None:
    problem = _exact_unary_scalar_problem()
    problem["construction"].append({"name": "B", "expr": "Point(sqrt(17),cos(1))"})
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    for values in ([0.0, -0.0], [math.ulp(0.0), -math.ulp(0.0)], [3.0, 4.0]):
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def _qualified_point_on_circle_problem() -> dict:
    return {
        "task": "solve",
        "id": "unseen-periodic-angle-composition",
        "variables": {"names": ["cx", "cy", "t", "ux", "uy"]},
        "construction": [
            {"name": "O", "expr": "Point(cx,cy)"},
            {"name": "X", "expr": "Point(ux,uy)"},
            {"name": "gamma", "expr": "Circle(O,4)"},
            {"name": "Q", "expr": "PointOnCircle(gamma,t)"},
        ],
        "constraints": [
            {"def": "Q.x", "value": 1},
            {"def": "Q.y", "value": 2},
            {"def": "Angle(Q,O,X)", "value": "pi/3"},
        ],
        "guards": [],
        "answer": "Distance(Q,X)",
        "post_process": "",
    }


def test_qualified_point_on_circle_consumers_are_bit_exact() -> None:
    reference = _build(_qualified_point_on_circle_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(2026072904)
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
    ]
    probes = [[0.0, 0.0, parameter, 3.0, 4.0] for parameter in periodic]
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-16, 16),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        ]
        for _ in range(1024)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


@pytest.mark.parametrize("consumer", ["Distance(Q,Line(O,X))"])
def test_point_on_circle_line_measurement_effect_edge_is_bit_exact(consumer: str) -> None:
    problem = _qualified_point_on_circle_problem()
    problem["constraints"] = [{"def": consumer, "value": 1}]
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    for values in (
        [0.0, 0.0, 0.0, 3.0, 4.0],
        [0.0, 0.0, math.nextafter(0.25, 0.0), 3.0, 4.0],
        [1.0, -2.0, math.ulp(0.0), -3.0, 5.0],
    ):
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [
            _bits(value) for value in expected
        ]


def test_qualified_point_on_circle_optimizer_trace_is_bit_exact() -> None:
    reference = _build(_qualified_point_on_circle_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))

    def run(function):
        trace: list[tuple[bytes, ...]] = []

        def residual(values):
            trace.append(tuple(_bits(value) for value in values))
            return function(list(values))

        result = least_squares(
            residual,
            [0.0, 0.0, 0.17, 3.0, 4.0],
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


@pytest.mark.parametrize("selector", ["near=Q", "far=Q", "exclude=Q,n=1"])
def test_point_on_circle_selector_flow_fails_closed_until_rounding_qualified(
    selector: str,
) -> None:
    problem = {
        "task": "solve",
        "id": "unseen-periodic-selector-composition",
        "variables": {"names": ["t", "h"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "gamma", "expr": "Circle(O,5)"},
            {"name": "Q", "expr": "PointOnCircle(gamma,t)"},
            {"name": "A", "expr": "Point(-10,h)"},
            {"name": "B", "expr": "Point(10,h)"},
            {"name": "ell", "expr": "Line(A,B)"},
            {"name": "P", "expr": f"Intersect(ell,gamma,{selector})"},
        ],
        "constraints": [{"def": "P.x", "value": 1}, {"def": "P.y", "value": 2}],
        "guards": [],
        "answer": "Distance(P,Q)",
        "post_process": "",
    }
    reference = _build(problem)
    with pytest.raises(UnsupportedRawLibmpBackend, match="Intersect"):
        compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))


@pytest.mark.parametrize("separation", [6.0, 10.0])
def test_exclude_only_intersection_preserves_multiple_candidate_list(
    separation: float,
) -> None:
    problem = {
        "task": "solve",
        "id": "unseen-exclude-with-multiple-survivors",
        "variables": {"names": ["y"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "C", "expr": f"Point({separation},0)"},
            {"name": "Q", "expr": "Point(0,y)"},
            {"name": "first", "expr": "Circle(O,5)"},
            {"name": "second", "expr": "Circle(C,5)"},
            {"name": "X", "expr": "Intersect(first,second,exclude=Q)"},
        ],
        "constraints": [
            {"def": "OnLine(O,C,X)", "value": 0},
            {"def": "Distance(O,C)", "value": 1},
        ],
        "guards": [],
        "answer": "Distance(O,C)",
        "post_process": "",
    }
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    for values in ([1.0], [math.ulp(0.0)], [1e-300]):
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]
        assert math.isnan(observed[0])
        assert math.isfinite(observed[1])


def test_subnormal_angle_quadrants_use_raw_mpf_signs() -> None:
    problem = {
        "task": "solve",
        "id": "unseen-subnormal-angle-composition",
        "variables": {"names": ["ax", "ay", "cx", "cy", "t", "r"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "A", "expr": "Point(ax,ay)"},
            {"name": "C", "expr": "Point(cx,cy)"},
            {"name": "base", "expr": "Line(O,A)"},
            {"name": "parallel", "expr": "ParallelLine(base,C)"},
            {"name": "D", "expr": "PointOnLine(parallel,t)"},
            {"name": "gamma", "expr": "Circle(O,r)"},
            {"name": "Q", "expr": "PointOnCircle(gamma,t)"},
        ],
        "constraints": [
            {"def": "Angle(A,O,C)", "value": 0},
            {"def": "Angle(D,C,O)", "value": 0},
            {"def": "Angle(Q,O,A)", "value": 0},
        ],
        "guards": [],
        "answer": "Angle(A,O,C)",
        "post_process": "",
    }
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    probes = []
    for scale in [1e-200, 1e-300, math.ulp(0.0)]:
        probes.extend(
            [scale, 0.0, cx, cy, 0.125, scale]
            for cx, cy in [
                (scale, scale),
                (-scale, scale),
                (-scale, -scale),
                (scale, -scale),
                (-scale, 0.0),
            ]
        )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def _incircle_contact_problem() -> dict:
    return {
        "task": "solve",
        "id": "unseen-incircle-contact-composition",
        "variables": {"names": ["bx", "by", "cx", "cy"]},
        "construction": [
            {"name": "A", "expr": "Point(0,0)"},
            {"name": "B", "expr": "Point(bx,by)"},
            {"name": "C", "expr": "Point(cx,cy)"},
            {"name": "D", "expr": "IncircleContactPoint(A,B,C,side='BC')"},
            {"name": "E", "expr": "IncircleContactPoint(A,B,C,side='CA')"},
            {"name": "F", "expr": "IncircleContactPoint(A,B,C,side='AB')"},
            {"name": "D0", "expr": "IncircleContactPoint(A,B,C,side=0)"},
            {"name": "E1", "expr": "IncircleContactPoint(A,B,C,side=1)"},
            {"name": "F2", "expr": "IncircleContactPoint(A,B,C,side=2)"},
        ],
        "constraints": [
            {"def": "D.x+D.y", "value": "D0.x+D0.y"},
            {"def": "E.x+E.y", "value": "E1.x+E1.y"},
            {"def": "F.x+F.y", "value": "F2.x+F2.y"},
            {"def": "OnLine(D,B,C)", "value": 0},
            {"def": "OnLine(E,C,A)", "value": 0},
            {"def": "OnLine(F,A,B)", "value": 0},
            {"def": "Distance(D,E)", "value": "Distance(E,F)"},
        ],
        "guards": [],
        "answer": "Distance(D,F)",
        "post_process": "",
    }


def test_incircle_contact_all_sides_fault_scope_and_subnormals_are_bit_exact() -> None:
    reference = _build(_incircle_contact_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(2026072905)
    probes = [
        [3.0, 0.0, 0.0, 4.0],
        [3.0, 0.0, 6.0, 0.0],  # collinear
        [0.0, 0.0, 0.0, 4.0],  # A == B: F is undefined, D/E remain usable
        [0.0, 0.0, 0.0, 0.0],  # all D/E/F undefined expression values
        [1e-300, 0.0, 0.0, 1e-300],
        [math.ulp(0.0), 0.0, 0.0, math.ulp(0.0)],
    ]
    probes.extend(
        [
            rng.uniform(2, 8),
            rng.uniform(-1, 1),
            rng.uniform(-2, 2),
            rng.uniform(2, 8),
        ]
        for _ in range(512)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_incircle_contact_optimizer_trace_is_bit_exact() -> None:
    reference = _build(_incircle_contact_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))

    def run(function):
        trace: list[tuple[bytes, ...]] = []

        def residual(values):
            trace.append(tuple(_bits(value) for value in values))
            return function(list(values))

        result = least_squares(
            residual,
            [3.0, 0.2, -0.3, 4.0],
            bounds=([-10.0] * 4, [10.0] * 4),
            max_nfev=48,
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


def test_expression_nan_sign_differs_from_construction_fault_nan() -> None:
    contact_reference = _build(_incircle_contact_problem())
    contact_raw = compile_raw_libmp_program(compile_typed_refnum_program(contact_reference.bundle))
    expression_expected = contact_reference.evaluate_float_residual(
        [0.0, 0.0, 0.0, 0.0]
    ).residual_vector
    expression_observed = contact_raw.evaluate([0.0, 0.0, 0.0, 0.0])
    assert [_bits(value) for value in expression_observed] == [
        _bits(value) for value in expression_expected
    ]
    assert all(_bits(value).hex() == "fff8000000000000" for value in expression_observed)

    fault_reference = _build(_problem())
    fault_raw = compile_raw_libmp_program(compile_typed_refnum_program(fault_reference.bundle))
    fault_values = [3.0, 4.0, -2.0, 5.0, 1.0, -3.0, 0.2, -1.0]
    construction_expected = fault_reference.evaluate_float_residual(fault_values).residual_vector
    construction_observed = fault_raw.evaluate(fault_values)
    assert [_bits(value) for value in construction_observed] == [
        _bits(value) for value in construction_expected
    ]
    assert all(_bits(value).hex() == "7ff8000000000000" for value in construction_observed)


def test_degenerate_incircle_and_perpendicular_bisector_match_frozen_scope() -> None:
    problem = {
        "task": "solve",
        "id": "unseen-degenerate-constructors",
        "variables": {"names": ["x", "y", "px", "py"]},
        "construction": [
            {"name": "O", "expr": "Point(x,y)"},
            {"name": "P", "expr": "Point(px,py)"},
            {"name": "inc", "expr": "Incircle(O,O,O)"},
            {"name": "pb", "expr": "PerpendicularBisector(O,O)"},
        ],
        "constraints": [
            {"def": "inc.radius", "value": 0},
            {"def": "Distance(inc.center,O)", "value": 0},
            {"def": "Distance(P,pb)", "value": 1},
            {"def": "Distance(pb,P)", "value": 1},
            {"def": "Distance(O,P)", "value": 2},
        ],
        "guards": [],
        "answer": "Distance(O,P)",
        "post_process": "",
    }
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    probes = [
        [0.0, 0.0, 3.0, 4.0],
        [1e-300, -1e-300, -2.0, 5.0],
        [math.ulp(0.0), -math.ulp(0.0), 1.0, 1.0],
    ]
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def _integer_over_float_line_problem() -> dict:
    return {
        "task": "solve",
        "id": "unseen-integer-over-float-line-normalization",
        "variables": {"names": ["h", "ox", "oy", "radius"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "A", "expr": "Point(5,0)"},
            {"name": "B", "expr": "Point(0,h)"},
            {"name": "ell", "expr": "Line(A,B)"},
            {"name": "F", "expr": "FootOfPerpendicular(O,ell)"},
            {"name": "C", "expr": "Point(ox,oy)"},
            {"name": "omega", "expr": "Circle(C,abs(radius))"},
        ],
        "constraints": [
            {"def": "Distance(O,F)", "value": 4},
            {"def": "IsTangent(omega,ell)", "value": 0},
        ],
        "guards": [],
        "answer": "Distance(O,F)",
        "post_process": "",
    }


def test_integer_over_float_line_normalization_is_bit_exact() -> None:
    reference = _build(_integer_over_float_line_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    rng = random.Random(0x1A7F10A7)
    probes = [
        [-2.0, 0.25, -1.5, 1.0],
        [-1.8718454986562816, -1.5004137869500882, 1.2891618694354667, -1.6539500250807122],
        [1.6301475043838023, 1.059563413048871, 1.8401934893582252, -0.4694463660131003],
    ]
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
        ]
        for _ in range(512)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_integer_over_float_line_optimizer_trace_is_identical() -> None:
    reference = _build(_integer_over_float_line_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))

    def run(function):
        trace: list[tuple[bytes, ...]] = []

        def residual(values):
            trace.append(tuple(_bits(value) for value in values))
            return function(list(values))

        result = least_squares(
            residual,
            [2.0, 0.5, -0.75, 1.25],
            bounds=([-10.0] * 4, [10.0] * 4),
            max_nfev=48,
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


def test_nonreal_scalar_values_fault_only_dependent_residuals() -> None:
    problem = {
        "task": "solve",
        "id": "unseen-local-nonreal-flow",
        "variables": {"names": ["t", "x"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "P", "expr": "Point(sqrt(t),0)"},
            {"name": "Q", "expr": "Point(x,1)"},
        ],
        "constraints": [
            {"def": "Distance(P,O)", "value": 1},
            {"def": "P.x + 1", "value": 2},
            {"def": "sqrt(t) + x", "value": 3},
            {"def": "Distance(Q,O)", "value": 4},
        ],
        "guards": [],
        "answer": "Distance(Q,O)",
        "post_process": "",
    }
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    for values in ([-1.0, 2.0], [-math.ulp(0.0), -3.0], [4.0, 2.0]):
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]
    assert all(_bits(value).hex() == "7ff8000000000000" for value in raw.evaluate([-1.0, 2.0])[:3])
    assert math.isfinite(raw.evaluate([-1.0, 2.0])[3])


def test_stored_angle_line_expression_preserves_symbolic_constraint_boundary() -> None:
    problem = {
        "task": "solve",
        "id": "unseen-angle-domain-rounding",
        "variables": {"names": ["a", "b", "x"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "P", "expr": "Point(x,0)"},
            {"name": "ell", "expr": "Line(a,b,0)"},
            {"name": "theta", "expr": "Angle(ell,ell)"},
        ],
        "constraints": [
            {"def": "theta", "value": 0},
            {"def": "theta + 1", "value": 1},
            {"def": "Distance(O,P)", "value": 2},
        ],
        "guards": [],
        "answer": "Distance(O,P)",
        "post_process": "",
    }
    reference = _build(problem)
    typed = compile_typed_refnum_program(reference.bundle)
    raw = compile_raw_libmp_program(typed)
    for values in ([3.0, 4.0, 2.0], [-3.0, 4.0, -2.0]):
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [
            _bits(value) for value in expected
        ]
