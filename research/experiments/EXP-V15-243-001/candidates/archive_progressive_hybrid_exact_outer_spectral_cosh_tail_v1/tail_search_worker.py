#!/usr/bin/env python3
"""Progressive side-search child with ordinary insurance and spectral cosh."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
CURRENT_ROOT = CAMPAIGN / "progressive_adaptive_hybrid_v1"
CURRENT_SEARCH_WORKER = CURRENT_ROOT / "search_worker.py"
CURRENT_SEARCH_ADAPTER = CURRENT_ROOT / "search_adapter.py"
CURRENT_SEARCH_CANDIDATE = CURRENT_ROOT / "candidate.py"
SPECTRAL_ROOT = CAMPAIGN / "spectral_cosh_preconditioned_gn_v1"
SPECTRAL_CANDIDATE = SPECTRAL_ROOT / "real_candidate.py"
SPECTRAL_SEAM = SPECTRAL_ROOT / "real_seam_patch.py"
EXPECTED_SHA256 = {
    CURRENT_SEARCH_WORKER: "a19339445c55542bd849c861dc179c6a225c60d2c12e49c90e3f338c80356ce6",
    CURRENT_SEARCH_ADAPTER: "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea",
    CURRENT_SEARCH_CANDIDATE: "9a449d370a2a87dea50bf3aa9cd0a3cc3d1484491e48829fd89cbdd1c82b7972",
    SPECTRAL_CANDIDATE: "7ac6ece4e34fa790c10218a5e8fe59def5ca1086562dc98751939d17aa5e2677",
    SPECTRAL_SEAM: "4902ca1f628949563736c8ea3a1950245e0e8e6af9be7f4463f8d4e69639fbf6",
}
SPECTRAL_COUNTERS = frozenset(
    {
        "spectral_cosh_linearizations",
        "spectral_cosh_activations",
        "spectral_cosh_fallbacks",
    }
)
_ACTIVE_INSURANCE: bool | None = None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_dependencies() -> dict[str, str]:
    observed = {
        str(path.resolve()): _sha256(path) if path.is_file() else "MISSING"
        for path in EXPECTED_SHA256
    }
    expected = {str(path.resolve()): value for path, value in EXPECTED_SHA256.items()}
    if observed != expected:
        raise RuntimeError("spectral tail dependency closure changed")
    return observed


def _load(name: str, path: Path) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _without_spectral_counters(counters: object) -> dict[str, object]:
    if not isinstance(counters, Mapping):
        raise TypeError("candidate outcome counters must be a mapping")
    return {
        str(key): value for key, value in counters.items() if key not in SPECTRAL_COUNTERS
    }


def _fallback_identity_solve(spectral: Any, *args, **kwargs):
    outcome = spectral.solve_local(*args, **kwargs)
    counters = getattr(outcome, "counters", None)
    if not isinstance(counters, Mapping):
        return outcome
    if int(counters.get("spectral_cosh_activations", 0)) != 0:
        return outcome
    clean = _without_spectral_counters(counters)
    try:
        return replace(outcome, counters=clean)
    except TypeError:
        return outcome.__class__(outcome.endpoint, outcome.status, clean)


def _spectral_module(spectral: Any) -> ModuleType:
    module = ModuleType("geotarget_spectral_cosh_surplus_local_module")
    module.REFERENCE = spectral.PARENT.REFERENCE
    module.compile_program = spectral.compile_program
    module.solve_local = lambda *args, **kwargs: _fallback_identity_solve(
        spectral, *args, **kwargs
    )
    return module


def install_search_patch(current: Any, spectral: Any) -> Mapping[str, object]:
    """Use cosh only for non-insurance services; no ordinal schedule exists."""

    policy = current.ADAPTER.POLICY
    frozen = current.ADAPTER.BASE.DEEP.FROZEN
    original_scheduler = policy.run_rung_scheduler
    original_frozen_run = frozen.run_local_arm
    candidate_module = _spectral_module(spectral)

    def scheduler_wrapper(starts, **kwargs):
        delegate = kwargs["run_rung"]

        def routed(spec, *args, **inner_kwargs):
            global _ACTIVE_INSURANCE
            if _ACTIVE_INSURANCE is not None:
                raise RuntimeError("nested spectral-cosh insurance routing")
            _ACTIVE_INSURANCE = bool(spec.insurance)
            try:
                return delegate(spec, *args, **inner_kwargs)
            finally:
                _ACTIVE_INSURANCE = None

        forwarded = dict(kwargs)
        forwarded["run_rung"] = routed
        return original_scheduler(starts, **forwarded)

    def frozen_run_wrapper(arm: str, **kwargs):
        if _ACTIVE_INSURANCE is None or _ACTIVE_INSURANCE:
            return original_frozen_run(arm, **kwargs)
        original_module = frozen.V2
        frozen.V2 = candidate_module
        try:
            return original_frozen_run(arm, **kwargs)
        finally:
            frozen.V2 = original_module

    policy.run_rung_scheduler = scheduler_wrapper
    frozen.run_local_arm = frozen_run_wrapper
    return {
        "schema": "geotarget.spectral-cosh-surplus-search/v1",
        "route": "all_noninsurance_side_services_spectral",
        "ordinal_schedule": False,
        "ordinary_counter_cauchy_insurance_preserved": True,
        "source_evaluator_guard_replay_or_deadline_changed": False,
        "case_family_truth_target_or_previous_outcome_routing": False,
    }


def main() -> None:
    verify_dependencies()
    _load("real_seam_patch", SPECTRAL_SEAM)
    current = _load("geotarget_spectral_cosh_surplus_current_search", CURRENT_SEARCH_WORKER)
    spectral = _load("geotarget_spectral_cosh_surplus_candidate", SPECTRAL_CANDIDATE)
    install_search_patch(current, spectral)
    current.main()


if __name__ == "__main__":
    main()
