#!/usr/bin/env python3
"""Unmodified frozen-v15 run followed by truth-free RESULT set union."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import candidate_v3


DEFAULT_FROZEN_ROOT = Path(
    os.environ.get(
        "GEOTARGET_FROZEN_SOLVER_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
)
FROZEN_RELATIVE_WORKER = Path(
    "research/experiments/EXP-REAL61-008/finalist_numeric_worker_v15/worker.py"
)
EXPECTED_FROZEN_WORKER_SHA256 = (
    "330e52c75b98d3c58a1422cec415b5a53673ebafb7e90789a271df34a308309d"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_frozen(root: Path):
    path = root / FROZEN_RELATIVE_WORKER
    if not path.is_file():
        raise SystemExit(f"frozen numerical-v15 worker is unavailable: {path}")
    if _sha256(path) != EXPECTED_FROZEN_WORKER_SHA256:
        raise SystemExit("frozen numerical-v15 worker SHA-256 mismatch")
    specification = importlib.util.spec_from_file_location(
        "geotarget_exp_multitarget_001_frozen_v15_result_union_v3", path
    )
    if specification is None or specification.loader is None:
        raise SystemExit(f"cannot import frozen worker: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _observe_arguments(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--frozen-root", type=Path, default=DEFAULT_FROZEN_ROOT)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--total-seconds", type=float, default=180.0)
    parser.add_argument("--cpu", type=int, default=13)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    observed, frozen = parser.parse_known_args(argv)
    # parse_known_args removes options owned here. Reconstruct the exact frozen
    # argv from the original list minus only the overlay-specific root option.
    cleaned: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == "--frozen-root":
            index += 2
            continue
        if argv[index].startswith("--frozen-root="):
            index += 1
            continue
        cleaned.append(argv[index])
        index += 1
    return observed, cleaned


def main() -> None:
    observed, frozen_arguments = _observe_arguments(sys.argv[1:])
    base = _load_frozen(observed.frozen_root.resolve())

    # No frozen function, constant, deadline, interpreter, plan, or argv field
    # is patched. base.main first materializes the complete baseline RESULT.
    sys.argv = [sys.argv[0], *frozen_arguments]
    base.main()
    if not observed.execute:
        return

    minimum_side_window = (
        candidate_v3.REPLAY_MIN_SECONDS
        + base.MIN_HP_ATTEMPT_SECONDS
        + candidate_v3.SNAPSHOT_AND_UNION_RESERVE_SECONDS
    )
    if (
        base.PROCESS_STARTED + observed.total_seconds - time.monotonic()
        < minimum_side_window
    ):
        # The no-slack path performs no RESULT read or write. Apart from this
        # clock check, execution has already returned from unmodified v15.
        return

    outcome = candidate_v3.extend_frozen_result(
        base,
        source=observed.source,
        source_sha256=observed.source_sha256,
        total_seconds=observed.total_seconds,
        cpu=observed.cpu,
        output=observed.output,
    )
    # Telemetry is printed rather than written after the deadline. RESULT and
    # its optional byte-exact baseline snapshot are the only durable products.
    print(json.dumps(outcome.to_dict(), sort_keys=True))


if __name__ == "__main__":
    main()
