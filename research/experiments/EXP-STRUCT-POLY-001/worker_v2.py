#!/usr/bin/env python3
"""Leftover-only full-v15 arm for EXP-STRUCT-POLY-001."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Mapping

from btf_polynomial_pipeline import (
    detect_btf_polynomial_plan,
    run_btf_polynomial_side_route,
)
from leftover_overlay import install_leftover_only


HERE = Path(__file__).resolve().parent
MAXIMUM_GENERATION_SECONDS = 2.0
MAXIMUM_SYMBOLIC_BLOCKS = 4
MAXIMUM_CARTESIAN_PROPOSALS = 32
SOURCE_REPLAY_SECONDS = 0.5
BASELINE_QUOTA = 0.75
EXPECTED_DEPENDENCY_SHA256 = {
    "block_structure.py": "9cb9ce02dc75c63945e350561509e73bbbea401091f400a8cdc0ed69b3dada06",
    "polynomial_side_route.py": "d7ccd1c9cd63135b4092d957ec15b7965cfba8bf82ea2a37553615a2e8a666c3",
    "btf_polynomial_pipeline.py": "9ac89ed200e97a80a2b91d44f338600c4d586c0ddad973e36785b8629f3ce557",
    "leftover_overlay.py": "8c4a2ea497fc033614697e58eaa370153ab97191f09e2bcc6c713fa84322ca79",
}
LAST_FACTORY_AUDIT: dict[str, object] = {}


def _load_v1_worker():
    name = "geotarget_exp_struct_poly_001_v1_support"
    specification = importlib.util.spec_from_file_location(name, HERE / "worker.py")
    if specification is None or specification.loader is None:
        raise ImportError(HERE / "worker.py")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


V1 = _load_v1_worker()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _mechanism_hash() -> str:
    return _sha256(Path(__file__).read_bytes())


def _closure_hash() -> str:
    return _sha256(
        b"".join(
            path.read_bytes()
            for path in (
                HERE.parent / "EXP-STRUCT-001/block_structure.py",
                HERE.parent / "EXP-POLY-001/polynomial_side_route.py",
                HERE / "btf_polynomial_pipeline.py",
                HERE / "leftover_overlay.py",
            )
        )
    )


def _verify_closure() -> None:
    if not V1.FROZEN_PYTHON.is_file() or not V1.FROZEN_WORKER.is_file():
        raise RuntimeError("frozen full-v15 champion closure is unavailable")
    if _sha256(V1.FROZEN_WORKER.read_bytes()) != V1.EXPECTED_FROZEN_WORKER_SHA256:
        raise RuntimeError("frozen full-v15 champion digest changed")
    dependencies = {
        "block_structure.py": HERE.parent / "EXP-STRUCT-001/block_structure.py",
        "polynomial_side_route.py": HERE.parent / "EXP-POLY-001/polynomial_side_route.py",
        "btf_polynomial_pipeline.py": HERE / "btf_polynomial_pipeline.py",
        "leftover_overlay.py": HERE / "leftover_overlay.py",
    }
    for name, path in dependencies.items():
        if not path.is_file() or _sha256(path.read_bytes()) != EXPECTED_DEPENDENCY_SHA256[name]:
            raise RuntimeError(f"leftover-only dependency changed: {name}")
    arm = json.loads((HERE / "arm-v2.json").read_text(encoding="utf-8"))
    if not isinstance(arm, Mapping) or arm.get("mechanism_hash") != _mechanism_hash():
        raise RuntimeError("v2 common arm mechanism hash mismatch")


def _proposal_factory(document, starts, generation_budget):
    LAST_FACTORY_AUDIT.clear()
    began = time.monotonic()
    budget = min(MAXIMUM_GENERATION_SECONDS, float(generation_budget))
    if not math.isfinite(budget) or budget <= 0.26:
        LAST_FACTORY_AUDIT.update(
            {"status": "NO_LEFTOVER_GENERATION_SLOT", "proposal_count": 0}
        )
        return ()
    result = run_btf_polynomial_side_route(
        document,
        starts[0],
        lambda _point: False,
        total_starts=4,
        baseline_quota=BASELINE_QUOTA,
        timeout_seconds=budget,
        maximum_symbolic_blocks=MAXIMUM_SYMBOLIC_BLOCKS,
        maximum_cartesian_proposals=MAXIMUM_CARTESIAN_PROPOSALS,
    )
    elapsed = time.monotonic() - began
    LAST_FACTORY_AUDIT.update(
        {
            "status": result.status,
            "active_polynomial_blocks": len(result.plan.active_blocks),
            "proposal_count": len(result.proposals),
            "locally_verified_count": len(result.verified),
            "generation_budget_seconds": budget,
            "elapsed_seconds": elapsed,
            "within_leftover_generation_budget": elapsed <= budget,
            "local_candidate_authority": False,
        }
    )
    if elapsed > budget or result.status != "complete":
        return ()
    return result.proposals


def install_full_v15_v2(document: Mapping[str, object]):
    _verify_closure()
    frozen = V1._load_frozen()
    audit = install_leftover_only(
        frozen.CHAMPION,
        proposal_factory=_proposal_factory,
        mechanism_hash=_mechanism_hash(),
        maximum_proposals=MAXIMUM_CARTESIAN_PROPOSALS,
        maximum_generation_seconds=MAXIMUM_GENERATION_SECONDS,
        source_replay_seconds=SOURCE_REPLAY_SECONDS,
    )
    return frozen, audit


def main() -> None:
    arguments = tuple(sys.argv[1:])
    source = V1._source(arguments)
    if source is None:
        V1._delegate(arguments)
    _path, document = source
    if not detect_btf_polynomial_plan(document).applicable:
        V1._delegate(arguments)
    frozen, audit = install_full_v15_v2(document)
    frozen.main()
    raw_output = V1._argument(arguments, "--output")
    if raw_output is not None:
        V1._atomic_json(
            Path(raw_output).resolve() / "EXP-STRUCT-POLY-001-V2-TELEMETRY.json",
            {
                "schema_version": "geotarget.exp-struct-poly-001-v2-telemetry/v1",
                "mechanism_hash": _mechanism_hash(),
                "closure_hash": _closure_hash(),
                "source_sha256": V1._argument(arguments, "--source-sha256"),
                "leftover_schedule": audit(),
                "proposal_factory": dict(LAST_FACTORY_AUDIT),
                "baseline_search_or_quota_modified": False,
                "local_candidate_authority": False,
            },
        )


if __name__ == "__main__":
    main()
