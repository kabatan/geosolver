"""Preregistered problem-unit summaries. All development analyses are exploratory."""
from collections import Counter
import argparse
import csv
import json
import math
import numpy as np
from scipy.stats import rankdata
from experiment import HERE, ROOT, clean, now, sha, verify_freeze, write_csv, write_json


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    x, y = x - x.mean(), y - y.mean()
    d = float(np.linalg.norm(x) * np.linalg.norm(y))
    return float(x @ y / d) if d else None


def rho(x, y):
    return corr(rankdata(x), rankdata(y)) if len(x) >= 3 else None


def ci(values):
    values = np.asarray([v for v in values if v is not None and math.isfinite(v)])
    return np.quantile(values, [.025, .975]).tolist() if len(values) else [None, None]


def bootstrap_rho(x, y):
    x, y = np.asarray(x), np.asarray(y)
    if len(x) < 3 or rho(x, y) is None:
        return [None, None], 0
    rng = np.random.default_rng(17200)
    values = []
    for _ in range(20):
        ix = rng.integers(len(x), size=(500, len(x)))
        a, b = rankdata(x[ix], axis=1), rankdata(y[ix], axis=1)
        a -= a.mean(axis=1, keepdims=True)
        b -= b.mean(axis=1, keepdims=True)
        den = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
        valid = den > 0
        values.extend((np.sum(a[valid] * b[valid], axis=1) / den[valid]).tolist())
    return ci(values), len(values)


def bootstrap_mean(x):
    x = np.asarray(x, float)
    if not len(x):
        return [None, None]
    rng = np.random.default_rng(17200)
    vals = []
    for _ in range(20):
        vals.extend(x[rng.integers(len(x), size=(500, len(x)))].mean(axis=1))
    return ci(vals)


def difference_ci(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if not len(a) or not len(b):
        return [None, None]
    rng = np.random.default_rng(17200)
    values = []
    for _ in range(20):
        aa = a[rng.integers(len(a), size=(500, len(a)))].mean(axis=1)
        bb = b[rng.integers(len(b), size=(500, len(b)))].mean(axis=1)
        values.extend(aa - bb)
    return ci(values)


def auc(scores, labels):
    scores, labels = np.asarray(scores), np.asarray(labels, dtype=bool)
    n1, n0 = int(labels.sum()), int((~labels).sum())
    return float((rankdata(scores)[labels].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else None


def metric(rows, key):
    rr = [r for r in rows if r.get("W") is not None and r.get(key) is not None]
    x, y = [r["W"] for r in rr], [r[key] for r in rr]
    point = rho(x, y)
    bounds, valid = bootstrap_rho(x, y)
    partial = None
    if len(rr) >= 5:
        C = np.column_stack((np.ones(len(rr)), rankdata([r["n_vars"] for r in rr]),
                             rankdata([r["phi_diag"] for r in rr])))
        xr, yr = rankdata(x), rankdata(y)
        xr -= C @ np.linalg.lstsq(C, xr, rcond=None)[0]
        yr -= C @ np.linalg.lstsq(C, yr, rcond=None)[0]
        partial = corr(xr, yr)
    labels = [v > 0 for v in y] if key.startswith("R") else [v >= .10 for v in y]
    return {"n": len(rr), "rho": point, "rho_ci95": bounds, "bootstrap_valid": valid,
            "partial_rho_nvars_phi": partial, "auc": auc(x, labels), "positives": sum(labels),
            "continuous_criterion": bool(point is not None and point >= .30
                                         and bounds[0] is not None and bounds[0] > 0)}


def group_summary(rows, key):
    out = {}
    for group in ["low", "middle", "high", "undetermined"]:
        y = [r[key] for r in rows if r["group"] == group and r.get(key) is not None]
        out[group] = {"n": len(y), "mean": float(np.mean(y)) if y else None,
                      "median": float(np.median(y)) if y else None}
    high = [r[key] for r in rows if r["group"] == "high" and r.get(key) is not None]
    low = [r[key] for r in rows if r["group"] == "low" and r.get(key) is not None]
    out["high_minus_low"] = {"mean": float(np.mean(high) - np.mean(low)) if high and low else None,
                             "ci95": difference_ci(high, low)}
    enough = len(high) >= 8 and len(low) >= 8
    if key == "R_saved":
        passed = enough and np.median(high) >= .10 and np.median(low) <= 0
    elif key == "D_F":
        lower = out["high_minus_low"]["ci95"][0]
        passed = (enough and np.median(high) >= .15 and np.median(low) <= .05
                  and lower is not None and lower > 0)
    else:
        passed = None
    out["enough_high_low"] = enough
    out["criterion"] = bool(passed) if passed is not None else None
    return out


def diagnostic_row(cid):
    d = json.loads((HERE / "diagnostics" / f"{cid}.json").read_text())
    return {k: d[k] for k in ("id", "n_vars", "n_eq", "method", "W", "W_raw", "group", "denominator", "crossings")} | {
        "phi_diag": d["n_F"] / d["points"], "diagnostic_seconds": d["seconds"],
        "diagnostic_residual_calls": d["residual_calls"]}


def main(diagnostics_only=False):
    manifest = verify_freeze()
    g_rows = {r["id"]: r for r in csv.DictReader((ROOT / "jssa/strategy/astra-consult-17/G/census.csv").open())}
    rows, starts, disagreements = [], [], []
    timings, classes, transitions, census_errors = Counter(), Counter(), Counter(), []
    for m in manifest:
        cid = m["id"]
        r = diagnostic_row(cid)
        gr = g_rows[cid]
        if diagnostics_only:
            nF, nI, hF, hI = [int(gr[k]) for k in ("n_F", "n_I", "hit_F", "hit_I")]
        else:
            d = json.loads((HERE / "paired" / f"{cid}.json").read_text())
            nF, nI, hF, hI = [d[k] for k in ("saved_n_F", "saved_n_I", "saved_hit_F", "saved_hit_I")]
            if [nF, nI, hF, hI] != [int(gr[k]) for k in ("n_F", "n_I", "hit_F", "hit_I")]:
                census_errors.append(cid)
            r["start_hard_errors"] = d["start_hard_errors"]
            records = d["records"]
            for label, F in [("F", True), ("I", False), ("all", None)]:
                sel = [s for s in records if F is None or s["F"] == F]
                r[f"n_{label}"] = len(sel)
                for arm in ["B", "N"]:
                    h = sum(s[arm]["cls"] == "hit" for s in sel)
                    r[f"hit_{arm}_{label}"] = h
                    r[f"p_{arm}_{label}"] = h / len(sel) if sel else None
                r[f"D_{label}_raw"] = (r[f"p_N_{label}"] - r[f"p_B_{label}"]) if sel else None
                r[f"D_{label}"] = r[f"D_{label}_raw"] if len(sel) >= 10 else None
            r["R_paired"] = r["p_B_I"] - r["p_B_F"] if r["n_F"] >= 10 and r["n_I"] >= 10 else None
            r["selected_arm"] = "N" if r["group"] == "high" else "B"
            r["policy_p"] = r[f"p_{r['selected_arm']}_all"]
            for s in records:
                flat = {"id": cid, "k": s["k"], "F": s["F"], "saved_cls": s["saved_cls"]}
                for arm in ["B", "N"]:
                    z = s[arm]
                    flat.update({f"{arm}_{k}": z.get(k) for k in ["cls", "seconds", "evaluations", "no_hard_calls"]})
                    flat[f"{arm}_status"] = z["optimizer"].get("status")
                    timings[arm] += z["seconds"]
                    classes[(r["method"], arm, "F" if s["F"] else "I", z["cls"])] += 1
                transitions[("F" if s["F"] else "I", s["B"]["cls"], s["N"]["cls"])] += 1
                same_cls = s["B"]["cls"] == s["saved_cls"]
                flat["B_saved_cls_same"] = same_cls
                if not same_cls:
                    disagreements.append(flat)
                starts.append(flat)
        r.update(saved_n_F=nF, saved_n_I=nI, saved_hit_F=hF, saved_hit_I=hI,
                 R_saved=hI/nI - hF/nF if nF >= 10 and nI >= 10 else None,
                 phi_saved=nF/(nF+nI))
        rows.append(r)

    summary = {"generated_utc": now(), "exploratory": True, "diagnostics_only": diagnostics_only,
               "freeze_sha256": sha(HERE / "freeze.json"), "analysis_code_sha256": sha(__file__),
               "coverage": {}, "associations": {}, "groups": {}}
    keys = ["R_saved"] if diagnostics_only else ["R_saved", "R_paired", "D_F", "D_I", "D_all"]
    for population in ["LM", "Powell", "all"]:
        rr = [r for r in rows if population == "all" or r["method"] == population]
        summary["coverage"][population] = dict(Counter(r["group"] for r in rr)) | {"total": len(rr)}
        summary["associations"][population] = {key: metric(rr, key) for key in keys}
        summary["groups"][population] = {key: group_summary(rr, key) for key in keys}
    seconds = [r["diagnostic_seconds"] for r in rows]
    summary["diagnostic_cost"] = {"sum_seconds": sum(seconds), "median_seconds": float(np.median(seconds)),
        "p95_seconds": float(np.quantile(seconds, .95)), "maximum_seconds": max(seconds),
        "residual_calls": sum(r["diagnostic_residual_calls"] for r in rows)}
    if not diagnostics_only:
        summary.update(local_seconds=dict(timings), paired_starts=len(starts),
                       baseline_class_disagreements=len(disagreements), census_disagreements=census_errors,
                       no_hard_calls=sum(s["N_no_hard_calls"] for s in starts),
                       B_no_hard_calls=sum(s["B_no_hard_calls"] for s in starts))
        summary["policy"] = {}
        for population in ["LM", "all"]:
            rr = [r for r in rows if population == "all" or r["method"] == population]
            p = {key: float(np.mean([r[key] for r in rr])) for key in ["p_B_all", "p_N_all", "policy_p"]}
            for arm in ["B", "N"]:
                diffs = [r["policy_p"] - r[f"p_{arm}_all"] for r in rr]
                p[f"policy_minus_{arm}"] = {"mean": float(np.mean(diffs)), "ci95": bootstrap_mean(diffs)}
            summary["policy"][population] = p
        write_csv(HERE / "per-start.csv", starts)
        write_csv(HERE / "baseline-disagreements.csv", disagreements)
        write_csv(HERE / "outcome-counts.csv", [dict(method=k[0], arm=k[1], start_group=k[2], cls=k[3], count=v)
                                               for k, v in sorted(classes.items())])
        write_csv(HERE / "transitions.csv", [dict(start_group=k[0], B=k[1], N=k[2], count=v)
                                            for k, v in sorted(transitions.items())])
    suffix = "-interim" if diagnostics_only else ""
    write_csv(HERE / f"per-problem{suffix}.csv", rows)
    write_json(HERE / f"summary{suffix}.json", summary)
    print(json.dumps(clean(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagnostics-only", action="store_true")
    main(ap.parse_args().diagnostics_only)
