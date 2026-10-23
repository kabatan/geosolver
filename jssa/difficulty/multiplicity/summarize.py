"""Apply fixed Q4 criteria; do not fit thresholds to results."""
from collections import Counter
import csv
import json
from pathlib import Path
import statistics

import numpy as np
import experiment as e


def main():
    e.verify_lock()
    manifest = json.loads((e.HERE / "manifest.json").read_text())
    frozen = json.loads((e.HERE / "frozen-candidates.json").read_text())
    run_rows, per_case = [], []
    expected = sum(map(len, frozen.values())) * 5
    for item in manifest:
        c = dict(id=item["id"], old12=item["old12"], n_vars=item["diagnosis"]["n_vars"],
                 q_active=item["diagnosis"]["q_active"], s=item["diagnosis"]["s_applicable"],
                 d=item["diagnosis"]["d_applicable"], r=item["diagnosis"]["r_applicable"],
                 n_candidates=item["n_candidates"], missing_reason=item["missing_reason"] or "")
        for variant in e.VARIANTS:
            selected = []
            for index, candidate in enumerate(frozen[item["id"]]):
                path = e.HERE / "runs" / f"{item['id']}__{index}__{variant}.json"
                if not path.exists():
                    raise RuntimeError(f"missing scheduled output: {path.name}")
                run = json.loads(path.read_text())
                outputs = run.get("outputs", [])
                # Timeouts and exceptions are failure, as registered, even if
                # a partial output happens to satisfy the residual threshold.
                failed = bool(run["status"] != "returned" or run.get("deadline_hit") or run.get("score_error"))
                passed = bool(run["passed"] and not failed)
                digits = [o["digits"] for o in outputs if o.get("digits") is not None]
                stats = run.get("rewrite_stats", {})
                rr = dict(id=item["id"], index=index, k=candidate["k"], variant=variant,
                          q_active=c["q_active"], old12=c["old12"], status=run["status"],
                          deadline=bool(run.get("deadline_hit")), score_error=run.get("score_error") or "",
                          init_error=run.get("init_error") or "", passed=int(passed),
                          numeric_pass_before_timeout_rule=int(bool(run["passed"])),
                          best_digits=max(digits) if digits else None,
                          n_outputs=len(outputs), n_eval_failed=sum(o.get("digits") is None for o in outputs),
                          n_internal_target=sum(o["internal_status"] == "target_reached" for o in outputs),
                          n_guard_fail=sum(not o.get("guard") for o in outputs),
                          n_hard_fail=sum(not o.get("hard") for o in outputs),
                          n_bounds_fail=sum(not o.get("bounds") for o in outputs),
                          initial_guard=run.get("initial_guard"), initial_hard=run.get("initial_hard"),
                          refinement_seconds=run.get("seconds"), process_seconds=run.get("process_seconds"),
                          rewrite_calls=stats.get("calls",0), rewrite_fallbacks=stats.get("fallbacks",0),
                          last_fallback=stats.get("last_fallback") or "")
                run_rows.append(rr)
                selected.append(rr)
            c[f"{variant}_success"] = sum(x["passed"] for x in selected)
            c[f"{variant}_pass"] = int(any(x["passed"] for x in selected))
            values = [x["best_digits"] for x in selected if x["best_digits"] is not None]
            c[f"{variant}_best_digits"] = max(values) if values else None
            c[f"{variant}_deadlines"] = sum(x["deadline"] for x in selected)
            c[f"{variant}_process_failures"] = sum(x["status"] != "returned" for x in selected)
            c[f"{variant}_score_errors"] = sum(bool(x["score_error"]) for x in selected)
            c[f"{variant}_refine_seconds"] = sum(x["refinement_seconds"] or 0 for x in selected)
            c[f"{variant}_process_seconds"] = sum(x["process_seconds"] or 0 for x in selected)
            c[f"{variant}_fallback_runs"] = sum(x["rewrite_fallbacks"] > 0 for x in selected)
        c["O_stall"] = bool(c["n_candidates"] and (c["O_best_digits"] is None or c["O_best_digits"] < 50))
        per_case.append(c)
    assert len(run_rows) == expected
    e.csv_write(e.HERE / "per-candidate.csv", run_rows)
    e.csv_write(e.HERE / "per-case.csv", per_case)
    available = [c for c in per_case if c["n_candidates"]]
    q = [c for c in available if c["q_active"]]
    nonq = [c for c in available if not c["q_active"]]
    rng = np.random.default_rng(42304)
    q_vals, n_vals = np.array([c["O_stall"] for c in q], float), np.array([c["O_stall"] for c in nonq], float)
    diffs = q_vals[rng.integers(0,len(q_vals),(10000,len(q_vals)))].mean(1) - n_vals[rng.integers(0,len(n_vals),(10000,len(n_vals)))].mean(1)
    ci = np.quantile(diffs,[0.025,0.975]).tolist()
    delta = float(q_vals.mean()-n_vals.mean())
    confusion = dict(tp=sum(c["O_stall"] for c in q), fp=sum(not c["O_stall"] for c in q),
                     fn=sum(c["O_stall"] for c in nonq), tn=sum(not c["O_stall"] for c in nonq))
    precision = confusion["tp"] / len(q) if q else None
    recall = confusion["tp"] / (confusion["tp"]+confusion["fn"]) if confusion["tp"]+confusion["fn"] else None
    specificity = confusion["tn"] / (confusion["tn"]+confusion["fp"]) if confusion["tn"]+confusion["fp"] else None
    stalled_q = [c for c in q if c["O_stall"]]
    rescue_q = {v: sum(c[f"{v}_pass"] for c in stalled_q) for v in e.VARIANTS[1:]}
    d_only = [c for c in available if c["d"] and not c["s"] and not c["r"]]
    d_gain = {v: statistics.mean((c[f"{v}_success"]-c["O_success"])/c["n_candidates"] for c in d_only) for v in ("D","A")}
    aggregate = []
    for variant in e.VARIANTS:
        rr = [r for r in run_rows if r["variant"] == variant]
        time_values = [r["refinement_seconds"] for r in rr if r["refinement_seconds"] is not None]
        aggregate.append(dict(variant=variant, case_pass=sum(c[f"{variant}_pass"] for c in per_case),
                              cases=36, available=34, candidate_pass=sum(r["passed"] for r in rr), candidates=len(rr),
                              raw_residual80_cases=sum(c[f"{variant}_best_digits"] is not None and c[f"{variant}_best_digits"]>=80 for c in per_case),
                              deadlines=sum(r["deadline"] for r in rr), process_failures=sum(r["status"]!="returned" for r in rr),
                              scoring_errors=sum(bool(r["score_error"]) for r in rr),
                              mean_refine_seconds=statistics.mean(time_values), median_refine_seconds=statistics.median(time_values),
                              total_refine_seconds=sum(time_values), total_process_seconds=sum(r["process_seconds"] or 0 for r in rr),
                              mean_penalized_seconds=statistics.mean((r["refinement_seconds"] if r["passed"] else 15.0) for r in rr),
                              fallback_runs=sum(bool(r["rewrite_fallbacks"]) for r in rr)))
    e.csv_write(e.HERE / "aggregate.csv", aggregate)
    regressions = [c["id"] for c in available if c["O_pass"] and not c["A_pass"]]
    rescues = {v: [c["id"] for c in available if not c["O_pass"] and c[f"{v}_pass"]] for v in e.VARIANTS[1:]}
    gain = (sum(c["A_pass"]-c["O_pass"] for c in per_case))/36
    strata = []
    for label, cases in (("old12", [c for c in per_case if c["old12"]]),
                         ("remaining24",[c for c in per_case if not c["old12"]]),
                         ("Qactive",q),("notQactive",nonq),("D_only",d_only),
                         ("R_present",[c for c in available if c["r"]])):
        strata.append(dict(stratum=label,n=len(cases),n_with_candidates=sum(c["n_candidates"]>0 for c in cases),
                           O_stalls=sum(c["O_stall"] for c in cases), **{v:sum(c[f"{v}_pass"] for c in cases) for v in e.VARIANTS}))
    e.csv_write(e.HERE / "strata.csv", strata)
    # No-op consistency checks use output digits only when neither run timed out.
    index = {(r["id"],r["index"],r["variant"]):r for r in run_rows}
    noops=[]
    for c in available:
        for v, applicable in (("S",c["s"]),("D",c["d"]),("R",c["r"])):
            if applicable:
                continue
            for i in range(c["n_candidates"]):
                a,b=index[(c["id"],i,"O")],index[(c["id"],i,v)]
                if a["deadline"] or b["deadline"]:
                    status="censored_by_deadline"
                elif a["best_digits"] == b["best_digits"] and a["passed"]==b["passed"]:
                    status="identical"
                else:
                    status="different"
                noops.append(dict(id=c["id"],index=i,variant=v,status=status))
    e.csv_write(e.HERE / "noop-consistency.csv",noops)
    summary = dict(utc=e.now(), expected_runs=expected, actual_runs=len(run_rows), cases=len(per_case),
        candidates=sum(map(len,frozen.values())), candidate_shortfall_including_no_vars=36*3-sum(map(len,frozen.values())),
        no_variables=[c["id"] for c in per_case if c["missing_reason"]=="no_variables"],
        missing_cases=[dict(id=c["id"],reason=c["missing_reason"]) for c in per_case if c["missing_reason"]],
        P1=dict(q_n=len(q),q_stalls=sum(q_vals),nonq_n=len(nonq),nonq_stalls=sum(n_vals),difference=delta,ci95=ci,
                passed=bool(len(q)>=4 and len(nonq)>=4 and delta>=0.30 and ci[0]>0),confusion=confusion,
                precision=precision,recall=recall,balanced_accuracy=(recall+specificity)/2 if recall is not None and specificity is not None else None,
                evaluable_only_n=sum(c["O_best_digits"] is not None for c in available)),
        P2=dict(stalled_q_n=len(stalled_q),rescued=rescue_q,
                passed=bool(len(stalled_q)>=3 and rescue_q["S"]>=len(stalled_q)/2 and rescue_q["D"]<=len(stalled_q)/4 and rescue_q["R"]<=len(stalled_q)/4)),
        P3=dict(d_only_n=len(d_only),mean_fraction_gains=d_gain,passed=bool(len(d_only)>=4 and min(d_gain.values())>=0.20)),
        P4=dict(case_gain=gain,regressions=regressions,passed=bool(gain>=0.10 and len(regressions)<=1)),
        rescues=rescues,aggregate=aggregate,strata=strata,
        status_counts=dict(Counter(r["status"] for r in run_rows)),
        score_errors=dict(Counter(r["score_error"] for r in run_rows if r["score_error"])),
        noop_counts=dict(Counter(r["status"] for r in noops)),
        fallback_runs=sum(r["rewrite_fallbacks"]>0 for r in run_rows),
        fallback_evaluations=sum(r["rewrite_fallbacks"] for r in run_rows),
        timedout_numeric_passes=sum(r["numeric_pass_before_timeout_rule"] and not r["passed"] for r in run_rows))
    e.dump(e.HERE / "summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
