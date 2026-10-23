"""Reassess all Q30a saved descriptors with the fixed score.py; no solver runs."""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
from collections import Counter
from pathlib import Path
from statistics import median

from execute_stage2 import BASE, DEST, assess, encoded_identity, now, read, rr, save, sha, verify_gate


def category(raw, assessment):
    if assessment is None:
        return "記録欠落"
    if assessment["matched"]:
        return "正解"
    if assessment.get("status") == "invalid_problem":
        return "DSL"
    stage = assessment.get("failure_stage")
    if stage == "search_or_refinement":
        return "探索"
    if stage in {"exactification", "final_verification"}:
        return "同定"
    if assessment["normal_completion"]:
        return "同定・解集合不一致"
    return "実行系（要個別確認）"


def csv_file(path, rows):
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    payload = text.getvalue().encode()
    if len(payload) >= 5_000_000:
        raise RuntimeError("CSV too large")
    Path(path).write_bytes(payload)


def main():
    lock, integrity = verify_gate()
    cases = [json.loads(line) for line in (BASE / "cases.jsonl").read_text().splitlines() if line.strip()]
    preflight = read(DEST / "preflight.json")
    plan = [task for batch in preflight["batches"] for task in batch]
    expected = {(task["case_id"], task["seed"]) for task in plan}
    if len(plan) != 85 or len(expected) != 85:
        raise RuntimeError("plan is not 17 x 5")
    observed = {(p.parent.name, int(p.stem)) for p in (DEST / "runs").glob("*/*.json")}
    if observed - expected:
        raise RuntimeError("unexpected extra execution records")
    for n in range(1, len(preflight["batches"]) + 1):
        if not read(DEST / "batches" / f"{n:02d}-complete.json")["all_workers_joined"]:
            raise RuntimeError("campaign not finished")
    per_run, assessments, failures, events = [], [], [], []
    contract_check_failures, raw_sizes, storage_errors = [], [], []
    problem_hashes = {c["id"]: encoded_identity(c["dsl"])["sha256"] for c in cases}
    preservation_checks = 0
    for task in plan:
        cid, seed = task["case_id"], task["seed"]
        path = DEST / "runs" / cid / f"{seed}.json"
        lifecycle_path = DEST / "lifecycle" / cid / f"{seed}.json"
        lifecycle = read(lifecycle_path) if lifecycle_path.exists() else {}
        raw = read(path) if path.exists() else {}
        assessment = raw.get("assessment") if not raw.get("assessment_unavailable") else None
        if path.exists() and lifecycle.get("record_sha256") and sha(path) != lifecycle["record_sha256"]:
            raise RuntimeError("saved record hash changed: " + str(path))
        if assessment is not None and raw.get("storage", {}).get("schema") == "q30a-summary-v1":
            rescored = assess(raw)
            if rescored != assessment:
                raise RuntimeError("fixed scorer disagrees with saved score: " + str(path))
            preservation_checks += 1
        if lifecycle.get("started_at_utc") and lifecycle.get("finished_at_utc"):
            events.extend([(lifecycle["started_at_utc"], 1), (lifecycle["finished_at_utc"], -1)])
        a = assessment or {}
        if raw.get("storage", {}).get("raw_canonical"):
            raw_sizes.append(raw["storage"]["raw_canonical"]["bytes"])
        if raw.get("storage_error"):
            storage_errors.append({**task, "error": raw["storage_error"]})
        checks = {
            "frozen_source": raw.get("source_hash") == lock["execution"]["source_tree_hash"],
            "fixed_problem": raw.get("problem_hash") == problem_hashes[cid],
            "180_seconds_one_core": raw.get("config", {}).get("time_limit_seconds") == 180 and raw.get("config", {}).get("cores") == 1,
            "cpu_affinity": raw.get("process", {}).get("actual_affinity") == [lifecycle.get("cpu")],
            "outer_process_completed": raw.get("process", {}).get("returncode") == 0 and raw.get("process", {}).get("timed_out") is False,
            "runner_contract_clear": not raw.get("execution_contract_issues"),
            "all_descriptors_retained": raw.get("storage", {}).get("all_answer_descriptors_retained") is True,
        }
        if not all(checks.values()):
            contract_check_failures.append({**task, "checks": checks})
        diagnostic = (raw.get("solver_result") or {}).get("diagnostics", {})
        kind = category(raw, assessment)
        row = {**task, "classification": kind, "matched": a.get("matched"),
               "record_missing": assessment is None, "status": a.get("status"),
               "normal_completion": a.get("normal_completion"), "failure_stage": a.get("failure_stage"),
               "geometric_matched": a.get("geometric_matched"), "official_output_matched": a.get("official_output_matched"),
               "n_answers": a.get("n_answers"), "extra_answers": a.get("extra"),
               "converted_outputs": json.dumps(a.get("converted_outputs", []), ensure_ascii=False),
               "termination_reason": a.get("termination_reason"), "cpu": lifecycle.get("cpu"),
               "started_at_utc": lifecycle.get("started_at_utc"), "finished_at_utc": lifecycle.get("finished_at_utc"),
               "wall_seconds": a.get("wall_seconds"), "process_wall_seconds": a.get("process_wall_seconds"),
               "cpu_seconds": a.get("cpu_seconds"), "peak_rss_bytes": a.get("peak_rss_bytes"),
               "numeric_feasible": diagnostic.get("numeric_feasible"), "exact_identified": diagnostic.get("exact_identified"),
               "record_bytes": path.stat().st_size if path.exists() else None,
               "execution_contract_issues": json.dumps(raw.get("execution_contract_issues", []))}
        per_run.append(row)
        assessments.append({**task, "assessment": assessment, "classification": kind,
                            "record_sha256": sha(path) if path.exists() else None})
        if kind != "正解":
            failures.append({**row, "assessment": assessment, "solver_error": (raw.get("solver_result") or {}).get("error"),
                             "runner_exception": lifecycle.get("runner_exception"), "process": raw.get("process"),
                             "diagnostics": diagnostic, "source_record": str(path.relative_to(BASE)),
                             "exact_assembly_summary": raw.get("diagnostic_evidence", {}).get("pipeline_summary", {}).get("exact_assembly")})
    problems = []
    for c in cases:
        rows = [r for r in per_run if r["case_id"] == c["id"]]
        successes = sum(r["matched"] is True for r in rows)
        missing = sum(r["record_missing"] for r in rows)
        prediction = next(p["predicted_successes_out_of_5"] for p in lock["adopted_problems"] if p["id"] == c["id"])
        problems.append({"case_id": c["id"], "variables": len(c["dsl"]["variables"]), "predicted_correct": prediction,
                         **{f"seed_{r['seed']}": "欠落" if r["record_missing"] else "○" if r["matched"] else "×" for r in rows},
                         "correct": successes, "observed_failures": len(rows) - successes - missing, "missing": missing,
                         "at_least_3_of_5_confirmed": successes >= 3,
                         "failure_categories": json.dumps(dict(Counter(r["classification"] for r in rows if r["classification"] != "正解")), ensure_ascii=False)})
    def aggregate(ids):
        selected = [r for r in per_run if r["case_id"] in ids]
        prob = [p for p in problems if p["case_id"] in ids]
        correct = sum(r["matched"] is True for r in selected)
        missing = sum(r["record_missing"] for r in selected)
        return {"problems": len(ids), "runs": len(selected), "correct": correct,
                "observed_failures": len(selected) - correct - missing, "missing": missing,
                "correct_fraction_fixed_denominator": correct / len(selected),
                "possible_correct_count": [correct, correct + missing],
                "problems_at_least_3_of_5": sum(p["correct"] >= 3 for p in prob),
                "possible_problems_at_least_3_of_5": [sum(p["correct"] >= 3 for p in prob), sum(p["correct"] + p["missing"] >= 3 for p in prob)],
                "problems_5_of_5": sum(p["correct"] == 5 for p in prob),
                "problems_at_least_1_of_5": sum(p["correct"] >= 1 for p in prob),
                "classifications": dict(Counter(r["classification"] for r in selected))}
    overall = aggregate([c["id"] for c in cases])
    auxiliary = aggregate([c["id"] for c in cases if c["dsl"]["variables"]])
    per_seed = []
    for seed in lock["execution"]["seeds"]:
        rows = [r for r in per_run if r["seed"] == seed]
        per_seed.append({"seed": seed, "correct": sum(r["matched"] is True for r in rows), "runs": len(rows),
                         "missing": sum(r["record_missing"] for r in rows),
                         "correct_excluding_zero_variables": sum(r["matched"] is True for r in rows if next(p for p in problems if p["case_id"] == r["case_id"])["variables"] > 0)})
    concurrency = peak = 0
    for _, delta in sorted(events):
        concurrency += delta
        peak = max(peak, concurrency)
    if concurrency or peak > 4:
        raise RuntimeError("invalid concurrency history")
    def decision(lower, upper, threshold):
        return "成立" if lower >= threshold else "不成立" if upper < threshold else "欠落のため判定不能"
    prediction_result = {
        "run_threshold": 73, "problem_threshold": 15,
        "run_decision": decision(*overall["possible_correct_count"], 73),
        "problem_decision": decision(*overall["possible_problems_at_least_3_of_5"], 15),
        "run_point_prediction": 76, "run_difference": overall["correct"] - 76,
        "problem_point_prediction": 16, "problem_difference": overall["problems_at_least_3_of_5"] - 16,
        "run_within_subjective_interval": 65 <= overall["correct"] <= 82,
        "problem_within_subjective_interval": 14 <= overall["problems_at_least_3_of_5"] <= 17,
    }
    metrics = {}
    for key in ("wall_seconds", "process_wall_seconds", "cpu_seconds", "peak_rss_bytes"):
        values = [r[key] for r in per_run if r[key] is not None]
        metrics[key] = {"count": len(values), "sum": sum(values), "min": min(values), "median": median(values), "max": max(values)} if values else {}
    correct_times = [r["wall_seconds"] for r in per_run if r["matched"] is True and r["wall_seconds"] is not None]
    metrics["correct_runs"] = {"count": len(correct_times), "median_seconds": median(correct_times) if correct_times else None,
                               "max_seconds": max(correct_times) if correct_times else None,
                               "within_10_seconds": sum(t <= 10 for t in correct_times),
                               "within_30_seconds": sum(t <= 30 for t in correct_times)}
    start = read(DEST / "execution-start.json")["started_at_utc"]
    finish = max(r["finished_at_utc"] for r in per_run if r["finished_at_utc"])
    result = {"created_at_utc": now(), "started_at_utc": start, "finished_at_utc": finish,
              "campaign_elapsed_seconds": (dt.datetime.fromisoformat(finish) - dt.datetime.fromisoformat(start)).total_seconds(),
              "overall": overall, "excluding_zero_variables": auxiliary, "per_seed": per_seed,
              "prediction": prediction_result, "metrics": metrics, "maximum_observed_parallel_runs": peak,
              "scoring_reproduction_checks": preservation_checks, "all_input_hashes_still_match": True,
              "per_run_contract_audit": {"checked": len(per_run), "failures": contract_check_failures},
              "storage_errors": storage_errors, "largest_run_summary_bytes": max(r["record_bytes"] or 0 for r in per_run),
              "largest_transient_raw_canonical_bytes": max(raw_sizes) if raw_sizes else None,
              "cpus": preflight["cpus"], "all_answer_descriptors_retained": all(r.get("assessment") is not None for r in assessments)}
    csv_file(BASE / "per-run.csv", per_run)
    csv_file(BASE / "per-problem.csv", problems)
    csv_file(BASE / "per-seed.csv", per_seed)
    save(BASE / "summary.json", result)
    # One diagnostic summary per failed run, avoiding an oversized aggregate file.
    for f in failures:
        save(DEST / "failure-diagnostics" / f'{f["case_id"]}-{f["seed"]}.json', f)
    save(DEST / "final-integrity.json", integrity)
    save(DEST / "completion.json", {"completed_at_utc": now(), "planned_runs": 85, "saved_records": len(observed),
         "scored_records": 85 - overall["missing"], "no_retries": True, "maximum_parallel": peak,
         "all_input_hashes_still_match": True})
    files = [p for p in DEST.rglob("*") if p.is_file()]
    sizes = {str(p.relative_to(DEST)): p.stat().st_size for p in files}
    if max(sizes.values()) >= 5_000_000:
        raise RuntimeError("oversized execution file")
    save(DEST / "file-audit.json", {"checked_at_utc": now(), "file_count": len(files), "total_bytes": sum(sizes.values()),
         "largest_file_bytes": max(sizes.values()), "files_sha256": {str(p.relative_to(DEST)): sha(p) for p in files},
         "files_bytes": sizes, "all_files_below_5MB": True})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
