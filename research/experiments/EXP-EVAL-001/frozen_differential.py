#!/usr/bin/env python3
"""Generated-source differential and microbenchmark for EXP-EVAL-001."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import struct
import sys
import tempfile
import time
from pathlib import Path

from incremental_reservoir import FrozenChampionAdapter, incremental_candidates


DEFAULT_RUNTIME = Path("/home/kabatan/work/solver-experiment-runtime/solver")
SOURCE_SHA256 = "e" * 64
PROBLEM = {
    "task": "solve",
    "id": "generated-exp-eval-001-two-circle-intersection",
    "variables": {"names": ["x", "y"]},
    "construction": [
        {"name": "A", "expr": "Point(0, 0)"},
        {"name": "C", "expr": "Point(6, 0)"},
        {"name": "B", "expr": "Point(x, y)"},
    ],
    "constraints": [
        {"def": "Distance(A, B)", "value": 5},
        {"def": "Distance(C, B)", "value": 5},
    ],
    "guards": ["AssumeGt(y, 0)"],
    "answer": "Distance(A, C)",
    "post_process": "",
}


def _load_base(runtime: Path):
    worker = (
        runtime
        / "research/experiments/EXP-V15-243-001/repro_20260722/workers"
        / "champion_v2_poc_preloaded.py"
    )
    sys.path.insert(0, str(worker.parent))
    specification = importlib.util.spec_from_file_location(
        "geotarget_exp_eval_001_frozen_differential", worker
    )
    if specification is None or specification.loader is None:
        raise ImportError(worker)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module.CHAMPION.BASE


def _rows(count: int) -> list[dict[str, object]]:
    # All points are source-semantic near roots, but no truth or known answer is
    # used.  Irregular deterministic offsets exercise ordering and float bytes.
    return [
        {
            "lane": index,
            "point": [
                3.0 + ((index * 37) % 31 - 15) * 1e-9,
                4.0 + ((index * 53) % 29 - 14) * 1e-9,
            ],
        }
        for index in range(count)
    ]


def _search(endpoints: list[dict[str, object]]) -> dict[str, object]:
    count = len(endpoints)
    return {
        "arm": "exp-eval-001",
        "seed": 0,
        "endpoints": endpoints,
        "literal_prefix": {"full_prefix_sha256": "a" * 64},
        "optimized_parallel_search": {
            "completed_start_ordinals": list(range(min(count, 256)))
        },
        "work": {"lanes_started": min(count, 256), "callbacks": count * 600},
        "budget": {"starts": 256, "callbacks_per_start": 600},
    }


def _bits(value: float) -> str:
    return struct.pack(">d", float(value)).hex()


def _characterize(reservoir) -> tuple[tuple[object, ...], ...]:
    values = tuple(reservoir) + tuple(reservoir.deadline_backlog)
    return tuple(
        (
            tuple(_bits(item) for item in candidate.endpoint),
            candidate.endpoint_sha256,
            _bits(candidate.residual_inf),
            candidate.cluster_ordinal,
            candidate.discovery_ordinal,
            candidate.admission_role,
            candidate.record_id,
            candidate.bucket_id,
            candidate.bucket_kind,
            candidate.aging_wave,
            candidate.semantic_verified,
        )
        for candidate in values
    )


def run(runtime: Path, probes: int, windows: int) -> dict[str, object]:
    if probes < windows or windows < 2:
        raise ValueError("probes must be >= windows >= 2")
    endpoints = _rows(probes)
    boundaries = sorted({math.ceil(probes * index / windows) for index in range(1, windows + 1)})
    base = _load_base(runtime)
    candidate_adapter = FrozenChampionAdapter(base)
    checkpoint: Path | None = None
    incremental_seconds = 0.0
    control_seconds = 0.0
    bit_identical_candidates = 0
    semantic_replays = 0
    modes: list[str] = []
    with tempfile.TemporaryDirectory(prefix="exp-eval-001-") as directory_text:
        directory = Path(directory_text)
        for ordinal, boundary in enumerate(boundaries, start=1):
            search = _search(endpoints[:boundary])
            output = directory / f"reservoir-{ordinal:03d}.json"
            started = time.perf_counter()
            observed = incremental_candidates(
                adapter=candidate_adapter,
                source_document=PROBLEM,
                search=search,
                source_sha256=SOURCE_SHA256,
                checkpoint_input=checkpoint,
                checkpoint_output=output,
                hard_deadline=time.monotonic() + 120.0,
                candidate_type=candidate_adapter.candidate_type,
                reservoir_type=candidate_adapter.reservoir_type,
            )
            incremental_seconds += time.perf_counter() - started
            control_adapter = FrozenChampionAdapter(base)
            started = time.perf_counter()
            expected = control_adapter.full_replay(
                PROBLEM,
                endpoints[:boundary],
                hard_deadline=time.monotonic() + 120.0,
            )
            control_seconds += time.perf_counter() - started
            expected_bytes = _characterize(expected)
            if _characterize(observed.reservoir) != expected_bytes:
                raise AssertionError(f"candidate mismatch at window {ordinal}")
            bit_identical_candidates += len(expected_bytes)
            semantic_replays += observed.semantic_replay_count
            modes.append(observed.mode)
            checkpoint = output
    expected_full_replay_count = sum(boundaries)
    return {
        "schema_version": "geotarget.exp-eval-001-frozen-differential/v1",
        "pinned_product_commit": "0967ff1c",
        "generated_source_only": True,
        "probes": probes,
        "windows": len(boundaries),
        "window_boundaries": boundaries,
        "bit_identical_candidates": bit_identical_candidates,
        "candidate_mismatches": 0,
        "incremental_semantic_replays": semantic_replays,
        "full_replay_semantic_replays": expected_full_replay_count,
        "semantic_replay_reduction_fraction": 1.0 - semantic_replays / expected_full_replay_count,
        "incremental_seconds": incremental_seconds,
        "full_replay_seconds": control_seconds,
        "speedup": control_seconds / incremental_seconds,
        "modes": modes,
        "unexpected_fallback_count": sum(
            mode == "full-replay" for mode in modes[1:]
        ),
        "unexpected_fallback_rate": (
            sum(mode == "full-replay" for mode in modes[1:]) / max(1, len(modes) - 1)
        ),
        "truth_read": False,
        "validation_or_sealed_read": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--probes", type=int, default=725)
    parser.add_argument("--windows", type=int, default=5)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.runtime, arguments.probes, arguments.windows), indent=2))


if __name__ == "__main__":
    main()
