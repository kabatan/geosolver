#!/usr/bin/env python3
"""Aggregate scanner results without persisting per-source records."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from source_only_scanner import scan_source


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("requests", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("source-only aggregate must be pinned to CPU14")
    requests = json.loads(arguments.requests.read_bytes())
    if not isinstance(requests, list):
        raise ValueError("requests must be a list")
    reasons: Counter[str] = Counter()
    lift_dimension_buckets: Counter[str] = Counter()
    selected_row_buckets: Counter[str] = Counter()
    ready = 0
    for request in requests:
        if not isinstance(request, dict) or not isinstance(request.get("source_path"), str):
            raise ValueError("request lacks source_path")
        record = scan_source(Path(request["source_path"]))
        reasons[str(record["reason"])] += 1
        if record.get("ready") is True:
            ready += 1
            dimension = int(record["lift_variable_count"])
            rows = int(record["selected_equality_count"])
            lift_dimension_buckets[
                "1-8" if dimension <= 8 else "9-16" if dimension <= 16 else "17-32" if dimension <= 32 else "33+"
            ] += 1
            selected_row_buckets[
                "1-8" if rows <= 8 else "9-16" if rows <= 16 else "17-32" if rows <= 32 else "33+"
            ] += 1
        del record
    result = {
        "schema_version": "geotarget.source-quadratic-moment-panel-aggregate/v1",
        "requests_sha256": sha256(arguments.requests),
        "request_count": len(requests),
        "ready_count": ready,
        "not_ready_count": len(requests) - ready,
        "reason_histogram": dict(sorted(reasons.items())),
        "ready_lift_dimension_buckets": dict(sorted(lift_dimension_buckets.items())),
        "ready_selected_equality_buckets": dict(sorted(selected_row_buckets.items())),
        "individual_records_retained": False,
        "source_path_emitted": False,
        "endpoint_used": False,
        "target_read": False,
        "truth_used": False,
        "authority_pass": False,
        "target_release": False,
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.write_text(payload, encoding="utf-8")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

