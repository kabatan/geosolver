#!/usr/bin/env python3
"""Run chunk-interleaved A/B/B/A geometry callback measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MEASURE = HERE / "measure_callbacks.py"
LEGS = (
    ("a1", "control"),
    ("b1", "candidate"),
    ("b2", "candidate"),
    ("a2", "control"),
)


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"malformed measurement: {path}")
    return value


def _problem_paths(root: Path) -> list[Path]:
    paths = sorted(root.glob("*/problem.json"))
    if not paths:
        raise ValueError(f"no */problem.json corpus found below {root}")
    return paths


def _chunks(values: Sequence[Path], size: int) -> list[list[Path]]:
    return [list(values[index : index + size]) for index in range(0, len(values), size)]


def _materialize_chunk(root: Path, ordinal: int, paths: Sequence[Path]) -> Path:
    chunk = root / f"chunk-{ordinal:03d}"
    chunk.mkdir(parents=True, exist_ok=False)
    for case_ordinal, source in enumerate(paths, start=1):
        target = chunk / f"{case_ordinal:03d}-{source.parent.name}"
        target.mkdir()
        (target / "problem.json").symlink_to(source.resolve())
    return chunk


def _run_leg(
    *,
    repository: Path,
    chunk: Path,
    output: Path,
    cpu: int,
    probes: int,
    repeats: int,
) -> Mapping[str, Any]:
    environment = {
        **os.environ,
        "GEOTARGET_BENCH_REPOSITORY": str(repository),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    subprocess.run(
        [
            "taskset",
            "-c",
            str(cpu),
            sys.executable,
            str(MEASURE),
            "--cases-root",
            str(chunk),
            "--output",
            str(output),
            "--probes",
            str(probes),
            "--repeats",
            str(repeats),
            "--compiled-only",
        ],
        check=True,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return _load(output)


def _combine(
    documents: Sequence[Mapping[str, Any]],
    *,
    chunk_size: int,
) -> dict[str, Any]:
    if not documents:
        raise ValueError("no measurements to combine")
    reference = documents[0]
    input_stream = hashlib.sha256(b"geotarget.interleaved-input-stream/v1\0")
    output_stream = hashlib.sha256(b"geotarget.interleaved-output-stream/v1\0")
    rows: list[Mapping[str, Any]] = []
    skipped: list[str] = []
    for document in documents:
        if document.get("schema_version") != reference.get("schema_version"):
            raise ValueError("measurement schemas differ")
        if document.get("config") != reference.get("config"):
            raise ValueError("measurement configs differ")
        input_stream.update(bytes.fromhex(str(document["input_stream_digest"])))
        output_stream.update(bytes.fromhex(str(document["output_stream_digest"])))
        rows.extend(document["rows"])
        skipped.extend(str(value) for value in document["skipped_source_sha256"])
    sources = [str(row["source_sha256"]) for row in rows]
    if len(sources) != len(set(sources)):
        raise ValueError("a case appears in more than one interleaved chunk")
    return {
        "schema_version": reference["schema_version"],
        "repository": reference["repository"],
        "git_commit": reference["git_commit"],
        "config": {
            **reference["config"],
            "interleave_chunk_size": chunk_size,
        },
        "input_stream_digest": input_stream.hexdigest(),
        "output_stream_digest": output_stream.hexdigest(),
        "completed_cases": len(rows),
        "skipped_source_sha256": skipped,
        "peak_rss_kib": max(int(document["peak_rss_kib"]) for document in documents),
        "rows": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-root", type=Path, required=True)
    parser.add_argument("--control-repository", type=Path, required=True)
    parser.add_argument("--candidate-repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--probes", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=10)
    arguments = parser.parse_args(argv)
    if arguments.chunk_size < 1 or arguments.probes < 1 or arguments.repeats < 1:
        raise SystemExit("chunk-size, probes, and repeats must be positive")
    output = arguments.output.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    inputs = output / "inputs"
    raw = output / "raw"
    inputs.mkdir()
    raw.mkdir()
    repositories = {
        "control": arguments.control_repository.expanduser().resolve(),
        "candidate": arguments.candidate_repository.expanduser().resolve(),
    }
    combined: dict[str, list[Mapping[str, Any]]] = {label: [] for label, _arm in LEGS}
    chunks = _chunks(
        _problem_paths(arguments.cases_root.expanduser().resolve()),
        arguments.chunk_size,
    )
    for chunk_ordinal, paths in enumerate(chunks, start=1):
        print(f"interleave {chunk_ordinal}/{len(chunks)}", file=sys.stderr, flush=True)
        chunk = _materialize_chunk(inputs, chunk_ordinal, paths)
        for label, arm in LEGS:
            leg_output = raw / f"chunk-{chunk_ordinal:03d}-{label}.json"
            combined[label].append(
                _run_leg(
                    repository=repositories[arm],
                    chunk=chunk,
                    output=leg_output,
                    cpu=arguments.cpu,
                    probes=arguments.probes,
                    repeats=arguments.repeats,
                )
            )
    for label, _arm in LEGS:
        document = _combine(combined[label], chunk_size=arguments.chunk_size)
        (output / f"{label}.json").write_text(
            json.dumps(document, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
