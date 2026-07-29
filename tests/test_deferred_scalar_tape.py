from __future__ import annotations

import math
import struct
import time

import pytest
from mpmath.libmp.libmpf import (
    from_float,
)

from geotarget.deferred_scalar_tape import (
    DeferredScalar,
    InputSlot,
    angle_acos,
    angle_atan2,
    area,
    compile_deferred_scalar,
    deferred,
    periodic_cos,
    periodic_sin,
)
from geotarget.raw_libmp_backend import (
    _as_float as raw_boundary_float,
)
from geotarget.raw_libmp_backend import (
    _Deferred as RawDeferred,
)
from geotarget.raw_libmp_backend import _evaluate_cached_periodic_tape
from geotarget.raw_libmp_backend import (
    _periodic_trig as raw_periodic_trig,
)


def _bits(value: float) -> bytes:
    return struct.pack(">d", value)


def _raw_boundary(expression, inputs):
    if isinstance(expression, InputSlot):
        return from_float(float(inputs[expression.index]))
    if isinstance(expression, int | float):
        return expression
    assert isinstance(expression, DeferredScalar)
    op, operands = expression.opcode, expression.operands
    if op == "area_points":
        points = tuple(
            tuple(_raw_boundary(coordinate, inputs) for coordinate in point)
            for point in operands[0]
        )
        return RawDeferred("area_points", (points,))
    if op in {"periodic_sin_turns", "periodic_cos_turns"}:
        return raw_periodic_trig(
            _raw_boundary(operands[0], inputs),
            cosine=op == "periodic_cos_turns",
        )
    return RawDeferred(op, tuple(_raw_boundary(item, inputs) for item in operands))


def _legacy_raw_float(expression, inputs) -> float:
    # This is deliberately only a legacy-raw topology regression oracle.  It
    # is not independent evidence of equivalence with the frozen evaluator,
    # because both sides share raw periodic helpers.
    return raw_boundary_float(_raw_boundary(expression, inputs))


def _op(name, *args):
    return deferred(name, *args)


def _deep_point_on_circle_intersection_expression():
    """POC -> Line -> Intersect(Line,Circle) -> Area/Angle scalar chain."""

    t = InputSlot(0)
    qx, qy = _op("mul", 5, periodic_cos(t)), _op("mul", 5, periodic_sin(t))
    ax, ay = 7, 2
    line_a = _op("sub", qy, ay)
    line_b = _op("sub", ax, qx)
    line_c = _op("sub", _op("mul", qx, ay), _op("mul", ax, qy))
    divisor = _op("add", _op("square", line_a), _op("square", line_b))
    distance_squared = _op("div", _op("square", line_c), divisor)
    multiplier = _op("sqrt", _op("div", _op("sub", 25, distance_squared), divisor))
    x0 = _op("div", _op("neg", _op("mul", line_a, line_c)), divisor)
    y0 = _op("div", _op("neg", _op("mul", line_b, line_c)), divisor)
    px = _op("add", x0, _op("mul", line_b, multiplier))
    py = _op("sub", y0, _op("mul", line_a, multiplier))
    on_circle = _op(
        "sub",
        _op("sqrt", _op("add", _op("square", px), _op("square", py))),
        5,
    )
    triangle_area = area(((0, 0), (qx, qy), (px, py)))
    angle = angle_atan2(
        _op("sub", _op("mul", qx, py), _op("mul", qy, px)),
        _op("add", _op("mul", qx, px), _op("mul", qy, py)),
    )
    return _op("add", _op("add", on_circle, triangle_area), angle)


@pytest.mark.parametrize(
    "parameter",
    [
        0.0,
        math.ulp(0.0),
        -math.ulp(0.0),
        math.nextafter(0.25, 0.0),
        0.25,
        math.nextafter(0.25, 1.0),
        math.nextafter(0.5, 0.0),
        0.5,
        math.nextafter(0.5, 1.0),
        float(2**52),
        -float(2**52),
        1e100,
        -1e100,
        float.fromhex("0x1.fffffffffffffp+1023"),
    ],
)
def test_periodic_modulo_matches_legacy_raw_boundary(parameter: float) -> None:
    # This only checks that the compiled tape preserves the legacy raw
    # topology.  Product equivalence is independently checked by generated
    # V15 problems against the frozen evaluator in
    # test_raw_periodic_generality.py.
    for expression in (periodic_sin(InputSlot(0)), periodic_cos(InputSlot(0))):
        tape = compile_deferred_scalar(expression)
        assert _bits(tape.evaluate_float([parameter])) == _bits(
            _legacy_raw_float(expression, [parameter])
        )


@pytest.mark.parametrize(
    "inputs",
    [
        [0.0, 1.0, -1.0],
        [math.ulp(0.0), -math.ulp(0.0), math.nextafter(1.0, 0.0)],
        [float.fromhex("0x1.fffffffffffffp+1023"), 1e-200, -0.75],
        [-1e200, 1e-200, math.nextafter(-1.0, 0.0)],
    ],
)
def test_scalar_ops_area_and_angles_match_legacy_raw_boundary(inputs) -> None:
    x, y, c = InputSlot(0), InputSlot(1), InputSlot(2)
    safe_square = _op("add", _op("square", _op("div", x, 3)), _op("square", y))
    expressions = [
        _op("add", _op("sub", x, y), _op("mul", c, 7)),
        _op("abs", _op("div", _op("neg", x), _op("add", _op("abs", y), 1))),
        _op("sqrt", safe_square),
        _op("pow_int", _op("add", _op("abs", c), 1), -3),
        area(((0, 0), (x, y), (_op("add", x, 1), _op("sub", y, 2)))),
        angle_atan2(y, x),
        angle_acos(c),
    ]
    for expression in expressions:
        expected = _legacy_raw_float(expression, inputs)
        observed = compile_deferred_scalar(expression).evaluate_float(inputs)
        assert _bits(observed) == _bits(expected)


@pytest.mark.parametrize(
    ("y", "x"),
    [(1.0, 0.0), (-1.0, 0.0), (0.0, 0.0), (math.nan, 1.0)],
)
def test_atan2_zero_axis_and_nan_do_not_evaluate_an_inactive_division(y, x) -> None:
    expression = angle_atan2(InputSlot(0), InputSlot(1))
    observed = compile_deferred_scalar(expression).evaluate_float([y, x])
    expected = _legacy_raw_float(expression, [y, x])
    if math.isnan(expected):
        assert math.isnan(observed)
    else:
        assert _bits(observed) == _bits(expected)


def test_raw_deferred_nodes_compile_without_import_coupling() -> None:
    expression = RawDeferred(
        "sqrt",
        (RawDeferred("add", (RawDeferred("square", (InputSlot(0),)), 4)),),
    )
    tape = compile_deferred_scalar(expression)
    assert tape.evaluate_float([3.0]) == math.sqrt(13.0)


def test_same_leaf_count_selector_branches_use_distinct_topology_tapes() -> None:
    """near/far/exclude branches may change topology without changing arity."""

    left, right = from_float(2.0), from_float(3.0)
    near_branch = RawDeferred("add", (left, right))
    far_branch = RawDeferred("mul", (left, right))
    exclude_branch = RawDeferred("sub", (left, right))
    program_identity = id(object())
    root_key = (17, 0)
    assert _evaluate_cached_periodic_tape(
        program_identity, root_key, near_branch
    ) == 5.0
    assert _evaluate_cached_periodic_tape(
        program_identity, root_key, far_branch
    ) == 6.0
    assert _evaluate_cached_periodic_tape(
        program_identity, root_key, exclude_branch
    ) == -1.0


@pytest.mark.parametrize(
    "parameter",
    [
        0.0,
        math.nextafter(0.25, 0.0),
        math.nextafter(0.25, 1.0),
        math.nextafter(0.5, 0.0),
        math.ulp(0.0),
        -math.ulp(0.0),
        1e100,
    ],
)
def test_deep_poc_intersect_chain_matches_legacy_raw_topology(parameter) -> None:
    expression = _deep_point_on_circle_intersection_expression()
    tape = compile_deferred_scalar(expression)
    assert _bits(tape.evaluate_float([parameter])) == _bits(
        _legacy_raw_float(expression, [parameter])
    )


def test_5000_callbacks_are_faster_than_reconstructing_sympy() -> None:
    x, y = InputSlot(0), InputSlot(1)
    expression = _op(
        "mul",
        periodic_cos(x),
        _op("abs", y),
    )
    tape = compile_deferred_scalar(expression)
    probes = [((index % 37) - 18.0, (index % 29) - 14.0) for index in range(5000)]

    for values in probes[:20]:
        tape.evaluate_float(values)
        _legacy_raw_float(expression, values)

    started = time.perf_counter()
    observed = [tape.evaluate_float(values) for values in probes]
    tape_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    expected = [_legacy_raw_float(expression, values) for values in probes]
    legacy_raw_elapsed = time.perf_counter() - started

    assert [_bits(value) for value in observed] == [_bits(value) for value in expected]
    assert tape_elapsed < legacy_raw_elapsed
