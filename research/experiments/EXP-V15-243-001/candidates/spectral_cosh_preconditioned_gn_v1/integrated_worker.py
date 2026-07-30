#!/usr/bin/env python3
"""Current campaign worker with one candidate-private spectral-cosh seam."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CURRENT_ROOT = HERE.parent / "progressive_adaptive_hybrid_v1"
CURRENT_FULL_WRAPPER = CURRENT_ROOT / "full_wrapper.py"
CURRENT_SEARCH_WORKER = CURRENT_ROOT / "search_worker.py"
CURRENT_SEARCH_ADAPTER = CURRENT_ROOT / "search_adapter.py"
CURRENT_SEARCH_CANDIDATE = CURRENT_ROOT / "candidate.py"
SPECTRAL_CANDIDATE = HERE / "real_candidate.py"
SPECTRAL_SEAM = HERE / "real_seam_patch.py"
EXPECTED_SHA256 = {
    CURRENT_FULL_WRAPPER: (
        "4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4"
    ),
    CURRENT_SEARCH_WORKER: (
        "a19339445c55542bd849c861dc179c6a225c60d2c12e49c90e3f338c80356ce6"
    ),
    CURRENT_SEARCH_ADAPTER: (
        "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea"
    ),
    CURRENT_SEARCH_CANDIDATE: (
        "9a449d370a2a87dea50bf3aa9cd0a3cc3d1484491e48829fd89cbdd1c82b7972"
    ),
    SPECTRAL_CANDIDATE: (
        "7ac6ece4e34fa790c10218a5e8fe59def5ca1086562dc98751939d17aa5e2677"
    ),
    SPECTRAL_SEAM: ("4902ca1f628949563736c8ea3a1950245e0e8e6af9be7f4463f8d4e69639fbf6"),
}
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
SEARCH_CHILD_ENV = "GEOTARGET_SPECTRAL_COSH_CURRENT_SEARCH_CHILD"
SIDE_PERIOD = 4
SIDE_RESIDUE = 3
SPECTRAL_COUNTERS = frozenset(
    {
        "spectral_cosh_linearizations",
        "spectral_cosh_activations",
        "spectral_cosh_fallbacks",
    }
)
_ACTIVE_START_ORDINAL: int | None = None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_dependencies() -> None:
    for path, expected in EXPECTED_SHA256.items():
        if not path.is_file() or _sha256(path) != expected:
            raise RuntimeError(f"hash-bound spectral-cosh dependency changed: {path}")


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
        str(key): value
        for key, value in counters.items()
        if key not in SPECTRAL_COUNTERS
    }


def _fallback_identity_solve(spectral: Any, *args, **kwargs):
    """Erase candidate telemetry iff every linearization used the baseline RHS."""

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
    """Expose the parent configuration so a zero-activation result is identical."""

    module = ModuleType("geotarget_spectral_cosh_current_campaign_local_module")
    module.REFERENCE = spectral.PARENT.REFERENCE
    module.compile_program = spectral.compile_program

    def solve_local(*args, **kwargs):
        return _fallback_identity_solve(spectral, *args, **kwargs)

    module.solve_local = solve_local
    return module


def install_search_patch(current: Any, spectral: Any) -> Mapping[str, object]:
    """Patch only ordinal routing and the frozen local module in one search child."""

    policy = current.ADAPTER.POLICY
    deep = current.ADAPTER.BASE.DEEP
    frozen = deep.FROZEN
    original_scheduler = policy.run_rung_scheduler
    original_frozen_run = frozen.run_local_arm
    candidate_module = _spectral_module(spectral)

    def scheduler_wrapper(starts, **kwargs):
        delegate = kwargs["run_rung"]

        def routed(spec, *args, **inner_kwargs):
            global _ACTIVE_START_ORDINAL
            if _ACTIVE_START_ORDINAL is not None:
                raise RuntimeError("nested spectral-cosh rung routing")
            _ACTIVE_START_ORDINAL = int(spec.ordinal)
            try:
                return delegate(spec, *args, **inner_kwargs)
            finally:
                _ACTIVE_START_ORDINAL = None

        forwarded = dict(kwargs)
        forwarded["run_rung"] = routed
        return original_scheduler(starts, **forwarded)

    def frozen_run_wrapper(arm: str, **kwargs):
        ordinal = _ACTIVE_START_ORDINAL
        if ordinal is None or ordinal % SIDE_PERIOD != SIDE_RESIDUE:
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
        "schema": "geotarget.spectral-cosh-current-search-binding/v1",
        "side_rule": "original_start_ordinal_mod_4_equals_3",
        "baseline_minimum_share": 0.75,
        "source_evaluator_guard_replay_or_deadline_changed": False,
        "zero_activation_spectral_counters_removed": True,
        "case_family_truth_target_or_previous_outcome_routing": False,
    }


def _search_main() -> None:
    _verify_dependencies()
    current = _load(
        "geotarget_spectral_cosh_current_adaptive_search_worker",
        CURRENT_SEARCH_WORKER,
    )
    spectral = _load(
        "geotarget_spectral_cosh_current_campaign_candidate",
        SPECTRAL_CANDIDATE,
    )
    install_search_patch(current, spectral)
    current.main()


def configure(*, frozen_root: Path):
    """Load the exact current worker and redirect only its search executable."""

    _verify_dependencies()
    wrapper = _load(
        "geotarget_spectral_cosh_current_adaptive_full_wrapper",
        CURRENT_FULL_WRAPPER,
    )
    control = wrapper.configure(frozen_root=frozen_root, enable_hybrid=True)
    base = control.CHAMPION.BASE
    authority = {
        name: getattr(base, name)
        for name in (
            "SCHEMA",
            "HP_BRIDGE",
            "PRECISION_RUNTIME",
            "RESTORATION_WORKER",
            "_authority_descriptor",
            "_descriptor_key",
            "_fresh_replay_candidates",
            "_run_hp_candidate",
            "_run_restoration_candidate",
            "_service_candidates",
        )
    }
    original_plan = base._plan
    base.SEARCH_WORKER = Path(__file__).resolve()

    def plan_wrapper(**kwargs):
        plan = dict(original_plan(**kwargs))
        plan.update(
            {
                "spectral_cosh_current_campaign": True,
                "spectral_cosh_worker_sha256": _sha256(Path(__file__)),
                "spectral_cosh_current_full_wrapper_sha256": EXPECTED_SHA256[
                    CURRENT_FULL_WRAPPER
                ],
                "spectral_cosh_side_rule": "original_start_ordinal_mod_4_equals_3",
                "spectral_cosh_baseline_minimum_share": 0.75,
                "spectral_cosh_zero_activation_byte_identical_fallback": True,
                "spectral_cosh_source_guard_replay_deadline_changed": False,
                "spectral_cosh_hp_or_final_authority_changed": False,
                "truth_case_family_target_or_previous_outcome_routing": False,
            }
        )
        return plan

    base._plan = plan_wrapper
    for name, value in authority.items():
        if getattr(base, name) is not value:
            raise RuntimeError(f"current campaign authority changed: {name}")
    return control


def main() -> None:
    if os.environ.get(SEARCH_CHILD_ENV) == "1":
        _search_main()
        return
    frozen_root = Path(
        os.environ.get("GEOTARGET_FROZEN_SOLVER_ROOT", str(DEFAULT_FROZEN_ROOT))
    ).resolve()
    control = configure(frozen_root=frozen_root)
    previous = os.environ.get(SEARCH_CHILD_ENV)
    os.environ[SEARCH_CHILD_ENV] = "1"
    try:
        control.main()
    finally:
        if previous is None:
            os.environ.pop(SEARCH_CHILD_ENV, None)
        else:
            os.environ[SEARCH_CHILD_ENV] = previous


if __name__ == "__main__":
    main()
