"""Exploratory, endpoint-only restart replay. No solver execution or imports."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import platform
import statistics
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
GRID = (8, 16, 32, 64, 128, math.inf)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return "inf" if obj > 0 else "-inf" if obj < 0 else None
    if isinstance(obj, dict):
        return {str(k): safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [safe(x) for x in obj]
    return obj


def write_json(name, obj):
    (HERE / name).write_text(json.dumps(safe(obj), ensure_ascii=False, indent=2) + "\n")


def write_csv(name, rows):
    if not rows:
        return
    with (HERE / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(safe(v)) if isinstance(v, (list, dict)) else safe(v)
                        for k, v in row.items()})


def dist(records, branches, budget, overhead):
    n = len(records)
    assert n > 0
    counts = [0] * branches
    work = 0
    for r in records:
        t = r["nfev"]
        assert isinstance(t, int) and t >= 0
        work += min(t, budget) + overhead
        if r["cls"] == "hit" and t <= budget:
            j = r["ref"]
            assert 0 <= j < branches
            counts[j] += 1
    return work / n, [x / n for x in counts], counts


def first(c, p):
    return c / sum(p) if sum(p) > 0 else math.inf


def dynamic(distributions, fixed=None, policy=None):
    """V(S) by first-step renewal, allowing state-dependent cutoffs."""
    m = len(distributions[0][1])
    values = [0.0] + [math.inf] * ((1 << m) - 1)
    choices = [len(distributions) - 1] * (1 << m)
    for mask in range(1, 1 << m):
        best = math.inf
        choice = len(distributions) - 1
        options = ([fixed] if fixed is not None else
                   [policy[mask]] if policy is not None else
                   list(reversed(range(len(distributions)))))
        for a in options:
            c, p, _ = distributions[a]
            indices = [j for j in range(m) if mask & (1 << j) and p[j] > 0]
            q = sum(p[j] for j in indices)
            v = ((c + sum(p[j] * values[mask ^ (1 << j)] for j in indices)) / q
                 if q > 0 else math.inf)
            if v < best:
                best, choice = v, a
        values[mask], choices[mask] = best, choice
    return values[-1], choices, values


def ratio(a, b):
    if math.isfinite(b) and b > 0:
        return a / b
    return None


def all_closed(c, p):
    """Independent inclusion-exclusion check for a fixed cutoff."""
    if any(x == 0 for x in p):
        return math.inf
    total = 0.0
    for k in range(1, len(p) + 1):
        for sub in itertools.combinations(p, k):
            total += (-1) ** (k + 1) / sum(sub)
    return c * total


def argmin_long_tie(values):
    return min(reversed(range(len(values))), key=lambda a: values[a])


def theory():
    rows = []
    for eps, duration in [(Fraction(1, 10), 100), (Fraction(1, 100), 1000)]:
        a, b = 1 - eps, eps
        c = a + b * duration
        ef_short, ef_long = 1 / a, c
        ea_long = c * (1 / a + 1 / b - 1)
        # 1/2 of trials use short cutoff, 1/2 long cutoff.
        cm, pa, pb = (1 + c) / 2, a, b / 2
        ea_mix = cm * (1 / pa + 1 / pb - 1 / (pa + pb))
        rows.append({"epsilon": str(eps), "slow_duration": duration,
                     "short_first_exact": str(ef_short), "short_all": "inf",
                     "long_first_exact": str(ef_long), "long_all_exact": str(ea_long),
                     "mixed_all_exact": str(ea_mix),
                     "short_first": float(ef_short), "long_first": float(ef_long),
                     "long_all": float(ea_long), "mixed_all": float(ea_mix)})
        assert ef_short < ef_long
    # Equal-probability two coupon check, unit duration.
    assert dynamic([(1.0, [.5, .5], [1, 1])], fixed=0)[0] == 3.0
    return rows


def main():
    t0 = time.monotonic()
    provenance = {}
    datasets = {}
    for seed, folder in [(0, "raw-323"), (1, "raw-323-seed1")]:
        dataset = {}
        for path in sorted((ROOT / "jssa/difficulty/minima" / folder).glob("*.json")):
            obj = json.loads(path.read_text())
            if obj.get("n_vars", 0) == 0:
                continue
            assert obj.get("seed") == seed
            assert obj.get("records")
            dataset[obj["case_id"]] = obj
            provenance[str(path.relative_to(ROOT))] = digest(path)
        datasets[seed] = dataset
    assert datasets[0].keys() == datasets[1].keys()
    details, curves, single = [], [], []
    audits = {"fixed_dp_crosschecks": 0, "max_relative_error": 0.0}
    for cid in sorted(datasets[0]):
        train, test = datasets[0][cid], datasets[1][cid]
        assert train["references"] == test["references"]
        d, m = train["n_vars"], len(train["references"])
        assert d == test["n_vars"]
        budgets = [x * (d + 1) for x in GRID]
        for overhead in [0, d + 1]:
            ds = {seed: [dist(obj["records"], m, b, overhead) for b in budgets]
                  for seed, obj in [(0, train), (1, test)]}
            ef = {seed: [first(c, p) for c, p, _ in s] for seed, s in ds.items()}
            ea = {seed: [dynamic(s, fixed=i)[0] for i in range(len(s))]
                  for seed, s in ds.items()}
            for seed in [0, 1]:
                for i, (c, p, _) in enumerate(ds[seed]):
                    independently = all_closed(c, p)
                    assert math.isfinite(independently) == math.isfinite(ea[seed][i])
                    if math.isfinite(independently):
                        err = abs(independently - ea[seed][i]) / max(1, abs(independently))
                        audits["max_relative_error"] = max(audits["max_relative_error"], err)
                        assert err < 1e-10
                    audits["fixed_dp_crosschecks"] += 1
            bf, ba = argmin_long_tie(ef[0]), argmin_long_tie(ea[0])
            train_opt, policy, _ = dynamic(ds[0])
            if not math.isfinite(train_opt):
                policy = [len(GRID) - 1] * (1 << m)
            test_opt, _, _ = dynamic(ds[1], policy=policy)
            row = dict(case_id=cid, d=d, n_refs=m, overhead=overhead,
                       n_seed0=len(train["records"]), n_seed1=len(test["records"]),
                       hits_seed0=ds[0][-1][2], hits_seed1=ds[1][-1][2],
                       complete_seed0=math.isfinite(ea[0][-1]),
                       complete_seed1=math.isfinite(ea[1][-1]),
                       first_cut_multiplier=GRID[bf], all_cut_multiplier=GRID[ba],
                       first_cut_evaluations=budgets[bf], all_cut_evaluations=budgets[ba],
                       first_baseline=ef[1][-1], first_firstcut=ef[1][bf],
                       first_ratio=ratio(ef[1][bf], ef[1][-1]),
                       all_baseline=ea[1][-1], all_firstcut=ea[1][bf],
                       all_firstcut_ratio=ratio(ea[1][bf], ea[1][-1]),
                       all_allcut=ea[1][ba], all_allcut_ratio=ratio(ea[1][ba], ea[1][-1]),
                       all_adaptive=test_opt, all_adaptive_ratio=ratio(test_opt, ea[1][-1]),
                       firstcut_hits_seed1=ds[1][bf][2],
                       adaptive_policy_multipliers={str(mask): GRID[a]
                                                    for mask, a in enumerate(policy) if mask})
            single.append(row)
            if m > 1:
                details.append(row)
                for seed in [0, 1]:
                    for i, (c, p, counts) in enumerate(ds[seed]):
                        curves.append(dict(case_id=cid, seed=seed, overhead=overhead,
                                           multiplier=GRID[i], budget=budgets[i],
                                           cost=c, probabilities=p, hits=counts,
                                           first=ef[seed][i], all=ea[seed][i]))
    multi0 = [r for r in details if r["overhead"] == 0]
    eligible = [r for r in multi0 if r["complete_seed0"] and r["complete_seed1"]]
    r1 = [r for r in eligible if r["first_ratio"] <= .8 and r["all_firstcut_ratio"] >= 2]
    r2 = [r for r in r1 if min(r["all_allcut_ratio"], r["all_adaptive_ratio"]) <= 1.1]
    finite_single = [r for r in single if r["overhead"] == 0 and r["first_ratio"] is not None]
    summary = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "status": "exploratory empirical-distribution replay, not live local searches",
        "new_local_searches": 0, "n_cases": len(datasets[0]),
        "n_records_seed0": sum(len(x["records"]) for x in datasets[0].values()),
        "n_records_seed1": sum(len(x["records"]) for x in datasets[1].values()),
        "truncated_seed0": sum(len(x["records"]) < 200 for x in datasets[0].values()),
        "truncated_seed1": sum(len(x["records"]) < 200 for x in datasets[1].values()),
        "n_multi": len(multi0), "n_multi_all_observed_both_seeds": len(eligible),
        "R1_ids": [r["case_id"] for r in r1], "R1_pass": len(r1) >= 2,
        "R2_ids": [r["case_id"] for r in r2], "R2_pass": len(r1) >= 2 and len(r2) == len(r1),
        "baseline_first_observable_cases": len(finite_single),
        "median_first_ratio": statistics.median(r["first_ratio"] for r in finite_single),
        "first_ratio_le_08_cases": sum(r["first_ratio"] <= .8 for r in finite_single),
        "first_lost_empirical_support": sum(not math.isfinite(r["first_firstcut"]) for r in finite_single),
        "audit": audits, "elapsed_sec": time.monotonic() - t0,
        "multi_no_overhead": multi0,
    }
    write_csv("all-problems.csv", single)
    write_csv("multi-value.csv", details)
    write_csv("cutoff-curves.csv", curves)
    write_json("summary.json", summary)
    write_json("theory-exact.json", theory())
    write_json("provenance.json", dict(python=platform.python_version(),
                                      inputs=provenance, script_sha256=digest(Path(__file__)),
                                      plan_sha256=digest(HERE / "analysis-plan.md")))
    print(json.dumps(safe({k: v for k, v in summary.items() if k != "multi_no_overhead"}), indent=2))
    for row in multi0:
        print(json.dumps(safe({k: row[k] for k in ["case_id", "n_seed0", "n_seed1", "first_cut_multiplier",
              "all_cut_multiplier", "first_ratio", "all_firstcut_ratio", "all_allcut_ratio", "all_adaptive_ratio",
              "firstcut_hits_seed1"]})))


if __name__ == "__main__":
    main()
