"""Analysis only: verify native traces and score the fixed R1--R5 criteria."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter

import numpy as np

from common import HERE, ROOT, write_json
from mechanism import ARMS


def equal_x(a, b):
    return a.get("x") == b.get("x")


def csv_write(path, rows):
    with path.open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def main():
    old = json.loads((HERE / "intervention.json").read_text())
    cases = [json.loads((HERE / "mechanism-data" / f"{c['id']}.json").read_text()) for c in old]
    assert len(cases) == 14 and all(len(c["records"]) == 80 for c in cases)
    old_by_id = {c["id"]: {r["k"]: r for r in c["records"]} for c in old}
    mismatch, trace_issues, call_issues, same_x, records = [], [], [], [], []
    for c in cases:
        for r in c["records"]:
            prev = old_by_id[c["id"]][r["k"]]
            assert r["start"] == prev["start"] and r["F"] == prev["F"]
            for arm, old_arm in [("B", "baseline"), ("N", "no_hard")]:
                for field in ["cls", "x", "res", "hard", "ans"]:
                    if r[arm].get(field) != prev[old_arm].get(field):
                        mismatch.append({"id": c["id"], "k": r["k"], "arm": arm, "field": field,
                                         "old": prev[old_arm].get(field), "new": r[arm].get(field)})
                if r[arm]["optimizer"].get("status") != prev[old_arm]["optimizer"].get("status"):
                    mismatch.append({"id": c["id"], "k": r["k"], "arm": arm, "field": "status"})
            for arm in ARMS:
                n = r[arm]["native"]
                if n["issues"]:
                    trace_issues.append({"id": c["id"], "k": r["k"], "arm": arm, "issues": n["issues"]})
                if n["native_nfev"] is not None:
                    if n["fun_calls_including_preflight"] != n["native_nfev"] + 1 or n["jac_calls_including_preflight"] != n["native_njev"]:
                        call_issues.append({"id": c["id"], "k": r["k"], "arm": arm})
                    # Native has one initial function call and a wrapper preflight.
                    n_missing = n["native_nfev"] - 1 - sum(n["counts"].values())
                    if n_missing:
                        call_issues.append({"id": c["id"], "k": r["k"], "arm": arm, "missing_trials": n_missing})
                    n_same = n.get("same_coordinate_unknown", 0)
                    if n_same:
                        same_x.append({"id": c["id"], "k": r["k"], "arm": arm, "count": n_same})
            records.append({"id": c["id"], "wall_group": c["wall_group"], **r})

    summary_rows, status_rows = [], []
    for c in cases:
        for F in (True, False):
            group = [r for r in c["records"] if r["F"] == F]
            row = {"id": c["id"], "stratum": "F" if F else "I", "n": len(group), "wall_group": c["wall_group"]}
            for arm in ARMS:
                row[arm] = sum(r[arm]["cls"] == "hit" for r in group)
                counter = Counter((r[arm]["cls"], str(r[arm]["optimizer"].get("status")),
                                   str(r[arm]["native"]["raw_info"])) for r in group)
                for (cls, status, raw), n in sorted(counter.items()):
                    status_rows.append({"id": c["id"], "stratum": row["stratum"], "arm": arm,
                                        "cls": cls, "scipy_status": status, "raw_info": raw, "n": n})
            row["B_fail"] = sum(r["B"]["cls"] != "hit" for r in group)
            row["B_fail_cross_descent_reject"] = sum(r["B"]["cls"] != "hit" and r["B"]["native"]["F_to_I_eq_descent_rejected"] > 0 for r in group)
            row["B_fail_cross_descent_reject_hard"] = sum(r["B"]["cls"] != "hit" and r["B"]["native"]["F_to_I_eq_descent_rejected_hard_increase"] > 0 for r in group)
            row["B_fail_cross_other_descent_reject"] = sum(r["B"]["cls"] != "hit" and r["B"]["native"]["F_to_I_eq_descent_rejected_other_ss_decrease"] > 0 for r in group)
            row["B_fail_raw_jac_gt_1e8"] = sum(r["B"]["cls"] != "hit" and r["B"]["native"]["hard_jac_raw_max"] > 1e8 for r in group)
            row["S_rescued"] = sum(r["B"]["cls"] != "hit" and r["S"]["cls"] == "hit" for r in group)
            row["J_rescued"] = sum(r["B"]["cls"] != "hit" and r["J"]["cls"] == "hit" for r in group)
            row["N_rescued"] = sum(r["B"]["cls"] != "hit" and r["N"]["cls"] == "hit" for r in group)
            row["N_lost"] = sum(r["B"]["cls"] == "hit" and r["N"]["cls"] != "hit" for r in group)
            summary_rows.append(row)
    csv_write(HERE / "mechanism-summary.csv", summary_rows)
    csv_write(HERE / "mechanism-status.csv", status_rows)
    a = next(r for r in summary_rows if r["id"] == "AIME-2010-II-14" and r["stratum"] == "F")
    rescued_wall = [r for r in records if r["wall_group"] and r["F"] and r["B"]["cls"] != "hit" and r["N"]["cls"] == "hit"]
    const_lost = [r for r in records if r["N"]["cls"] == "hit" and r["C"]["cls"] != "hit"]
    r4 = sum(r["S"]["cls"] == "hit" for r in rescued_wall)
    r5 = sum(r["CS"]["cls"] == "hit" for r in const_lost)
    summary = {
        "runs": len(records)*len(ARMS), "pairs": len(records), "source_mismatches": mismatch,
        "trace_issues": trace_issues, "native_call_count_issues": call_issues,
        "same_coordinate_trials_unknown": same_x,
        "R1": {"S_minus_B": (a["S"]-a["B"])/a["n"], "N_minus_B": (a["N"]-a["B"])/a["n"],
               "pass": abs(a["S"]-a["B"]) <= .1*a["n"] and a["N"]-a["B"] >= .5*a["n"]},
        "R2": {"n": a["B_fail_cross_descent_reject"], "denominator": a["B_fail"],
               "pass": a["B_fail_cross_descent_reject"] >= .8*a["B_fail"]},
        "R3": {"J_minus_B": (a["J"]-a["B"])/a["n"], "pass": a["J"]-a["B"] >= .2*a["n"]},
        "R4": {"n": r4, "denominator": len(rescued_wall), "pass": r4 >= .5*len(rescued_wall)},
        "R5": {"n": r5, "denominator": len(const_lost), "pass": r5 >= .5*len(const_lost) if const_lost else None},
        "class_totals": {arm: dict(Counter(r[arm]["cls"] for r in records)) for arm in ARMS},
        "raw_status_totals": {arm: dict(Counter(str(r[arm]["native"]["raw_info"]) for r in records)) for arm in ARMS},
        "B_S_same_x": sum(equal_x(r["B"], r["S"]) for r in records),
        "B_S_same_class": sum(r["B"]["cls"] == r["S"]["cls"] for r in records),
        "B_S_status_changed": sum(r["B"]["optimizer"].get("status") != r["S"]["optimizer"].get("status") for r in records),
        "B_S_nfev_changed": sum(r["B"]["optimizer"].get("nfev") != r["S"]["optimizer"].get("nfev") for r in records),
        "B_S_class_changes": [{"id": r["id"], "k": r["k"], "F": r["F"], "B": r["B"]["cls"], "S": r["S"]["cls"]} for r in records if r["B"]["cls"] != r["S"]["cls"]],
        "const_lost_C_raw_status": dict(Counter(str(r["C"]["native"]["raw_info"]) for r in const_lost)),
        "const_lost_CS_raw_status": dict(Counter(str(r["CS"]["native"]["raw_info"]) for r in const_lost)),
        "const_lost_eq_norm_median": float(np.median([r["C"].get("res", np.nan) for r in const_lost])),
        "solver_seconds_including_trace": sum(r[a]["seconds"] for r in records for a in ARMS),
        "nonfinite_error_all_sentinel": {arm: sum(r[arm]["cls"] == "error" and r[arm]["optimizer"].get("optimality") == 0 for r in records) for arm in ARMS},
    }
    # Failure mechanisms are problem-stratified; do not pool outcomes as independent problems.
    summary["wall_F"] = {arm: {"hit": sum(r[arm]["cls"] == "hit" for r in records if r["wall_group"] and r["F"]),
                                        "n": sum(r["wall_group"] and r["F"] for r in records)} for arm in ARMS}
    summary["aime"] = {}
    for F in (True, False):
        group = [r for r in records if r["id"] == "AIME-2010-II-14" and r["F"] == F]
        summary["aime"]["F" if F else "I"] = {
            arm: {"hit": sum(r[arm]["cls"] == "hit" for r in group),
                  "status": dict(Counter(str(r[arm]["optimizer"]["status"]) for r in group)),
                  "raw_info": dict(Counter(str(r[arm]["native"]["raw_info"]) for r in group)),
                  "accepted_I_runs": sum(r[arm]["native"]["accepted_I"] > 0 for r in group),
                  "fail_accepted_all_F": sum(r[arm]["cls"] != "hit" and r[arm]["native"]["accepted_all_F"] for r in group),
                  "hit_accepted_I_runs": sum(r[arm]["cls"] == "hit" and r[arm]["native"]["accepted_I"] > 0 for r in group)} for arm in ARMS}
    write_json(HERE / "mechanism-summary.json", summary)

    traces = json.loads((HERE / "native-aime-traces.json").read_text())["records"]
    tail_rows, trace_rows = [], []
    for rec in traces:
        for arm in ARMS:
            n = rec[arm]["native"]
            trace_rows.append({"k": rec["k"], "arm": arm, "cls": rec[arm]["cls"],
                               "status": rec[arm]["optimizer"]["status"], "raw_info": n["raw_info"],
                               "res": rec[arm].get("res"), "accepted": n["counts"].get("accepted", 0),
                               "rejected": n["counts"].get("rejected", 0),
                               "F_to_I_eq_descent_rejected": n["F_to_I_eq_descent_rejected"],
                               "hard_jac_max": n["hard_jac_raw_max"]})
            for t in n["tail"]:
                tail_rows.append({"k": rec["k"], "arm": arm, "trial": t["index"], "decision": t["decision"],
                                  "base_F": t["base"]["F"], "trial_F": t["F"],
                                  "base_eq_ss": t["base"]["eq_ss"], "trial_eq_ss": t["eq_ss"],
                                  "base_hard": t["base"]["hard"], "trial_hard": t["hard"],
                                  "step_scaled": t["step_scaled"], "x": json.dumps(t["x"])})
    csv_write(HERE / "native-aime-summary.csv", trace_rows)
    csv_write(HERE / "native-last-steps.csv", tail_rows)

    # Compact per-case files: the same data, without indentation; keep each file small.
    for c in cases:
        (HERE / "mechanism-data" / f"{c['id']}.json").write_text(json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n")
    paths = [HERE / "preregistration-resume.md", HERE / "mechanism.py", HERE / "summarize_mechanism.py",
             HERE / "intervention.json", HERE / "native-aime-traces.json"]
    paths += sorted((HERE / "mechanism-data").glob("*.json"))
    write_json(HERE / "mechanism-provenance.json", {
        "sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}})
    print(json.dumps({k: summary[k] for k in ["runs", "source_mismatches", "trace_issues", "native_call_count_issues", "R1", "R2", "R3", "R4", "R5", "B_S_same_x", "B_S_same_class", "B_S_status_changed", "class_totals", "const_lost_C_raw_status", "const_lost_CS_raw_status"]}, indent=2))


if __name__ == "__main__":
    main()
