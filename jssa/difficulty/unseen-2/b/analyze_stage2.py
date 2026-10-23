"""Q30b exact-set results and explicit missingness, with no solver execution."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import statistics
import sys

sys.dont_write_bytecode = True
import execute_stage2 as stage

BASE, DEST, rr = stage.BASE, stage.DEST, stage.rr


def evidence(raw):
    result = raw.get("solver_result") or {}
    return ((result.get("q30b_storage_summary") or {}).get("diagnostic_evidence")
            or raw.get("diagnostic_evidence") or result.get("diagnostics") or {})


def classification(row):
    if row["missing_record"]:
        return "記録欠測"
    if row["matched"]:
        return "正答"
    if row["status"] == "invalid":
        return "DSL"
    if not row["normal_completion"]:
        return "実行系（探索・同定の判別不能）"
    if row["numeric_feasible"] or row["n_answers"]:
        return "同定・答え集合"
    return "探索・精密化・検証"


def collect():
    lock = stage.read(BASE / "prediction.lock.json")
    refs = {r["id"]: r["canonical_keys"] for r in stage.read(BASE / "audit/static.json")["geometric_references"]}
    missing = {(r["case_id"], r["seed"]): r for p in (DEST / "missing").glob("*.json") for r in [stage.read(p)]}
    rows = []
    for problem in lock["adopted_problems"]:
        cid = problem["id"]
        for seed in range(301, 306):
            path = DEST / "runs" / cid / f"{seed}.json"
            lifecycle = DEST / "run-lifecycle" / cid / f"{seed}.json"
            if not path.is_file() and not lifecycle.is_file() and (cid, seed) not in missing:
                continue
            raw = stage.read(path) if path.is_file() else {}
            life = stage.read(lifecycle) if lifecycle.is_file() else {}
            if not path.is_file() and not life.get("finished_at_utc") and (cid, seed) not in missing:
                continue  # Running is not missing.
            result = raw.get("solver_result") or {}
            diag = result.get("diagnostics") or {}
            out = rr.read_run_outcome(raw)
            actual = rr._answer_keys(result)
            absent = bool((cid, seed) in missing or raw.get("assessment_unavailable") or life.get("assessment_unavailable") or not path.is_file())
            ev = evidence(raw)
            pipeline = ev.get("pipeline_summary") or {}
            row = {"case_id": cid, "seed": seed, "n_variables": problem["n_variables"],
                   "reference": problem["geometric_reference"], "actual_keys": actual, "expected_keys": refs[cid],
                   "matched": None if absent else bool(out["normal_completion"] and actual == refs[cid]),
                   "runner_matched_without_missingness_overlay": bool(out["normal_completion"] and actual == refs[cid]),
                   "missing_record": absent, "missing_reason": missing.get((cid, seed), {}).get("reason") or raw.get("missing_reason") or life.get("missing_reason"),
                   "n_answers": len(actual), "extra_answers": sorted(set(actual) - set(refs[cid])),
                   "missing_answers": sorted(set(refs[cid]) - set(actual)),
                   "numeric_feasible": diag.get("numeric_feasible"), "exact_identified": diag.get("exact_identified"),
                   "solver_error": result.get("error"), "execution_contract_issues": raw.get("execution_contract_issues", []),
                   "cpu_affinity": raw.get("process", {}).get("actual_affinity"),
                   "returncode": raw.get("process", {}).get("returncode"),
                   "started_at_utc": life.get("started_at_utc"), "finished_at_utc": life.get("finished_at_utc"),
                   "record_sha256": stage.sha(path) if path.is_file() else None,
                   "record_bytes": path.stat().st_size if path.is_file() else None,
                   "diagnostic_evidence": {k: pipeline.get(k) for k in ("search", "refinement", "exact_assembly", "answer_candidate_values", "answer_extraction_candidate_ids")},
                   **out}
            row["classification"] = classification(row)
            rows.append(row)
    return lock, rows


def totals(rows, ids, planned_runs):
    selected = [r for r in rows if r["case_id"] in ids]
    counts = Counter(r["classification"] for r in selected)
    per = []
    for cid in ids:
        runs = [r for r in selected if r["case_id"] == cid]
        correct = sum(r["matched"] is True for r in runs)
        absent = sum(r["missing_record"] for r in runs)
        per.append({"case_id": cid, "correct": correct,
                    "observed_incorrect": sum(r["matched"] is False for r in runs),
                    "missing": absent, "recorded_attempts": len(runs),
                    "at_least_3_correct_confirmed": correct >= 3,
                    "at_least_3_possible_with_missing": correct + absent >= 3})
    correct = sum(r["matched"] is True for r in selected)
    return {"planned_runs": planned_runs, "recorded_attempts": len(selected), "correct": correct,
            "observed_incorrect": sum(r["matched"] is False for r in selected),
            "missing": sum(r["missing_record"] for r in selected),
            "correct_fraction_fixed_denominator": correct / planned_runs,
            "problems": len(ids), "problems_at_least_3_confirmed": sum(r["at_least_3_correct_confirmed"] for r in per),
            "problems_at_least_3_possible_with_missing": sum(r["at_least_3_possible_with_missing"] for r in per),
            "classification_counts": dict(counts), "per_problem": per}


def progress():
    lock, rows = collect()
    summary = totals(rows, lock["adopted_problem_ids"], 85)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_problem"}, ensure_ascii=False))
    for r in rows:
        if r["matched"] is not True:
            print(json.dumps({k: r[k] for k in ("case_id", "seed", "matched", "classification", "status", "numeric_feasible", "exact_identified", "failure_stage", "rejection_tags", "solver_error")}, ensure_ascii=False))


def csv_text(rows, fields):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row.get(k), (list, dict)) else row.get(k) for k in fields})
    return stream.getvalue()


def finalize():
    lock, verification = stage.verify_gate()
    batches = [stage.read(DEST / "batches" / f"{n:02d}-complete.json") for n in range(1, 26)]
    if not all(b["all_workers_joined"] for b in batches):
        raise RuntimeError("not all batches joined")
    _, rows = collect()
    if len(rows) != 85:
        raise RuntimeError("incomplete attempted-run inventory")
    # The frozen scorer is invoked without changes. Its raw false value for a
    # storage-missing result is explicitly overlaid with null in user reports.
    rr.assess_campaign(DEST, cases_path=BASE / "cases.jsonl")
    scored = {(r["case_id"], r["seed"]): r for line in (DEST / "assessment.jsonl").read_text().splitlines() for r in [json.loads(line)]}
    for row in rows:
        official = scored[row["case_id"], row["seed"]]
        if official["matched"] != row["runner_matched_without_missingness_overlay"]:
            raise RuntimeError("scoring discrepancy")
        raw = stage.read(DEST / "runs" / row["case_id"] / f'{row["seed"]}.json')
        if not all(raw.get("storage", {}).get(k) for k in ("read_run_outcome_preserved", "answer_keys_preserved")):
            raise RuntimeError("storage equivalence verification unavailable")
        if row["execution_contract_issues"]:
            raise RuntimeError("execution contract issue; inspect before reporting")
    main = totals(rows, lock["adopted_problem_ids"], 85)
    nonzero_ids = [p["id"] for p in lock["adopted_problems"] if p["n_variables"] > 0]
    auxiliary = totals(rows, nonzero_ids, 70)
    zero_ids = [p["id"] for p in lock["adopted_problems"] if p["n_variables"] == 0]
    zero = totals(rows, zero_ids, 15)
    lower_pass = main["correct"] >= 77 and main["problems_at_least_3_confirmed"] >= 16
    upper_pass = main["correct"] + main["missing"] >= 77 and main["problems_at_least_3_possible_with_missing"] >= 16
    decision = "成立" if lower_pass else ("欠測により判定不能" if upper_pass else "不成立")
    per_seed = {str(seed): {k: v for k, v in totals([r for r in rows if r["seed"] == seed], lock["adopted_problem_ids"], 17).items() if k not in {"per_problem", "problems_at_least_3_confirmed", "problems_at_least_3_possible_with_missing"}} for seed in range(301, 306)}
    events = []
    for row in rows:
        if row["started_at_utc"] and row["finished_at_utc"]:
            events += [(row["started_at_utc"], 1), (row["finished_at_utc"], -1)]
    concurrent, maximum = 0, 0
    for _, delta in sorted(events):
        concurrent += delta
        maximum = max(maximum, concurrent)
    if maximum > 4:
        raise RuntimeError("parallel cap exceeded")
    files = [p for p in DEST.rglob("*") if p.is_file()]
    oversize = [str(p.relative_to(BASE)) for p in files if p.stat().st_size >= 5_000_000]
    if oversize:
        raise RuntimeError("oversize output files: " + repr(oversize))
    seconds = [r["wall_seconds"] for r in rows if r["wall_seconds"] is not None]
    summary = {"created_at_utc": stage.now(), "prediction_decision": decision, "main": main,
               "nonzero_variable_subset": auxiliary, "zero_variable_subset": zero, "per_seed": per_seed,
               "point_prediction": lock["prediction"],
               "started_at_utc": stage.read(DEST / "execution-start.json")["started_at_utc"],
               "completed_at_utc": batches[-1]["completed_at_utc"],
               "observed_max_parallel_runs": maximum, "scored_by_unmodified_assess_campaign": True,
               "missingness_overlay": "matched=null for missing records; not classified as solver failures; fixed denominators maintained",
               "median_wall_seconds": statistics.median(seconds), "max_wall_seconds": max(seconds),
               "sum_wall_seconds": sum(seconds), "record_count": len(rows),
               "max_execution_file_bytes_before_final_report": max(p.stat().st_size for p in files),
               "execution_file_bytes_before_final_report": sum(p.stat().st_size for p in files),
               "final_lock_verification_passed": True}
    stage.save(BASE / "results.json", summary)
    with (BASE / "results.jsonl").open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
    fields = ["case_id", "seed", "n_variables", "matched", "missing_record", "classification", "status", "normal_completion", "n_answers", "numeric_feasible", "exact_identified", "wall_seconds", "failure_stage", "termination_reason", "rejection_tags", "actual_keys", "expected_keys"]
    (BASE / "results.csv").write_text(csv_text(rows, fields))
    problem_rows = []
    for p in main["per_problem"]:
        runs = [r for r in rows if r["case_id"] == p["case_id"]]
        problem_rows.append({**p, "n_variables": runs[0]["n_variables"], **{f'seed_{r["seed"]}': "missing" if r["missing_record"] else ("correct" if r["matched"] else "incorrect") for r in runs}})
    (BASE / "per-problem.csv").write_text(csv_text(problem_rows, list(problem_rows[0])))
    stage.save(BASE / "failure-classification.json", {"rule": "Observed stage classification, not proof that the DSL uniquely specifies the intended solution; existing semantic and independent-witness audits remain the DSL evidence.", "records": [r for r in rows if r["matched"] is not True]})
    stage.save(DEST / "verification-final.json", verification)
    stage.save(DEST / "completion.json", {"completed_at_utc": batches[-1]["completed_at_utc"], "reported_at_utc": stage.now(),
         "attempted_runs": 85, "correct": main["correct"], "observed_incorrect": main["observed_incorrect"],
         "missing": main["missing"], "all_25_batches_joined": True, "max_parallel": maximum,
         "solver_retry_count": 0, "prediction_decision": decision, "results_sha256": stage.sha(BASE / "results.jsonl")})
    rr.write_checksums(DEST)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["progress", "finalize"])
    args = parser.parse_args()
    progress() if args.action == "progress" else finalize()
