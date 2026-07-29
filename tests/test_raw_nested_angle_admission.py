from __future__ import annotations

import math
import random
import struct
import sys
import time
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import least_squares

from geotarget.continuation import _load_frozen
from geotarget.raw_libmp_backend import (
    UnsupportedRawLibmpBackend,
    compile_raw_libmp_program,
)
from geotarget.typed_refnum_ir import compile_typed_refnum_program

_CONSUMERS = (
    "{angle} + 1",
    "2 * {angle}",
    "{angle} / 2 + 1",
    "{angle} ** 2",
    "sin({angle})",
    "cos({angle})",
    "-{angle}",
    "+{angle}",
    "abs({angle} - 1)",
    "sqrt({angle})",
)


def _build(document):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module(
        "geotarget_nested_angle_test_runtime", base.PRECISION_RUNTIME
    )
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )
    return evaluator


def _problem(*, kind: str, expressions: tuple[str, ...]) -> dict:
    if kind == "ppp":
        names = ["ax", "ay", "bx", "by", "cx", "cy"]
        construction = [
            {"name": "A", "expr": "Point(ax, ay)"},
            {"name": "B", "expr": "Point(bx, by)"},
            {"name": "C", "expr": "Point(cx, cy)"},
        ]
        angle = "Angle(B, A, C)"
    elif kind == "ll":
        names = ["ax", "ay", "bx", "by"]
        construction = [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "A", "expr": "Point(ax, ay)"},
            {"name": "B", "expr": "Point(bx, by)"},
            {"name": "ell", "expr": "Line(O, A)"},
            {"name": "axis", "expr": "Line(O, B)"},
        ]
        angle = "Angle(ell, axis)"
    else:  # pragma: no cover - test helper misuse
        raise AssertionError(kind)
    return {
        "task": "solve",
        # Deliberately constant: admission must depend on expression semantics,
        # never a benchmark identity or a known corpus shape.
        "id": "unknown-generated-angle-composition",
        "variables": {"names": names},
        "construction": construction,
        "constraints": [
            {"def": expression.format(angle=angle), "value": 0}
            for expression in expressions
        ],
        "guards": [],
        "answer": "Distance(A, B)",
        "post_process": "",
    }


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _compiled(problem: dict):
    reference = _build(problem)
    typed = compile_typed_refnum_program(reference.bundle)
    return reference, compile_raw_libmp_program(typed)


@pytest.mark.parametrize("kind", ["ppp", "ll"])
def test_generated_safe_scalar_closure_is_reference_bit_exact(kind: str) -> None:
    """Exercise 10 consumers x 1,500 unknown geometries for each Angle form."""

    reference, raw = _compiled(_problem(kind=kind, expressions=_CONSUMERS))
    rng = random.Random(2026072901 if kind == "ppp" else 2026072902)
    width = 6 if kind == "ppp" else 4
    for _ in range(1_500):
        values = [rng.uniform(-32.0, 32.0) for _ in range(width)]
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [
            _bits(value) for value in expected
        ]


@pytest.mark.parametrize(
    ("kind", "values"),
    [
        ("ppp", [0.0, 0.0, -1.0, 2.0**-500, -1.0, -(2.0**-500)]),
        ("ppp", [0.0, 0.0, -1.0, 0.0, 1.0, 2.0**-52]),
        ("ppp", [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        ("ll", [-1.0, 2.0**-500, -1.0, -(2.0**-500)]),
        ("ll", [1.0, 0.0, 1.0, 2.0**-52]),
    ],
)
def test_nested_angle_boundaries_and_faults_match_reference(
    kind: str, values: list[float]
) -> None:
    reference, raw = _compiled(_problem(kind=kind, expressions=_CONSUMERS))
    expected = reference.evaluate_float_residual(values).residual_vector
    observed = raw.evaluate(values)
    assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


@pytest.mark.parametrize("kind", ["ppp", "ll"])
def test_nested_angle_optimizer_trace_matches_reference(kind: str) -> None:
    expression = "cos({angle}) + sin({angle}) / 3"
    reference, raw = _compiled(_problem(kind=kind, expressions=(expression,)))
    initial = (
        np.array([0.2, -0.3, -1.4, 0.6, 1.1, -0.8])
        if kind == "ppp"
        else np.array([-1.4, 0.6, 1.1, -0.8])
    )

    def solve(function):
        trace: list[tuple[bytes, ...]] = []

        def recorded(values):
            residual = np.asarray(function(values), dtype=float)
            trace.append(tuple(_bits(value) for value in residual))
            return residual

        result = least_squares(
            recorded,
            initial,
            method="trf",
            ftol=1e-12,
            xtol=1e-12,
            gtol=1e-12,
            max_nfev=64,
        )
        return result, trace

    expected, expected_trace = solve(
        lambda values: reference.evaluate_float_residual(values).residual_vector
    )
    observed, observed_trace = solve(raw.evaluate)
    assert observed_trace == expected_trace
    assert observed.status == expected.status
    assert observed.nfev == expected.nfev
    assert observed.njev == expected.njev
    assert [_bits(value) for value in observed.x] == [
        _bits(value) for value in expected.x
    ]
    assert [_bits(value) for value in observed.fun] == [
        _bits(value) for value in expected.fun
    ]
    assert _bits(observed.cost) == _bits(expected.cost)


def test_safe_scalar_construction_alias_is_admitted() -> None:
    problem = _problem(kind="ppp", expressions=("theta + 1",))
    problem["construction"].append(
        {"name": "theta", "expr": "Angle(B, A, C)"}
    )
    reference, raw = _compiled(problem)
    values = [0.0, 0.0, -2.0, 1.0, -3.0, -4.0]
    assert [_bits(value) for value in raw.evaluate(values)] == [
        _bits(value)
        for value in reference.evaluate_float_residual(values).residual_vector
    ]


@pytest.mark.parametrize(
    "construction",
    [
        {"name": "P", "expr": "Point(Angle(B,A,C), 0)"},
        {"name": "circle", "expr": "Circle(A, Angle(B,A,C))"},
        {"name": "line", "expr": "Line(Angle(B,A,C), 1, 0)"},
        {"name": "P", "expr": "PointOnLine(line, Angle(B,A,C))"},
    ],
)
def test_geometry_consumers_fail_closed_without_problem_identity(
    construction: dict,
) -> None:
    problem = _problem(kind="ppp", expressions=("Distance(A, B)",))
    if construction["expr"].startswith("PointOnLine"):
        problem["construction"].extend(
            [
                {"name": "line", "expr": "Line(A, B)"},
                construction,
            ]
        )
    else:
        problem["construction"].append(construction)
    typed = compile_typed_refnum_program(_build(problem).bundle)
    with pytest.raises(UnsupportedRawLibmpBackend, match="Angle composition"):
        compile_raw_libmp_program(typed)


def test_degenerate_angle_fault_is_constraint_local() -> None:
    problem = _problem(
        kind="ppp",
        expressions=("sin(Angle(B,A,C))", "Distance(B,C)"),
    )
    reference, raw = _compiled(problem)
    values = [1.0, 1.0, 1.0, 1.0, 4.0, 5.0]
    expected = reference.evaluate_float_residual(values).residual_vector
    observed = raw.evaluate(values)
    assert math.isnan(observed[0]) and math.isnan(expected[0])
    assert _bits(observed[1]) == _bits(expected[1])


def test_constraint_side_root_angle_remains_qualified_and_reference_bit_exact() -> None:
    reference, raw = _compiled(
        _problem(kind="ppp", expressions=("Angle(B, A, C)",))
    )
    probes = [
        [0.0, 0.0, 3.0, 0.0, 1.0, 4.0],
        [0.0, 0.0, -2.0, 1.0, 3.0, -4.0],
    ]
    rng = random.Random(20260729)
    probes.extend(
        [[rng.uniform(-8, 8) for _ in range(6)] for _ in range(64)]
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [
            _bits(value) for value in expected
        ]
