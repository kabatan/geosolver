#!/usr/bin/env python3
"""Run one leftover-only continuation after a completed roweq180 HP attempt."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for path in (HERE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapter import AgedRestorationAuthoritySeam, endpoint_sha256, mechanism_manifest  # noqa: E402
from research.infrastructure.memory_safety.safe_subprocess import atomic_write_json  # noqa: E402


THREAD_NAMES = (
    "OMP_NUM_THREADS",
    "OMP_THREAD_LIMIT",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--endpoint-sha256")
    parser.add_argument("--authority-artifact", type=Path, required=True)
    parser.add_argument("--leftover-seconds", type=float, required=True)
    parser.add_argument("--leftover-callbacks", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    affinity = sorted(os.sched_getaffinity(0))
    environment = {name: os.environ.get(name) for name in THREAD_NAMES}
    if len(affinity) != 1:
        raise SystemExit("one pinned logical CPU required")
    if any(value != "1" for value in environment.values()):
        raise SystemExit(f"one-thread environment required: {environment}")
    if not (0.0 < arguments.leftover_seconds <= 60.0):
        raise SystemExit("leftover seconds must be in (0, 60]")
    if not (0 <= arguments.leftover_callbacks <= 600):
        raise SystemExit("leftover callbacks must be in [0, 600]")

    endpoint = json.loads(arguments.endpoint)
    if not isinstance(endpoint, list):
        raise SystemExit("endpoint must be a JSON array")
    observed_endpoint_sha = endpoint_sha256(endpoint)
    expected_endpoint_sha = arguments.endpoint_sha256 or observed_endpoint_sha
    authority = json.loads(arguments.authority_artifact.read_text(encoding="utf-8"))

    seam = AgedRestorationAuthoritySeam(
        arguments.source.read_bytes(),
        arguments.source_sha256,
        leftover_callback_cap=arguments.leftover_callbacks,
        deadline_monotonic=time.monotonic() + arguments.leftover_seconds,
    )
    decision = seam.enqueue(
        endpoint=endpoint,
        endpoint_sha256_value=expected_endpoint_sha,
        authority_artifact=authority,
        tick=0,
    )
    result = seam.service_oldest(tick=1)
    result["trigger"] = {
        "eligible": decision.eligible,
        "reason": decision.reason,
        "residual_inf": decision.residual_inf,
        "failure_reasons": list(decision.observed_failure_reasons),
    }
    result["mechanism_manifest"] = mechanism_manifest()
    result["cpu_affinity"] = affinity
    result["thread_environment"] = environment
    atomic_write_json(arguments.output, result)


if __name__ == "__main__":
    main()
