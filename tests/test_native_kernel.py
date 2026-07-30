from __future__ import annotations

import math
import random
import struct
import sys
import time
from pathlib import Path

from geotarget.compiled_evaluator import compile_residual_plan
from geotarget.continuation import _load_frozen
from geotarget.native_kernel import native_capability

PROBLEM = {
    "task": "solve",
    "id": "native-admission-does-not-read-this",
    "variables": {"names": ["ax", "ay", "bx", "by", "px", "py", "t"]},
    "construction": [
        {"name": "A", "expr": "Point(ax, ay)"},
        {"name": "B", "expr": "Point(bx, by)"},
        {"name": "P", "expr": "Point(px, py)"},
        {"name": "M", "expr": "Midpoint(A, B)"},
        {"name": "S", "expr": "PointOnSegment(A, B, t)"},
        {"name": "ell", "expr": "Line(A, B)"},
    ],
    "constraints": [
        {"def": "Distance(P, A)", "value": "Distance(P, B)"},
        {"def": "Distance(P, M)", "value": "Distance(P, S)"},
        {"def": "Distance(P, ell)", "value": 2},
        {"def": "Area(A, B, P)", "value": 4},
    ],
    "guards": [],
    "answer": "Distance(P, M)",
    "post_process": "",
}


def _build(document=PROBLEM):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_native_kernel_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document,
        callback_cap=4096,
        deadline=time.monotonic() + 120,
    )
    return evaluator


def _bits(values) -> tuple[bytes, ...]:
    return tuple(struct.pack(">d", float(value)) for value in values)


def test_native_flat_kernel_is_bitwise_and_falls_back_by_value_class() -> None:
    capability = native_capability()
    assert capability["available"] is True
    reference = _build()
    compilation = compile_residual_plan(reference, source_sha256="a" * 64)
    assert compilation.plan is not None
    native = compilation.plan.native_program
    assert native is not None
    assert compilation.plan.metadata()["mode"] == "native_flat_tape_bf53"
    assert native.metadata()["fastmath"] is False
    assert native.metadata()["problem_identity_read"] is False

    generator = random.Random(20260731)
    native_completed = 0
    for _ in range(1024):
        values = [generator.uniform(-8.0, 8.0) for _ in range(7)]
        raw_native = native.implementation.evaluate(values)
        if raw_native is None:
            continue
        native_completed += 1
        expected = reference.evaluate_float_residual(values).residual_vector
        assert _bits(raw_native) == _bits(expected)
        assert _bits(native.evaluate(values)) == _bits(expected)
    assert native_completed >= 900

    boundary_points = [
        [-0.0, 1.0, 3.0, 4.0, 1.0, 2.0, 0.5],
        [math.nextafter(0.0, 1.0), 1.0, 3.0, 4.0, 1.0, 2.0, 0.5],
        [math.inf, 1.0, 3.0, 4.0, 1.0, 2.0, 0.5],
        [math.nan, 1.0, 3.0, 4.0, 1.0, 2.0, 0.5],
    ]
    for values in boundary_points:
        assert native.implementation.evaluate(values) is None
        assert _bits(native.evaluate(values)) == _bits(
            compilation.plan.flat_tape_program.evaluate(values)
        )


def test_native_admission_rejects_periodic_tape_as_a_whole() -> None:
    problem = {
        **PROBLEM,
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "gamma", "expr": "Circle(O, 2)"},
            {"name": "P", "expr": "PointOnCircle(gamma, t)"},
        ],
        "constraints": [{"def": "Distance(O, P)", "value": 2}],
    }
    compilation = compile_residual_plan(_build(problem), source_sha256="b" * 64)
    assert compilation.plan is not None
    assert compilation.plan.native_program is None
