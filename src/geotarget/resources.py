from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import psutil

from geotarget.models import SolveOptions


class ResourceError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceReservation:
    physical_cpus: tuple[int, ...]
    available_memory_bytes: int


BYTES_PER_WORKER = 1_500_000_000
AUTO_MEMORY_RESERVE_BYTES = 4 * 1024**3


def physical_cpu_ids() -> tuple[int, ...]:
    allowed = (
        set(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else set(range(os.cpu_count() or 1))
    )
    identities: dict[tuple[str, str], int] = {}
    for cpu in sorted(allowed):
        topology = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        try:
            package = (topology / "physical_package_id").read_text().strip()
            core = (topology / "core_id").read_text().strip()
        except OSError:
            package, core = "0", str(cpu)
        identities.setdefault((package, core), cpu)
    return tuple(identities.values())


def reserve(options: SolveOptions) -> ResourceReservation:
    physical = physical_cpu_ids()
    compatible = tuple(cpu for cpu in physical if 0 <= cpu < 16)
    available = psutil.virtual_memory().available
    if options.engine == "reference":
        if options.cores != 1:
            raise ResourceError("the byte-identical reference engine requires exactly one core")
        resolved_cores = 1
    elif options.cores == "auto":
        cpu_capacity = len(compatible) - 1
        memory_capacity = (available - AUTO_MEMORY_RESERVE_BYTES) // BYTES_PER_WORKER
        resolved_cores = min(cpu_capacity, memory_capacity)
        if resolved_cores < 1:
            raise ResourceError(
                "automatic core selection cannot reserve one physical core and 4 GiB of memory"
            )
    else:
        resolved_cores = options.cores
    if resolved_cores > len(physical):
        message = (
            f"requested {resolved_cores} cores, but only "
            f"{len(physical)} physical cores are available"
        )
        raise ResourceError(message)
    required = resolved_cores * BYTES_PER_WORKER
    if available < required:
        raise ResourceError(
            f"requested cores require {required} bytes, but only {available} bytes are available"
        )
    if len(compatible) < resolved_cores:
        raise ResourceError(
            f"requested {resolved_cores} cores, but only {len(compatible)} satisfy "
            "the frozen [0,15] affinity contract"
        )
    return ResourceReservation(
        physical_cpus=compatible[:resolved_cores], available_memory_bytes=available
    )
