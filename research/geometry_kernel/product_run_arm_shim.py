#!/usr/bin/env python3
"""Expose broker-correct product execution through the frozen run_arm CLI."""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Sequence
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[2]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from research.geometry_kernel.run_product_arm import _arm_base_commit  # noqa: E402
from research.geometry_kernel.run_product_arm import main as run_product_arm  # noqa: E402

REAL_RUN_ARM = Path(
    "/home/kabatan/work/solver-artifacts/geometry-kernel/20260731-e5abe0-baseline/"
    "experiment-harness/research/campaigns/EXP-GLOBAL-001/run_arm.py"
)
REAL_RUN_ARM_SHA256 = "e0b554fdd1c852656c942c5a25919cdd1c2b86b5c70a877ec83de4d3dcb7ae74"
PRODUCT_ROOTS = {
    "e5abe0c84b485273e06c38b1b69ce9efa3e02408": Path(
        "/home/kabatan/work/solver-wt/control-main-e5abe0"
    ),
    "720ae718d73c83cc542b7c946da2d644ee91a4aa": Path(
        "/home/kabatan/work/solver-wt/geometry-kernel-promote"
    ),
}


def _argument(arguments: Sequence[str], name: str) -> str:
    try:
        return arguments[arguments.index(name) + 1]
    except (ValueError, IndexError) as error:
        raise ValueError(f"missing required passthrough argument: {name}") from error


def _product_root(arguments: Sequence[str]) -> Path:
    arm = Path(_argument(arguments, "--arm")).expanduser().resolve()
    commit = _arm_base_commit(arm)
    try:
        return PRODUCT_ROOTS[commit]
    except KeyError as error:
        raise ValueError(f"no product root is frozen for arm base {commit}") from error


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if hashlib.sha256(REAL_RUN_ARM.read_bytes()).hexdigest() != REAL_RUN_ARM_SHA256:
            raise ValueError("frozen run_arm.py SHA-256 mismatch")
        root = _product_root(arguments)
        cpus = _argument(arguments, "--cpus")
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    return run_product_arm(
        [
            "--product-root",
            str(root),
            "--cpus",
            cpus,
            "--run-arm",
            str(REAL_RUN_ARM),
            "--",
            *arguments,
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
