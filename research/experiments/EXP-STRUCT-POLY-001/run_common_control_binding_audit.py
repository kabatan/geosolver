#!/usr/bin/env python3
"""Truth-free direct-control/no-op differential for the registered source SHA."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from btf_polynomial_pipeline import detect_btf_polynomial_plan
import worker_v2


EXPECTED_SOURCE_SHA256 = (
    "63fb3e07117c47ee18aa18cbb2e891578e84c1d8e3fb8dc1d3b26b777a70b1c0"
)
TOTAL_SECONDS = 15.0
SEARCH_SECONDS = 5.0
STARTS = 16
CALLBACKS_PER_START = 32
AGGREGATE_CALLBACK_CAP = 512


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _arguments(source: Path, output: Path, cpu: int) -> list[str]:
    return [
        "--source",
        str(source),
        "--source-sha256",
        EXPECTED_SOURCE_SHA256,
        "--total-seconds",
        str(TOTAL_SECONDS),
        "--search-seconds",
        str(SEARCH_SECONDS),
        "--starts",
        str(STARTS),
        "--callbacks-per-start",
        str(CALLBACKS_PER_START),
        "--aggregate-callback-cap",
        str(AGGREGATE_CALLBACK_CAP),
        "--seed",
        "0",
        "--cpu",
        str(cpu),
        "--output",
        str(output),
    ]


def _without_elapsed(result: object) -> object:
    if not isinstance(result, dict):
        raise RuntimeError("common control emitted malformed RESULT")
    normalized = dict(result)
    normalized.pop("elapsed_wall_seconds", None)
    return normalized


def _run(entrypoint: Path, source: Path, shared: Path, cpu: int):
    arguments = _arguments(source, shared, cpu)
    dry = subprocess.run(
        [str(worker_v2.V1.FROZEN_PYTHON), str(entrypoint), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=10,
    )
    plan = (shared / "PLAN.json").read_bytes()
    plan_sha256 = _sha256(plan)
    execute = subprocess.run(
        [
            "taskset",
            "-c",
            str(cpu),
            str(worker_v2.V1.FROZEN_PYTHON),
            str(entrypoint),
            *arguments,
            "--execute",
            "--plan-sha256",
            plan_sha256,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=TOTAL_SECONDS + 10.0,
    )
    result = (shared / "RESULT.json").read_bytes()
    result_document = json.loads(result)
    return {
        "plan": plan,
        "dry_stdout": dry.stdout,
        "dry_stderr": dry.stderr,
        "execute_stdout": execute.stdout,
        "execute_stderr": execute.stderr,
        "result": result,
        "normalized_result": _without_elapsed(result_document),
        "telemetry_exists": (
            shared / "EXP-STRUCT-POLY-001-V2-TELEMETRY.json"
        ).exists(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", type=int, default=0)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists():
        raise SystemExit("audit output must not already exist")
    payload = arguments.source.read_bytes()
    if _sha256(payload) != EXPECTED_SOURCE_SHA256:
        raise SystemExit("registered truth-free source SHA-256 mismatch")
    document = json.loads(payload)
    if not isinstance(document, dict) or document.get("task") != "solve":
        raise SystemExit("solve formulation required")
    if detect_btf_polynomial_plan(document).applicable:
        raise SystemExit("registered no-op source unexpectedly activates side route")

    worker_v2._verify_closure()
    output.mkdir(parents=True)
    shared = output / "shared-output"
    direct = _run(worker_v2.COMMON_CONTROL, arguments.source, shared, arguments.cpu)
    shutil.copytree(shared, output / "direct-control")
    shutil.rmtree(shared)
    candidate = _run(Path(worker_v2.__file__), arguments.source, shared, arguments.cpu)
    shutil.copytree(shared, output / "v2-no-op")
    shutil.rmtree(shared)

    audit = {
        "schema_version": "geotarget.exp-struct-poly-001-common-control-audit/v1",
        "truth_or_scorer_used": False,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "combined_route_applicable": False,
        "common_control_path": str(worker_v2.COMMON_CONTROL),
        "common_control_sha256": _sha256(worker_v2.COMMON_CONTROL.read_bytes()),
        "periodic_layer_sha256": {
            name: expected
            for name, (_path, expected) in worker_v2.EXPECTED_COMMON_CONTROL_LAYERS.items()
        },
        "dry_plan_bytes_equal": candidate["plan"] == direct["plan"],
        "dry_stdout_bytes_equal": candidate["dry_stdout"] == direct["dry_stdout"],
        "dry_stderr_bytes_equal": candidate["dry_stderr"] == direct["dry_stderr"],
        "execute_stdout_bytes_equal": (
            candidate["execute_stdout"] == direct["execute_stdout"]
        ),
        "execute_stderr_bytes_equal": (
            candidate["execute_stderr"] == direct["execute_stderr"]
        ),
        "result_semantics_equal": (
            candidate["normalized_result"] == direct["normalized_result"]
        ),
        "result_excluded_nondeterministic_fields": ["elapsed_wall_seconds"],
        "direct_result_sha256": _sha256(direct["result"]),
        "candidate_result_sha256": _sha256(candidate["result"]),
        "candidate_telemetry_created": candidate["telemetry_exists"],
        "status": candidate["normalized_result"].get("status"),
        "completed": candidate["normalized_result"].get("completed"),
        "search_process_classification": candidate["normalized_result"]
        .get("search", {})
        .get("process_classification"),
        "hp_attempt_count": candidate["normalized_result"].get("hp_attempt_count"),
        "distinct_exact_target_count": candidate["normalized_result"].get(
            "distinct_exact_target_count"
        ),
    }
    if not all(
        audit[field]
        for field in (
            "dry_plan_bytes_equal",
            "dry_stdout_bytes_equal",
            "dry_stderr_bytes_equal",
            "execute_stdout_bytes_equal",
            "execute_stderr_bytes_equal",
            "result_semantics_equal",
        )
    ) or audit["candidate_telemetry_created"]:
        raise RuntimeError("v2 no-op differs from the registered common control")
    rendered = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    (output / "AUDIT.json").write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
