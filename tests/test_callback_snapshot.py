from __future__ import annotations

import copy
import math
import struct
import sys
import time
from pathlib import Path

import numpy as np

from geotarget.callback_snapshot import compile_callback_snapshot
from geotarget.compiled_evaluator import CompiledResidualEvaluator, compile_residual_plan
from geotarget.continuation import _load_frozen
from geotarget.fused_evaluation import install_fused_evaluation

PROBLEM = {
    "task": "solve",
    "id": "snapshot-routing-does-not-read-this",
    "variables": {"names": ["ax", "ay", "bx", "by", "px", "py"]},
    "construction": [
        {"name": "A", "expr": "Point(ax, ay)"},
        {"name": "B", "expr": "Point(bx, by)"},
        {"name": "P", "expr": "Point(px, py)"},
        {"name": "ell", "expr": "Line(A, B)"},
    ],
    "constraints": [
        {"def": "Distance(P, A)", "value": "Distance(P, ell)"},
        {"def": "Area(A, B, P)", "value": 1},
    ],
    "guards": ["AssumeNe(Distance(A, B), 0)"],
    "answer": "Distance(P, B)",
    "post_process": "",
}


def _runtime(name: str):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    return base._load_module(name, base.PRECISION_RUNTIME)


def _build(runtime, document):
    return runtime.build_source_case(
        document,
        callback_cap=4096,
        deadline=time.monotonic() + 120,
    )


def _bits(values) -> tuple[bytes, ...]:
    return tuple(struct.pack(">d", float(value)) for value in values)


def _assert_opaque_equal(expected, observed) -> None:
    assert _bits(expected.residual) == _bits(observed.residual)
    assert expected.finite is observed.finite
    assert expected.semantics_valid is observed.semantics_valid
    assert _bits([expected.violation]) == _bits([observed.violation])
    assert _bits(expected.violation_vector) == _bits(observed.violation_vector)


def test_snapshot_preserves_complete_callback_and_numeric_lane_boundaries() -> None:
    runtime = _runtime("geotarget_callback_snapshot_test_runtime")
    _case, reference_budget, _reference = _build(runtime, copy.deepcopy(PROBLEM))
    _case, candidate_budget, reference = _build(runtime, copy.deepcopy(PROBLEM))
    compilation = compile_residual_plan(reference, source_sha256="a" * 64)
    assert compilation.plan is not None
    assert compilation.plan.flat_tape_program is not None
    candidate = CompiledResidualEvaluator(reference, compilation.plan)
    snapshot = compile_callback_snapshot(candidate)
    assert snapshot is not None
    candidate.compiled_callback_snapshot = snapshot
    candidate_budget.evaluator = candidate
    metadata = snapshot.metadata()
    assert metadata["numeric_lanes"] == ["bf53_residual", "mp80_guard", "float_hard"]
    assert metadata["numeric_lanes_share_values"] is False
    assert metadata["problem_identity_read"] is False

    install_fused_evaluation(reference_budget)
    install_fused_evaluation(candidate_budget)
    probes = [
        [0.0, 0.0, 3.0, 4.0, 1.0, 2.0],
        [1.0, -2.0, 1.0, -2.0, 0.5, 0.25],
        [math.nextafter(1.0, math.inf), -1.0, 4.0, 2.0, -3.0, 8.0],
    ]
    for point in probes:
        expected = reference_budget(np.asarray(point, dtype=float))
        observed = candidate_budget(np.asarray(point, dtype=float))
        _assert_opaque_equal(expected, observed)


def test_snapshot_subnormal_requests_whole_callback_fallback() -> None:
    runtime = _runtime("geotarget_callback_snapshot_subnormal_runtime")
    _case, _budget, reference = _build(runtime, copy.deepcopy(PROBLEM))
    compilation = compile_residual_plan(reference, source_sha256="b" * 64)
    assert compilation.plan is not None
    candidate = CompiledResidualEvaluator(reference, compilation.plan)
    snapshot = compile_callback_snapshot(candidate)
    assert snapshot is not None
    assert snapshot.evaluate([math.nextafter(0.0, 1.0), 0.0, 3.0, 4.0, 1.0, 2.0]) is None


def test_snapshot_admission_is_invariant_under_problem_rename() -> None:
    runtime = _runtime("geotarget_callback_snapshot_rename_runtime")
    renamed = copy.deepcopy(PROBLEM)
    renamed["id"] = "unrelated-name"
    metadata = []
    for document, digest in ((PROBLEM, "c" * 64), (renamed, "d" * 64)):
        _case, _budget, reference = _build(runtime, copy.deepcopy(document))
        compilation = compile_residual_plan(reference, source_sha256=digest)
        assert compilation.plan is not None
        snapshot = compile_callback_snapshot(CompiledResidualEvaluator(reference, compilation.plan))
        assert snapshot is not None
        metadata.append(snapshot.metadata()["support_key_sha256"])
    assert metadata[0] == metadata[1]
