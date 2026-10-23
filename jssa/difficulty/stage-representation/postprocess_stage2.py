"""Small fixed-CPU batches for the already specified order probes and grading."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import time

import psutil
import diagnostic as d
import execute_stage2 as ex
import measure_stage2 as measurement


def jobs(stage):
    if stage == "order":
        return [{"key": "order-" + identifier, "kind": "order", "id": identifier}
                for identifier in d.read(d.BASE / "protocol.json")["controls"]["R0_ids"]]
    if stage == "grade":
        from analyze_stage2 import campaigns
        return [{"key": "grade-" + name, "kind": "grade", "campaign": name}
                for name, _, _, _ in campaigns()]
    return [{"key": "summarize", "kind": "summarize"}]


def run(job, cpu):
    receipt_path = d.OUT / "postprocessing" / (job["key"] + ".json")
    started_path = d.OUT / "postprocessing" / (job["key"] + ".started.json")
    if receipt_path.exists() or started_path.exists():
        return {"job": job["key"], "status": "previous_attempt_preserved"}
    allowance = 15. if job["kind"] == "order" else measurement.reserve(45., job["key"])
    if allowance < .1:
        d.save(receipt_path, {"job": job, "status": "additional_budget_exhausted"})
        if job["kind"] != "order":
            measurement.finish(job["key"], 0)
        return {"job": job["key"], "status": "additional_budget_exhausted"}
    if job["kind"] == "order":
        command = [ex.PYTHON, str(d.BASE / "measure_stage2.py"), "order", "--id", job["id"]]
    else:
        command = [ex.PYTHON, str(d.BASE / "analyze_stage2.py"), job["kind"]]
        if job["kind"] == "grade":
            command.extend(["--campaign", job["campaign"]])
    start = time.monotonic()
    result = {"job": job, "utc_start": d.utc(), "cpu": cpu,
              "outer_watchdog_seconds": allowance,
              "order_numeric_budget_seconds": 10 if job["kind"] == "order" else None}
    d.save(started_path, result)
    reason, peak, affinity_violations = None, 0, []
    with (receipt_path.parent / (job["key"] + ".log")).open("wb") as log:
        old = os.sched_getaffinity(0)
        os.sched_setaffinity(0, {cpu})
        try:
            proc = subprocess.Popen(command, cwd=d.ROOT, env=ex.environment(),
                                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        finally:
            os.sched_setaffinity(0, old)
        while proc.poll() is None:
            tree = []
            try:
                root = psutil.Process(proc.pid)
                tree = [root] + root.children(recursive=True)
                rss = 0
                for p in tree:
                    try:
                        rss += p.memory_info().rss
                        if p.cpu_affinity() != [cpu]:
                            affinity_violations.append({"pid": p.pid, "affinity": p.cpu_affinity()})
                    except psutil.Error:
                        pass
                peak = max(peak, rss)
            except psutil.Error:
                pass
            if time.monotonic() - start >= allowance:
                reason = "external_timeout"
            elif peak > 2 * 1024**3:
                reason = "memory_limit"
            elif affinity_violations:
                reason = "affinity_violation"
            if reason:
                for p in reversed(tree):
                    try:
                        p.kill()
                    except psutil.Error:
                        pass
                proc.wait(timeout=2)
                break
            time.sleep(.1)
    elapsed = time.monotonic() - start
    result.update(utc_end=d.utc(), elapsed_seconds=elapsed, returncode=proc.returncode,
                  termination=reason, peak_tree_rss_bytes=peak, affinity_violations=affinity_violations,
                  status="completed" if proc.returncode == 0 and not reason else "failed")
    if job["kind"] != "order":
        measurement.finish(job["key"], elapsed)
    if job["kind"] == "order" and not (d.OUT / "orders" / (job["id"] + ".json")).exists():
        d.save(d.OUT / "orders" / (job["id"] + ".json"),
               {"id": job["id"], "status": "NA", "reason": reason or "process_failed",
                "new_solves": 0, "execution_receipt": str(receipt_path.relative_to(d.OUT))})
    d.save(receipt_path, result)
    return {"job": job["key"], "status": result["status"]}


def batch(stage, index):
    ex.verify_lock()
    cpus = d.read(d.OUT / "manifest.json")["cpus"]
    subset = jobs(stage)[3*index:3*(index+1)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = [pool.submit(run, job, cpu) for job, cpu in zip(subset, cpus)]
        result = [f.result() for f in pending]
    d.save(d.OUT / "postprocessing" / f"batch-{stage}-{index}.json", result)
    print(json.dumps({"stage": stage, "batch_id": index, "jobs": result}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["batch", "drive"])
    p.add_argument("--stage", choices=["order", "grade", "summarize"], required=True)
    p.add_argument("--batch-id", type=int, default=0)
    args = p.parse_args()
    if not (d.OUT / "rear-complete.json").exists():
        raise RuntimeError("postprocessing requires completion of all planned rear jobs")
    if args.command == "batch":
        batch(args.stage, args.batch_id)
    else:
        for i in range(args.batch_id, (len(jobs(args.stage)) + 2) // 3):
            subprocess.run([ex.PYTHON, str(Path(__file__).resolve()), "batch", "--stage", args.stage,
                            "--batch-id", str(i)], env=ex.environment(), cwd=d.ROOT,
                           check=True, timeout=60)
