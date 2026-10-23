"""Problem-level statistics for the predeclared astra-B experiments."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.special import expit
from scipy.stats import binomtest, rankdata, spearmanr

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def read_csv(path, key):
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == len({r[key] for r in rows}), str(path)
    return {r[key]: r for r in rows}


def partial(x, y, controls=()):
    x, y = rankdata(x), rankdata(y)
    mat = np.column_stack([np.ones(len(x))] + [rankdata(v) for v in controls])
    x = x - mat @ np.linalg.lstsq(mat, x, rcond=None)[0]
    y = y - mat @ np.linalg.lstsq(mat, y, rcond=None)[0]
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def correlation(x, y, controls=(), reps=2000):
    x, y = np.asarray(x), np.asarray(y)
    controls = [np.asarray(c) for c in controls]
    rng = np.random.default_rng(102314)
    b = []
    for _ in range(reps):
        ix = rng.integers(0, len(x), len(x))
        b.append(partial(x[ix], y[ix], [c[ix] for c in controls]))
    return {"n": len(x), "rho": partial(x, y, controls),
            "ci95": np.nanquantile(b, [0.025, 0.975]).tolist()}


def cv_compare(rows, human=False):
    n = len(rows)
    dims = np.array([min(r["n"], 5) for r in rows])
    dummies = [dims == k for k in range(2, 6)]
    basic = dummies + [np.log([r["dsl_len"] for r in rows])]
    if human:
        hrank = np.empty(n)
        for contest in ("AIME", "HMMT"):
            ids = [i for i, r in enumerate(rows) if r["contest"] == contest]
            hrank[ids] = rankdata([rows[i]["human"] for i in ids]) / len(ids)
        basic += [hrank, np.array([r["contest"] == "HMMT" for r in rows])]
    X0 = np.column_stack(basic)
    X1 = np.column_stack(basic + [[r["Q"] for r in rows]])
    y = np.array([r["logit_p"] for r in rows])
    p = np.array([r["p"] for r in rows])
    errors = np.zeros((2, n))
    xent = np.zeros((2, n))
    repeats = 20
    rng = np.random.default_rng(102315)
    repeat_mse = []
    for _ in range(repeats):
        perm = rng.permutation(n)
        assignment = np.empty(n, dtype=int)
        assignment[perm] = np.arange(n) % 5
        thiserr = np.zeros((2, n))
        for fold in range(5):
            train, test = assignment != fold, assignment == fold
            for k, X in enumerate((X0, X1)):
                mu, sd = X[train].mean(axis=0), X[train].std(axis=0)
                sd[sd < 1e-12] = 1
                a = np.column_stack([np.ones(train.sum()), (X[train]-mu)/sd])
                b = np.column_stack([np.ones(test.sum()), (X[test]-mu)/sd])
                penalty = np.eye(a.shape[1])
                penalty[0, 0] = 0
                coef = np.linalg.solve(a.T@a+penalty, a.T@y[train])
                pred = b@coef
                thiserr[k, test] = (pred-y[test])**2
                pp = np.clip(expit(pred), 1e-9, 1-1e-9)
                xent[k, test] += -(p[test]*np.log(pp)+(1-p[test])*np.log(1-pp)) / repeats
        errors += thiserr / repeats
        repeat_mse.append(thiserr.mean(axis=1).tolist())
    rng = np.random.default_rng(102316)
    differences = []
    for _ in range(2000):
        ix = rng.integers(0, n, n)
        differences.append(float(np.mean(errors[0, ix]-errors[1, ix])))
    return {"n": n, "folds": 5, "repeats": repeats, "ridge_lambda": 1,
            "mse_baseline": float(errors[0].mean()), "mse_add_Q": float(errors[1].mean()),
            "mse_improvement": float((errors[0]-errors[1]).mean()),
            "improvement_ci95_conditional_on_fits": np.quantile(differences, [0.025, 0.975]).tolist(),
            "cross_entropy_baseline": float(xent[0].mean()), "cross_entropy_add_Q": float(xent[1].mean()),
            "repeat_mse": repeat_mse}


def feature_stats():
    feats = read_csv(OUT / "features.csv", "id")
    humans = read_csv(ROOT / "jssa/difficulty/ghost-1023/human_feat.csv", "case_id")
    factors = read_csv(ROOT / "jssa/difficulty/dissociation/factors.csv", "case_id")
    rows = []
    for cid, f in feats.items():
        if f["status"] != "ok" or not f["Q"] or int(f["n_valid"]) < 8:
            continue
        h = humans[cid]
        raw = json.loads((ROOT / f"jssa/difficulty/minima/raw-323/{cid}.json").read_text())
        total = len(raw["records"])
        hits = sum(r["cls"] == "hit" for r in raw["records"])
        ps = (hits + 0.5) / (total + 1)
        row = {"id": cid, "n": int(f["n"]), "m": int(f["m"]),
               "Q": float(f["Q"]), "good_step_fraction": float(f["good_step_fraction"]),
               "step_box_norm": float(f["step_box_norm"]), "linear_remaining": float(f["linear_remaining"]),
               "n_valid": int(f["n_valid"]), "n_starts": total, "hits": hits, "p": hits/total,
               "logit_p": float(np.log(ps/(1-ps))), "dsl_len": int(h["dsl_len"]),
               "human": float(h["human"]) if h["human"] else None, "contest": h["contest"],
               "C": float(h["C"]), "p_seed1": float(factors[cid]["p"]) if cid in factors else None}
        rows.append(row)
    with (OUT / "analysis-cases.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    get = lambda rows, k: np.array([r[k] for r in rows], dtype=float)
    controls = [get(rows, "n"), get(rows, "dsl_len")]
    summary = {"feature_status_counts": dict(Counter(f["status"] for f in feats.values())),
               "primary_n": len(rows), "excluded_under_8_valid": [cid for cid, f in feats.items() if f["status"] == "ok" and int(f["n_valid"]) < 8],
               "Q_vs_p": correlation(get(rows, "Q"), get(rows, "p")),
               "Q_vs_p_partial_n_len": correlation(get(rows, "Q"), get(rows, "p"), controls),
               "good_step_vs_p_partial_n_len": correlation(get(rows, "good_step_fraction"), get(rows, "p"), controls),
               "step_size_vs_p_partial_n_len": correlation(get(rows, "step_box_norm"), get(rows, "p"), controls),
               "linear_remaining_vs_p_partial_n_len": correlation(get(rows, "linear_remaining"), get(rows, "p"), controls),
               "Q_vs_C_partial_n_len": correlation(get(rows, "Q"), get(rows, "C"), controls),
               "cv_all": cv_compare(rows)}
    with_seed1 = [r for r in rows if r["p_seed1"] is not None]
    summary["Q_vs_p_seed1_partial_n_len"] = correlation(get(with_seed1, "Q"), get(with_seed1, "p_seed1"), [get(with_seed1, "n"), get(with_seed1, "dsl_len")])
    hr = [r for r in rows if r["human"] is not None]
    for contest in ("AIME", "HMMT"):
        rr = [r for r in hr if r["contest"] == contest]
        ctrl = [get(rr, "n"), get(rr, "dsl_len")]
        summary[f"human_{contest}"] = {"Q_vs_human_raw": correlation(get(rr, "Q"), get(rr, "human")),
                                      "Q_vs_human_partial": correlation(get(rr, "Q"), get(rr, "human"), ctrl),
                                      "Q_vs_p_partial": correlation(get(rr, "Q"), get(rr, "p"), ctrl),
                                      "human_vs_p": correlation(get(rr, "human"), get(rr, "p"))}
    summary["cv_human_subset"] = cv_compare(hr, human=True)
    summary["bootstrap_note"] = "2000 resamples of problems; CV CI conditions on fitted out-of-fold predictions and is not a fresh benchmark confidence interval."
    (OUT / "feature-stats.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k:v for k,v in summary.items() if not k.startswith('cv')}, indent=2, ensure_ascii=False))
    print("CV", {k:{a:b for a,b in v.items() if a != "repeat_mse"} for k,v in summary.items() if k.startswith("cv")})


def intervention_stats():
    all_results = []
    summary = []
    for path in sorted((OUT / "interventions").glob("*.json")):
        d = json.loads(path.read_text())
        all_results.append(d)
        for cap in ("80", "320"):
            base = np.array([r["base"][cap]["cls"] == "hit" for r in d["rows"]])
            for mode in ("base", "sharpen", "flatten"):
                hit = np.array([r[mode][cap]["cls"] == "hit" for r in d["rows"]])
                gain, loss = int((hit & ~base).sum()), int((base & ~hit).sum())
                rr = [r[mode][cap] for r in d["rows"]]
                rec = {"id": d["id"], "group": d["group"], "Q": d["Q"], "a": d["a"],
                       "cap": int(cap), "mode": mode, "n": len(hit), "hits": int(hit.sum()), "p": float(hit.mean()),
                       "delta_p": float(hit.mean()-base.mean()), "gain": gain, "loss": loss,
                       "mcnemar_p": binomtest(gain, gain+loss, 0.5).pvalue if gain+loss else 1.0,
                       "median_evaluations": float(np.median([r["evaluations"] for r in rr])),
                       "capped": sum(r["status"] == 0 for r in rr), "timeout": sum(r["cls"] == "timeout" for r in rr),
                       "left_box": sum(r["cls"] == "left_box" for r in rr),
                       "stuck": sum(r["cls"] == "stuck" for r in rr),
                       "wrong_branch": sum(r["cls"] == "wrong_branch" for r in rr),
                       "max_aug_res_at_hit": max([r["augmented_residual_norm"] for r in rr if r["cls"] == "hit"] or [0])}
                summary.append(rec)
    for cap in (80, 320):
        ids = [i for i,r in enumerate(summary) if r["cap"] == cap and r["mode"] != "base"]
        ids.sort(key=lambda i: summary[i]["mcnemar_p"])
        running = 0.0
        for j,i in enumerate(ids):
            running = max(running, min(1, (len(ids)-j)*summary[i]["mcnemar_p"]))
            summary[i]["holm_p"] = running
    with (OUT / "intervention-summary.csv").open("w") as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0])+["holm_p"])
        w.writeheader()
        w.writerows(summary)
    grouped = []
    for cap in (80, 320):
        for group in ("high_Q", "low_Q"):
            for mode in ("sharpen", "flatten"):
                rr = [r for r in summary if r["cap"] == cap and r["group"] == group and r["mode"] == mode]
                grouped.append({"cap": cap, "group": group, "mode": mode,
                                "n_problems": len(rr), "median_delta_p": float(np.median([r["delta_p"] for r in rr])),
                                "mean_delta_p": float(np.mean([r["delta_p"] for r in rr])),
                                "number_improved": sum(r["delta_p"] > 0 for r in rr),
                                "number_worsened": sum(r["delta_p"] < 0 for r in rr)})
    (OUT / "intervention-group-stats.json").write_text(json.dumps(grouped, indent=2) + "\n")
    print("INTERVENTIONS", json.dumps(summary, ensure_ascii=False, indent=2))
    print("GROUPS", json.dumps(grouped, indent=2))


if __name__ == "__main__":
    feature_stats()
    if (OUT / "interventions").exists() and len(list((OUT / "interventions").glob("*.json"))) == 12:
        intervention_stats()
