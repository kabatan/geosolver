import csv, glob, json, os, statistics as st, collections, sys
BASE = r"C:\jssa-redraw\out\B-winpc\runs"
OUT = r"C:\jssa-redraw\out\B-winpc-summary"
os.makedirs(OUT, exist_ok=True)
rows = []
for p in glob.glob(BASE + r"\*\*\*.json"):
    if p.endswith(".stats.json"):
        continue
    d = json.load(open(p, encoding="utf-8"))
    sc, rs, pr = d["score"], d.get("redraw_stats") or {}, d["process"]
    res = d.get("solver_result") or {}
    rows.append({"mode": d["mode"], "case_id": d["case_id"], "seed": d["seed"], "matched": sc["matched"],
                 "status": sc.get("status"), "solver_status": res.get("status"), "wall_seconds": sc.get("wall_seconds"),
                 "process_elapsed_s": round(pr["elapsed_seconds"], 2), "timed_out": pr["timed_out"], "returncode": pr["returncode"],
                 "cpu_percent_start": round(d["loadavg_start"], 1), "cpu": d["cpu"], "lm_first": d["lm_first"],
                 "sequences": rs.get("sequences"), "starts": rs.get("starts"), "checked": rs.get("checked"),
                 "infeasible": rs.get("infeasible"), "replaced": rs.get("replaced"), "redraws": rs.get("redraws"),
                 "gave_up_sequences": rs.get("gave_up_sequences"), "note": sc.get("note", "")[:80],
                 "solver_error": ((res.get("error") or {}).get("message") if isinstance(res.get("error"), dict) else (res.get("error") or ""))})
rows.sort(key=lambda r: (r["case_id"], r["seed"], r["mode"]))
with open(OUT + r"\per-run.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
c = collections.Counter((r["mode"], r["status"]) for r in rows)
print(len(rows), dict(c))
errs = [r for r in rows if r["status"] in ("engine_error", "resource_error")]
print("error rows:", len(errs), collections.Counter((r["mode"], r["status"]) for r in errs))
for r in errs[:6]:
    print(r["case_id"], r["seed"], r["mode"], r["status"], r["wall_seconds"], str(r["solver_error"])[:160])
print("cpu% at start median", st.median(r["cpu_percent_start"] for r in rows), "max", max(r["cpu_percent_start"] for r in rows))
print("timed_out:", sum(1 for r in rows if r["timed_out"]))
print("lm_first values:", collections.Counter(r["lm_first"] for r in rows))
for m in ("plain", "redraw"):
    L = [r for r in rows if r["mode"] == m]
    print(m, "matched", sum(1 for r in L if r["matched"]), "of", len(L), "sequences>0:", sum(1 for r in L if (r["sequences"] or 0) > 0))
