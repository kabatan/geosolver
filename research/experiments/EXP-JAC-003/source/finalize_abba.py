"""Atomically publish a captured EXP-JAC-003 ABBA run after external audits."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import formal_abba


RUN_SCHEMA = "exp-jac-003-formal-abba-run/v1"
HOST_SCHEMA = "exp-jac-003-host-observation/v1"
SOURCE_OBSERVATION_SCHEMA = "exp-jac-003-source-observation/v1"
FORMAL_AUDIT_SCHEMA = "geotarget.formal-performance-run/v1"
LABEL = "EXP-JAC-003-development-abba"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise formal_abba.FormalCaptureError(f"object required: {path}")
    return value


def _copy_once(source: Path, target: Path) -> None:
    if target.exists():
        raise formal_abba.FormalCaptureError(f"audit target exists: {target}")
    with source.open("rb") as reader, target.open("xb") as writer:
        shutil.copyfileobj(reader, writer)
        writer.flush()
        os.fsync(writer.fileno())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--source-lock", required=True, type=Path)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--official", required=True, type=Path)
    parser.add_argument("--outer-audit", required=True, type=Path)
    parser.add_argument("--host-observation", required=True, type=Path)
    parser.add_argument("--source-observation", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repo = arguments.repo.resolve()
    staging = arguments.staging.resolve()
    official = arguments.official.resolve()
    if not staging.is_dir():
        raise formal_abba.FormalCaptureError("formal staging directory is missing")
    if official.exists():
        raise formal_abba.FormalCaptureError("official result already exists")
    source_lock, source_lock_sha = formal_abba._validate_source_lock(
        repo, arguments.source_lock.resolve()
    )
    capture_path = staging / "capture.json"
    capture = _load(capture_path)
    if capture.get("schema_version") != formal_abba.CAPTURE_SCHEMA:
        raise formal_abba.FormalCaptureError("capture schema drift")
    if not capture.get("capture_complete"):
        raise formal_abba.FormalCaptureError("capture is incomplete")
    if capture.get("outcomes_inspected_by_orchestrator") is not False:
        raise formal_abba.FormalCaptureError(
            "capture outcome-inspection boundary drift"
        )
    if capture.get("source_lock_sha256") != source_lock_sha:
        raise formal_abba.FormalCaptureError("capture/source lock mismatch")
    if capture.get("sequence") != list(formal_abba.ABBA):
        raise formal_abba.FormalCaptureError("capture ABBA order drift")
    if capture.get("child_exit_codes") != [0, 0, 0, 0]:
        raise formal_abba.FormalCaptureError("capture child failure")
    for row in capture["segments"]:
        trace = staging / row["trace_path"]
        if (
            not trace.is_file()
            or formal_abba._file_sha256(trace) != row["trace_sha256"]
        ):
            raise formal_abba.FormalCaptureError("captured segment trace drift")

    audit = _load(arguments.outer_audit.resolve())
    if audit.get("schema") != FORMAL_AUDIT_SCHEMA:
        raise formal_abba.FormalCaptureError("outer formal audit schema drift")
    if audit.get("label") != LABEL:
        raise formal_abba.FormalCaptureError("outer formal audit label drift")
    if audit.get("outcome") != "completed" or audit.get("exit_code") != 0:
        raise formal_abba.FormalCaptureError(
            "outer formal audit did not complete cleanly"
        )
    if audit.get("error") is not None:
        raise formal_abba.FormalCaptureError("outer formal audit contains an error")

    host = _load(arguments.host_observation.resolve())
    if host.get("schema_version") != HOST_SCHEMA or host.get("label") != LABEL:
        raise formal_abba.FormalCaptureError("host observation schema or label drift")
    if host.get("formal_outer_pid") != audit.get("child_pid"):
        raise formal_abba.FormalCaptureError("host observation outer PID mismatch")
    if host.get("formal_segment_pids") != capture.get("child_pids"):
        raise formal_abba.FormalCaptureError("host observation segment PID mismatch")
    if host.get("host_contention_event_count") != 0:
        raise formal_abba.FormalCaptureError("host contention was observed")
    if host.get("lease_loss_count") != 0:
        raise formal_abba.FormalCaptureError("formal lease loss was observed")
    if host.get("all_formal_pids_ended") is not True:
        raise formal_abba.FormalCaptureError("formal PIDs are still live")
    if host.get("outcomes_inspected") is not False:
        raise formal_abba.FormalCaptureError("host observer inspected outcomes")
    if host.get("observation_started_at_utc") > audit.get("started_at_utc"):
        raise formal_abba.FormalCaptureError("host observation started too late")
    if host.get("observation_ended_at_utc") < audit.get("ended_at_utc"):
        raise formal_abba.FormalCaptureError("host observation ended too early")

    source_observation = _load(arguments.source_observation.resolve())
    if source_observation.get("schema_version") != SOURCE_OBSERVATION_SCHEMA:
        raise formal_abba.FormalCaptureError("source observation schema drift")
    if source_observation.get("head_commit") != capture["lock_commit"]:
        raise formal_abba.FormalCaptureError("source observation HEAD mismatch")
    if source_observation.get("source_lock_sha256") != source_lock_sha:
        raise formal_abba.FormalCaptureError("source observation lock mismatch")
    if source_observation.get("outcomes_inspected") is not False:
        raise formal_abba.FormalCaptureError("source observer inspected outcomes")
    if source_observation.get("source_hash_mismatch_count") != 0:
        raise formal_abba.FormalCaptureError("source observer found source drift")

    audit_dir = staging / "audit"
    if audit_dir.exists():
        raise formal_abba.FormalCaptureError("audit staging directory already exists")
    audit_dir.mkdir()
    _copy_once(arguments.outer_audit.resolve(), audit_dir / "formal-run-audit.json")
    _copy_once(
        arguments.host_observation.resolve(), audit_dir / "host-observation.json"
    )
    _copy_once(
        arguments.source_observation.resolve(), audit_dir / "source-observation.json"
    )
    run = {
        "atomically_published": True,
        "candidate_input_uncompressed_sha256": capture[
            "candidate_input_uncompressed_sha256"
        ],
        "child_exit_codes": capture["child_exit_codes"],
        "child_pids": capture["child_pids"],
        "experiment_id": "EXP-JAC-003",
        "fresh_process_count": capture["fresh_process_count"],
        "fresh_writable_depot_count": capture["fresh_writable_depot_count"],
        "frozen_control_preflight_mismatch_count": 0,
        "host_contention_event_count": host["host_contention_event_count"],
        "input_hash_mismatch_count": 0,
        "input_manifest_sha256": capture["input_manifest_sha256"],
        "julia_manifest_sha256": capture["julia_manifest_sha256"],
        "lease_loss_count": host["lease_loss_count"],
        "process_wall_ns": capture["process_wall_ns"],
        "public_surface_drift_count": 0,
        "schema_version": RUN_SCHEMA,
        "segments": capture["segments"],
        "sequence": capture["sequence"],
        "source_hash_mismatch_count": 0,
        "source_lock_sha256": source_lock_sha,
        "staging_mismatch_count": 0,
        "audit_sha256": {
            "formal": formal_abba._file_sha256(audit_dir / "formal-run-audit.json"),
            "host": formal_abba._file_sha256(audit_dir / "host-observation.json"),
            "source": formal_abba._file_sha256(audit_dir / "source-observation.json"),
        },
    }
    formal_abba._write_once(staging / "formal-run-manifest.json", run)
    official.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, official)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
