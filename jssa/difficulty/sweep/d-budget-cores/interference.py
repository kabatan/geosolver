"""Describe overlap with recorded Q37 jobs; no new solver work or causal correction."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]


def stamp(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def union_seconds(intervals):
    end, total = float("-inf"), 0.0
    for lo, hi in sorted(intervals):
        total += max(0.0, hi - max(lo, end))
        end = max(end, hi)
    return total


def main():
    manifest = json.loads((BASE / "manifest.json").read_text())
    ours = [json.loads(p.read_text()) for p in (BASE / "receipts").glob("*.json")]
    assert len(ours) == len(manifest["jobs"]), "finish the fixed sweep first"
    first = min(stamp(r["started_utc"]) for r in ours)
    last = max(stamp(r["finished_utc"]) for r in ours)
    others = []
    for path in sorted((ROOT / "jssa/difficulty/budget-monotonicity/execution/receipts").glob("lane*.json")):
        if path.name.endswith("-start.json"):
            continue
        data = path.read_bytes()
        r = json.loads(data)
        if not r.get("start_utc") or not r.get("end_utc"):
            continue
        if stamp(r["end_utc"]) <= first or stamp(r["start_utc"]) >= last:
            continue
        if r.get("affinity") != [r.get("cpu")] or r.get("affinity_violations"):
            continue
        others.append({"task": "Q37", "path": str(path.relative_to(ROOT)),
                       "sha256": hashlib.sha256(data).hexdigest(), "cpu": r["cpu"],
                       "start_utc": r["start_utc"], "end_utc": r["end_utc"],
                       "affinity": r["affinity"]})
    rows = []
    for r in sorted(ours, key=lambda r: r["job"]):
        lo, hi = stamp(r["started_utc"]), stamp(r["finished_utc"])
        overlaps, references = [], []
        for other in others:
            a, b = max(lo, stamp(other["start_utc"])), min(hi, stamp(other["end_utc"]))
            if other["cpu"] == r["cpu"] and b > a:
                overlaps.append((a, b))
                references.append(other["path"])
        seconds = union_seconds(overlaps)
        rows.append({"job": r["job"], "id": r["id"], "seed": r["seed"], "budget": r["budget"],
                     "cores_requested": r["cores"], "cpu": r["cpu"],
                     "recorded_interval_seconds": hi-lo, "q37_same_cpu_overlap_seconds": seconds,
                     "q37_same_cpu_overlap_fraction": seconds/(hi-lo),
                     "q37_receipts": json.dumps(references, separators=(",", ":"))})
    with (BASE / "per-run-interference.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    process_path = Path(manifest["raw_root"]) / "resume-host-processes.json"
    summary = {"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "meaning": "Overlap of recorded job intervals assigned to the same logical CPU, not measured scheduler wait or exclusive causal attribution.",
               "coverage": "Completed Q37 receipts only. Ongoing/missing Q37 receipts and all other jobs are not included in overlap totals; counts are lower bounds.",
               "worker_cpu_caveat": "Q43d process_info.cpu_seconds uses time.process_time() in the worker and excludes symbolic child processes; CPU/wall is not a host-contention estimator.",
               "host_process_snapshot": str(process_path),
               "host_process_snapshot_sha256": hashlib.sha256(process_path.read_bytes()).hexdigest(),
               "q43d_jobs_with_recorded_q37_same_cpu_overlap": sum(r["q37_same_cpu_overlap_seconds"] > 0 for r in rows),
               "q43d_jobs": len(rows), "other_receipt_intervals": others}
    (BASE / "interference.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "other_receipt_intervals"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
