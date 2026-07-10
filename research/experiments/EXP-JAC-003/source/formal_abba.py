"""Capture one result-blind, nonofficial EXP-JAC-003 ABBA staging directory.

Invoke this command exactly once as the child of research/harness/exclusive_run.py.
It never publishes an official result.  Finalization requires the completed
outer audit and an independent host observation after this process exits.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


CAPTURE_SCHEMA = "exp-jac-003-formal-abba-capture/v1"
SOURCE_LOCK_SCHEMA = "exp-jac-003-development-source-lock/v1"
ABBA = (
    "K0-DENSE-PUBLIC",
    "K1-CACHED-ROUTED",
    "K1-CACHED-ROUTED",
    "K0-DENSE-PUBLIC",
)


class FormalCaptureError(RuntimeError):
    """A fail-closed preflight or child-capture error."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _write_once(path: Path, document: dict[str, Any]) -> None:
    if path.exists():
        raise FormalCaptureError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        raise FormalCaptureError(f"temporary output already exists: {temporary}")
    with temporary.open("xb") as handle:
        handle.write(_canonical(document) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def _validate_source_lock(repo: Path, path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    lock = json.loads(payload)
    if lock.get("schema_version") != SOURCE_LOCK_SCHEMA:
        raise FormalCaptureError("source-lock schema drift")
    head = _git(repo, "rev-parse", "HEAD")
    relative_lock = path.resolve().relative_to(repo).as_posix()
    lock_commit = _git(repo, "log", "-1", "--format=%H", "--", relative_lock)
    if head != lock_commit:
        raise FormalCaptureError("HEAD is not the commit that froze the source lock")
    if _git(repo, "rev-parse", "HEAD^") != lock["source_commit"]:
        raise FormalCaptureError("source lock is not the sole child of source_commit")
    for relative, expected in lock["files"].items():
        target = repo.joinpath(*relative.split("/"))
        if not target.is_file() or _file_sha256(target) != expected:
            raise FormalCaptureError(f"source-lock file drift: {relative}")
    return lock, _sha256(payload)


def _inventory(root: Path) -> tuple[str, int, int]:
    rows: list[dict[str, Any]] = []
    total = 0
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        payload = path.read_bytes()
        total += len(payload)
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(payload),
                "size": len(payload),
            }
        )
    return _sha256(_canonical(rows)), len(rows), total


def _make_read_only(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def _base_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        JULIA_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    return environment


def _run_logged(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    started = time.monotonic_ns()
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=dict(environment),
            stdout=stdout,
            stderr=stderr,
        )
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except BaseException:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise
    ended = time.monotonic_ns()
    return {
        "command": list(command),
        "exit_code": exit_code,
        "pid": process.pid,
        "wall_ns": ended - started,
    }


def _require_success(result: dict[str, Any], label: str) -> None:
    if result["exit_code"] != 0:
        raise FormalCaptureError(f"{label} exited with {result['exit_code']}")


def _julia_command(
    julia: str, project: Path, script: Path, *arguments: Path | str
) -> list[str]:
    return [
        julia,
        "--startup-file=no",
        "--history-file=no",
        "--threads=1",
        f"--project={project}",
        str(script),
        *(str(argument) for argument in arguments),
    ]


def _segment_topology(path: Path, variant: str, expected: dict[str, str]) -> None:
    document = json.loads(path.read_bytes())
    checks = {
        "schema_version": "exp-jac-003-segment-trace/v1",
        "variant": variant,
        "case_count": 64,
        "starts_per_case": 32,
        "candidate_input_sha256": expected["candidate"],
        "manifest_sha256": expected["manifest"],
        "source_lock_sha256": expected["source_lock"],
        "julia_threads": 1,
    }
    for key, value in checks.items():
        if document.get(key) != value:
            raise FormalCaptureError(f"segment topology mismatch for {key}")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 64:
        raise FormalCaptureError("segment case topology mismatch")
    ids = [case.get("opaque_case_id") for case in cases]
    if ids != sorted(ids) or len(set(ids)) != 64:
        raise FormalCaptureError("segment opaque-ID topology mismatch")
    # No attempt status, endpoint, callback, timing metric or Gold field is read here.


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--source-lock", required=True, type=Path)
    parser.add_argument("--input-manifest", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--frozen-k0", required=True, type=Path)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--julia", default="julia")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repo = arguments.repo.resolve()
    staging = arguments.staging.resolve()
    partial = staging.with_name(f".{staging.name}.partial")
    if staging.exists() or partial.exists():
        raise FormalCaptureError("formal staging or partial path already exists")
    if _git(repo, "status", "--porcelain"):
        raise FormalCaptureError("formal source worktree must be clean")
    source_lock, source_lock_sha = _validate_source_lock(
        repo, arguments.source_lock.resolve()
    )
    input_manifest_bytes = arguments.input_manifest.read_bytes()
    input_manifest = json.loads(input_manifest_bytes)
    input_manifest_sha = _sha256(input_manifest_bytes)
    candidate_compressed = arguments.candidate.read_bytes()
    candidate_raw = gzip.decompress(candidate_compressed)
    candidate_descriptor = input_manifest["artifacts"]["candidate"]
    if _sha256(candidate_compressed) != candidate_descriptor["compressed_sha256"]:
        raise FormalCaptureError("candidate compressed hash mismatch")
    if _sha256(candidate_raw) != candidate_descriptor["uncompressed_sha256"]:
        raise FormalCaptureError("candidate uncompressed hash mismatch")

    project = repo / "research" / "experiments" / "EXP-JAC-003"
    source = project / "source"
    julia_manifest_sha = _file_sha256(project / "Manifest.toml")
    if julia_manifest_sha != source_lock["julia_manifest_sha256"]:
        raise FormalCaptureError("Julia Manifest hash mismatch")
    expected = {
        "candidate": candidate_descriptor["uncompressed_sha256"],
        "manifest": julia_manifest_sha,
        "source_lock": source_lock_sha,
    }

    partial.mkdir(parents=True)
    logs = partial / "logs"
    traces = partial / "segments"
    logs.mkdir()
    traces.mkdir()
    capture_complete = False
    try:
        with tempfile.TemporaryDirectory(
            prefix="exp-jac-003-", dir=staging.parent
        ) as raw_temp:
            temporary = Path(raw_temp).resolve()
            candidate_path = temporary / "development-candidate-inputs.json"
            candidate_path.write_bytes(candidate_raw)
            template = temporary / "template-depot"
            template.mkdir()
            template_environment = _base_environment()
            template_environment["JULIA_DEPOT_PATH"] = str(template)
            preparation = _run_logged(
                [
                    arguments.julia,
                    "--startup-file=no",
                    "--history-file=no",
                    "--threads=1",
                    f"--project={project}",
                    "-e",
                    "using Pkg; Pkg.instantiate(); Pkg.precompile()",
                ],
                cwd=repo,
                environment=template_environment,
                stdout_path=logs / "environment.stdout.log",
                stderr_path=logs / "environment.stderr.log",
                timeout_seconds=3_600.0,
            )
            _require_success(preparation, "environment preparation")
            template_hash, template_files, template_bytes = _inventory(template)
            _make_read_only(template)
            _validate_source_lock(repo, arguments.source_lock.resolve())

            preflight_overlay = temporary / "preflight-overlay"
            preflight_overlay.mkdir()
            preflight_environment = _base_environment()
            preflight_environment["JULIA_DEPOT_PATH"] = os.pathsep.join(
                (str(preflight_overlay), str(template))
            )
            preflight_environment.update(
                EXP_JAC003_CANDIDATE_SHA256=expected["candidate"],
                EXP_JAC003_MANIFEST_SHA256=expected["manifest"],
                EXP_JAC003_SOURCE_LOCK_SHA256=expected["source_lock"],
            )
            julia_tests = _run_logged(
                _julia_command(
                    arguments.julia,
                    project,
                    source / "test_candidate.jl",
                ),
                cwd=repo,
                environment=preflight_environment,
                stdout_path=logs / "julia-tests.stdout.log",
                stderr_path=logs / "julia-tests.stderr.log",
                timeout_seconds=900.0,
            )
            _require_success(julia_tests, "Julia candidate tests")
            python_tests = _run_logged(
                [sys.executable, "-m", "unittest", "test_assessor.py"],
                cwd=source,
                environment=_base_environment(),
                stdout_path=logs / "python-tests.stdout.log",
                stderr_path=logs / "python-tests.stderr.log",
                timeout_seconds=300.0,
            )
            _require_success(python_tests, "Python assessor tests")
            current_surface = partial / "current-public-surface.json"
            public_surface = _run_logged(
                _julia_command(
                    arguments.julia,
                    project,
                    source / "capture_current_public_surface.jl",
                    project / "baseline-contract.json",
                    project / "public-baseline-snapshot.json",
                    current_surface,
                ),
                cwd=repo,
                environment=preflight_environment,
                stdout_path=logs / "public-surface.stdout.log",
                stderr_path=logs / "public-surface.stderr.log",
                timeout_seconds=900.0,
            )
            _require_success(public_surface, "public-surface replay")

            safety_trace = partial / "candidate-safety.json"
            safety_capture = _run_logged(
                _julia_command(
                    arguments.julia,
                    project,
                    source / "capture_safety.jl",
                    candidate_path,
                    safety_trace,
                ),
                cwd=repo,
                environment=preflight_environment,
                stdout_path=logs / "safety-capture.stdout.log",
                stderr_path=logs / "safety-capture.stderr.log",
                timeout_seconds=7_200.0,
            )
            _require_success(safety_capture, "candidate safety capture")
            safety_report = partial / "safety-assessment.json"
            safety_assessment = _run_logged(
                [
                    sys.executable,
                    str(source / "assess_safety_only.py"),
                    "--manifest",
                    str(arguments.input_manifest.resolve()),
                    "--truth",
                    str(arguments.truth.resolve()),
                    "--safety",
                    str(safety_trace),
                    "--output",
                    str(safety_report),
                ],
                cwd=repo,
                environment=_base_environment(),
                stdout_path=logs / "safety-assessment.stdout.log",
                stderr_path=logs / "safety-assessment.stderr.log",
                timeout_seconds=900.0,
            )
            _require_success(safety_assessment, "independent safety assessment")

            k0_preflight_trace = partial / "k0-preflight.json"
            k0_preflight = _run_logged(
                _julia_command(
                    arguments.julia,
                    project,
                    source / "run_segment.jl",
                    ABBA[0],
                    candidate_path,
                    k0_preflight_trace,
                ),
                cwd=repo,
                environment=preflight_environment,
                stdout_path=logs / "k0-preflight.stdout.log",
                stderr_path=logs / "k0-preflight.stderr.log",
                timeout_seconds=13_200.0,
            )
            _require_success(k0_preflight, "K0 preflight capture")
            _segment_topology(k0_preflight_trace, ABBA[0], expected)
            k0_report = partial / "k0-replay-assessment.json"
            k0_assessment = _run_logged(
                [
                    sys.executable,
                    str(source / "assess_k0_replay.py"),
                    "--manifest",
                    str(arguments.input_manifest.resolve()),
                    "--frozen-k0",
                    str(arguments.frozen_k0.resolve()),
                    "--trace",
                    str(k0_preflight_trace),
                    "--output",
                    str(k0_report),
                ],
                cwd=repo,
                environment=_base_environment(),
                stdout_path=logs / "k0-assessment.stdout.log",
                stderr_path=logs / "k0-assessment.stderr.log",
                timeout_seconds=900.0,
            )
            _require_success(k0_assessment, "K0 exact replay assessment")
            _validate_source_lock(repo, arguments.source_lock.resolve())

            segment_rows: list[dict[str, Any]] = []
            pids: set[int] = set()
            for slot, variant in enumerate(ABBA):
                overlay = temporary / f"segment-{slot}-overlay"
                overlay.mkdir()
                environment = _base_environment()
                environment["JULIA_DEPOT_PATH"] = os.pathsep.join(
                    (str(overlay), str(template))
                )
                environment.update(
                    EXP_JAC003_CANDIDATE_SHA256=expected["candidate"],
                    EXP_JAC003_MANIFEST_SHA256=expected["manifest"],
                    EXP_JAC003_SOURCE_LOCK_SHA256=expected["source_lock"],
                )
                trace = traces / f"segment-{slot}.json"
                result = _run_logged(
                    _julia_command(
                        arguments.julia,
                        project,
                        source / "run_segment.jl",
                        variant,
                        candidate_path,
                        trace,
                    ),
                    cwd=repo,
                    environment=environment,
                    stdout_path=logs / f"segment-{slot}.stdout.log",
                    stderr_path=logs / f"segment-{slot}.stderr.log",
                    timeout_seconds=13_200.0,
                )
                _require_success(result, f"formal segment {slot}")
                if result["pid"] in pids:
                    raise FormalCaptureError("formal child PID was reused")
                pids.add(result["pid"])
                _segment_topology(trace, variant, expected)
                overlay_hash, overlay_files, overlay_bytes = _inventory(overlay)
                segment_rows.append(
                    {
                        "child_pid": result["pid"],
                        "exit_code": result["exit_code"],
                        "overlay_bytes": overlay_bytes,
                        "overlay_file_count": overlay_files,
                        "overlay_inventory_sha256": overlay_hash,
                        "process_wall_ns": result["wall_ns"],
                        "slot": slot,
                        "trace_path": trace.relative_to(partial).as_posix(),
                        "trace_sha256": _file_sha256(trace),
                        "variant": variant,
                    }
                )
                _validate_source_lock(repo, arguments.source_lock.resolve())

            capture = {
                "candidate_input_uncompressed_sha256": expected["candidate"],
                "capture_complete": True,
                "child_exit_codes": [row["exit_code"] for row in segment_rows],
                "child_pids": [row["child_pid"] for row in segment_rows],
                "environment_preparation_wall_ns": preparation["wall_ns"],
                "experiment_id": "EXP-JAC-003",
                "fresh_process_count": 4,
                "fresh_writable_depot_count": 4,
                "input_manifest_sha256": input_manifest_sha,
                "julia_manifest_sha256": julia_manifest_sha,
                "lock_commit": _git(repo, "rev-parse", "HEAD"),
                "outcomes_inspected_by_orchestrator": False,
                "preflight": {
                    "julia_candidate_tests_exit_code": julia_tests["exit_code"],
                    "k0_exact_replay_exit_code": k0_assessment["exit_code"],
                    "public_surface_exit_code": public_surface["exit_code"],
                    "python_assessor_tests_exit_code": python_tests["exit_code"],
                    "safety_assessment_exit_code": safety_assessment["exit_code"],
                },
                "process_wall_ns": [row["process_wall_ns"] for row in segment_rows],
                "schema_version": CAPTURE_SCHEMA,
                "segments": segment_rows,
                "sequence": list(ABBA),
                "source_lock_sha256": source_lock_sha,
                "template_depot_bytes": template_bytes,
                "template_depot_file_count": template_files,
                "template_depot_inventory_sha256": template_hash,
            }
            _write_once(partial / "capture.json", capture)
            capture_complete = True
        os.replace(partial, staging)
    except BaseException:
        # Preserve a partial directory for forensic audit; never rename or publish it.
        raise
    if not capture_complete:
        raise FormalCaptureError("capture did not reach its terminal receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
