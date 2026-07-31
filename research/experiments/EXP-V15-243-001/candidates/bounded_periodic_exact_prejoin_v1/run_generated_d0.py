#!/usr/bin/env python3.12
"""Four-family source-only D0 for the 25% proposal overlay."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np


HERE = Path(__file__).resolve().parent


def _load_adapter():
    specification = importlib.util.spec_from_file_location(
        "geotarget_bounded_prejoin_generated_adapter", HERE / "search_adapter.py"
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("adapter unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _prefix(dimension: int = 2, count: int = 16):
    points = tuple(
        np.asarray([10.0 * ordinal + axis for axis in range(dimension)], dtype=float)
        for ordinal in range(count)
    )
    return SimpleNamespace(
        points=points,
        sources=tuple(
            "counter_product_cauchy" if ordinal % 4 == 0 else "frozen_control"
            for ordinal in range(count)
        ),
        scale_exponents=tuple(range(count)),
        literal_scales=np.ones(dimension, dtype=float),
    )


def _documents():
    periodic_construction = [
        {"name": "O", "expr": "Point(0,0)"},
        {"name": "A", "expr": "Point(1,0)"},
        {"name": "P", "expr": "Rotate(A,theta,O)"},
    ]
    return {
        "bounded-only": {
            "variables": {"names": ["x", "u"]},
            "construction": [],
            "constraints": [],
            "guards": ["Bound(x,(-2,3),inclusive=False)"],
            "answer": "u",
        },
        "periodic-only": {
            "variables": {"names": ["theta", "u"]},
            "construction": periodic_construction,
            "constraints": [{"def": "Distance(O,P)", "value": 1}],
            "guards": [],
            "answer": "Distance(O,P)",
        },
        "mixed": {
            "variables": {"names": ["theta", "x"]},
            "construction": periodic_construction,
            "constraints": [{"def": "Distance(O,P)", "value": "x"}],
            "guards": ["Bound(x,(0,2),inclusive=False)"],
            "answer": "Distance(O,P)",
        },
        "raw-occurrence-near-miss": {
            "variables": {"names": ["theta", "u"]},
            "construction": periodic_construction,
            "constraints": [{"def": "Distance(O,P)", "value": 1}],
            "guards": [],
            "answer": "theta",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("generated D0 must be pinned to expected CPU")
    adapter = _load_adapter()
    activation = {}
    passthrough_checks = 0
    side_checks = 0
    for family, document in _documents().items():
        prefix = _prefix()
        proposed, record = adapter._quarter_prefix(
            SimpleNamespace(document=document), prefix
        )
        if family == "raw-occurrence-near-miss":
            if proposed is not prefix or record.get("eligible") is not False:
                raise AssertionError("near-miss did not fail closed")
            activation[family] = "exact-passthrough"
            continue
        if proposed is prefix or record.get("side_route_launches") != 4:
            raise AssertionError(f"{family} did not activate exactly 25%")
        for ordinal, (before, after) in enumerate(
            zip(prefix.points, proposed.points, strict=True)
        ):
            if ordinal % 4 == 2:
                side_checks += 1
            else:
                passthrough_checks += 1
                if before.tobytes() != after.tobytes():
                    raise AssertionError("baseline ordinal changed")
        activation[family] = "25%-active"

    result = {
        "schema_version": "geotarget.bounded-periodic-exact-prejoin-generated-d0/v1",
        "family_count": len(activation),
        "activation_histogram": {
            "25%-active": sum(value == "25%-active" for value in activation.values()),
            "exact-passthrough": sum(value == "exact-passthrough" for value in activation.values()),
        },
        "side_route_ordinal_checks": side_checks,
        "baseline_bitwise_passthrough_checks": passthrough_checks,
        "source_problem_modified": False,
        "target_evaluated_for_routing": False,
        "truth_case_family_target_count_outcome_routing": False,
        "completed": True,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
