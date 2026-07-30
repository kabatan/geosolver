"""Candidate-private QPoint reflection opcode for exact-coordinate replay."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
import threading
from typing import Any, Mapping, Sequence


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
ORIGINAL_CANDIDATE = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/exact_coordinate_replay/candidate.py"
)
ORIGINAL_QQBAR = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-004/qqbar_exact_replay/qqbar_worker.jl"
)
EXPECTED_ORIGINAL_CANDIDATE_SHA256 = "e0f24e605e7e7211d134ddea66e66adbb89307148a8f03c1afebd4a2c969c66f"
EXPECTED_ORIGINAL_QQBAR_SHA256 = "3ac6415600da77f8748a11d15fa47eb3dcb9f8deada375388fc762a155df0b4a"

_LINE_REFLECT = """function qreflect(value::QPoint, mirror::QLine)
  foot = qfoot(value, mirror)
  return qsub(qscale(foot, 2), value)
end
"""
_POINT_REFLECT = """
function qreflect(value::QPoint, center::QPoint)
  return qsub(qscale(center, 2), value)
end
"""
_LOCK = threading.RLock()


class ReflectIntegrationError(RuntimeError):
    """The frozen exact-coordinate replay seam changed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def verify_dependencies() -> dict[str, str]:
    observed = {
        str(ORIGINAL_CANDIDATE): _sha256(ORIGINAL_CANDIDATE),
        str(ORIGINAL_QQBAR): _sha256(ORIGINAL_QQBAR),
    }
    expected = {
        str(ORIGINAL_CANDIDATE): EXPECTED_ORIGINAL_CANDIDATE_SHA256,
        str(ORIGINAL_QQBAR): EXPECTED_ORIGINAL_QQBAR_SHA256,
    }
    if observed != expected:
        raise ReflectIntegrationError("frozen exact-coordinate dependency changed")
    return observed


verify_dependencies()
ORIGINAL = _load("geotarget_exact_reflect_original_candidate", ORIGINAL_CANDIDATE)
_ORIGINAL_EXTENDED_WORKER_SOURCE = ORIGINAL._extended_worker_source


def extended_worker_source() -> str:
    """Insert only the typed QPoint,QPoint overload after the line overload."""

    verify_dependencies()
    source = _ORIGINAL_EXTENDED_WORKER_SOURCE()
    if source.count(_LINE_REFLECT) != 1 or _POINT_REFLECT in source:
        raise ReflectIntegrationError("QQBar qreflect seam changed")
    return source.replace(_LINE_REFLECT, _LINE_REFLECT + _POINT_REFLECT, 1)


def remove_point_reflect_overload(source: str) -> str:
    if source.count(_POINT_REFLECT) != 1:
        raise ReflectIntegrationError("private point reflection overload is not unique")
    return source.replace(_POINT_REFLECT, "", 1)


def certify_exact_coordinate_witness(
    document: Mapping[str, Any],
    coordinate_lane_a: Sequence[str],
    coordinate_lane_b: Sequence[str],
    target_lane_a: str,
    target_lane_b: str,
    **kwargs,
) -> dict[str, Any]:
    """Delegate unchanged authority logic with one private source insertion."""

    verify_dependencies()
    with _LOCK:
        previous = ORIGINAL._extended_worker_source
        ORIGINAL._extended_worker_source = extended_worker_source
        try:
            return ORIGINAL.certify_exact_coordinate_witness(
                document,
                coordinate_lane_a,
                coordinate_lane_b,
                target_lane_a,
                target_lane_b,
                **kwargs,
            )
        finally:
            ORIGINAL._extended_worker_source = previous


def closure_manifest() -> dict[str, object]:
    patched = extended_worker_source()
    original = _ORIGINAL_EXTENDED_WORKER_SOURCE()
    return {
        "schema": "geotarget.exact-coordinate-reflect-point-private/v1",
        "numeric_semantics": "Reflect(point, center) = 2*center - point",
        "argument_order": ["reflected_point", "center_point"],
        "added_typed_method": "qreflect(::QPoint, ::QPoint)",
        "existing_line_method_changed": False,
        "other_extended_worker_bytes_identical_after_overload_removal": (
            remove_point_reflect_overload(patched) == original
        ),
        "branch_or_definedness_added": False,
        "wrong_types_fail_closed_by_julia_dispatch": True,
        "maximum_recognition_degree": 8,
        "case_family_truth_target_count_or_outcome_routing": False,
        "dependency_sha256": verify_dependencies(),
        "original_extended_worker_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "patched_extended_worker_sha256": hashlib.sha256(patched.encode()).hexdigest(),
    }


__all__ = [
    "ORIGINAL",
    "certify_exact_coordinate_witness",
    "closure_manifest",
    "extended_worker_source",
    "remove_point_reflect_overload",
    "verify_dependencies",
]
