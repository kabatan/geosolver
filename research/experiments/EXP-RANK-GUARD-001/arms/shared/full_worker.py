#!/usr/bin/env python3
"""Hash-bound, proposal-only rank/guard arms over the frozen full v15 champion."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from typing import Mapping


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_FROZEN_SOLVER_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
PRELOADED_WORKER = RUNTIME_ROOT / (
    "research/experiments/EXP-V15-243-001/repro_20260722/workers/"
    "champion_v2_poc_preloaded.py"
)
PRELOADED_WORKER_SHA256 = (
    "e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301"
)
CHARTED_SEARCH_WORKER = HERE / "charted_search_worker.py"
CHARTED_SEARCH_WORKER_SHA256 = (
    "54b4f87ff589f40ff75a0f10ffff5228118d4b43795d35e697b7440eb63896bb"
)
CHARTED_SEARCH_ADAPTER = HERE / "charted_search_adapter.py"
CHARTED_SEARCH_ADAPTER_SHA256 = (
    "3c4128a38525373ea227cec6352eed3edc408d71e56cf82bcfec0db9c0d2382c"
)
CHARTED = "charted-weak-pair"
ADAPTED_CPQR_BLOCKED = "adapted-cpqr-blocked"
MODES = (CHARTED, ADAPTED_CPQR_BLOCKED)
ADAPTED_CPQR_BLOCKER = (
    "the frozen Python proposal seam exposes only the charged Float64 source "
    "callback; it does not expose a hash-bound 128/256/512-bit callback, so "
    "the adapted-CPQR stability certificate cannot be reproduced without "
    "changing the canonical/evaluator authority"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _verify_closure() -> None:
    expected = {
        PRELOADED_WORKER: PRELOADED_WORKER_SHA256,
        CHARTED_SEARCH_WORKER: CHARTED_SEARCH_WORKER_SHA256,
        CHARTED_SEARCH_ADAPTER: CHARTED_SEARCH_ADAPTER_SHA256,
    }
    for path, digest in expected.items():
        if not path.is_file() or _sha256(path) != digest:
            raise RuntimeError(f"hash-bound rank/guard closure changed: {path}")


def _closure_manifest() -> dict[str, object]:
    return {
        "schema_version": "geotarget.exp-rank-guard-001-closure/v1",
        "files": [
            {
                "role": role,
                "path": str(path.resolve()),
                "sha256": digest,
            }
            for role, path, digest in (
                ("frozen_full_worker", PRELOADED_WORKER, PRELOADED_WORKER_SHA256),
                (
                    "charted_search_worker",
                    CHARTED_SEARCH_WORKER,
                    CHARTED_SEARCH_WORKER_SHA256,
                ),
                (
                    "charted_search_adapter",
                    CHARTED_SEARCH_ADAPTER,
                    CHARTED_SEARCH_ADAPTER_SHA256,
                ),
            )
        ],
    }


def _decorate_plan(
    plan: Mapping[str, object],
    *,
    mode: str,
    frozen_final_schema: str,
) -> dict[str, object]:
    decorated = dict(plan)
    common = {
        "rank_guard_binding_schema": "geotarget.exp-rank-guard-001-plan/v1",
        "rank_guard_mode": mode,
        "rank_guard_shared_worker_sha256": _sha256(Path(__file__)),
        "rank_guard_closure": _closure_manifest(),
        "final_result_schema": frozen_final_schema,
        "final_result_schema_unchanged": True,
        "search_candidate_file_unchanged": True,
        "source_problem_modified": False,
        "variables_equations_or_bounds_modified": False,
        "source_replay_authority_modified": False,
        "hp_pslq_or_canonical_authority_modified": False,
        "truth_case_family_target_or_previous_outcome_routing": False,
        "baseline_prefix_minimum_fraction": 0.75,
        "counter_cauchy_insurance_period": 4,
    }
    if mode == CHARTED:
        common.update(
            {
                "proposal_overlay_active": True,
                "proposal_overlay": "strict-bound logit charted symmetric weak pair",
                "proposal_overlay_scope": "prefix proposals only",
                "overlay_callback_fraction_max": 0.05,
                "overlay_callback_absolute_max": 64,
                "frozen_local_kernel_unchanged": True,
                "adapted_cpqr_active": False,
            }
        )
    elif mode == ADAPTED_CPQR_BLOCKED:
        common.update(
            {
                "proposal_overlay_active": False,
                "adapted_cpqr_active": False,
                "adapted_cpqr_fail_closed": True,
                "adapted_cpqr_blocker": ADAPTED_CPQR_BLOCKER,
                "execution_route": "unchanged_frozen_champion",
            }
        )
    else:
        raise ValueError(f"unknown rank/guard mode: {mode!r}")
    decorated.update(common)
    return decorated


def run(mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"unknown rank/guard mode: {mode!r}")
    _verify_closure()
    for path in (PRELOADED_WORKER.parent, RUNTIME_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    preloaded = _load(
        f"geotarget_exp_rank_guard_001_frozen_{mode.replace('-', '_')}",
        PRELOADED_WORKER,
    )
    champion = preloaded.CHAMPION
    base = champion.BASE
    frozen_plan = base._plan
    frozen_final_schema = base.SCHEMA
    frozen_search_candidate = base.SEARCH_CANDIDATE
    frozen_search_candidate_digest = base.EXPECTED_SEARCH_CANDIDATE_SHA256
    frozen_hp_bridge = base.HP_BRIDGE
    frozen_restoration_worker = base.RESTORATION_WORKER
    frozen_descriptor_key = base._descriptor_key
    frozen_service_candidates = base._service_candidates

    if mode == CHARTED:
        base.SEARCH_WORKER = CHARTED_SEARCH_WORKER
        base.SEARCH_ADAPTER = CHARTED_SEARCH_ADAPTER

    def plan_wrapper(**kwargs):
        return _decorate_plan(
            frozen_plan(**kwargs),
            mode=mode,
            frozen_final_schema=frozen_final_schema,
        )

    base._plan = plan_wrapper

    # These assertions are executable custody checks, not documentation.
    if base.SCHEMA != frozen_final_schema:
        raise AssertionError("full solve-result schema changed")
    if base.SEARCH_CANDIDATE != frozen_search_candidate:
        raise AssertionError("frozen search candidate changed")
    if base.EXPECTED_SEARCH_CANDIDATE_SHA256 != frozen_search_candidate_digest:
        raise AssertionError("frozen search candidate digest authority changed")
    if base.HP_BRIDGE is not frozen_hp_bridge:
        raise AssertionError("HP bridge changed")
    if base.RESTORATION_WORKER is not frozen_restoration_worker:
        raise AssertionError("restoration worker changed")
    if base._descriptor_key is not frozen_descriptor_key:
        raise AssertionError("exact descriptor key changed")
    if base._service_candidates is not frozen_service_candidates:
        raise AssertionError("reservoir/HP service changed")

    preloaded.main()


__all__ = [
    "ADAPTED_CPQR_BLOCKED",
    "ADAPTED_CPQR_BLOCKER",
    "CHARTED",
    "MODES",
    "_decorate_plan",
    "run",
]
