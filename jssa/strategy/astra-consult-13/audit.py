"""Exploratory audit of saved outcomes and independent static phi measurements."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
import numpy as np
import scipy
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import rankdata

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BOOT = 3000


def csv_rows(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def write_csv(name, rows):
    with (OUT / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def corr(x, y):
    x, y = np.asarray(x), np.asarray(y)
    return float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 0 and np.std(y) > 0 else np.nan


def rho(x, y):
    return corr(rankdata(x), rankdata(y))


def partial(x, y, d, categorical=False):
    if categorical:
        z = np.column_stack([np.ones(len(d))] + [(np.minimum(d, 5) == i).astype(float) for i in range(2, 6)])
    else:
        z = np.column_stack([np.ones(len(d)), rankdata(d)])
    xr, yr = rankdata(x), rankdata(y)
    return corr(xr - z @ np.linalg.lstsq(z, xr, rcond=None)[0],
                yr - z @ np.linalg.lstsq(z, yr, rcond=None)[0])


def within_contest(x, y, labels):
    a, b = np.empty(len(x)), np.empty(len(y))
    for group in np.unique(labels):
        ix = labels == group
        a[ix] = rankdata(x[ix]) / (sum(ix) + 1)
        b[ix] = rankdata(y[ix]) / (sum(ix) + 1)
    return corr(a, b)


def interval(fn, arrays, labels=None, seed=13001):
    arrays = [np.asarray(a) for a in arrays]
    rng = np.random.default_rng(seed)
    n = len(arrays[0])
    if labels is not None:
        groups = [np.where(labels == x)[0] for x in np.unique(labels)]
    values = []
    for _ in range(BOOT):
        ix = rng.integers(n, size=n) if labels is None else np.concatenate([rng.choice(g, len(g)) for g in groups])
        values.append(fn(*(a[ix] for a in arrays)))
    valid = np.asarray(values)[np.isfinite(values)]
    return dict(n=n, estimate=float(fn(*arrays)), ci95=np.quantile(valid, [.025, .975]).tolist(),
                bootstrap_valid=len(valid))


def loss(y, p):
    p = np.clip(p, 1e-12, 1-1e-12)
    return -y * np.log(p) - (1-y) * np.log1p(-p)


def fit_predict(x_train, y_train, x_test):
    center = x_train.mean(axis=0)
    scale = x_train.std(axis=0)
    scale[scale < 1e-12] = 1
    a = np.column_stack([np.ones(len(y_train)), (x_train-center)/scale])
    b = np.column_stack([np.ones(len(x_test)), (x_test-center)/scale])
    penalty = np.ones(a.shape[1]) * .01
    penalty[0] = 0

    def objective(w):
        logits = a @ w
        value = np.mean(np.logaddexp(0, logits) - y_train*logits) + .5*np.sum(penalty*w*w)
        gradient = a.T @ (expit(logits)-y_train)/len(y_train) + penalty*w
        return value, gradient

    fit = minimize(objective, np.zeros(a.shape[1]), jac=True, method="L-BFGS-B",
                   options={"gtol": 1e-9, "ftol": 1e-12, "maxiter": 500})
    if not fit.success:
        raise RuntimeError(fit.message)
    return expit(b @ fit.x)


def cv(rows):
    d = np.asarray([min(r["n_vars"], 5) for r in rows])
    base = np.column_stack([(d == j).astype(float) for j in range(2, 6)])
    old = np.asarray([r["phi0"] for r in rows])
    new = np.asarray([r["phi_independent"] for r in rows])
    nc = np.log1p([r["n_checks"] for r in rows])
    designs = {"d": base, "d+phi0": np.column_stack([base, old]),
               "d+phi_independent": np.column_stack([base, new]),
               "d+checks": np.column_stack([base, nc]),
               "d+checks+phi_independent": np.column_stack([base, nc, new])}
    labels = []
    for r in rows:
        found = re.match(r"([A-Za-z]+)-(\d{4})", r["id"])
        labels.append("-".join(found.groups()).upper() if found else r["id"])
    labels = np.asarray(labels)
    groups = np.unique(labels)
    preds = []
    outputs = {}
    for target in ("p0", "p1"):
        y = np.asarray([r[target] for r in rows])
        outputs[target] = {}
        matrices = {name: np.zeros((10, len(rows))) for name in designs}
        for repeat in range(10):
            rng = np.random.default_rng([13002, repeat])
            shuffled = rng.permutation(groups)
            assignment = {g: i % 5 for i, g in enumerate(shuffled)}
            folds = np.asarray([assignment[g] for g in labels])
            for fold in range(5):
                test = folds == fold
                for name, x in designs.items():
                    matrices[name][repeat, test] = fit_predict(x[~test], y[~test], x[test])
        for name, p in matrices.items():
            losses = loss(y[None, :], p)
            outputs[target][name] = dict(log_loss=float(losses.mean()),
                rmse=float(np.sqrt(np.mean((p-y[None, :])**2))),
                mean_repeat_rho=float(np.mean([rho(y, v) for v in p])),
                log_loss_by_repeat=losses.mean(axis=1).tolist())
            for i, row in enumerate(rows):
                preds.append(dict(id=row["id"], group=labels[i], target=target, model=name,
                                  y=y[i], mean_prediction=float(p[:, i].mean()), mean_log_loss=float(losses[:, i].mean())))
        for full, reference in [("d+phi_independent", "d"), ("d+checks+phi_independent", "d+checks")]:
            delta = (loss(y[None,:], matrices[full])-loss(y[None,:], matrices[reference])).mean(axis=0)
            # Conditional description only: shared training sets are not refit by this bootstrap.
            outputs[target][full]["loss_difference"] = interval(lambda z: np.mean(z), [delta])
    write_csv("cv-predictions.csv", preds)
    return dict(groups=len(groups), grouping="contest-year", repeats=10, folds=5, l2=.01,
                weighting="equal weight per problem", results=outputs)


def main():
    started = time.perf_counter()
    source = ROOT / "jssa/difficulty/start-feasibility-1023/per-problem.csv"
    existing = csv_rows(source)
    human_file = ROOT / "jssa/difficulty/ghost-1023/human_feat.csv"
    humans = {r["case_id"]: r for r in csv_rows(human_file)}
    independent = {r["id"]: r for r in csv_rows(OUT / "phi-independent.csv")}
    rows, hashes, lm_seconds = [], {}, []
    for old in existing:
        cid = old["id"]
        rawpaths = [ROOT / ("jssa/difficulty/minima/" + name) / (cid+".json") for name in ["raw-323", "raw-323-seed1"]]
        raw = []
        for path in rawpaths:
            data = path.read_bytes()
            raw.append(json.loads(data))
            hashes[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
        record = raw[0]["records"]
        assert len(record) == int(old["starts"]) == sum("start" in r for r in record)
        assert sum(r["cls"] == "hit" for r in record) == int(old["hit_feas"])+int(old["hit_infeas"])
        assert abs(raw[0]["p_any"]-float(old["p"])) < 1e-12
        r = {k: int(old[k]) for k in ["n_vars", "starts", "n_feas", "hit_feas", "n_infeas", "hit_infeas", "n_checks"]}
        r = {"id": cid, **r}
        pf = r["hit_feas"]/r["n_feas"] if r["n_feas"] else None
        pi = r["hit_infeas"]/r["n_infeas"] if r["n_infeas"] else None
        phi = r["n_feas"]/r["starts"]
        h = humans[cid]
        r.update(phi0=phi, p0=float(old["p"]), p1=raw[1]["p_any"], n_seed1=len(raw[1]["records"]),
                 phi_independent=float(independent[cid]["phi"]),
                 p_feas=pf, p_infeas=pi,
                 conditional_difference=pf-pi if pf is not None and pi is not None else None,
                 distribution_gain=pf-float(old["p"]) if pf is not None else None,
                 contest=h["contest"], human=float(h["human"]) if h["human"] else None,
                 method="Powell" if r["n_vars"] > raw[0]["n_constraints"] else "LM")
        if r["method"] == "LM":
            lm_seconds.extend(rec["sec"] for rec in record)
        rows.append(r)
    write_csv("joined.csv", rows)
    out = {"scope": "exploratory; no new local solver run", "n_problems": len(rows),
           "n_starts": sum(r["starts"] for r in rows), "n_under_200": sum(r["starts"] < 200 for r in rows),
           "n_Powell": sum(r["method"] == "Powell" for r in rows)}
    out["existing_LM_timing"] = dict(n=len(lm_seconds), mean=float(np.mean(lm_seconds)),
        quantiles_50_90_99_100=np.quantile(lm_seconds, [.5,.9,.99,1]).tolist(),
        n_at_least_10_seconds=sum(t >= 10 for t in lm_seconds))
    out["pooled"] = {k: sum(r[k] for r in rows) for k in ["n_feas", "hit_feas", "n_infeas", "hit_infeas"]}
    out["pooled"]["p_feas"] = out["pooled"]["hit_feas"]/out["pooled"]["n_feas"]
    out["pooled"]["p_infeas"] = out["pooled"]["hit_infeas"]/out["pooled"]["n_infeas"]
    out["correlations"] = {}
    for subset, rr in [("all", rows), ("n200", [r for r in rows if r["starts"] == 200]),
                        ("LM", [r for r in rows if r["method"] == "LM"])]:
        d = np.asarray([r["n_vars"] for r in rr])
        for feature in ("phi0", "phi_independent"):
            x = np.asarray([r[feature] for r in rr])
            for target in ("p0", "p1"):
                y = np.asarray([r[target] for r in rr])
                key = f"{subset}:{feature}:{target}"
                out["correlations"][key] = interval(rho, [x, y])
                out["correlations"][key]["partial_rank_d"] = partial(x, y, d)
                out["correlations"][key]["partial_d_categories"] = partial(x, y, d, categorical=True)
                if subset == "all" and target == "p0":
                    out["correlations"][key]["partial_ci"] = interval(partial, [x,y,d])
    out["phi_measurement_agreement"] = dict(
        rho=rho([r["phi0"] for r in rows], [r["phi_independent"] for r in rows]),
        mean_absolute_difference=float(np.mean([abs(r["phi0"]-r["phi_independent"]) for r in rows])))
    out["human"] = {}
    for contest in ("all", "AIME", "HMMT"):
        rr = [r for r in rows if r["human"] is not None and (contest == "all" or r["contest"] == contest)]
        h = np.asarray([r["human"] for r in rr])
        for key in ("phi0", "phi_independent", "p0"):
            out["human"][contest+":"+key] = interval(rho, [h, [r[key] for r in rr]])
    hr = [r for r in rows if r["human"] is not None]
    hc = np.asarray([r["contest"] for r in hr])
    for key in ("phi0", "phi_independent", "p0"):
        out["human"]["within_contest:"+key] = interval(within_contest,
            [[r["human"] for r in hr], [r[key] for r in hr], hc], labels=hc)
    eligible = [r for r in rows if r["n_feas"] >= 10 and r["n_infeas"] >= 10]
    out["conditional"] = dict(n=len(eligible),
        median_difference=float(np.median([r["conditional_difference"] for r in eligible])),
        mean_difference=interval(lambda x: np.mean(x), [[r["conditional_difference"] for r in eligible]]),
        mean_distribution_gain=interval(lambda x: np.mean(x), [[r["distribution_gain"] for r in eligible]]),
        median_distribution_gain=float(np.median([r["distribution_gain"] for r in eligible])),
        n_difference_over_02=sum(r["conditional_difference"] > .2 for r in eligible),
        n_difference_below_minus02=sum(r["conditional_difference"] < -.2 for r in eligible))
    out["extremes"] = dict(n_phi0_zero=sum(r["phi0"]==0 for r in rows),
        zero_phi_with_hits=[r["id"] for r in rows if r["phi0"] == 0 and r["p0"] > 0],
        n_phi0_one=sum(r["phi0"]==1 for r in rows),
        all_feasible_p_below_03=[r["id"] for r in rows if r["phi0"]==1 and r["p0"] < .3],
        new_phi_still_zero=[r["id"] for r in rows if r["phi_independent"] == 0])
    low = [r for r in rows if r["p0"] < .3]
    out["low_p"] = {"n":len(low), **{k:sum(r[k] for r in low) for k in ["n_feas", "hit_feas", "n_infeas", "hit_infeas"]}}
    out["cv"] = cv(rows)
    out["seconds"] = time.perf_counter()-started
    out["software"] = dict(python=sys.version, executable=sys.executable, numpy=np.__version__, scipy=scipy.__version__)
    for p in [Path(__file__), OUT/"analysis-plan.md", OUT/"phi-independent.csv", source, human_file]:
        hashes[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    for rel in ["src/geosolver/engine/standard/search/scipy_multistart_backend.py",
                "src/geosolver/engine/standard/evaluation/_hard_feasibility_core.py",
                "src/geosolver/engine/standard/evaluation/guard_penalty.py",
                "src/geosolver/engine/standard/problem/compile_problem_hard_feasibility.py"]:
        hashes[rel] = hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
    (OUT / "input-sha256.json").write_text(json.dumps(hashes, indent=2)+"\n")
    (OUT / "audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k not in ["extremes", "cv"]}, ensure_ascii=False, indent=2))
    print("CV", json.dumps(out["cv"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
