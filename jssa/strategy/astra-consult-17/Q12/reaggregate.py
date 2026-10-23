"""Recount frozen CSV/JSON records, using only the Python standard library.

No optimizer, solver, DSL evaluation, candidate generation or one-step diagnostic.
All writes stay beside this script.
"""
from pathlib import Path
import csv
import hashlib
import json
from collections import Counter, defaultdict
from statistics import mean

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshots"

def rows(name):
    with (SNAP / name).open(newline="") as f:
        return list(csv.DictReader(f))

def flag(x):
    return x in ("True", "true", "1")

def num(row, key):
    return int(row.get(key) or 0)

def main():
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for f in manifest["files"]:
        assert hashlib.sha256((HERE / f["snapshot"]).read_bytes()).hexdigest() == f["sha256"]
    g = rows("G-intervention.csv")
    gw = [x for x in g if flag(x["wall_group"])]
    gn = [x for x in g if not flag(x["wall_group"])]
    gout = {"problems": len(g), "selected_wall_problems": len(gw),
            "wall_F_B_hits": sum(num(x, "F_baseline_hit") for x in gw),
            "wall_F_N_hits": sum(num(x, "F_no_hard_hit") for x in gw),
            "wall_F_denominator": 40 * len(gw),
            "wall_F_mean_delta": mean(float(x["delta_F"]) for x in gw),
            "other_F_mean_delta": mean(float(x["delta_F"]) for x in gn),
            "wall_F_improved_ge_010": sum(float(x["delta_F"]) >= .10 for x in gw),
            "wall_F_rescues": sum(num(x, "F_rescued") for x in gw),
            "wall_F_losses": sum(num(x, "F_lost") for x in gw),
            "all_F_rescues": sum(num(x, "F_rescued") for x in g),
            "all_F_losses": sum(num(x, "F_lost") for x in g),
            "all_I_rescues": sum(num(x, "I_rescued") for x in g),
            "all_I_losses": sum(num(x, "I_lost") for x in g)}
    q1 = rows("Q1-per-problem.csv")
    complete = [x for x in q1 if flag(x["complete"])]
    summary = json.loads((SNAP / "Q1-summary.json").read_text())
    q1out = {"expected_problems": len(q1), "complete_problems": len(complete),
             "complete_starts": sum(num(x, "n") for x in complete),
             "all_observed_starts": sum(num(x, "observed") for x in q1),
             "complete_methods": dict(Counter(x["method"] for x in complete)),
             "complete_pairs": {k: sum(num(x, k) for x in complete)
                                for k in ("rescue_N", "loss_N", "rescue_G2", "loss_G2", "old_disagree")},
             "not_random_sample": True}
    q1out["arms"] = {}
    classes = ("hit", "stuck", "wrong_branch", "wrong_answer", "left_box", "error", "timeout", "missing_start", "missing_run")
    for arm in ("B", "N", "G2"):
        macro = mean(num(x, arm + "_hits") / num(x, "n") for x in complete)
        assert abs(macro - summary["means"][arm]) < 1e-12
        all_counts = {c: sum(num(x, arm + "_" + c) for x in q1) for c in classes}
        complete_counts = {c: sum(num(x, arm + "_" + c) for x in complete) for c in classes}
        q1out["arms"][arm] = {"complete_macro_p": macro, "complete_counts": complete_counts,
                              "all_observed_counts": all_counts,
                              "all_counts_match_stored_summary": all(all_counts[c] == summary["class_counts_all_observed"][arm].get(c, 0) for c in classes)}
    for k in ("N", "G2"):
        deltas = [num(x, k + "_hits") / num(x, "n") - num(x, "B_hits") / num(x, "n") for x in complete]
        q1out[k + "_complete_delta"] = {"mean": mean(deltas), "positive": sum(x > 0 for x in deltas),
                                         "negative": sum(x < 0 for x in deltas), "zero": sum(x == 0 for x in deltas)}
    assert len(complete) == summary["completed_problems"]
    q4 = rows("Q4-per-case.csv")
    cand = rows("Q4-per-candidate.csv")
    eligible = [x for x in q4 if num(x, "n_candidates") > 0]
    grouped = defaultdict(list)
    for x in cand:
        grouped[(x["id"], x["variant"])].append(x)
    for x in eligible:
        for arm in ("O", "S", "D", "R", "A"):
            assert sum(num(c, "passed") for c in grouped[(x["id"], arm)]) == num(x, arm + "_success")
            assert bool(num(x, arm + "_pass")) == any(num(c, "passed") for c in grouped[(x["id"], arm)])
    q4out = {"all_problems": len(q4), "candidate_bearing_problems": len(eligible),
             "candidates": sum(num(x, "n_candidates") for x in q4), "runs": len(cand), "arms": {}}
    for arm in ("O", "S", "D", "R", "A"):
        q4out["arms"][arm] = {"pass_problems": sum(num(x, arm + "_pass") for x in q4),
                               "pass_candidates": sum(num(c, "passed") for c in cand if c["variant"] == arm),
                               "refine_seconds": sum(float(c["refinement_seconds"]) for c in cand if c["variant"] == arm)}
    for v in (True, False):
        sub = [x for x in eligible if flag(x["q_active"]) == v]
        stalled = [x for x in sub if flag(x["O_stall"])]
        q4out["qactive" if v else "non_qactive"] = {"n": len(sub), "O_stall": len(stalled),
                                                    "S_rescued_stall": sum(num(x, "S_pass") for x in stalled)}
    q4out["A_case_losses_at_80_digits"] = sum(num(x, "O_pass") and not num(x, "A_pass") for x in eligible)
    q6 = rows("Q6-per-problem.csv")
    box = Counter()
    for x in q6:
        box.update(json.loads(x["F_left_box_without_box"]))
    q6out = {"problems": len(q6), "starts": sum(num(x, "n") for x in q6),
             "classification_mismatches": sum(num(x, "classification_mismatches") for x in q6),
             "F_left_box_without_box": dict(box), "main_examples": {}}
    for ident in ("HMMT-2007-FEB-GEO-04", "AIME-2021-II-14", "JMO-2017-PRE-01"):
        x = next(x for x in q6 if x["id"] == ident)
        q6out["main_examples"][ident] = {k: (json.loads(x[k]) if k.endswith(("original", "normalized", "without_box")) and x[k] else x[k])
            for k in ("method", "F_n", "I_n", "F_original", "I_original", "F_without_box", "I_without_box", "F_normalized", "I_normalized")}
    out = {"source_capture_utc": manifest["captured_utc"],
           "scope": "Arithmetic checks on frozen aggregate/individual-candidate records; no raw optimizer replay.",
           "G": gout, "Q1": q1out, "Q4": q4out, "Q6": q6out}
    (HERE / "reaggregate.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
