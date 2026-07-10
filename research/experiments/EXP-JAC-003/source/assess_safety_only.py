"""Fail-closed, pre-timing EXP-JAC-003 safety assessor."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import assess_development as full


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--safety", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    manifest = json.loads(arguments.manifest.read_bytes())
    truth = full._artifact(
        arguments.truth, manifest["artifacts"]["assessor"], "assessor"
    )
    safety = full._load(arguments.safety)
    result = full.assess_safety(safety, truth)
    full._write_once(
        arguments.output,
        {
            "counts": result["counts"],
            "experiment_id": full.CARD_ID,
            "passed": result["passed"],
            "schema_version": "exp-jac-003-safety-assessment/v1",
        },
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
