#!/usr/bin/env python3
"""Aggregate-only compiler-readiness gate for preselected degree-one attempts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from typed_join import source_only_readiness


FORBIDDEN_KEYS = frozenset(
    {
        "id",
        "family",
        "truth",
        "answer",
        "target",
        "outcome",
        "result",
        "score",
        "known_count",
    }
)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _signature_text(signature: Mapping[str, object]) -> str:
    return json.dumps(signature, sort_keys=True, separators=(",", ":"))


def main() -> int:
    arguments = _parser().parse_args()
    requests = json.loads(arguments.requests.read_text(encoding="utf-8"))
    if not isinstance(requests, list):
        raise SystemExit("requests must be an array")
    ready = 0
    signatures: dict[str, int] = {}
    rejected = 0
    for request in requests:
        if not isinstance(request, Mapping) or FORBIDDEN_KEYS & set(request):
            raise SystemExit("request crossed the identity/target/truth boundary")
        if set(request) != {"source_path", "endpoint"}:
            raise SystemExit("request must contain only source_path and endpoint")
        endpoint = request["endpoint"]
        if not isinstance(endpoint, list):
            raise SystemExit("endpoint must be a list")
        try:
            assessment = source_only_readiness(
                Path(str(request["source_path"])),
                [float(item) for item in endpoint],
            )
            signature = _signature_text(assessment["anonymous_signature"])
            signatures[signature] = signatures.get(signature, 0) + 1
            ready += 1
        except Exception:
            rejected += 1
    aggregate = {
        "schema_version": "geotarget.guided-target-source-only-readiness/v1",
        "request_count": len(requests),
        "typed_regular_root_compiler_ready_count": ready,
        "rejected_count": rejected,
        "anonymous_signature_count": len(signatures),
        "anonymous_signature_histogram": signatures,
        "gate_minimum_attempts": 10,
        "gate_minimum_signatures": 2,
        "gate_pass": ready >= 10 and len(signatures) >= 2,
        "target_read": False,
        "truth_used": False,
        "individual_records_emitted": False,
        "worker_viability_requires_separate_contained_probe": True,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
