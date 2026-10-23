"""Inventory a strict-contract stop without importing or running the scorer."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
EXEC = BASE / "execution"
LIMIT = 4_900_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    data = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
    if len(data) >= LIMIT:
        raise ValueError("summary too large")
    path.write_bytes(data)


def write_csv(name, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    data = stream.getvalue().encode()
    if len(data) >= LIMIT:
        raise ValueError("inventory too large")
    (BASE / name).write_bytes(data)


def main():
    lock = read(BASE / "prediction.lock.json")
    sources = read(BASE / "source-manifest.json")["sources"]
    mismatches = []
    for kind, folder, entries in (("locked_artifact", BASE, lock["artifacts"]), ("manifest_source", ROOT, sources)):
        for relative, expected in entries.items():
            path = folder / relative
            actual = {"sha256": sha(path), "bytes": path.stat().st_size} if path.exists() else None
            if expected != actual:
                mismatches.append({"kind": kind, "path": str(path.relative_to(ROOT)), "expected": expected, "actual": actual})
    jobs = list(csv.DictReader((BASE / "jobs.csv").open()))
    rows, intervals, receipts, raw_errors = [], [], [], []
    for job in jobs:
        key = f"lane{job['lane']}-{int(job['lane_order']):03d}"
        startpath = EXEC / "receipts" / f"{key}-start.json"
        receiptpath = EXEC / "receipts" / f"{key}.json"
        rawpath = BASE / job["campaign_relative"] / "runs" / job["id"] / f"{job['seed']}.json"
        start = read(startpath) if startpath.exists() else {}
        receipt = read(receiptpath) if receiptpath.exists() else {}
        raw = read(rawpath) if rawpath.exists() else {}
        result = raw.get("solver_result") or {}
        outcome = receipt.get("outcome") or {}
        state = "completed" if receipt else "running" if start else "not_started"
        status = outcome.get("status")
        if state == "completed":
            receipts.append(receipt)
            intervals.extend([(receipt["start_utc"], 1), (receipt["end_utc"], -1)])
            if receipt["raw_sha256"] != sha(rawpath):
                raw_errors.append(key)
        stderr = raw.get("process", {}).get("stderr", "")
        missing = ("storage_file_size_limit" if "[Errno 27] File too large" in stderr else
                   "engine_error_artifact_missing" if (result.get("error") or {}).get("code") == "artifact_missing" else
                   status if state == "completed" and not outcome.get("normal_completion") else None)
        rows.append({"id": job["id"], "stratum": job["stratum"], "seed": int(job["seed"]),
                     "budget_seconds": int(job["time_limit_seconds"]), "lane": int(job["lane"]),
                     "lane_order": int(job["lane_order"]), "execution_state": state,
                     "public_status": status, "normal_completion": outcome.get("normal_completion"),
                     "correctness": "not_assessed", "missing_reason": missing,
                     "cpu": start.get("cpu"), "start_utc": start.get("start_utc"), "end_utc": receipt.get("end_utc"),
                     "solver_wall_seconds": outcome.get("wall_seconds"),
                     "process_wall_seconds": outcome.get("process_wall_seconds"),
                     "worker_cpu_seconds": outcome.get("cpu_seconds"),
                     "periodic_monitor_unavailable": receipt.get("affinity_monitor_unavailable", False) if receipt else None,
                     "raw_path": str(rawpath.relative_to(BASE)) if raw else None,
                     "raw_sha256": sha(rawpath) if raw else None,
                     "raw_bytes": rawpath.stat().st_size if raw else None,
                     "receipt_path": str(receiptpath.relative_to(BASE)) if receipt else None})
    write_csv("execution-inventory.csv", rows)
    bykey = {(r["id"], r["seed"], r["budget_seconds"]): r for r in rows}
    problemrows = []
    for problem in csv.DictReader((BASE / "selection.csv").open()):
        subset = [r for r in rows if r["id"] == problem["id"]]
        row = {"id": problem["id"], "stratum": problem["stratum"],
               "completed": sum(r["execution_state"] == "completed" for r in subset),
               "running": sum(r["execution_state"] == "running" for r in subset),
               "not_started": sum(r["execution_state"] == "not_started" for r in subset)}
        for seed in (370101, 370201, 370301):
            flags = []
            for budget in (180, 360, 900):
                run = bykey[(problem["id"], seed, budget)]
                flags.append("-" if run["execution_state"] == "not_started" else "~" if run["execution_state"] == "running" else
                             "S" if run["public_status"] == "solved" else "F" if run["public_status"] == "no_answer_found" else "?")
            row[f"status_{seed}_180_360_900"] = "".join(flags)
        problemrows.append(row)
    write_csv("per-problem-status.csv", problemrows)
    current = peak = 0
    for _, delta in sorted(intervals):
        current += delta
        peak = max(peak, current)
    files = [{"path": str(path.relative_to(BASE)), "bytes": path.stat().st_size} for path in BASE.rglob("*") if path.is_file()]
    loads = [sample["load_average"] for receipt in receipts for sample in receipt.get("load_samples", [])]
    global_loads = [json.loads(line) for line in (EXEC / "load.jsonl").read_text().splitlines()]
    start = read(EXEC / "execution-start.json")
    preflight = read(EXEC / "preflight.json")
    summary = {"summary_utc": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
               "state": "stopped_frozen_contract_mismatch", "experiment_complete": False,
               "planned_runs": 360, "execution_states": dict(Counter(r["execution_state"] for r in rows)),
               "completed_public_statuses": dict(Counter(r["public_status"] for r in rows if r["execution_state"] == "completed")),
               "unknown_completed_runs": sum(bool(r["missing_reason"]) for r in rows),
               "missing_reasons": dict(Counter(r["missing_reason"] for r in rows if r["missing_reason"])),
               "budget_status_counts": {str(b): dict(Counter((r["public_status"] or r["execution_state"]) for r in rows if r["budget_seconds"] == b)) for b in (180, 360, 900)},
               "stratum_execution_states": {g: dict(Counter(r["execution_state"] for r in rows if r["stratum"] == g)) for g in "ABCD"},
               "fully_executed_problems": sum(r["completed"] == 9 for r in problemrows),
               "prediction_commit": preflight["prediction_commit"], "prediction_lock_sha256": sha(BASE / "prediction.lock.json"),
               "frozen_solver_commit": lock["frozen_solver_commit"], "initial_verification_utc": preflight["verified_utc"],
               "initial_locked_file_count": preflight["locked_file_count"], "initial_locked_source_count": preflight["source_manifest_file_count"],
               "current_mismatches": mismatches,
               "src_diff_vs_frozen_empty": not subprocess.check_output(["git", "diff", lock["frozen_solver_commit"], "--", "src"], cwd=ROOT).strip(),
               "current_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
               "execution_start_utc": start["execution_start_utc"], "last_completed_utc": max((r["end_utc"] for r in receipts), default=None),
               "first_frozen_contract_stop": read(EXEC / "supervisor-error.json"),
               "lane_cpus": preflight["cpu_allocation"]["lane_cpus"], "peak_parallel_completed_intervals": peak,
               "affinity_violation_receipts": sum(bool(r["affinity_violations"]) for r in receipts),
               "periodic_monitor_unavailable_runs": sum(bool(r.get("affinity_monitor_unavailable")) for r in receipts),
               "raw_receipt_hash_mismatches": raw_errors,
               "initial_load_average": start["load_average"],
               "per_run_load1_observed_min_max": [min(v[0] for v in loads), max(v[0] for v in loads)] if loads else None,
               "global_load_samples": len(global_loads),
               "global_load1_min_max": [min(r["load_average"][0] for r in global_loads), max(r["load_average"][0] for r in global_loads)],
               "largest_files": sorted(files, key=lambda r: r["bytes"], reverse=True)[:10],
               "files_over_locked_limit": [r for r in files if r["bytes"] > LIMIT],
               "grading_executed": False, "N": None, "R": None, "V": None,
               "prediction_verdicts": {"P1": "判定不能（実行未完・未採点）", "P2": "判定不能（実行未完・未採点）", "P3": "判定不能（実行未完・未採点）"},
               "solver_retries": 0, "prediction_selection_protocol_changed": False}
    save(BASE / "stopped-summary.json", summary)
    save(BASE / "unknown-runs.json", [row for row in rows if row["missing_reason"]])
    print(json.dumps({k: v for k, v in summary.items() if k not in ("largest_files", "first_frozen_contract_stop")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
