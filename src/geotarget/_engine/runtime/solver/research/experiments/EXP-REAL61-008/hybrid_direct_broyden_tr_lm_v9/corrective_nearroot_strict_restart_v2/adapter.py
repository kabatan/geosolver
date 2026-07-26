"""Thin paired adapter: retained-invalid v1 versus near-root restart v2."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
from typing import Mapping


HERE = Path(__file__).resolve().parent
V1_ADAPTER_PATH = HERE.parent / "corrective_accepted_invalid_v1/adapter.py"
V2_CANDIDATE_PATH = HERE / "candidate.py"
EXPECTED_SHA256 = {
    "v1_adapter": "8196091fa91d9df6060c8047b4793607704401ee33900bb5181c2dbb40822be7",
    "v2_candidate": "d2904af6e1f0f0dbc8432dfb2adf3039e28c502131df45ffdd3bfde42f7acafc",
}


def _load(label: str, path: Path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != EXPECTED_SHA256[label]:
        raise RuntimeError(f"hash-bound near-root paired dependency changed: {label}")
    name = f"geotarget_exp008_nearroot_restart_adapter_{label}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


V1 = _load("v1_adapter", V1_ADAPTER_PATH)
V2 = _load("v2_candidate", V2_CANDIDATE_PATH)

CONTROL = V1.CORRECTIVE
CANDIDATE = V2.REFERENCE_NAME
ARMS = (CONTROL, CANDIDATE)
PRECISION_RUNTIME = V1.PRECISION_RUNTIME


def _payload() -> dict[str, object]:
    return {
        "schema_version": "geotarget.exp-real61-008.nearroot-restart-paired/v1",
        "arms": list(ARMS),
        "control": CONTROL,
        "candidate": CANDIDATE,
        "control_manifest": dict(V1.CORRECTIVE_MODULE.configuration_manifest()),
        "candidate_manifest": dict(V2.configuration_manifest()),
        "candidate_delta_manifest": dict(V2.delta_manifest()),
        "same_frozen_unchanged_source_literal_prefix": True,
        "same_original_coordinate_starts": True,
        "same_per_start_numerical_scale": "max(1,abs(start))",
        "same_callback_caps_and_deadline": True,
        "same_precision_isolated_untouched_evaluator": True,
        "source_problem_modified": False,
        "variables_or_equations_changed": False,
        "all_source_variables_equations_guards_branches_retained": True,
        "source_bounds_only": True,
        "added_or_inferred_bounds": False,
        "gauge_or_symmetry_reduction": False,
        "elimination_or_reparameterization": False,
        "case_family_source_truth_target_count_or_outcome_routing": False,
        "predeclared_decision": {
            "third_corrective_allowed": False,
            "advance_if": (
                "coverage and starts-launched are noninferior, P3/SPOT gains persist, "
                "and P5 is recovered on confirmation"
            ),
            "otherwise": "freeze v2 and retain v1 control",
        },
    }


def _digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


_BASE_PAYLOAD = _payload()
BINDING_RECORD = {
    **_BASE_PAYLOAD,
    "configuration_digest": _digest(_BASE_PAYLOAD),
    "module_sha256": dict(EXPECTED_SHA256),
    "v1_binding_record": V1.BINDING_RECORD,
}


def build_literal_prefix(document, base_case, base_policy):
    return V1.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm == CONTROL:
        return V1.CORRECTIVE_MODULE.compile_program(document)
    if arm == CANDIDATE:
        return V2.compile_program(document)
    raise ValueError(f"unknown near-root restart arm: {arm!r}")


_DELEGATE_LOCK = threading.RLock()


def run_local_arm(arm: str, **kwargs):
    if arm == CONTROL:
        module = V1.CORRECTIVE_MODULE
    elif arm == CANDIDATE:
        module = V2
    else:
        raise ValueError(f"unknown near-root restart arm: {arm!r}")
    with _DELEGATE_LOCK:
        original = V1.BASE.ROW_MODULE
        V1.BASE.ROW_MODULE = module
        try:
            return V1.BASE.run_local_arm(V1.BASE.ROW, **kwargs)
        finally:
            V1.BASE.ROW_MODULE = original


def configuration_manifest() -> Mapping[str, object]:
    return BINDING_RECORD


__all__ = [
    "ARMS",
    "BINDING_RECORD",
    "CANDIDATE",
    "CONTROL",
    "PRECISION_RUNTIME",
    "build_literal_prefix",
    "compile_program",
    "configuration_manifest",
    "run_local_arm",
]
