"""Linux-only, one-CPU GMB baseline with immutable inputs and raw evidence."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import os
import platform
import re
import signal
import statistics
import subprocess
import sys
import time
from collections import Counter
from contextlib import ExitStack, suppress
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.gmb import environment as env

ROOT = env.ROOT
REPO = ROOT.parent.parent
WORKER = ROOT / "measurement_worker.py"
PROTOCOL = ROOT / "PROTOCOL.md"
PAPER = "https://arxiv.org/html/2012.02590v2"
OMITTED = {
    "IMO_2002_P6": (
        "任意個数の単位円",
        "https://www.imo-official.org/problems/2002/eng.pdf",
    ),
    "IMO_2006_P6": (
        "一般の凸多角形",
        "https://www.imo-register.org.uk/2006-report.html",
    ),
    "IMO_2011_P2": (
        "有限点集合の風車問題",
        "https://www.imo-official.org/problems/2011/eng.pdf",
    ),
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    temporary = Path(path).with_suffix(Path(path).suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def git(*arguments):
    return subprocess.check_output(["git", "-C", str(REPO), *arguments], text=True).strip()


def defaults():
    tree = ast.parse((env.SOURCE / "src/util.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "DEFAULTS" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError("upstream DEFAULTS not found")


def identity_files():
    files = [
        ROOT / name
        for name in (
            "environment.py",
            "campaign.py",
            "measurement_worker.py",
            "requirements.lock",
            "PROTOCOL.md",
        )
    ]
    files.extend(
        REPO / name
        for name in (
            "pyproject.toml",
            "uv.lock",
            "benchmarks/cases.jsonl",
            "src/geosolver/engine-lock.json",
        )
        if (REPO / name).is_file()
    )
    return {str(path.relative_to(REPO)): sha256(path) for path in files}


def host_snapshot(cpu):
    import psutil

    topology = Path(f"/sys/devices/system/cpu/cpu{cpu}")

    def optional(path):
        return path.read_text().strip() if path.exists() else None

    return {
        "timestamp_utc": utc_now(),
        "platform": platform.platform(),
        "controller_python": platform.python_version(),
        "controller_psutil": psutil.__version__,
        "cpu": cpu,
        "cpu_model": next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            None,
        ),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cpus": psutil.cpu_count(),
        "thread_siblings": optional(topology / "topology/thread_siblings_list"),
        "physical_core_id": optional(topology / "topology/core_id"),
        "governor": optional(topology / "cpufreq/scaling_governor"),
        "frequency_khz": optional(topology / "cpufreq/scaling_cur_freq"),
        "boost": optional(Path("/sys/devices/system/cpu/cpufreq/boost")),
        "controller_affinity": sorted(os.sched_getaffinity(0)),
        "load_average": list(os.getloadavg()),
        "available_memory_bytes": psutil.virtual_memory().available,
        "per_cpu_times": [dict(item._asdict()) for item in psutil.cpu_times(percpu=True)],
        "exclusive_core": False,
    }


def inventory():
    inputs = sorted((env.SOURCE / "problems/IMO").glob("*.smt2"))
    if len(inputs) != 36 or len({item.stem for item in inputs}) != 36:
        raise RuntimeError("expected exactly 36 distinct public IMO inputs")
    entries = [
        {
            "case_id": path.stem,
            "availability": "public_input",
            "upstream_path": str(path.relative_to(env.SOURCE)),
            "input_sha256": sha256(path),
            "input_bytes": path.stat().st_size,
            "declared_eval_count": len(
                re.findall(r"\(\s*eval\b", re.sub(r";[^\n]*", "", path.read_text(encoding="utf-8")))
            ),
            "input": f"inputs/{path.name}",
        }
        for path in inputs
    ]
    entries.extend(
        {
            "case_id": case_id,
            "availability": "unsupported",
            "reason": reason,
            "problem_source": source,
            "identification": "reconstructed_from_public_inventory_and_problem_statements",
            "input": None,
            "input_sha256": None,
        }
        for case_id, (reason, source) in OMITTED.items()
    )
    if len({item["case_id"] for item in entries}) != 39:
        raise RuntimeError("39-case inventory has duplicate IDs")
    return sorted(entries, key=lambda item: item["case_id"])


def prepare(directory, cpu, timeout, *, smoke=False):
    env.source_identity()
    cpu = env.choose_cpu(cpu)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    dirty = git("status", "--porcelain", "--untracked-files=all")
    if dirty and not smoke:
        raise RuntimeError("commit the protocol/harness before preparing the official campaign")
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "inputs").mkdir()
    upstream_defaults = defaults()
    options = dict(upstream_defaults, verbosity=-1, plot_freq=-1, loss_freq=-1, losses_freq=-1)
    if smoke:
        entries = [
            {
                "case_id": case_id,
                "availability": "public_input",
                "input": f"inputs/{case_id}.smt2",
                "input_sha256": sha256(ROOT / "smoke.smt2"),
                "instrument": instrument,
            }
            for case_id, instrument in [("synthetic_recorded", True), ("synthetic_plain", False)]
        ]
        for item in entries:
            (directory / item["input"]).write_bytes((ROOT / "smoke.smt2").read_bytes())
    else:
        entries = inventory()
        for item in entries:
            if item["input"]:
                (directory / item["input"]).write_bytes(
                    (env.SOURCE / item["upstream_path"]).read_bytes()
                )
    # Keep the environment check outside timed problem runs, with its complete output.
    with ExitStack() as stack:
        stdout = stack.enter_context((directory / "doctor.stdout.log").open("w"))
        stderr = stack.enter_context((directory / "doctor.stderr.log").open("w"))
        subprocess.run(
            [
                "taskset",
                "--cpu-list",
                str(cpu),
                str(env.PYTHON),
                "-B",
                str(ROOT / "environment.py"),
                "_child",
                "doctor",
                str(cpu),
            ],
            cwd=directory,
            env=env.child_environment(directory),
            stdout=stdout,
            stderr=stderr,
            check=True,
            timeout=120,
        )
    doctor = read_json(directory / "doctor.stdout.log")
    if doctor["cpu_affinity"] != [cpu] or doctor["source_commit"] != env.COMMIT:
        raise RuntimeError("doctor identity mismatch")
    manifest = {
        "schema_version": 1,
        "purpose": "synthetic_harness_check" if smoke else "gmb_imo39_single_seed_baseline",
        "prepared_utc": utc_now(),
        "paper": PAPER,
        "repo_commit": git("rev-parse", "HEAD"),
        "repo_dirty": dirty,
        "upstream_url": env.UPSTREAM,
        "upstream_commit": env.COMMIT,
        "source": str(env.SOURCE),
        "source_files": {
            str(path.relative_to(env.SOURCE)): sha256(path)
            for path in sorted((env.SOURCE / "src").rglob("*.py"))
        },
        "identity_files": identity_files(),
        "doctor_sha256": sha256(directory / "doctor.stdout.log"),
        "runtime_identity": doctor,
        "cpu": cpu,
        "jobs": 1,
        "seeds": [0],
        "timeout_seconds": timeout,
        "termination_grace_seconds": 2.0,
        "upstream_defaults": upstream_defaults,
        "options": options,
        "host": host_snapshot(cpu),
        "entries": entries,
        "independent_geometry_validation": "not_performed",
    }
    write_json(directory / "campaign-manifest.json", manifest)
    (directory / "PROTOCOL.md").write_bytes(PROTOCOL.read_bytes())
    (directory / "UPSTREAM-LICENSE").write_bytes((env.SOURCE / "LICENSE").read_bytes())
    (directory / "requirements.lock").write_bytes(env.LOCK.read_bytes())
    print(f"prepared {len(entries)} cases: {directory}", flush=True)
    return manifest


def assert_identity(directory, manifest):
    env.source_identity()
    for name, expected in manifest["identity_files"].items():
        if sha256(REPO / name) != expected:
            raise RuntimeError(f"changed implementation/config: {name}")
    for name, expected in manifest["source_files"].items():
        if sha256(env.SOURCE / name) != expected:
            raise RuntimeError(f"changed upstream source: {name}")
    for entry in manifest["entries"]:
        if entry["input"] and sha256(directory / entry["input"]) != entry["input_sha256"]:
            raise RuntimeError(f"changed input: {entry['case_id']}")


def monitor(process, started, timeout, cpu, grace=2.0):
    """Own and reap exactly this process group; wait4 preserves per-run resource usage."""
    timed_out = False
    cancelled = False
    term_time = None
    violations = set()
    observed_masks = set()
    max_threads = 0
    samples = 0
    next_sample = started + 0.25
    while True:
        try:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                process.returncode = os.waitstatus_to_exitcode(status)
                # Completion must be observed within the limit, not merely before the next signal.
                timed_out = timed_out or time.monotonic() - started > timeout
                break
            now = time.monotonic()
            if now >= next_sample:
                tasks = Path(f"/proc/{process.pid}/task")
                with suppress(FileNotFoundError, ProcessLookupError):
                    tids = list(tasks.iterdir())
                    max_threads = max(max_threads, len(tids))
                    for tid in tids:
                        with suppress(ProcessLookupError):
                            mask = tuple(sorted(os.sched_getaffinity(int(tid.name))))
                            observed_masks.add(mask)
                            if mask != (cpu,):
                                violations.add(mask)
                    samples += 1
                next_sample = now + 0.5
            if now - started >= timeout and term_time is None:
                timed_out = True
                term_time = now
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
            if term_time is not None and now - term_time >= grace:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
            time.sleep(0.025)
        except KeyboardInterrupt:
            cancelled = True
            if term_time is None:
                term_time = time.monotonic()
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
    # Reap the leader first, then remove any unexpectedly surviving owned descendants.
    descendants_remained = False
    with suppress(ProcessLookupError):
        os.killpg(process.pid, 0)
        descendants_remained = True
        os.killpg(process.pid, signal.SIGKILL)
    return {
        "pid": process.pid,
        "returncode": process.returncode,
        "timed_out": timed_out,
        "cancelled": cancelled,
        "wall_seconds": time.monotonic() - started,
        "timeout_signal_seconds": term_time - started if term_time is not None else None,
        "cpu_user_seconds": usage.ru_utime,
        "cpu_system_seconds": usage.ru_stime,
        "cpu_seconds": usage.ru_utime + usage.ru_stime,
        "peak_rss_bytes": usage.ru_maxrss * 1024,
        "affinity_masks_observed": [list(mask) for mask in sorted(observed_masks)],
        "affinity_violations": [list(mask) for mask in sorted(violations)],
        "affinity_samples": samples,
        "max_os_threads": max_threads,
        "descendants_remaining_at_leader_exit": descendants_remained,
    }


def outcome(process, child):
    if process["cancelled"]:
        return "cancelled"
    if process["affinity_violations"] or process["descendants_remaining_at_leader_exit"]:
        return "resource_violation"
    if process["timed_out"]:
        return "timeout"
    if child and child.get("outcome") == "error":
        return "error"
    if process["returncode"] != 0 or child is None:
        return "crash"
    if child["outcome"] == "model_returned" and child["models_returned"] > 0:
        return "model_returned"
    if child["outcome"] == "no_model" and child["models_returned"] == 0:
        return "no_model"
    return "invalid_artifact"


def run_one(directory, manifest, entry, seed):
    run_dir = directory / "runs" / entry["case_id"] / str(seed)
    run_dir.mkdir(parents=True, exist_ok=False)
    before = host_snapshot(manifest["cpu"])
    request = {
        "schema_version": 1,
        "case_id": entry["case_id"],
        "seed": seed,
        "cpu": manifest["cpu"],
        "source": str(env.SOURCE),
        "venv": str(env.PYTHON.parent.parent),
        "python_version": env.PYTHON_VERSION,
        "input": str(directory / entry["input"]),
        "input_sha256": entry["input_sha256"],
        "upstream_defaults": manifest["upstream_defaults"],
        "options": manifest["options"],
        "instrument": entry.get("instrument", True),
    }
    child_env = env.child_environment(run_dir)
    child_env["PYTHONHASHSEED"] = str(seed)
    arguments = [
        "taskset",
        "--cpu-list",
        str(manifest["cpu"]),
        str(env.PYTHON),
        "-B",
        str(WORKER),
        str(run_dir / "request.json"),
    ]
    # The small request serialization below is deliberately included in cold-start timing.
    started_utc = utc_now()
    started = time.monotonic()
    request["monotonic_origin"] = started
    write_json(run_dir / "request.json", request)
    with ExitStack() as stack:
        stdout = stack.enter_context((run_dir / "stdout.log").open("w"))
        stderr = stack.enter_context((run_dir / "stderr.log").open("w"))
        process = subprocess.Popen(
            arguments,
            cwd=run_dir,
            env=child_env,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            resource_record = monitor(
                process,
                started,
                manifest["timeout_seconds"],
                manifest["cpu"],
                manifest["termination_grace_seconds"],
            )
        except BaseException:
            env.terminate_group(process)
            raise
    child_path = run_dir / "child-result.json"
    child = read_json(child_path) if child_path.is_file() else None
    record = {
        "schema_version": 1,
        "case_id": entry["case_id"],
        "seed": seed,
        "started_utc": started_utc,
        "finished_utc": utc_now(),
        "outcome": outcome(resource_record, child),
        "process": resource_record,
        "command": arguments,
        "environment": {
            key: child_env[key]
            for key in (
                *env.THREAD_VARIABLES,
                "CUDA_VISIBLE_DEVICES",
                "PYTHONHASHSEED",
                "MPLBACKEND",
            )
        },
        "host_before": before,
        "host_after": host_snapshot(manifest["cpu"]),
        "input_sha256": entry["input_sha256"],
        "manifest_sha256": sha256(directory / "campaign-manifest.json"),
    }
    write_json(run_dir / "run.json", record)
    print(
        f"{entry['case_id']} seed={seed}: {record['outcome']} "
        f"wall={resource_record['wall_seconds']:.3f}s "
        f"cpu={resource_record['cpu_seconds']:.3f}s",
        flush=True,
    )
    if resource_record["cancelled"]:
        raise KeyboardInterrupt
    return record


def run_campaign(directory):
    manifest = read_json(directory / "campaign-manifest.json")
    assert_identity(directory, manifest)
    if (directory / "SHA256SUMS").exists():
        raise RuntimeError("sealed campaign cannot be run again; use a new directory")
    for entry in manifest["entries"]:
        if not entry["input"]:
            continue
        for seed in manifest["seeds"]:
            # Resume only terminal runs; never silently repeat an incomplete/failed run.
            run_dir = directory / "runs" / entry["case_id"] / str(seed)
            if (run_dir / "run.json").exists():
                continue
            if run_dir.exists():
                raise RuntimeError(
                    f"incomplete run requires review, not automatic retry: {run_dir}"
                )
            run_one(directory, manifest, entry, seed)
    assert_identity(directory, manifest)


def event_summary(events):
    result = {"last_event": events[-1]["event"] if events else None}
    for name in ("imports", "preprocess", "initializations", "build", "solve", "train"):
        starts = []
        seconds = 0.0
        count = 0
        for event in events:
            if event["event"] == name + "_start":
                starts.append(event["elapsed_seconds"])
            elif event["event"] in (name + "_end", name + "_error") and starts:
                seconds += event["elapsed_seconds"] - starts.pop()
                count += 1
        result[name + "_completed_seconds"] = seconds if count else None
        result[name + "_completed_calls"] = count
        result[name + "_incomplete_calls"] = len(starts)
    result["train_errors"] = sum(event["event"] == "train_error" for event in events)
    materialized = [
        event["materialized_seconds"] for event in events if event["event"] == "model_materialized"
    ]
    result["first_model_seconds"] = min(materialized) if materialized else None
    return result


def rows_from_raw(directory, manifest):
    rows = []
    for entry in manifest["entries"]:
        for seed in manifest["seeds"]:
            row = dict(case_id=entry["case_id"], seed=seed, availability=entry["availability"])
            row["declared_eval_count"] = entry.get("declared_eval_count")
            if not entry["input"]:
                row.update(outcome="unsupported", reason=entry["reason"])
            else:
                run_dir = directory / "runs" / entry["case_id"] / str(seed)
                run = read_json(run_dir / "run.json")
                child = (
                    read_json(run_dir / "child-result.json")
                    if (run_dir / "child-result.json").exists()
                    else {}
                )
                events = (
                    [
                        json.loads(line)
                        for line in (run_dir / "events.jsonl").read_text().splitlines()
                        if line.strip()
                    ]
                    if (run_dir / "events.jsonl").exists()
                    else []
                )
                row.update(outcome=run["outcome"], **event_summary(events))
                row.update(
                    {
                        key: run["process"][key]
                        for key in (
                            "wall_seconds",
                            "cpu_seconds",
                            "peak_rss_bytes",
                            "returncode",
                            "timed_out",
                            "affinity_violations",
                            "max_os_threads",
                        )
                    }
                )
                goals = child.get("goal_diagnostics", [])
                row["goals_total"] = sum(item["total"] for item in goals) if goals else None
                row["goals_passed"] = sum(item["passed"] for item in goals) if goals else None
                row["all_goals_passed"] = (
                    all(item["all_passed"] for item in goals) if row["goals_total"] else None
                )
                row["models_returned"] = child.get("models_returned")
                row["failure_stage"] = child.get("failure_stage")
                row["artifact"] = str(run_dir.relative_to(directory))
            rows.append(row)
    return rows


def distribution(values):
    return {
        "n": len(values),
        "mean": statistics.mean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "sum": sum(values),
    }


def summarize(directory):
    manifest = read_json(directory / "campaign-manifest.json")
    rows = rows_from_raw(directory, manifest)
    ran = [row for row in rows if row["outcome"] != "unsupported"]
    successful = [row for row in ran if row["outcome"] == "model_returned"]
    goal_rows = [row for row in successful if row["all_goals_passed"] is not None]
    summary = {
        "schema_version": 1,
        "manifest_sha256": sha256(directory / "campaign-manifest.json"),
        "outcome_counts": dict(sorted(Counter(row["outcome"] for row in rows).items())),
        "inventory_rows": len(rows),
        "executed_runs": len(ran),
        "model_returned_runs": len(successful),
        "model_return_rate_among_executable": len(successful) / len(ran) if ran else None,
        "model_return_rate_including_unsupported": len(successful) / len(rows) if rows else None,
        "goal_evaluable_returned_runs": len(goal_rows),
        "all_goals_passed_runs": sum(row["all_goals_passed"] for row in goal_rows),
        "independent_geometry_validation": "not_performed",
        "wall_seconds_all_including_censored": distribution([row["wall_seconds"] for row in ran]),
        "wall_seconds_model_returned": distribution([row["wall_seconds"] for row in successful]),
        "cpu_seconds_all": distribution([row["cpu_seconds"] for row in ran]),
        "peak_rss_bytes": distribution([row["peak_rss_bytes"] for row in ran]),
        "affinity_violation_runs": sum(bool(row["affinity_violations"]) for row in ran),
        "train_error_count": sum(row["train_errors"] for row in ran),
        "caveat": "single seed; upstream model acceptance only; no GeoSolver comparison",
    }
    outputs = {
        "summary.json": json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        "case-results.jsonl": "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    }
    for name, value in outputs.items():
        path = directory / name
        if path.exists() and path.read_text(encoding="utf-8") != value:
            raise RuntimeError(f"refusing to overwrite different summary: {name}")
        if not path.exists():
            path.write_text(value, encoding="utf-8")
    csv_path = directory / "case-results.csv"
    if not csv_path.exists():
        keys = sorted({key for row in rows for key in row})
        keys = [
            "case_id",
            "seed",
            "outcome",
            *[key for key in keys if key not in {"case_id", "seed", "outcome"}],
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def seal(directory):
    manifest = read_json(directory / "campaign-manifest.json")
    assert_identity(directory, manifest)
    summarize(directory)
    if (directory / "SHA256SUMS").exists():
        raise RuntimeError("already sealed; use verify")
    paths = sorted(path for path in directory.rglob("*") if path.is_file())
    with (directory / "SHA256SUMS").open("x", encoding="utf-8") as handle:
        for path in paths:
            handle.write(f"{sha256(path)}  {path.relative_to(directory)}\n")
    print(f"sealed {len(paths)} files; SHA256SUMS sha256={sha256(directory / 'SHA256SUMS')}")


def verify(directory):
    expected_paths = set()
    for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        path = directory / name
        if not path.resolve().is_relative_to(directory.resolve()):
            raise RuntimeError("unsafe checksum path")
        if sha256(path) != digest:
            raise RuntimeError(f"checksum mismatch: {name}")
        expected_paths.add(name)
    actual_paths = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if actual_paths != expected_paths:
        raise RuntimeError("unlisted/missing artifact files")
    summarize(directory)
    print(f"verified {len(expected_paths)} files and deterministic JSON summaries")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["prepare", "run", "summarize", "seal", "verify", "smoke"]
    )
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cpu", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if sys.platform != "linux":
        parser.error("this protocol is Linux-only")
    if args.command in {"prepare", "smoke"}:
        prepare(directory, args.cpu, args.timeout, smoke=args.command == "smoke")
        if args.command == "smoke":
            run_campaign(directory)
            recorded = read_json(directory / "runs/synthetic_recorded/0/models/000.json")
            plain = read_json(directory / "runs/synthetic_plain/0/models/000.json")
            if recorded != plain:
                raise RuntimeError("measurement hooks changed the synthetic model")
            write_json(
                directory / "smoke-check.json", {"identical_models": True, "benchmark": False}
            )
            seal(directory)
    else:
        {"run": run_campaign, "summarize": summarize, "seal": seal, "verify": verify}[args.command](
            directory
        )


if __name__ == "__main__":
    main()
