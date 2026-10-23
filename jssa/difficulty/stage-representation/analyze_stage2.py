"""Locked Q39 denominators, descriptive bootstrap, unchanged official grader."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time

import diagnostic as d
import execute_stage2 as ex
import measure_stage2 as measurement

CELLS = (("A", "A"), ("A", "B"), ("B", "A"), ("B", "B"))
PROTOCOL = d.read(d.BASE / "protocol.json")
SELECTED = d.selected()
TARGETS = PROTOCOL["controls"]["R0_ids"]
FAMILIES = {
    "tangency": [k for k, r in SELECTED.items() if r["stratum"] in
                  ("tangency_line_gap", "tangency_contact")],
    "point_distance_zero": [k for k, r in SELECTED.items() if r["stratum"] == "distance_point_zero"],
}
STRATA = {s: [k for k, r in SELECTED.items() if r["stratum"] == s]
          for s in sorted({r["stratum"] for r in SELECTED.values()})}
FRONT_CACHE, MEASURE_CACHE = {}, {}


def csv_save(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)


def front(identifier, seed, mode, index):
    key = identifier, seed, mode, index
    if key not in FRONT_CACHE:
        path = d.front_dir(identifier, seed, mode) / f"{index}.json"
        FRONT_CACHE[key] = d.read(path) if path.exists() else {
            "F": False, "candidate": None, "prefixes": {}, "missing_artifact": True}
    return FRONT_CACHE[key]


def measured(identifier, seed, origin, rear, index):
    key = identifier, seed, origin, rear, index
    if key not in MEASURE_CACHE:
        path = d.rear_dir(identifier, seed, origin, rear) / f"measurement-{index}.json"
        MEASURE_CACHE[key] = d.read(path) if path.exists() else {
            "final": measurement.absent("measurement_missing"),
            "input": measurement.absent("measurement_missing"),
            "target_digit_gain": 0., "measurement_missing": True}
    return MEASURE_CACHE[key]


def problem_comparison(identifier, front_b="B", rear_b="B", seeds=d.SEEDS, origins=None):
    origins = ("A", front_b) if origins is None else origins
    fr_a = [front(identifier, s, "A", i) for s in seeds for i in range(8)]
    fr_b = [front(identifier, s, front_b, i) for s in seeds for i in range(8)]
    ra = [measured(identifier, s, o, "A", i) for s in seeds for o in origins for i in range(8)]
    rb = [measured(identifier, s, o, rear_b, i) for s in seeds for o in origins for i in range(8)]
    F_A = statistics.mean(float(r["F"]) for r in fr_a)
    F_B = statistics.mean(float(r["F"]) for r in fr_b)
    R_A = statistics.mean(float(r["final"]["R50"]) for r in ra)
    R_B = statistics.mean(float(r["final"]["R50"]) for r in rb)
    differences = [b["target_digit_gain"] - a["target_digit_gain"] for a, b in zip(ra, rb, strict=True)]
    common = []
    for a, b in zip(fr_a, fr_b, strict=True):
        flags = [r["prefixes"].get("200", {}) for r in (a, b)]
        common.append(all(v.get("reached") or v.get("carried") for v in flags))
    finite = [front(identifier, s, o, i).get("candidate") is not None
              for s in seeds for o in origins for i in range(8)]
    conditional_n = sum(finite)
    prefix_stats = {}
    for prefix in (200, 800, 1200):
        pairs = [(a["prefixes"].get(str(prefix), {}), b["prefixes"].get(str(prefix), {}))
                 for a, b in zip(fr_a, fr_b, strict=True)]
        pairs = [(a, b) for a, b in pairs
                 if (a.get("reached") or a.get("carried")) and (b.get("reached") or b.get("carried"))]
        prefix_stats[str(prefix)] = {"common_pairs": len(pairs),
             "A_Q_below_1e4": sum(a.get("Q") is not None and a["Q"] <= 1e-4 for a, _ in pairs),
             "B_Q_below_1e4": sum(b.get("Q") is not None and b["Q"] <= 1e-4 for _, b in pairs)}
    return {"id": identifier, "stratum": SELECTED[identifier]["stratum"],
            "front_A": F_A, "front_B": F_B, "front_difference": F_A - F_B,
            "rear_A": R_A, "rear_B": R_B, "rear_difference": R_B - R_A,
            "paired_gain_difference": statistics.median(differences),
            "front_n_per_arm": len(fr_a), "rear_n_per_arm": len(ra),
            "finite_candidate_n": conditional_n,
            "conditional_rear_A": sum(float(r["final"]["R50"]) for r, ok in zip(ra, finite) if ok) / conditional_n
                                  if conditional_n else None,
            "conditional_rear_B": sum(float(r["final"]["R50"]) for r, ok in zip(rb, finite) if ok) / conditional_n
                                  if conditional_n else None,
            "common_prefix_200_fraction": statistics.mean(common),
            "common_prefixes": prefix_stats,
            "both_rate_gates": F_A - F_B >= .1 - 1e-12 and R_B - R_A >= .1 - 1e-12,
            "measurement_missing_n": sum(r.get("measurement_missing", False) for r in ra + rb),
            "measurement_error_n": sum(r["final"]["status"] not in ("observed", "missing") for r in ra + rb)}


def group_comparison(ids, front_b="B", rear_b="B", seeds=d.SEEDS, origins=None, bootstrap=True):
    rows = [problem_comparison(k, front_b, rear_b, seeds, origins) for k in ids]
    if not rows:
        return {"problem_count": 0, "status": "NA"}
    result = {"problem_count": len(rows), "ids": list(ids),
              **{k: statistics.mean(r[k] for r in rows) for k in
                 ("front_A", "front_B", "front_difference", "rear_A", "rear_B", "rear_difference",
                  "common_prefix_200_fraction")},
              "paired_gain_difference": statistics.median(r["paired_gain_difference"] for r in rows),
              "cases_meeting_both_rates": [r["id"] for r in rows if r["both_rate_gates"]],
              "measurement_missing_n": sum(r["measurement_missing_n"] for r in rows),
              "measurement_error_n": sum(r["measurement_error_n"] for r in rows)}
    result["threshold_gate"] = (result["front_difference"] >= .1 - 1e-12
                                and result["rear_difference"] >= .1 - 1e-12
                                and result["paired_gain_difference"] >= 20
                                and len(result["cases_meeting_both_rates"]) >= 3
                                and result["common_prefix_200_fraction"] >= .9)
    if bootstrap:
        import numpy as np
        rng = np.random.default_rng(39099)
        samples = rng.integers(0, len(rows), size=(10000, len(rows)))
        intervals = {}
        for k in ("front_difference", "rear_difference", "paired_gain_difference"):
            values = np.array([r[k] for r in rows])[samples]
            estimates = np.median(values, axis=1) if k == "paired_gain_difference" else values.mean(axis=1)
            intervals[k] = [float(v) for v in np.quantile(estimates, [.025, .975])]
        result["descriptive_95pct_problem_bootstrap"] = intervals
    return result


def campaigns():
    configs = [(f"normal-{f}{r}", list(SELECTED), f, r) for f, r in CELLS]
    for family, ids, mode in [("L", PROTOCOL["controls"]["L_ids"], "L"),
                *[("mask-" + tag, [PROTOCOL["controls"]["masked_case"]], "mask:" + tag)
                  for tag in PROTOCOL["controls"]["masks"]]]:
        for f, r in (("A", "A"), ("A", mode), (mode, "A"), (mode, mode)):
            configs.append((family + "-" + ("A" if f == "A" else "B") + ("A" if r == "A" else "B"), ids, f, r))
    configs.extend(("R0-" + f, TARGETS, f, "R0") for f in ("A", "B"))
    return configs


def grade_campaign(name):
    from benchmarks import research_runner as rr
    ex.verify_lock()
    if not (d.OUT / "front-seal.json").exists():
        raise RuntimeError("unsealed front")
    _, ids, f, r = next(c for c in campaigns() if c[0] == name)
    records = [record for record in rr._load_cases() if record.identifier in ids]
    manifest = rr._manifest(records, list(d.SEEDS))
    manifest.update(diagnostic_wrapper_hashes={p: d.sha(d.BASE / p) for p in
                     ("diagnostic.py", "execute_stage2.py", "measure_stage2.py", "analyze_stage2.py")},
                    diagnostic_arm=f + "->" + r, frozen_complete_solver_performance=False)
    destination = d.BASE / "campaign" / name
    d.save(destination / "campaign-manifest.json", manifest)
    case_meta = {row["id"]: row for row in manifest["cases"]}
    jobs = {(j["id"], j["seed"], j["front_mode"], j["rear_mode"]): j
            for j in ex.job_list("rear")}
    for identifier in ids:
        for seed in d.SEEDS:
            job = jobs[identifier, seed, f, r]
            path = d.rear_dir(identifier, seed, f, r)
            phase_path = path / "phase-c.json"
            status_path = d.OUT / "jobs" / (job["key"] + ".json")
            status = d.read(status_path) if status_path.exists() else {"status": "missing"}
            process_path = d.OUT / "processes" / (job["key"] + ".json")
            process = d.read(process_path) if process_path.exists() else {}
            issues = []
            if status["status"] != "completed":
                issues.append("diagnostic_job_" + status["status"])
            for i in range(8):
                pre = front(identifier, seed, f, i)
                if not pre.get("callback_limit_ok", True):
                    issues.append("callback_limit_exceeded")
                rp = path / f"{i}.json"
                if rp.exists() and d.read(rp).get("error"):
                    issues.append("refinement_exception")
            if phase_path.exists():
                phase = d.read(phase_path)
                solver = {"status": phase["status"], "answers": phase["answers"],
                          "termination_reason": phase["termination_reason"],
                          "elapsed_seconds": status.get("elapsed_seconds"),
                          "diagnostics": {"phase_timings": phase["timings"],
                            "counters": phase["counters"],
                            "rejection_tags": phase["rejection_tags"],
                            "process_info": {"cpu_seconds": status.get("cpu_seconds"),
                                             "peak_rss_bytes": process.get("peak_tree_rss_bytes")},
                            "pipeline_summary": {"exact_assembly": {
                                 "numeric_feasible_count": phase["numeric_feasible_count"],
                                 "rejection_tags": phase["rejection_tags"]},
                                 "verification_records": phase["verification_summary"]}}}
            else:
                solver = {"status": "engine_error", "answers": [],
                          "termination_reason": "engine_failed"}
            raw = {"schema_version": 2, "case_id": identifier, "seed": seed,
                   "problem_hash": case_meta[identifier]["problem_hash"],
                   "reference_hash": case_meta[identifier]["reference_hash"],
                   "source_hash": manifest["source_hash"],
                   "dependency_lock_hash": manifest["dependency_lock_hash"],
                   "config_hash": manifest["config_hash"], "config": manifest["config"],
                   "wrapper_hashes": manifest["diagnostic_wrapper_hashes"],
                   "diagnostic_arm": manifest["diagnostic_arm"],
                   "execution_contract_issues": sorted(set(issues)),
                   "process": {"returncode": process.get("returncode"),
                               "timed_out": process.get("termination") == "external_timeout",
                               "elapsed_seconds": process.get("elapsed_seconds")},
                   "solver_result": solver}
            d.save(destination / "runs" / identifier / f"{seed}.json", raw)
    started = time.monotonic()
    rr.assess_campaign(destination)
    assessment = [json.loads(line) for line in (destination / "assessment.jsonl").read_text().splitlines()]
    result = {"campaign": name, "arm": f + "->" + r, "runs": len(assessment),
              "matched": sum(row["matched"] is True for row in assessment),
              "normal_completion": sum(row["normal_completion"] for row in assessment),
              "status_counts": dict(Counter(row["status"] for row in assessment)),
              "set_relation_counts": dict(Counter(row["set_relation"] for row in assessment)),
              "elapsed_seconds_assessor": time.monotonic() - started}
    d.save(destination / "grading-receipt.json", result)
    print(json.dumps(result))


def read_assessments():
    return {name: [json.loads(line) for line in (d.BASE / "campaign" / name / "assessment.jsonl").read_text().splitlines()]
            for name, _, _, _ in campaigns()}


def cell_statistics(ids, origin, rear):
    rows = [measured(identifier, seed, origin, rear, i)
            for identifier in ids for seed in d.SEEDS for i in range(8)]
    result = {"origin": origin, "rear": rear, "problem_count": len(ids), "slots": len(rows),
              "R50": statistics.mean(float(r["final"]["R50"]) for r in rows),
              "R80": statistics.mean(float(r["final"]["R80"]) for r in rows),
              "input_target_digits_median": statistics.median(r["input"]["target_digits"] for r in rows),
              "final_target_digits_median": statistics.median(r["final"]["target_digits"] for r in rows),
              "original_residual_digits_median": statistics.median(r["final"]["A_digits"] for r in rows),
              "Q_digits_median": statistics.median(r["final"]["Q_digits"] for r in rows),
              "target_digit_gain_median": statistics.median(r["target_digit_gain"] for r in rows)}
    for threshold in (50, 80):
        key = f"first_{threshold}_digits_saved_time_upper_bound"
        times = [r[key] for r in rows if r.get(key) is not None]
        result[f"observed_{threshold}_hit_count"] = len(times)
        result[f"{threshold}_saved_time_upper_bound_median_conditional"] = statistics.median(times) if times else None
    return result


def audit_execution():
    jobs = [d.read(p) for p in sorted((d.OUT / "jobs").glob("*.json"))
            if not p.name.endswith(".started.json")]
    processes = [d.read(p) for p in (d.OUT / "processes").glob("*.json")]
    front_records = [d.read(p) for p in (d.OUT / "front").rglob("[0-7].json")]
    rear_records = [d.read(p) for p in (d.OUT / "rear").rglob("[0-7].json")]
    metrics = [d.read(p) for p in (d.OUT / "rear").rglob("measurement-[0-7].json")]
    phase = [d.read(p) for p in (d.OUT / "rear").rglob("phase-c.json")]
    files = [p for p in d.BASE.rglob("*") if p.is_file()]
    snapshots = Counter(s["label"] for r in rear_records for s in r["snapshots"])
    return {"utc": d.utc(), "lock_verified": ex.verify_lock(),
            "jobs": dict(Counter(r["status"] for r in jobs)),
            "expected_jobs": {s: len(ex.job_list(s)) for s in ("prepare", "front", "rear")},
            "front_slots": len(front_records), "rear_slots": len(rear_records),
            "expected_front_slots": 1440, "expected_rear_slots": 4128,
            "front_candidate_missing": sum(r["candidate"] is None for r in front_records),
            "front_timeouts": sum(r["timeout"] for r in front_records),
            "front_errors": sum(bool(r["error"]) for r in front_records),
            "front_callback_limit_violations": sum(not r["callback_limit_ok"] for r in front_records),
            "front_callbacks": sum(r["callback_count"] for r in front_records),
            "front_rewrite_fallbacks": sum(r["rewrite_audit"].get("rewrite_fallback", 0) for r in front_records),
            "front_row_mismatches": sum(r["rewrite_audit"].get("row_count_mismatch", 0) for r in front_records),
            "rear_missing": sum(r["missing"] for r in rear_records),
            "rear_errors": sum(bool(r.get("error")) for r in rear_records),
            "rear_statuses": dict(Counter(c["status"] for r in rear_records for c in r["candidates"])),
            "rear_rewrite_fallbacks": sum(r.get("rewrite_audit", {}).get("rewrite_fallback", 0) for r in rear_records),
            "rear_row_mismatches": sum(r.get("rewrite_audit", {}).get("row_count_mismatch", 0) for r in rear_records),
            "snapshots": dict(snapshots), "measurement_records": len(metrics),
            "measurement_final_statuses": dict(Counter(r["final"]["status"] for r in metrics)),
            "phase_c_records": len(phase), "phase_c_timeouts": sum(r["time_limited"] for r in phase),
            "phase_c_rejection_tags": dict(Counter(t for r in phase for t in r["rejection_tags"])),
            "affinity_violations": sum(len(r["affinity_violations"]) for r in processes),
            "process_terminations": dict(Counter(str(r["termination"]) for r in processes)),
            "peak_worker_tree_rss_bytes": max((r["peak_tree_rss_bytes"] for r in processes), default=0),
            "max_file_bytes": max(p.stat().st_size for p in files),
            "oversized_files": [str(p.relative_to(d.BASE)) for p in files if p.stat().st_size >= 5_000_000],
            "all_execution_file_bytes": sum(p.stat().st_size for p in files if d.OUT in p.parents),
            "pre_worker_launch_failures_preserved": 2,
            "coincident_circle_exact_final_count": sum(any(c["exact_at_180dps"] for c in r["final"].get("coincident_contacts", [])) for r in metrics),
            "coincident_circle_near_final_count": sum(bool(r["final"].get("coincident_contacts")) for r in metrics)}


def summarize():
    ex.verify_lock()
    assessments = read_assessments()
    per_problem = [problem_comparison(k) for k in SELECTED]
    per_seed = []
    for seed in d.SEEDS:
        per_seed.extend(dict(problem_comparison(k, seeds=(seed,)), seed=seed) for k in SELECTED)
    families = {name: group_comparison(ids) for name, ids in FAMILIES.items()}
    for name, result in families.items():
        result["seeds"] = {str(s): group_comparison(FAMILIES[name], seeds=(s,), bootstrap=False) for s in d.SEEDS}
        result["all_seed_directions_positive"] = all(r["front_difference"] > 0 and r["rear_difference"] > 0
                                                     for r in result["seeds"].values())
        result["crossing_supported"] = result["threshold_gate"] and result["all_seed_directions_positive"]
    strata = {name: group_comparison(ids) for name, ids in STRATA.items()}
    l_result = group_comparison(PROTOCOL["controls"]["L_ids"], front_b="L", rear_b="L")
    l_result["retains_5pp_gaps"] = l_result["front_difference"] >= .05 and l_result["rear_difference"] >= .05
    masked = {tag: group_comparison([PROTOCOL["controls"]["masked_case"]],
                   front_b="mask:" + tag, rear_b="mask:" + tag) for tag in PROTOCOL["controls"]["masks"]}
    r0 = {}
    for label, ids in {"targets": TARGETS, **{k: v for k, v in STRATA.items() if not k.startswith("unchanged")}, **FAMILIES}.items():
        b_result = group_comparison(ids)
        r_result = group_comparison(ids, rear_b="R0", origins=("A", "B"))
        effect = b_result["rear_difference"]
        fraction = r_result["rear_difference"] / effect if effect > 0 else None
        digit_distance = abs(r_result["paired_gain_difference"] - b_result["paired_gain_difference"])
        r0[label] = {"B": b_result, "R0": r_result, "B_positive_effect_ge_10pp": effect >= .1,
                     "rate_effect_fraction_reproduced": fraction, "median_gain_distance": digit_distance,
                     "regularization_explanation_compatible": effect >= .1 and fraction >= .8 and digit_distance <= 10}
    official = {}
    for name, rows in assessments.items():
        selected_rows = [r for r in rows if r["case_id"] in TARGETS]
        official[name] = {"all_runs": len(rows), "all_matches": sum(r["matched"] is True for r in rows),
                          "all_rate": statistics.mean(float(r["matched"] is True) for r in rows),
                          "target_runs": len(selected_rows),
                          "target_matches": sum(r["matched"] is True for r in selected_rows),
                          "target_rate": statistics.mean(float(r["matched"] is True) for r in selected_rows) if selected_rows else None,
                          "normal_completions": sum(r["normal_completion"] for r in rows),
                          "set_relations": dict(Counter(r["set_relation"] for r in rows))}
    advantage = official["normal-AB"]["target_rate"] - max(official["normal-" + c]["target_rate"] for c in ("AA", "BA", "BB"))
    supported = [name for name, r in families.items() if r["crossing_supported"]]
    cross_cases = sorted({i for name in supported for i in families[name]["cases_meeting_both_rates"]})
    orders = [d.read(p) for p in sorted((d.OUT / "orders").glob("*.json"))]
    order_summary = {"cases": len(orders), "statuses": dict(Counter(r["status"] for r in orders)),
                     "cases_with_quadratic_to_linear_row": [r["id"] for r in orders
                              if any(s["quadratic_to_linear_compatible"] for s in r.get("slopes", []))]}
    by_origin = {group: {origin: group_comparison(ids, origins=(origin,)) for origin in ("A", "B")}
                 for group, ids in {"targets": TARGETS, **FAMILIES, **STRATA}.items()}
    stage_cells = {name: cell_statistics(ids, f, r) for name, ids, f, r in campaigns()}
    stage_cells.update({"targets-" + f + r: cell_statistics(TARGETS, f, r) for f, r in CELLS})
    execution = audit_execution()
    result = {"utc": d.utc(), "families": families, "strata": strata, "L": l_result,
              "R0": r0, "masked": masked, "official": official, "orders": order_summary,
              "rear_comparison_by_front_origin": by_origin, "stage_cells": stage_cells,
              "gate": {"supported_independent_families": supported, "distinct_crossing_cases": cross_cases,
                       "multi_command_gate": len(supported) >= 2 and len(cross_cases) >= 6,
                       "AB_target_answer_set_advantage": advantage,
                       "answer_set_advantage_gate": advantage >= .05,
                       "regularization_only_must_be_rejected": True,
                       "deep_theory_demonstrated": False,
                       "solver_unique_demonstrated": False},
              "execution": execution}
    d.save(d.BASE / "summary.json", result)
    flat = lambda r: {k: v for k, v in r.items() if not isinstance(v, (dict, list))}
    csv_save(d.BASE / "per-problem.csv", [flat(r) for r in per_problem])
    csv_save(d.BASE / "per-seed.csv", [flat(r) for r in per_seed])
    arm_rows = []
    for name, rows in assessments.items():
        for identifier in sorted({r["case_id"] for r in rows}):
            rs = [r for r in rows if r["case_id"] == identifier]
            arm_rows.append({"campaign": name, "id": identifier, "runs": len(rs),
                             "matches": sum(r["matched"] is True for r in rs),
                             "normal_completions": sum(r["normal_completion"] for r in rs),
                             "extra": sum(bool(r["extra"]) for r in rs),
                             "missing": sum(bool(r["missing"]) for r in rs)})
    csv_save(d.BASE / "answer-set-results.csv", arm_rows)
    csv_save(d.BASE / "stage-cell-results.csv", [dict(campaign=name, **r) for name, r in stage_cells.items()])
    csv_save(d.BASE / "per-problem-cell.csv", [dict(id=identifier, campaign=name,
                   **cell_statistics([identifier], f, r))
                   for name, ids, f, r in campaigns() for identifier in ids])
    csv_save(d.BASE / "order-results.csv", [{"id": r["id"], "status": r["status"],
                    "block": s["block"], "kind": s["kind"], "order_A": s["order_A_median"],
                    "order_B": s["order_B_median"], "quadratic_to_linear": s["quadratic_to_linear_compatible"]}
                   for r in orders for s in r.get("slopes", [])] +
                  [{"id": r["id"], "status": r["status"], "reason": r.get("reason", r.get("error", ""))}
                   for r in orders if not r.get("slopes")])
    write_answer(result, per_problem)
    print(json.dumps({"summary": "written", "gate": result["gate"], "execution": execution}))


def pp(x):
    return f"{100*x:+.1f}"


def rate(x):
    return f"{100*x:.1f}"


def write_answer(summary, problems):
    g, e = summary["gate"], summary["execution"]
    family_text = "、".join(f"{name} {int(r['crossing_supported'])}" for name, r in summary["families"].items())
    # Passing a numerical threshold alone cannot establish either of the two
    # conceptual criteria; those require a separately justified interpretation.
    rows = ["# Q39：探索と精密化で有利な表現は逆転するか", "",
        "| 4基準 | 判定 | 結果に基づく理由 |", "|---|---|---|",
        f"| 直感に反する | {'保留' if g['multi_command_gate'] else '不可'} | 事前基準を満たす独立命令族は{len(g['supported_independent_families'])}/2 |",
        "| 深い理論が必要 | 不可 | この実験から必要性を示せない。尖点・次数・行の重み・局所rankの説明を除外していない |",
        f"| 広がり・再現 | {'保留' if g['multi_command_gate'] else '不可'} | 両命令族・同一6問以上・3seedの固定条件を{'通過' if g['multi_command_gate'] else '満たさない'} |",
        f"| solverならでは | 不可 | A→Bの答え集合一致率の優越は{pp(g['AB_target_answer_set_advantage'])}ポイント。固有の能力を実証していない |", "",
        "**Aの中心を担えるか：現状では不可。後段Bの改善だけでは段間逆転ではなく、重根の正則化だけで説明できる結果も採用しない。**", "",
        "予測・診断設計・問題選択は一切変更していない。以下は凍結NOMAD単体＋診断用MpmathRefinerの結果であり、完成solverの性能ではない。", "",
        "## 固定と実行", "",
        f"- 予測固定commit `59691a92`、凍結src `60db4b6`。11固定ファイル・src 251ファイル・採点器・選択DSLのhashを実行前後に確認。",
        f"- 作業開始UTC `{d.read(d.BASE / 'execution-start.json')['execution_start_utc']}`。最初の探索開始UTC `{d.read(d.BASE / 'search-start.json')['utc']}`。",
        "- CPU 3・7・12に固定、最大3 worker、各ライブラリ1thread。各数値jobに150秒の外側監視。通常と必須対照を含む前段180 job、後段516 job。",
        "- 前段6秒/1,200 callback、後段8秒/候補、Phase C 20秒を維持。参考答えは全前段候補の封印後に別プロセスで読む。同定前の座標を180dpsで観測し、観測保存後に元AでPhase C。",
        "- 起動監視の不具合2件はPython worker開始前に停止。元記録を保存し、未着手分だけを開始した。開始済みの探索・精密化を再試行していない。", "",
        "## 主比較", "",
        "率は問題を等重み。Fの分母は24枠/問/前段、Rは前段A/B由来を合わせた48枠/問/後段。欠測・前段timeoutを成功から除外するが分母からは除かない。桁差は同じ候補に対するB−Aの増分差の問内中央値を取り、その問題間中央値。", "",
        "| 独立命令族 | 問題数 | F(A) % | F(B) % | ΔF pt | R(A) % | R(B) % | ΔR pt | paired桁差 | 200回共通到達率 % | 交差 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for name, r in summary["families"].items():
        rows.append(f"| {name} | {r['problem_count']} | {rate(r['front_A'])} | {rate(r['front_B'])} | {pp(r['front_difference'])} | {rate(r['rear_A'])} | {rate(r['rear_B'])} | {pp(r['rear_difference'])} | {r['paired_gain_difference']:+.2f} | {rate(r['common_prefix_200_fraction'])} | {'成立' if r['crossing_supported'] else '不成立'} |")
    rows += ["", "交差の固定閾値はΔF≥10pt、ΔR≥10pt、paired桁差≥20、両率を満たす同一3問以上/族、3seedすべてで両率差が正、共通200回到達/自然終了が90%以上。複数命令の支持には両族と合計6問以上を要求する。", "",
             "| 構造層 | n | ΔF pt | ΔR pt | paired桁差 |", "|---|---:|---:|---:|---:|"]
    for name, r in summary["strata"].items():
        rows.append(f"| {name} | {r['problem_count']} | {pp(r['front_difference'])} | {pp(r['rear_difference'])} | {r['paired_gain_difference']:+.2f} |")
    rows += ["", "問題単位bootstrap 10,000回・seed39099の95%記述区間、各seedの率差、共通評価回数の観測数は [summary.json](summary.json) に保存した。閾値の選択や採点には使用していない。", "",
             "## 重み・正則化・混合の対照", "",
             f"線円の重みを除くL（7問）はΔF={pp(summary['L']['front_difference'])}pt、ΔR={pp(summary['L']['rear_difference'])}pt、paired桁差={summary['L']['paired_gain_difference']:+.2f}。前後とも5pt以上を保つ条件は{'通過' if summary['L']['retains_5pp_gaps'] else '不通過'}。", "",
             "| R0比較 | BのΔR pt | R0のΔR pt | Bの正効果の再現割合 | 桁差の隔たり | 事前の正則化説明との整合 |",
             "|---|---:|---:|---:|---:|---|"]
    for name, r in summary["R0"].items():
        frac = "NA" if r["rate_effect_fraction_reproduced"] is None else f"{100*r['rate_effect_fraction_reproduced']:.1f}%"
        verdict = "整合" if r["regularization_explanation_compatible"] else ("閾値未達" if r["B_positive_effect_ge_10pp"] else "Bの正効果10pt未満・判定対象外")
        rows.append(f"| {name} | {pp(r['B']['rear_difference'])} | {pp(r['R0']['rear_difference'])} | {frac} | {r['median_gain_distance']:.2f} | {verdict} |")
    rows += ["", "R0はBの枝符号を利用する診断であり独立solverではない。Bとの差が残っても、深い理論の必要性を示すものではない。", "",
             "| 混合1問でBにする行 | ΔF pt | ΔR pt | paired桁差 |", "|---|---:|---:|---:|"]
    for name, r in summary["masked"].items():
        rows.append(f"| {name} | {pp(r['front_difference'])} | {pp(r['rear_difference'])} | {r['paired_gain_difference']:+.2f} |")
    rows += ["", f"局所消失次数の対象21問：{json.dumps(summary['orders']['statuses'], ensure_ascii=False)}。二次→一次に整合する行を持つ問題は{len(summary['orders']['cases_with_quadratic_to_linear_row'])}問。元検証済みの保存点がない場合はNAとし、新しい根は探索していない。次数は全隣接log slopeの中央値で、接点の別等式面から外れる方向も含むため証明ではない。NAから正則化説を排除しない。", "",
             "## 答え集合の既存採点", "",
             "`benchmarks.research_runner.assess_campaign`を変更せず実行。完全なcanonical答え集合と正常終了を要求し、余剰値・欠落値を保持した。", "",
             "| 通常条件 | 対象21問×3seedの一致 | 一致率 % | 全25問×3seedの一致 |", "|---|---:|---:|---:|"]
    for cell in ("AA", "AB", "BA", "BB"):
        r = summary["official"]["normal-" + cell]
        rows.append(f"| {cell[0]}→{cell[1]} | {r['target_matches']}/{r['target_runs']} | {rate(r['target_rate'])} | {r['all_matches']}/{r['all_runs']} |")
    rows += ["", f"A→Bの他3条件の最良値に対する差は{pp(g['AB_target_answer_set_advantage'])}pt。5pt以上の固定条件は{'通過' if g['answer_set_advantage_gate'] else '不通過'}。L・R0・混合対照を含む全採点は [answer-set-results.csv](answer-set-results.csv) とsummaryに記載。", "",
             "## 全25問", "", "| 問題 | ΔF pt | ΔR pt | paired桁差 | F/R両率閾値 |", "|---|---:|---:|---:|---|"]
    for r in problems:
        rows.append(f"| {r['id']} | {pp(r['front_difference'])} | {pp(r['rear_difference'])} | {r['paired_gain_difference']:+.2f} | {'通過' if r['both_rate_gates'] else '不通過'} |")
    rows += ["", "有限候補だけの条件付きRと分母も [per-problem.csv](per-problem.csv)、seed別は [per-seed.csv](per-seed.csv) に保存。成績による除外・問題の交換はない。", "",
             "## 完了・失敗・資源の記録", "",
             f"- 保存枠：前段{e['front_slots']}/1440、後段{e['rear_slots']}/4128、同定前観測{e['measurement_records']}/4128、Phase C {e['phase_c_records']}/516。",
             f"- 前段：欠測{e['front_candidate_missing']}、timeout {e['front_timeouts']}、例外{e['front_errors']}。後段：欠測{e['rear_missing']}、例外{e['rear_errors']}、終了状態 {json.dumps(e['rear_statuses'], ensure_ascii=False)}。",
             f"- Phase C時間切れ{e['phase_c_timeouts']}。正常に保存された途中結果の扱いは元採点器のstatus規則に従う。強制終了は正常終了に置換しない。",
             f"- Bのfallback回数：前段{e['front_rewrite_fallbacks']}、後段{e['rear_rewrite_fallbacks']}。行数不一致：前段{e['front_row_mismatches']}、後段{e['rear_row_mismatches']}。無効Bは共通Q/Rで成功に数えない。",
             f"- 同一円の後段最終点観測：180dpsで一致{e['coincident_circle_exact_final_count']}枠、1e-30の近接診断を含め{e['coincident_circle_near_final_count']}枠。元Aによる測定・検証を維持した。",
             f"- callback上限違反{e['front_callback_limit_violations']}、worker開始後のaffinity違反{e['affinity_violations']}。最大worker＋子プロセスRSS {e['peak_worker_tree_rss_bytes']/1024**2:.1f} MiB。",
             f"- 最大ファイル{e['max_file_bytes']:,} bytes。5,000,000 bytes以上のファイルは{len(e['oversized_files'])}件。生記録は`.gitignore`対象とし、src・予測固定ファイルへの変更は0。",
             "", "共有機の時間上限はCPU使用可能量の揺れを含む。共通評価回数の不足や観測NAがあれば機構判断を保留し、実行時間だけを研究核の根拠にしない。", "",
             "[予測](prediction.md) / [診断設計](diagnostic-design.md) / [実行開始記録](execution-start.json) / [配線検査](wiring-check.json) / [実装](diagnostic.py)", ""]
    (d.BASE / "answer.md").write_text("\n".join(rows))


if __name__ == "__main__":
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (4_900_000, 4_900_000))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["grade", "summarize"])
    p.add_argument("--campaign")
    args = p.parse_args()
    if args.command == "grade":
        grade_campaign(args.campaign)
    else:
        summarize()
