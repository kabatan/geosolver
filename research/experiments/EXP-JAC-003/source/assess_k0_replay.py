"""Exact frozen K0 replay gate used before formal ABBA timing."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import assess_development as full


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--frozen-k0", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    manifest = json.loads(arguments.manifest.read_bytes())
    frozen = full._artifact(
        arguments.frozen_k0,
        manifest["artifacts"]["k0_control"],
        "K0",
    )
    trace = full._load(arguments.trace)
    cases = full._segment_cases(trace, 0, full.ABBA[0])
    mismatch_count = full._k0_replay_count([cases, [], [], cases], frozen)
    # The helper compares both K0 slots; the same preflight trace is deliberately
    # supplied twice, so divide by two to retain the physical mismatch count.
    if mismatch_count % 2:
        raise full.AssessmentError("K0 replay duplicate-check parity failure")
    mismatch_count //= 2
    full._write_once(
        arguments.output,
        {
            "experiment_id": full.CARD_ID,
            "mismatch_count": mismatch_count,
            "passed": mismatch_count == 0,
            "schema_version": "exp-jac-003-k0-replay-assessment/v1",
        },
    )
    return 0 if mismatch_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
