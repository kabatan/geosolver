#!/usr/bin/env python3
"""Wave3: exact-identity cache baseline feeding Repair B's DiGS surplus tail."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from threading import Lock
from typing import Mapping


HERE = Path(__file__).resolve().parent
REPAIR_B = HERE.parent / "diffusive_gibbs_repair_b_authority_v1/worker.py"
CACHE_REFERENCE_WORKER = HERE / "authority_cache_reference_worker.py"
CACHE_CANDIDATE = HERE / "authority_cache_candidate.py"
EXPECTED = {
    REPAIR_B: "1dd115da19b201a494b2fc2d20b51f6fbd66ef6008d959f09539cd06065840d6",
    CACHE_REFERENCE_WORKER: "357f9a19aa54aaa0999df2b6df340e4a3a5a9896bba6346961d006a89a0fc8ec",
    CACHE_CANDIDATE: "3acc3a09207c17a21cbe8708d3741fb7a65a9ec00ac85aca329907a6bf760e33",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify() -> None:
    for path, expected in EXPECTED.items():
        if not path.is_file() or _sha256(path) != expected:
            raise RuntimeError(f"Wave3 cache/Repair-B closure mismatch: {path}")


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _cache_class():
    # Authenticate the copied policy before executing its module body.
    if _sha256(CACHE_CANDIDATE) != EXPECTED[CACHE_CANDIDATE]:
        raise RuntimeError("authority cache policy changed before import")
    module = _load("geotarget_wave3_confirmed_identity_cache", CACHE_CANDIDATE)
    return module.ConfirmedIdentityCache


def _identity(exact, value: object):
    if not isinstance(value, Mapping):
        return None
    return exact.boundary.descriptor_identity(value.get("descriptor"))


def _duplicate_terminal(ordinary: Mapping[str, object], candidate: object) -> dict[str, object]:
    return {
        "attempt_kind": "DUPLICATE_AFTER_EXACT_AUTHORITY",
        "endpoint_float64_sha256": getattr(candidate, "endpoint_sha256", None),
        "residual_inf": getattr(candidate, "residual_inf", None),
        "provisional_target": getattr(candidate, "provisional_target", None),
        "cluster_ordinal": getattr(candidate, "cluster_ordinal", None),
        "cluster_rank": getattr(candidate, "cluster_rank", None),
        "status": "DUPLICATE_CONFIRMED_TARGET_SKIPPED",
        "authority_pass": False,
        "descriptor": None,
        "ordinary_hp_proposal": dict(ordinary),
        "ordinary_descriptor_is_final_authority": False,
        "confirmed_identity_cache_hit": True,
        "case_family_truth_target_count_routing": False,
    }


def install_cache(exact) -> dict[str, object]:
    """Capture ordinary and exact once, after exact_outer and before Repair B."""

    base = exact.BASE
    if getattr(base, "_geotarget_exact_authority_cache_v1", False):
        raise RuntimeError("exact authority cache installed twice")
    original_exact = base._run_hp_candidate
    original_ordinary = exact._ORDINARY_HP
    if original_exact is not exact._run_exact_outer:
        raise RuntimeError("cache must capture the pristine installed exact_outer")
    cache = _cache_class()()
    call_lock = Lock()
    statistics: dict[str, object] = {
        "ordinary_attempts": 0,
        "exact_outer_attempts": 0,
        "cache_hits": 0,
        "confirmed_identity_count": 0,
    }

    def run_cached(**kwargs):
        # Frozen baseline services this callable serially.  The lock also makes
        # temporary ordinary reuse fail closed if that assumption changes.
        with call_lock:
            ordinary = original_ordinary(**kwargs)
            statistics["ordinary_attempts"] = int(statistics["ordinary_attempts"]) + 1
            ordinary_identity = (
                _identity(exact, ordinary) if exact._ordinary_ready(ordinary) else None
            )
            if cache.already_confirmed(ordinary_identity):
                statistics["cache_hits"] = int(statistics["cache_hits"]) + 1
                return _duplicate_terminal(ordinary, kwargs["candidate"])

            saved = exact._ORDINARY_HP
            if saved is not original_ordinary:
                raise RuntimeError("exact_outer ordinary callable changed after capture")
            exact._ORDINARY_HP = lambda **_unused: ordinary
            try:
                result = original_exact(**kwargs)
            finally:
                exact._ORDINARY_HP = saved
            statistics["exact_outer_attempts"] = int(
                statistics["exact_outer_attempts"]
            ) + 1
            if isinstance(result, Mapping) and result.get("authority_pass") is True:
                cache.confirm(_identity(exact, result))
                statistics["confirmed_identity_count"] = cache.count()
            return result

    base._run_hp_candidate = run_cached
    base._geotarget_exact_authority_cache_v1 = True
    base._geotarget_exact_authority_cache_statistics = statistics

    original_plan = base._plan

    def plan(**kwargs):
        document = original_plan(**kwargs)
        closure = {
            str(path.resolve()): expected for path, expected in EXPECTED.items()
        }
        document.update({
            "wave3_exact_cache_repair_b": True,
            "wave3_install_order": [
                "exact_outer_capture_once",
                "confirmed_identity_cache_capture_once",
                "repair_b_final_result_seam",
            ],
            "wave3_cache_reference_closure": closure,
            "wave3_cache_failed_or_first_confirmation_skipped": False,
            "wave3_problem_family_truth_routing": False,
            "wave3_shared_portfolio_framework": False,
            "wave3_worker_sha256": _sha256(Path(__file__)),
        })
        return document

    base._plan = plan
    return statistics


def main() -> None:
    _verify()
    repair = _load("geotarget_wave3_cache_repair_b_main", REPAIR_B)
    arguments = repair._arguments(sys.argv[1:])
    exact = repair.configure()
    statistics = install_cache(exact)
    original_side = repair._run_side

    def run_side(base, side_arguments, baseline):
        attempts, telemetry = original_side(base, side_arguments, baseline)
        telemetry["confirmed_identity_cache"] = dict(statistics)
        telemetry["cache_saved_confirmations_become_only_true_wall_surplus"] = True
        return attempts, telemetry

    repair._run_side = run_side
    repair.install_result_seam(exact.BASE, arguments)
    exact.main()


if __name__ == "__main__":
    main()
