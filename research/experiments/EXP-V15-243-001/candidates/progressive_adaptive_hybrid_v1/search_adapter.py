"""Bind the adaptive 64->600 hybrid to the unchanged frozen v15 seam."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Mapping


HERE = Path(__file__).resolve().parent
BASE_ADAPTER_PATH = (
    HERE.parent / "progressive_local_budget_v1" / "search_adapter.py"
)
BASE_ADAPTER_SHA256 = "244c6125ce7a51d03368bc514ab5f99f1e3e0dffa989a678c70fe0ffc5e30d94"


def _load(name: str, path: Path, expected_sha256: str | None = None):
    payload = path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise RuntimeError(f"hash-bound adaptive hybrid dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


POLICY = _load("geotarget_progressive_adaptive_hybrid_policy", HERE / "candidate.py")
BASE = _load(
    "geotarget_progressive_adaptive_hybrid_base_adapter",
    BASE_ADAPTER_PATH,
    BASE_ADAPTER_SHA256,
)
CONTROL = "frozen_v15_original_start_loop"
CANDIDATE = "progressive_adaptive_hybrid_64_600"
ARMS = (CONTROL, CANDIDATE)
PRECISION_RUNTIME = BASE.PRECISION_RUNTIME
FROZEN = BASE.FROZEN
FROZEN_ADAPTER_PATH = BASE.FROZEN_ADAPTER_PATH
FROZEN_ADAPTER_SHA256 = BASE.FROZEN_ADAPTER_SHA256
DEEP_ADAPTER_SHA256 = BASE.DEEP_ADAPTER_SHA256


def build_literal_prefix(document, base_case, base_policy):
    return BASE.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm == CONTROL:
        return BASE.compile_program(BASE.CONTROL, document)
    if arm == CANDIDATE:
        return BASE.compile_program(BASE.PROFILE_64, document)
    raise ValueError(f"unknown adaptive hybrid arm: {arm!r}")


def set_partial_output(path: Path | None) -> None:
    BASE.set_partial_output(path)


def run_local_arm(arm: str, **kwargs):
    if arm == CONTROL:
        return BASE.run_local_arm(BASE.CONTROL, **kwargs)
    if arm != CANDIDATE:
        raise ValueError(f"unknown adaptive hybrid arm: {arm!r}")
    POLICY.set_active_profile(POLICY.PROFILE)
    BASE.DEEP.SCHEDULER = POLICY
    BASE.DEEP.FINALIZE_RESERVE_SECONDS = 3.0
    BASE.DEEP.MAX_SERVICE_WALL_SECONDS = POLICY.MAX_ATTEMPT_WALL_SECONDS
    return BASE.DEEP.run_local_arm(BASE.DEEP.CANDIDATE, **kwargs)


def configuration_manifest() -> Mapping[str, object]:
    payload: dict[str, object] = {
        "schema_version": "geotarget.exp-v15-243.adaptive-hybrid-binding/v1",
        "arms": list(ARMS),
        "control": CONTROL,
        "candidate": CANDIDATE,
        "policy": POLICY.configuration_manifest(),
        "base_progressive_adapter_sha256": BASE_ADAPTER_SHA256,
        "deep_binding_sha256": DEEP_ADAPTER_SHA256,
        "frozen_local_adapter_sha256": FROZEN_ADAPTER_SHA256,
        "same_immutable_literal_prefix": True,
        "same_frozen_v15_local_kernel": True,
        "same_source_evaluator_callback_ledger_and_deadline": True,
        "current_checkpoint_support": False,
        "current_resume_mode": "charged original-start reexecution",
        "source_problem_modified": False,
        "case_family_truth_target_or_previous_outcome_routing": False,
        "canonical_verifier_modified": False,
    }
    payload["configuration_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


BINDING_RECORD = configuration_manifest()


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
    "set_partial_output",
]
