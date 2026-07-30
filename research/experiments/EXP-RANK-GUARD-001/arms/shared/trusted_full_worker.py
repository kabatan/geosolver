#!/usr/bin/env python3
"""Full-v15 composition wrapper for the generated-qualified trust-v2 arm."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASE_FULL_WORKER = HERE / "full_worker.py"
BASE_FULL_WORKER_SHA256 = (
    "9697639a32ea9a4d420ab1be3b49e5419058cf4ed45c3831dbb960ca1a2a3c36"
)
TRUSTED_SEARCH_WORKER = HERE / "trusted_search_worker.py"
TRUSTED_SEARCH_WORKER_SHA256 = (
    "729ff1d7cf31b5d58ed822f975310efc5853680012fe30cec9d104ed3e732fbc"
)
TRUSTED_SEARCH_ADAPTER = HERE / "trusted_search_adapter.py"
TRUSTED_SEARCH_ADAPTER_SHA256 = (
    "3fc36b6ec622547f20317dee13d1a1af90ecf091046d41d4cfdc68ee3b778fd4"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load():
    if _sha256(BASE_FULL_WORKER) != BASE_FULL_WORKER_SHA256:
        raise RuntimeError("hash-bound charted v1 full worker changed")
    for path, expected in (
        (TRUSTED_SEARCH_WORKER, TRUSTED_SEARCH_WORKER_SHA256),
        (TRUSTED_SEARCH_ADAPTER, TRUSTED_SEARCH_ADAPTER_SHA256),
    ):
        if _sha256(path) != expected:
            raise RuntimeError(f"hash-bound trust-v2 file changed: {path}")
    name = "geotarget_exp_rank_guard_001_trusted_full_base"
    specification = importlib.util.spec_from_file_location(name, BASE_FULL_WORKER)
    if specification is None or specification.loader is None:
        raise ImportError(BASE_FULL_WORKER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def run() -> None:
    base = _load()
    base.CHARTED_SEARCH_WORKER = TRUSTED_SEARCH_WORKER
    base.CHARTED_SEARCH_WORKER_SHA256 = TRUSTED_SEARCH_WORKER_SHA256
    base.CHARTED_SEARCH_ADAPTER = TRUSTED_SEARCH_ADAPTER
    base.CHARTED_SEARCH_ADAPTER_SHA256 = TRUSTED_SEARCH_ADAPTER_SHA256
    original_decorate = base._decorate_plan

    def decorate(plan, *, mode, frozen_final_schema):
        result = original_decorate(
            plan, mode=mode, frozen_final_schema=frozen_final_schema
        )
        result.update(
            {
                "rank_guard_binding_schema": (
                    "geotarget.exp-rank-guard-001-trust-v2-plan/v1"
                ),
                "rank_guard_trust_v2_wrapper_sha256": _sha256(Path(__file__)),
                "proposal_overlay": (
                    "near-boundary finite-two-sided strict-bound headroom times "
                    "rank-confidence; "
                    "otherwise unchanged charted-v1 radii"
                ),
                "trust_v2_headroom_gate": 0.1,
                "trust_v2_minimum_outer_radius": 0.03125,
                "trust_v2_inner_ratio": 0.25,
                "radii_per_activation": 2,
                "callback_work_unchanged_from_charted_v1": True,
                "first_75_percent_and_insurance_unchanged": True,
                "tail_replacement_fraction": 0.25,
                "positive_semantic_guard_margin_available": False,
                "generated_stress_qualified_only": True,
                "formal_score_claim": False,
            }
        )
        return result

    base._decorate_plan = decorate
    base.run(base.CHARTED)


if __name__ == "__main__":
    run()
