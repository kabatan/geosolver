"""Execute the locked Q37 jobs without changing solver, selection or grading.

Run `prepare`, then `supervise` in a background exec session. Each job imports
the frozen research runner in a fresh process. Only its budget constant and a
size-checking wrapper around its final JSON writer are set. No worker hooks.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import threading
import time
import traceback

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
EXEC = BASE / "execution"
LIMIT = 4_900_000
COMMIT = "58e399315f259699e99cc1b190aa46c78d573e5a"
LOCK_SHA = "0e4729ecb1a500bd46c2e01127f016ae23601e6b1f45d52af96ce142e88c2cbc"
PYTHON = "/home/kabatan/work/solver/.venv/bin/python"
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
import psutil
from benchmarks import research_runner as rr


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, timeout=30)


def payload(value):
    result = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
    if len(result) >= LIMIT:
        raise ValueError(f"JSON exceeds locked {LIMIT}-byte ceiling: {len(result)} bytes")
    return result


def save(path, value, *, new=False):
    data = payload(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if new and path.exists():
        raise FileExistsError(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".q37-", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def clean_env():
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith(("PYTHON", "GEOSOLVER", "Q30", "Q36", "Q37", "LD_")):
            del environment[key]
    environment.update(PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
                       PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    environment.update(rr.THREAD_ENVIRONMENT)
    return environment


def jobs():
    rows = list(csv.DictReader((BASE / "jobs.csv").open()))
    for row in rows:
        for key in ("lane", "lane_order", "seed", "time_limit_seconds", "within_triplet", "cores", "outer_watchdog_seconds"):
            row[key] = int(row[key])
    return rows


def key(job):
    return f"lane{job['lane']}-{job['lane_order']:03d}"


def raw_path(job):
    return BASE / job["campaign_relative"] / "runs" / job["id"] / f"{job['seed']}.json"


def receipt_path(job, suffix=""):
    return EXEC / "receipts" / f"{key(job)}{suffix}.json"


def verify():
    lock_path = BASE / "prediction.lock.json"
    if sha(lock_path) != LOCK_SHA or lock_path.read_bytes() != git("show", f"{COMMIT}:jssa/difficulty/budget-monotonicity/prediction.lock.json"):
        raise RuntimeError("prediction lock differs from the committed bytes")
    lock = read(lock_path)
    verified = {}
    for folder, entries in ((BASE, lock["artifacts"]), (ROOT, read(BASE / "source-manifest.json")["sources"])):
        for rel, expected in entries.items():
            path = folder / rel
            actual = {"sha256": sha(path), "bytes": path.stat().st_size}
            if actual != expected:
                raise RuntimeError(f"locked source changed: {path}: {actual}")
            verified[str(path.relative_to(ROOT))] = actual
    if git("diff", lock["frozen_solver_commit"], "--", "src", "benchmarks/research_runner.py", "uv.lock").strip():
        raise RuntimeError("frozen src, runner or dependency lock changed")
    if git("ls-files", "--others", "--exclude-standard", "src").strip():
        raise RuntimeError("untracked src file")
    fingerprint = rr.runtime_fingerprint()
    from geosolver.runtime.integrity import verify_engine_lock
    if fingerprint["issues"] or fingerprint["source_hash"] != lock["product_source_hash"] or not verify_engine_lock()[0]:
        raise RuntimeError(f"runtime identity mismatch: {fingerprint}")
    if "sitecustomize" in sys.modules:
        raise RuntimeError("unexpected sitecustomize")
    rows = jobs()
    if len(rows) != 360 or len({(r['id'], r['seed'], r['time_limit_seconds']) for r in rows}) != 360:
        raise RuntimeError("invalid locked job table")
    selected = list(csv.DictReader((BASE / "selection.csv").open()))
    records = {r.identifier: r for r in rr._load_cases()}
    for row in selected:
        record = records[row["id"]]
        if not record.runnable or sha(record.dsl_path) != row["dsl_sha256"]:
            raise RuntimeError(f"input changed: {row['id']}")
        if json.loads(record.dsl_path.read_text()) != record.dsl:
            raise RuntimeError(f"embedded DSL changed: {row['id']}")
        if hashlib.sha256(rr._canonical_json(list(record.references)).encode()).hexdigest() != row["reference_sha256"]:
            raise RuntimeError(f"reference changed: {row['id']}")
    return {"verified_utc": now(), "prediction_commit": COMMIT,
            "prediction_commit_time": git("show", "-s", "--format=%cI", COMMIT).decode().strip(),
            "prediction_lock_sha256": LOCK_SHA, "locked_file_count": len(lock["artifacts"]),
            "source_manifest_file_count": len(read(BASE / "source-manifest.json")["sources"]),
            "verified_files": verified, "frozen_solver_commit": lock["frozen_solver_commit"],
            "runtime_fingerprint": fingerprint, "python": sys.executable, "python_version": sys.version,
            "src_git_tree": git("rev-parse", lock["frozen_solver_commit"] + ":src").decode().strip(),
            "remote_tracking_refs": git("for-each-ref", "--contains", COMMIT, "--format=%(refname) %(objectname)", "refs/remotes").decode().splitlines(),
            "push_evidence": "User reports push near 2026-10-23T16:18:35Z; local tracking reference corroborates commit containment, not server time.",
            "authorization": "Explicit user stage-2 authorization, 180/360/900 seconds, 3 locked seeds, all 360 jobs, maximum 4 jobs, 1 fixed core each.",
            "file_size_limit_bytes": LIMIT, "storage_guard": "Check full runner JSON size before its unchanged writer; all descendants inherit RLIMIT_FSIZE. No result compaction or worker patch.",
            "adapter_sha256": sha(__file__), "environment": clean_env_subset()}


def clean_env_subset():
    environment = clean_env()
    return {k: environment[k] for k in ("PYTHONPATH", "PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE", *rr.THREAD_ENVIRONMENT)}


def choose_cpus():
    eligible = sorted(os.sched_getaffinity(0))
    core_map = {}
    for cpu in eligible:
        topology = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        physical = ((topology / "physical_package_id").read_text().strip(), (topology / "core_id").read_text().strip())
        core_map.setdefault(physical, []).append(cpu)
    samples = [{"utc": now(), "load_average": os.getloadavg(), "utilization_percent": psutil.cpu_percent(interval=3, percpu=True)} for _ in range(3)]
    available = []
    affinity_errors = []
    for siblings in core_map.values():
        cpu = min(siblings)
        try:
            os.sched_setaffinity(0, {cpu})
            if os.sched_getaffinity(0) != {cpu}:
                raise RuntimeError("affinity readback mismatch")
            available.append(cpu)
        except OSError as error:
            affinity_errors.append({"cpu": cpu, "error": str(error)})
        finally:
            os.sched_setaffinity(0, eligible)
    if len(available) < 4:
        save(EXEC / f"cpu-wait-{time.time_ns()}.json", {"utc": now(), "samples": samples, "available": available})
        raise RuntimeError("fewer than four pinnable independent physical cores; wait, do not launch")
    sibling_map = {min(siblings): siblings for siblings in core_map.values()}
    scores = {cpu: sum(sample["utilization_percent"][sibling]
                       for sample in samples for sibling in sibling_map[cpu]) / len(samples)
              for cpu in available}
    chosen = sorted(sorted(available, key=lambda cpu: (scores[cpu], cpu))[:4])
    return {"selection_utc": now(), "lane_cpus": chosen,
            "physical_cores": [{"socket": p[0], "core": p[1], "siblings": cpus} for p, cpus in core_map.items()],
            "selection_rule": "Among affinity-verified independent physical cores, choose four lowest combined SMT utilization means over three 3-second samples; assign these representatives to lanes in ascending CPU order.",
            "combined_sibling_utilization_percent": scores, "affinity_probe_errors": affinity_errors,
            "availability_interpretation": "The locked plan requires available independent cores and enforced affinity, not an exclusive host reservation. Early idle-core checks were conservative operational checks, not changes to problem selection or execution order.",
            "samples": samples, "exclusive_host_reservation": False,
            "limitation": "Affinity is enforceable; other host jobs are not visible in this PID namespace and may later share these cores. Host load, per-core utilization and CPU/wall ratio must accompany timing claims."}


def prepare():
    if (EXEC / "preflight.json").exists():
        raise RuntimeError("preflight already exists; do not overwrite")
    preflight = verify()
    allocation = choose_cpus()
    records = {r.identifier: r for r in rr._load_cases()}
    ids = read(BASE / "prediction.lock.json")["selected_problem_ids"]
    campaigns = sorted({(r["time_limit_seconds"], r["seed"], r["campaign_relative"]) for r in jobs()})
    manifests = {}
    for budget, seed, relative in campaigns:
        rr.CANONICAL_TIME_LIMIT_SECONDS = budget
        manifest = rr._manifest([records[cid] for cid in ids], [seed])
        manifest["execution_layout"] = {"worker_count": 4, "cores_per_job": 1, "lane_cpus": allocation["lane_cpus"], "job_table_sha256": sha(BASE / "jobs.csv")}
        path = BASE / relative / "campaign-manifest.json"
        save(path, manifest, new=True)
        manifests[relative] = sha(path)
    preflight.update(cpu_allocation=allocation, campaign_manifest_sha256=manifests,
                     preparation_completed_utc=now(), executed_solver_runs=0)
    save(EXEC / "preflight.json", preflight, new=True)
    print(json.dumps({"prepared": True, "lane_cpus": allocation["lane_cpus"], "utc": now(), "solver_runs": 0}), flush=True)


def minimal_raw(job, cpu, issue, process=None):
    manifest = read(BASE / job["campaign_relative"] / "campaign-manifest.json")
    case = next(row for row in manifest["cases"] if row["id"] == job["id"])
    return {"schema_version": 2, "case_id": job["id"], "seed": job["seed"],
            "problem_hash": case["problem_hash"], "source_hash": manifest["source_hash"],
            "dependency_lock_hash": manifest["dependency_lock_hash"],
            "config": {k: manifest["config"][k] for k in ("time_limit_seconds", "cores", "thread_environment")},
            "execution_contract_issues": [issue], "solver_result": None,
            "process": process or {"assigned_cpu": cpu, "actual_affinity": None, "returncode": None, "timed_out": False, "elapsed_seconds": None, "stdout": "", "stderr": ""}}


def run_job(lane, order):
    job = next(r for r in jobs() if r["lane"] == lane and r["lane_order"] == order)
    preflight = read(EXEC / "preflight.json")
    cpu = preflight["cpu_allocation"]["lane_cpus"][lane]
    if preflight["adapter_sha256"] != sha(__file__):
        raise RuntimeError("adapter changed after preparation")
    if receipt_path(job, "-start").exists() or raw_path(job).exists():
        raise RuntimeError("already started; retries are prohibited")
    os.sched_setaffinity(0, {cpu})
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
    verify()
    rr.CANONICAL_TIME_LIMIT_SECONDS = job["time_limit_seconds"]
    record = next(r for r in rr._load_cases() if r.identifier == job["id"])
    start = {"job": job, "start_utc": now(), "pid": os.getpid(), "cpu": cpu,
             "affinity": sorted(os.sched_getaffinity(0)), "load_average": os.getloadavg(),
             "adapter_sha256": sha(__file__), "prediction_lock_sha256": LOCK_SHA}
    save(receipt_path(job, "-start"), start, new=True)
    started = time.monotonic()
    stop = threading.Event()
    processes, samples = {}, []

    def observe():
        while not stop.is_set():
            samples.append({"elapsed": time.monotonic() - started, "load_average": os.getloadavg()})
            try:
                children = [psutil.Process(), *psutil.Process().children(recursive=True)]
            except psutil.Error:
                children = []
            for process in children:
                try:
                    times = process.cpu_times()
                    prior = processes.setdefault(str(process.pid), {"pid": process.pid, "name": process.name(), "first_seen": time.monotonic() - started, "affinities": []})
                    affinity = process.cpu_affinity()
                    if affinity not in prior["affinities"]:
                        prior["affinities"].append(affinity)
                    prior.update(last_seen=time.monotonic() - started, cpu_seconds=times.user + times.system,
                                 peak_sampled_rss_bytes=max(prior.get("peak_sampled_rss_bytes", 0), process.memory_info().rss))
                except psutil.Error:
                    pass
            stop.wait(2)

    monitor = threading.Thread(target=observe, daemon=True)
    monitor.start()
    storage = {}
    original_write = rr._atomic_json

    def guarded_write(path, value):
        try:
            payload(value)
        except Exception:
            storage["error"] = traceback.format_exc()
            storage["process"] = {k: v for k, v in value.get("process", {}).items() if k not in ("stdout", "stderr")}
            raise
        original_write(path, value)

    rr._atomic_json = guarded_write
    error = None
    try:
        rr._run_one(record, job["seed"], BASE / job["campaign_relative"], cpu)
    except BaseException:
        error = traceback.format_exc()
        if not raw_path(job).exists():
            save(raw_path(job), minimal_raw(job, cpu, "adapter_or_storage_error", storage.get("process")), new=True)
    finally:
        stop.set()
        monitor.join(timeout=5)
    raw = read(raw_path(job))
    outcome = rr.read_run_outcome(raw)
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {**start, "end_utc": now(), "adapter_elapsed_seconds": time.monotonic() - started,
               "load_average_end": os.getloadavg(), "load_samples": samples,
               "observed_processes": list(processes.values()),
               "affinity_violations": [p for p in processes.values() if p["affinities"] != [[cpu]]],
               "children_cpu_seconds": usage.ru_utime + usage.ru_stime,
               "raw_path": str(raw_path(job).relative_to(ROOT)), "raw_sha256": sha(raw_path(job)),
               "raw_bytes": raw_path(job).stat().st_size, "outcome": outcome,
               "adapter_error": error, "storage_error": storage.get("error"),
               "mechanism_outcome": "known" if outcome["normal_completion"] else "unknown"}
    save(receipt_path(job), receipt, new=True)
    print(json.dumps({"job": key(job), "id": job["id"], "budget": job["time_limit_seconds"], "status": outcome["status"], "utc": now()}), flush=True)


def assess(budget, seed):
    verify()
    rr.CANONICAL_TIME_LIMIT_SECONDS = budget
    campaign = BASE / f"campaign/t{budget}/s{seed}"
    rr.assess_campaign(campaign, cases_path=ROOT / "benchmarks/cases.jsonl")
    rows = [json.loads(line) for line in (campaign / "assessment.jsonl").read_text().splitlines()]
    save(EXEC / "grading" / f"t{budget}-s{seed}.json", {"utc": now(), "budget": budget, "seed": seed, "rows": len(rows), "matched": sum(r["matched"] is True for r in rows), "assessment_sha256": sha(campaign / "assessment.jsonl")}, new=True)


def supervise():
    EXEC.mkdir(exist_ok=True)
    lockstream = (EXEC / "supervisor.lock").open("a")
    fcntl.flock(lockstream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
    verify()
    preflight = read(EXEC / "preflight.json")
    if sha(__file__) != preflight["adapter_sha256"]:
        raise RuntimeError("adapter changed")
    for rel, expected in preflight["campaign_manifest_sha256"].items():
        if sha(BASE / rel / "campaign-manifest.json") != expected:
            raise RuntimeError("prepared campaign manifest changed")
    if not (EXEC / "execution-start.json").exists():
        save(EXEC / "execution-start.json", {"execution_start_utc": now(), "prediction_lock_sha256": LOCK_SHA,
             "preflight_sha256": sha(EXEC / "preflight.json"), "lane_cpus": preflight["cpu_allocation"]["lane_cpus"],
             "load_average": os.getloadavg(), "pid": os.getpid(), "authorization_observed": True}, new=True)
    all_jobs = jobs()
    queues = [[r for r in all_jobs if r["lane"] == lane and not receipt_path(r).exists()] for lane in range(4)]
    if any(receipt_path(r, "-start").exists() or raw_path(r).exists() for queue in queues for r in queue):
        raise RuntimeError("started job has no completion receipt; inspect and record unknown without retry before resuming")
    active = {}
    environment = clean_env()
    last_load = 0.0
    loadpath = EXEC / "load.jsonl"
    while any(queues) or active:
        for lane in range(4):
            if lane in active and active[lane][0].poll() is not None:
                process, job, log = active.pop(lane)
                log.close()
                if not receipt_path(job).exists():
                    save(EXEC / "supervisor-error.json", {"utc": now(), "job": job, "returncode": process.returncode, "reason": "child exited without completion receipt; no retry"})
                    # Other already-started jobs may finish; do not launch further work.
                    for other, _, _ in active.values():
                        other.wait()
                    raise RuntimeError("job adapter failed; inspect supervisor-error.json")
            if lane not in active and queues[lane]:
                job = queues[lane].pop(0)
                logpath = EXEC / "logs" / f"{key(job)}.log"
                logpath.parent.mkdir(exist_ok=True)
                log = logpath.open("xb")
                tempdir = EXEC / "tmp" / key(job)
                tempdir.mkdir(parents=True, exist_ok=False)
                jobenv = {**environment, "TMPDIR": str(tempdir)}
                process = subprocess.Popen([PYTHON, str(Path(__file__).resolve()), "job", str(lane), str(job["lane_order"])], cwd=ROOT, env=jobenv, stdout=log, stderr=subprocess.STDOUT)
                active[lane] = (process, job, log)
        status = {"utc": now(), "completed": sum(receipt_path(r).exists() for r in all_jobs), "planned": len(all_jobs),
                  "active": [{"job": key(j), "id": j["id"], "seed": j["seed"], "budget": j["time_limit_seconds"], "cpu": preflight["cpu_allocation"]["lane_cpus"][lane], "pid": p.pid} for lane, (p, j, _) in active.items()],
                  "remaining_by_lane": [len(q) for q in queues], "load_average": os.getloadavg()}
        save(EXEC / "status.json", status)
        if time.monotonic() - last_load >= 30:
            sample = {"utc": now(), "load_average": os.getloadavg(), "cpu_utilization": psutil.cpu_percent(percpu=True), "completed": status["completed"]}
            data = (json.dumps(sample, separators=(",", ":")) + "\n").encode()
            if (loadpath.stat().st_size if loadpath.exists() else 0) + len(data) >= LIMIT:
                raise RuntimeError("load log size ceiling reached")
            with loadpath.open("ab") as stream:
                stream.write(data)
            last_load = time.monotonic()
            print(json.dumps(status), flush=True)
        if active:
            time.sleep(3)
    errors = []
    for budget in (180, 360, 900):
        for seed in (370101, 370201, 370301):
            done = subprocess.run([PYTHON, str(Path(__file__).resolve()), "assess", str(budget), str(seed)], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=180)
            if done.returncode:
                errors.append({"budget": budget, "seed": seed, "returncode": done.returncode, "stdout": done.stdout, "stderr": done.stderr})
    save(EXEC / "execution-end.json", {"execution_end_utc": now(), "completed": sum(receipt_path(r).exists() for r in all_jobs), "planned": len(all_jobs), "grading_errors": errors, "postflight": verify()}, new=True)
    save(EXEC / "status.json", {"utc": now(), "completed": 360, "planned": 360, "active": [], "state": "completed", "grading_errors": errors})
    print("All 360 locked jobs completed; grading finished.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "supervise", "job", "assess", "verify"])
    parser.add_argument("numbers", nargs="*", type=int)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "supervise":
        supervise()
    elif args.action == "job":
        run_job(*args.numbers)
    elif args.action == "assess":
        assess(*args.numbers)
    else:
        info = verify()
        print(json.dumps({k: v for k, v in info.items() if k != "verified_files"}, indent=2))


if __name__ == "__main__":
    main()
