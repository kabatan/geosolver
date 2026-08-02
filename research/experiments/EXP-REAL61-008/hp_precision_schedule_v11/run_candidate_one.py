#!/usr/bin/env python3
"""Run one two-prefix precision-schedule configuration through full authority."""

from __future__ import annotations

import argparse
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ADAPTER_PATH = HERE.parent / "dev41_target_hp_adapter/adapter.py"
CANDIDATE_PATH = HERE / "candidate.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.infrastructure.memory_safety.safe_subprocess import atomic_write_json


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def build_candidate_authority(
    source_payload: bytes,
    source_sha256: str,
    endpoint: list[object],
    *,
    strict_stage_count: int = 4,
    deadline_seconds: float = 23.0,
) -> dict[str, object]:
    """Run the reviewed schedule and return the unchanged adapter authority."""

    if strict_stage_count not in (4, 6):
        raise ValueError("strict_stage_count must be 4 or 6")
    adapter = _load(
        "geotarget_exp008_hp_precision_schedule_adapter", ADAPTER_PATH
    )
    candidate = _load(
        "geotarget_exp008_hp_precision_schedule_candidate", CANDIDATE_PATH
    )
    candidate.STRICT_STAGE_COUNT = strict_stage_count
    runtime = replace(adapter._load_runtime(), candidate=candidate)
    result = adapter._build_with_runtime(
        source_payload,
        source_sha256,
        endpoint,
        deadline_seconds=deadline_seconds,
        runtime=runtime,
    )
    result["precision_schedule_experiment"] = {
        "independent_prefix_bits": [512, 768],
        "strict_stage_count": strict_stage_count,
        "source_or_problem_modified": False,
        "bounds_or_gauge_added": False,
        "truth_case_family_or_target_count_read": False,
        "final_original_dsl_replay_bits": [512, 768, 1024],
        "owned_pslq_proposal_confirmation_bits": [768, 1024],
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--strict-stage-count", type=int, choices=(4, 6), required=True)
    parser.add_argument("--deadline-seconds", type=float, default=23.0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    endpoint = json.loads(arguments.endpoint)
    if not isinstance(endpoint, list):
        raise SystemExit("endpoint must be a JSON array")
    result = build_candidate_authority(
        arguments.source.read_bytes(),
        arguments.source_sha256,
        endpoint,
        strict_stage_count=arguments.strict_stage_count,
        deadline_seconds=arguments.deadline_seconds,
    )
    atomic_write_json(arguments.output, result)


if __name__ == "__main__":
    main()
