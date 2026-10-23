"""Post-hoc sensitivity, fixed in sensitivity-plan.md before this computation."""
from __future__ import annotations

import hashlib
import numpy as np
import analyze as a


def feasible_fallback(pilot):
    f = [r for r in pilot if r["start_feasible"]]
    i = [r for r in pilot if not r["start_feasible"]]
    if min(len(f), len(i)) < 2:
        return "feasible"
    qf = (sum(map(a.candidate, f)) + .5) / (len(f)+1)
    qi = (sum(map(a.candidate, i)) + .5) / (len(i)+1)
    return "plain" if qf < qi else "feasible"


def main():
    ids = sorted(r["id"] for r in a.load_csv(a.FEAS / "predictions.csv"))
    rows = []
    for horizon in (40, 200):
        for cid in ids:
            arms = {x: a.load_json(a.FEAS / f"seed2-{x}" / f"{cid}.json") for x in ("plain", "feasible")}
            for d in arms.values():
                d["gap"] = max(0, d["elapsed"] - sum(r["sec"] for r in d["records"]))
            n = min(horizon, *(len(d["records"]) for d in arms.values()))
            k = min(20, n)
            pilot = arms["plain"]["records"][:k]
            selections = {"plain": "plain", "feasible": "feasible",
                          "original20": a.pilot_choice(pilot),
                          "feasible_fallback20_posthoc": feasible_fallback(pilot),
                          "oracle_tail": max(("plain", "feasible"), key=lambda x: sum(map(a.hit, arms[x]["records"][k:n])))}
            ref = [("feasible", j) for j in range(n)]
            for method, chosen in selections.items():
                picks = [(chosen, j) for j in range(n)] if method in ("plain", "feasible") else (
                    [("plain", j) for j in range(k)] + [(chosen, j) for j in range(k, n)])
                e = a.evaluate_subset(arms, picks)
                lo, hi = a.diff_bounds(arms, picks, ref)
                rows.append({"id": cid, "horizon": horizon, "M": n,
                             "both200": int(all(len(x["records"]) == 200 for x in arms.values())),
                             "method": method, "choice": chosen, **e,
                             "diff_vs_feasible_low": lo, "diff_vs_feasible_high": hi})
    summary = {}
    for horizon in (40, 200):
        hr = [r for r in rows if r["horizon"] == horizon]
        summary[str(horizon)] = {}
        for subset, rr in [("all", hr), ("M_equals_H", [r for r in hr if r["M"] == horizon]),
                           ("both200", [r for r in hr if r["both200"]])]:
            summary[str(horizon)][subset] = out = {}
            ref = {r["id"]: r for r in rr if r["method"] == "feasible"}
            for method in ("plain", "feasible", "original20", "feasible_fallback20_posthoc", "oracle_tail"):
                m = [r for r in rr if r["method"] == method]
                out[method] = {"n": len(m), "mean_p": np.mean([r["p"] for r in m]),
                    "any_hit": sum(r["any_hit"] for r in m),
                    "mean_seconds_low": np.mean([r["seconds_low"] for r in m]),
                    "mean_seconds_allocated": np.mean([r["seconds_allocated"] for r in m]),
                    "mean_seconds_high": np.mean([r["seconds_high"] for r in m]),
                    "p_diff_vs_feasible": a.mean_ci([r["p"]-ref[r["id"]]["p"] for r in m]),
                    "cost_diff_allocated_vs_feasible": a.mean_ci([r["seconds_allocated"]-ref[r["id"]]["seconds_allocated"] for r in m]),
                    "cost_diff_lower_vs_feasible": np.mean([r["diff_vs_feasible_low"] for r in m]),
                    "cost_diff_upper_vs_feasible": np.mean([r["diff_vs_feasible_high"] for r in m])}
    a.write_csv("sensitivity-per-problem.csv", rows)
    a.write_json("sensitivity-summary.json", summary)
    a.write_json("sensitivity-provenance.json", {"input_sha256": a.INPUTS,
        "plan_sha256": hashlib.sha256((a.HERE / "sensitivity-plan.md").read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256((a.HERE / "horizon_sensitivity.py").read_bytes()).hexdigest(),
        "status": "post-hoc", "local_optimizer_calls": 0})
    for h in summary:
        print(h, {m: {k: r[k] for k in ("mean_p", "any_hit", "mean_seconds_allocated", "p_diff_vs_feasible", "cost_diff_lower_vs_feasible", "cost_diff_upper_vs_feasible")}
                  for m, r in summary[h]["all"].items()})


if __name__ == "__main__":
    main()
