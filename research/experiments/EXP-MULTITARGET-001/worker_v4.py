#!/usr/bin/env python3
"""Exact common control first, optional post-control descriptor union second."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping

import candidate_v4


DEFAULT_CONTROL_ROOT = Path(
    os.environ.get(
        "GEOTARGET_FROZEN_SOLVER_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
)
CONTROL_RELATIVE_ENTRYPOINT = Path(
    "research/experiments/EXP-V15-243-001/repro_20260722/workers/"
    "champion_v2_poc_preloaded.py"
)
EXPECTED_CONTROL_ENTRYPOINT_SHA256 = (
    "e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301"
)
CONTROL_CLOSURE = {
    CONTROL_RELATIVE_ENTRYPOINT: EXPECTED_CONTROL_ENTRYPOINT_SHA256,
    Path(
        "research/experiments/EXP-V15-243-001/repro_20260722/workers/"
        "precision_runtime_preload.py"
    ): "1139fa3ae5f4805b4791bc3f99fb6dd89b38f0cdc778c29871eb7d3469e3c403",
    Path(
        "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/champion_v2_wrapper.py"
    ): "0fc41efe21ab029e74ab8c3112d42271057d4dfeb808b52fea11500c2ae7003d",
    Path(
        "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/champion_v1_wrapper.py"
    ): "022bd5363adc5df51ff0e9c44d82dbced9f830dd9ea3271f0e4af26cf05e3d9c",
    Path(
        "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/approved_hp_bridge_v5.py"
    ): "812f7a2d761e7fe19c3991b9fcdffa5adb9d859aa36b034f7bfddaf201afb40f",
    Path(
        "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/champion_closure_manifest.py"
    ): "0e7910f33594ac600e85f964ca182e3bbc6835ca9a44a39db40d877e957542d5",
    Path(
        "research/experiments/EXP-V15-243-001/champion_v2/worker.py"
    ): "241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca",
    Path(
        "research/experiments/EXP-V15-243-001/champion_v1/worker.py"
    ): "9189a7e2c64a51c70a1cc41cca44ed35c561058c2ffc82d962410d8b913d3e14",
    Path(
        "research/experiments/EXP-V15-243-001/champion_v0/worker.py"
    ): "1a9b62f2b88657f0e43aa0c9fc2a794d686ea595a6544b1a75093e3d6239e889",
    Path(
        "research/experiments/EXP-V15-243-001/champion_v0/search_worker.py"
    ): "ce2dd5018037fbe5175fc63a2d20d9463243be58d4deeca3bc7cb1aed44e30bf",
    Path(
        "research/experiments/EXP-V15-243-001/candidates/"
        "endpoint_reservoir/candidate.py"
    ): "3224cc16b77c63eb8f0f9536678504f314da27a4ed299a4b1853ccc0e3887ef8",
    Path(
        "research/experiments/EXP-REAL61-008/"
        "finalist_numeric_worker_v15/worker.py"
    ): "330e52c75b98d3c58a1422cec415b5a53673ebafb7e90789a271df34a308309d",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_control_closure(root: Path) -> None:
    mismatches: dict[str, dict[str, str]] = {}
    for relative, expected in CONTROL_CLOSURE.items():
        path = root / relative
        actual = _sha256(path) if path.is_file() else "MISSING"
        if actual != expected:
            mismatches[str(relative)] = {"expected": expected, "actual": actual}
    if mismatches:
        raise SystemExit(
            "common control closure SHA-256 mismatch: "
            + json.dumps(mismatches, sort_keys=True)
        )


def _load_control(root: Path):
    _verify_control_closure(root)
    path = root / CONTROL_RELATIVE_ENTRYPOINT
    worker_directory = str(path.parent)
    if worker_directory not in sys.path:
        sys.path.insert(0, worker_directory)
    specification = importlib.util.spec_from_file_location(
        "geotarget_exp_multitarget_001_common_control_result_union_v4", path
    )
    if specification is None or specification.loader is None:
        raise SystemExit(f"cannot import common control: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    preload = sys.modules.get("precision_runtime_preload")
    if preload is None or Path(str(preload.__file__)).resolve() != (
        path.parent / "precision_runtime_preload.py"
    ).resolve():
        raise SystemExit("common control precision preload provenance mismatch")
    return module


def _observe_arguments(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--control-root", type=Path, default=DEFAULT_CONTROL_ROOT)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--total-seconds", type=float, default=180.0)
    parser.add_argument("--cpu", type=int, default=13)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    observed, _unknown = parser.parse_known_args(argv)
    cleaned: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == "--control-root":
            index += 2
            continue
        if argv[index].startswith("--control-root="):
            index += 1
            continue
        cleaned.append(argv[index])
        index += 1
    return observed, cleaned


def _source_dimension(source: Path) -> int:
    document = json.loads(source.read_text(encoding="utf-8"))
    variables = document.get("variables") if isinstance(document, Mapping) else None
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(names, list):
        raise RuntimeError("common control source dimension unavailable")
    return len(names)


def main() -> None:
    observed, control_arguments = _observe_arguments(sys.argv[1:])
    control = _load_control(observed.control_root.resolve())

    # Invoke the exact formal control entrypoint first. Nothing in CHAMPION,
    # its periodic semantics, precision preload, BASE, plan, or argv is patched.
    sys.argv = [sys.argv[0], *control_arguments]
    control.main()
    if not observed.execute:
        return

    candidate_v4.snapshot_common_control_result(observed.output)
    if _source_dimension(observed.source) == 0:
        return

    base = control.CHAMPION.BASE
    minimum_side_window = (
        candidate_v4.REPLAY_MIN_SECONDS
        + base.MIN_HP_ATTEMPT_SECONDS
        + candidate_v4.SNAPSHOT_AND_UNION_RESERVE_SECONDS
    )
    if (
        base.PROCESS_STARTED + observed.total_seconds - time.monotonic()
        < minimum_side_window
    ):
        # No-slack RESULT is solely the exact common control's durable output.
        return

    outcome = candidate_v4.extend_common_control_result(
        base,
        source=observed.source,
        source_sha256=observed.source_sha256,
        total_seconds=observed.total_seconds,
        cpu=observed.cpu,
        output=observed.output,
    )
    print(json.dumps(outcome, sort_keys=True))


if __name__ == "__main__":
    main()
