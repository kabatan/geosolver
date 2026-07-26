"""One general restart wave for the accepted-invalid direct-Broyden survivor.

The first track is the frozen accepted-semantic-invalid-retained kernel.  If it
stalls after reducing the untouched relation infinity norm by at least the
cube root of Float64 epsilon, and the caller's per-start callback quota still
has room, one fresh strict-semantic-invalid-refresh track is launched from the
*same original start*.  A failed restart cannot replace the first track's best
endpoint; a strict endpoint is returned only when the strict track reports a
safe root through the unchanged raw evaluator.

The cube-root-epsilon trigger is dimensionless and fixed before confirmation.
No problem identity, family, truth, target count, source rewrite, inferred
bound, gauge, symmetry reduction, or reparameterization is available here.
The caller remains the authority for the shared per-start callback quota and
deadline, exactly as for both frozen parent kernels.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Mapping

import numpy as np


HERE = Path(__file__).resolve().parent
RETAINED_PATH = HERE.parent / "corrective_accepted_invalid_v1/candidate.py"
STRICT_PATH = HERE.parent / "candidate.py"
RETAINED_SHA256 = "3575d816897fafe0e696141f20c063ae338cfc51e7aebe610cd1a625d63fdc2b"
STRICT_SHA256 = "e9c9bd7fc950baafdb90b8899c86ef6286da539b868f6fd0e00664b709dd0caa"
REFERENCE_NAME = (
    "precision_isolated_retained_then_strict_nearroot_restart_"
    "direct_broyden_ruiz_tr_lm"
)
RESTART_REDUCTION_RATIO = float(np.cbrt(np.finfo(float).eps))

INITIAL_BLOCK = """    best = current
    trust_radius = float(base.initial_trust_radius)
"""

INITIAL_REPLACEMENT = """    best = current
    initial_relation_inf = float(current.relation_inf)
    trust_radius = float(base.initial_trust_radius)
"""

RETURN_BLOCK = """    return CandidateOutcome(best.x.copy(), status, counters)
"""

RETURN_REPLACEMENT = """    estimated_callbacks = (
        int(counters[\"initial_state_evaluations\"])
        + int(counters[\"trial_state_evaluations\"])
        + int(counters[\"fd_direction_evaluations\"])
    )
    remaining_callbacks = max(0, int(max_callbacks) - estimated_callbacks)
    strong_progress = bool(
        math.isfinite(initial_relation_inf)
        and initial_relation_inf > 0.0
        and math.isfinite(float(best.relation_inf))
        and float(best.relation_inf)
        <= initial_relation_inf * _NEARROOT_RESTART_REDUCTION_RATIO
    )
    restart_eligible = bool(
        status == \"stalled_or_budget\"
        and strong_progress
        and remaining_callbacks >= 2
        and time.monotonic() < deadline_monotonic
    )
    counters[\"nearroot_strict_restart_eligible\"] = int(restart_eligible)
    counters[\"nearroot_strict_restart_attempts\"] = 0
    counters[\"nearroot_strict_restart_safe_roots\"] = 0
    counters[\"nearroot_strict_restart_exceptions\"] = 0
    if restart_eligible:
        counters[\"nearroot_strict_restart_attempts\"] = 1
        try:
            strict = _STRICT_SOLVE_LOCAL(
                case,
                program,
                _STRICT_CONFIGURATION,
                anchor,
                per_start_scale=variable_scale,
                source_lower=explicit_lower,
                source_upper=explicit_upper,
                max_callbacks=remaining_callbacks,
                deadline_monotonic=deadline_monotonic,
            )
        except Exception:
            strict = None
            counters[\"nearroot_strict_restart_exceptions\"] = 1
        if strict is not None:
            for _name, _value in strict.counters.items():
                if isinstance(_value, (bool, int, np.integer)):
                    counters[_name] = int(counters.get(_name, 0)) + int(_value)
        counters[\"nearroot_strict_restart_eligible\"] = 1
        counters[\"nearroot_strict_restart_attempts\"] = 1
        if strict is not None and strict.status == \"safe_root\":
            counters[\"nearroot_strict_restart_safe_roots\"] = 1
            return CandidateOutcome(strict.endpoint.copy(), \"safe_root\", counters)
    return CandidateOutcome(best.x.copy(), status, counters)
"""


def _load_hash_bound(name: str, path: Path, expected: str) -> ModuleType:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected:
        raise RuntimeError(f"hash-bound near-root restart dependency changed: {path}")
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


_RETAINED = _load_hash_bound(
    "geotarget_exp008_nearroot_restart_retained", RETAINED_PATH, RETAINED_SHA256
)
_STRICT = _load_hash_bound(
    "geotarget_exp008_nearroot_restart_strict", STRICT_PATH, STRICT_SHA256
)


def _load_restart_kernel() -> tuple[ModuleType, str]:
    source = _RETAINED.PATCHED_SOURCE
    if source.count(INITIAL_BLOCK) != 1:
        raise RuntimeError("accepted-invalid initial-state block is not unique")
    if source.count(RETURN_BLOCK) != 1:
        raise RuntimeError("accepted-invalid return block is not unique")
    patched = source.replace(INITIAL_BLOCK, INITIAL_REPLACEMENT, 1).replace(
        RETURN_BLOCK, RETURN_REPLACEMENT, 1
    )
    name = "geotarget_exp008_direct_broyden_nearroot_strict_restart_kernel"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached, patched
    module = ModuleType(name)
    # PATCHED_SOURCE is the transformed frozen parent source, whose relative
    # dependency paths are rooted at the frozen parent's directory.
    module.__file__ = str(STRICT_PATH)
    module.__package__ = ""
    module.__dict__["_STRICT_SOLVE_LOCAL"] = _STRICT.solve_local
    module.__dict__["_STRICT_CONFIGURATION"] = _STRICT.REFERENCE
    module.__dict__["_NEARROOT_RESTART_REDUCTION_RATIO"] = RESTART_REDUCTION_RATIO
    sys.modules[name] = module
    exec(compile(patched, str(STRICT_PATH), "exec"), module.__dict__)
    return module, patched


_KERNEL, PATCHED_SOURCE = _load_restart_kernel()
PATCHED_SOURCE_SHA256 = hashlib.sha256(PATCHED_SOURCE.encode("utf-8")).hexdigest()

ADProgram = _KERNEL.ADProgram
CandidateOutcome = _KERNEL.CandidateOutcome
Configuration = _KERNEL.Configuration
compile_program = _KERNEL.compile_program
solve_local = _KERNEL.solve_local
REFERENCE = replace(_KERNEL.REFERENCE, name=REFERENCE_NAME)
CONFIGURATIONS = {REFERENCE_NAME: REFERENCE}


def configuration_manifest(
    configuration: Configuration = REFERENCE,
) -> Mapping[str, object]:
    payload = dict(_RETAINED.configuration_manifest(configuration))
    payload.update(
        {
            "candidate": configuration.name,
            "corrective_wave": (
                "near-root stalled retained track restarts the strict refresh policy "
                "once from the identical original start"
            ),
            "restart_trigger": {
                "status": "stalled_or_budget",
                "relation_reduction_ratio_at_most": RESTART_REDUCTION_RATIO,
                "ratio_derivation": "cuberoot(Float64 epsilon)",
                "minimum_remaining_callbacks": 2,
            },
            "restart_origin": "identical caller-provided original start",
            "restart_policy": "frozen strict semantic-invalid refresh parent",
            "restart_count_cap_per_local_start": 1,
            "failed_restart_endpoint_policy": (
                "retain first-track best; strict endpoint replaces it only on safe_root"
            ),
            "caller_shared_callback_quota_and_deadline_required": True,
            "retained_parent_sha256": RETAINED_SHA256,
            "strict_parent_sha256": STRICT_SHA256,
            "patched_kernel_source_sha256": PATCHED_SOURCE_SHA256,
            "source_problem_modified": False,
            "variables_or_equations_changed": False,
            "source_rewrite_or_reparameterization": False,
            "gauge_or_symmetry_reduction": False,
            "added_or_inferred_bounds": False,
            "case_family_truth_target_count_or_outcome_routing": False,
        }
    )
    return payload


def delta_manifest() -> Mapping[str, object]:
    return {
        "retained_parent_sha256": RETAINED_SHA256,
        "strict_parent_sha256": STRICT_SHA256,
        "patched_kernel_source_sha256": PATCHED_SOURCE_SHA256,
        "initial_block_replacement_count": _RETAINED.PATCHED_SOURCE.count(
            INITIAL_BLOCK
        ),
        "return_block_replacement_count": _RETAINED.PATCHED_SOURCE.count(RETURN_BLOCK),
        "all_other_retained_kernel_source_bytes_preserved": True,
    }


__all__ = [
    "ADProgram",
    "CONFIGURATIONS",
    "CandidateOutcome",
    "Configuration",
    "PATCHED_SOURCE_SHA256",
    "REFERENCE",
    "REFERENCE_NAME",
    "RESTART_REDUCTION_RATIO",
    "compile_program",
    "configuration_manifest",
    "delta_manifest",
    "solve_local",
]
