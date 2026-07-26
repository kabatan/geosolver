"""Paired frozen-direct versus accepted-invalid corrective adapter.

The two arms differ only in the hash-audited semantic-invalid refresh
predicate.  Both consume the same frozen literal prefix, original-coordinate
starts, numerical scales, source bounds, callbacks, precision-isolated
evaluator, direct-model cache, trust/LM policy, and endpoint replay.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
from typing import Mapping


HERE = Path(__file__).resolve().parent
EXP008 = HERE.parents[1]
LITERAL_ADAPTER_PATH = EXP008 / "dev41_literal_local_screen/adapter.py"
FROZEN_CANDIDATE_PATH = HERE.parent / "candidate.py"
CORRECTIVE_CANDIDATE_PATH = HERE / "candidate.py"
PRECISION_RUNTIME_PATH = EXP008 / "ad_inverse_broyden/precision_runtime.py"
EXPECTED_SHA256 = {
    "literal_adapter": "c7e0191633456b52163c96fe8a7ba2ee2436e8737cc20c7738e6f972026c854f",
    "frozen_candidate": "e9c9bd7fc950baafdb90b8899c86ef6286da539b868f6fd0e00664b709dd0caa",
    "corrective_candidate": "3575d816897fafe0e696141f20c063ae338cfc51e7aebe610cd1a625d63fdc2b",
    "precision_runtime": "8d072c47f8a7f3bcb15dfff44d952e94c97adba22d6f42a2a758cad52a80cd7b",
}


def _load(label: str, path: Path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != EXPECTED_SHA256[label]:
        raise RuntimeError(f"hash-bound accepted-invalid dependency changed: {label}")
    name = f"geotarget_exp008_accepted_invalid_adapter_{label}"
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


BASE = _load("literal_adapter", LITERAL_ADAPTER_PATH)
FROZEN_MODULE = _load("frozen_candidate", FROZEN_CANDIDATE_PATH)
CORRECTIVE_MODULE = _load("corrective_candidate", CORRECTIVE_CANDIDATE_PATH)
PRECISION_RUNTIME = _load("precision_runtime", PRECISION_RUNTIME_PATH)

FROZEN_DIRECT = FROZEN_MODULE.REFERENCE_NAME
CORRECTIVE = CORRECTIVE_MODULE.REFERENCE_NAME
ARMS = (FROZEN_DIRECT, CORRECTIVE)


def _payload() -> dict[str, object]:
    return {
        "schema_version": "geotarget.exp-real61-008.accepted-invalid-corrective-paired/v1",
        "arms": list(ARMS),
        "control": FROZEN_DIRECT,
        "candidate": CORRECTIVE,
        "corrective_manifest": dict(CORRECTIVE_MODULE.configuration_manifest()),
        "delta_manifest": dict(CORRECTIVE_MODULE.delta_manifest()),
        "same_frozen_unchanged_source_literal_prefix": True,
        "same_original_coordinate_starts": True,
        "same_per_start_numerical_scale": "max(1,abs(start))",
        "same_callback_caps_and_deadline": True,
        "same_direct_model_cache": True,
        "same_trust_damping_ruiz_cpqr_svd_and_acceptance": True,
        "precision_runtime": PRECISION_RUNTIME.precision_manifest(),
        "source_problem_modified": False,
        "variables_or_equations_changed": False,
        "all_source_variables_equations_guards_branches_retained": True,
        "source_bounds_only": True,
        "added_or_inferred_bounds": False,
        "gauge_or_symmetry_reduction": False,
        "elimination_or_reparameterization": False,
        "case_family_source_truth_target_count_or_outcome_routing": False,
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
    "source_only_policy_digest": BASE.BINDING_RECORD["source_only_policy_digest"],
    "frozen_literal_binding_record": BASE.BINDING_RECORD,
}


def build_literal_prefix(document, base_case, base_policy):
    return BASE.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm == FROZEN_DIRECT:
        return FROZEN_MODULE.compile_program(document)
    if arm == CORRECTIVE:
        return CORRECTIVE_MODULE.compile_program(document)
    raise ValueError(f"unknown accepted-invalid corrective arm: {arm!r}")


_DELEGATE_LOCK = threading.RLock()


def run_local_arm(arm: str, **kwargs):
    if arm == FROZEN_DIRECT:
        module = FROZEN_MODULE
    elif arm == CORRECTIVE:
        module = CORRECTIVE_MODULE
    else:
        raise ValueError(f"unknown accepted-invalid corrective arm: {arm!r}")
    with _DELEGATE_LOCK:
        original = BASE.ROW_MODULE
        BASE.ROW_MODULE = module
        try:
            return BASE.run_local_arm(BASE.ROW, **kwargs)
        finally:
            BASE.ROW_MODULE = original


def configuration_manifest() -> Mapping[str, object]:
    return BINDING_RECORD


__all__ = [
    "ARMS",
    "BINDING_RECORD",
    "CORRECTIVE",
    "CORRECTIVE_MODULE",
    "FROZEN_DIRECT",
    "FROZEN_MODULE",
    "PRECISION_RUNTIME",
    "build_literal_prefix",
    "compile_program",
    "configuration_manifest",
    "run_local_arm",
]
