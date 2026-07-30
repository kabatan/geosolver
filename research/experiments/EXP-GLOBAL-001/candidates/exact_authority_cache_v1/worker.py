#!/usr/bin/env python3
"""Exact-outer worker with candidate-private confirmed-identity caching."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
from typing import Mapping

from candidate import ConfirmedIdentityCache


FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
OUTER_PATH = (
    FROZEN_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "exact_outer_decorator/worker.py"
)
os.environ["GEOTARGET_EXACT_OUTER_MODE"] = "CONFIRM_ALL_AUTHORITIES"


def _load_outer():
    name = "geotarget_exp_global_exact_authority_cache_v1_outer"
    spec = importlib.util.spec_from_file_location(name, OUTER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(OUTER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OUTER = _load_outer()
BASE = OUTER.BASE
_ORIGINAL_EXACT_OUTER = BASE._run_hp_candidate
_ORIGINAL_ORDINARY = OUTER._ORDINARY_HP
_CACHE = ConfirmedIdentityCache()


def _identity(value: object):
    if not isinstance(value, Mapping):
        return None
    return OUTER.boundary.descriptor_identity(value.get("descriptor"))


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


def _run_cached(**kwargs):
    ordinary = _ORIGINAL_ORDINARY(**kwargs)
    ordinary_identity = _identity(ordinary) if OUTER._ordinary_ready(ordinary) else None
    if _CACHE.already_confirmed(ordinary_identity):
        return _duplicate_terminal(ordinary, kwargs["candidate"])

    # Reuse the already charged ordinary attempt.  The frozen exact-outer
    # function sees the same object and performs only its exact replay tail.
    saved = OUTER._ORDINARY_HP
    OUTER._ORDINARY_HP = lambda **_unused: ordinary
    try:
        result = _ORIGINAL_EXACT_OUTER(**kwargs)
    finally:
        OUTER._ORDINARY_HP = saved

    if isinstance(result, Mapping) and result.get("authority_pass") is True:
        _CACHE.confirm(_identity(result))
    return result


BASE._run_hp_candidate = _run_cached
BASE._geotarget_exact_authority_cache_v1 = True


def main() -> None:
    OUTER.main()


if __name__ == "__main__":
    main()
