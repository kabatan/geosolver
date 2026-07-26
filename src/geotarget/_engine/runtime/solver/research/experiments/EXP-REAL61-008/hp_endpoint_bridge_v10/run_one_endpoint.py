#!/usr/bin/env python3
"""Run one unchanged Float64 endpoint through the frozen numerical-v3 lane.

The default is a dry run which writes only a deterministic plan.  Actual HP
work requires ``--execute`` together with that plan's SHA-256.  The child is
serialized by the repository-wide HP lock and receives only original source
bytes/digest plus the bare endpoint; no case/family/truth key is accepted.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
from typing import Iterator, Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
WORKER = HERE.parent / "roweq180_delta_authority/worker.py"
PYTHON = ROOT / "python/.venv/bin/python"
GLOBAL_HP_LOCK = Path("/tmp/geotarget-one-heavy-hp-process-v1.lock")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.infrastructure.memory_safety.safe_subprocess import (  # noqa: E402
    Limits,
    atomic_write_json,
    run_guarded,
)


THREAD_ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "GOTO_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "RAYON_NUM_THREADS": "1",
    "MALLOC_ARENA_MAX": "2",
    "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES": str(8 * 1024**3),
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _endpoint_sha256(endpoint: list[float]) -> str:
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", value) for value in endpoint
    )
    return _sha256(payload)


def _parse_endpoint(text: str) -> list[float]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError("endpoint must be a JSON array") from error
    if not isinstance(value, list):
        raise argparse.ArgumentTypeError("endpoint must be a JSON array")
    endpoint: list[float] = []
    for coordinate in value:
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
            raise argparse.ArgumentTypeError("endpoint coordinates must be numbers")
        converted = float(coordinate)
        if not math.isfinite(converted):
            raise argparse.ArgumentTypeError("endpoint coordinates must be finite")
        endpoint.append(converted)
    return endpoint


def _check_source(source: Path, expected_sha256: str, dimension: int) -> bytes:
    payload = source.read_bytes()
    if _sha256(payload) != expected_sha256:
        raise SystemExit("source SHA-256 mismatch")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit("source is not JSON") from error
    names = None
    if isinstance(document, Mapping):
        variables = document.get("variables")
        if isinstance(variables, Mapping):
            names = variables.get("names")
    if (
        not isinstance(document, Mapping)
        or document.get("task") != "solve"
        or not isinstance(names, list)
    ):
        raise SystemExit("source is not an untouched solve problem")
    if len(names) != dimension:
        raise SystemExit("endpoint dimension does not match source variables")
    return payload


@contextmanager
def _exclusive_hp_job() -> Iterator[None]:
    GLOBAL_HP_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with GLOBAL_HP_LOCK.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _accepted(document: object, source_sha256: str, endpoint_sha256: str) -> bool:
    if not isinstance(document, Mapping):
        return False
    final = document.get("final_result")
    contract = document.get("input_contract")
    if not isinstance(final, Mapping) or not isinstance(contract, Mapping):
        return False
    final_contract = final.get("input_contract")
    transforms = final.get("problem_transformations")
    scope = final.get("authority_scope")
    return bool(
        document.get("schema_version")
        == "geotarget.exp008-target-first-fallback-composition/v1"
        and final.get("source_raw_sha256") == source_sha256
        and final.get("endpoint_float64_sha256") == endpoint_sha256
        and contract.get("same_source_bytes_both_attempts") is True
        and contract.get("same_float64_endpoint_both_attempts") is True
        and contract.get("source_or_problem_modified") is False
        and contract.get("bounds_added") is False
        and contract.get("gauge_or_symmetry_reduction") is False
        and isinstance(final_contract, Mapping)
        and all(
            final_contract.get(name) is False
            for name in ("truth", "known_target_count", "case_id", "family")
        )
        and isinstance(transforms, Mapping)
        and transforms
        and all(value is False for value in transforms.values())
        and isinstance(scope, Mapping)
        and scope.get("numerical_configuration_512_768") is True
        and scope.get("target_512_768_1024") is True
        and scope.get("original_dsl_hp_replay") is True
        and scope.get("target_only_owned_pslq") is True
        and scope.get("all_coordinate_exactification_required") is False
        and scope.get("exact_configuration_witness_required") is False
        and scope.get("target_image_completeness_required") is False
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--endpoint", type=_parse_endpoint, required=True)
    parser.add_argument("--endpoint-sha256", required=True)
    parser.add_argument("--cpu", type=int, default=13)
    parser.add_argument("--deadline-seconds", type=float, default=46.0)
    parser.add_argument("--primary-cap-seconds", type=float, default=23.0)
    parser.add_argument("--process-timeout-seconds", type=float, default=56.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan-sha256")
    arguments = parser.parse_args()

    if arguments.cpu < 0 or arguments.cpu >= 16:
        raise SystemExit("CPU must be a first-sibling physical core in [0,15]")
    if (
        not math.isfinite(arguments.deadline_seconds)
        or not math.isfinite(arguments.primary_cap_seconds)
        or not math.isfinite(arguments.process_timeout_seconds)
        or arguments.deadline_seconds <= 0.0
        or arguments.primary_cap_seconds <= 0.0
        or arguments.process_timeout_seconds <= arguments.deadline_seconds
        or arguments.process_timeout_seconds > 56.0
    ):
        raise SystemExit("invalid HP deadline/process timeout")
    if len(arguments.source_sha256) != 64 or len(arguments.endpoint_sha256) != 64:
        raise SystemExit("source and endpoint SHA-256 values must have 64 hex digits")
    try:
        int(arguments.source_sha256, 16)
        int(arguments.endpoint_sha256, 16)
    except ValueError as error:
        raise SystemExit("source and endpoint SHA-256 values must be hexadecimal") from error

    endpoint = arguments.endpoint
    observed_endpoint_sha256 = _endpoint_sha256(endpoint)
    if observed_endpoint_sha256 != arguments.endpoint_sha256:
        raise SystemExit("endpoint Float64 SHA-256 mismatch")
    _check_source(arguments.source, arguments.source_sha256, len(endpoint))
    if not PYTHON.is_file() or not WORKER.is_file():
        raise SystemExit("frozen HP Python or worker is unavailable")

    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / "authority.json"
    status = output / "process-status.json"
    command = [
        "taskset",
        "-c",
        str(arguments.cpu),
        str(PYTHON),
        str(WORKER),
        "--source",
        str(arguments.source.resolve()),
        "--source-sha256",
        arguments.source_sha256,
        "--endpoint",
        json.dumps(endpoint, separators=(",", ":"), allow_nan=False),
        "--deadline-seconds",
        str(arguments.deadline_seconds),
        "--primary-cap-seconds",
        str(arguments.primary_cap_seconds),
        "--output",
        str(artifact),
    ]
    plan = {
        "schema_version": "geotarget.exp008-single-raw-endpoint-hp-plan/v1",
        "status": "DRY_RUN_NOT_STARTED",
        "source_sha256": arguments.source_sha256,
        "endpoint_float64_sha256": observed_endpoint_sha256,
        "endpoint": endpoint,
        "worker_sha256": _sha256(WORKER.read_bytes()),
        "command": command,
        "truth_read": False,
        "case_or_family_identity_read": False,
        "source_or_problem_modified": False,
        "bounds_or_gauge_added": False,
        "endpoint_unchanged_before_refinement": True,
        "hp_child_count_started": 0,
    }
    plan_path = output / "PLAN.json"
    atomic_write_json(plan_path, plan)
    plan_sha256 = _sha256(plan_path.read_bytes())
    if not arguments.execute:
        print(
            json.dumps(
                {
                    "plan_sha256": plan_sha256,
                    "endpoint_float64_sha256": observed_endpoint_sha256,
                },
                indent=2,
            )
        )
        return
    if arguments.plan_sha256 != plan_sha256:
        raise SystemExit("execution requires the exact dry-run PLAN SHA-256")

    limits = Limits(
        timeout_seconds=arguments.process_timeout_seconds,
        rss_bytes=480 * 1024**2,
        address_space_bytes=1536 * 1024**2,
        data_bytes=1024 * 1024**2,
        output_bytes=1024**2,
        tail_bytes=16 * 1024,
    )
    artifact.unlink(missing_ok=True)
    with _exclusive_hp_job():
        guarded = run_guarded(
            command,
            limits=limits,
            environment=THREAD_ENVIRONMENT,
            cwd=ROOT,
            status_path=status,
        )
    document = None
    if guarded.accepted_output and artifact.is_file():
        try:
            document = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            document = None
    atomic_write_json(
        output / "RESULT.json",
        {
            "schema_version": "geotarget.exp008-single-raw-endpoint-hp-result/v1",
            "status": "COMPLETE",
            "process_classification": guarded.classification,
            "artifact_accepted": _accepted(
                document, arguments.source_sha256, observed_endpoint_sha256
            ),
            "authority_pass": (
                document.get("authority_pass") is True
                if isinstance(document, Mapping)
                else False
            ),
            "winner": (
                document.get("winner") if isinstance(document, Mapping) else None
            ),
            "source_sha256": arguments.source_sha256,
            "endpoint_float64_sha256": observed_endpoint_sha256,
            "endpoint_unchanged_before_refinement": True,
            "artifact_sha256": (
                _sha256(artifact.read_bytes()) if artifact.is_file() else None
            ),
            "truth_read": False,
            "case_or_family_identity_read": False,
            "source_or_problem_modified": False,
            "bounds_or_gauge_added": False,
        },
    )


if __name__ == "__main__":
    main()
