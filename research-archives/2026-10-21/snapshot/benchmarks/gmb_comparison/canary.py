"""Linux one-CPU synthetic canaries. This never loads any of the 36 IMO cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.gmb.campaign import host_snapshot, monitor
from benchmarks.gmb.environment import terminate_group
from benchmarks.gmb_comparison.checker import CHECKER_POLICY, check_configuration, inspect_gmbl
from benchmarks.gmb_comparison.measurement_worker import write_json
from benchmarks.gmb_comparison.sources import sha256

REPO = Path(__file__).resolve().parents[2]
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)
SYNTHETIC_GMBL = """(param (A B C) triangle)
(define M point (midp A B))
(define l line (line A B))
(define Omega circle (circ A B C))
(eval (cong A C B C))
"""


def canary_identity():
    from geosolver.runtime.integrity import engine_identity_hashes

    sources = sorted(Path(__file__).parent.glob("*.py")) + [
        REPO / "benchmarks/gmb/campaign.py",
        REPO / "benchmarks/gmb/environment.py",
        REPO / "benchmarks/research_runner.py",
        REPO / "benchmarks/gmb_comparison/protocol.json",
        REPO / "src/geosolver/engine-lock.json",
        REPO / "uv.lock",
    ]
    return {
        "engine_identity": engine_identity_hashes(),
        "python": sys.version,
        "executable": sys.executable,
        "prefix": sys.prefix,
        "source_sha256": {str(path.relative_to(REPO)): sha256(path) for path in sources},
        "checker_policy": CHECKER_POLICY,
    }


def synthetic_gmbl(*, redundant=False):
    if not redundant:
        return SYNTHETIC_GMBL
    return SYNTHETIC_GMBL + "(assert (= (dist A C) 2))\n(assert (= (mul 2 (dist A C)) 4))\n"


def unexpected_observation_failure(failure):
    # A native accepted candidate must be materializable. Only optional,
    # unaccepted intermediate candidates may legitimately fail domain checks.
    return not (
        failure.get("kind") == "candidate_domain_rejection"
        and failure.get("stage") in {"refinement_return", "verified_candidate_revision"}
    )


def healthy_canary_completion(artifact, child):
    # Matching two error artifacts is not evidence of healthy instrumentation.
    return bool(
        artifact
        and artifact.get("status") == "completed"
        and artifact.get("solver_status") == "success"
        and artifact.get("public_solved") is True
        and child.get("outcome") == "completed"
        and child.get("solver_status") == "success"
    )


def observation_record_issues(payload, event, *, timeout):
    if event is None:
        return ["missing_emission_event"]
    issues = []
    candidate = payload["candidate"]
    coordinates = hashlib.sha256(
        json.dumps(candidate["x_hp"], separators=(",", ":")).encode()
    ).hexdigest()
    for key in ("candidate_uid", "candidate_id", "revision", "coordinate_sha256", "stage"):
        if payload.get(key) != event.get(key):
            issues.append(f"event_identity_mismatch:{key}")
    if candidate["candidate_id"] != payload["candidate_id"]:
        issues.append("candidate_id_mismatch")
    if candidate["revision"] != payload["revision"]:
        issues.append("candidate_revision_mismatch")
    if coordinates != payload["coordinate_sha256"]:
        issues.append("coordinate_hash_mismatch")
    observed = payload["coordinate_observed_seconds"]
    materialized = payload["materialized_seconds"]
    emitted = event.get("emitted_seconds")
    if emitted is None or not 0 <= observed <= materialized <= emitted <= timeout:
        issues.append("invalid_emission_time")
    return issues


def synthetic_problem(*, redundant=False):
    conditions = [{"left": "Area(A, B, C)", "operator": ">", "right": 0}]
    if redundant:
        conditions.extend(
            [
                {"left": "Distance(A,C)", "operator": "=", "right": 2},
                {"left": "2*Distance(A,C)", "operator": "=", "right": 4},
            ]
        )
    return {
        "id": "SYNTHETIC_REDUNDANT" if redundant else "SYNTHETIC_GUARDS_ONLY",
        "variables": ["x", "y"],
        "constructions": [
            {"name": "A", "expression": "Point(0,0)"},
            {"name": "B", "expression": "Point(1,0)"},
            {"name": "C", "expression": "Point(x,y)"},
            {"name": "M", "expression": "Midpoint(A,B)"},
            {"name": "l", "expression": "Line(A,B)"},
            {"name": "Omega", "expression": "Circumcircle(A,B,C)"},
        ],
        "conditions": conditions,
        "target": "0",
    }


def run_synthetic(directory, *, problem, instrument, cpu, timeout):
    from geosolver.runtime.integrity import engine_identity_hashes

    directory.mkdir(parents=True, exist_ok=False)
    problem_path = directory / "problem.json"
    write_json(problem_path, problem)
    request = {
        "schema_version": 1,
        "synthetic_canary": True,
        "seed": 0,
        "cpu": cpu,
        "timeout_seconds": timeout,
        "input": str(problem_path),
        "input_sha256": sha256(problem_path),
        "venv": str(Path(sys.prefix).resolve()),
        "output_directory": str(directory),
        "engine_identity": engine_identity_hashes(),
        "declarations": inspect_gmbl(SYNTHETIC_GMBL)["declarations"],
        "instrument": instrument,
    }
    environment = dict(os.environ)
    environment.update({key: "1" for key in THREAD_VARIABLES})
    environment.update({"PYTHONHASHSEED": "0", "CUDA_VISIBLE_DEVICES": "-1"})
    command = [
        "taskset",
        "--cpu-list",
        str(cpu),
        sys.executable,
        "-B",
        "-m",
        "benchmarks.gmb_comparison.measurement_worker",
        str(directory / "request.json"),
    ]
    before = host_snapshot(cpu)
    origin = time.monotonic()
    request["monotonic_origin"] = origin
    write_json(directory / "request.json", request)
    with (
        (directory / "stdout.log").open("w") as stdout,
        (directory / "stderr.log").open("w") as stderr,
    ):
        process = subprocess.Popen(
            command, cwd=REPO, env=environment, stdout=stdout, stderr=stderr, start_new_session=True
        )
        try:
            resources = monitor(process, origin, timeout, cpu)
        except BaseException:
            terminate_group(process)
            raise
    record = {
        "process": resources,
        "command": command,
        "host_before": before,
        "host_after": host_snapshot(cpu),
        "problem_sha256": sha256(problem_path),
        "environment": {key: environment[key] for key in THREAD_VARIABLES},
    }
    write_json(directory / "run.json", record)
    path = directory / "worker-artifact.json"
    artifact = json.loads(path.read_text()) if path.is_file() else None
    return record, artifact


def canary(directory, *, cpu=4, timeout=30):
    if sys.platform != "linux" or cpu not in os.sched_getaffinity(0):
        raise RuntimeError("This canary requires Linux and an available single CPU")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    identity = canary_identity()
    inputs = []
    for redundant in (False, True):
        problem = synthetic_problem(redundant=redundant)
        case_dir = directory / problem["id"]
        case_dir.mkdir()
        problem_path, source_path = case_dir / "problem.json", case_dir / "checker-input.smt2"
        write_json(problem_path, problem)
        source_path.write_text(synthetic_gmbl(redundant=redundant), encoding="utf-8")
        inputs.append(
            {
                "case_id": problem["id"],
                "problem": str(problem_path.relative_to(directory)),
                "problem_sha256": sha256(problem_path),
                "checker_input": str(source_path.relative_to(directory)),
                "checker_input_sha256": sha256(source_path),
            }
        )
    write_json(
        directory / "canary-manifest.json",
        {
            "schema_version": 1,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "study_kind": "synthetic_instrumentation_canary",
            "natural_cases_executed": 0,
            "seed": 0,
            "cpu": cpu,
            "timeout_seconds": timeout,
            "order": "guards plain, guards observed, redundant plain, redundant observed",
            "intermediate_candidate_observation": False,
            "identity": identity,
            "inputs": inputs,
        },
    )
    checks = []
    for redundant in (False, True):
        problem = synthetic_problem(redundant=redundant)
        source = synthetic_gmbl(redundant=redundant)
        paired = []
        for instrument in (False, True):
            run_dir = directory / problem["id"] / ("observed" if instrument else "plain")
            record, artifact = run_synthetic(
                run_dir,
                problem=problem,
                instrument=instrument,
                cpu=cpu,
                timeout=timeout,
            )
            paired.append((run_dir, record, artifact))
        plain, observed = paired
        artifacts_present = plain[2] is not None and observed[2] is not None
        same_answers = artifacts_present and plain[2]["answers"] == observed[2]["answers"]
        same_candidates = artifacts_present and (
            plain[2]["candidate_records"] == observed[2]["candidate_records"]
        )
        resource_ok = all(
            not record["process"]["timed_out"]
            and record["process"]["returncode"] == 0
            and not record["process"]["cancelled"]
            and not record["process"]["affinity_violations"]
            and not record["process"]["descendants_remaining_at_leader_exit"]
            for _, record, _ in paired
        )
        child_results = []
        for run_dir, _, _ in paired:
            child_path = run_dir / "child-result.json"
            child_results.append(json.loads(child_path.read_text()) if child_path.is_file() else {})
        completion_ok = all(
            healthy_canary_completion(run[2], child)
            for run, child in zip(paired, child_results, strict=True)
        )
        assessments = []
        events_path = observed[0] / "events.jsonl"
        events = (
            [json.loads(line) for line in events_path.read_text().splitlines()]
            if events_path.is_file()
            else []
        )
        emitted = {item["model"]: item for item in events if item["event"] == "model_materialized"}
        observation_errors = []
        child = child_results[1]
        observation_errors.extend(
            item
            for item in child.get("materialization_failures", [])
            if unexpected_observation_failure(item)
        )
        for model in sorted((observed[0] / "models").glob("*.json")):
            payload = json.loads(model.read_text())
            outcome = check_configuration(source, payload["witness"])
            event = emitted.get(f"models/{model.name}")
            integrity_issues = observation_record_issues(payload, event, timeout=timeout)
            observation_errors.extend(integrity_issues)
            assessments.append(
                {
                    "model": model.name,
                    "sha256": sha256(model),
                    "materialized_seconds": payload["materialized_seconds"],
                    "emitted_seconds": None if event is None else event.get("emitted_seconds"),
                    "stage": payload["stage"],
                    "integrity_issues": integrity_issues,
                    "assessment": outcome,
                }
            )
        write_json(observed[0] / "synthetic-assessment.json", assessments)
        valid_count = sum(item["assessment"]["valid"] is True for item in assessments)
        primary_count = sum(
            item["assessment"]["valid"] is True and item["stage"] == "native_accepted_return"
            for item in assessments
        )
        check = {
            "case_id": problem["id"],
            "artifacts_present": artifacts_present,
            "same_exact_answers": same_answers,
            "same_candidate_records": same_candidates,
            "resource_ok": resource_ok,
            "healthy_solver_completion": completion_ok,
            "exported_count": len(assessments),
            "independently_valid_count": valid_count,
            "native_accepted_and_valid_count": primary_count,
            "all_exported_valid": bool(assessments) and valid_count == len(assessments),
            "observation_errors": observation_errors,
            "passed": bool(
                resource_ok
                and completion_ok
                and same_answers
                and same_candidates
                and primary_count
                and primary_count == len(assessments)
                and not observation_errors
            ),
        }
        checks.append(check)
        print(json.dumps(check), flush=True)
    identity_unchanged = canary_identity() == identity
    result = {
        "schema_version": 1,
        "natural_cases_executed": 0,
        "cpu": cpu,
        "synthetic_timeout_seconds": timeout,
        "not_a_performance_comparison": True,
        "manifest_sha256": sha256(directory / "canary-manifest.json"),
        "source_identity_unchanged": identity_unchanged,
        "checks": checks,
        "passed": identity_unchanged and all(item["passed"] for item in checks),
    }
    write_json(directory / "summary.json", result)
    hashes = {
        str(path.relative_to(directory)): sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }
    write_json(directory / "sha256.json", hashes)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cpu", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if not canary(args.output, cpu=args.cpu, timeout=args.timeout)["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
