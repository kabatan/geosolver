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
COMMON_CONTROL = (
    V1.FROZEN_ROOT
    / "research/experiments/EXP-V15-243-001/repro_20260722/workers/"
    "champion_v2_poc_preloaded.py"
)
EXPECTED_COMMON_CONTROL_SHA256 = (
    "e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301"
)
EXPECTED_COMMON_CONTROL_LAYERS = {
    "precision_runtime_preload.py": (
        V1.FROZEN_ROOT
        / "research/experiments/EXP-V15-243-001/repro_20260722/workers/"
        "precision_runtime_preload.py",
        "1139fa3ae5f4805b4791bc3f99fb6dd89b38f0cdc778c29871eb7d3469e3c403",
    ),
    "point_on_circle/champion_v2_wrapper.py": (
        V1.FROZEN_ROOT
        / "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/champion_v2_wrapper.py",
        "0fc41efe21ab029e74ab8c3112d42271057d4dfeb808b52fea11500c2ae7003d",
    ),
    "point_on_circle/champion_v1_wrapper.py": (
        V1.FROZEN_ROOT
        / "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/champion_v1_wrapper.py",
        "022bd5363adc5df51ff0e9c44d82dbced9f830dd9ea3271f0e4af26cf05e3d9c",
    ),
    "point_on_circle/approved_hp_bridge_v5.py": (
        V1.FROZEN_ROOT
        / "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/approved_hp_bridge_v5.py",
        "812f7a2d761e7fe19c3991b9fcdffa5adb9d859aa36b034f7bfddaf201afb40f",
    ),
    "point_on_circle/champion_closure_manifest.py": (
        V1.FROZEN_ROOT
        / "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/champion_closure_manifest.py",
        "0e7910f33594ac600e85f964ca182e3bbc6835ca9a44a39db40d877e957542d5",
    ),
    "champion_v2/worker.py": (
        V1.FROZEN_ROOT
        / "research/experiments/EXP-V15-243-001/champion_v2/worker.py",
        "241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca",
    ),
    "champion_v1/worker.py": (
        V1.FROZEN_ROOT
        / "research/experiments/EXP-V15-243-001/champion_v1/worker.py",
        "9189a7e2c64a51c70a1cc41cca44ed35c561058c2ffc82d962410d8b913d3e14",
    ),
}


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
    if not V1.FROZEN_PYTHON.is_file() or not COMMON_CONTROL.is_file():
        raise RuntimeError("frozen full-v15 champion closure is unavailable")
    if V1.FROZEN_WORKER.resolve() != COMMON_CONTROL.resolve():
        raise RuntimeError("v2 is not bound to the registered common control")
    if V1.EXPECTED_FROZEN_WORKER_SHA256 != EXPECTED_COMMON_CONTROL_SHA256:
        raise RuntimeError("v1 and v2 disagree on the common-control digest")
    if _sha256(COMMON_CONTROL.read_bytes()) != EXPECTED_COMMON_CONTROL_SHA256:
        raise RuntimeError("registered common-control digest changed")
    for name, (path, expected) in EXPECTED_COMMON_CONTROL_LAYERS.items():
        if not path.is_file() or _sha256(path.read_bytes()) != expected:
            raise RuntimeError(f"common-control periodic layer changed: {name}")
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
    loaded_layers = {
        "preloaded": Path(frozen.__file__).resolve(),
        "point_on_circle_v2": Path(frozen.CHAMPION.__file__).resolve(),
        "point_on_circle_v1": Path(frozen.CHAMPION.V1.__file__).resolve(),
        "original_v2": Path(frozen.CHAMPION.ORIGINAL_V2.__file__).resolve(),
        "original_v1": Path(frozen.CHAMPION.V1.ORIGINAL_V1.__file__).resolve(),
    }
    expected_layers = {
        "preloaded": COMMON_CONTROL.resolve(),
        "point_on_circle_v2": EXPECTED_COMMON_CONTROL_LAYERS[
            "point_on_circle/champion_v2_wrapper.py"
        ][0].resolve(),
        "point_on_circle_v1": EXPECTED_COMMON_CONTROL_LAYERS[
            "point_on_circle/champion_v1_wrapper.py"
        ][0].resolve(),
        "original_v2": EXPECTED_COMMON_CONTROL_LAYERS[
            "champion_v2/worker.py"
        ][0].resolve(),
        "original_v1": EXPECTED_COMMON_CONTROL_LAYERS[
            "champion_v1/worker.py"
        ][0].resolve(),
    }
    if loaded_layers != expected_layers:
        raise RuntimeError("loaded common-control layer graph changed")
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
