"""Independent post-run reference scoring and fixed Q9 hypothesis evaluation."""
from __future__ import annotations

import csv
from collections import Counter
import json
import math
from pathlib import Path

import numpy as np

from experiment import OUT, ROOT, METHODS, SEEDS, NSTART, clean, save, verify_freeze
from probe_basins import reference_values


def write_csv(name, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (OUT / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def numeric_match(value, refs):
    if value is None or not math.isfinite(value):
        return None
    return next((k for k, ref in enumerate(refs) if abs(value-ref) <= 1e-6*max(1.0, abs(ref))), None)


def main():
    verify_freeze()
    manifest = json.loads((OUT / "manifest.json").read_text())
    ids = manifest["selected"]
    paths = [OUT / "raw" / f"{cid}__{seed}.json" for cid in ids for seed in SEEDS]
    missing = [str(path.relative_to(OUT)) for path in paths if not path.exists()]
    if missing:
        raise RuntimeError("All scheduled tasks must finish before reference scoring: " + repr(missing))
    # First and only benchmark reference access in the new pilot evaluation.
    references = {}
    for line in (ROOT / "benchmarks/cases.jsonl").read_text().splitlines():
        case = json.loads(line)
        if case["id"] in ids:
            references[case["id"]] = reference_values(case["answer"])
    runs, starts, checks, issues = [], [], [], []
    byrun = {}
    for path in paths:
        task = json.loads(path.read_text())
        cid, seed = task["id"], task["seed"]
        refs = references[cid]
        first_rows = []
        prefixes = []
        for method in METHODS:
            result = task["methods"][method]
            assert len(result["rows"]) == NSTART
            prep = result["prep_sec"]
            elapsed = prep
            first_hit_time = None
            first_candidate_time = None
            first_hit_k = None
            n_hit, n_wrong = 0, 0
            seen_refs = set()
            n_candidate = 0
            for row in result["rows"]:
                elapsed += row["sec"]
                original = row["status"]
                scored = original
                ref = None
                if original == "candidate":
                    n_candidate += 1
                    if first_candidate_time is None:
                        first_candidate_time = elapsed
                    ref = numeric_match(row.get("answer"), refs)
                    if ref is not None:
                        scored = "hit"
                        n_hit += 1
                        seen_refs.add(ref)
                        if first_hit_time is None:
                            first_hit_time = elapsed
                            first_hit_k = row["k"]
                    else:
                        scored = "wrong_answer"
                        n_wrong += 1
                starts.append({"id": cid, "seed": seed, "method": method, "k": row["k"],
                    "pool_index": row.get("pool_index"), "status": scored, "original_status": original,
                    "ref": ref, "answer": row.get("answer"), "residual": row.get("residual"),
                    "start_feasible": row.get("start_feasible"),
                    "start_residual_finite": row.get("start_residual_finite"),
                    "solve_sec": row.get("solve_sec"), "check_sec": row.get("check_sec"),
                    "sec": row["sec"], "nfev": row.get("nfev"),
                    "start": json.dumps(row.get("start")), "x": json.dumps(row.get("x"))})
            run = {"id": cid, "seed": seed, "method": method,
                "S8": int(first_hit_time is not None),
                "S16": int(first_hit_time is not None and first_hit_time <= 16),
                "C16": min(16, first_hit_time) if first_hit_time is not None else 16,
                "first_hit_sec": first_hit_time, "first_hit_k": first_hit_k,
                "first_candidate_sec": first_candidate_time, "n_hits": n_hit, "p": n_hit / NSTART,
                "n_candidates": n_candidate, "n_wrong_answer": n_wrong,
                "all_references_seen": int(len(seen_refs) == len(refs)), "n_references": len(refs),
                "prep_sec": prep, "full8_sec": elapsed,
                "solve8_sec": sum(r.get("solve_sec", 0) for r in result["rows"]),
                "check8_sec": sum(r.get("check_sec", 0) for r in result["rows"]),
                "nfev": sum(r.get("nfev", 0) for r in result["rows"]),
                "unique_signatures": result.get("n_unique_signatures"),
                "n_varying": task["methods"]["G"].get("n_varying"),
                "n_pool_signatures": task["methods"]["G"].get("pool_unique_signatures"),
                "missing_fraction": task["methods"]["G"].get("missing_fraction"),
                "n_feasible": sum(r.get("start_feasible", False) for r in result["rows"]),
                "n_finite_residual": sum(r.get("start_residual_finite", False) for r in result["rows"]),
                "prep_failed": int("prep_error" in result)}
            runs.append(run)
            byrun[(cid, seed, method)] = run
            first_rows.append(result["rows"][0])
            prefixes.append(result.get("selected_strata"))
        complete = all(p is not None for p in prefixes)
        stratum_ok = complete and all(p == prefixes[0] for p in prefixes)
        comparable = all(r["status"] not in ("timeout", "prep_failure") for r in first_rows)
        first_equal = comparable and all(r["status"] == first_rows[0]["status"] and r.get("x") == first_rows[0].get("x")
                                         and r.get("answer") == first_rows[0].get("answer") for r in first_rows)
        check = {"id": cid, "seed": seed, "strata_available": complete,
                 "prefix_strata_equal": stratum_ok, "first_comparable": comparable,
                 "first_status_endpoint_answer_exactly_equal": first_equal}
        checks.append(check)
        if (complete and not stratum_ok) or (comparable and not first_equal):
            issues.append(check)

    rows = []
    fields = ("S8", "S16", "C16", "p", "n_hits", "n_wrong_answer", "prep_sec", "full8_sec",
              "nfev", "unique_signatures", "n_varying", "n_pool_signatures", "missing_fraction",
              "n_feasible", "n_finite_residual", "prep_failed")
    for cid in ids:
        row = {"id": cid}
        for method in METHODS:
            rr = [byrun[cid, seed, method] for seed in SEEDS]
            for field in fields:
                values = [r[field] for r in rr if r[field] is not None]
                row[f"{method}_{field}"] = float(np.mean(values)) if values else None
            row[f"{method}_success_seeds"] = sum(r["S8"] for r in rr)
        row["G_minus_U_success_seeds"] = row["G_success_seeds"] - row["U_success_seeds"]
        row["G_minus_X_success_seeds"] = row["G_success_seeds"] - row["X_success_seeds"]
        rows.append(row)
    # Problem-level bootstrap; three seeds stay in the same resampled unit.
    index = np.random.default_rng(910299).integers(0, len(ids), (10000, len(ids)))
    def compare(a, b, field):
        aa = np.asarray([r[f"{a}_{field}"] for r in rows], dtype=float)
        bb = np.asarray([r[f"{b}_{field}"] for r in rows], dtype=float)
        delta = aa - bb
        boots = delta[index].mean(1)
        return {"delta": float(delta.mean()), "ci95": np.quantile(boots, [.025, .975]).tolist(),
                "mean_a": float(aa.mean()), "mean_b": float(bb.mean()),
                "ratio": float(aa.mean()/bb.mean()) if bb.mean() else None}
    comparisons = {f"{a}-{b}_{field}": compare(a, b, field)
                   for a, b in (("G", "U"), ("G", "X"), ("X", "U"))
                   for field in ("S8", "S16", "C16", "p", "full8_sec", "prep_sec", "unique_signatures")}
    p1 = comparisons["G-U_S8"]
    p2 = comparisons["G-X_S8"]
    p3u, p3x = comparisons["G-U_C16"], comparisons["G-X_C16"]
    win2 = sum(r["G_minus_U_success_seeds"] >= 2 for r in rows)
    lose2 = sum(r["G_minus_U_success_seeds"] <= -2 for r in rows)
    predictions = {
        "P1": {"passed": p1["delta"] >= .10 and p1["ci95"][0] > 0, **p1},
        "P2": {"passed": p2["delta"] >= .05 and p2["ci95"][0] > 0, **p2},
        "P3": {"passed": p3u["ratio"] <= .80 and p3x["ratio"] <= .90 and p3u["ci95"][1] < 0 and p3x["ci95"][1] < 0,
               "G-U": p3u, "G-X": p3x},
        "P4": {"passed": win2 >= 6 and lose2 <= 2, "wins_at_least_2_seeds": win2, "losses_at_least_2_seeds": lose2}}
    stats = {}
    for method in METHODS:
        rr = [r for r in runs if r["method"] == method]
        ss = [r for r in starts if r["method"] == method]
        stats[method] = {"runs": len(rr), "starts": len(ss),
            "S8_successes": sum(r["S8"] for r in rr), "S8_mean": np.mean([r["S8"] for r in rr]),
            "S16_successes": sum(r["S16"] for r in rr),
            "C16_mean": np.mean([r["C16"] for r in rr]),
            "hits": sum(r["n_hits"] for r in rr), "candidates": sum(r["n_candidates"] for r in rr),
            "wrong_answers": sum(r["n_wrong_answer"] for r in rr),
            "prep_mean": np.mean([r["prep_sec"] for r in rr]), "prep_median": np.median([r["prep_sec"] for r in rr]),
            "full8_mean": np.mean([r["full8_sec"] for r in rr]),
            "nfev": sum(r["nfev"] for r in rr), "statuses": dict(Counter(r["status"] for r in ss)),
            "unique_signatures_mean": np.mean([r["unique_signatures"] for r in rr]),
            "solved_problems_any_seed": sum(r[f"{method}_success_seeds"] > 0 for r in rows),
            "solved_problems_all_seeds": sum(r[f"{method}_success_seeds"] == len(SEEDS) for r in rows)}
    with (ROOT / "jssa/difficulty/ghost-1023/human_feat.csv").open() as stream:
        human = {r["case_id"]: r for r in csv.DictReader(stream)}
    coverage = []
    for cid in ids:
        h = human.get(cid, {})
        coverage.append({"id": cid, "contest": h.get("contest", ""), "human": h.get("human", ""),
                         "human_available": bool(h.get("human"))})
    summary = {"n_problems": len(ids), "n_seeds": len(SEEDS), "n_runs": len(runs), "n_starts": len(starts),
        "predictions": predictions, "central_candidate_supported": all(r["passed"] for r in predictions.values()),
        "stats": stats, "comparisons": comparisons,
        "checks": {"n_tasks": len(checks), "stratum_matches": sum(r["prefix_strata_equal"] for r in checks),
                   "first_comparable": sum(r["first_comparable"] for r in checks),
                   "first_exact_matches": sum(r["first_status_endpoint_answer_exactly_equal"] for r in checks),
                   "issues": issues, "frozen_hashes_unchanged": True},
        "geometry": {"constant_feature_runs": sum(r["n_varying"] == 0 for r in runs if r["method"] == "G"),
                     "varying_columns_median": np.median([r["n_varying"] for r in runs if r["method"] == "G"]),
                     "missing_fraction_mean": np.mean([r["missing_fraction"] for r in runs if r["method"] == "G"])},
        "human_coverage": {"n": sum(r["human_available"] for r in coverage),
                           "by_contest": dict(Counter(r["contest"] for r in coverage if r["human_available"]))}}
    write_csv("per-start.csv", starts)
    write_csv("per-run.csv", runs)
    write_csv("per-problem.csv", rows)
    write_csv("run-checks.csv", checks)
    write_csv("human-coverage.csv", coverage)
    save(OUT / "summary.json", summary)
    print(json.dumps(clean(summary), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
