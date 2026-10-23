import json, glob, csv, os, statistics as st, collections, math

BASE = "/home/kabatan/work/jssa-ablation34/out/runs"
OUT = "/mnt/c/geosolver/jssa-out/ablation34"
os.makedirs(OUT, exist_ok=True)
ARMS = ["BASE", "NO_SECOND_ATTEMPT", "NO_NOMAD", "NO_ALGEBRAIC", "NO_SCALE_CHART", "NO_RESCUE", "NO_ANALYTIC_JAC"]
R = {}
for p in glob.glob(BASE + "/*/*/*.json"):
    d = json.load(open(p))
    R[(d["arm"], d["case_id"], d["seed"])] = d
cases = sorted({k[1] for k in R})
seeds = sorted({k[2] for k in R})
print("runs", len(R), "cases", len(cases), "seeds", seeds)
rows = []
for k, d in sorted(R.items()):
    rows.append({"arm": d["arm"], "case_id": d["case_id"], "seed": d["seed"], "matched": d["matched"], "status": d["status"],
                 "elapsed_s": round(d["elapsed_seconds"], 2), "wall_s": d["wall_seconds"], "timed_out": d["timed_out"],
                 "failure_stage": d["failure_stage"], "loadavg_start": round(d["loadavg_start"], 2), "cpu": d["cpu"],
                 "ablations": ",".join(d["ablations"] or [])})
with open(OUT + "/per-run.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def wall(d):
    return d["wall_seconds"] if d["wall_seconds"] is not None else d["elapsed_seconds"]


base = {(c, s): R.get(("BASE", c, s)) for c in cases for s in seeds}
summary = []
for arm in ARMS:
    A = {(c, s): R.get((arm, c, s)) for c in cases for s in seeds}
    n = sum(1 for v in A.values() if v is not None)
    solved = sum(1 for v in A.values() if v and v["matched"])
    both = [(c, s) for (c, s) in A if A[(c, s)] and base[(c, s)] and A[(c, s)]["matched"] and base[(c, s)]["matched"]]
    ratios = [wall(A[k]) / wall(base[k]) for k in both if wall(base[k]) > 0]
    gained = [k for k in A if A[k] and base[k] and A[k]["matched"] and not base[k]["matched"]]
    lost = [k for k in A if A[k] and base[k] and not A[k]["matched"] and base[k]["matched"]]
    tmo = sum(1 for v in A.values() if v and v["timed_out"])
    allw = [wall(v) for v in A.values() if v]
    summary.append({"arm": arm, "runs": n, "matched": solved, "diff_vs_BASE": solved - sum(1 for v in base.values() if v and v["matched"]),
                    "both_solved": len(both), "time_ratio_median_both_solved": round(st.median(ratios), 3) if ratios else None,
                    "lost_vs_BASE": len(lost), "gained_vs_BASE": len(gained), "timeouts": tmo,
                    "median_wall_all_s": round(st.median(allw), 2), "total_wall_h": round(sum(allw) / 3600, 2),
                    "lost_cases": ";".join(sorted({f"{c}#{s}" for c, s in lost})), "gained_cases": ";".join(sorted({f"{c}#{s}" for c, s in gained}))})
with open(OUT + "/summary.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
for s in summary:
    print(s["arm"], "runs", s["runs"], "matched", s["matched"], "diff", s["diff_vs_BASE"], "both", s["both_solved"], "ratio", s["time_ratio_median_both_solved"], "lost", s["lost_vs_BASE"], "gained", s["gained_vs_BASE"], "tmo", s["timeouts"], "medwall", s["median_wall_all_s"], "h", s["total_wall_h"])
bl = [R[k]["loadavg_start"] for k in R]
print("loadavg_start median", round(st.median(bl), 2), "max", round(max(bl), 2))
# per-arm per-seed matched
for arm in ARMS:
    print(arm, {s: sum(1 for c in cases if R.get((arm, c, s)) and R[(arm, c, s)]["matched"]) for s in seeds})
print("BASE failures:", sorted((c, s, R[("BASE", c, s)]["status"], R[("BASE", c, s)]["failure_stage"]) for c in cases for s in seeds if R.get(("BASE", c, s)) and not R[("BASE", c, s)]["matched"]))
print("non-normal statuses:", collections.Counter(d["status"] for d in R.values()))
