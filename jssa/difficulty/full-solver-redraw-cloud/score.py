"""Score preregistration-4 (A0, S1-S3) for one arm directory (out/A or out/B). Usage: score.py OUT_DIR"""
import csv
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
out = Path(sys.argv[1])
pred = {r["id"]: r for r in csv.DictReader(open(ROOT / "jssa/difficulty/start-feasibility-1023/predictions.csv"))}
runs = {}
for f in (out / "runs").glob("*/*/*.json"):
    if f.name.endswith(".stats.json"):
        continue
    d = json.loads(f.read_text())
    runs[(d["mode"], d["case_id"], d["seed"])] = d
seeds = sorted({k[2] for k in runs})
ids = [i for i in pred if all((m, i, s) in runs for m in ("plain", "redraw") for s in seeds)]


def cost(d):
    return min(180.0, float(d["score"]["wall_seconds"] or 180.0)) if d["score"]["matched"] else 180.0


rows = []
for i in ids:
    c = {m: [cost(runs[(m, i, s)]) for s in seeds] for m in ("plain", "redraw")}
    ok = {m: [runs[(m, i, s)]["score"]["matched"] for s in seeds] for m in ("plain", "redraw")}
    st = [runs[("redraw", i, s)]["redraw_stats"] or {} for s in seeds]
    stp = [runs[("plain", i, s)]["redraw_stats"] or {} for s in seeds]
    rows.append({"id": i, "C_plain": statistics.mean(c["plain"]), "C_redraw": statistics.mean(c["redraw"]),
                 "ok_plain": sum(ok["plain"]), "ok_redraw": sum(ok["redraw"]),
                 "lm_ran_plain": sum(1 for x in stp if x.get("sequences", 0) > 0),
                 "lm_ran_redraw": sum(1 for x in st if x.get("sequences", 0) > 0),
                 "replaced": sum(x.get("replaced", 0) for x in st), "checked": sum(x.get("checked", 0) for x in st),
                 "pred_delta": pred[i]["pred_delta"]})
for r in rows:
    r["diff"] = r["C_redraw"] - r["C_plain"]
with open(out / "per-problem.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
diffs = np.array([r["diff"] for r in rows])
rng = np.random.default_rng(0)
boot = [rng.choice(diffs, len(diffs)).mean() for _ in range(10000)]
lo, hi = np.percentile(boot, [2.5, 97.5])
n_runs = len(rows) * len(seeds)
replaced_runs = sum(1 for i in ids for s in seeds if (runs[("redraw", i, s)]["redraw_stats"] or {}).get("replaced", 0) > 0)
acc_p = sum(r["ok_plain"] for r in rows) / n_runs
acc_r = sum(r["ok_redraw"] for r in rows) / n_runs
pd_rows = [r for r in rows if r["pred_delta"] not in ("", "None")]
rho = spearmanr([-r["diff"] for r in pd_rows], [float(r["pred_delta"]) for r in pd_rows]).statistic
res = {"problems": len(rows), "seeds": seeds, "runs_per_arm": n_runs,
       "A0_share_runs_with_replacement": replaced_runs / n_runs,
       "runs_lm_stage_ran_plain": sum(r["lm_ran_plain"] for r in rows),
       "runs_lm_stage_ran_redraw": sum(r["lm_ran_redraw"] for r in rows),
       "mean_C_plain": float(np.mean([r["C_plain"] for r in rows])),
       "mean_C_redraw": float(np.mean([r["C_redraw"] for r in rows])),
       "S1_mean_diff": float(diffs.mean()), "S1_ci95": [float(lo), float(hi)],
       "S1_holds": bool(hi < 0),
       "S2_acc_plain": acc_p, "S2_acc_redraw": acc_r, "S2_holds": bool(acc_r - acc_p >= -0.01),
       "S3_rho_cost_drop_vs_pred_delta": float(rho), "S3_n": len(pd_rows), "S3_holds": bool(rho >= 0.3),
       "problems_faster_by_10pct": sum(1 for r in rows if r["C_redraw"] < 0.9 * r["C_plain"]),
       "problems_slower_by_10pct": sum(1 for r in rows if r["C_redraw"] > 1.1 * r["C_plain"])}
json.dump(res, open(out / "score.json", "w"), indent=1)
print(json.dumps(res, indent=1))
