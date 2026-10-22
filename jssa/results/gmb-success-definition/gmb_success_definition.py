"""Re-tabulate existing GMB records: GMB self-judgement vs independent checker, and why the checker rejected."""
import csv, json, os, collections, re, math

HOME = "/home/kabatan/work"
RECORDS = [
    # label, condition, case-results dir, assessment dir
    ("default_seed0", "default eps=1e-3", f"{HOME}/geosolver/benchmarks/local-evaluation/gmb-imo39-seed0-cpu4-20261022",
     f"{HOME}/geosolver/benchmarks/local-evaluation/gmb-geosolver-campaign-20261022/assessment"),
    ("default_seeds1-2", "default eps=1e-3", f"{HOME}/geosolver/benchmarks/local-evaluation/gmb-imo39-seeds1-2-cpu4-20261022",
     f"{HOME}/geosolver/benchmarks/local-evaluation/gmb-geosolver-campaign-20261022/assessment"),
    ("strict_seed0", "strict eps=1e-8", f"{HOME}/geosolver-gmbstrict/benchmarks/local-evaluation/gmb-strict-seed0-cpu4-20261022",
     f"{HOME}/geosolver-gmbstrict/benchmarks/local-evaluation/gmb-strict-comparison-campaign-20261022/assessment"),
    ("strict_seeds1-2", "strict eps=1e-8", f"{HOME}/geosolver-gmbstrict/benchmarks/local-evaluation/gmb-strict-seeds1-2-cpu4-20261022",
     f"{HOME}/geosolver-gmbstrict/benchmarks/local-evaluation/gmb-strict-comparison-campaign-20261022/assessment"),
]
OUT = "/mnt/c/geosolver/jssa-out/gmb-success-definition"
os.makedirs(OUT, exist_ok=True)


def load_rr(adir):
    rows = {}
    for l in open(adir + "/run-results.jsonl"):
        r = json.loads(l)
        if r["method"] == "gmb":
            rows[(r["case_id"], r["seed"], os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(r["run_directory"])))) if False else r["run_directory"])] = r
    return rows


def walk_checks(x, acc):
    if isinstance(x, dict):
        if "kind" in x and "label" in x and "status" in x and "error" in x:
            acc.append(x)
        for v in x.values():
            walk_checks(v, acc)
    elif isinstance(x, list):
        for v in x:
            walk_checks(v, acc)


def bucket(e):
    if e is None:
        return "no_error_value"
    if e < 1e-6: return "<1e-6"
    if e < 1e-4: return "1e-6..1e-4"
    if e < 1e-3: return "1e-4..1e-3"
    if e < 1e-2: return "1e-3..1e-2"
    if e < 1: return "1e-2..1"
    return ">=1"


def fnum(s):
    try:
        return float(s)
    except Exception:
        return None


trial_rows = []
summary = []
fail_breakdown = []
for label, cond, cdir, adir in RECORDS:
    rr_all = load_rr(adir)
    # reused rows are those whose run_directory lies under this record directory
    byk = {}
    for (case, seed, rd), r in rr_all.items():
        if rd.startswith(cdir + "/"):
            byk[(case, seed)] = r
    cr = list(csv.DictReader(open(cdir + "/case-results.csv")))
    n = len(cr)
    outcomes = collections.Counter(r["outcome"] for r in cr)
    returned = [r for r in cr if r["outcome"] == "model_returned"]
    selfpass = [r for r in returned if r["all_goals_passed"] == "True"]
    selfunknown = [r for r in returned if r["all_goals_passed"] == ""]
    indep = {}
    for tol in ("1e-3", "1e-6", "1e-9"):
        ok_ret = 0
        ok_self = 0
        for r in returned:
            k = (r["case_id"], int(r["seed"]))
            a = byk.get(k)
            if a is None:
                continue
            ok = a["thresholds"][tol]["success"]
            ok_ret += ok
            if r["all_goals_passed"] == "True":
                ok_self += ok
        indep[tol] = (ok_ret, ok_self)
    # failure breakdown at 1e-6 among returned models
    cats = collections.Counter(); eqbuckets = collections.Counter(); selfpass_fail_cats = collections.Counter(); selfpass_fail_buckets = collections.Counter()
    for r in returned:
        k = (r["case_id"], int(r["seed"]))
        a = byk.get(k)
        if a is None:
            continue
        mf = os.path.join(adir, "models/gmb", r["case_id"], str(r["seed"]), "000.json")
        info = {"record": label, "case_id": r["case_id"], "seed": r["seed"], "self_pass": r["all_goals_passed"],
                "indep_1e-3": a["thresholds"]["1e-3"]["success"], "indep_1e-6": a["thresholds"]["1e-6"]["success"], "indep_1e-9": a["thresholds"]["1e-9"]["success"],
                "goals_passed": r["goals_passed"], "goals_total": r["goals_total"]}
        failed_eq, failed_strict, all_eq = [], [], []
        witness = False
        if os.path.exists(mf):
            d = json.load(open(mf))
            res = d["checks"]["1e-6"]["result"]
            acc = []
            walk_checks(res, acc)
            for c in acc:
                e = fnum(c.get("error"))
                if c["kind"] == "equality":
                    if e is not None:
                        all_eq.append(e)
                    if c["status"] == "failed":
                        failed_eq.append(e)
                elif c["status"] == "failed":
                    failed_strict.append((c["kind"], c["label"]))
            reasons = " ".join(d["checks"]["1e-6"].get("failure_reasons") or [])
            witness = ("invalid_intersection_witness" in reasons) or ("ambiguous" in reasons)
        mx_failed = max([e for e in failed_eq if e is not None], default=None)
        mx_all = max(all_eq, default=None)
        info.update({"max_failed_equality_error": mx_failed, "max_equality_error": mx_all, "n_failed_equality": len(failed_eq),
                     "n_failed_strict_inequality": len(failed_strict), "witness_or_branch_flag": witness})
        if info["indep_1e-6"]:
            cat = "pass_1e-6"
        elif witness and not failed_eq:
            cat = "witness/branch (invalid intersection witness or ambiguous exclusion)"
        elif failed_strict and not failed_eq:
            cat = "inequality (strict) failed"
        elif failed_eq and failed_strict:
            cat = "equality residual + inequality"
        elif failed_eq:
            cat = "equality residual only"
        else:
            cat = "other"
        info["category_1e-6"] = cat
        info["equality_error_bucket"] = bucket(mx_failed) if failed_eq else ""
        trial_rows.append(info)
        cats[cat] += 1
        if failed_eq:
            eqbuckets[bucket(mx_failed)] += 1
        if r["all_goals_passed"] == "True" and not info["indep_1e-6"]:
            selfpass_fail_cats[cat] += 1
            if failed_eq:
                selfpass_fail_buckets[bucket(mx_failed)] += 1
    summary.append({
        "record": label, "condition": cond, "trials": n, "outcomes": dict(outcomes),
        "(a1)_models_returned": len(returned), "(a2)_self_check_all_goals_passed": len(selfpass), "self_check_not_evaluated": len(selfunknown),
        "(b)_indep_1e-3_of_returned": indep["1e-3"][0], "(b)_indep_1e-6_of_returned": indep["1e-6"][0], "(b)_indep_1e-9_of_returned": indep["1e-9"][0],
        "(b)_indep_1e-3_of_selfpass": indep["1e-3"][1], "(b)_indep_1e-6_of_selfpass": indep["1e-6"][1], "(b)_indep_1e-9_of_selfpass": indep["1e-9"][1],
        "(c)_categories_returned_1e-6": dict(cats), "(c)_failed_equality_error_buckets_returned": dict(eqbuckets),
        "(c)_categories_selfpass_but_fail_1e-6": dict(selfpass_fail_cats), "(c)_equality_buckets_selfpass_but_fail": dict(selfpass_fail_buckets),
    })

json.dump(summary, open(OUT + "/summary.json", "w"), ensure_ascii=False, indent=1)
keys = list(trial_rows[0])
with open(OUT + "/per-trial.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(trial_rows)
for s in summary:
    print(json.dumps(s, ensure_ascii=False))
