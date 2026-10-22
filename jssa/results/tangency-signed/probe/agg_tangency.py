import json, glob, os, csv, statistics as st

D = "/home/kabatan/work/jssa-searchmode/tangency-out"
OUT = "/mnt/c/geosolver/jssa-out/tangency-signed"
os.makedirs(OUT, exist_ok=True)
cases = sorted({os.path.basename(p).split(".")[0] for p in glob.glob(D + "/*.json") if "solver" not in p})
rows = []
cand_rows = []
for c in cases:
    for order in ("off_first", "on_first"):
        p = f"{D}/{c}.{order}.json"
        if not os.path.exists(p):
            rows.append({"case_id": c, "order": order, "status": "no_output"})
            continue
        d = json.load(open(p))
        w, s = d.get("without_signed_rewrite", {}), d.get("with_signed_rewrite", {})
        if "error" in w or "error" in s or not w or not s:
            rows.append({"case_id": c, "order": order, "status": "error"})
            continue
        def best(x):
            v = [r["residual_digits"] for r in x["candidates"] if r["residual_digits"] is not None]
            return max(v) if v else None
        def med(x):
            v = [r["residual_digits"] for r in x["candidates"] if r["residual_digits"] is not None]
            return st.median(v) if v else None
        wc = {r["candidate_id"]: r for r in w["candidates"]}
        sc = {r["candidate_id"]: r for r in s["candidates"]}
        common = sorted(set(wc) & set(sc))
        better = sum(1 for i in common if (sc[i]["residual_digits"] or 0) > (wc[i]["residual_digits"] or 0) + 1)
        worse = sum(1 for i in common if (wc[i]["residual_digits"] or 0) > (sc[i]["residual_digits"] or 0) + 1)
        for i in common:
            cand_rows.append({"case_id": c, "order": order, "candidate_id": i,
                              "without_status": wc[i]["status"], "without_digits": wc[i]["residual_digits"],
                              "with_status": sc[i]["status"], "with_digits": sc[i]["residual_digits"]})
        rows.append({
            "case_id": c, "order": order, "status": "ok", "n_candidates": d["n_input_candidates"],
            "with_seconds": round(s["seconds"], 2), "without_seconds": round(w["seconds"], 2),
            "with_converged": s["converged"], "without_converged": w["converged"],
            "with_best_digits": best(s), "without_best_digits": best(w),
            "with_median_digits": med(s), "without_median_digits": med(w),
            "with_deadline_hit": s["deadline_hit"], "without_deadline_hit": w["deadline_hit"],
            "candidates_with_more_digits": better, "candidates_with_fewer_digits": worse, "common_candidates": len(common),
        })
keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("case_id", "order", "status"), k))
with open(OUT + "/per-case.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
if cand_rows:
    with open(OUT + "/per-candidate.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cand_rows[0])); w.writeheader(); w.writerows(cand_rows)
ok = [r for r in rows if r["status"] == "ok"]
print(len(rows), "rows,", len(ok), "ok")
for r in ok:
    print(r["case_id"], r["order"], "cands", r["n_candidates"], "t_with", r["with_seconds"], "t_without", r["without_seconds"],
          "conv", r["with_converged"], r["without_converged"], "best", r["with_best_digits"] and round(r["with_best_digits"], 1), r["without_best_digits"] and round(r["without_best_digits"], 1),
          "med", r["with_median_digits"] and round(r["with_median_digits"], 1), r["without_median_digits"] and round(r["without_median_digits"], 1),
          "more/less", r["candidates_with_more_digits"], r["candidates_with_fewer_digits"], "dl", r["with_deadline_hit"], r["without_deadline_hit"])
