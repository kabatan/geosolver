"""Bind progressive local budgeting to the unchanged frozen v15 kernel.

The frozen runtime is a read-only experiment dependency.  Its deep-scheduler
binding already provides fail-closed fork isolation, callback reconciliation,
and the mature champion local kernel.  This adapter replaces only the policy
module and exposes both preregistered tranche profiles as paired arms.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Mapping


HERE = Path(__file__).resolve().parent
DEFAULT_RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
RUNTIME_ROOT = Path(
    os.environ.get("GEOTARGET_EXPERIMENT_RUNTIME", str(DEFAULT_RUNTIME_ROOT))
).resolve()
DEEP_ADAPTER_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/deep_scheduler/search_adapter.py"
)
DEEP_ADAPTER_SHA256 = "1cd81d7011fc1da07f31540c64e44d4e669775873bd2432e1e61bdbdf76eecad"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _load(name: str, path: Path, expected_sha256: str | None = None):
    payload = path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise RuntimeError(f"hash-bound progressive dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


POLICY = _load("geotarget_progressive_local_budget_policy", HERE / "candidate.py")
DEEP = _load(
    "geotarget_progressive_local_budget_deep_binding",
    DEEP_ADAPTER_PATH,
    DEEP_ADAPTER_SHA256,
)

CONTROL = "frozen_v15_original_start_loop"
PROFILE_64 = "progressive_local_budget_64_192_600"
PROFILE_96 = "progressive_local_budget_96_300_600"
ARMS = (CONTROL, PROFILE_64, PROFILE_96)
PROFILE_BY_ARM = {
    PROFILE_64: "64-192-600",
    PROFILE_96: "96-300-600",
}
PRECISION_RUNTIME = DEEP.PRECISION_RUNTIME
FROZEN = DEEP.FROZEN
FROZEN_ADAPTER_PATH = DEEP.FROZEN_ADAPTER_PATH
FROZEN_ADAPTER_SHA256 = DEEP.FROZEN_ADAPTER_SHA256


def build_literal_prefix(document, base_case, base_policy):
    return DEEP.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm == CONTROL:
        return DEEP.compile_program(DEEP.CONTROL, document)
    if arm in PROFILE_BY_ARM:
        return DEEP.compile_program(DEEP.CANDIDATE, document)
    raise ValueError(f"unknown progressive local-budget arm: {arm!r}")


def set_partial_output(path: Path | None) -> None:
    DEEP.set_partial_output(path)


def run_local_arm(arm: str, **kwargs):
    if arm == CONTROL:
        return DEEP.run_local_arm(DEEP.CONTROL, **kwargs)
    try:
        profile = PROFILE_BY_ARM[arm]
    except KeyError as error:
        raise ValueError(f"unknown progressive local-budget arm: {arm!r}") from error

    # One worker executes one arm, so policy rebinding is process-private.  The
    # mature local kernel, source evaluator, ledger and verifier remain frozen.
    POLICY.set_active_profile(profile)
    DEEP.SCHEDULER = POLICY
    DEEP.FINALIZE_RESERVE_SECONDS = 3.0
    DEEP.MAX_SERVICE_WALL_SECONDS = POLICY.MAX_ATTEMPT_WALL_SECONDS
    return DEEP.run_local_arm(DEEP.CANDIDATE, **kwargs)


def configuration_manifest() -> Mapping[str, object]:
    payload: dict[str, object] = {
        "schema_version": "geotarget.exp-v15-243.progressive-local-binding/v1",
        "arms": list(ARMS),
        "control": CONTROL,
        "candidate_profiles": dict(PROFILE_BY_ARM),
        "policy": POLICY.configuration_manifest(),
        "deep_binding_sha256": DEEP_ADAPTER_SHA256,
        "frozen_local_adapter_sha256": FROZEN_ADAPTER_SHA256,
        "same_immutable_literal_prefix": True,
        "same_frozen_v15_local_kernel": True,
        "same_source_evaluator_callback_ledger_and_deadline": True,
        "only_candidate_delta": (
            "minimum-service progressive callback allocation and dynamic per-attempt "
            "wall cap with truth-blind promotion telemetry"
        ),
        "current_checkpoint_support": False,
        "current_resume_mode": "charged original-start prefix reexecution",
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
    "CONTROL",
    "DEEP_ADAPTER_PATH",
    "DEEP_ADAPTER_SHA256",
    "FROZEN_ADAPTER_PATH",
    "FROZEN_ADAPTER_SHA256",
    "PRECISION_RUNTIME",
    "PROFILE_64",
    "PROFILE_96",
    "build_literal_prefix",
    "compile_program",
    "configuration_manifest",
    "run_local_arm",
    "set_partial_output",
]
