"""Post-hoc (not preregistered): refit the logit model without G_det on the same 292 problems and score it on
the 20 held-out 2026 problems. First checks that the same fitting code reproduces ghost-1023/model-1023.json."""
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

D = Path(__file__).resolve().parents[1]
feas = {r["id"]: r for r in csv.DictReader(open(D / "start-feasibility-1023/per-problem.csv"))}
G = {r["id"]: int(int(r["n_pairs_found"]) > 0) for r in csv.DictReader(open(D / "ghost-exact/per-problem.csv"))
     if r["n_pairs_found"] != ""}
B = {r["id"]: r for r in csv.DictReader(open(D / "minima/basins-323.csv"))}
rows = []
for cid in G:  # same rows and target as the fit that produced model-1023.json (p from basins-323, 200 as base)
    if cid not in feas:
        continue
    r, p = feas[cid], float(B[cid]["p"])
    rows.append((cid, min(int(B[cid]["n_vars"]), 7), int(r["n_feas"]) / int(r["starts"]), G[cid],
                 math.log((p * 200 + .5) / ((1 - p) * 200 + .5))))


def design(nv, phi, g, use_g):
    x = [1.0] + [1.0 if nv == k else 0.0 for k in range(2, 8)] + [phi]
    return x + [g] if use_g else x


def fit(use_g):
    X = np.array([design(nv, phi, g, use_g) for _, nv, phi, g, _ in rows])
    y = np.array([t for *_, t in rows])
    return np.linalg.lstsq(X, y, rcond=None)[0]


m = json.load(open(D / "ghost-1023/model-1023.json"))["full"]
b = fit(True)
ref = [m["intercept"]] + [m["n_vars"][str(k)] for k in range(2, 8)] + [m["phi"], m["G"]]
print("fit_on", len(rows), "reproduces model-1023:", np.allclose(b, ref, atol=1e-6))
b2 = fit(False)
out = D / "new2026-predict"
pred = {r["id"]: r for r in csv.DictReader(open(out / "predictions.csv"))}
obs = {r["id"]: float(r["observed_logit"]) for r in csv.DictReader(open(out / "outcomes.csv"))}
ids = sorted(obs)
p2 = [float(np.dot(b2, design(min(int(pred[i]["n_vars"]), 7), float(pred[i]["phi"]), 0, False))) for i in ids]
y = [obs[i] for i in ids]
res = {"coef_nvars_phi": {"intercept": b2[0], **{f"n_vars={k}": b2[k - 1] for k in range(2, 8)}, "phi": b2[7]},
       "spearman": spearmanr(p2, y).statistic, "sse": sum((a - c) ** 2 for a, c in zip(p2, y)),
       "per_problem": {i: {"pred_logit": a, "observed_logit": c} for i, a, c in zip(ids, p2, y)}}
json.dump(res, open(out / "posthoc_nvars_phi.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "per_problem"}, indent=1))
