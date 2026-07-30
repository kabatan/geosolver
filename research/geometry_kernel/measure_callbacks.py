#!/usr/bin/env python3
"""Measure deterministic same-work residual and full-callback streams."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import resource
import struct
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

REPOSITORY = Path(
    os.environ.get("GEOTARGET_BENCH_REPOSITORY", Path(__file__).resolve().parents[2])
).resolve()
RUNTIME_ROOT = REPOSITORY / "src/geotarget/_engine/runtime"
GEOSOLVER_SOURCE = RUNTIME_ROOT / "geosolver/src"
if str(GEOSOLVER_SOURCE) not in sys.path:
    sys.path.insert(0, str(GEOSOLVER_SOURCE))
if str(REPOSITORY / "src") not in sys.path:
    sys.path.insert(0, str(REPOSITORY / "src"))

from geotarget.continuation import _load_frozen  # noqa: E402
from geotarget.search_pool_worker_entrypoint import (  # noqa: E402
    _activate_compiled_evaluator,
)

SCHEMA = "geotarget.geometry-kernel-same-work/v1"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _float_bytes(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _update_vector(digest: Any, values: Iterable[float]) -> None:
    materialized = tuple(float(value) for value in values)
    digest.update(struct.pack(">Q", len(materialized)))
    for value in materialized:
        digest.update(_float_bytes(value))


def _probes(
    source_sha256: str,
    dimension: int,
    count: int,
    *,
    include_boundaries: bool,
) -> tuple[tuple[float, ...], ...]:
    if dimension == 0:
        return ((),)
    probes: list[tuple[float, ...]] = []
    if include_boundaries:
        probes.extend(
            [
                tuple(0.0 for _ in range(dimension)),
                tuple(-0.0 if index % 2 else 0.0 for index in range(dimension)),
                tuple(
                    math.nextafter(0.0, 1.0) if index % 2 else -math.nextafter(0.0, 1.0)
                    for index in range(dimension)
                ),
                tuple(
                    math.nextafter(1.0, math.inf) if index % 2 else math.nextafter(-1.0, -math.inf)
                    for index in range(dimension)
                ),
            ]
        )
    seed = int(source_sha256[:16], 16)
    generator = random.Random(seed)
    target = count + (4 if include_boundaries else 0)
    while len(probes) < target:
        probes.append(tuple(generator.uniform(-8.0, 8.0) for _ in range(dimension)))
    return tuple(probes)


def _problem_paths(cases_root: Path) -> list[Path]:
    direct = sorted(cases_root.glob("*/problem.json"))
    if direct:
        return direct
    if cases_root.name == "problem.json" and cases_root.is_file():
        return [cases_root]
    raise ValueError(f"no */problem.json corpus found below {cases_root}")


def _backend_family(metadata: dict[str, Any]) -> str:
    mode = str(metadata.get("mode", "reference"))
    opcodes = metadata.get("opcodes")
    if not isinstance(opcodes, list):
        nested = metadata.get("raw_semantic_gate_metadata", {})
        opcodes = nested.get("opcodes", []) if isinstance(nested, dict) else []
    structural = json.dumps(sorted(str(value) for value in opcodes), separators=(",", ":"))
    return f"{mode}:{_sha256(structural.encode())[:12]}"


def _observation_digest(evaluator: Any, probes: Sequence[Sequence[float]]) -> str:
    digest = hashlib.sha256(b"geotarget.geometry-kernel-residual-stream/v1\0")
    for point in probes:
        result = evaluator.evaluate_float_residual(list(point))
        _update_vector(digest, point)
        _update_vector(digest, result.residual_vector)
        digest.update(str(result.evaluation_status).encode())
        digest.update(b"1" if result.is_finite else b"0")
        digest.update(_float_bytes(result.residual_norm_float))
    return digest.hexdigest()


def _callback_digest(budget: Any, probes: Sequence[Sequence[float]]) -> str:
    digest = hashlib.sha256(b"geotarget.geometry-kernel-callback-stream/v1\0")
    for point in probes:
        result = budget(np.asarray(point, dtype=float))
        _update_vector(digest, point)
        _update_vector(digest, result.residual)
        digest.update(b"1" if result.finite else b"0")
        digest.update(b"1" if result.semantics_valid else b"0")
        digest.update(_float_bytes(result.violation))
        _update_vector(digest, result.violation_vector)
    return digest.hexdigest()


def _time_calls(callable_: Any, points: Sequence[Sequence[float]], repeats: int) -> dict[str, Any]:
    completed = 0
    started_wall = time.perf_counter_ns()
    started_cpu = time.process_time_ns()
    for _ in range(repeats):
        for point in points:
            callable_(point)
            completed += 1
    cpu_ns = time.process_time_ns() - started_cpu
    wall_ns = time.perf_counter_ns() - started_wall
    return {
        "completed": completed,
        "wall_ns": wall_ns,
        "cpu_ns": cpu_ns,
        "throughput_per_second": completed / (wall_ns / 1_000_000_000),
    }


def measure(arguments: argparse.Namespace) -> dict[str, Any]:
    base = _load_frozen(RUNTIME_ROOT)
    runtime = base._load_module("geotarget_geometry_kernel_measure_runtime", base.PRECISION_RUNTIME)
    rows: list[dict[str, Any]] = []
    input_stream = hashlib.sha256(b"geotarget.geometry-kernel-input-stream/v1\0")
    output_stream = hashlib.sha256(b"geotarget.geometry-kernel-output-stream/v1\0")
    paths = _problem_paths(arguments.cases_root)
    for ordinal, path in enumerate(paths, start=1):
        print(f"measure {ordinal}/{len(paths)} {path.parent.name}", file=sys.stderr, flush=True)
        payload = path.read_bytes()
        source_sha256 = _sha256(payload)
        document = json.loads(payload)
        _case, budget, reference = runtime.build_source_case(
            document,
            callback_cap=max(10_000_000, arguments.probes * arguments.repeats * 4),
            deadline=time.monotonic() + 86_400,
        )
        evaluator, metadata = _activate_compiled_evaluator(
            reference,
            budget,
            source_sha256=source_sha256,
        )
        points = _probes(
            source_sha256,
            len(reference.bundle.var_names),
            arguments.probes,
            include_boundaries=arguments.include_boundaries,
        )
        timing_points = points[-arguments.probes :]
        for point in points:
            _update_vector(input_stream, point)
        residual_digest = _observation_digest(evaluator, points)
        callback_digest = _callback_digest(budget, points)
        output_stream.update(bytes.fromhex(residual_digest))
        output_stream.update(bytes.fromhex(callback_digest))
        # Boundary probes are differential-only. Timing uses normal finite
        # probes so a semantic fallback cannot dominate an unrelated class.
        _observation_digest(evaluator, timing_points)
        residual_timing = _time_calls(
            lambda point, evaluator=evaluator: evaluator.evaluate_float_residual(list(point)),
            timing_points,
            arguments.repeats,
        )
        callback_timing = _time_calls(
            lambda point, budget=budget: budget(np.asarray(point, dtype=float)),
            timing_points,
            arguments.repeats,
        )
        rows.append(
            {
                "source_sha256": source_sha256,
                "dimension": len(reference.bundle.var_names),
                "residual_dimension": len(reference.bundle.spec.constraints),
                "backend": str(metadata.get("mode", "reference")),
                "structural_family": _backend_family(metadata),
                "routing": {
                    "case_specific": bool(metadata.get("case_specific_routing", False)),
                    "problem_identity_read": bool(metadata.get("problem_identity_read", False)),
                    "corpus_metadata_read": bool(metadata.get("corpus_metadata_read", False)),
                },
                "input_digest": _sha256(b"".join(_float_bytes(v) for p in points for v in p)),
                "residual_digest": residual_digest,
                "callback_digest": callback_digest,
                "residual": residual_timing,
                "callback": callback_timing,
            }
        )
    return {
        "schema_version": SCHEMA,
        "repository": str(REPOSITORY),
        "git_commit": subprocess.run(
            ["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip(),
        "config": {
            "probes": arguments.probes,
            "repeats": arguments.repeats,
            "include_boundaries": arguments.include_boundaries,
        },
        "input_stream_digest": input_stream.hexdigest(),
        "output_stream_digest": output_stream.hexdigest(),
        "completed_cases": len(rows),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "rows": rows,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--cases-root", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--probes", type=int, default=64)
    value.add_argument("--repeats", type=int, default=5)
    value.add_argument("--include-boundaries", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.probes < 4 or arguments.repeats < 1:
        raise SystemExit("probes must be >= 4 and repeats must be >= 1")
    output = arguments.output.expanduser().resolve()
    if output == REPOSITORY or REPOSITORY in output.parents:
        raise SystemExit("measurement output must be outside the repository")
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    document = measure(arguments)
    temporary = output.with_suffix(output.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
