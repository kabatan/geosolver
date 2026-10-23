"""Audit the 31 new receipts, using unchanged score.assess; never search or retry."""
from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import traceback

sys.dont_write_bytecode = True
import execute_supplement as outer

BASE, ROOT, WORK, DEST = outer.BASE, outer.ROOT, outer.WORK, outer.DEST


def stamp(value):
    parsed = dt.datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    return parsed


def csv_new(path, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    data = stream.getvalue().encode()
    assert len(data) < 5_000_000
    with path.open("xb") as target:
        target.write(data)


def count(rows):
    return {"correct": sum(r["matched"] for r in rows), "runs": len(rows),
            "saved_summaries": sum(r["summary_available"] for r in rows),
            "summary_save_failures": sum(not r["summary_available"] for r in rows),
            "solver_outputs_available": sum(r["solver_output_available"] for r in rows),
            "output_record_missing": sum(not r["solver_output_available"] for r in rows),
            "normal_completion": sum(r["normal_completion"] for r in rows),
            "no_answer_found": sum(r["status"] == "no_answer_found" for r in rows),
            "abnormal_or_missing": sum(not r["normal_completion"] for r in rows)}


def comparison(name, prediction, rows):
    c = count(rows)
    assert c["runs"] == prediction["runs"]
    interval = prediction.get("subjective_90_percent_count_interval")
    point = prediction["correct_point"]
    return {"name": name, **c, "predicted_correct": point,
            "difference_from_point": c["correct"] - point,
            "point_exactly_met": c["correct"] == point,
            "interval_low": interval[0] if interval else None,
            "interval_high": interval[1] if interval else None,
            "inside_fixed_interval": interval[0] <= c["correct"] <= interval[1] if interval else None}


def floor_reproduction(lock):
    import mpmath
    import sympy as sp
    from geosolver.problem.ir.compiler import safe_eval_expr_hp
    from geosolver.runtime.integrity import source_tree_hash
    from score import convert
    original_path = outer.runner.CORPUS / "dsl/AIME-1996-15.json"
    rewritten_path = BASE / "dsl/AIME-1996-15.json"
    original = outer.read(original_path)["target"]
    rewritten = outer.read(rewritten_path)["target"]
    assert original == "(1000*r) // 1" and rewritten == "r"
    with mpmath.mp.workdps(100):
        context = {"r": mpmath.mp.mpf(7) / 9, "mpf": mpmath.mp.mpf}
        try:
            safe_eval_expr_hp(original, context)
        except Exception as error:
            error_info = {"exception_type": type(error).__name__, "message": str(error),
                          "cause_type": type(error.__cause__).__name__,
                          "cause_message": str(error.__cause__),
                          "traceback_excerpt": traceback.format_exc()[-4000:]}
        else:
            raise AssertionError("the frozen floor bug did not reproduce")
        assert error_info["cause_type"] == "TypeError"
        assert "mpf" in error_info["cause_message"] and "//" in error_info["cause_message"]
        value = safe_eval_expr_hp(rewritten, context)
        assert value == context["r"]
        converted = convert(sp.Rational(7, 9), "floor_1000")
        assert converted == 777
        return {"reproduced_at_utc": outer.now(), "frozen_commit": lock["frozen_commit"],
                "source_hash": source_tree_hash(), "decimal_precision": 100,
                "method": "Direct frozen HP evaluator call at the pre-existing r=7/9 witness; no solver/search invocation",
                "original_dsl_sha256": outer.sha(original_path), "original_target": original,
                "rewritten_dsl_sha256": outer.sha(rewritten_path), "rewritten_target": rewritten,
                "original_target_error": error_info,
                "rewritten_target_value": mpmath.mp.nstr(value, 100),
                "rewritten_target_error": None, "fixed_score_conversion": str(converted),
                "score_sha256": outer.sha(BASE / "score.py"),
                "solver_search_executed": False, "solver_inputs_modified": False,
                "does_not_establish_cause_of_every_original_search_failure": True}


def main():
    outer.file_limits()
    lock, gate = outer.verify_gate()
    runtime = outer.verify_runtime(lock)
    from score import assess
    plan = lock["execution_plan"]
    manifest = outer.read(DEST / "execution-manifest.json")
    assert manifest["prediction_lock_sha256"] == outer.LOCK_SHA
    assert manifest["execution_plan"] == plan
    assert manifest["outer_orchestrator_sha256"] == outer.sha(BASE / "execute_supplement.py")
    batches = []
    previous_finish = None
    for b in plan["batches"]:
        n = b["batch"]
        start = outer.read(DEST / "batches" / f"{n:02d}-start.json")
        finish = outer.read(DEST / "batches" / f"{n:02d}-complete.json")
        assert finish["all_workers_joined"]
        assert [t["task_number"] for t in start["tasks"]] == b["task_numbers"]
        assert [r["task_number"] for r in finish["results"]] == b["task_numbers"]
        if previous_finish:
            assert stamp(start["started_at_utc"]) > previous_finish
        previous_finish = stamp(finish["completed_at_utc"])
        for r in finish["results"]:
            assert outer.sha(ROOT / r["output_path"]) == r["output_sha256"]
            assert stamp(start["started_at_utc"]) <= stamp(r["started_at_utc"])
            assert stamp(r["finished_at_utc"]) <= previous_finish
        batches.append({"batch": n, "started_at_utc": start["started_at_utc"],
                        "completed_at_utc": finish["completed_at_utc"],
                        "runs": finish["completed_runs"],
                        "wall_seconds": (previous_finish - stamp(start["started_at_utc"])).total_seconds()})
    paths = {ROOT / t["output_path"] for t in plan["tasks"]}
    assert set(DEST.glob("*/runs/*/*.json")) == paths and len(paths) == 31
    rows = []
    missing_output_evidence = []
    for task in plan["tasks"]:
        path = ROOT / task["output_path"]
        doc = outer.read(path)
        saved = doc["assessment"]
        execution, process = doc.get("execution", {}), doc.get("process", {})
        available = "answers" in doc
        solver_available = available and doc.get("engine") is not None
        if not solver_available:
            excerpt = doc.get("process_stderr_excerpt", "")
            rich_lengths = [int(n) for n in re.findall(r"\+(\d+)", excerpt)]
            lower_bound = max(rich_lengths, default=0)
            missing_output_evidence.append({
                "task_number": task["task_number"], "case_id": task["id"], "seed": task["seed"],
                "status": saved["status"], "process": process,
                "stderr_excerpt": excerpt,
                "traceback_at_cli_output_write": "output.write_text(payload" in excerpt,
                "displayed_payload_character_lower_bound": lower_bound,
                "inherited_file_size_limit_bytes": outer.LIMIT,
                "file_limit_cause_inferred_from_write_trace_and_oversize_payload":
                    "output.write_text(payload" in excerpt and lower_bound > outer.LIMIT,
                "exception_tail_not_preserved_by_fixed_runner": True,
                "solver_answer_count_and_exact_set_unknown": True,
            })
        assert doc["group"] == task["group"]
        assert (saved["case_id"], saved["seed"]) == (task["id"], task["seed"])
        if available:
            assert execution["source_hash"] == lock["source_hash"]
            if doc.get("engine"):
                assert doc["engine"]["source_hash"] == lock["source_hash"]
            dsl = outer.read(ROOT / task["dsl_path"])
            digest = hashlib.sha256(outer.runner.rr._canonical_json(dsl).encode()).hexdigest()
            assert execution["problem_hash"] == digest
            assert execution["dependency_lock_hash"] == lock["dependency_lock_sha256"]
            assert execution["config"] == {"time_limit_seconds": 180, "cores": 1,
                                            "thread_environment": plan["thread_environment"]}
            assert process["actual_affinity"] == [process["assigned_cpu"]]
            assert process["assigned_cpu"] in plan["cpus"]
            result = {
                "status": saved["status"], "answers": doc["answers"], "engine": doc.get("engine"),
                "diagnostics": doc["diagnostics"], "elapsed_seconds": saved["wall_seconds"],
                "termination_reason": saved["termination_reason"]} if solver_available else None
            raw = {**execution, "process": process, "solver_result": result}
        else:
            raw = {"case_id": task["id"], "seed": task["seed"], "solver_result": None}
        scored = assess(raw)
        assert scored["matched"] == saved["matched"]
        if available:
            for key in ("geometric_matched", "official_output_matched", "actual_exact_keys",
                        "expected_exact_keys", "answer_expressions", "converted_outputs", "conversion_errors",
                        "n_answers", "normal_completion", "status", "termination_reason"):
                assert scored[key] == saved[key], (task["task_number"], key)
        start, finish = stamp(doc["started_at_utc"]), stamp(doc["finished_at_utc"])
        assert finish >= start > stamp(lock["locked_at_utc"])
        assert start > stamp(manifest["started_at_utc"])
        rows.append({"task_number": task["task_number"], "batch": task["batch"], "group": task["group"],
                     "case_id": task["id"], "seed": task["seed"], "matched": scored["matched"],
                     "summary_available": available, "solver_output_available": solver_available,
                     "status": saved["status"], "scoring_status": scored["status"],
                     "normal_completion": scored["normal_completion"],
                     "n_answers": scored["n_answers"] if solver_available else None,
                     "score_n_answers": scored["n_answers"],
                     "answers": " | ".join(scored["answer_expressions"]),
                     "official_outputs": " | ".join(scored["converted_outputs"]),
                     "extra_answers": scored["extra"] if solver_available else None,
                     "failure_stage": saved.get("failure_stage"),
                     "numeric_feasible": saved.get("diag_numeric"), "exact_identified": saved.get("diag_identified"),
                     "solver_seconds": saved.get("wall_seconds") if solver_available else None,
                     "process_seconds": saved.get("process_wall_seconds"),
                     "assigned_cpu": process.get("assigned_cpu"),
                     "execution_contract_issues": json.dumps(execution.get("execution_contract_issues")),
                     "started_at_utc": doc["started_at_utc"], "finished_at_utc": doc["finished_at_utc"],
                     "seconds_after_prediction_lock": (start - stamp(lock["locked_at_utc"])).total_seconds(),
                     "receipt_path": task["output_path"], "receipt_sha256": outer.sha(path),
                     "receipt_bytes": path.stat().st_size, "source_hash": execution.get("source_hash"),
                     "problem_hash": execution.get("problem_hash"),
                     "dependency_lock_hash": execution.get("dependency_lock_hash"),
                     "raw_canonical_sha256": doc.get("raw_canonical_sha256"),
                     "runner_error": doc.get("runner_error", "").splitlines()[-1:]})
    events = [(stamp(r[k]), delta) for r in rows for k, delta in
              [("started_at_utc", 1), ("finished_at_utc", -1)]]
    active = maximum = 0
    for _, delta in sorted(events):
        active += delta
        maximum = max(maximum, active)
    assert active == 0 and maximum <= 4
    main_rows = [r for r in rows if r["group"] == "main"]
    diagnostics = [r for r in rows if r["group"] != "main"]
    predictions = lock["predictions"]
    comparisons = [comparison(p["case_id"], p, [r for r in main_rows if r["case_id"] == p["case_id"]])
                   for p in predictions["main_by_problem"]]
    comparisons += [comparison("main_total", predictions["main_total"], main_rows),
                    comparison("diagnostic_seed205_repeats", predictions["diagnostic_seed205_repeats"],
                               [r for r in diagnostics if r["seed"] == 205]),
                    comparison("diagnostic_new_missing", predictions["diagnostic_new_missing"],
                               [r for r in diagnostics if r["group"] == "hexagon-new"]),
                    comparison("diagnostic_total", predictions["diagnostic_total"], diagnostics)]
    old_summary = outer.read(BASE / "summary.json")
    assert old_summary["prediction_judgments"] == {"P1": False, "P2": False, "P3": False, "P4": True}
    q19 = [json.loads(line) for line in (outer.runner.CORPUS / "prereg/q19-scored/assessment.jsonl").read_text().splitlines()]
    q19 = [r for r in q19 if r["in_target"]]
    assert (sum(r["matched"] for r in q19), len(q19)) == (85, 130)
    changed = [r for r in main_rows if r["case_id"] != "AIME-1983-12"]
    summary = {"analyzed_at_utc": outer.now(), "prediction_commit": outer.COMMIT,
               "prediction_lock_sha256": outer.LOCK_SHA, "score_sha256": outer.sha(BASE / "score.py"),
               "analysis_script_sha256": outer.sha(__file__),
               "main": count(main_rows), "changed_supplement": count(changed), "diagnostic": count(diagnostics),
               "missing_output_evidence": missing_output_evidence,
               "predictions": comparisons, "original_results_unchanged": lock["original_results_unchanged"],
               "original_prediction_judgments_unchanged": old_summary["prediction_judgments"],
               "arithmetic_all_execution_counts_requested_by_user": {
                   "meaning": "Bookkeeping only: both old missing trials and new trials counted; no replacement or rejudgment of old P1-P4",
                   "main": {"correct": 20 + count(main_rows)["correct"], "runs": 45 + 25},
                   "changed8": {"correct": 20 + count(changed)["correct"], "runs": 40 + 20},
                   "diagnostic": {"correct": 1 + count(diagnostics)["correct"], "runs": 7 + 6}},
               "timing": {"prediction_locked_at_utc": lock["locked_at_utc"],
                          "execution_started_at_utc": manifest["started_at_utc"],
                          "first_run_started_at_utc": min(r["started_at_utc"] for r in rows),
                          "last_run_finished_at_utc": max(r["finished_at_utc"] for r in rows),
                          "maximum_observed_concurrent_run_intervals": maximum,
                          "batches_sequential": True, "batches": batches},
               "audit": {"committed_and_working_files_verified": len(gate["committed_and_working_files_sha256"]),
                         "evidence_files_verified": gate["evidence_files_verified"],
                         "all_31_assessments_recomputed_and_agreed": True,
                         "new_solver_runs": 31, "automatic_retries": 0, "sealed_raw_accessed": False,
                         "runtime_verification": runtime,
                         "maximum_run_receipt_bytes": max(r["receipt_bytes"] for r in rows)}}
    outer.save_new(WORK / "floor-reproduction.json", floor_reproduction(lock))
    csv_new(WORK / "results.csv", rows)
    csv_new(WORK / "prediction-comparisons.csv", comparisons)
    outer.save_new(WORK / "summary.json", summary)
    files = [p for p in WORK.rglob("*") if p.is_file()]
    assert all(p.stat().st_size < 5_000_000 for p in files)
    outer.save_new(DEST / "completion.json", {
        "completed_at_utc": outer.now(), "completed_runs": 31, "main_runs": 25, "diagnostic_runs": 6,
        "all_batches_joined": True, "max_parallel": maximum,
        "new_summary_sha256": outer.sha(WORK / "summary.json"),
        "per_file_limit_bytes": 5_000_000, "max_file_bytes_before_this_receipt": max(p.stat().st_size for p in files),
        "files_sha256": {str(p.relative_to(WORK)): outer.sha(p) for p in sorted(files)},
        "sealed_raw_accessed": False, "original_records_unchanged": True,
    })
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
