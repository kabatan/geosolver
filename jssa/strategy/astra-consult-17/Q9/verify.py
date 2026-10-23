"""Post-measurement integrity audit; never changes protocol, code or raw runs."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
import math

import numpy as np

from experiment import (OUT, ROOT, METHODS, SEEDS, NSTART, build, point_names, rng_for,
                        figure, orientation_signature, triples_for, strata_at, save, sha, verify_freeze)
from probe_basins import answer_float, construction_coordinates, reference_values


def main():
    verify_freeze()
    manifest = json.loads((OUT / "manifest.json").read_text())
    ids = manifest["selected"]
    issues = []
    counts = Counter()
    method_rows = defaultdict(list)
    coordinate_errors = []
    selected_metadata = []
    duplicate_solves = []
    cases = {c["id"]: c for c in (json.loads(line) for line in (ROOT / "benchmarks/cases.jsonl").read_text().splitlines()) if c["id"] in ids}
    for case_index, cid in enumerate(ids):
        case = cases[cid]
        refs = reference_values(case["answer"])
        bundle, ev = build(case["dsl"])
        names = sorted(point_names(case["dsl"]))
        trip = triples_for(cid, names)
        projected = {}
        if case_index < 8:
            for name in names:
                try:
                    projected.update(construction_coordinates(case["dsl"], [name]))
                except Exception:
                    # Non-point construction candidates are explicitly missing.
                    pass
        info = next(r for r in manifest["inventory"] if r["id"] == cid)
        selected_metadata.append({"id": cid, "n_vars": info["n_vars"],
            "n_constraints": info["n_constraints"], "point_candidates": info["point_candidates"]})
        for seed in SEEDS:
            task = json.loads((OUT / "raw" / f"{cid}__{seed}.json").read_text())
            counts["tasks"] += 1
            gmeta = task["methods"]["G"]
            box = np.asarray(gmeta["box"])
            unit = rng_for(cid, seed).random((256, len(box)))
            pool = box[:, 0] + unit * (box[:, 1] - box[:, 0])
            cache = {}
            by_start = defaultdict(list)
            for method in METHODS:
                result = task["methods"][method]
                fresh_hits = []
                elapsed = result["prep_sec"]
                first_candidate_correct = None
                first_candidate_time = None
                for row in result["rows"]:
                    counts["starts"] += 1
                    k = row["k"]
                    start = np.asarray(row["start"])
                    ix = row["pool_index"]
                    if not np.array_equal(start, pool[ix]):
                        issues.append((cid, seed, method, k, "start_not_rng_pool"))
                    if ix not in cache:
                        cache[ix] = strata_at(ev, start)
                    st = cache[ix]
                    if bool(st // 2) != row["start_feasible"] or bool(st % 2) != row["start_residual_finite"]:
                        issues.append((cid, seed, method, k, "fresh_stratum_mismatch"))
                    counts["start_strata_recomputed"] += 1
                    by_start[ix].append((method, k, row))
                    # Verify stored signs at selected starts with fresh construction contexts.
                    coords = figure(ev, start, names)
                    sig = orientation_signature(coords, trip)[gmeta["varying_columns"]].tolist()
                    if sig != result["selected_signatures"][k]:
                        issues.append((cid, seed, method, k, "fresh_signature_mismatch"))
                    counts["selected_signatures_recomputed"] += 1
                    if case_index < 8 and seed == SEEDS[0] and (method, k) in (("U", 0), ("G", 7)):
                        values = dict(zip(bundle.var_names, start))
                        for j, name in enumerate(names):
                            for axis_i, axis in enumerate(("x", "y")):
                                key = f"{axis}_{name}"
                                if key not in projected:
                                    continue
                                vn, pe = projected[key]
                                value = answer_float(pe, [values[v] for v in vn])
                                if value is not None and math.isfinite(value) and np.isfinite(coords[j, axis_i]):
                                    error = abs(value-coords[j, axis_i])/max(1, abs(value))
                                    coordinate_errors.append(float(error))
                                    if error > 1e-8:
                                        issues.append((cid, seed, method, k, "coordinate_projection_difference", key, float(error)))
                    elapsed += row["sec"]
                    hit = False
                    if row["status"] == "candidate":
                        x = row["x"]
                        snap = ev.evaluate_float_residual(x)
                        hard = ev.evaluate_float_hard_feasibility(x, include_margins=False)
                        guard, _ = ev.evaluate_guard(x)
                        residual = np.linalg.norm(np.asarray(snap.residual_vector, dtype=float))
                        finite = math.isfinite(residual)
                        in_box = np.all(np.asarray(x) >= box[:, 0]) and np.all(np.asarray(x) <= box[:, 1])
                        if not (finite and residual <= 1e-8 and hard.hard_feasible and guard and in_box):
                            issues.append((cid, seed, method, k, "candidate_fresh_conditions_failed", float(residual)))
                        value = answer_float(ev, x)
                        if value is None or abs(value-row["answer"]) > 1e-12*max(1, abs(row["answer"])):
                            issues.append((cid, seed, method, k, "fresh_answer_mismatch"))
                        hit = value is not None and any(abs(value-r) <= 1e-6*max(1, abs(r)) for r in refs)
                        counts["candidates_rechecked"] += 1
                        if first_candidate_correct is None:
                            first_candidate_correct = hit
                            first_candidate_time = elapsed
                    fresh_hits.append(hit)
                method_rows[method].append({"id": cid, "seed": seed, "success": any(fresh_hits),
                    "first_candidate_correct": first_candidate_correct, "first_candidate_sec": first_candidate_time,
                    "first_candidate_C16": min(16, first_candidate_time) if first_candidate_time is not None else 16,
                    "timeouts": sum(r["status"] == "timeout" for r in result["rows"]),
                    "has_timeout": any(r["status"] == "timeout" for r in result["rows"])})
            for ix, group in by_start.items():
                comparable = [g for g in group if g[2]["status"] != "timeout"]
                if len(comparable) < 2:
                    continue
                first = comparable[0][2]
                same = all(r["status"] == first["status"] and r.get("x") == first.get("x") and r.get("answer") == first.get("answer")
                           for _, _, r in comparable[1:])
                duplicate_solves.append({"id": cid, "seed": seed, "pool_index": ix,
                                         "n_methods": len(comparable), "exactly_equal": same})
                if not same:
                    issues.append((cid, seed, ix, "same_start_different_endpoint"))
    summary = json.loads((OUT / "summary.json").read_text())
    for method, rows in method_rows.items():
        if sum(r["success"] for r in rows) != summary["stats"][method]["S8_successes"]:
            issues.append((method, "independent_hit_count_mismatch"))
    problem_rows = list(csv.DictReader((OUT / "per-problem.csv").open()))
    different = []
    for row in problem_rows:
        a = int(row["U_success_seeds"])
        b = int(row["X_success_seeds"])
        c = int(row["G_success_seeds"])
        if len({a, b, c}) > 1:
            different.append({"id": row["id"], "U": a, "X": b, "G": c,
                              "U_C16": float(row["U_C16"]), "X_C16": float(row["X_C16"]), "G_C16": float(row["G_C16"])})
    diagnostics = {"method": {method: {
        "first_candidate_correct": sum(r["first_candidate_correct"] is True for r in rr),
        "first_candidate_wrong": sum(r["first_candidate_correct"] is False for r in rr),
        "no_candidate": sum(r["first_candidate_correct"] is None for r in rr),
        "first_candidate_C16_mean": np.mean([r["first_candidate_C16"] for r in rr]),
        "successful_runs_with_timeout": sum(r["success"] and r["has_timeout"] for r in rr),
        "unsuccessful_runs_with_timeout": sum(not r["success"] and r["has_timeout"] for r in rr)} for method, rr in method_rows.items()},
        "problems_with_different_success_counts": different,
        "G_better_problem_count": sum(int(r["G_success_seeds"]) > int(r["U_success_seeds"]) for r in problem_rows),
        "G_worse_problem_count": sum(int(r["G_success_seeds"]) < int(r["U_success_seeds"]) for r in problem_rows),
        "variable_count_histogram": dict(Counter(r["n_vars"] for r in selected_metadata)),
        "note": "記述・検算。追加の合格基準ではない。first-candidateは数値候補で、証明・精密化を含まない。"}
    save(OUT / "verification.json", {"passed": not issues, "counts": dict(counts), "issues": issues,
        "independent_coordinate_projection_count": len(coordinate_errors),
        "max_coordinate_relative_difference": max(coordinate_errors, default=None),
        "repeated_start_groups": len(duplicate_solves),
        "repeated_start_groups_exactly_equal": sum(r["exactly_equal"] for r in duplicate_solves),
        "frozen_hashes_unchanged": True,
        "source_sha256": sha(OUT / "verify.py")})
    save(OUT / "diagnostics.json", diagnostics)
    save(OUT / "repeated-start-audit.json", duplicate_solves)
    print(json.dumps({"passed": not issues, "counts": dict(counts), "issues": issues,
                      "coordinate_max_difference": max(coordinate_errors, default=None),
                      "different_success_problems": different}, ensure_ascii=False, indent=2))
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
