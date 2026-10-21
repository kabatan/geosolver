"""Frozen Linux IMO36 comparison; run native solvers first and assess offline."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from benchmarks.gmb import campaign as gmb
from benchmarks.gmb import environment as gmb_env
from benchmarks.gmb_comparison.canary import THREAD_VARIABLES, canary_identity
from benchmarks.gmb_comparison.prepare import preflight

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sha256, read_json, write_json = gmb.sha256, gmb.read_json, gmb.write_json


def check_seal(directory, name="SHA256SUMS"):
    """Read-only: unlike an old summarizer, never regenerate legacy artifacts."""
    root = Path(directory).resolve()
    for line in (root / name).read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or sha256(path) != digest:
            raise RuntimeError(f"Invalid sealed artifact: {relative}")


def check_canary(directory):
    directory = Path(directory).resolve()
    summary = read_json(directory / "summary.json")
    manifest = read_json(directory / "canary-manifest.json")
    if summary.get("passed") is not True or not summary.get("source_identity_unchanged"):
        raise RuntimeError("Synthetic instrumentation canary did not pass")
    if manifest["identity"] != canary_identity():
        raise RuntimeError("Canary implementation differs from the current harness")
    if summary["manifest_sha256"] != sha256(directory / "canary-manifest.json"):
        raise RuntimeError("Canary manifest changed")
    for relative, digest in read_json(directory / "sha256.json").items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory) or sha256(path) != digest:
            raise RuntimeError(f"Canary artifact changed: {relative}")
    return {
        "directory": str(directory),
        "summary_sha256": sha256(directory / "summary.json"),
        "manifest_sha256": sha256(directory / "canary-manifest.json"),
        "sha256_index_sha256": sha256(directory / "sha256.json"),
    }


def geo_environment():
    import geosolver
    from benchmarks.research_runner import runtime_fingerprint
    from geosolver.runtime.integrity import installed_dependencies, verify_engine_lock

    ok, reason = verify_engine_lock()
    if not ok:
        raise RuntimeError(reason)
    module = Path(geosolver.__file__).resolve()
    if module != REPO / "src/geosolver/__init__.py":
        raise RuntimeError(f"Unexpected imported GeoSolver: {module}")
    fingerprint = runtime_fingerprint()
    if fingerprint["issues"]:
        raise RuntimeError(f"Runtime dependency mismatch: {fingerprint['issues']}")
    return {
        "python": platform.python_version(),
        "executable": sys.executable,
        "prefix": str(Path(sys.prefix).resolve()),
        "module": str(module),
        "runtime_packages": installed_dependencies(),
        "runtime_fingerprint": fingerprint,
        "all_packages": dict(
            sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
        ),
    }


def implementation_files():
    paths = [
        path
        for path in HERE.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".json", ".md", ".smt2"}
        and "__pycache__" not in path.parts
        and "results" not in path.relative_to(HERE).parts
    ]
    paths.append(REPO / "benchmarks/research_runner.py")
    return gmb.identity_files() | {str(path.relative_to(REPO)): sha256(path) for path in paths}


def copy_checked(source, destination, digest):
    data = Path(source).read_bytes()
    import hashlib

    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError(f"Input changed before copying: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise RuntimeError(f"Refusing to overwrite input: {destination}")
    destination.write_bytes(data)


def prepare_campaign(directory, canary_directory, legacy_directories):
    if sys.platform != "linux":
        raise RuntimeError("This measurement protocol is Linux-only")
    directory = Path(directory).resolve()
    protocol = read_json(HERE / "protocol.json")
    if protocol.get("main_run_authorized") is not True:
        raise RuntimeError("The user has not authorized the main campaign")
    expected = {"cpu": 4, "time_limit_seconds": 180, "parallel_jobs": 1, "initial_seeds": [0, 1, 2]}
    if any(protocol[key] != value for key, value in expected.items()):
        raise RuntimeError("The authorized initial measurement settings changed")
    gmb_env.choose_cpu(protocol["cpu"])
    gmb_env.source_identity()
    report = preflight()
    if (
        not report["all_inputs_ready"]
        or report["input_count"] != 36
        or report["official_input_count"] != 34
        or report["original_aligned_input_count"] != 2
    ):
        raise RuntimeError("All 36 audited inputs must be ready")
    canary = check_canary(canary_directory)
    environment = geo_environment()
    # Only measurement-related changes must be committed; unrelated user notes stay untouched.
    scope = [
        "src",
        "benchmarks/gmb",
        "benchmarks/gmb_comparison",
        "tests",
        "pyproject.toml",
        "uv.lock",
    ]
    dirty = gmb.git("status", "--porcelain", "--untracked-files=all", "--", *scope)
    if dirty:
        raise RuntimeError("Commit the scoped input/harness checkpoint before main measurement")
    legacy = []
    baseline = None
    legacy_by_seed = {}
    for root in legacy_directories:
        root = Path(root).resolve()
        check_seal(root)
        old = read_json(root / "campaign-manifest.json")
        seeds = old["seeds"]
        if old["cpu"] != 4 or old["timeout_seconds"] != 180:
            raise RuntimeError("Legacy measurement settings differ")
        for name in ("campaign.py", "environment.py", "measurement_worker.py", "requirements.lock"):
            relative = f"benchmarks/gmb/{name}"
            if sha256(REPO / relative) != old["identity_files"][relative]:
                raise RuntimeError(f"Legacy GMB measurement implementation differs: {name}")
        if baseline and (
            old["options"] != baseline["options"] or old["source_files"] != baseline["source_files"]
        ):
            raise RuntimeError("The legacy GMB implementation/options differ across seeds")
        baseline = old
        for seed in seeds:
            if seed in legacy_by_seed:
                raise RuntimeError(f"Legacy seed {seed} is provided by multiple sources")
            legacy_by_seed[seed] = root
        legacy.append(
            {
                "directory": str(root),
                "seeds": seeds,
                "manifest_sha256": sha256(root / "campaign-manifest.json"),
                "sha256sums_sha256": sha256(root / "SHA256SUMS"),
            }
        )
    missing_seeds = [seed for seed in protocol["initial_seeds"] if seed not in legacy_by_seed]
    if missing_seeds:
        raise RuntimeError(f"No legacy GMB measurement covers seeds {missing_seeds}")
    directory.mkdir(parents=True, exist_ok=False)
    entries = []
    for row in sorted(report["cases"], key=lambda item: item["case_id"]):
        case_id = row["case_id"]
        audit = read_json(HERE / "audit" / f"{case_id}.json")
        selected = row["comparison_input"]
        entry = {
            "case_id": case_id,
            "geo_input": f"inputs/geosolver/{case_id}.json",
            "geo_sha256": row["case_sha256"],
            "gmbl_input": f"inputs/gmbl/{case_id}.smt2",
            "gmbl_sha256": selected["sha256"],
            "input_origin": selected["origin"],
            "original_assumptions_covered": row["original_assumptions_covered"],
            "declarations": row["checker_coverage"]["declarations"],
            "bindings": audit.get("witness_bindings", {}),
            "audit_sha256": row["audit_sha256"],
            "review_sha256": row["review_sha256"],
            "gmb_runs": {},
        }
        copy_checked(
            HERE / "cases" / f"{case_id}.json", directory / entry["geo_input"], entry["geo_sha256"]
        )
        copy_checked(selected["path"], directory / entry["gmbl_input"], entry["gmbl_sha256"])
        for seed in protocol["initial_seeds"]:
            if selected["origin"] == "official_gmb":
                run_dir = legacy_by_seed[seed] / "runs" / case_id / str(seed)
                if read_json(run_dir / "run.json")["input_sha256"] != entry["gmbl_sha256"]:
                    raise RuntimeError(f"Legacy input is different: {case_id}/{seed}")
                origin = "reused_official"
            else:
                run_dir = directory / "gmb-aligned/runs" / case_id / str(seed)
                origin = "new_aligned"
            entry["gmb_runs"][str(seed)] = {"directory": str(run_dir), "origin": origin}
        entries.append(entry)
    # This doctor only imports/tests the environment, not any natural problem.
    doctor_dir = directory / "gmb-environment"
    doctor_dir.mkdir()
    with (
        (doctor_dir / "stdout.log").open("w") as stdout,
        (doctor_dir / "stderr.log").open("w") as stderr,
    ):
        subprocess.run(
            [
                "taskset",
                "--cpu-list",
                "4",
                str(gmb_env.PYTHON),
                "-B",
                str(gmb_env.ROOT / "environment.py"),
                "_child",
                "doctor",
                "4",
            ],
            cwd=doctor_dir,
            env=gmb_env.child_environment(doctor_dir),
            stdout=stdout,
            stderr=stderr,
            check=True,
            timeout=45,
        )
    doctor = read_json(doctor_dir / "stdout.log")
    for key in ("packages", "python", "source_commit", "builder", "cpu_affinity"):
        if doctor[key] != baseline["runtime_identity"][key]:
            raise RuntimeError(f"GMB environment differs from the baseline: {key}")
    write_json(directory / "preflight.json", report)
    manifest = {
        "schema_version": 1,
        "study": protocol["study"],
        "input_profile": protocol["input_profile"],
        "authorization": {
            "user_authorized": True,
            "text": protocol["main_run_authorization_text"],
            "date": protocol["main_run_authorization_date"],
        },
        "prepared_utc": gmb.utc_now(),
        "repo_commit": gmb.git("rev-parse", "HEAD"),
        "unrelated_worktree_status": gmb.git("status", "--porcelain", "--untracked-files=all"),
        "cpu": 4,
        "timeout_seconds": 180,
        "seeds": [0, 1, 2],
        "jobs": 1,
        "protocol": protocol,
        "engine_identity": report["solver_lock"]["identity"],
        "geo_environment": environment,
        "gmb_environment": doctor,
        "canary": canary,
        "host": gmb.host_snapshot(4),
        "identity_files": implementation_files(),
        "preflight_sha256": sha256(directory / "preflight.json"),
        "legacy_sources": legacy,
        "entries": entries,
        "planned_new_geosolver_runs": 108,
        "planned_new_gmb_runs": 6,
        "reused_gmb_runs": 102,
    }
    write_json(directory / "campaign-manifest.json", manifest)
    gmb_dir = directory / "gmb-aligned"
    gmb_dir.mkdir()
    aligned = [e for e in entries if e["input_origin"] != "official_gmb"]
    write_json(
        gmb_dir / "campaign-manifest.json",
        {
            "schema_version": 1,
            "purpose": "original_statement_aligned_two_case_remeasurement",
            "comparison_manifest_sha256": sha256(directory / "campaign-manifest.json"),
            "cpu": 4,
            "jobs": 1,
            "seeds": [0, 1, 2],
            "timeout_seconds": 180,
            "termination_grace_seconds": 2.0,
            "options": baseline["options"],
            "upstream_defaults": baseline["upstream_defaults"],
            "entries": [
                {
                    "case_id": e["case_id"],
                    "input": str(directory / e["gmbl_input"]),
                    "input_sha256": e["gmbl_sha256"],
                }
                for e in aligned
            ],
        },
    )
    write_json(
        directory / "execution-lock.json",
        {
            "campaign_manifest_sha256": sha256(directory / "campaign-manifest.json"),
            "gmb_manifest_sha256": sha256(gmb_dir / "campaign-manifest.json"),
        },
    )
    print(f"Frozen 36 cases / 108 GeoSolver + 6 new GMB runs: {directory}", flush=True)
    return manifest


def assert_identity(directory, manifest):
    lock = read_json(directory / "execution-lock.json")
    if sha256(directory / "campaign-manifest.json") != lock["campaign_manifest_sha256"]:
        raise RuntimeError("Campaign manifest changed after preparation")
    if sha256(directory / "gmb-aligned/campaign-manifest.json") != lock["gmb_manifest_sha256"]:
        raise RuntimeError("Aligned GMB manifest changed")
    for relative, digest in manifest["identity_files"].items():
        if sha256(REPO / relative) != digest:
            raise RuntimeError(f"Frozen implementation/input changed: {relative}")
    for entry in manifest["entries"]:
        for prefix in ("geo", "gmbl"):
            if sha256(directory / entry[f"{prefix}_input"]) != entry[f"{prefix}_sha256"]:
                raise RuntimeError(f"Frozen input changed: {entry['case_id']}")
    if geo_environment() != manifest["geo_environment"]:
        raise RuntimeError("GeoSolver runtime environment changed")
    gmb_env.source_identity()


def run_geosolver(directory, manifest, entry, seed):
    run_dir = directory / "geosolver/runs" / entry["case_id"] / str(seed)
    run_dir.mkdir(parents=True, exist_ok=False)
    request = {
        "schema_version": 1,
        "synthetic_canary": False,
        "case_id": entry["case_id"],
        "seed": seed,
        "cpu": manifest["cpu"],
        "timeout_seconds": manifest["timeout_seconds"],
        "input": str(directory / entry["geo_input"]),
        "input_sha256": entry["geo_sha256"],
        "venv": manifest["geo_environment"]["prefix"],
        "output_directory": str(run_dir),
        "engine_identity": manifest["engine_identity"],
        "declarations": entry["declarations"],
        "bindings": entry["bindings"],
        "instrument": True,
        "campaign_manifest": str(directory / "campaign-manifest.json"),
        "campaign_manifest_sha256": sha256(directory / "campaign-manifest.json"),
    }
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    variables = set(THREAD_VARIABLES) | set(gmb_env.THREAD_VARIABLES)
    environment.update(dict.fromkeys(variables, "1"))
    environment.update(
        {
            "PYTHONHASHSEED": str(seed),
            "CUDA_VISIBLE_DEVICES": "-1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "VIRTUAL_ENV": sys.prefix,
        }
    )
    command = [
        "taskset",
        "--cpu-list",
        str(manifest["cpu"]),
        sys.executable,
        "-B",
        "-m",
        "benchmarks.gmb_comparison.measurement_worker",
        str(run_dir / "request.json"),
    ]
    before, started_utc = gmb.host_snapshot(manifest["cpu"]), gmb.utc_now()
    origin = time.monotonic()
    request["monotonic_origin"] = origin
    write_json(run_dir / "request.json", request)
    with (run_dir / "stdout.log").open("w") as stdout, (run_dir / "stderr.log").open("w") as stderr:
        process = subprocess.Popen(
            command, cwd=REPO, env=environment, stdout=stdout, stderr=stderr, start_new_session=True
        )
        try:
            resources = gmb.monitor(process, origin, manifest["timeout_seconds"], manifest["cpu"])
        except BaseException:
            gmb_env.terminate_group(process)
            raise
    child_file = run_dir / "child-result.json"
    child = read_json(child_file) if child_file.is_file() else None
    outcome = (
        "cancelled"
        if resources["cancelled"]
        else "resource_violation"
        if resources["affinity_violations"] or resources["descendants_remaining_at_leader_exit"]
        else "timeout"
        if resources["timed_out"]
        else "crash"
        if resources["returncode"] != 0 or child is None
        else child["outcome"]
    )
    record = {
        "schema_version": 1,
        "case_id": entry["case_id"],
        "seed": seed,
        "outcome": outcome,
        "process": resources,
        "input_sha256": entry["geo_sha256"],
        "manifest_sha256": request["campaign_manifest_sha256"],
        "started_utc": started_utc,
        "finished_utc": gmb.utc_now(),
        "command": command,
        "environment": {
            key: environment[key]
            for key in sorted(variables | {"PYTHONHASHSEED", "CUDA_VISIBLE_DEVICES", "VIRTUAL_ENV"})
        },
        "host_before": before,
        "host_after": gmb.host_snapshot(manifest["cpu"]),
    }
    write_json(run_dir / "run.json", record)
    print(
        f"GeoSolver {entry['case_id']} seed={seed}: {outcome}, "
        f"native models={len(child.get('model_files', [])) if child else 0}, "
        f"wall={resources['wall_seconds']:.3f}s",
        flush=True,
    )
    if resources["cancelled"]:
        raise KeyboardInterrupt
    return record


def run_campaign(directory):
    directory = Path(directory).resolve()
    if (directory / "RAW_SHA256SUMS").exists():
        raise RuntimeError("This campaign is already sealed; do not rerun")
    manifest = read_json(directory / "campaign-manifest.json")
    assert_identity(directory, manifest)
    completed = 0
    for method in ("geosolver", "gmb-aligned"):
        native = (
            read_json(directory / "gmb-aligned/campaign-manifest.json")
            if method != "geosolver"
            else manifest
        )
        for seed in manifest["seeds"]:
            for entry in native["entries"]:
                run_dir = directory / method / "runs" / entry["case_id"] / str(seed)
                if (run_dir / "run.json").is_file():
                    completed += 1
                    continue
                if run_dir.exists():
                    raise RuntimeError(
                        f"Incomplete run requires manual review, not retry: {run_dir}"
                    )
                assert_identity(directory, manifest)
                write_json(
                    directory / "progress.json",
                    {
                        "completed_new_runs": completed,
                        "total_new_runs": 114,
                        "method": method,
                        "case_id": entry["case_id"],
                        "seed": seed,
                        "updated_utc": gmb.utc_now(),
                    },
                )
                if method == "geosolver":
                    run_geosolver(directory, manifest, entry, seed)
                else:
                    gmb.run_one(directory / method, native, entry, seed)
                completed += 1
    assert_identity(directory, manifest)
    for legacy in manifest["legacy_sources"]:
        root = Path(legacy["directory"])
        if sha256(root / "SHA256SUMS") != legacy["sha256sums_sha256"]:
            raise RuntimeError("Legacy seal changed")
        check_seal(root)
    write_json(
        directory / "progress.json",
        {
            "completed_new_runs": completed,
            "total_new_runs": 114,
            "phase": "raw_complete",
            "updated_utc": gmb.utc_now(),
        },
    )
    paths = sorted(path for path in directory.rglob("*") if path.is_file())
    with (directory / "RAW_SHA256SUMS").open("x", encoding="utf-8") as handle:
        for path in paths:
            handle.write(f"{sha256(path)}  {path.relative_to(directory)}\n")
    print(f"Sealed raw evidence: {completed} new runs, {len(paths)} files", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--output", required=True, type=Path)
    prepare_parser.add_argument("--canary", required=True, type=Path)
    prepare_parser.add_argument(
        "--legacy",
        required=True,
        action="append",
        type=Path,
        help="Sealed prior GMB measurement directory; repeat once per seed partition",
    )
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--campaign", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare_campaign(args.output, args.canary, args.legacy)
    else:
        run_campaign(args.campaign)


if __name__ == "__main__":
    main()
