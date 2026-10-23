"""Reproducible exploratory summaries; never launches local optimization."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import rankdata, spearmanr

from common import HERE, ROOT, RAW, clean, write_json


def auc(y, score):
    y = np.asarray(y, bool); score = np.asarray(score, float)
    if not y.any() or y.all():
        return None
    return float((rankdata(score)[y].sum() - y.sum()*(y.sum()+1)/2) / (y.sum()*(~y).sum()))


def rho(x, y):
    good = [(a, b) for a, b in zip(x, y) if a is not None and b is not None and np.isfinite(a+b)]
    if len(good) < 3:
        return None
    a, b = np.array(good).T
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    return {"n": len(a), "rho": float(spearmanr(a, b).statistic)}


def model_fit_predict(X, y, test):
    # Fixed L2=1, sum log loss. Fold-local imputation and standardization.
    med = np.nanmedian(X, axis=0)
    med = np.nan_to_num(med)
    X = np.where(np.isfinite(X), X, med)
    test = np.where(np.isfinite(test), test, med)
    mu, scale = X.mean(0), X.std(0)
    scale[scale < 1e-12] = 1
    A = np.column_stack([np.ones(len(X)), (X-mu)/scale])
    B = np.column_stack([np.ones(len(test)), (test-mu)/scale])
    def objective(beta):
        z = A @ beta
        val = np.sum(np.logaddexp(0, z) - y*z) + 0.5*np.sum(beta[1:]**2)
        grad = A.T @ (expit(z)-y)
        grad[1:] += beta[1:]
        return val, grad
    fit = minimize(objective, np.zeros(A.shape[1]), jac=True, method="BFGS", options={"gtol": 1e-7})
    return expit(B @ fit.x), {"median": med.tolist(), "mean": mu.tolist(), "scale": scale.tolist(),
                              "coefficients": fit.x.tolist(), "l2": 1.0,
                              "gradient_norm": float(np.linalg.norm(fit.jac))}


def main():
    rows = json.loads((HERE / "census.json").read_text())
    byid = {r["id"]: r for r in rows}
    ds = [json.loads(s) for s in (HERE / "endpoint-diagnostics.jsonl").read_text().splitlines()]
    trials = json.loads((HERE / "intervention.json").read_text())
    orig = list(csv.DictReader((ROOT / "jssa/difficulty/start-feasibility-1023/per-problem.csv").open()))
    mismatch = [(r["id"], old) for r in orig for old, new in
                [("n_feas", "n_F"), ("n_infeas", "n_I"), ("hit_feas", "hit_F"), ("hit_infeas", "hit_I")]
                if int(r[old]) != byid[r["id"]][new]]
    assert not mismatch
    eligible = [r for r in rows if r["n_F"] >= 10 and r["n_I"] >= 10]
    def totals(group):
        keys = ["n_F", "n_I", "hit_F", "hit_I", "F_failed_finite", "F_failed_endF", "wall_count",
                "fail_b8", "fail_b6", "fail_b4", "fail_toward6", "fail_toward4", "fail_toward2",
                "hit_b8", "hit_b6", "hit_b4", "hit_tested", "F_stuck", "F_left_box", "F_wrong_answer"]
        return {k: sum(r.get(k, 0) for r in group) for k in keys}
    summary = {"census_problems": len(rows), "source_match": not mismatch, "totals": totals(rows),
               "eligible": len(eligible), "negative": sum(r["gap"] < 0 for r in eligible),
               "strong_negative": sum(r["gap"] < -0.2 for r in eligible),
               "method_counts": dict(Counter(r["method"] for r in rows)),
               "boundary_by_method": {m: totals([r for r in rows if r["method"] == m]) for m in ["LM", "Powell"]}}
    groups = {"strong_negative": [r for r in eligible if r["gap"] < -0.2],
              "mild_negative": [r for r in eligible if -0.2 <= r["gap"] < 0],
              "nonnegative": [r for r in eligible if r["gap"] >= 0]}
    summary["W_by_gap"] = {k: {"n": len(g), "W_median": float(np.median([r["W"] for r in g])),
                                     "W_ge_02": sum(r["W"] >= .2 for r in g), **totals(g)} for k, g in groups.items()}
    summary["feature_associations"] = {}
    features = ["W", "Q", "phi_probe", "n_vars", "n_eq", "n_guards", "n_strict", "n_not_equal",
                "angle_guard", "area_guard", "product_guard", "predicate_guard", "checks_line_distinct",
                "checks_triangle_nondegenerate", "checks_intersection_exclude_distinct",
                "checks_intersection_selection_trace", "hit_min_margin_median"]
    for feature in features:
        g = [r for r in eligible if r.get(feature) is not None]
        summary["feature_associations"][feature] = {
            "n": len(g), "rho_with_I_minus_F": rho([r[feature] for r in g], [-r["gap"] for r in g]),
            "auc_negative": auc([r["gap"] < 0 for r in g], [r[feature] for r in g]),
            "auc_strong_negative": auc([r["gap"] < -.2 for r in g], [r[feature] for r in g])}
    # This is retrospective problem-level cross-validation, not a prospectively held-out task set.
    model_features = [k for k in features if k not in ["W", "Q", "phi_probe", "hit_min_margin_median"]]
    geom_features = model_features + ["phi_probe", "Q"]
    y = np.array([r["gap"] < 0 for r in eligible], float)
    out_rows = [{"id": r["id"], "negative_seed0": int(y[i]), "gap_seed0": r["gap"]} for i, r in enumerate(eligible)]
    model_results, models = {}, {}
    for name, feats in [("static", model_features), ("static_plus_Q_phi", geom_features)]:
        X = np.array([[np.nan if r.get(k) is None else r[k] for k in feats] for r in eligible], float)
        pred = []
        for i in range(len(X)):
            mask = np.arange(len(X)) != i
            p, _ = model_fit_predict(X[mask], y[mask], X[i:i+1])
            pred.append(float(p[0]))
            out_rows[i][name] = float(p[0])
        _, model = model_fit_predict(X, y, X[:1])
        model["features"] = feats
        models[name] = model
        model_results[name] = {"loo_auc": auc(y, pred), "brier": float(np.mean((y-np.array(pred))**2)),
                               "predicted_negative": sum(p >= .5 for p in pred),
                               "true_positive": sum(y[i] and p >= .5 for i, p in enumerate(pred)),
                               "false_positive": sum(not y[i] and p >= .5 for i, p in enumerate(pred))}
    summary["exploratory_LOO"] = model_results
    summary["constant_prevalence_brier"] = float(np.mean((y-y.mean())**2))
    write_json(HERE / "input-models.json", models)
    with (HERE / "input-predictions.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0])); w.writeheader(); w.writerows(out_rows)

    per_trial = []
    per_problem = []
    for case in trials:
        recs = case["records"]
        assert len(recs) == 80 and sum(r["F"] for r in recs) == 40
        a = {"id": case["id"], "W": case["W"], "wall_group": case["wall_group"], "selection": case["selection"]}
        for F, label in [(True, "F"), (False, "I")]:
            rs = [r for r in recs if r["F"] == F]
            for arm in ["baseline", "no_hard"]:
                c = Counter(r[arm]["cls"] for r in rs)
                a[f"{label}_{arm}_hit"] = c["hit"]
                a[f"{label}_{arm}_classes"] = dict(c)
                a[f"{label}_{arm}_seconds"] = sum(r[arm]["seconds"] for r in rs)
                a[f"{label}_{arm}_evals"] = sum(r[arm]["evaluations"] for r in rs)
            a[f"delta_{label}"] = (a[f"{label}_no_hard_hit"]-a[f"{label}_baseline_hit"])/len(rs)
            a[f"{label}_rescued"] = sum(r["baseline"]["cls"] != "hit" and r["no_hard"]["cls"] == "hit" for r in rs)
            a[f"{label}_lost"] = sum(r["baseline"]["cls"] == "hit" and r["no_hard"]["cls"] != "hit" for r in rs)
        for r in recs:
            per_trial.append({"id": case["id"], "k": r["k"], "F": r["F"],
                              "baseline": r["baseline"]["cls"], "no_hard": r["no_hard"]["cls"]})
        per_problem.append(a)
    walls = [r for r in per_problem if r["wall_group"]]
    others = [r for r in per_problem if not r["wall_group"]]
    avg = lambda group, key: float(np.mean([r[key] for r in group]))
    mW, mO = avg(walls, "delta_F"), avg(others, "delta_F")
    p1 = next(r["delta_F"] for r in per_problem if r["id"] == "AIME-2010-II-14")
    p2count = sum(r["delta_F"] >= .10 for r in walls)
    p3count = sum(abs(r["delta_F"]) <= .10 for r in others)
    summary["pilot"] = {
        "problems": len(trials), "pairs": len(per_trial), "optimizations": 2*len(per_trial),
        "wall_n": len(walls), "other_n": len(others), "wall_delta_F": mW, "other_delta_F": mO,
        "wall_delta_I": avg(walls, "delta_I"), "other_delta_I": avg(others, "delta_I"),
        "P1": {"value": p1, "pass": p1 >= .5},
        "P2": {"mean": mW, "n_ge_01": p2count, "denominator": len(walls), "pass": mW >= .2 and 3*p2count >= 2*len(walls)},
        "P3": {"n_abs_le_01": p3count, "denominator": len(others), "pass": p3count >= .8*len(others)},
        "P4": {"difference": mW-mO, "pass": mW-mO >= .15},
        "class_totals": {arm: dict(Counter(r[arm]["cls"] for c in trials for r in c["records"])) for arm in ["baseline", "no_hard"]},
        "solver_seconds": sum(r[arm]["seconds"] for c in trials for r in c["records"] for arm in ["baseline", "no_hard"]),
        "redraw_seconds": sum(c["redraw_seconds"] for c in trials)}
    write_json(HERE / "intervention-summary.json", per_problem)
    flat = [{k: v for k, v in r.items() if not isinstance(v, dict)} for r in per_problem]
    with (HERE / "intervention-summary.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0])); w.writeheader(); w.writerows(flat)
    with (HERE / "paired-outcomes.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(per_trial[0])); w.writeheader(); w.writerows(per_trial)
    summary["endpoint_classes"] = {cl: {"count": sum(r["cls"] == cl for r in ds),
                                               "endF": sum(r["cls"] == cl and r["end_feasible"] is True for r in ds),
                                               "b6": sum(r["cls"] == cl and r.get("b6", 0) for r in ds)}
                                     for cl in sorted(set(r["cls"] for r in ds))}
    by_id_details = {}
    for r in ds:
        by_id_details.setdefault(r["id"], []).append(r)
    summary["boundary_examples"] = {}
    for cid in [r["id"] for r in per_problem if r["selection"] == "negative"]:
        rs = [r for r in by_id_details[cid] if r["cls"] != "hit"]
        tags = Counter()
        for r in rs:
            tags.update(r.get("tags", {}))
        summary["boundary_examples"][cid] = {"census": byid[cid], "failure_tags": dict(tags)}
    seed1 = {r["id"]: r for r in csv.DictReader((ROOT / "jssa/difficulty/start-feasibility-1023/per-problem-seed1.csv").open())}
    summary["seed1_strong_negative"] = []
    for r in groups["strong_negative"]:
        s = seed1[r["id"]]
        gap = int(s["hit_feas"])/int(s["n_feas"])-int(s["hit_infeas"])/int(s["n_infeas"])
        summary["seed1_strong_negative"].append({"id": r["id"], "gap0": r["gap"], "gap1": gap})
    write_json(HERE / "summary.json", summary)
    paths = [HERE/"preregistration-pilot.md", ROOT/"benchmarks/cases.jsonl",
             ROOT/"src/geosolver/engine/standard/search/scipy_multistart_backend.py"] + sorted(RAW.glob("*.json"))
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    import scipy
    write_json(HERE / "provenance.json", {"python": sys.version, "executable": sys.executable,
                                          "numpy": np.__version__, "scipy": scipy.__version__, "sha256": manifest})
    print(json.dumps(clean({k: summary[k] for k in ["totals", "W_by_gap", "feature_associations", "exploratory_LOO", "pilot"]}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
