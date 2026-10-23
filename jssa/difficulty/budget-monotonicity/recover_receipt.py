"""Record a completed engine-error run whose frozen outcome reader raised.

Only the missing outer receipt is written. The raw, start receipt, sealed
executor and solver stay unchanged; this command never starts a solver.
"""
from __future__ import annotations

import datetime as dt
import json

import execute_stage2 as execution


def recover(job=None):
    event = (execution.read(execution.EXEC / "supervisor-error.json") if job is None else
             {"utc": execution.now(), "job": job, "reason": "outer receipt observer found the logged outcome-reader exception"})
    job = event["job"]
    destination = execution.receipt_path(job)
    if destination.exists():
        print("Completion receipt already exists; no change.")
        return
    start = execution.read(execution.receipt_path(job, "-start"))
    rawpath = execution.raw_path(job)
    raw = execution.read(rawpath)
    result = raw.get("solver_result") or {}
    logfile = execution.EXEC / "logs" / f"{execution.key(job)}.log"
    error = logfile.read_text()
    if (result.get("status") != "engine_error" or result.get("diagnostics") is not None
            or "read_run_outcome" not in error or "NoneType" not in error):
        raise RuntimeError("unrecognized completion failure; inspect without rerunning")
    ended = dt.datetime.fromtimestamp(rawpath.stat().st_mtime, dt.UTC)
    started = dt.datetime.fromisoformat(start["start_utc"].replace("Z", "+00:00"))
    outcome = {"status": "engine_error", "normal_completion": False, "failure_stage": "runtime",
               "termination_reason": result.get("termination_reason"), "rejection_tags": [],
               "wall_seconds": result.get("elapsed_seconds", raw["process"].get("elapsed_seconds")),
               "process_wall_seconds": raw["process"].get("elapsed_seconds"),
               "cpu_seconds": None, "peak_rss_bytes": None, "phase_timings": {}, "counters": {}}
    receipt = {**start, "end_utc": ended.isoformat(timespec="microseconds").replace("+00:00", "Z"),
               "adapter_elapsed_seconds": (ended - started).total_seconds(), "load_average_end": None,
               "load_samples": [], "observed_processes": [], "affinity_violations": [],
               "affinity_monitor_unavailable": True, "children_cpu_seconds": None,
               "raw_path": str(rawpath.relative_to(execution.ROOT)), "raw_sha256": execution.sha(rawpath),
               "raw_bytes": rawpath.stat().st_size, "outcome": outcome, "adapter_error": error,
               "storage_error": None, "mechanism_outcome": "unknown",
               "receipt_recovery": {"utc": execution.now(), "script_sha256": execution.sha(__file__),
                   "reason": "frozen read_run_outcome does not accept engine_error diagnostics=null",
                   "end_time_source": "existing atomic raw file mtime; not a recovered worker finish clock",
                   "lost_fields": ["periodic load samples", "process monitor samples", "child CPU accounting"],
                   "raw_unchanged": True, "solver_reexecuted": False,
                   "supervisor_error": event}}
    execution.save(destination, receipt, new=True)
    execution.save(execution.EXEC / "recoveries" / f"{execution.key(job)}.json", receipt["receipt_recovery"], new=True)
    print(json.dumps({"recovered_outer_receipt": execution.key(job), "outcome": "unknown", "solver_runs": 0}))


if __name__ == "__main__":
    recover()
