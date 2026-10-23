"""Observe outer receipt failures and resume only unstarted locked jobs.

The sealed executor, runner and solver are unchanged. Capture supervisor stdout
in bounded files so logging cannot block scheduling. This observer only handles
the known diagnostics=null bookkeeping exception, preserving original raw data.
"""
from __future__ import annotations

import os
import resource
import subprocess
import time

import execute_stage2 as execution
from recover_receipt import recover


def observe(jobs):
    recovered = 0
    for job in jobs:
        if execution.receipt_path(job).exists() or not execution.raw_path(job).exists():
            continue
        log = execution.EXEC / "logs" / f"{execution.key(job)}.log"
        text = log.read_text() if log.exists() else ""
        if "read_run_outcome" in text and "NoneType" in text:
            recover(job)
            recovered += 1
    return recovered


def main():
    os.sched_setaffinity(0, {2})  # Outside the four experimental cores.
    resource.setrlimit(resource.RLIMIT_FSIZE, (execution.LIMIT, execution.LIMIT))
    execution.verify()
    jobs = execution.jobs()
    execution.save(execution.EXEC / "resume-driver-start.json", {
        "utc": execution.now(), "driver_sha256": execution.sha(__file__),
        "sealed_executor_sha256": execution.sha(execution.__file__),
        "recovery_script_sha256": execution.sha(execution.BASE / "recover_receipt.py"),
        "reason": "Preserve existing raw runs and resume unstarted jobs after the frozen null-diagnostics reader exception.",
        "solver_and_scoring_modified": False, "retries_permitted": False,
    }, new=True)
    cycle = 0
    while not (execution.EXEC / "execution-end.json").exists():
        cycle += 1
        count_before = sum(execution.receipt_path(job).exists() for job in jobs)
        logpath = execution.EXEC / "logs" / f"supervisor-resume-{cycle:03d}.log"
        with logpath.open("xb") as stream:
            process = subprocess.Popen([execution.PYTHON, str(execution.BASE / "execute_stage2.py"), "supervise"],
                                       cwd=execution.ROOT, env=execution.clean_env(),
                                       stdout=stream, stderr=subprocess.STDOUT)
            while process.poll() is None:
                observe(jobs)
                time.sleep(0.5)
            observe(jobs)
        count_after = sum(execution.receipt_path(job).exists() for job in jobs)
        execution.save(execution.EXEC / "resumptions" / f"cycle-{cycle:03d}.json", {
            "utc": execution.now(), "returncode": process.returncode,
            "completed_before": count_before, "completed_after": count_after,
            "log": str(logpath.relative_to(execution.BASE)), "solver_retries": 0,
        }, new=True)
        if process.returncode and count_after <= count_before:
            raise RuntimeError("supervisor stopped without new receipts; inspect rather than retry")
        if process.returncode:
            event = execution.read(execution.EXEC / "supervisor-error.json")
            if not execution.receipt_path(event["job"]).exists():
                raise RuntimeError("unhandled missing receipt; inspect rather than retry")
    print("All locked runs and original campaign grading finished.", flush=True)


if __name__ == "__main__":
    main()
