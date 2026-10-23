"""Bounded Q39 batches. Every solver worker has one fixed physical core.

The background coordinator only launches at most three jobs per batch, records
each 150-second watchdog, and never retries an already-started job.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

BASE = Path(__file__).resolve().parent
_runtime_location = BASE / "runtime-location.json"
ROOT = (Path(json.loads(_runtime_location.read_text())["root"])
        if _runtime_location.exists() else BASE.parents[2])
OUT = BASE / "execution"
PYTHON = "/home/kabatan/work/solver/.venv/bin/python"
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[name] = "1"
import psutil
import diagnostic as d
ROOT = d.ROOT


def verify_lock():
    lock = d.read(BASE / "prediction.lock.json")
    expected_lock = d.read(BASE / "execution-start.json")["prediction_lock_sha256"]
    if d.sha(BASE / "prediction.lock.json") != expected_lock:
        raise RuntimeError("prediction lock changed")
    for path, expected in lock["artifacts_sha256"].items():
        if d.sha(BASE / path) != expected:
            raise RuntimeError("stage-1 file changed: " + path)
    manifest = d.read(BASE / "source-manifest.json")
    for path, expected in {**manifest["tracked_src_files_sha256"],
                           **manifest["read_inputs_sha256"]}.items():
        if d.sha(ROOT / path) != expected:
            raise RuntimeError("source changed: " + path)
    for row in d.selected().values():
        if d.sha(ROOT / row["dsl_path"]) != row["dsl_sha256"]:
            raise RuntimeError("selected DSL changed")
    return True


def environment():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PYTHON", "GEOSOLVER", "Q30", "Q36", "Q37", "LD_"))}
    env.update(PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
               PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        env[name] = "1"
    return env


def setup():
    verify_lock()
    from benchmarks import research_runner as rr
    fp = rr.runtime_fingerprint()
    if fp["issues"]:
        raise RuntimeError(fp["issues"])
    import PyNomad
    with d.mp.workdps(15):
        precision = d.mp.prec
    if precision != 53:
        raise RuntimeError("search B is not binary53")
    topology = {}
    for cpu in sorted(os.sched_getaffinity(0)):
        p = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        key = ((p / "physical_package_id").read_text().strip(),
               (p / "core_id").read_text().strip())
        topology.setdefault(key, []).append(cpu)
    samples = [psutil.cpu_percent(interval=3, percpu=True) for _ in range(3)]
    scores = {min(cpus): sum(s[c] for s in samples for c in cpus) / len(samples)
              for cpus in topology.values()}
    cpus = sorted(sorted(scores, key=lambda c: (scores[c], c))[:3])
    original = os.sched_getaffinity(0)
    for cpu in cpus:
        os.sched_setaffinity(0, {cpu})
        if os.sched_getaffinity(0) != {cpu}:
            raise RuntimeError("affinity verification failed")
    os.sched_setaffinity(0, original)
    manifest = {"utc": d.utc(), "runtime": fp, "python": sys.executable,
                "python_version": sys.version, "53bit_search_B": precision,
                "cpus": cpus, "cpu_samples": samples, "cpu_scores": scores,
                "topology": [{"package_core": list(k), "cpus": v} for k, v in topology.items()],
                "load_average": os.getloadavg(), "thread_environment": environment(),
                "wrapper_sha256": {p.name: d.sha(p) for p in [BASE / "diagnostic.py", Path(__file__)]},
                "max_workers": 3, "job_watchdog_seconds": 150,
                "worker_and_descendants_rss_limit": 2 * 1024**3,
                "file_size_limit": 4_900_000, "split_at_bytes": 4_000_000,
                "authorization_receipt_sha256": d.sha(BASE / "execution-start.json")}
    # Do not copy unrelated environment credentials into evidence.
    manifest["thread_environment"] = {k: environment()[k] for k in environment()
                                       if k.endswith("NUM_THREADS") or k in ("PYTHONPATH", "PYTHONHASHSEED")}
    d.save(OUT / "manifest.json", manifest)
    d.save(BASE / "execution-manifest.json", manifest)
    print(json.dumps({"setup": "ok", "cpus": cpus, "runtime_issues": fp["issues"]}))


def job_list(stage):
    protocol = d.read(BASE / "protocol.json")
    jobs = []
    for identifier in protocol["selected_ids"]:
        if stage == "prepare":
            jobs.append({"stage": stage, "id": identifier})
            continue
        for seed in d.SEEDS:
            front_modes = ["A", "B"]
            if hashlib.sha256(f"front|{identifier}|{seed}".encode()).digest()[0] % 2:
                front_modes.reverse()
            extras = []
            if identifier in protocol["controls"]["L_ids"]:
                extras.append("L")
            if identifier == protocol["controls"]["masked_case"]:
                extras.extend("mask:" + k for k in protocol["controls"]["masks"])
            if stage == "front":
                jobs.extend({"stage": stage, "id": identifier, "seed": seed, "mode": m}
                            for m in front_modes + extras)
            elif stage == "rear":
                cells = [("A", "A"), ("A", "B"), ("B", "B"), ("B", "A")]
                rotation = hashlib.sha256(f"rear|{identifier}|{seed}".encode()).digest()[0] % 4
                cells = cells[rotation:] + cells[:rotation]
                # Common A->A and front A are reused exactly as permitted.
                for mode in extras:
                    cells.extend([("A", mode), (mode, mode), (mode, "A")])
                if identifier in protocol["controls"]["R0_ids"]:
                    cells.extend([("A", "R0"), ("B", "R0")])
                jobs.extend({"stage": stage, "id": identifier, "seed": seed,
                             "front_mode": f, "rear_mode": r} for f, r in cells)
    for i, job in enumerate(jobs):
        job["index"] = i
        job["key"] = f"{stage}-{i:04d}"
    return jobs


def worker(job, cpu):
    os.sched_setaffinity(0, {cpu})
    resource.setrlimit(resource.RLIMIT_FSIZE, (4_900_000, 4_900_000))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    verify_lock()
    started = time.monotonic()
    result = {"job": job, "utc_start": d.utc(), "cpu": cpu,
              "affinity": sorted(os.sched_getaffinity(0)), "load_average": os.getloadavg(),
              "wrapper_sha256": {p.name: d.sha(p) for p in [BASE / "diagnostic.py", Path(__file__)]}}
    d.save(OUT / "jobs" / (job["key"] + ".started.json"), result)
    try:
        if job["stage"] == "prepare":
            result["result"] = d.prepare(job["id"])
        elif job["stage"] == "front":
            result["result"] = d.front(job["id"], job["seed"], job["mode"])
        elif job["stage"] == "rear":
            result["result"] = d.rear(job["id"], job["seed"], job["front_mode"], job["rear_mode"])
        result["status"] = "completed"
    except BaseException as exc:
        result.update(status="failed", error_type=type(exc).__name__, error=str(exc)[:4000],
                      traceback=traceback.format_exc()[-12000:])
    result.update(utc_end=d.utc(), elapsed_seconds=time.monotonic() - started,
                  cpu_seconds=time.process_time(), peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    d.save(OUT / "jobs" / (job["key"] + ".json"), result)
    print(json.dumps({"job": job["key"], "status": result["status"], "elapsed": result["elapsed_seconds"]}))


def run_one(job, cpu):
    marker = OUT / "jobs" / (job["key"] + ".started.json")
    receipt = OUT / "jobs" / (job["key"] + ".json")
    if marker.exists() or receipt.exists():
        return {"job": job["key"], "status": "previous_attempt_preserved"}
    log = OUT / "logs" / (job["key"] + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    begin = time.monotonic()
    rss_peak, violations, processes = 0, [], {}
    reason = None
    with log.open("wb") as stream:
        # Linux affinity is per calling thread. Set it before fork/exec so the
        # child is pinned even before taskset executes (no startup race).
        old_affinity = os.sched_getaffinity(0)
        os.sched_setaffinity(0, {cpu})
        try:
            proc = subprocess.Popen(["taskset", "-c", str(cpu), PYTHON, str(Path(__file__).resolve()),
                       "worker", "--job", json.dumps(job), "--cpu", str(cpu)],
                       cwd=ROOT, env=environment(), stdout=stream, stderr=subprocess.STDOUT,
                       start_new_session=True)
        finally:
            os.sched_setaffinity(0, old_affinity)
        while proc.poll() is None:
            try:
                tree = [psutil.Process(proc.pid)]
                tree += tree[0].children(recursive=True)
                rss = 0
                for p in tree:
                    try:
                        rss += p.memory_info().rss
                        affinity = p.cpu_affinity()
                        processes[p.pid] = {"pid": p.pid, "affinity": affinity}
                        if affinity != [cpu]:
                            violations.append({"pid": p.pid, "affinity": affinity})
                    except psutil.Error:
                        pass
                rss_peak = max(rss_peak, rss)
            except psutil.Error:
                pass
            if time.monotonic() - begin >= 150:
                reason = "external_timeout"
            elif rss_peak > 2 * 1024**3:
                reason = "memory_limit"
            elif violations:
                reason = "affinity_violation"
            if reason:
                for p in reversed(tree):
                    try:
                        p.kill()
                    except psutil.Error:
                        pass
                proc.wait(timeout=5)
                break
            time.sleep(0.25)
    result = {"job": job, "cpu": cpu, "returncode": proc.returncode,
              "elapsed_seconds": time.monotonic() - begin, "peak_tree_rss_bytes": rss_peak,
              "processes": list(processes.values()), "affinity_violations": violations,
              "termination": reason, "utc_end": d.utc()}
    d.save(OUT / "processes" / (job["key"] + ".json"), result)
    if not receipt.exists():
        d.save(receipt, {"job": job, "status": "failed", "error_type": reason or "process_crash",
                         "process": result, "partial_files_preserved": True})
    return {"job": job["key"], "status": d.read(receipt)["status"], "termination": reason}


def batch(stage, batch_id):
    verify_lock()
    cpus = d.read(OUT / "manifest.json")["cpus"]
    jobs = job_list(stage)[batch_id * len(cpus):(batch_id + 1) * len(cpus)]
    submission = {"stage": stage, "batch_id": batch_id, "utc": d.utc(), "jobs": jobs}
    d.save(OUT / "batches" / f"{stage}-{batch_id:04d}.submitted.json", submission)
    with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
        futures = [pool.submit(run_one, job, cpu) for job, cpu in zip(jobs, cpus)]
        result = [f.result() for f in futures]
    d.save(OUT / "batches" / f"{stage}-{batch_id:04d}.json", result)
    print(json.dumps({"stage": stage, "batch_id": batch_id, "result": result}), flush=True)


def seal_front():
    records = {}
    for p in sorted((OUT / "front").rglob("*.json")):
        records[str(p.relative_to(OUT))] = d.sha(p)
    d.save(OUT / "front-seal.json", {"utc": d.utc(), "count": len(records),
                                   "sha256": records, "reference_access_before_seal": False})


def drive(stage, start_batch=0):
    cpus = d.read(OUT / "manifest.json")["cpus"]
    jobs = job_list(stage)
    d.save(OUT / f"{stage}-jobs.json", jobs)
    for batch_id in range(start_batch, (len(jobs) + len(cpus) - 1) // len(cpus)):
        # The parent is an idle background coordinator; each actual command is
        # an explicit batch of at most 3 jobs with per-job 150-second watchdogs.
        subprocess.run([PYTHON, str(Path(__file__).resolve()), "batch", "--stage", stage,
                        "--batch-id", str(batch_id)], cwd=ROOT, env=environment(),
                       check=True, timeout=165)
        failures = [d.read(OUT / "jobs" / (j["key"] + ".json"))
                    for j in jobs[batch_id * len(cpus):(batch_id + 1) * len(cpus)]]
        if stage == "prepare" and any(r["status"] != "completed" for r in failures):
            raise RuntimeError("preparation failure; no search launched")
    if stage == "front":
        seal_front()
    d.save(OUT / (stage + "-complete.json"), {"utc": d.utc(), "jobs": len(jobs)})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["setup", "worker", "batch", "drive", "seal"])
    p.add_argument("--job")
    p.add_argument("--cpu", type=int)
    p.add_argument("--stage", choices=["prepare", "front", "rear"])
    p.add_argument("--batch-id", type=int, default=0)
    args = p.parse_args()
    if args.command == "setup":
        setup()
    elif args.command == "worker":
        worker(json.loads(args.job), args.cpu)
    elif args.command == "batch":
        batch(args.stage, args.batch_id)
    elif args.command == "drive":
        drive(args.stage, args.batch_id)
    else:
        seal_front()
