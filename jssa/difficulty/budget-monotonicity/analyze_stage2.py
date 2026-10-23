"""Report every locked Q37 run and exact missing-data bounds, without reruns."""
from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
from collections import Counter
from statistics import median

import execute_stage2 as execution

BASE = execution.BASE
EXEC = execution.EXEC
SEEDS = (370101, 370201, 370301)
BUDGETS = (180, 360, 900)
PAIRS = ((0, 1), (0, 2), (1, 2))
LOSS_PATTERNS = {"100", "101", "010", "110"}


def read(path):
    return execution.read(path)


def object_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_csv(name, rows):
    stream = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    data = stream.getvalue().encode()
    if len(data) >= execution.LIMIT:
        raise ValueError("CSV exceeds locked size cap")
    (BASE / name).write_bytes(data)


def compact_candidate(candidate):
    """Retain initial coordinates and provenance; hash long refined coordinates."""
    keys = ("candidate_id", "candidate_uid", "candidate_key", "origin_key", "origin_phase", "origin_backend",
            "origin_seed", "origin_start_point_index", "rank", "ledger_rank", "values", "score", "residual_norm",
            "guard_ok", "hard_feasible", "hard_violation_tags", "revision", "refinement_status",
            "coordinate_precision_dps", "answer_precision_dps", "derivation_kind", "phase_history")
    result = {k: candidate[k] for k in keys if k in candidate}
    for field in ("x_hp", "answer_hp", "residual_norm_hp", "source"):
        if field in candidate:
            result[field + "_sha256"] = object_sha(candidate[field])
    return result


def stage_evidence(raw):
    result = raw.get("solver_result") or {}
    diagnostics = result.get("diagnostics") or {}
    pipeline = diagnostics.get("pipeline_summary") or {}
    ledger = [compact_candidate(c) for c in pipeline.get("candidate_ledger", [])]
    refined = [compact_candidate(c) for c in diagnostics.get("candidate_records", [])]
    exact = []
    for entry in pipeline.get("exact_candidate_records", []):
        candidate = entry.get("candidate", {})
        e = entry.get("exact_result", {})
        exact.append({"candidate": compact_candidate(candidate), "exact_result": {k: e[k] for k in
                      ("exact_status", "identification_method", "input_precision_dps", "minimal_polynomial",
                       "polynomial_degree", "selected_exact_value", "descriptor", "evidence_origin", "discovery_precision_dps") if k in e}})
    verification = [{k: row[k] for k in ("candidate_id", "candidate_uid", "verified", "status", "precision_dps",
                     "hard_feasible", "hard_failure_tags", "input_revision", "revision") if k in row}
                    for row in pipeline.get("verification_records", [])]
    # Comparison identities explicitly include coordinates and provenance, not UID alone.
    ledger_identity = [{k: row.get(k) for k in ("values", "origin_phase", "origin_backend", "origin_seed", "origin_start_point_index", "rank")} for row in ledger]
    return {"raw_status": result.get("status"), "termination_reason": result.get("termination_reason"),
            "phase_timings": diagnostics.get("phase_timings", {}), "counters": diagnostics.get("counters", {}),
            "config_snapshot": diagnostics.get("config_snapshot", {}),
            "pipeline": {k: pipeline[k] for k in ("initial_probe", "search", "refinement", "exact_assembly", "search_staged_fallback", "phase_rescue", "phase_discrete_completion", "answer_source_candidate_id", "answer_candidate_values", "answer_extraction_candidate_ids") if k in pipeline},
            "candidate_ledger": ledger, "candidate_ledger_identity_sha256": object_sha(ledger_identity),
            "refined_candidates": refined, "exact_candidates": exact, "verification_records": verification,
            "debug_candidates": [{k: row[k] for k in ("candidate_id", "candidate_uid", "stage", "hard_feasible", "refinement_status", "rejection_tag") if k in row} for row in pipeline.get("debug_candidates", [])],
            "all_answers": result.get("answers", [])}


def metric_flags(cells):
    triples = [cells[i:i + 3] for i in (0, 3, 6)]
    losses = [[int(triple[a] == 1 and triple[b] == 0) for a, b in PAIRS] for triple in triples]
    counts = [sum(row[k] for row in losses) for k in range(3)]
    return {"N": int(any(counts)), "R": int(max(counts) >= 2), "R3": int(max(counts) == 3),
            "V": int(any(tuple(t) in ((1, 0, 1), (0, 1, 0)) for t in triples))}


def bounds(cells):
    unknown = [i for i, value in enumerate(cells) if value is None]
    completions = []
    for values in itertools.product((0, 1), repeat=len(unknown)):
        filled = list(cells)
        for i, value in zip(unknown, values, strict=True):
            filled[i] = value
        completions.append(metric_flags(filled))
    return {name: [min(row[name] for row in completions), max(row[name] for row in completions)] for name in ("N", "R", "R3", "V")}


def range_grade(actual, expected):
    low, high = actual
    if expected[0] <= low <= high <= expected[1]:
        return "成立"
    if high < expected[0] or low > expected[1]:
        return "不成立"
    return "判定不能"


def concentration_grade(strata):
    ab = [strata["A"]["N"][i] + strata["B"]["N"][i] for i in (0, 1)]
    c, d = strata["C"]["N"], strata["D"]["N"]
    possibilities, ratios, zero = [], [], False
    for a, b, e in itertools.product(range(ab[0], ab[1] + 1), range(c[0], c[1] + 1), range(d[0], d[1] + 1)):
        if a + b + e == 0:
            zero = True
        else:
            ratios.append(a / (a + b + e))
            possibilities.append(a / (a + b + e) >= 0.75 and e <= 1)
    verdict = ("判定対象なし" if not possibilities else "成立" if all(possibilities) and not zero
               else "不成立" if not any(possibilities) and not zero else "判定不能")
    return {"verdict": verdict, "A_plus_B_N_bounds": ab, "D_N_bounds": d,
            "A_plus_B_fraction_bounds_if_N_positive": [min(ratios), max(ratios)] if ratios else None,
            "N_zero_possible": zero}


def analyze():
    jobs = execution.jobs()
    selection = list(csv.DictReader((BASE / "selection.csv").open()))
    assessments = {}
    for budget in BUDGETS:
        for seed in SEEDS:
            path = BASE / f"campaign/t{budget}/s{seed}/assessment.jsonl"
            substituted = set()
            if not path.exists():
                path = BASE / f"grading-views/t{budget}/s{seed}/assessment.jsonl"
                receipt = path.parent / "view-receipt.json"
                if receipt.exists():
                    substituted = {r["id"] for r in read(receipt)["substitutions_for_unknown_only"]}
            if path.exists():
                for line in path.read_text().splitlines():
                    row = json.loads(line)
                    row["q37_assessment_source"] = str(path.relative_to(BASE))
                    row["q37_unknown_placeholder"] = row["case_id"] in substituted
                    assessments[(row["case_id"], seed, budget)] = row
    runs, diagnostics, receipts = [], {}, {}
    for job in jobs:
        identity = (job["id"], job["seed"], job["time_limit_seconds"])
        rawpath = execution.raw_path(job)
        raw = read(rawpath) if rawpath.exists() else {}
        receiptfile = execution.receipt_path(job)
        receipt = read(receiptfile) if receiptfile.exists() else {}
        assessment = assessments.get(identity)
        try:
            outcome = execution.rr.read_run_outcome(raw)
        except AttributeError:
            if not receipt.get("receipt_recovery"):
                raise
            outcome = receipt["outcome"]
        result = raw.get("solver_result") or {}
        diag = result.get("diagnostics") or {}
        pipeline = diag.get("pipeline_summary") or {}
        timings = diag.get("phase_timings") or {}
        known = bool(assessment is not None and outcome["normal_completion"]
                     and assessment["normal_completion"] and assessment["matched"] is not None)
        value = int(assessment["matched"] is True) if known else None
        stderr = raw.get("process", {}).get("stderr", "")
        missing_reason = (None if known else "storage_file_size_limit" if "[Errno 27] File too large" in stderr
                          else "assessment_missing" if not assessment else outcome["status"])
        info = diag.get("process_info") or {}
        load = receipt.get("load_samples", [])
        cpu_s = info.get("cpu_seconds")
        wall_s = outcome.get("wall_seconds")
        rows = {"id": job["id"], "stratum": job["stratum"], "seed": job["seed"], "budget_seconds": job["time_limit_seconds"],
                "lane": job["lane"], "lane_order": job["lane_order"], "cpu": receipt.get("cpu"),
                "start_utc": receipt.get("start_utc"), "end_utc": receipt.get("end_utc"),
                "matched_original": (assessment.get("matched") if assessment and not assessment.get("q37_unknown_placeholder") else None),
                "matched_frozen_grader": assessment.get("matched") if assessment else None,
                "assessment_source": assessment.get("q37_assessment_source") if assessment else None,
                "grading_unknown_placeholder": assessment.get("q37_unknown_placeholder") if assessment else None,
                "mechanism_y": value, "category": "correct" if value == 1 else "normal_incorrect" if value == 0 else "unknown",
                "status": outcome["status"], "termination_reason": outcome.get("termination_reason"),
                "missing_reason": missing_reason,
                "set_relation": assessment.get("set_relation") if assessment else None,
                "failure_stage": outcome.get("failure_stage"), "solver_wall_seconds": wall_s,
                "process_wall_seconds": outcome.get("process_wall_seconds"), "worker_cpu_seconds": cpu_s,
                "worker_cpu_to_solver_wall_ratio": cpu_s / wall_s if cpu_s is not None and wall_s else None,
                "children_cpu_seconds": receipt.get("children_cpu_seconds"),
                "load1_mean": sum(s["load_average"][0] for s in load) / len(load) if load else None,
                "load1_min": min(s["load_average"][0] for s in load) if load else None,
                "load1_max": max(s["load_average"][0] for s in load) if load else None,
                "affinity_violations": len(receipt.get("affinity_violations", [])),
                "search_seconds": timings.get("search"), "refinement_seconds": timings.get("refinement"),
                "exact_assembly_seconds": timings.get("exact_assembly"), "rescue_seconds": timings.get("phase_rescue"),
                "search_evaluations": pipeline.get("search", {}).get("evaluation_count"),
                "refinement_attempted": pipeline.get("refinement", {}).get("attempted_count"),
                "refinement_converged": pipeline.get("refinement", {}).get("converged_count"),
                "exact_accepted": pipeline.get("exact_assembly", {}).get("accepted_count"),
                "fallback_triggered": pipeline.get("search_staged_fallback", {}).get("triggered"),
                "fallback_selected_stage": pipeline.get("search_staged_fallback", {}).get("selected_stage"),
                "rescue_triggered": pipeline.get("phase_rescue", {}).get("triggered"),
                "answer_source_candidate_id": pipeline.get("answer_source_candidate_id"),
                "raw_sha256": execution.sha(rawpath) if rawpath.exists() else None,
                "raw_bytes": rawpath.stat().st_size if rawpath.exists() else None,
                "raw_path": str(rawpath.relative_to(BASE)), "receipt_path": str(receiptfile.relative_to(BASE))}
        if receipt and receipt.get("raw_sha256") != rows["raw_sha256"]:
            raise RuntimeError(f"raw hash no longer matches completion receipt: {rawpath}")
        runs.append(rows)
        diagnostics[identity] = stage_evidence(raw)
        receipts[identity] = receipt
    write_csv("per-run.csv", runs)
    bykey = {(r["id"], r["seed"], r["budget_seconds"]): r for r in runs}
    perproblem, pertriplet, pairs, regressions = [], [], [], []
    patterns = Counter({"".join(map(str, p)): 0 for p in itertools.product((0, 1), repeat=3)})
    for problem in selection:
        cid = problem["id"]
        cells = [bykey[(cid, seed, budget)]["mechanism_y"] for seed in SEEDS for budget in BUDGETS]
        metric_bounds = bounds(cells)
        problemrow = {"id": cid, "stratum": problem["stratum"], "observed_cells": sum(v is not None for v in cells),
                      **{f"{metric}_{suffix}": metric_bounds[metric][i] for metric in metric_bounds for i, suffix in enumerate(("lower", "upper"))}}
        for i, seed in enumerate(SEEDS):
            triple = cells[3 * i:3 * i + 3]
            pattern = "".join("?" if v is None else str(v) for v in triple)
            problemrow[f"pattern_{seed}"] = pattern
            patterns[pattern] += 1
            pertriplet.append({"id": cid, "stratum": problem["stratum"], "seed": seed, "pattern_180_360_900": pattern,
                               "observed_loss": any(triple[a] == 1 and triple[b] == 0 for a, b in PAIRS)})
            for a, b in PAIRS:
                left = bykey[(cid, seed, BUDGETS[a])]
                right = bykey[(cid, seed, BUDGETS[b])]
                x, y = triple[a], triple[b]
                label = "unknown" if x is None or y is None else "loss" if (x, y) == (1, 0) else "gain" if (x, y) == (0, 1) else "both_correct" if x == 1 else "both_incorrect"
                pair = {"id": cid, "stratum": problem["stratum"], "seed": seed, "short_budget": BUDGETS[a], "long_budget": BUDGETS[b], "short_y": x, "long_y": y, "label": label}
                pairs.append(pair)
                if label == "loss":
                    dl, dr = diagnostics[(cid, seed, BUDGETS[a])], diagnostics[(cid, seed, BUDGETS[b])]
                    evidence = {"comparison": pair, "short_run": left, "long_run": right,
                                "ledger_coordinates_and_origins_equal": dl["candidate_ledger_identity_sha256"] == dr["candidate_ledger_identity_sha256"],
                                "short_stats": dl, "long_stats": dr,
                                "causal_limit": "The first recorded divergence is observational. Timing and shared load can also change wall-clock cutoffs; no extra runs or interventions were performed."}
                    evidencepath = BASE / "regression-evidence" / f"{cid}-s{seed}-{BUDGETS[a]}-{BUDGETS[b]}.json"
                    execution.save(evidencepath, evidence)
                    regressions.append({**pair, "ledger_coordinates_and_origins_equal": evidence["ledger_coordinates_and_origins_equal"],
                                        "short_fallback": left["fallback_selected_stage"], "long_fallback": right["fallback_selected_stage"],
                                        "short_refinement_seconds": left["refinement_seconds"], "long_refinement_seconds": right["refinement_seconds"],
                                        "short_exact_accepted": left["exact_accepted"], "long_exact_accepted": right["exact_accepted"],
                                        "long_set_relation": right["set_relation"], "evidence": str(evidencepath.relative_to(BASE))})
        for budget in BUDGETS:
            values = [bykey[(cid, seed, budget)]["mechanism_y"] for seed in SEEDS]
            problemrow[f"correct_{budget}"] = sum(v == 1 for v in values)
            problemrow[f"unknown_{budget}"] = sum(v is None for v in values)
        perproblem.append(problemrow)
    write_csv("per-problem.csv", perproblem)
    write_csv("per-triplet.csv", pertriplet)
    write_csv("budget-pairs.csv", pairs)
    write_csv("regressions.csv", regressions)
    metrics = {metric: [sum(p[f"{metric}_{suffix}"] for p in perproblem) for suffix in ("lower", "upper")] for metric in ("N", "R", "R3", "V")}
    strata = {group: {metric: [sum(p[f"{metric}_{suffix}"] for p in perproblem if p["stratum"] == group) for suffix in ("lower", "upper")] for metric in metrics} for group in "ABCD"}
    bybudget = {str(budget): dict(Counter(r["category"] for r in runs if r["budget_seconds"] == budget)) for budget in BUDGETS}
    bypair = {f"{BUDGETS[a]}->{BUDGETS[b]}": dict(Counter(p["label"] for p in pairs if p["short_budget"] == BUDGETS[a] and p["long_budget"] == BUDGETS[b])) for a, b in PAIRS}
    all_load = [row["load_average"] for receipt in receipts.values() for row in receipt.get("load_samples", [])]
    ratios = [r["worker_cpu_to_solver_wall_ratio"] for r in runs if r["worker_cpu_to_solver_wall_ratio"] is not None]
    start = read(EXEC / "execution-start.json")
    end = read(EXEC / "execution-end.json") if (EXEC / "execution-end.json").exists() else None
    summary = {"analysis_utc": execution.now(), "prediction_lock_sha256": execution.LOCK_SHA,
               "planned_runs": 360, "saved_runs": sum(r["raw_sha256"] is not None for r in runs),
               "assessed_runs": len(assessments), "completed_receipts": sum(bool(r) for r in receipts.values()),
               "unknown_runs": sum(r["category"] == "unknown" for r in runs), "status_counts": dict(Counter(r["status"] for r in runs)),
               "mechanism_metric_bounds_out_of_40": metrics, "strata_metric_bounds_out_of_10": strata,
               "budget_categories_out_of_120": bybudget, "budget_pair_counts_out_of_120": bypair,
               "pattern_counts_out_of_120": dict(sorted(patterns.items())),
               "fully_observed_problems": sum(p["observed_cells"] == 9 for p in perproblem),
               "fully_observed_problem_metric_counts": {metric: sum(p[f"{metric}_lower"] for p in perproblem if p["observed_cells"] == 9) for metric in metrics},
               "predictions": {"P1": {"point": 4, "range": [1, 8], "actual_bounds": metrics["N"], "verdict": range_grade(metrics["N"], [1, 8])},
                               "P2": {"point": 1, "range": [1, 3], "actual_bounds": metrics["R"], "verdict": range_grade(metrics["R"], [1, 3])},
                               "P3": concentration_grade(strata)},
               "execution_start_utc": start["execution_start_utc"], "execution_end_utc": end["execution_end_utc"] if end else None,
               "lane_cpus": start["lane_cpus"], "affinity_violation_runs": sum(r["affinity_violations"] > 0 for r in runs),
               "recovered_receipts_with_periodic_monitor_unavailable": sum(bool(r.get("receipt_recovery")) for r in receipts.values()),
               "original_campaign_grading_errors": end["grading_errors"] if end else None,
               "load_averages": {str(minutes): {"min": min(v[i] for v in all_load), "max": max(v[i] for v in all_load), "mean": sum(v[i] for v in all_load) / len(all_load)} for i, minutes in enumerate((1, 5, 15))} if all_load else {},
               "worker_cpu_to_solver_wall_ratio": {"min": min(ratios), "median": median(ratios), "max": max(ratios)} if ratios else {},
               "max_saved_raw_bytes": max((r["raw_bytes"] or 0) for r in runs),
               "sum_process_wall_seconds": sum(r["process_wall_seconds"] or 0 for r in runs),
               "sum_worker_cpu_seconds": sum(r["worker_cpu_seconds"] or 0 for r in runs),
               "regression_pair_count": len(regressions), "no_additional_solver_runs": True}
    execution.save(BASE / "summary.json", summary)
    execution.save(BASE / "unknown-runs.json", [{k: r[k] for k in ("id", "seed", "budget_seconds", "status", "missing_reason", "matched_original", "raw_path", "receipt_path")} for r in runs if r["category"] == "unknown"])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    analyze()
