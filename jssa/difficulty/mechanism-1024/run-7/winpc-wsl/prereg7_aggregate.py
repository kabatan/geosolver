import json, glob, csv, os, statistics as st, collections
W = "/home/kabatan/work/jssa-prereg7"; OUT = "/mnt/c/geosolver/jssa-out/prereg7"
os.makedirs(OUT, exist_ok=True)
ps = json.load(open(W + "/problem-set.json"))
strata = {k: ps[k] for k in ("hard", "fast_algebraic", "fast_search", "multivalued")}
ARMS = ["BASE", "NO_ALGEBRAIC", "NO_SECOND_ATTEMPT"]
R = {}
for p in glob.glob(W + "/out/runs/*/*/*.json"):
    d = json.load(open(p)); R[(d["arm"], d["case_id"], d["seed"])] = d
ids = [i for k in strata for i in strata[k]]
seeds = (401, 402, 403)
print("runs", len(R), "expected", 72 * 3 * 3)
def wall(d): return d["wall_seconds"] if d["wall_seconds"] is not None else d["elapsed_seconds"]
def cost(d): return wall(d) if d["matched"] else 180.0
rows = []
for (arm, c, s), d in sorted(R.items()):
    rows.append({"arm": arm, "case_id": c, "seed": s, "stratum": next(k for k in strata if c in strata[k]), "matched": d["matched"], "status": d["status"],
        "wall_s": round(wall(d), 2), "cost_s": round(cost(d), 2), "timed_out": d["timed_out"], "failure_stage": d["failure_stage"], "second_attempt_triggered": d["second_attempt_triggered"],
        "rescue_triggered": d["rescue_triggered"], "answer_source": d["answer_source_candidate_id"], "refine_attempted": d["refine_attempted"], "exact_accepted": d["exact_accepted"],
        "exact_rejected_false": d["exact_rejected_false"], "loadavg_start": round(d["loadavg_start"], 2), "cpu": d["cpu"], "returncode": d["returncode"]})
with open(OUT + "/per-run.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def solved(arm, c): return sum(1 for s in seeds if R.get((arm, c, s)) and R[(arm, c, s)]["matched"]) >= 2
res = {}
for k, L in list(strata.items()) + [("all72", ids)]:
    res[k] = {a: sum(solved(a, c) for c in L) for a in ARMS}
    res[k]["mean_cost"] = {a: round(st.mean(cost(R[(a, c, s)]) for c in L for s in seeds if (a, c, s) in R), 2) for a in ARMS}
    res[k]["runs_matched"] = {a: sum(1 for c in L for s in seeds if R.get((a, c, s)) and R[(a, c, s)]["matched"]) for a in ARMS}
def ratios(arm, L):
    out = {}
    for c in L:
        r = [wall(R[(arm, c, s)]) / wall(R[("BASE", c, s)]) for s in seeds if (arm, c, s) in R and ("BASE", c, s) in R and R[(arm, c, s)]["matched"] and R[("BASE", c, s)]["matched"] and wall(R[("BASE", c, s)]) > 0]
        if r: out[c] = st.median(r)
    return out
m2 = {}
for k in ("fast_algebraic", "fast_search"):
    rr = ratios("NO_ALGEBRAIC", strata[k]); m2[k] = {"n_with_ratio": len(rr), "n_ge_1.5": sum(1 for v in rr.values() if v >= 1.5), "median_of_problem_medians": round(st.median(rr.values()), 3) if rr else None, "per_problem": {c: round(v, 2) for c, v in rr.items()}}
rr_all = ratios("NO_SECOND_ATTEMPT", ids)
fire = {a: {"second_attempt_triggered_runs": sum(1 for (aa, c, s), d in R.items() if aa == a and d["second_attempt_triggered"]), "rescue_triggered_runs": sum(1 for (aa, c, s), d in R.items() if aa == a and d["rescue_triggered"])} for a in ARMS}
err = collections.Counter((a, d["status"], d["failure_stage"]) for (a, c, s), d in R.items() if not d["matched"])
tmo = {a: sum(1 for (aa, c, s), d in R.items() if aa == a and d["timed_out"]) for a in ARMS}
fp = {a: sum(1 for (aa, c, s), d in R.items() if aa == a and not d["matched"] and d["answer_keys"]) for a in ARMS}
mv = {a: {"exact": sum(1 for c in strata["multivalued"] for s in seeds if R.get((a, c, s)) and R[(a, c, s)]["matched"])} for a in ARMS}
per_problem = []
for c in ids:
    per_problem.append({"case_id": c, "stratum": next(k for k in strata if c in strata[k]), **{f"{a}_seeds_matched": sum(1 for s in seeds if R.get((a, c, s)) and R[(a, c, s)]["matched"]) for a in ARMS}, **{f"{a}_mean_cost": round(st.mean(cost(R[(a, c, s)]) for s in seeds if (a, c, s) in R), 1) for a in ARMS}})
with open(OUT + "/per-problem.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(per_problem[0])); w.writeheader(); w.writerows(per_problem)
lost = [p["case_id"] for p in per_problem if p["NO_SECOND_ATTEMPT_seeds_matched"] < p["BASE_seeds_matched"]]
bl = [d["loadavg_start"] for d in R.values()]
summary = {"runs": len(R), "solved_problems_by_stratum": res, "M2_time_ratio_NO_ALGEBRAIC_vs_BASE": m2, "second_attempt_firing_and_rescue": fire,
           "NO_SECOND_ATTEMPT_time_ratio_median_all": round(st.median(rr_all.values()), 3) if rr_all else None,
           "unmatched_counts": {f"{a}|{s}|{f}": n for (a, s, f), n in err.items()}, "timeouts": tmo, "unmatched_with_answer_keys": fp, "multivalued_matched_runs": mv,
           "problems_where_NO_SECOND_ATTEMPT_seeds_matched_lt_BASE": lost, "loadavg_start_median": round(st.median(bl), 2), "loadavg_start_max": round(max(bl), 2)}
json.dump(summary, open(OUT + "/summary.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(summary, indent=1, ensure_ascii=False))
