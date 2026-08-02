"""Drop-in HP authority adapter with only the false POC inventory removed.

This module is intentionally smaller than ``candidate.py``.  It contains no
periodic endpoint canonicalization and no search policy.  Runners which
currently point ``ADAPTER_PATH`` at the frozen authority adapter can instead
point at this file; every exported authority function still executes in the
hash-bound original module, with just the incorrect ``PointOnCircle`` unit
domain entry absent.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
ORIGINAL = (
    ROOT
    / "research/experiments/EXP-REAL61-008/dev41_target_hp_adapter/adapter.py"
)
ORIGINAL_SHA256 = (
    "c4b8e7974ba09921723e2545321c9e454e24978f535a42f2aaa728792929984a"
)
MODULE_NAME = "geotarget_point_on_circle_repaired_authority_adapter_base"


def _load_original():
    observed = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
    if observed != ORIGINAL_SHA256:
        raise RuntimeError("frozen HP authority adapter digest changed")
    cached = sys.modules.get(MODULE_NAME)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(MODULE_NAME, ORIGINAL)
    if specification is None or specification.loader is None:
        raise ImportError(ORIGINAL)
    module = importlib.util.module_from_spec(specification)
    sys.modules[MODULE_NAME] = module
    specification.loader.exec_module(module)
    return module


_BASE = _load_original()
_inventory = dict(_BASE._UNIT_PARAMETER_POSITIONS)
if _inventory.get("PointOnCircle") not in {(1,), None}:
    raise RuntimeError("unexpected PointOnCircle HP inventory contract")
_inventory.pop("PointOnCircle", None)
_BASE._UNIT_PARAMETER_POSITIONS = _inventory

# Re-export the exact original adapter surface.  Function globals continue to
# point at _BASE, whose corrected inventory is process-local to this fresh HP
# worker.  Wrapper metadata is added after the export.
for _name, _value in vars(_BASE).items():
    if _name not in {"__name__", "__file__", "__spec__", "__loader__"}:
        globals()[_name] = _value

POINT_ON_CIRCLE_SEMANTIC_REPAIR = {
    "schema_version": (
        "geotarget.exp-v15-243.point-on-circle-hp-adapter-wrapper/v1"
    ),
    "original_sha256": ORIGINAL_SHA256,
    "point_on_circle_intrinsic_unit_bound": False,
    "endpoint_canonicalization": False,
    "source_or_endpoint_modified": False,
    "case_family_truth_or_target_routing": False,
}

