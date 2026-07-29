from __future__ import annotations

import math
import random
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from scipy.optimize import least_squares

from geotarget.continuation import _load_frozen
from geotarget.flat_tape_backend import (
    UnsupportedFlatTapeBackend,
    compile_flat_tape_program,
)
from geotarget.raw_libmp_backend import compile_raw_libmp_program
from geotarget.typed_refnum_ir import compile_typed_refnum_program


def _build(document):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_flat_tape_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=1024, deadline=time.monotonic() + 120
    )
    return evaluator


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _compile_flat(reference):
    typed = compile_typed_refnum_program(reference.bundle)
    raw = compile_raw_libmp_program(typed)
    return compile_flat_tape_program(typed, raw_semantic_gate=raw)


def _broad_problem() -> dict:
    return {
        "task": "solve",
        "id": "unknown-flat-tape-generated-composition",
        "variables": {
            "names": ["ax", "ay", "bx", "by", "px", "py", "radius", "t"]
        },
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "A", "expr": "Point(ax,ay)"},
            {"name": "B", "expr": "Point(bx,by)"},
            {"name": "P", "expr": "Point(px,py)"},
            {"name": "M", "expr": "Midpoint(A,B)"},
            {"name": "S", "expr": "PointOnSegment(A,B,t)"},
            {"name": "ell", "expr": "Line(A,B)"},
            {"name": "gamma", "expr": "Circle(O,abs(radius))"},
        ],
        "constraints": [
            {"def": "Distance(P,M)", "value": "Distance(A,B)+1"},
            {"def": "Distance(P,ell)", "value": "Distance(ell,S)"},
            {"def": "Distance(P,gamma)", "value": "Distance(gamma,S)"},
            {"def": "Area(A,S,P)", "value": 2},
            {"def": "Angle(A,P,B)", "value": "pi/3"},
            {"def": "gamma.center.x+gamma.center.y", "value": "gamma.radius"},
            {"def": "sqrt(abs(t))+sin(t)", "value": "cos(t)"},
        ],
        "guards": [],
        "answer": "Distance(P,M)",
        "post_process": "",
    }


def test_generated_broad_tape_is_reference_bit_exact_and_reuses_buffers() -> None:
    reference = _build(_broad_problem())
    flat = _compile_flat(reference)
    buffers = flat._buffers()
    buffer_ids = (
        id(buffers.scalars),
        id(buffers.point_x),
        id(buffers.line_a),
        id(buffers.circle_x),
    )
    probes = [
        [3.0, 0.0, 0.0, 4.0, -2.0, 5.0, 6.0, 0.25],
        [0.0, 0.0, 0.0, 0.0, 1.0, -1.0, 0.0, math.ulp(0.0)],
    ]
    rng = random.Random(2026072910)
    probes.extend(
        [
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-2, 2),
        ]
        for _ in range(1024)
    )
    for values in probes:
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = flat.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]
    assert buffer_ids == (
        id(flat._buffers().scalars),
        id(flat._buffers().point_x),
        id(flat._buffers().line_a),
        id(flat._buffers().circle_x),
    )


def test_deep_scalar_dag_executes_as_a_flat_tape_without_callback_recursion() -> None:
    expression = "x"
    for _ in range(180):
        expression = f"({expression}+1)"
    problem = {
        "task": "solve",
        "id": "unknown-deep-flat-dag",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": expression, "value": 180}],
        "guards": [],
        "answer": "x",
        "post_process": "",
    }
    reference = _build(problem)
    flat = _compile_flat(reference)
    assert flat.instruction_count >= 182
    for value in (-3.5, 0.0, math.ulp(0.0), 7.25):
        expected = reference.evaluate_float_residual([value]).residual_vector
        assert [_bits(item) for item in flat.evaluate([value])] == [
            _bits(item) for item in expected
        ]


def test_fanout_is_compiled_once_per_tape_and_is_bit_exact() -> None:
    constraints = [
        {"def": f"shared*{index}+shared", "value": index}
        for index in range(1, 65)
    ]
    problem = {
        "task": "solve",
        "id": "unknown-flat-fanout",
        "variables": {"names": ["x", "y"]},
        "construction": [{"name": "shared", "expr": "x+y"}],
        "constraints": constraints,
        "guards": [],
        "answer": "shared",
        "post_process": "",
    }
    reference = _build(problem)
    flat = _compile_flat(reference)
    assert sum(instruction.op.name == "ADD" for instruction in flat.construction_tape) == 1
    for values in ([0.0, -0.0], [3.25, -7.5], [math.ulp(0.0), -1.0]):
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = flat.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_unsupported_union_signature_is_rejected_without_identity_routing() -> None:
    problem = {
        "task": "solve",
        "id": "identity-cannot-enable-flat-intersection",
        "variables": {"names": ["h"]},
        "construction": [
            {"name": "A", "expr": "Point(-2,h)"},
            {"name": "B", "expr": "Point(2,h)"},
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "ell", "expr": "Line(A,B)"},
            {"name": "gamma", "expr": "Circle(O,1)"},
            {"name": "P", "expr": "Intersect(ell,gamma,exclude=A)"},
        ],
        "constraints": [{"def": "Distance(P,O)", "value": 1}],
        "guards": [],
        "answer": "h",
        "post_process": "",
    }
    typed = compile_typed_refnum_program(_build(problem).bundle)
    raw = compile_raw_libmp_program(typed)
    with pytest.raises(UnsupportedFlatTapeBackend, match="unsupported typed signature"):
        compile_flat_tape_program(typed, raw_semantic_gate=raw)


def test_flat_compiler_rejects_missing_or_mismatched_semantic_admission() -> None:
    typed = compile_typed_refnum_program(_build(_broad_problem()).bundle)
    with pytest.raises(UnsupportedFlatTapeBackend, match="raw semantic/effect admission"):
        compile_flat_tape_program(typed, raw_semantic_gate=object())  # type: ignore[arg-type]

    unknown_abi = replace(typed, semantic_abi="unknown/typed-abi-v999")
    raw = compile_raw_libmp_program(typed)
    with pytest.raises(UnsupportedFlatTapeBackend, match="typed semantic ABI"):
        compile_flat_tape_program(unknown_abi, raw_semantic_gate=raw)


def test_raw_gate_from_same_layout_but_different_dag_cannot_issue_token() -> None:
    def problem(offset: int) -> dict:
        return {
            "task": "solve",
            "id": f"unknown-provenance-{offset}",
            "variables": {"names": ["x"]},
            "construction": [{"name": "A", "expr": f"Point(x+{offset},0)"}],
            "constraints": [{"def": "A.x", "value": 1}],
            "guards": [],
            "answer": "A.x",
            "post_process": "",
        }

    first = compile_typed_refnum_program(_build(problem(1)).bundle)
    second = compile_typed_refnum_program(_build(problem(999)).bundle)
    raw_from_first = compile_raw_libmp_program(first)
    with pytest.raises(UnsupportedFlatTapeBackend, match="provenance"):
        compile_flat_tape_program(second, raw_semantic_gate=raw_from_first)


def test_symbolic_numeric_effect_flow_into_geometry_is_not_specialized() -> None:
    problem = {
        "task": "solve",
        "id": "unknown-symbolic-geometry-effect",
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "A", "expr": "Point(cos(1),sin(1))"},
            {"name": "B", "expr": "Point(x,y)"},
        ],
        "constraints": [{"def": "Distance(A,B)", "value": 1}],
        "guards": [],
        "answer": "Distance(A,B)",
        "post_process": "",
    }
    typed = compile_typed_refnum_program(_build(problem).bundle)
    raw = compile_raw_libmp_program(typed)
    with pytest.raises(UnsupportedFlatTapeBackend, match="symbolic geometry composition"):
        compile_flat_tape_program(typed, raw_semantic_gate=raw)


def test_normal_subnormal_boundary_delegates_to_qualified_raw_gate() -> None:
    reference = _build(_broad_problem())
    flat = _compile_flat(reference)
    values = [sys.float_info.min] * len(flat.variable_names)
    expected = reference.evaluate_float_residual(values).residual_vector
    observed = flat.evaluate(values)
    assert [_bits(value) for value in observed] == [_bits(value) for value in expected]
    assert (
        flat.metadata()["subnormal_input_policy"]
        == "raw_semantic_gate_value_class_fallback"
    )


def test_angle_scalar_composition_uses_bit_qualified_raw_backend() -> None:
    problem = {
        "task": "solve",
        "id": "unknown-generated-angle-scalar-composition",
        "variables": {"names": ["ax", "ay", "bx", "by"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "A", "expr": "Point(ax,ay)"},
            {"name": "B", "expr": "Point(bx,by)"},
        ],
        "constraints": [
            {"def": "Angle(A,O,B)+Angle(B,A,O)", "value": "pi"}
        ],
        "guards": [],
        "answer": "Distance(A,B)",
        "post_process": "",
    }
    typed = compile_typed_refnum_program(_build(problem).bundle)
    raw = compile_raw_libmp_program(typed)
    with pytest.raises(
        UnsupportedFlatTapeBackend, match="Angle scalar composition"
    ):
        compile_flat_tape_program(typed, raw_semantic_gate=raw)


def test_one_program_is_bit_exact_under_eight_thread_contention() -> None:
    reference = _build(_broad_problem())
    flat = _compile_flat(reference)
    inputs = [
        [
            1.0 + lane,
            -0.25 * lane,
            -2.0 + lane / 7,
            4.0 - lane / 9,
            lane / 3,
            -5.0 + lane,
            0.5 + lane,
            -0.75 + lane / 11,
        ]
        for lane in range(8)
    ]
    expected = [
        tuple(_bits(value) for value in reference.evaluate_float_residual(values).residual_vector)
        for values in inputs
    ]

    def exercise(lane: int) -> tuple[int, tuple[bytes, ...]]:
        observed: tuple[bytes, ...] = ()
        for _ in range(250):
            observed = tuple(_bits(value) for value in flat.evaluate(inputs[lane]))
            if observed != expected[lane]:
                return lane, observed
        return lane, observed

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(exercise, range(8)))
    assert [observed for lane, observed in results] == [expected[lane] for lane in range(8)]
    assert flat.metadata()["scratch_isolation"] == "thread_local_reused_per_thread"


@pytest.mark.parametrize(
    "initial",
    [
        [3.0, 0.25, -1.0, 4.0, -2.0, 5.0, 6.0, 0.2],
        [math.ulp(0.0), -0.0, 4.0, math.ulp(1.0), 2.0, -3.0, -5.0, math.ulp(0.0)],
    ],
)
def test_broad_geometry_optimizer_replay_is_observation_identical(initial) -> None:
    reference = _build(_broad_problem())
    flat = _compile_flat(reference)

    def run(function):
        trace = []

        def residual(values):
            result = function(list(values))
            vector = result.residual_vector if hasattr(result, "residual_vector") else result
            trace.append(
                (
                    tuple(_bits(value) for value in values),
                    tuple(_bits(value) for value in vector),
                )
            )
            return vector

        outcome = least_squares(residual, initial, method="trf", max_nfev=24)
        return outcome, trace

    expected, expected_trace = run(reference.evaluate_float_residual)
    observed, observed_trace = run(flat.evaluate)
    assert observed_trace == expected_trace
    assert (observed.status, observed.nfev) == (expected.status, expected.nfev)
    assert tuple(_bits(value) for value in observed.x) == tuple(
        _bits(value) for value in expected.x
    )


def test_flat_tape_warm_callback_microbenchmark() -> None:
    reference = _build(_broad_problem())
    flat = _compile_flat(reference)
    values = [3.0, 0.25, -1.0, 4.0, -2.0, 5.0, 6.0, 0.2]
    for _ in range(32):
        reference.evaluate_float_residual(values)
        flat.evaluate(values)

    def elapsed(function, count: int) -> float:
        started = time.perf_counter()
        for _ in range(count):
            function(values)
        return time.perf_counter() - started

    count = 2_000
    reference_seconds = elapsed(reference.evaluate_float_residual, count)
    flat_seconds = elapsed(flat.evaluate, count)
    assert flat_seconds < reference_seconds
