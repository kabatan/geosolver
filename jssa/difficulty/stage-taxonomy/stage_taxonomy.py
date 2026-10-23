"""Classify slow or failed runs of the main 3-seed record by where the time went and why candidates were rejected.
Uses only stored fields (phase_timings, pipeline_summary, debug_candidates, rejection_tags); no solver rerun."""
import json, glob, csv, collections, re, os, statistics as st

BASE = "/home/kabatan/work/geosolver/benchmarks/local-evaluation/jssa-main-j6-20261022"
OUT = "/mnt/c/geosolver/jssa-out/stage-taxonomy"
os.makedirs(OUT, exist_ok=True)
SLOW = 30.0

A = {}
for l in open(BASE + "/assessment.jsonl"):
    a = json.loads(l)
    A[(a["case_id"], a["seed"])] = a


def norm(t):
    t = str(t)
    if t.startswith("guard["):
        return "guard_violated(inequality/branch)"
    if t.startswith("verification_error"):
        return "verification_compile_error"
    return re.sub(r"\d+", "N", t)


rows = []
for p in sorted(glob.glob(BASE + "/runs/*/*.json")):
    j = json.load(open(p))
    cid, seed = j["case_id"], j["seed"]
    a = A[(cid, seed)]
    slow = a["wall_seconds"] >= SLOW
    failed = not a["matched"]
    if not (slow or failed):
        continue
    d = j["solver_result"]["diagnostics"]
    ps = d.get("pipeline_summary") or {}
    pt = d.get("phase_timings") or {}
    stages = {"search": pt.get("search") or 0.0, "refinement": pt.get("refinement") or 0.0,
              "identification_verification": pt.get("exact_assembly") or 0.0, "rescue": (pt.get("rescue") or 0.0) + (pt.get("phase_rescue") or 0.0)}
    total = sum(stages.values()) or 1.0
    dom = max(stages, key=stages.get)
    rf = ps.get("refinement") or {}
    ea = ps.get("exact_assembly") or {}
    att, conv = rf.get("attempted_count"), rf.get("converged_count")
    dbg = ps.get("debug_candidates") or []
    rej = collections.Counter()
    for t in d.get("rejection_tags") or []:
        rej[norm(t)] += 1
    ctags = collections.Counter()
    for c in dbg:
        if c.get("rejection_tag"):
            ctags[norm(c["rejection_tag"])] += 1
        for t in c.get("hard_violation_tags") or []:
            ctags[norm(t)] += 1
    sf = ps.get("search_staged_fallback") or {}
    pr = ps.get("phase_rescue") or {}
    conv_frac = (conv / att) if att else None
    # rule-based label (documented in README)
    if failed:
        fs = a.get("failure_stage")
        cls = "failed:" + str(fs) if fs else "failed:answer-set-mismatch(finished normally)"
    elif dom == "refinement":
        cls = "slow:refinement-bound" + ("(low convergence)" if conv_frac is not None and conv_frac < 0.5 else "")
    elif dom == "identification_verification":
        cls = "slow:identification/verification-bound"
    elif dom == "search":
        cls = "slow:search-bound" + ("(second attempt)" if sf.get("triggered") else "")
    else:
        cls = "slow:rescue-bound"
    top_rej = ", ".join(f"{k}x{v}" for k, v in (rej).most_common(3)) if rej else ""
    rows.append({
        "case_id": cid, "seed": seed, "wall_s": round(a["wall_seconds"], 1), "correct": a["matched"], "class": cls, "dominant_stage": dom,
        "dominant_stage_share": round(stages[dom] / total, 2),
        "search_s": round(stages["search"], 1), "refinement_s": round(stages["refinement"], 1),
        "identification_verification_s": round(stages["identification_verification"], 1), "rescue_s": round(stages["rescue"], 1),
        "candidates_sent_to_refinement": att, "candidates_converged": conv, "convergence_fraction": None if conv_frac is None else round(conv_frac, 2),
        "exact_accepted": ea.get("accepted_count"), "exact_rejected_false": ea.get("rejected_false_positive_count"),
        "second_attempt_triggered": sf.get("triggered"), "rescue_triggered": pr.get("triggered"),
        "run_rejection_tags": "; ".join(f"{k}x{v}" for k, v in rej.most_common()),
        "candidate_rejection_or_violation_tags": "; ".join(f"{k}x{v}" for k, v in ctags.most_common(5)),
        "failure_stage": a.get("failure_stage"), "termination_reason": a.get("termination_reason"),
    })

with open(OUT + "/per-run.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

cnt = collections.Counter(r["class"] for r in rows)
med = collections.defaultdict(list)
for r in rows:
    med[r["class"]].append(r["wall_s"])
with open(OUT + "/class-counts.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["class", "runs", "problems", "correct", "wall_median_s", "wall_max_s"])
    for k, v in cnt.most_common():
        L = [r for r in rows if r["class"] == k]
        w.writerow([k, v, len({r["case_id"] for r in L}), sum(1 for r in L if r["correct"]), round(st.median(med[k]), 1), max(med[k])])
print(len(rows))
for k, v in cnt.most_common():
    L = [r for r in rows if r["class"] == k]
    print(k, v, "problems", len({r["case_id"] for r in L}), "correct", sum(1 for r in L if r["correct"]), "wall_med", round(st.median(med[k]), 1))
# rejection tag prevalence by class
byc = collections.defaultdict(collections.Counter)
for r in rows:
    for t in r["run_rejection_tags"].split("; "):
        if t:
            byc[r["class"]][t.split("x")[0]] += 1
for k in cnt:
    print(k, dict(byc[k].most_common(5)))
# problems that are consistently slow across seeds
byp = collections.defaultdict(list)
for r in rows:
    byp[r["case_id"]].append(r)
cons = [(c, len(L), sorted({x["class"] for x in L})) for c, L in byp.items() if len(L) == 3]
print("problems slow/failed in all 3 seeds:", len(cons))
print("of which same class in all seeds:", sum(1 for c, n, cl in cons if len(cl) == 1))
