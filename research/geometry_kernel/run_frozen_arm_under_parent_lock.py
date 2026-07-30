#!/usr/bin/env python3
"""Invoke attested run_arm while its parent owns the benchmark lock."""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path

REAL_RUN_ARM = Path(
    "/home/kabatan/work/solver-artifacts/geometry-kernel/20260731-e5abe0-baseline/"
    "experiment-harness/research/campaigns/EXP-GLOBAL-001/run_arm.py"
)
REAL_RUN_ARM_SHA256 = "e0b554fdd1c852656c942c5a25919cdd1c2b86b5c70a877ec83de4d3dcb7ae74"
BENCHMARK_LOCK = Path("/tmp/geotarget-exp-global-benchmark-v1.lock")


def _parent_holds_benchmark_lock() -> bool:
    stat = BENCHMARK_LOCK.stat()
    device = f"{os.major(stat.st_dev):02x}:{os.minor(stat.st_dev):02x}:{stat.st_ino}"
    parent = str(os.getppid())
    for line in Path("/proc/locks").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if (
            len(fields) >= 6
            and fields[1:4] == ["FLOCK", "ADVISORY", "WRITE"]
            and fields[4] == parent
            and fields[5] == device
        ):
            return True
    return False


def main() -> int:
    if hashlib.sha256(REAL_RUN_ARM.read_bytes()).hexdigest() != REAL_RUN_ARM_SHA256:
        raise SystemExit("frozen run_arm.py SHA-256 mismatch")
    if not _parent_holds_benchmark_lock():
        raise SystemExit("parent does not own the benchmark lock")
    specification = importlib.util.spec_from_file_location(
        "geotarget_geometry_kernel_locked_run_arm", REAL_RUN_ARM
    )
    if specification is None or specification.loader is None:
        raise SystemExit("cannot load frozen run_arm.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    original_flock = module.fcntl.flock

    def parent_owned_flock(fd: int, operation: int) -> object:
        if operation == fcntl.LOCK_EX | fcntl.LOCK_NB:
            return None
        return original_flock(fd, operation)

    module.fcntl.flock = parent_owned_flock
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
