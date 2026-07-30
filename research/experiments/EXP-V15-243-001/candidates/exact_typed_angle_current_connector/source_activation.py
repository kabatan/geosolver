#!/usr/bin/env python3
"""Aggregate-only source probe for the exact typed Angle equality mechanism.

This is deliberately not an evaluator.  It copies only the D0 source-shape
predicate and never inspects endpoints, target values, scorer data, or truth.
It prints one aggregate record and no source identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


POINT_DOMAIN = "POINT_UNSIGNED_RADIAN_[0,PI]"
LINE_DOMAIN = "LINE_ACUTE_RADIAN_[0,PI/2]"
MAXIMUM_AUTHORITY_FRACTION = 0.25
MINIMUM_BASELINE_FRACTION = 0.75


def classify_source_relation(node: Mapping[str, Any]) -> bool:
    """Exact copy of the D0 direct, same-typed ``Angle = Angle`` predicate."""
    if node.get("op") != "Equal" or set(node) - {"op", "left", "right"}:
        return False
    left = node.get("left")
    right = node.get("right")
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return False
    allowed = {"op", "args", "unit", "domain"}
    if set(left) - allowed or set(right) - allowed:
        return False
    if left.get("op") != "Angle" or right.get("op") != "Angle":
        return False
    if left.get("unit") != "radian" or right.get("unit") != "radian":
        return False
    left_args = left.get("args")
    right_args = right.get("args")
    if (
        not isinstance(left_args, list)
        or not isinstance(right_args, list)
        or len(left_args) != len(right_args)
    ):
        return False
    expected = {3: POINT_DOMAIN, 2: LINE_DOMAIN}.get(len(left_args))
    return bool(
        expected is not None
        and left.get("domain") == right.get("domain") == expected
    )


def _nodes(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


def aggregate_source_documents(
    documents: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    total = 0
    activated_documents = 0
    relations = 0
    zero_dimensional_documents = 0
    for document in documents:
        total += 1
        count = sum(classify_source_relation(node) for node in _nodes(document))
        relations += count
        activated_documents += count > 0
        # This is telemetry only.  A connector, if one existed, must return
        # the baseline object by identity for a proven zero-dimensional source.
        dimensions = document.get("variables")
        zero_dimensional_documents += isinstance(dimensions, list) and not dimensions
    return {
        "schema_version": "geotarget.exact-typed-angle-source-activation/v1",
        "scope": "source-structural aggregate only",
        "documents_total": total,
        "documents_with_direct_typed_angle_equality": activated_documents,
        "direct_typed_angle_equality_relations": relations,
        "zero_dimensional_documents": zero_dimensional_documents,
        "authority_route_enabled": False,
        "connector_decision": "STOP_NO_EXACT_OPERAND_OBLIGATION_SEAM",
        "maximum_authority_fraction": MAXIMUM_AUTHORITY_FRACTION,
        "minimum_baseline_fraction": MINIMUM_BASELINE_FRACTION,
        "individual_source_identity_emitted": False,
        "truth_or_scorer_read": False,
    }


def _load(path: Path, expected_sha256: str | None) -> Mapping[str, Any]:
    payload = path.read_bytes()
    if expected_sha256 is not None:
        observed = hashlib.sha256(payload).hexdigest()
        if observed != expected_sha256:
            raise ValueError("source SHA-256 mismatch")
    value = json.loads(payload)
    if not isinstance(value, Mapping):
        raise ValueError("source must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", type=Path, required=True)
    parser.add_argument("--source-sha256", action="append")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    hashes = args.source_sha256 or [None] * len(args.source)
    if len(hashes) != len(args.source):
        parser.error("--source-sha256 count must match --source count")
    result = aggregate_source_documents(
        _load(path, digest) for path, digest in zip(args.source, hashes)
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
