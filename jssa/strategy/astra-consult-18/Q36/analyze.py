"""Q36 stage 1: aggregate saved records only; never import or run a solver.

Run from any directory with Python 3. Standard library only, no network.
After prediction.lock.json exists, only --check (read-only) is permitted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
LIMIT = 5_000_000
sources: dict[str, dict] = {}
products: dict[str, bytes] = {}


def read(path: str) -> str:
    blob = (ROOT / path).read_bytes()
    sources[path] = {"path": path, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}
    return blob.decode("utf-8")


def read_json(path: str):
    return json.loads(read(path))


def csv_input(path: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(read(path))))


def emit_json(name: str, obj) -> None:
    products[name] = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def emit_csv(name: str, rows: list[dict]) -> None:
    assert rows, name
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    products[name] = buf.getvalue().encode()


def answer_items(answer) -> list[str]:
    items = answer if isinstance(answer, list) else [answer]
    result = []
    for value in items:
        text = re.sub(r"\(\d+個\)", "", str(value))
        result.extend(s.strip() for s in ([text] if "CRootOf" in text else text.split(",")) if s.strip())
    return result


def wilson(h: int, n: int):
    """Descriptive binomial interval; archive time-censoring is not ignored in the report."""
    if not n:
        return None, None
    z = 1.959963984540054
    p = h / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def iid_missing(probabilities: list[float], draws: int):
    """Inclusion-exclusion model, not an estimate of full-solver failure."""
    result = 0.0
    for mask in range(1, 1 << len(probabilities)):
        mass = sum(p for i, p in enumerate(probabilities) if mask & (1 << i))
        sign = 1 if mask.bit_count() % 2 else -1
        result += sign * max(0.0, 1 - mass) ** draws
    return max(0.0, min(1.0, result))


def inspect_archive(path: str, cid: str) -> dict:
    d = read_json(path)
    assert d["case_id"] == cid, path
    records = d.get("records", [])
    if "starts_done" in d:
        assert len(records) == d["starts_done"], path
    if "counts" in d:
        assert dict(Counter(r["cls"] for r in records)) == d["counts"], path
    refs = d.get("references", [])
    hits = [sum(r.get("cls") == "hit" and r.get("ref") == j for r in records) for j in range(len(refs))]
    if "hits_by_ref" in d:
        assert hits == d["hits_by_ref"], path
    assert sum(hits) == sum(r.get("cls") == "hit" for r in records), path
    for r in records:
        if r.get("cls") == "hit":
            ref = refs[r["ref"]]
            assert abs(r["ans"] - ref) <= 1e-6 * max(1, abs(ref)), (path, r["k"])
    return d


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="recompute saved-data aggregates in memory and compare bytes")
    args = parser.parse_args()
    if (OUT / "prediction.lock.json").exists() and not args.check:
        raise SystemExit("Prediction is locked. Use --check; overwriting locked artifacts is forbidden.")

    read(str(Path(__file__).relative_to(ROOT)))
    for path in [
        "jssa/strategy/codex-tasks-1023.md",
        "jssa/strategy/gpt-pro-consult-18-prompt.md",
        "jssa/strategy/gpt-pro-consult-18-answer.md",
        "jssa/difficulty/probe_basins.py",
        "src/geosolver/engine/standard/problem/load_problem_bundle.py",
    ]:
        read(path)
    basin_rows = csv_input("jssa/difficulty/minima/basins-323.csv")
    assert len(basin_rows) == 323
    basin_lookup = {r["id"]: r for r in basin_rows}
    assert len(basin_lookup) == 323
    attr = csv_input("jssa/results/mechanism-attribution/attribution.csv")
    stages = csv_input("jssa/results/stage-profile-20261023/per-case.csv")
    stage_lookup = {(r["case_id"], r["seed"]): r for r in stages}
    assert len(attr) == len(stages) == len(stage_lookup) == 969
    assert len({(r["case_id"], r["seed"]) for r in attr}) == 969
    for r in attr:
        assert r["matched"] == stage_lookup[r["case_id"], r["seed"]]["correct"]
    assert sum(r["matched"] == "True" for r in attr) == 953

    census, selected, scope_notes = [], {}, []
    for cohort, path, rawdir in [
        ("development", "benchmarks/cases.jsonl", "jssa/difficulty/minima/raw-323"),
        ("2026", "jssa/difficulty/new2026/cases.jsonl", "jssa/difficulty/new2026-predict/raw"),
    ]:
        cases = [json.loads(line) for line in read(path).splitlines() if line.strip()]
        assert len(cases) == (323 if cohort == "development" else 20)
        for case in cases:
            cid = case["id"]
            exprs = answer_items(case["answer"])
            archive = f"{rawdir}/{cid}.json"
            d = inspect_archive(archive, cid) if (ROOT / archive).exists() else None
            if d is not None:
                assert len(d.get("references", [])) == len(exprs), cid
            eligible = len(exprs) > 1
            census.append({
                "cohort": cohort, "case_id": cid, "reference_count": len(exprs),
                "reference_expressions": " | ".join(exprs), "target": case["dsl"]["target"],
                "multiple_answers": eligible, "archive_path": archive if d is not None else "",
                "archive_reference_count": len(d.get("references", [])) if d is not None else None,
                "archive_completed_starts": d.get("starts_done") if d is not None else None,
            })
            if eligible:
                assert cohort == "development" and d is not None
                seed1 = inspect_archive(f"jssa/difficulty/minima/raw-323-seed1/{cid}.json", cid)
                assert d["references"] == seed1["references"] and d["box"] == seed1["box"], cid
                assert len(set(d["references"])) == len(exprs), cid
                assert int(basin_lookup[cid]["n_starts"]) == len(d["records"]), cid
                assert math.isclose(float(basin_lookup[cid]["p"]), d["p_any"], abs_tol=1e-12), cid
                selected[cid] = (case, [d, seed1])
            if cid == "AIME-2013-II-15":
                scope_notes.append({"case_id": cid, "references": exprs, "target": case["dsl"]["target"],
                                    "disposition": "single-valued in this checkout; requested r1 version unavailable"})
    assert len(selected) == 8
    emit_csv("input-census.csv", census)

    local_rows, case_rows, coverage, full_rows, proxy_rows, models = [], [], [], [], [], []
    geometry_checks = []
    for cid, (case, ds) in sorted(selected.items()):
        exprs = answer_items(case["answer"])
        refs = ds[0]["references"]
        k_values = len(refs)
        full = sorted([r for r in attr if r["case_id"] == cid], key=lambda r: int(r["seed"]))
        assert [r["seed"] for r in full] == ["0", "1", "2"]
        n_equal = sum(r["set_relation"] == "equal" for r in full)
        n_empty = sum(r["status"] == "no_answer_found" for r in full)
        n_ambiguous = len(full) - n_equal - n_empty
        assert all(r["set_relation"] in {"equal", "missing"} for r in full)
        for r in full:
            full_rows.append({key: r[key] for key in [
                "case_id", "seed", "status", "matched", "set_relation", "answer_source_stage",
                "answer_source_uid_prefix", "failure_stage", "refine_attempted", "refine_converged",
                "exact_accepted", "wall_s",
            ]} | {"returned_values_available": False,
                  "per_value_inference": "all_present_from_equal" if r["set_relation"] == "equal" else
                  "all_absent_from_no_answer_found" if r["status"] == "no_answer_found" else "unknown_which_value_missing"})

        ns = [len(d["records"]) for d in ds]
        hs = [[sum(r.get("cls") == "hit" and r.get("ref") == j for r in d["records"]) for j in range(k_values)] for d in ds]
        pooled = [sum(h[j] for h in hs) for j in range(k_values)]
        total_n, total_hit = sum(ns), sum(pooled)
        for label, n, hits in [(str(d["seed"]), n, h) for d, n, h in zip(ds, ns, hs)] + [("pooled", total_n, pooled)]:
            any_hit = sum(hits)
            for j, count in enumerate(hits):
                lo, hi = wilson(count, n)
                qlo, qhi = wilson(count, any_hit)
                local_rows.append({
                    "case_id": cid, "seed": label, "ref_index": j, "value_expression": exprs[j],
                    "value_numeric": refs[j], "completed_starts": n, "hits_any_value": any_hit,
                    "value_hits": count, "p_value_per_start": count / n,
                    "q_value_given_hit": count / any_hit if any_hit else None,
                    "p_wilson_low_descriptive": lo, "p_wilson_high_descriptive": hi,
                    "q_wilson_low_descriptive": qlo, "q_wilson_high_descriptive": qhi,
                    "zero_count_iid_one_sided_upper95": 1 - 0.05 ** (1 / n) if count == 0 else None,
                })
        q = [h / total_hit for h in pooled] if total_hit else None
        case_rows.append({
            "case_id": cid, "value_count": k_values, "n_seed0": ns[0], "n_seed1": ns[1],
            "hits_seed0": ";".join(map(str, hs[0])), "hits_seed1": ";".join(map(str, hs[1])),
            "hits_pooled": ";".join(map(str, pooled)), "total_n": total_n, "total_hits": total_hit,
            "p_any": total_hit / total_n, "p_min": min(pooled) / total_n,
            "q_min": min(q) if q else None, "q_max": max(q) if q else None,
            "max_min_hit_ratio": max(pooled) / min(pooled) if min(pooled) else None,
            "unobserved_value_count": sum(h == 0 for h in pooled),
            "effective_values_given_hit": 1 / sum(x*x for x in q) if q else None,
            "iid_missing_after20_attempts_plugin": iid_missing([h/total_n for h in pooled], 20),
            "iid_missing_after20_hits_plugin": iid_missing(q, 20) if q else None,
            "full_runs": len(full), "full_equal": n_equal, "full_missing": len(full)-n_equal,
            "full_no_answer": n_empty, "full_partial_missing_value_unknown": n_ambiguous,
            "full_sources": " | ".join(sorted({r["answer_source_uid_prefix"] for r in full})),
        })
        for j, ref in enumerate(refs):
            coverage.append({
                "case_id": cid, "ref_index": j, "value_expression": exprs[j], "value_numeric": ref,
                "full_runs": 3, "present_runs_lower_bound": n_equal,
                "present_runs_upper_bound": n_equal+n_ambiguous, "absent_runs_lower_bound": n_empty,
                "absent_runs_upper_bound": n_empty+n_ambiguous, "unknown_runs": n_ambiguous,
                "basis": "equal set => all present; no_answer_found => all absent; partial missing => identity unknown",
            })

        # A position-only baseline: one representative per value, same box metric.
        # All start coordinates below are saved seed-0 coordinates, not regenerated.
        d0 = ds[0]
        if all(h > 0 for h in hs[0]):
            box = d0["box"]
            def normalize(x):
                return [(v-a)/(b-a) for v, (a, b) in zip(x, box)]
            def dist(x, y):
                return sum((a-b)**2 for a, b in zip(x, y))
            centers, representative_k = [], []
            for j in range(k_values):
                rs = [r for r in d0["records"] if r.get("cls") == "hit" and r.get("ref") == j]
                assert all("x" in r for r in rs), cid
                xs = [normalize(r["x"]) for r in rs]
                mean = [statistics.mean(x[l] for x in xs) for l in range(len(box))]
                index = min(range(len(xs)), key=lambda i: (dist(xs[i], mean), rs[i]["k"]))
                centers.append(xs[index])
                representative_k.append(rs[index]["k"])
            counts = [0] * k_values
            assert all("start" in r for r in d0["records"]), cid
            for r in d0["records"]:
                start = normalize(r["start"])
                nearest = min(range(k_values), key=lambda j: (dist(start, centers[j]), j))
                counts[nearest] += 1
            models.append({"case_id": cid, "box": box, "value_expressions": exprs, "values": refs,
                           "normalized_centers": centers, "representative_seed0_k": representative_k,
                           "saved_start_cell_counts": counts, "saved_start_count": ns[0]})
            for j in range(k_values):
                g = counts[j] / ns[0]
                q1 = hs[1][j] / sum(hs[1])
                proxy_rows.append({
                    "case_id": cid, "ref_index": j, "value_expression": exprs[j],
                    "seed0_voronoi_start_count": counts[j], "seed0_saved_starts": ns[0],
                    "position_proxy_g": g, "seed1_q_given_hit": q1,
                    "abs_difference": abs(g-q1), "proxy_rare_g_le_0_20": g <= 0.20,
                    "seed1_rare_q_le_0_20": q1 <= 0.20,
                    "prospective_validation": False,
                })
        if cid == "AIME-2007-I-15":
            for j in range(k_values):
                xs = [r["x"] for r in d0["records"] if r.get("ref") == j]
                t = statistics.median(2*x[1]/x[0] for x in xs)
                geometry_checks.append({"case_id": cid, "value_expression": exprs[j],
                                        "quantity": "AE/AC = 2*ex/s", "value": t,
                                        "boundary_margin": min(t, 1-t), "basis": "saved seed0 hit coordinates"})
        if cid == "aime-2003-1-7":
            for expression, perimeter in zip(exprs, refs):
                x = math.sqrt(((perimeter-30)/2)**2 - 15**2)
                geometry_checks.append({"case_id": cid, "value_expression": expression,
                                        "quantity": "positive x from perimeter = 30+2*sqrt(225+x*x)",
                                        "value": x, "boundary_margin": min(x, 60-x),
                                        "basis": "direct substitution into DSL; saved local box [0,60]"})

    emit_csv("local-value-counts.csv", local_rows)
    emit_csv("per-problem.csv", case_rows)
    emit_csv("full-solver-runs.csv", full_rows)
    emit_csv("full-value-coverage.csv", coverage)
    emit_csv("geometry-proxy.csv", proxy_rows)
    emit_json("geometry-model.json", {"method": "normalized-box nearest representative; mean-nearest saved hit per value",
                                       "not_a_basin_measure": True, "models": models})
    emit_csv("geometry-checks.csv", geometry_checks)
    summary = {
        "stage": 1, "solver_invocations": 0, "network_requests": 0,
        "development_cases": 323, "new2026_cases": 20,
        "development_multivalue_cases": len(selected), "new2026_multivalue_cases": 0,
        "distinct_case_value_pairs": len(coverage), "local_records_selected": sum(r["total_n"] for r in case_rows),
        "main_campaign_rows": len(attr), "main_campaign_correct": 953,
        "selected_full_runs": len(full_rows), "selected_full_equal": sum(r["set_relation"] == "equal" for r in full_rows),
        "selected_full_partial_missing": sum(r["per_value_inference"] == "unknown_which_value_missing" for r in full_rows),
        "selected_full_no_answer": sum(r["status"] == "no_answer_found" for r in full_rows),
        "geometry_proxy_cases": len(models), "geometry_proxy_value_flags": sum(r["proxy_rare_g_le_0_20"] for r in proxy_rows),
        "geometry_proxy_retrospective_flag_matches": sum(r["proxy_rare_g_le_0_20"] == r["seed1_rare_q_le_0_20"] for r in proxy_rows),
        "geometry_proxy_max_abs_error": max(r["abs_difference"] for r in proxy_rows),
        "scope_notes": scope_notes,
        "limits": [
            "Saved main-campaign tables do not contain returned values; coverage bounds are not observed per-value frequencies.",
            "All seed0/seed1 outcomes were viewed before prediction registration; neither is a prospective holdout.",
            "Some archives stopped before 200 starts due to wall budget; Wilson intervals are descriptive iid approximations.",
            "Local hit classification is numerical, not proof of existence or completeness.",
            "No new solver run or altered target was made; no sealed/unseen solver output was read.",
        ],
    }
    emit_json("summary.json", summary)
    emit_json("source-manifest.json", {"schema_version": 1, "sources": [sources[k] for k in sorted(sources)]})
    for name, blob in products.items():
        assert len(blob) <= LIMIT, (name, len(blob))
        path = OUT / name
        if args.check:
            assert path.read_bytes() == blob, f"reproduction mismatch: {name}"
        else:
            path.write_bytes(blob)
    print(json.dumps({"mode": "check" if args.check else "aggregate", "outputs": len(products),
                      "inputs": len(sources), "selected_cases": len(selected),
                      "local_records": summary["local_records_selected"],
                      "full_equal": summary["selected_full_equal"], "full_runs": len(full_rows),
                      "solver_invocations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
