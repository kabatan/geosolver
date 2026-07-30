#!/usr/bin/env python3
"""Deadline-isolated incremental continuation over the frozen champion."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Mapping, Sequence

from deadline_policy import (
    HARD_FINISH_MARGIN_SECONDS,
    MIN_CHILD_ALLOWANCE_SECONDS,
    continuation_seconds,
    internal_budget,
    run_bounded_process,
)


HERE = Path(__file__).resolve().parent
EXPERIMENT_ONE = HERE.parent / "EXP-EVAL-001"
FROZEN_RUNTIME = Path("/home/kabatan/work/solver-experiment-runtime")
FROZEN_SOLVER = FROZEN_RUNTIME / "solver"
FROZEN_ENTRYPOINT = (
    FROZEN_SOLVER
    / "research/experiments/EXP-V15-243-001/repro_20260722/workers"
    / "champion_v2_poc_preloaded.py"
)
EXPECTED_FROZEN_ENTRYPOINT_SHA256 = (
    "e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301"
)
CONTINUATION_CHILD = HERE / "continuation_child.py"
PHASE2_DIRECTORY = "exp-eval-003-continuation"
TELEMETRY_NAME = "EXP-EVAL-003-TELEMETRY.json"
SAFETY_FIELDS = (
    "source_bytes_unchanged",
    "truth_case_family_known_target_count_read",
    "source_or_problem_modified",
    "variables_or_equations_removed",
    "bounds_added_or_inferred",
    "gauge_or_symmetry_reduction",
    "coordinate_reparameterization",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--total-seconds", type=float, required=True)
    parser.add_argument("--search-seconds", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    values, _unknown = parser.parse_known_args(argv)
    if values.total_seconds <= 0.0 or values.search_seconds <= 0.0:
        raise SystemExit("total/search seconds must be positive")
    return values


def _replace_option(arguments: Sequence[str], name: str, value: float) -> list[str]:
    rewritten = list(arguments)
    try:
        index = rewritten.index(name)
    except ValueError as error:
        raise SystemExit(f"required worker option is absent: {name}") from error
    if index + 1 >= len(rewritten):
        raise SystemExit(f"required worker option has no value: {name}")
    rewritten[index + 1] = str(value)
    return rewritten


def _load_frozen():
    if not FROZEN_ENTRYPOINT.is_file():
        raise SystemExit(f"frozen champion is unavailable: {FROZEN_ENTRYPOINT}")
    if _sha256(FROZEN_ENTRYPOINT) != EXPECTED_FROZEN_ENTRYPOINT_SHA256:
        raise SystemExit("frozen champion SHA-256 mismatch")
    for path in (FROZEN_ENTRYPOINT.parent, FROZEN_SOLVER):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    name = "geotarget_exp_eval_003_frozen_champion"
    specification = importlib.util.spec_from_file_location(name, FROZEN_ENTRYPOINT)
    if specification is None or specification.loader is None:
        raise ImportError(FROZEN_ENTRYPOINT)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _candidate_is_safe(
    candidate: Mapping[str, Any], initial: Mapping[str, Any], source_sha256: str
) -> bool:
    return bool(
        candidate.get("schema_version") == initial.get("schema_version")
        == "geotarget.exp008-finalist-numeric-worker-v15/v1"
        and candidate.get("completed") is True
        and candidate.get("source_sha256") == source_sha256
        and all(candidate.get(name) == initial.get(name) for name in SAFETY_FIELDS)
    )


def _promote_artifacts(output: Path, phase2: Path) -> None:
    for name in ("search.json", "candidate-reservoir.json"):
        source = phase2 / name
        if source.is_file():
            temporary = output / f".{name}.exp-eval-003.tmp"
            shutil.copyfile(source, temporary)
            os.replace(temporary, output / name)


def _thread_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment["GEOTARGET_PRODUCT_PYTHON"] = sys.executable
    prefixes = (
        str(FROZEN_RUNTIME / "geosolver/src"),
        str(FROZEN_SOLVER),
        str(EXPERIMENT_ONE),
    )
    inherited = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        (*prefixes, inherited) if inherited else prefixes
    )
    return environment


def main() -> None:
    options = _arguments(sys.argv[1:])
    started = time.monotonic()
    outer_deadline = started + options.total_seconds
    latest_child_finish = outer_deadline - HARD_FINISH_MARGIN_SECONDS
    budget = internal_budget(options.total_seconds, options.search_seconds)
    environment = _thread_environment()
    os.environ.update(environment)
    if str(EXPERIMENT_ONE) not in sys.path:
        sys.path.insert(0, str(EXPERIMENT_ONE))

    frozen = _load_frozen()
    from incremental_reservoir import install_initial_checkpoint

    output = options.output.resolve()
    install_initial_checkpoint(
        frozen.CHAMPION.BASE,
        output / "candidate-reservoir.json",
        options.source_sha256,
    )
    frozen_arguments = _replace_option(
        sys.argv[1:], "--total-seconds", budget.total_seconds
    )
    frozen_arguments = _replace_option(
        frozen_arguments, "--search-seconds", budget.search_seconds
    )
    original_arguments = sys.argv
    sys.argv = [str(FROZEN_ENTRYPOINT), *frozen_arguments]
    try:
        frozen.main()
    finally:
        sys.argv = original_arguments
    if not options.execute:
        return

    initial_path = output / "RESULT.json"
    initial = _load_json(initial_path)
    selected = initial
    phase2 = output / PHASE2_DIRECTORY
    seconds = continuation_seconds(
        latest_finish=latest_child_finish, now=time.monotonic()
    )
    child_outcome = None
    child_telemetry: dict[str, Any] | None = None
    promoted = False
    promotion_reason = "initial-result-retained-no-continuation-margin"
    if seconds >= MIN_CHILD_ALLOWANCE_SECONDS and (output / "search.json").is_file():
        command = [
            sys.executable,
            str(CONTINUATION_CHILD),
            "--source",
            str(options.source.resolve()),
            "--source-sha256",
            options.source_sha256,
            "--initial-output",
            str(output),
            "--output",
            str(phase2),
            "--seconds",
            str(seconds),
            "--cpu",
            str(options.cpu),
            "--seed",
            str(options.seed),
        ]
        child_outcome = run_bounded_process(
            command,
            latest_finish=latest_child_finish,
            environment=environment,
            cwd=FROZEN_SOLVER,
        )
        child_result_path = phase2 / "RESULT.json"
        child_telemetry_path = phase2 / "EXP-EVAL-003-CHILD-TELEMETRY.json"
        if child_telemetry_path.is_file():
            child_telemetry = _load_json(child_telemetry_path)
        overlay = (
            child_telemetry.get("incremental_overlay")
            if isinstance(child_telemetry, Mapping)
            else None
        )
        child_artifacts_complete = bool(
            child_outcome.accepted
            or child_outcome.classification == "HARD_DEADLINE_TERMINATED"
        )
        if (
            child_artifacts_complete
            and child_result_path.is_file()
            and isinstance(overlay, Mapping)
            and time.monotonic() <= outer_deadline - 1.0
        ):
            candidate = _load_json(child_result_path)
            if _candidate_is_safe(candidate, initial, options.source_sha256):
                selected = candidate
                _promote_artifacts(output, phase2)
                promoted = True
                promotion_reason = (
                    "incremental-continuation-promoted"
                    if child_outcome.accepted
                    else "incremental-continuation-promoted-after-bounded-cleanup"
                )
            else:
                promotion_reason = "initial-result-retained-authority-mismatch"
        elif child_outcome.classification == "HARD_DEADLINE_TERMINATED":
            promotion_reason = "initial-result-retained-hard-deadline"
        else:
            promotion_reason = "initial-result-retained-child-not-accepted"
    elif not (output / "search.json").is_file():
        promotion_reason = "initial-result-retained-search-artifact-absent"

    telemetry = {
        "schema_version": "geotarget.exp-eval-003-telemetry/v1",
        "outer_total_seconds": options.total_seconds,
        "internal_initial_total_seconds": budget.total_seconds,
        "internal_initial_search_seconds": budget.search_seconds,
        "hard_finish_margin_seconds": HARD_FINISH_MARGIN_SECONDS,
        "requested_continuation_seconds": seconds,
        "continuation_promoted": promoted,
        "status": promotion_reason,
        "child": (
            {
                "classification": child_outcome.classification,
                "returncode": child_outcome.returncode,
                "elapsed_seconds": child_outcome.elapsed_seconds,
                "stderr_tail": child_outcome.stderr_tail,
            }
            if child_outcome is not None
            else None
        ),
        "incremental_overlay": (
            child_telemetry.get("incremental_overlay")
            if isinstance(child_telemetry, Mapping)
            else None
        ),
        "canonical_authority_modified": False,
        "hp_or_exactification_modified": False,
        "frozen_result_schema_preserved": True,
    }
    _atomic_json(output / TELEMETRY_NAME, telemetry)
    elapsed = time.monotonic() - started
    selected = dict(selected)
    selected["elapsed_wall_seconds"] = elapsed
    selected["within_total_wall_budget"] = elapsed <= options.total_seconds
    _atomic_json(initial_path, selected)


if __name__ == "__main__":
    main()
