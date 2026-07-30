from __future__ import annotations

import math
import random
import struct
import sys
import time
from pathlib import Path

from geotarget.continuation import _load_frozen
from geotarget.flat_tape_backend import compile_flat_tape_program
from geotarget.raw_libmp_backend import compile_raw_libmp_program
from geotarget.typed_refnum_ir import compile_typed_refnum_program

PROBLEM = {
    "task": "solve",
    "id": "triangle-center-flat-qualification",
    "variables": {"names": ["ax", "ay", "bx", "by", "cx", "cy"]},
    "construction": [
        {"name": "A", "expr": "Point(ax, ay)"},
        {"name": "B", "expr": "Point(bx, by)"},
        {"name": "C", "expr": "Point(cx, cy)"},
        {"name": "U", "expr": "Circumcenter(A, B, C)"},
        {"name": "omega", "expr": "Circumcircle(A, B, C)"},
        {"name": "H", "expr": "Orthocenter(A, B, C)"},
        {"name": "G", "expr": "Centroid(A, B, C)"},
        {"name": "I", "expr": "Incenter(A, B, C)"},
        {"name": "iota", "expr": "Incircle(A, B, C)"},
    ],
    "constraints": [
        {"def": "Distance(U, A)", "value": "Distance(U, C)"},
        {"def": "Distance(A, omega)", "value": 0},
        {"def": "Distance(H, G)", "value": "Distance(G, U)"},
        {"def": "Distance(I, iota.center)", "value": 0},
        {"def": "iota.radius", "value": "Distance(I, Line(A, B))"},
    ],
    "guards": [],
    "answer": "Distance(U, I)",
    "post_process": "",
}


def _build(document=PROBLEM):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_flat_center_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document,
        callback_cap=4096,
        deadline=time.monotonic() + 120,
    )
    typed = compile_typed_refnum_program(evaluator.bundle)
    raw = compile_raw_libmp_program(typed)
    return evaluator, compile_flat_tape_program(typed, raw_semantic_gate=raw)


def _bits(values) -> tuple[bytes, ...]:
    return tuple(struct.pack(">d", float(value)) for value in values)


def test_triangle_centers_and_circles_are_bitwise_qualified() -> None:
    reference, flat = _build()
    generator = random.Random(2026073101)
    probes = [
        [0.0, 0.0, 3.0, 0.0, 0.0, 4.0],
        [0.0, 0.0, 1.0, 1.0, 2.0, 2.0],
        [math.nextafter(0.0, 1.0), 0.0, 3.0, 0.0, 0.0, 4.0],
    ]
    probes.extend([generator.uniform(-8.0, 8.0) for _ in range(6)] for _ in range(1024))
    for point in probes:
        expected = reference.evaluate_float_residual(point).residual_vector
        assert _bits(flat.evaluate(point)) == _bits(expected)
    metadata = flat.metadata()
    assert {
        "CIRCUMCENTER",
        "CIRCUMCIRCLE",
        "ORTHOCENTER",
        "CENTROID",
        "INCENTER",
        "INCIRCLE",
    }.issubset(metadata["opcodes"])


def test_selector_free_line_intersection_is_bitwise_qualified() -> None:
    problem = {
        "task": "solve",
        "id": "line-intersect-flat-qualification",
        "variables": {"names": ["ax", "ay", "bx", "by", "cx", "cy", "dx", "dy"]},
        "construction": [
            {"name": "A", "expr": "Point(ax, ay)"},
            {"name": "B", "expr": "Point(bx, by)"},
            {"name": "C", "expr": "Point(cx, cy)"},
            {"name": "D", "expr": "Point(dx, dy)"},
            {"name": "ell", "expr": "Line(A, B)"},
            {"name": "m", "expr": "Line(C, D)"},
            {"name": "P", "expr": "Intersect(ell, m)"},
        ],
        "constraints": [
            {"def": "Distance(P, A)", "value": 2},
            {"def": "Distance(P, C)", "value": 3},
        ],
        "guards": [],
        "answer": "Distance(A, C)",
        "post_process": "",
    }
    reference, flat = _build(problem)
    generator = random.Random(2026073102)
    probes = [
        [0.0, 0.0, 4.0, 0.0, 2.0, -3.0, 2.0, 5.0],
        [0.0, 0.0, 4.0, 0.0, 1.0, 0.0, 5.0, 0.0],
    ]
    probes.extend([generator.uniform(-8.0, 8.0) for _ in range(8)] for _ in range(1024))
    for point in probes:
        expected = reference.evaluate_float_residual(point).residual_vector
        assert _bits(flat.evaluate(point)) == _bits(expected)
    assert "INTERSECT_LL" in flat.metadata()["opcodes"]
