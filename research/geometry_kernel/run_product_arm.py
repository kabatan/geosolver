#!/usr/bin/env python3
"""Run a frozen campaign arm with the production parent-owned HP broker.

The campaign runner starts each solve in a guarded process group.  Product
execution keeps immutable HP preloaders in its long-lived parent process, so a
direct worker adapter would incorrectly charge preloader RSS to every solve.
This wrapper restores the production ownership boundary without changing the
worker, its inputs, or any solver decision.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

THREAD_ENVIRONMENT = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "GOTO_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "JULIA_NUM_PRECOMPILE_TASKS": "1",
    "JULIA_PKG_PRECOMPILE_AUTO": "0",
    "RAYON_NUM_THREADS": "1",
    "MALLOC_ARENA_MAX": "2",
    "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES": str(8 * 1024**3),
}


def _arm_base_commit(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("base_commit"), str):
        raise ValueError("arm manifest has no base commit")
    return value["base_commit"]


def _repository_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def _parse_cpus(value: str) -> tuple[int, ...]:
    cpus = tuple(int(item) for item in value.split(","))
    if not cpus or len(set(cpus)) != len(cpus) or any(cpu < 0 or cpu > 15 for cpu in cpus):
        raise ValueError("CPUs must be distinct values in [0,15]")
    return cpus


def _passthrough_arm(arguments: Sequence[str]) -> Path:
    try:
        index = arguments.index("--arm")
        value = arguments[index + 1]
    except (ValueError, IndexError) as error:
        raise ValueError("run_arm arguments must contain --arm PATH") from error
    return Path(value).expanduser().resolve()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root", type=Path, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--run-arm", type=Path, required=True)
    parser.add_argument("run_arm_arguments", nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)
    passthrough = list(arguments.run_arm_arguments)
    if passthrough and passthrough[0] == "--":
        passthrough.pop(0)
    try:
        root = arguments.product_root.expanduser().resolve()
        run_arm = arguments.run_arm.expanduser().resolve()
        cpus = _parse_cpus(arguments.cpus)
        arm_path = _passthrough_arm(passthrough)
        if not (root / "src/geotarget").is_dir() or not run_arm.is_file():
            raise ValueError("product root or frozen run_arm.py is unavailable")
        if _repository_head(root) != _arm_base_commit(arm_path):
            raise ValueError("product root HEAD differs from the frozen arm base commit")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error

    source = root / "src"
    sys.path.insert(0, str(source))
    from geotarget.runtime_broker import ProductRuntimeBroker

    hp_worker = (
        source
        / "geotarget/_engine/runtime/solver/research/experiments/EXP-V15-243-001"
        / "candidates/point_on_circle_periodic_semantics/"
        / "champion_composition_worker_no_1280.py"
    )
    environment = {**os.environ, **THREAD_ENVIRONMENT}
    with ProductRuntimeBroker(
        cpus=cpus,
        hp_worker=hp_worker,
        hp_environment=THREAD_ENVIRONMENT,
    ) as broker:
        token = broker.begin_session(cpus)
        try:
            environment.update(broker.session_environment(token))
            completed = subprocess.run(
                [sys.executable, str(run_arm), *passthrough],
                env=environment,
                check=False,
            )
        finally:
            broker.end_session(token)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
