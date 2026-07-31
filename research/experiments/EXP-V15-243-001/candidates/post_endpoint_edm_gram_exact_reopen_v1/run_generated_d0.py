#!/usr/bin/env python3.12
"""Generated exact/metamorphic D0 for anchored EDM/Gram reconstruction."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path

from candidate import Inapplicable, reconstruct_anchored_edm, replay_branches, squared_distance


def _sha(tag: str) -> str:
    return hashlib.sha256(tag.encode("ascii")).hexdigest()


def _edm(points):
    return {
        frozenset((left, right)): (points[left][0] - points[right][0]) ** 2 + (points[left][1] - points[right][1]) ** 2
        for index, left in enumerate(points)
        for right in tuple(points)[index + 1 :]
    }


def _replay(source_sha: str, endpoint_sha: str):
    def run(request):
        return {
            "source_sha256": source_sha,
            "endpoint_float64_sha256": endpoint_sha,
            "reflection_ordinal": request["reflection_ordinal"],
            "construction_exact": True,
            "constraints_exact": True,
            "guards_and_definedness_exact": True,
            "raw_target_link_exact": True,
            "untouched_source_replay": True,
            "source_parser_or_compiler_modified": False,
        }
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("D0 must be pinned to expected CPU")

    families = (
        {"A": (Fraction(0), Fraction(0)), "B": (Fraction(4), Fraction(0)), "C": (Fraction(1), Fraction(3))},
        {"A": (Fraction(1), Fraction(2)), "B": (Fraction(4), Fraction(6)), "C": (Fraction(6), Fraction(1))},
        {"A": (Fraction(-2), Fraction(1)), "B": (Fraction(3), Fraction(1)), "C": (Fraction(0), Fraction(5)), "D": (Fraction(4), Fraction(4))},
        {"A": (Fraction(2), Fraction(-1)), "B": (Fraction(8), Fraction(7)), "C": (Fraction(-1), Fraction(4)), "D": (Fraction(5), Fraction(9))},
        {"A": (Fraction(0), Fraction(0)), "B": (Fraction(5), Fraction(0)), "C": (Fraction(1), Fraction(2)), "D": (Fraction(3), Fraction(7)), "E": (Fraction(-2), Fraction(4))},
        {"A": (Fraction(-3), Fraction(-2)), "B": (Fraction(1), Fraction(4)), "C": (Fraction(6), Fraction(0)), "D": (Fraction(2), Fraction(-5)), "E": (Fraction(-4), Fraction(3))},
    )
    signatures = set()
    exact_checks = 0
    replayed = 0
    permutation_checks = 0
    for ordinal, points in enumerate(families):
        labels = tuple(points)
        result = reconstruct_anchored_edm(
            labels=labels,
            squared_distances=_edm(points),
            anchor_left="A",
            anchor_right="B",
            anchor_left_xy=points["A"],
            anchor_right_xy=points["B"],
        )
        signatures.add("K3" if len(labels) == 3 else "K4" if len(labels) == 4 else "K5PLUS")
        for branch in result.branches:
            for index, left in enumerate(labels):
                for right in labels[index + 1 :]:
                    if squared_distance(branch[left], branch[right]) != _edm(points)[frozenset((left, right))]:
                        raise AssertionError("exact EDM changed after reconstruction")
                    exact_checks += 1
        source_sha = _sha(f"source:{ordinal}")
        endpoint_sha = _sha(f"endpoint:{ordinal}")
        joined = replay_branches(
            result,
            source_sha256=source_sha,
            endpoint_sha256=endpoint_sha,
            replay=_replay(source_sha, endpoint_sha),
        )
        if joined["accepted_reflection_count"] != 2:
            raise AssertionError("both exact reflections must reach generated replay")
        replayed += 1
        permuted = tuple(reversed(labels))
        again = reconstruct_anchored_edm(
            labels=permuted,
            squared_distances=_edm(points),
            anchor_left="A",
            anchor_right="B",
            anchor_left_xy=points["A"],
            anchor_right_xy=points["B"],
        )
        if again.exact_rank != result.exact_rank or len(again.branches) != len(result.branches):
            raise AssertionError("label permutation changed exact EDM semantics")
        permutation_checks += 1

    negative_rejected = 0
    base = families[0]
    bad_inputs = []
    missing = _edm(base)
    missing.pop(next(iter(missing)))
    bad_inputs.append((tuple(base), missing, base["A"], base["B"]))
    anchor_mismatch = _edm(base)
    anchor_mismatch[frozenset(("A", "B"))] += 1
    bad_inputs.append((tuple(base), anchor_mismatch, base["A"], base["B"]))
    tetrahedron = {
        frozenset((left, right)): Fraction(1)
        for index, left in enumerate(("A", "B", "C", "D"))
        for right in ("A", "B", "C", "D")[index + 1 :]
    }
    bad_inputs.append((("A", "B", "C", "D"), tetrahedron, (0, 0), (1, 0)))
    for labels, distances, anchor_left_xy, anchor_right_xy in bad_inputs:
        try:
            reconstruct_anchored_edm(
                labels=labels,
                squared_distances=distances,
                anchor_left="A", anchor_right="B",
                anchor_left_xy=anchor_left_xy, anchor_right_xy=anchor_right_xy,
            )
        except Inapplicable:
            negative_rejected += 1
    if negative_rejected != len(bad_inputs):
        raise AssertionError("invalid EDM escaped fail-closed checks")

    result = {
        "schema_version": "geotarget.post-endpoint-edm-gram-exact-reopen-generated-d0/v1",
        "generated_source_count": len(families),
        "generated_signature_count": len(signatures),
        "exact_pair_checks": exact_checks,
        "both_reflections_replayed_source_count": replayed,
        "permutation_metamorphic_checks": permutation_checks,
        "negative_rejected_count": negative_rejected,
        "source_parser_or_compiler_modified": False,
        "authority_pass": False,
        "target_release": False,
        "completed": True,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
