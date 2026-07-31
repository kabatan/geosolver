#!/usr/bin/env python3.12
"""Generated exact/replay D0 for RR-07 post-endpoint inverse."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from candidate import ACTIONS, Inapplicable, exact_squared_distances, reconstruct, replay_both_reflections


def _sha(tag: str) -> str:
    return hashlib.sha256(tag.encode("ascii")).hexdigest()


def _replay(source_sha: str, endpoint_sha: str, *, reject_reflection: int | None = None):
    def run(request):
        ordinal = request["reflection_ordinal"]
        accepted = ordinal != reject_reflection
        return {
            "source_sha256": source_sha,
            "endpoint_float64_sha256": endpoint_sha,
            "reflection_ordinal": ordinal,
            "construction_exact": accepted,
            "constraints_exact": accepted,
            "guards_and_definedness_exact": accepted,
            "raw_target_link_exact": accepted,
            "untouched_source_replay": accepted,
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

    positives = (
        (13, 14, 15, 8, ACTIONS[0]),
        (5, 5, 6, 3, ACTIONS[1]),
        (7, 8, 9, 5, ACTIONS[2]),
        (4, 5, 7, 4, ACTIONS[0]),
        (15, 13, 14, 6, ACTIONS[1]),
    )
    action_counts = Counter()
    replay_accepted = 0
    old_no_bounded_relation_accepted = 0
    reflection_checks = 0
    for ordinal, (a, b, c, t, action) in enumerate(positives):
        result = reconstruct(side_a=a, side_b=b, side_c=c, tangent=t, action=action)
        if exact_squared_distances(result) != (a * a, b * b, c * c):
            raise AssertionError("SSS inverse changed exact side squares")
        if result.branches[0].apex_y.square != result.branches[1].apex_y.square:
            raise AssertionError("reflection pair changed Heron height")
        if result.branches[0].apex_y.coefficient != -result.branches[1].apex_y.coefficient:
            raise AssertionError("both reflections were not retained")
        reflection_checks += 2
        source_sha, endpoint_sha = _sha(f"source:{ordinal}"), _sha(f"endpoint:{ordinal}")
        replay = replay_both_reflections(
            result,
            source_sha256=source_sha,
            endpoint_sha256=endpoint_sha,
            replay=_replay(source_sha, endpoint_sha),
        )
        if replay["accepted_reflection_count"] != 2:
            raise AssertionError("untouched replay rejected a positive")
        replay_accepted += 1
        action_counts[action] += 1
        if ordinal == 0:  # generated analogue of the old relation-free stratum
            old_no_bounded_relation_accepted += 1

    negatives = (
        (3, 4, 5, 2, ACTIONS[0]),  # tangent identity false
        (1, 2, 3, 2, ACTIONS[1]),  # degenerate
        (5, 5, 6, 0, ACTIONS[2]),  # zero tangent
        (5, 5, 6, 3, "EXCIRCLE_CONTACT"),
    )
    rejected = 0
    for values in negatives:
        try:
            reconstruct(side_a=values[0], side_b=values[1], side_c=values[2], tangent=values[3], action=values[4])
        except Inapplicable:
            rejected += 1
    if rejected != len(negatives):
        raise AssertionError("near-miss was not rejected")

    result = {
        "schema_version": "geotarget.rr07-post-endpoint-exact-reopen-generated-d0/v1",
        "static_source_count": len(positives),
        "static_action_count": len(action_counts),
        "replay_accepted_source_count": replay_accepted,
        "replay_accepted_action_count": len(action_counts),
        "old_no_bounded_relation_generated_analogue_count": old_no_bounded_relation_accepted,
        "reflection_exact_checks": reflection_checks,
        "negative_rejected_count": rejected,
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
