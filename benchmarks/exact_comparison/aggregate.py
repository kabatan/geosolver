"""Aggregate exact runs and a GeoSolver research campaign into tables.

usage: aggregate.py --msolve DIR --elim DIR --geo-runs per-run.csv --out DIR
                    [--paths per-problem-paths-cost.csv] [--audit classification.csv] [--lift DIR]

--geo-runs is the per-run table of a GeoSolver campaign (case_id, seed, matched, wall_seconds).
--paths supplies e2h_rating (human difficulty) per case.
Writes cases.csv (one row per case), summary.json and summary.md.
"""

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from summarize import classify, load_dir  # noqa: E402

CASES = HERE.parent / "cases.jsonl"


def position(cid):
    m = re.search(r"(\d+)$", cid)
    if not m:
        return None, None
    n, u = int(m.group(1)), cid.upper()
    if u.startswith("AIME"):
        return "AIME", n / 15
    if "GEO" in u:
        return "HMMT", n / 10
    if u.startswith("JMO"):
        return "JMO", n / 12
    return None, None


def tercile(p):
    if p is None:
        return "unknown"
    return "early" if p <= 1 / 3 else ("middle" if p <= 2 / 3 else "late")


def geo_runs_table(path):
    runs = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            runs[r["case_id"]].append({"seed": int(r["seed"]), "matched": r["matched"] == "True",
                                       "seconds": float(r["wall_seconds"]), "status": r["status"]})
    return runs


def load_csv(path, key="id"):
    if not path:
        return {}
    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    k = key if rows and key in rows[0] else next(iter(rows[0]))
    return {r[k]: r for r in rows}


def med(xs):
    return statistics.median(xs) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--msolve", required=True)
    ap.add_argument("--elim")
    ap.add_argument("--geo-runs", required=True)
    ap.add_argument("--paths")
    ap.add_argument("--out", required=True)
    ap.add_argument("--audit")
    ap.add_argument("--lift")
    a = ap.parse_args()
    ms, el = load_dir(a.msolve), load_dir(a.elim)
    lift = load_dir(a.lift) if a.lift else {}
    audit, diff = load_csv(a.audit), load_csv(a.paths, key="case_id")
    geo = geo_runs_table(a.geo_runs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for line in CASES.open():
        case = json.loads(line)
        cid = case["id"]
        m, e = ms.get(cid), el.get(cid)
        src, p = position(cid)
        runs = geo[cid]
        matched = [r["matched"] for r in runs]
        au = audit.get(cid, {})
        row = {
            "id": cid, "source": src, "position": tercile(p),
            "audit_A": au.get("A", ""), "audit_weight": au.get("weight", ""),
            "e2h_rating": diff.get(cid, {}).get("e2h_rating", ""),
            "dsl_vars": len(case["dsl"]["variables"]),
            "msolve_class": classify(m),
            "poly_vars": (m or {}).get("nvars"), "poly_eqs": (m or {}).get("neqs"),
            "max_degree": max((m or {}).get("degrees") or [0]) if m and m.get("degrees") else None,
            "bezout": (m or {}).get("bezout"),
            "translate_s": (m or {}).get("translate_seconds"),
            "msolve_s": (m or {}).get("solve_seconds"),
            "filter_s": (m or {}).get("filter_seconds"),
            "real_solutions": (m or {}).get("real_solutions"),
            "verified_configurations": (m or {}).get("verified_configurations"),
            "elim_status": (e or {}).get("solve_status") or (e or {}).get("reason"),
            "elim_s": (e or {}).get("solve_seconds"),
            "elim_candidates": len((e or {}).get("candidate_values") or []),
            "elim_reference_in": (e or {}).get("reference_among_candidates"),
            "geo_runs": len(runs), "geo_matched": sum(matched),
            "geo_median_s": med([r["seconds"] for r in runs]),
            "geo_median_s_matched": med([r["seconds"] for r, ok in zip(runs, matched) if ok]),
            "lift": (lift.get(cid) or {}).get("status", ""),
            "unsupported_reason": (m or {}).get("reason", ""),
        }
        rows.append(row)
    with open(out / "cases.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def block(sel):
        c = Counter(r["msolve_class"] for r in sel)
        ok = [r for r in sel if r["msolve_class"] == "answer_set_matches"]
        nonfinite = [r for r in sel if r["msolve_class"] in ("positive_dimensional", "free_parameter")]
        hard = [r for r in sel if r["msolve_class"] in ("timeout", "error")]
        g_any = lambda rs: sum(r["geo_matched"] > 0 for r in rs)  # noqa: E731
        g_all = lambda rs: sum(r["geo_runs"] > 0 and r["geo_matched"] == r["geo_runs"] for r in rs)  # noqa: E731
        return {
            "n": len(sel), "msolve_classes": dict(c),
            "msolve_matched_median_s": med([r["msolve_s"] for r in ok]),
            "msolve_matched_median_total_s": med([r["translate_s"] + r["msolve_s"] + r["filter_s"] for r in ok]),
            "geo_any_seed": g_any(sel), "geo_all_seeds": g_all(sel),
            "geo_median_s_matched": med([r["geo_median_s_matched"] for r in sel if r["geo_median_s_matched"]]),
            "nonfinite_n": len(nonfinite), "nonfinite_geo_any": g_any(nonfinite),
            "nonfinite_elim_reference_in": sum(bool(r["elim_reference_in"]) for r in nonfinite),
            "msolve_fail_n": len(hard), "msolve_fail_geo_any": g_any(hard), "msolve_fail_geo_all": g_all(hard),
            "median_dsl_vars": med([r["dsl_vars"] for r in sel]),
            "median_poly_vars": med([r["poly_vars"] for r in sel if r["poly_vars"]]),
            "spurious_roots_median": med([r["real_solutions"] - r["verified_configurations"] for r in ok]),
            "spurious_ratio_median": med([r["verified_configurations"] / r["real_solutions"]
                                          for r in ok if r["real_solutions"]]),
        }

    summary = {"all": block(rows)}
    groups = defaultdict(list)
    for r in rows:
        groups["audit:" + (r["audit_A"] + r["audit_weight"] if r["audit_A"] == "E2" else r["audit_A"] or "?")].append(r)
        groups["position:" + r["position"]].append(r)
        groups["source:" + str(r["source"])].append(r)
        groups[f"source_position:{r['source']}:{r['position']}"].append(r)
        groups["msolve_class:" + r["msolve_class"]].append(r)
    for k in sorted(groups):
        summary[k] = block(groups[k])
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    lines = ["| group | n | msolve一致 | 有限でない | 時間切れ/メモリ | 未対応 | geo≥1seed | geo全seed | msolve中央値s | geo中央値s |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for k, b in summary.items():
        c = b["msolve_classes"]
        lines.append(
            f"| {k} | {b['n']} | {c.get('answer_set_matches', 0)} | "
            f"{c.get('positive_dimensional', 0) + c.get('free_parameter', 0)} | "
            f"{c.get('timeout', 0) + c.get('error', 0)} | {c.get('unsupported', 0)} | "
            f"{b['geo_any_seed']} | {b['geo_all_seeds']} | {b['msolve_matched_median_s']} | {b['geo_median_s_matched']} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
