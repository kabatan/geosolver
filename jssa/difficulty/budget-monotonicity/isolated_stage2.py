"""Resume only the 256 unstarted Q37 jobs from the clean frozen checkout.

The original executor, 104 raws/receipts, manifests and prediction lock remain
unchanged. The solver and scorer are imported exclusively from /tmp/q37-clean.
This outer adapter adds contention evidence and catches the frozen reader's
known null-diagnostics exception without changing any raw or grading function.
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
SHARED_ROOT = BASE.parents[2]
ROOT = Path("/tmp/q37-clean")
EXEC = BASE / "execution"
RESUME = EXEC / "resume"
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
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
    source_locations = {}
    for folder, entries in ((BASE, lock["artifacts"]), (ROOT, read(BASE / "source-manifest.json")["sources"])):
        for rel, expected in entries.items():
            path = folder / rel
            if folder == ROOT and rel.startswith("jssa/"):
                path = SHARED_ROOT / rel
                if rel == "jssa/strategy/codex-tasks-1023.md":
                    path = RESUME / "frozen-sources" / rel
            actual = {"sha256": sha(path), "bytes": path.stat().st_size}
            if actual != expected:
                raise RuntimeError(f"locked source changed: {path}: {actual}")
            verified[rel] = actual
            source_locations[rel] = str(path)
    if git("rev-parse", "HEAD").decode().strip() != FROZEN or git("status", "--porcelain").strip():
        raise RuntimeError("runtime checkout is not clean at the frozen commit")
    if Path(rr.__file__).resolve() != ROOT / "benchmarks/research_runner.py":
        raise RuntimeError("scorer import is not from the clean checkout")
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
            "verified_file_locations": source_locations, "runtime_checkout": str(ROOT),
            "scorer_import_path": rr.__file__, "scorer_sha256": sha(rr.__file__),
            "runtime_fingerprint": fingerprint, "python": sys.executable, "python_version": sys.version,
            "src_git_tree": git("rev-parse", lock["frozen_solver_commit"] + ":src").decode().strip(),
            "remote_tracking_refs": git("for-each-ref", "--contains", COMMIT, "--format=%(refname) %(objectname)", "refs/remotes").decode().splitlines(),
            "push_evidence": "User reports push near 2026-10-23T16:18:35Z; local tracking reference corroborates commit containment, not server time.",
            "authorization": "User authorized resuming exactly the 256 unstarted jobs after the Q38 shared-scorer collision; existing 104 jobs, all locked choices and lane order stay unchanged. Shared high load is accepted with observations; no retries.",
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
    if (RESUME / "preflight.json").exists():
        raise RuntimeError("resume preflight already exists; do not overwrite")
    preflight = verify()
    original = read(EXEC / "preflight.json")
    if original["cpu_allocation"]["lane_cpus"] != [4, 10, 14, 15]:
        raise RuntimeError("unexpected original CPU assignment")
    baseline, completed, pending = {}, [], []
    for job in jobs():
        if receipt_path(job).exists():
            receipt = read(receipt_path(job))
            if receipt["job"] != job or receipt["raw_sha256"] != sha(raw_path(job)):
                raise RuntimeError("existing receipt/raw mismatch")
            completed.append(key(job))
            for path in (receipt_path(job), receipt_path(job, "-start"), raw_path(job)):
                baseline[str(path.relative_to(BASE))] = {"sha256": sha(path), "bytes": path.stat().st_size}
        else:
            if receipt_path(job, "-start").exists() or raw_path(job).exists():
                raise RuntimeError("incomplete previously started job: no retry")
            pending.append(key(job))
    if len(completed) != 104 or len(pending) != 256:
        raise RuntimeError("resume must begin at exactly 104 complete / 256 unstarted")
    for lane in range(4):
        lane_jobs = [j for j in jobs() if j["lane"] == lane]
        done = [receipt_path(j).exists() for j in lane_jobs]
        if done != sorted(done, reverse=True):
            raise RuntimeError("existing runs are not a lane prefix")
    for rel, digest in original["campaign_manifest_sha256"].items():
        path = BASE / rel / "campaign-manifest.json"
        if sha(path) != digest:
            raise RuntimeError("original manifest changed")
        baseline[str(path.relative_to(BASE))] = {"sha256": sha(path), "bytes": path.stat().st_size}
    for name in ("preflight.json", "execution-start.json", "execution-stopped.json"):
        path = EXEC / name
        baseline[str(path.relative_to(BASE))] = {"sha256": sha(path), "bytes": path.stat().st_size}
    save(RESUME / "baseline.json", {"utc": now(), "files": baseline, "completed_job_keys": completed,
         "pending_job_keys_in_jobs_csv_order": pending, "solver_runs": 0}, new=True)
    preflight.update(cpu_allocation=original["cpu_allocation"],
                     campaign_manifest_sha256=original["campaign_manifest_sha256"],
                     original_adapter_sha256=original["adapter_sha256"],
                     baseline_sha256=sha(RESUME / "baseline.json"),
                     completed_before_resume=104, unstarted_before_resume=256,
                     preparation_completed_utc=now(), load_average=os.getloadavg(), executed_solver_runs=0)
    save(RESUME / "preflight.json", preflight, new=True)
    print(json.dumps({"prepared": True, "lane_cpus": [4, 10, 14, 15], "verified_artifacts": 13,
                      "verified_sources": 271, "completed": 104, "pending": 256, "load_average": os.getloadavg(),
                      "source_hash": preflight["runtime_fingerprint"]["source_hash"], "solver_runs": 0}), flush=True)


def verify_baseline():
    preflight = read(RESUME / "preflight.json")
    if sha(RESUME / "baseline.json") != preflight["baseline_sha256"]:
        raise RuntimeError("baseline manifest changed")
    baseline = read(RESUME / "baseline.json")
    for rel, expected in baseline["files"].items():
        path = BASE / rel
        if {"sha256": sha(path), "bytes": path.stat().st_size} != expected:
            raise RuntimeError(f"pre-resume evidence changed: {rel}")
    return {"preserved_files": len(baseline["files"]), "preserved_jobs": 104}


def pressure():
    try:
        return Path("/proc/pressure/cpu").read_text().strip()
    except OSError:
        return None


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
    preflight = read(RESUME / "preflight.json")
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
             "adapter_sha256": sha(__file__), "prediction_lock_sha256": LOCK_SHA,
             "runtime_checkout": str(ROOT), "scorer_import_path": rr.__file__,
             "resume_preflight_sha256": sha(RESUME / "preflight.json")}
    save(receipt_path(job, "-start"), start, new=True)
    started = time.monotonic()
    stop = threading.Event()
    processes, samples = {}, []
    siblings = [int(v) for v in Path(f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list").read_text().strip().split(",")]

    def observe():
        psutil.cpu_percent(percpu=True)
        first = True
        while not stop.is_set():
            utilization = psutil.cpu_percent(percpu=True)
            sample = {"elapsed": time.monotonic() - started, "utc": now(), "load_average": os.getloadavg(),
                      "cpu_pressure": pressure(),
                      "physical_core_logical_cpu_utilization_percent": None if first else {str(c): utilization[c] for c in siblings}}
            first = False
            try:
                children = [psutil.Process(), *psutil.Process().children(recursive=True)]
            except psutil.Error:
                children = []
            own_pids = {p.pid for p in children}
            competitors = []
            for other in psutil.process_iter(["pid", "name", "status", "cpu_num"]):
                try:
                    info = other.info
                    if info["pid"] not in own_pids and info["status"] == "running" and info["cpu_num"] in siblings:
                        competitors.append(info)
                except psutil.Error:
                    pass
            sample["visible_other_runnable_processes_on_core"] = competitors[:16]
            sample["visible_other_runnable_process_count_on_core"] = len(competitors)
            samples.append(sample)
            for process in children:
                try:
                    times = process.cpu_times()
                    prior = processes.setdefault(str(process.pid), {"pid": process.pid, "name": process.name(), "first_seen": time.monotonic() - started, "affinities": []})
                    affinity = process.cpu_affinity()
                    if affinity not in prior["affinities"]:
                        prior["affinities"].append(affinity)
                    prior.update(last_seen=time.monotonic() - started, cpu_seconds=times.user + times.system,
                                 peak_sampled_rss_bytes=max(prior.get("peak_sampled_rss_bytes", 0), process.memory_info().rss))
                    try:
                        runtime_ns, wait_ns, slices = map(int, Path(f"/proc/{process.pid}/schedstat").read_text().split())
                        prior.update(sampled_scheduler_runtime_seconds=runtime_ns / 1e9,
                                     sampled_scheduler_wait_seconds=wait_ns / 1e9, sampled_scheduler_timeslices=slices)
                    except (OSError, ValueError):
                        pass
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
    recovery = None
    try:
        outcome = rr.read_run_outcome(raw)
    except AttributeError:
        result = raw.get("solver_result") or {}
        if result.get("status") != "engine_error" or result.get("diagnostics") is not None:
            raise
        recovery = {"utc": now(), "reason": "frozen read_run_outcome rejects engine_error diagnostics=null",
                    "reader_exception": traceback.format_exc(), "script_sha256": sha(__file__),
                    "raw_unchanged": True, "solver_reexecuted": False, "lost_fields": [],
                    "end_time_source": "live outer adapter completion clock; monitor samples retained"}
        outcome = {"status": "engine_error", "normal_completion": False, "failure_stage": "runtime",
                   "termination_reason": result.get("termination_reason"), "rejection_tags": [],
                   "wall_seconds": result.get("elapsed_seconds", raw["process"].get("elapsed_seconds")),
                   "process_wall_seconds": raw["process"].get("elapsed_seconds"),
                   "cpu_seconds": None, "peak_rss_bytes": None, "phase_timings": {}, "counters": {}}
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {**start, "end_utc": now(), "adapter_elapsed_seconds": time.monotonic() - started,
               "load_average_end": os.getloadavg(), "load_samples": samples,
               "observed_processes": list(processes.values()),
               "affinity_violations": [p for p in processes.values() if p["affinities"] != [[cpu]]],
               "children_cpu_seconds": usage.ru_utime + usage.ru_stime,
               "raw_path": str(raw_path(job).relative_to(SHARED_ROOT)), "raw_sha256": sha(raw_path(job)),
               "raw_bytes": raw_path(job).stat().st_size, "outcome": outcome,
               "adapter_error": error, "storage_error": storage.get("error"),
               "mechanism_outcome": "known" if outcome["normal_completion"] else "unknown"}
    receipt["contention_observation_limit"] = "Host load/CPU pressure and SMT utilization are host-wide; visible process competitors are PID-namespace limited. Sampled task scheduler wait is a lower bound; polling can miss short-lived tasks. CPU affinity is not exclusive reservation."
    if recovery:
        receipt["receipt_recovery"] = recovery
        save(RESUME / "recoveries" / f"{key(job)}.json", recovery, new=True)
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
    os.sched_setaffinity(0, {2})
    EXEC.mkdir(exist_ok=True)
    lockstream = (EXEC / "supervisor.lock").open("a")
    fcntl.flock(lockstream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
    verify()
    verify_baseline()
    preflight = read(RESUME / "preflight.json")
    if sha(__file__) != preflight["adapter_sha256"]:
        raise RuntimeError("adapter changed")
    for rel, expected in preflight["campaign_manifest_sha256"].items():
        if sha(BASE / rel / "campaign-manifest.json") != expected:
            raise RuntimeError("prepared campaign manifest changed")
    save(RESUME / "execution-start.json", {"execution_start_utc": now(), "prediction_lock_sha256": LOCK_SHA,
         "preflight_sha256": sha(RESUME / "preflight.json"), "lane_cpus": preflight["cpu_allocation"]["lane_cpus"],
         "load_average": os.getloadavg(), "cpu_pressure": pressure(), "pid": os.getpid(),
         "completed_before_resume": 104, "remaining": 256, "authorization_observed": True,
         "stopped_commit": "ee89b975", "user_reported_push_utc": "2026-10-23T17:38:41Z",
         "collision": "Q38 approved null-diagnostics edit changed shared research_runner bytes; not a prediction/selection/plan error."}, new=True)
    all_jobs = jobs()
    queues = [[r for r in all_jobs if r["lane"] == lane and not receipt_path(r).exists()] for lane in range(4)]
    if any(receipt_path(r, "-start").exists() or raw_path(r).exists() for queue in queues for r in queue):
        raise RuntimeError("started job has no completion receipt; inspect and record unknown without retry before resuming")
    active = {}
    environment = clean_env()
    last_load = 0.0
    loadpath = RESUME / "load.jsonl"
    while any(queues) or active:
        for lane in range(4):
            if lane in active and active[lane][0].poll() is not None:
                process, job, log = active.pop(lane)
                log.close()
                if not receipt_path(job).exists():
                    save(RESUME / "supervisor-error.json", {"utc": now(), "job": job, "returncode": process.returncode, "reason": "child exited without completion receipt; no retry"})
                    # Other already-started jobs may finish; do not launch further work.
                    for other, _, _ in active.values():
                        other.wait()
                    raise RuntimeError("job adapter failed; inspect supervisor-error.json")
            if lane not in active and queues[lane]:
                job = queues[lane].pop(0)
                logpath = RESUME / "logs" / f"{key(job)}.log"
                logpath.parent.mkdir(parents=True, exist_ok=True)
                log = logpath.open("xb")
                tempdir = EXEC / "tmp" / f"isolated-{key(job)}"
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
    save(RESUME / "preservation-check.json", {"utc": now(), **verify_baseline()}, new=True)
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
