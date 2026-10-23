"""Preregistered paired hard-penalty intervention; monkeypatches only in this file."""
from __future__ import annotations

import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from common import (HERE, case_context, classify, feasible, reference_values,
                    smb, ExternalPipelineConfig, write_json)

NEGATIVE = ["AIME-2010-II-14", "HMMT-2007-FEB-GEO-06", "HMMT-2007-FEB-GEO-04",
            "HMMT-2024-FEB-GEO-01", "JMO-2017-PRE-01", "AIME-2007-I-15", "HMMT-2022-FEB-GEO-03"]
CONTROL = ["JMO-2006-PRE-02", "HMMT-2024-FEB-GEO-04", "HMMT-2008-FEB-GEO-02",
           "HMMT-2006-FEB-GEO-06", "AIME-2022-I-08", "aime-2003-2-11", "JMO-2024-PRE-03"]
SEED = 17007


def solve(bundle, ev, bounds, start, k, refs, arm, trace=False):
    old_hard = smb._evaluate_hard_feasibility_penalty
    old_vector = smb._evaluate_augmented_residual_vector
    old_ls = smb.least_squares
    trace_rows, status = [], {}

    def logged_vector(**kw):
        r = old_vector(**kw)
        x = kw["values"]
        trace_rows.append({"x": list(map(float, x)), "eq_ss": float(r[:-2] @ r[:-2]),
                           "guard_row": float(r[-2]), "hard_row": float(r[-1]),
                           "F": feasible(ev, x)})
        return r

    def logged_ls(*args, **kw):
        ans = old_ls(*args, **kw)
        status.update(status=int(ans.status), message=str(ans.message), nfev=int(ans.nfev),
                      cost=float(ans.cost), optimality=float(ans.optimality))
        return ans

    if arm == "no_hard":
        smb._evaluate_hard_feasibility_penalty = lambda **kw: 0.0
    smb.least_squares = logged_ls
    if trace:
        smb._evaluate_augmented_residual_vector = logged_vector
    telemetry = smb._SearchTelemetry()
    config = ExternalPipelineConfig.production_baseline_tier(seed=SEED, total_time_budget_sec=180.0).search
    t0 = time.monotonic()
    try:
        cand = smb._collect_local_start_record(
            bundle=bundle, evaluator=ev, bounds=bounds, config=config,
            seed=SEED, start_index=k, start=np.array(start, float),
            deadline_monotonic=t0+10.0, telemetry=telemetry)
        result = classify(ev, cand, refs)
    except (smb._SearchDeadlineExceeded, TimeoutError):
        result = {"cls": "timeout"}
    except Exception as ex:
        result = {"cls": "error", "error": repr(ex)}
    finally:
        smb._evaluate_hard_feasibility_penalty = old_hard
        smb._evaluate_augmented_residual_vector = old_vector
        smb.least_squares = old_ls
    result.update(seconds=time.monotonic()-t0, evaluations=telemetry.evaluation_count, optimizer=status)
    if trace:
        result["trace"] = trace_rows
    return result


def one_case(cid):
    t0 = time.monotonic()
    case, bundle, ev, raw, bounds, lo, width = case_context(cid)
    refs = reference_values(case["answer"])
    rng = np.random.default_rng(SEED)
    samples = []
    counts = Counter()
    for proposal in range(50000):
        x = lo + width * rng.random(len(lo))
        F = feasible(ev, x)
        if counts[F] < 40:
            samples.append((proposal, F, x))
            counts[F] += 1
        if counts[False] == counts[True] == 40:
            break
    redraw_sec = time.monotonic()-t0
    records = []
    for k, (proposal, F, x) in enumerate(samples):
        arms = ["baseline", "no_hard"] if k % 2 == 0 else ["no_hard", "baseline"]
        rec = {"k": k, "proposal": proposal, "F": F, "start": x.tolist()}
        for arm in arms:
            rec[arm] = solve(bundle, ev, bounds, x, k, refs, arm)
        records.append(rec)
    return {"id": cid, "seed": SEED, "selection": "negative" if cid in NEGATIVE else "control",
            "W": CENSUS[cid]["W"], "wall_group": cid in NEGATIVE and CENSUS[cid]["W"] >= 0.20,
            "proposals": proposal+1, "sample_F": counts[True], "sample_I": counts[False],
            "redraw_seconds": redraw_sec, "elapsed": time.monotonic()-t0, "records": records}


def main():
    global CENSUS
    CENSUS = {r["id"]: r for r in json.loads((HERE / "census.json").read_text())}
    # Keep the complete original evaluation trace for the three fixed seed-0 failures.
    case, bundle, ev, raw, bounds, lo, width = case_context("AIME-2010-II-14")
    refs = reference_values(case["answer"])
    traces = []
    for k in [2, 3, 5]:
        r = next(r for r in raw["records"] if r["k"] == k)
        rec = {"k": k, "start": r["start"], "saved": r}
        for arm in ["baseline", "no_hard"]:
            rec[arm] = solve(bundle, ev, bounds, r["start"], k, refs, arm, trace=True)
        traces.append(rec)
    write_json(HERE / "aime-traces.json", traces)
    result = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for row in pool.map(one_case, NEGATIVE+CONTROL):
            result.append(row)
            write_json(HERE / "intervention.json", result)
            print(row["id"], "wall", row["wall_group"],
                  {arm: {str(F): sum(r["F"] == F and r[arm]["cls"] == "hit" for r in row["records"])
                         for F in [True, False]} for arm in ["baseline", "no_hard"]}, flush=True)


if __name__ == "__main__":
    main()
