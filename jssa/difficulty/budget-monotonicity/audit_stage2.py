"""Final read-only experiment audit; write only its small audit receipt."""
from __future__ import annotations

from collections import Counter
import json
import subprocess

import isolated_stage2 as execution


def audit():
    base, dest = execution.BASE, execution.EXEC
    preflight = execution.read(dest / "preflight.json")
    resumed = execution.read(execution.RESUME / "preflight.json")
    baseline = execution.read(execution.RESUME / "baseline.json")
    original_keys = set(baseline["completed_job_keys"])
    current = execution.verify()
    preservation = execution.verify_baseline()
    all_jobs = execution.jobs()
    issues, intervals, completed = [], [], []
    if current["adapter_sha256"] != resumed["adapter_sha256"]:
        issues.append({"issue": "isolated_adapter_changed"})
    if execution.sha(base / "execute_stage2.py") != preflight["adapter_sha256"]:
        issues.append({"issue": "original_executor_changed"})
    previous = {}
    for job in all_jobs:
        receiptfile = execution.receipt_path(job)
        if not receiptfile.exists():
            issues.append({"job": execution.key(job), "issue": "missing_completion_receipt"})
            continue
        receipt = execution.read(receiptfile)
        completed.append(receipt)
        start = execution.read(execution.receipt_path(job, "-start"))
        cpu = preflight["cpu_allocation"]["lane_cpus"][job["lane"]]
        if receipt["job"] != job or start["job"] != job:
            issues.append({"job": execution.key(job), "issue": "job_identity_changed"})
        if receipt["cpu"] != cpu or start["affinity"] != [cpu] or receipt["affinity_violations"]:
            issues.append({"job": execution.key(job), "issue": "cpu_affinity_violation"})
        expected_adapter = (preflight if execution.key(job) in original_keys else resumed)["adapter_sha256"]
        if receipt["adapter_sha256"] != expected_adapter or start["adapter_sha256"] != expected_adapter or receipt["prediction_lock_sha256"] != execution.LOCK_SHA:
            issues.append({"job": execution.key(job), "issue": "adapter_or_lock_changed"})
        if execution.key(job) not in original_keys and (
            receipt.get("runtime_checkout") != str(execution.ROOT)
            or receipt.get("scorer_import_path") != str(execution.ROOT / "benchmarks/research_runner.py")
        ):
            issues.append({"job": execution.key(job), "issue": "resumed_runtime_checkout_mismatch"})
        if execution.sha(execution.raw_path(job)) != receipt["raw_sha256"]:
            issues.append({"job": execution.key(job), "issue": "raw_bytes_changed_after_completion"})
        if receipt["start_utc"] != start["start_utc"] or receipt["end_utc"] < receipt["start_utc"]:
            issues.append({"job": execution.key(job), "issue": "invalid_time_receipt"})
        if job["lane"] in previous and previous[job["lane"]]["end_utc"] > receipt["start_utc"]:
            issues.append({"job": execution.key(job), "issue": "lane_order_overlap"})
        previous[job["lane"]] = receipt
        intervals.extend([(receipt["start_utc"], 1), (receipt["end_utc"], -1)])
        raw = execution.read(execution.raw_path(job))
        if raw.get("case_id") != job["id"] or raw.get("seed") != job["seed"]:
            issues.append({"job": execution.key(job), "issue": "raw_identity_mismatch"})
        if raw.get("config", {}).get("time_limit_seconds") != job["time_limit_seconds"] or raw.get("config", {}).get("cores") != 1:
            issues.append({"job": execution.key(job), "issue": "raw_budget_or_core_mismatch"})
    running = peak = 0
    for _, delta in sorted(intervals):
        running += delta
        peak = max(peak, running)
    if peak > 4:
        issues.append({"issue": "parallel_limit_exceeded", "observed": peak})
    expected_raw = {execution.raw_path(job).resolve() for job in all_jobs}
    actual_raw = {p.resolve() for p in (base / "campaign").glob("*/*/runs/*/*.json")}
    unexpected = sorted(str(p.relative_to(base)) for p in actual_raw - expected_raw)
    if unexpected:
        issues.append({"issue": "unplanned_raw_files", "files": unexpected})
    files = [{"path": str(p.relative_to(base)), "bytes": p.stat().st_size} for p in base.rglob("*") if p.is_file()]
    large = [p for p in files if p["bytes"] > execution.LIMIT]
    if large:
        issues.append({"issue": "file_size_limit_exceeded", "files": large})
    tracked_raw = subprocess.check_output(
        ["git", "ls-files", "--", str(base.relative_to(execution.SHARED_ROOT) / "campaign" / "*" / "*" / "runs")],
        cwd=execution.SHARED_ROOT, timeout=30,
    ).decode().splitlines()
    if tracked_raw:
        issues.append({"issue": "raw_files_tracked_by_git", "files": tracked_raw})
    result = {"audit_utc": execution.now(), "complete": len(completed) == 360, "issues": issues,
              "locked_files_verified": current["locked_file_count"], "locked_sources_verified": current["source_manifest_file_count"],
              "prediction_lock_sha256": execution.LOCK_SHA, "source_hash": current["runtime_fingerprint"]["source_hash"],
              "adapter_sha256_unchanged": current["adapter_sha256"] == resumed["adapter_sha256"],
              "original_executor_sha256_unchanged": execution.sha(base / "execute_stage2.py") == preflight["adapter_sha256"],
              "pre_resume_preservation": preservation,
              "runtime_checkout": str(execution.ROOT), "frozen_scorer_sha256": current["scorer_sha256"],
              "planned_jobs": 360, "start_receipts": len(list((dest / "receipts").glob("*-start.json"))),
              "completed_receipts": len(completed), "raw_files": len(actual_raw), "peak_parallel_jobs_from_utc_intervals": peak,
              "lane_cpus": preflight["cpu_allocation"]["lane_cpus"],
              "jobs_completed_by_lane": dict(Counter(r["job"]["lane"] for r in completed)),
              "observed_affinity_violation_runs": sum(bool(r["affinity_violations"]) for r in completed),
              "periodic_affinity_monitor_unavailable_runs": sum(bool(r.get("affinity_monitor_unavailable")) for r in completed),
              "execution_contract_issue_runs": sum(bool(execution.read(execution.raw_path(r["job"])).get("execution_contract_issues")) for r in completed),
              "execution_contract_issue_counts": dict(Counter(issue for r in completed for issue in execution.read(execution.raw_path(r["job"])).get("execution_contract_issues", []))),
              "largest_files": sorted(files, key=lambda r: r["bytes"], reverse=True)[:10],
              "file_count_at_audit": len(files), "file_limit_bytes": execution.LIMIT,
              "tracked_raw_file_count": len(tracked_raw), "raw_files_not_committed": not tracked_raw}
    execution.save(base / "integrity-audit.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if issues or not result["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    audit()
