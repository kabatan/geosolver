from __future__ import annotations

import math
import random
import struct
import sys
import time
from pathlib import Path

import pytest
from raw_exact_unary_fixtures import (
    DEGENERATE_PROBES,
    EXACT_UNARY_PROBES,
    exact_unary_composition_problem,
    exact_unary_degenerate_problem,
)
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
    runtime = base._load_module("geotarget_exact_unary_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )
    return evaluator


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _assert_bit_exact(reference, raw, probes) -> None:
    for values in probes:
        expected = reference.evaluate_float_residual(list(values)).residual_vector
        observed = raw.evaluate(list(values))
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_exact_unary_construction_six_consumer_structures_are_bit_exact() -> None:
    problem = exact_unary_composition_problem()
    problem["construction"].append({"name": "s_again", "expr": "sqrt(2)"})
    problem["constraints"].append({"def": "s-s_again", "value": 0})
    reference = _build(problem)
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    # Structurally identical input-free exact expressions share one compiled
    # node even when authored as distinct constructions.
    assert sum(node.opcode == "Sqrt" for node in raw.nodes) == 1

    probes = list(EXACT_UNARY_PROBES)
    probes.extend(
        [
            (0.0, -0.0),
            (-0.0, math.ulp(0.0)),
            (math.ulp(0.0), -math.ulp(0.0)),
            (math.nextafter(0.0, -1.0), math.nextafter(0.0, 1.0)),
        ]
    )
    rng = random.Random(2026072909)
    probes.extend((rng.uniform(-8, 8), rng.uniform(-8, 8)) for _ in range(1024))
    _assert_bit_exact(reference, raw, probes)


def test_exact_unary_cancellation_preserves_construction_fault_scope() -> None:
    reference = _build(exact_unary_degenerate_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    _assert_bit_exact(reference, raw, DEGENERATE_PROBES)
    assert all(math.isnan(value) for value in raw.evaluate([0.0]))


def test_exact_unary_large_downstream_dag_fails_closed_by_structure() -> None:
    construction = [{"name": "P0", "expr": "Point(sqrt(2),0)"}]
    construction.extend(
        {"name": f"P{index}", "expr": f"Point(P{index - 1}.x+1,0)"}
        for index in range(1, 40)
    )
    problem = {
        "task": "solve",
        "id": "unknown-large-exact-unary-dag",
        "variables": {"names": ["x"]},
        "construction": construction,
        "constraints": [{"def": "Distance(P0,P39)", "value": "x"}],
        "guards": [],
        "answer": "x",
        "post_process": "",
    }
    typed = compile_typed_refnum_program(_build(problem).bundle)
    with pytest.raises(UnsupportedRawLibmpBackend, match="resource cap"):
        compile_raw_libmp_program(typed)


def test_exact_unary_construction_optimizer_trace_and_endpoint_are_bit_exact() -> None:
    reference = _build(exact_unary_composition_problem())
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))

    def run(function):
        trace: list[tuple[bytes, ...]] = []

        def residual(values):
            trace.append(tuple(_bits(value) for value in values))
            return function(list(values))

        result = least_squares(
            residual,
            [0.75, -0.5],
            bounds=([-10.0, -10.0], [10.0, 10.0]),
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
