"""Formal one-logical-CPU execution contract for candidate HP children.

Pinning to one logical CPU is stricter than merely requesting one physical
core: the child and all descendants, including Julia/CAS, inherit a singleton
affinity mask.  Threaded numerical runtimes are separately limited to one.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


THREAD_LIMIT_ENV = {
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "RAYON_NUM_THREADS": "1",
}


def selected_cpu() -> int:
    if not hasattr(os, "sched_getaffinity"):
        raise RuntimeError("Linux CPU affinity is required by the formal contract")
    allowed = sorted(os.sched_getaffinity(0))
    if not allowed:
        raise RuntimeError("process has no allowed CPU")
    return allowed[0]


def child_affinity_setter(cpu: int):
    if isinstance(cpu, bool) or not isinstance(cpu, int) or cpu < 0:
        raise ValueError("cpu must be a nonnegative integer")

    def pin() -> None:
        os.sched_setaffinity(0, {cpu})

    return pin


def child_environment(
    base: Mapping[str, str], *, pythonpath: str
) -> dict[str, str]:
    environment = dict(base)
    environment.update(THREAD_LIMIT_ENV)
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "CUDA_VISIBLE_DEVICES": "",
            "PYTHONPATH": pythonpath,
        }
    )
    return environment


def cpu_topology(cpu: int) -> dict[str, object]:
    root = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")

    def read_integer(name: str) -> int | None:
        try:
            return int((root / name).read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return None

    return {
        "logical_cpu": cpu,
        "physical_package_id": read_integer("physical_package_id"),
        "core_id": read_integer("core_id"),
        "singleton_logical_cpu_affinity": True,
        "descendants_inherit_affinity": True,
        "thread_limit_environment": dict(sorted(THREAD_LIMIT_ENV.items())),
    }


__all__ = [
    "THREAD_LIMIT_ENV",
    "child_affinity_setter",
    "child_environment",
    "cpu_topology",
    "selected_cpu",
]

