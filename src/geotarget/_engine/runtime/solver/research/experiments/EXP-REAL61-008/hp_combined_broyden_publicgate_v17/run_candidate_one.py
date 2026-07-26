#!/usr/bin/env python3
"""Run the thin Broyden/public-gate composition through unchanged authority."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PUBLIC_RUNNER_PATH = HERE.parent / "public_gate_progressive_hp_v16/run_candidate_one.py"
CANDIDATE_PATH = HERE / "candidate.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.infrastructure.memory_safety.safe_subprocess import (  # noqa: E402
    atomic_write_json,
)


def _load_public_runner():
    name = "geotarget_exp008_combined_v17_public_runner"
    specification = importlib.util.spec_from_file_location(name, PUBLIC_RUNNER_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(PUBLIC_RUNNER_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    module.CANDIDATE_PATH = CANDIDATE_PATH
    return module


def build_combined_authority(
    source_payload: bytes,
    source_sha256: str,
    endpoint: Sequence[object],
    *,
    deadline_seconds: float = 23.0,
) -> dict[str, object]:
    runner = _load_public_runner()
    result = runner.build_public_gate_authority(
        source_payload,
        source_sha256,
        list(endpoint),
        deadline_seconds=deadline_seconds,
    )
    result["hp_combined_broyden_publicgate_experiment"] = {
        "event_refreshed_direct_good_broyden": True,
        "public_gate_progressive_stopping": True,
        "numerical_v3_authority_unchanged": True,
        "source_or_problem_modified": False,
        "variables_or_equations_changed": False,
        "bounds_added_or_inferred": False,
        "gauge_or_symmetry_reduction": False,
        "coordinate_reparameterization": False,
        "case_family_truth_or_known_target_count_read": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--deadline-seconds", type=float, default=23.0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    endpoint = json.loads(arguments.endpoint)
    if not isinstance(endpoint, list):
        raise SystemExit("endpoint must be a JSON array")
    result = build_combined_authority(
        arguments.source.read_bytes(),
        arguments.source_sha256,
        endpoint,
        deadline_seconds=arguments.deadline_seconds,
    )
    atomic_write_json(arguments.output, result)


if __name__ == "__main__":
    main()
