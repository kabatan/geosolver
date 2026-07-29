from __future__ import annotations

import copy
import struct
import sys
import time
from pathlib import Path

import numpy as np

from geotarget.continuation import _load_frozen
from geotarget.fused_evaluation import (
    FUSION_SCHEMA_VERSION,
    REFERENCE_CALL_SHA256,
    install_fused_evaluation,
)

PROBLEM = {
    "task": "solve",
    "id": "general-fused-evaluation-regression",
    "variables": {"names": ["tB", "tC"]},
    "construction": [
        {"name": "O", "expr": "Point(0, 0)"},
        {"name": "Gamma", "expr": "Circle(O, 25)"},
        {"name": "A", "expr": "Point(25, 0)"},
        {"name": "B", "expr": "PointOnCircle(Gamma, tB)"},
        {"name": "C", "expr": "PointOnCircle(Gamma, tC)"},
    ],
    "constraints": [
        {"def": "Distance(A, B)", "value": 14},
        {"def": "Distance(B, C)", "value": "Distance(A, C)"},
    ],
    "guards": [
        "AssumeNe(Distance(B, C), 0)",
        "AssumeGt(Area(A, B, C), 0)",
    ],
    "answer": "Distance(A, C)",
    "post_process": "",
}


def _runtime(name: str):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    return base._load_module(name, base.PRECISION_RUNTIME)


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _result_bits(result):
    return {
        "residual": tuple(_bits(value) for value in result.residual),
        "finite": result.finite,
        "semantics_valid": result.semantics_valid,
        "violation": _bits(result.violation),
        "violation_vector": tuple(_bits(value) for value in result.violation_vector),
    }


def test_fused_budget_is_bit_identical_for_regular_and_invalid_points() -> None:
    runtime = _runtime("geotarget_test_fused_evaluation_runtime")
    _case, reference_budget, _evaluator = runtime.build_source_case(
        copy.deepcopy(PROBLEM), callback_cap=512, deadline=time.monotonic() + 120
    )
    _case, fused_budget, _evaluator = runtime.build_source_case(
        copy.deepcopy(PROBLEM), callback_cap=512, deadline=time.monotonic() + 120
    )
    original_call = type(reference_budget).__call__
    metadata = install_fused_evaluation(fused_budget)

    assert metadata["schema_version"] == FUSION_SCHEMA_VERSION
    assert metadata["reference_call_sha256"] == REFERENCE_CALL_SHA256
    assert metadata["case_specific_routing"] is False
    assert metadata["problem_identity_read"] is False

    points = (
        np.asarray([0.25, 0.75]),
        np.asarray([-4.0, 3.0]),
        np.asarray([0.0, 0.0]),
        np.asarray([np.nan, 1.0]),
        np.asarray([np.inf, -np.inf]),
    )
    for point in points:
        expected = original_call(reference_budget, point)
        observed = fused_budget(point)
        assert _result_bits(observed) == _result_bits(expected)

    for counter in ("callbacks", "finite", "invalid", "guard_failed"):
        assert getattr(fused_budget, counter) == getattr(reference_budget, counter)
    assert _bits(fused_budget.best_norm) == _bits(reference_budget.best_norm)


def test_fused_install_is_idempotent_for_persistent_workers() -> None:
    runtime = _runtime("geotarget_test_fused_evaluation_idempotent_runtime")
    _case, budget, _evaluator = runtime.build_source_case(
        copy.deepcopy(PROBLEM), callback_cap=32, deadline=time.monotonic() + 120
    )
    first = install_fused_evaluation(budget)
    installed_call = type(budget).__call__
    second = install_fused_evaluation(budget)

    assert first == second
    assert type(budget).__call__ is installed_call
