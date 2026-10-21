"""CPU-only timing snapshot; reads receipts/operational metadata, never answers.

Run again at final reporting time. --as-of fixes the wall-clock cutoff. Input
hashes identify a snapshot, not a historical recovery of subsequently changed
receipts. --verify-snapshot checks whether its inputs are still byte-identical.
No campaign helper is imported, so this cannot launch jobs or update a ledger.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
DEFAULT_RUN = HERE.parents[2] / "qwen/.runtime/night_recipe_search_20260929"


def iso(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()


def unix(value):
    return dt.datetime.fromisoformat(value).timestamp()


def union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end < start:
            raise ValueError("Reversed interval")
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def length(intervals):
    return sum(b - a for a, b in union(intervals))


def intersection(left, right):
    left, right = union(left), union(right)
    i = j = 0
    result = []
    while i < len(left) and j < len(right):
        a, b = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if a < b:
            result.append([a, b])
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return result


class Reader:
    def __init__(self):
        self.sources = {}

    def read(self, path):
        path = Path(path).resolve()
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Input changed while being read; rerun: {path}")
        self.sources[str(path)] = {
            "path": str(path), "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content), "mtime_ns": after.st_mtime_ns,
        }
        return json.loads(content)

    def fingerprint(self, path):
        path = Path(path).resolve()
        content = path.read_bytes()
        self.sources[str(path)] = {
            "path": str(path), "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content), "mtime_ns": path.stat().st_mtime_ns,
        }


def interval_record(path, data, category, archive=None):
    allowed = ("status", "start_unix", "end_unix", "elapsed_seconds")
    return {
        "receipt": str(path), "category": category, "archive": archive,
        "metadata": {key: data[key] for key in allowed if key in data},
    }


def build(run, as_of=None):
    read = Reader()
    clock = read.read(run / "clock.json")
    ledger = read.read(run / "gpu-wait-ledger.json")
    quiet_policy = read.read(run / "operational-amendment-006.json")
    read.read(run / "timing-policy.json")
    records, excluded, seen = [], [], set()
    # Do not recurse through train/final, recovery receipts, or shared guards:
    # those describe an execution already represented by the primary receipt.
    for directory, category in (("train", "training"), ("outputs", "generation")):
        for path in sorted((run / directory).glob("*/receipt.json")):
            data = read.read(path)
            record = interval_record(path, data, category)
            projection = any(
                data.get(key) for key in
                ("projection", "projection_of", "projected_from", "reused_from", "reused")
            ) or any("projection" in key.lower() for key in data)
            if projection or "start_unix" not in data:
                excluded.append({"receipt": str(path), "reason": "projection/reuse or no execution start"})
                continue
            identity = (category, data["start_unix"], data.get("end_unix"), data.get("driver_sha256"))
            if identity in seen:
                excluded.append({"receipt": str(path), "reason": "duplicate execution timestamps/driver"})
                continue
            seen.add(identity)
            records.append(record)

    failed = []
    for archive in sorted((run / "failed-attempts").iterdir()):
        if not archive.is_dir() or not archive.name.startswith(("train-", "eval-")):
            continue
        category = "training" if archive.name.startswith("train-") else "generation"
        paths = [p for p in archive.glob("*/receipt.json")
                 if p.parent.name != "shared-guard" and not p.parent.name.startswith("night20260929-")]
        if len(paths) != 1:
            failed.append({"archive": str(archive), "category": category,
                           "duration_lower_seconds": None, "duration_upper_seconds": None,
                           "limitation": "No unique primary archived receipt"})
            continue
        path = paths[0]
        data = read.read(path)
        record = interval_record(path, data, category, str(archive))
        start = data.get("start_unix")
        if start is None:
            record["limitation"] = "Primary start missing"
        elif data.get("end_unix") is not None:
            end = data["end_unix"]
            record.update(lower_interval=[start, end], upper_interval=[start, end],
                          duration_lower_seconds=end-start, duration_upper_seconds=end-start,
                          end_basis="primary receipt end_unix")
        else:
            event_path, status_path = archive / "priority-event.json", archive / "status.json"
            event = read.read(event_path) if event_path.exists() else {}
            status = read.read(status_path) if status_path.exists() else {}
            lower_end = unix(event["time"]) if event.get("time") else None
            upper_end = unix(status["time"]) if status.get("state") == "interrupted" else None
            record["interruption_evidence"] = {
                "event": str(event_path) if event else None,
                "event_utc": event.get("time"),
                "cleanup_status": str(status_path) if status else None,
                "cleanup_status_utc": status.get("time"),
                "wrapper_reported_elapsed_seconds": status.get("elapsed_seconds"),
            }
            if lower_end is not None and lower_end >= start:
                record.update(lower_interval=[start, lower_end], duration_lower_seconds=lower_end-start)
            if upper_end is not None and upper_end >= start:
                record.update(upper_interval=[start, upper_end], duration_upper_seconds=upper_end-start)
            record["end_basis"] = (
                "Driver end absent. Event detection is the lower episode bound; status time is "
                "the cleanup-complete upper bound under campaign/resume cleanup code. "
                "Wrapper elapsed is separate and includes guard startup."
            )
        failed.append(record)

    incident_path = run / "incidents/launcher-2563012-sigterm/incident.json"
    incident = read.read(incident_path) if incident_path.exists() else {}
    pause_path = run / "failed-attempts/eval-X512-2026093001-main-81920-common-attempt2/cause-observation.json"
    pause = read.read(pause_path) if pause_path.exists() else {}
    review_policy_path = run / "parallel-review-policy.json"
    review_policy = read.read(review_policy_path) if review_policy_path.exists() else {}
    # Only operational fields from this staffing policy are retained. No grades,
    # mapping, answer, score, or scientific outcome file is opened.
    for path in (Path(__file__), HERE / "campaign.py", HERE / "resume.py", HERE / "timing.py"):
        read.fingerprint(path)
    cutoff = time.time() if as_of is None else as_of
    start = unix(clock["start_utc"])
    if cutoff < start:
        raise ValueError("as-of precedes campaign start")
    intervals = {"successful_training": [], "successful_generation": [],
                 "failed_lower": [], "failed_upper": [], "contention_wait": []}
    summary = {}
    open_records = []
    for category in ("training", "generation"):
        completed = []
        for record in records:
            if record["category"] != category:
                continue
            data = record["metadata"]
            if data["start_unix"] > cutoff:
                excluded.append({"receipt": record["receipt"], "reason": "execution starts after as-of"})
                continue
            end = data.get("end_unix")
            if data.get("status") == "complete" and end is not None and end <= cutoff:
                record["receipt_wall_seconds"] = end - data["start_unix"]
                completed.append(record)
                intervals["successful_" + category].append([data["start_unix"], end])
            else:
                open_records.append({**record, "age_from_recorded_start_seconds": cutoff-data["start_unix"],
                                     "accounted_execution_seconds": None,
                                     "limitation": "Non-final receipt does not establish continuous liveness; not counted as completed or kernel-busy time"})
        summary["successful_" + category] = {
            "count": len(completed),
            "receipt_wall_duration_sum_seconds": sum(x["receipt_wall_seconds"] for x in completed),
            "reported_elapsed_sum_seconds": sum(x["metadata"].get("elapsed_seconds", 0) for x in completed),
            "reported_elapsed_available_count": sum("elapsed_seconds" in x["metadata"] for x in completed),
            "interval_union_seconds": length(intervals["successful_" + category]),
            "records": completed,
        }
    for record in failed:
        for side in ("lower", "upper"):
            interval = record.get(side + "_interval")
            if interval and interval[1] <= cutoff:
                intervals["failed_" + side].append(interval)
    summary["failed_or_interrupted"] = {
        "count": len(failed),
        "duration_lower_sum_seconds": sum(b-a for a, b in intervals["failed_lower"]),
        "duration_upper_sum_seconds": sum(b-a for a, b in intervals["failed_upper"]),
        "lower_bound_count": len(intervals["failed_lower"]), "upper_bound_count": len(intervals["failed_upper"]),
        "lower_interval_union_seconds": length(intervals["failed_lower"]),
        "upper_interval_union_seconds": length(intervals["failed_upper"]),
        "records": failed,
    }
    wait_records = []
    for index, entry in enumerate(ledger.get("closed_intervals", [])):
        a, b = unix(entry["start_utc"]), unix(entry["end_utc"])
        wait_records.append({**entry, "ledger_index": index, "timestamp_duration_seconds": b-a,
                             "declared_minus_timestamp_seconds": entry["seconds"]-(b-a)})
        if a <= cutoff:
            intervals["contention_wait"].append([max(a, start), min(b, cutoff)])
    if ledger.get("current_wait_started_utc"):
        a = unix(ledger["current_wait_started_utc"])
        if a <= cutoff:
            intervals["contention_wait"].append([max(a, start), cutoff])
    closed_sum = sum(x["seconds"] for x in ledger.get("closed_intervals", []))
    summary["contention_wait"] = {
        "closed_interval_count": len(wait_records), "closed_declared_sum_seconds": closed_sum,
        "ledger_closed_wait_seconds": ledger.get("closed_wait_seconds"),
        "ledger_total_minus_interval_sum_seconds": ledger.get("closed_wait_seconds", 0)-closed_sum,
        "interval_union_seconds_at_cutoff": length(intervals["contention_wait"]),
        "current_wait_started_utc": ledger.get("current_wait_started_utc"),
        "records": wait_records,
        "meaning": "Recorded admission contention waiting, with polling resolution; not all external GPU residency or measured GPU-kernel busy time. Quiet-period waits are excluded by timing.end_wait().",
    }
    # Quiet status is overwritten; retain the policy and an explicitly derived
    # minimum, not invented timestamped intervals or a measured total.
    quiet_from = unix(quiet_policy["time"])
    admitted = [x for x in records + failed if quiet_from <= x.get("metadata", {}).get("start_unix", -1) <= cutoff]
    summary["quiet_periods"] = {
        "policy_seconds_per_admission": quiet_policy["quiet_seconds"],
        "policy_record_utc": quiet_policy["time"], "observed_postpolicy_admission_count": len(admitted),
        "policy_implied_minimum_seconds": len(admitted)*quiet_policy["quiet_seconds"],
        "measured_total_seconds": None, "timestamped_intervals": [],
        "limitation": "Derived minimum assumes documented wrapper admission policy applied. Exact quiet starts, polling overshoot, resets and additional abandoned waits were not retained; never subtract this minimum from the wall partition.",
        "admission_receipts": [x["receipt"] for x in admitted],
    }
    known = intervals["successful_training"] + intervals["successful_generation"] + intervals["failed_lower"] + intervals["contention_wait"]
    known_union = union(known)
    overlap_checks = {}
    categories = ["successful_training", "successful_generation", "failed_lower", "contention_wait"]
    for i, left in enumerate(categories):
        for right in categories[i+1:]:
            overlap_checks[left + "__" + right] = length(intersection(intervals[left], intervals[right]))
    pause_anchors = {
        "automatic_priority_event_utc": pause.get("event", {}).get("time"),
        "automation_updated_utc": pause.get("automation_updated_utc"),
        "paused_observation_utc": pause.get("time"),
        "documented_resume_policy_utc": review_policy.get("time"),
        "user_confirmation": review_policy.get("manual_pause"),
        "actual_user_pause_seconds": None,
        "limitation": "Anchors do not record the exact pause/resume actions. No exact pause duration is imputed or added to job/wait sums.",
    }
    if pause_anchors["automation_updated_utc"] and pause_anchors["documented_resume_policy_utc"]:
        pause_anchors["recorded_anchor_span_seconds_not_exact_pause_duration"] = unix(pause_anchors["documented_resume_policy_utc"])-unix(pause_anchors["automation_updated_utc"])
    monitoring = {
        "incident_path": str(incident_path), "observed_utc": incident.get("observed_utc"),
        "resolved_utc": incident.get("resolved_utc"), "guard_finished_utc": incident.get("guard_finished_utc"),
        "monitoring_gap_seconds": None, "termination_time": None, "signal_sender": None,
        "limitation": "The same S512 attempt completed and is counted once as successful generation. Unknown monitoring gap is an overlapping annotation, not an additional failed job or additive time category.",
    }
    return {
        "schema_version": 1, "artifact_role": "preparatory_timing_snapshot_not_campaign_completion",
        "observed_utc": iso(cutoff), "as_of_unix": cutoff, "campaign_start_utc": clock["start_utc"],
        "wall_elapsed_seconds": cutoff-start, "runtime_root": str(run),
        "scope": "CPU-only receipt/operational-metadata accounting; no GPU/process control, mappings, grades, answer bodies or scientific outcomes",
        "time_definition": "Receipt/job wall elapsed includes startup, CPU work and waiting inside the job. It is not GPU kernel busy time. reported_elapsed uses each driver's own timer and may differ slightly from end_unix-start_unix.",
        "summary": summary, "open_or_nonfinal_execution_records": open_records,
        "excluded_duplicate_projection_or_nonexecution_records": excluded,
        "user_pause": pause_anchors, "uncertain_monitoring_gap": monitoring,
        "wall_partition": {
            "known_lower_bound_union_seconds": length(known_union),
            "known_lower_bound_union_intervals": known_union,
            "unclassified_wall_seconds": cutoff-start-length(known_union),
            "pairwise_overlap_seconds": overlap_checks,
            "limitation": "Residual includes open jobs, preparation, quiet periods, recovery/control work, manual pause and unrecorded overhead; it is not attributed to any one cause. Failure upper bounds, quiet minima and monitoring/pause annotations are not added to the union.",
        },
        "deduplication": "Only train/*/receipt.json and outputs/*/receipt.json plus one primary receipt per failed-attempt archive. Excludes training final copies, shared guard receipts, retry/recovery/projection summaries. Identical category/start/end/driver execution identities are counted once.",
        "source_fingerprints": list(read.sources.values()),
        "rerun_command": f"python3 {Path(__file__).resolve()} --runtime {run}",
        "reproduce_cutoff_command": f"python3 {Path(__file__).resolve()} --runtime {run} --as-of {iso(cutoff)}",
        "limitations": [
            "Whole-system/per-process GPU utilization samples are not available; do not label these sums GPU active/busy hours.",
            "Input hashes permit source-drift checks. Reusing an old as-of cannot recover an overwritten receipt/ledger; preserve the JSON snapshot itself.",
            "The archive hash manifest coverage limitations remain in operations-audit.json; new hashes do not repair historical omissions.",
            "Prelaunch refusal has no job receipt duration and is not assigned invented execution time.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--as-of", help="ISO-8601 UTC cutoff; default is end of input collection")
    parser.add_argument("--verify-snapshot", type=Path, help="Read-only source hash drift check")
    args = parser.parse_args()
    if args.verify_snapshot:
        saved = json.loads(args.verify_snapshot.read_text())
        drift = []
        for entry in saved["source_fingerprints"]:
            path = Path(entry["path"])
            current = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            if current != entry["sha256"]:
                drift.append({"path": str(path), "expected": entry["sha256"], "actual": current})
        print(json.dumps({"checked": len(saved["source_fingerprints"]), "drift": drift}, indent=2))
        return
    result = build(args.runtime.resolve(), unix(args.as_of) if args.as_of else None)
    output = args.runtime / "timing-accounting.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"snapshot": str(output), "observed_utc": result["observed_utc"],
                      "wall_elapsed_seconds": result["wall_elapsed_seconds"],
                      "successful_training_seconds": result["summary"]["successful_training"]["receipt_wall_duration_sum_seconds"],
                      "successful_generation_seconds": result["summary"]["successful_generation"]["receipt_wall_duration_sum_seconds"],
                      "contention_wait_seconds": result["summary"]["contention_wait"]["interval_union_seconds_at_cutoff"],
                      "open_records": len(result["open_or_nonfinal_execution_records"])}, indent=2))


if __name__ == "__main__":
    main()
