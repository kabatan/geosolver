"""Read-only reanalysis for astra-I. No optimizer, solver CLI, or network calls.

Run from any directory with the specified pre-existing Python environment:
  python -B analyze.py --measure-features
  python -B analyze.py
All writes are confined to this script's directory; inputs are hashed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FEAS = ROOT / "jssa/difficulty/start-feasibility-1023"
RAW = ROOT / "jssa/difficulty/minima/raw-323"
INPUTS: dict[str, str] = {}
SEED = 171023
BOOT = 10000


def read_bytes(path):
    data = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    return data


def load_json(path):
    return json.loads(read_bytes(path))


def load_csv(path):
    return list(csv.DictReader(read_bytes(path).decode().splitlines()))


def write_csv(name, rows):
    if not rows:
        return
    with (HERE / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def clean_json(x):
    if isinstance(x, dict):
        return {k: clean_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean_json(v) for v in x]
    if isinstance(x, np.ndarray):
        return clean_json(x.tolist())
    if isinstance(x, np.generic):
        return clean_json(x.item())
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def write_json(name, obj):
    (HERE / name).write_text(json.dumps(clean_json(obj), ensure_ascii=False, indent=2) + "\n")


def mean_ci(values):
    a = np.asarray(values, dtype=float)
    if not len(a):
        return {"n": 0}
    assert np.isfinite(a).all()
    rng = np.random.default_rng(SEED)
    means = []
    for _ in range(20):
        ii = rng.integers(0, len(a), (BOOT // 20, len(a)))
        means.extend(a[ii].mean(axis=1).tolist())
    return {"n": len(a), "mean": float(a.mean()), "ci95": np.quantile(means, [.025, .975]).tolist()}


def quantiles(values):
    a = np.asarray(values, dtype=float)
    return {"n": len(a), "mean": float(a.mean()), "min": float(a.min()),
            "q25": float(np.quantile(a, .25)), "median": float(np.median(a)),
            "q75": float(np.quantile(a, .75)), "q90": float(np.quantile(a, .9)), "max": float(a.max())}


def candidate(record):
    # Deliberately does NOT inspect cls, ref, references, or answer keys.
    ans = record.get("ans")
    return ans is not None and math.isfinite(float(ans))


def hit(record):
    # Used only by evaluation and by the explicitly labelled oracle control.
    return record["cls"] == "hit"


def pilot_choice(records, oracle=False):
    if len(records) < 20:
        return "plain"
    f = [r for r in records if r["start_feasible"]]
    i = [r for r in records if not r["start_feasible"]]
    if min(len(f), len(i)) < 2:
        return "plain"
    obs = hit if oracle else candidate
    qf = (sum(map(obs, f)) + .5) / (len(f) + 1)
    qi = (sum(map(obs, i)) + .5) / (len(i) + 1)
    return "feasible" if qf > qi else "plain"


def evaluate_subset(arms, picks):
    recs = [arms[a]["records"][k] for a, k in picks]
    low = sum(float(r["sec"]) for r in recs)
    used = Counter(a for a, _ in picks)
    est = low + sum(arms[a]["gap"] * n / len(arms[a]["records"]) for a, n in used.items())
    high = low + sum(arms[a]["gap"] for a in used)
    return {"p": sum(map(hit, recs)) / len(recs), "hits": sum(map(hit, recs)),
            "any_hit": int(any(map(hit, recs))), "candidates": sum(map(candidate, recs)),
            "false_candidates": sum(candidate(r) and not hit(r) for r in recs),
            "seconds_low": low, "seconds_allocated": est, "seconds_high": high,
            "nfev": sum(r["nfev"] for r in recs),
            "redraws": sum(r.get("redraws", 0) for r in recs)}


def diff_bounds(arms, left, right):
    # Common attempts cancel exactly, including their unrecorded overhead.
    lp, rp = set(left) - set(right), set(right) - set(left)
    raw = sum(arms[a]["records"][k]["sec"] for a, k in lp)
    raw -= sum(arms[a]["records"][k]["sec"] for a, k in rp)
    lo = raw - sum(arms[a]["gap"] for a in {a for a, _ in rp})
    hi = raw + sum(arms[a]["gap"] for a in {a for a, _ in lp})
    return lo, hi


def local_analysis():
    ids = sorted(r["id"] for r in load_csv(FEAS / "predictions.csv"))
    rows, audit_rows = [], []
    methods = ("plain", "feasible", "pilot20", "oracle_labels20", "oracle_hits")
    for cid in ids:
        arms = {a: load_json(FEAS / f"seed2-{a}" / f"{cid}.json") for a in ("plain", "feasible")}
        for a, data in arms.items():
            rr = data["records"]
            assert [r["k"] for r in rr] == list(range(len(rr)))
            gap = data["elapsed"] - sum(r["sec"] for r in rr)
            assert gap >= -1e-6
            data["gap"] = max(0, gap)
            audit_rows.append({"id": cid, "arm": a, "records": len(rr), "elapsed": data["elapsed"],
                               "sum_sec": sum(r["sec"] for r in rr), "unallocated_seconds": data["gap"],
                               "redraws": sum(r.get("redraws", 0) for r in rr),
                               "hits": sum(map(hit, rr)), "candidates": sum(map(candidate, rr)),
                               "false_candidates": sum(candidate(r) and not hit(r) for r in rr)})
        n = min(40, *(len(x["records"]) for x in arms.values()))
        assert n > 0
        k = min(20, n)
        pilot = arms["plain"]["records"][:k]
        choice = pilot_choice(pilot)
        ochoice = pilot_choice(pilot, oracle=True)
        choices = {"plain": [("plain", j) for j in range(n)],
                   "feasible": [("feasible", j) for j in range(n)],
                   "pilot20": [("plain", j) for j in range(k)] + [(choice, j) for j in range(k, n)],
                   "oracle_labels20": [("plain", j) for j in range(k)] + [(ochoice, j) for j in range(k, n)]}
        oracle_arm = max(("plain", "feasible"), key=lambda a: sum(map(hit, arms[a]["records"][:n])))
        choices["oracle_hits"] = choices[oracle_arm]
        row = {"id": cid, "n_vars": arms["plain"]["n_vars"], "M": n,
               "n_plain": len(arms["plain"]["records"]), "n_feasible": len(arms["feasible"]["records"]),
               "both200": int(all(len(v["records"]) == 200 for v in arms.values())),
               "pilot_n": k, "pilot_f": sum(bool(r["start_feasible"]) for r in pilot),
               "pilot_q_f": sum(candidate(r) and r["start_feasible"] for r in pilot),
               "pilot_q_i": sum(candidate(r) and not r["start_feasible"] for r in pilot),
               "pilot_candidates": sum(map(candidate, pilot)),
               "pilot_false_candidates": sum(candidate(r) and not hit(r) for r in pilot),
               "choice": choice, "oracle_label_choice": ochoice,
               "pilot_seconds_low": sum(r["sec"] for r in pilot),
               "pilot_seconds_allocated": sum(r["sec"] for r in pilot) + arms["plain"]["gap"] * k / len(arms["plain"]["records"]),
               "pilot_seconds_high": sum(r["sec"] for r in pilot) + arms["plain"]["gap"],
               "pilot_nfev": sum(r["nfev"] for r in pilot),
               "full_p_plain": arms["plain"]["p_any"], "full_p_feasible": arms["feasible"]["p_any"]}
        for method in methods:
            ev = evaluate_subset(arms, choices[method])
            row.update({f"{method}_{key}": v for key, v in ev.items()})
        for ref in ("plain", "feasible"):
            low, high = diff_bounds(arms, choices["pilot20"], choices[ref])
            row[f"diff_vs_{ref}_low"] = low
            row[f"diff_vs_{ref}_high"] = high
        # Tail is disjoint from the pilot; positive p is the evaluation label only.
        if n > k:
            pp = sum(map(hit, arms["plain"]["records"][k:n])) / (n-k)
            pf = sum(map(hit, arms["feasible"]["records"][k:n])) / (n-k)
            row["tail_delta"] = pf - pp
        else:
            row["tail_delta"] = ""
        rows.append(row)
    write_csv("local-per-problem.csv", rows)
    write_csv("local-cost-audit.csv", audit_rows)
    result = {"full_stream_reproduction": {
        "mean_p_plain": np.mean([r["full_p_plain"] for r in rows]),
        "mean_p_feasible": np.mean([r["full_p_feasible"] for r in rows]),
        "starts_plain": sum(r["n_plain"] for r in rows), "starts_feasible": sum(r["n_feasible"] for r in rows)},
        "coverage": {"problems": len(rows), "M40": sum(r["M"] == 40 for r in rows),
                     "M_lt20": sum(r["M"] < 20 for r in rows), "both200": sum(r["both200"] for r in rows)},
        "pilot_cost": {x: quantiles([r[f"pilot_{x}"] for r in rows]) for x in ("seconds_low", "seconds_allocated", "seconds_high", "nfev")},
        "decision_disagreement_with_true_labels": sum(r["choice"] != r["oracle_label_choice"] for r in rows),
        "pilot_false_candidates": sum(r["pilot_false_candidates"] for r in rows),
        "pilot_candidates": sum(r["pilot_candidates"] for r in rows),
        "selected_stream_false_candidates": sum(r["pilot20_false_candidates"] for r in rows),
        "support": {"fewer_than_two_F": sum(r["pilot_f"] < 2 for r in rows),
                    "fewer_than_two_I": sum(r["pilot_n"]-r["pilot_f"] < 2 for r in rows),
                    "complete20_both_at_least2": sum(r["pilot_n"] == 20 and 2 <= r["pilot_f"] <= 18 for r in rows)},
        "all_stream_candidate_counts": {a: {k: sum(r[k] for r in audit_rows if r["arm"] == a)
                                              for k in ("candidates", "false_candidates", "hits")} for a in ("plain", "feasible")},
        "subsets": {}}
    for subset, rr in [("all150", rows), ("M40", [r for r in rows if r["M"] == 40]),
                       ("both200", [r for r in rows if r["both200"]])]:
        result["subsets"][subset] = out = {"n": len(rr), "choose_feasible": sum(r["choice"] == "feasible" for r in rr)}
        for m in methods:
            out[m] = {"mean_p": np.mean([r[f"{m}_p"] for r in rr]),
                      "any_hit_problems": sum(r[f"{m}_any_hit"] for r in rr),
                      "total_hits": sum(r[f"{m}_hits"] for r in rr),
                      "mean_seconds_low": np.mean([r[f"{m}_seconds_low"] for r in rr]),
                      "mean_seconds_allocated": np.mean([r[f"{m}_seconds_allocated"] for r in rr]),
                      "mean_seconds_high": np.mean([r[f"{m}_seconds_high"] for r in rr])}
        for ref in ("plain", "feasible"):
            out[f"pilot_vs_{ref}"] = {
                "p_diff": mean_ci([r["pilot20_p"] - r[f"{ref}_p"] for r in rr]),
                "cost_diff_allocated": mean_ci([r["pilot20_seconds_allocated"] - r[f"{ref}_seconds_allocated"] for r in rr]),
                "cost_diff_lower": mean_ci([r[f"diff_vs_{ref}_low"] for r in rr]),
                "cost_diff_upper": mean_ci([r[f"diff_vs_{ref}_high"] for r in rr]),
                "gained_any_hit": sum(r["pilot20_any_hit"] > r[f"{ref}_any_hit"] for r in rr),
                "lost_any_hit": sum(r["pilot20_any_hit"] < r[f"{ref}_any_hit"] for r in rr)}
    return result


def measure_features():
    # Only constructs evaluators and evaluates already saved initial points.
    # Never imports probe_basins, which exposes optimizer entry points.
    sys.path.insert(0, str(ROOT / "src"))
    from geosolver import GeometryProblem
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    cases = {r["id"]: r for r in (json.loads(s) for s in read_bytes(ROOT / "benchmarks/cases.jsonl").decode().splitlines())}
    old = {r["id"]: r for r in load_csv(FEAS / "per-problem.csv")}
    rows = []
    for index, cid in enumerate(sorted(cases)):
        data = load_json(RAW / f"{cid}.json")
        rr = data.get("records", [])
        d = int(data["n_vars"])
        if d == 0:
            rows.append({"id": cid, "d": 0, "n": 0, "feasible": 0, "phi": 1.0,
                         "feature_seconds": 0, "build_seconds": 0, "mismatched_saved_start": 0,
                         "matches_existing": True, "pilot20_n": 0, "pilot20_seconds_low": 0,
                         "pilot20_seconds_allocated": 0, "pilot20_seconds_high": 0})
            continue
        t0 = time.perf_counter()
        ev = build_ir_evaluator(load_problem_bundle(GeometryProblem.model_validate(cases[cid]["dsl"]).engine_document()))
        build_s = time.perf_counter() - t0
        box = np.asarray(data["box"], dtype=float)
        rng = np.random.default_rng(data["seed"])
        nf, mismatched = 0, 0
        t0 = time.perf_counter()
        for k, r in enumerate(rr):
            assert r["k"] == k
            x = box[:, 0] + rng.random(d) * (box[:, 1] - box[:, 0])
            if "start" in r and not np.array_equal(x, np.asarray(r["start"])):
                mismatched += 1
            # Match the existing phi CSV's exact population, not unseen points.
            if "start" not in r:
                continue
            try:
                feasible = bool(ev.evaluate_float_hard_feasibility(list(x), include_margins=False).hard_feasible)
            except Exception:
                feasible = False
            nf += feasible
        feature_s = time.perf_counter() - t0
        nn = sum("start" in r for r in rr)
        assert nn > 0
        gap = max(0, data["elapsed"] - sum(r["sec"] for r in rr))
        pilot = rr[:20]
        ps = sum(r["sec"] for r in pilot)
        rows.append({"id": cid, "d": d, "n": nn, "feasible": nf, "phi": nf / nn,
                     "feature_seconds": feature_s, "build_seconds": build_s,
                     "mismatched_saved_start": mismatched,
                     "matches_existing": nf == int(old[cid]["n_feas"]) and nn == int(old[cid]["starts"]),
                     "pilot20_n": len(pilot), "pilot20_seconds_low": ps,
                     "pilot20_seconds_allocated": ps + gap * len(pilot) / len(rr),
                     "pilot20_seconds_high": ps + gap})
        if index % 40 == 0:
            print(f"features {index+1}/{len(cases)}", flush=True)
    assert all(r["matches_existing"] and r["mismatched_saved_start"] == 0 for r in rows)
    write_csv("features.csv", rows)
    write_json("feature-provenance.json", {"measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.executable, "local_optimizer_calls": 0, "single_thread": True,
        "feature_input_hashes": INPUTS, "phi_matches_existing": True, "saved_starts_match_regeneration": True})


SPLITS = [(0, x + .5) for x in range(7)] + [(1, x) for x in (.025, .1, .25, .5, .75, .9, .975)]


def fit_tree(X, C, depth, use_phi):
    sums = C.sum(axis=0)
    arm = int(np.argmin(sums))
    node = {"arm": arm, "n": len(X), "cost_sum": float(sums[arm])}
    if depth == 0:
        return node
    best, score = None, float(sums[arm])
    for col, threshold in SPLITS:
        if col == 1 and not use_phi:
            continue
        left = X[:, col] <= threshold
        if min(left.sum(), (~left).sum()) < 20:
            continue
        val = C[left].sum(axis=0).min() + C[~left].sum(axis=0).min()
        if val < score - 1e-9:
            best, score = (col, threshold, left), float(val)
    if best is not None:
        col, threshold, left = best
        node.update({"feature": ["d", "phi"][col], "col": col, "threshold": threshold,
                     "left": fit_tree(X[left], C[left], depth-1, use_phi),
                     "right": fit_tree(X[~left], C[~left], depth-1, use_phi)})
    return node


def predict_tree(node, x):
    if "col" not in node:
        return node["arm"]
    branch = "left" if x[node["col"]] <= node["threshold"] else "right"
    return predict_tree(node[branch], x)


def group_and_fold(cid):
    c = cid.upper()
    contest = "AIME" if c.startswith("AIME") else "HMMT" if c.startswith("HMMT") else "JMO" if c.startswith("JMO") else "OTHER"
    year = re.search(r"(?:19|20)\d{2}", c)
    group = f"{contest}-{year[0]}" if year else cid
    fold = int(hashlib.sha256(("astra-I|" + group).encode()).hexdigest()[:8], 16) % 5
    return group, fold


def config_analysis():
    data = load_csv(ROOT / "jssa/results/search-mode-ablation/per-run.csv")
    feat = {r["id"]: r for r in load_csv(HERE / "features.csv")}
    profile = load_csv(ROOT / "jssa/results/stage-profile-20261023/per-case.csv")
    ids = sorted({r["case_id"] for r in data})
    index = {(r["case_id"], r["search_mode"]): r for r in data}
    assert len(index) == len(data) == 969 and len(ids) == 323
    X = np.array([[float(feat[c]["d"]), float(feat[c]["phi"])] for c in ids])
    folds = np.array([group_and_fold(c)[1] for c in ids])
    feature_s = np.array([float(feat[c]["feature_seconds"]) for c in ids])
    build_s = np.array([float(feat[c]["build_seconds"]) for c in ids])
    variable = X[:, 0] > 0
    result, models, rows = {}, {}, []
    for portfolio, modes in [("two", ["disco_mads", "scipy_multistart"]),
                             ("three", ["disco_mads", "scipy_multistart", "mads"])]:
        C = np.array([[float(index[c, a]["wall_seconds"]) if index[c, a]["solved"] == "True"
                       and float(index[c, a]["wall_seconds"]) <= 180 else 180.0 for a in modes] for c in ids])
        correct = np.array([[index[c, a]["solved"] == "True" and float(index[c, a]["wall_seconds"]) <= 180 for a in modes] for c in ids])
        choice = {a: np.full(len(ids), j, dtype=int) for j, a in enumerate(modes)}
        choice.update({"sbs_train": np.zeros(len(ids), dtype=int), "tree_d": np.zeros(len(ids), dtype=int),
                       "tree_d_phi": np.zeros(len(ids), dtype=int), "oracle": np.argmin(C, axis=1)})
        models[portfolio] = {"modes": modes, "folds": {}}
        for fold in range(5):
            train, test = folds != fold, folds == fold
            choice["sbs_train"][test] = int(np.argmin(C[train].sum(axis=0)))
            fm = {"n_train": int(train.sum()), "n_test": int(test.sum()),
                  "uniform": modes[int(choice["sbs_train"][test][0])]}
            for method, use_phi in [("tree_d", False), ("tree_d_phi", True)]:
                # d=0 takes the default without diagnostics in both train and test.
                tree = fit_tree(X[train & variable], C[train & variable], 2, use_phi)
                for i in np.flatnonzero(test & variable):
                    choice[method][i] = predict_tree(tree, X[i])
                fm[method] = tree
            models[portfolio]["folds"][str(fold)] = fm
        models[portfolio]["full_tree_d_phi_descriptive_only"] = fit_tree(X[variable], C[variable], 2, True)
        out = {"n": len(ids), "fold_counts": dict(Counter(map(int, folds))),
               "groups": len({group_and_fold(c)[0] for c in ids}), "methods": {}}
        for method, pred in choice.items():
            costs = C[np.arange(len(ids)), pred]
            hits = correct[np.arange(len(ids)), pred]
            ref = C[:, 0]
            overhead = feature_s if method == "tree_d_phi" else np.zeros(len(ids))
            build = build_s if method == "tree_d_phi" else np.zeros(len(ids))
            out["methods"][method] = {
                "mean_C": float(costs.mean()), "correct": int(hits.sum()),
                "choice_counts": dict(Counter(modes[j] for j in pred)),
                "difference_vs_default_free": mean_ci(costs-ref),
                "mean_C_feature_x1": float((costs+overhead).mean()),
                "mean_C_feature_x4": float((costs+4*overhead).mean()),
                "mean_C_feature_and_build_x1": float((costs+overhead+build).mean()),
                "difference_vs_default_feature_x1": mean_ci(costs+overhead-ref),
                "difference_vs_train_best_fixed_free": mean_ci(costs-C[np.arange(len(ids)), choice["sbs_train"]]),
                "difference_vs_train_best_fixed_feature_x1": mean_ci(costs+overhead-C[np.arange(len(ids)), choice["sbs_train"]]),
                "gained_vs_default": int((hits & ~correct[:, 0]).sum()),
                "lost_vs_default": int((~hits & correct[:, 0]).sum()),
                "overhead_note": "diagnostic-feature accounting sensitivity, not a fresh 180s end-to-end replay"}
            for i, cid in enumerate(ids):
                rows.append({"portfolio": portfolio, "method": method, "id": cid,
                             "group": group_and_fold(cid)[0], "fold": int(folds[i]),
                             "d": int(X[i, 0]), "phi": X[i, 1], "choice": modes[pred[i]],
                             "C": costs[i], "correct": bool(hits[i]), "C_default": ref[i],
                             "feature_seconds": overhead[i], "build_seconds": build[i],
                             "C_plus_feature": costs[i]+overhead[i]})
        a, b = choice["tree_d_phi"], choice["tree_d"]
        out["phi_increment"] = mean_ci(C[np.arange(len(ids)), a] + feature_s - C[np.arange(len(ids)), b])
        result[portfolio] = out
    write_csv("config-oof.csv", rows)
    write_json("config-models.json", models)
    # Pilot overhead versus existing complete default solver, purely descriptive.
    by_id = {}
    for row in profile:
        t = float(row["wall_time_s"])
        cost = t if row["correct"] == "True" and t <= 180 else 180
        by_id.setdefault(row["case_id"], []).append(cost)
    pilot_rows = []
    for cid in ids:
        f = feat[cid]
        if int(f["d"]) == 0:
            continue
        full = sum(by_id[cid]) / len(by_id[cid])
        low, est = float(f["pilot20_seconds_low"]), float(f["pilot20_seconds_allocated"])
        pilot_rows.append({"id": cid, "pilot_n": int(f["pilot20_n"]), "pilot_sec_lower": low,
                           "pilot_sec_allocated": est, "default_C_3seed": full,
                           "ratio_lower": low/full, "ratio_allocated": est/full})
    write_csv("pilot-cost-vs-default.csv", pilot_rows)
    result["pilot_cost_vs_default_different_campaigns"] = {
        "n": len(pilot_rows), "fewer_than20": sum(r["pilot_n"] < 20 for r in pilot_rows),
        "pilot_sec_lower": quantiles([r["pilot_sec_lower"] for r in pilot_rows]),
        "ratio_lower": quantiles([r["ratio_lower"] for r in pilot_rows]),
        "pilot_lower_gt_default": sum(r["ratio_lower"] > 1 for r in pilot_rows),
        "pilot_lower_gt_10pct_default": sum(r["ratio_lower"] > .1 for r in pilot_rows)}
    result["feature_timing"] = {"feature_seconds": quantiles(feature_s[variable]),
                                "build_seconds": quantiles(build_s[variable])}
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure-features", action="store_true")
    args = ap.parse_args()
    start = time.perf_counter()
    if args.measure_features:
        measure_features()
    if not (HERE / "features.csv").exists():
        raise SystemExit("Run --measure-features first (hard-feasibility evaluation only; no local optimization).")
    local = local_analysis()
    config = config_analysis()
    cloud = ROOT / "jssa/difficulty/full-solver-redraw-cloud/out/A"
    write_json("summary.json", {"local": local, "configuration": config,
               "cloud_out_A": "exists_read_only" if cloud.exists() else "見つからない",
               "new_local_search_runs": 0})
    write_json("provenance.json", {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.executable, "analysis_wall_seconds": time.perf_counter()-start,
        "new_local_search_runs": 0, "threads": 1, "bootstrap_seed": SEED, "bootstrap_repetitions": BOOT,
        "input_sha256": INPUTS, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "plan_sha256": hashlib.sha256((HERE / "analysis-plan.md").read_bytes()).hexdigest()})
    print(json.dumps(clean_json({"local_coverage": local["coverage"],
                    "local_pilot_vs_feasible": local["subsets"]["all150"]["pilot_vs_feasible"],
                    "config_two": config["two"]["methods"],
                    "analysis_seconds": time.perf_counter()-start}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
