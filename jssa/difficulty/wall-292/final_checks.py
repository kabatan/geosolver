"""Audit recovery provenance and fixed-criterion sensitivity; no new solves."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

import analyze

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARMS = ("B", "N", "G2")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    out = {r["k"]: r for r in rows}
    assert len(out) == len(rows), path
    return out


def main():
    manifest = json.loads((HERE / "manifest.json").read_text())
    plan = json.loads((HERE / "recovery-plan.json").read_text())
    recovery = json.loads((HERE / "recovery-summary.json").read_text())
    v2 = json.loads((HERE / "recovery-v2-freeze.json").read_text())
    summary = json.loads((HERE / "summary.json").read_text())
    table = list(csv.DictReader((HERE / "per-problem.csv").open()))
    by_plan = {r["id"]: r for r in plan["cases"]}
    assert digest(HERE / "resume_v2.py") == v2["code_sha256"]
    assert digest(HERE / "resume.py") == v2["prior_code_sha256"]
    assert digest(HERE / "recovery-plan.json") == v2["plan_sha256"]
    assert digest(HERE / "recovery-protocol.md") == plan["protocol_sha256"]
    counts, origins, calls = Counter(), Counter(), Counter()
    errors, timeouts, error_tags = Counter(), Counter(), Counter()
    all_arm_counts = Counter()
    stop_differences = []
    old_means = []
    for meta in manifest["problems"]:
        cid = meta["id"]
        p = HERE / "records" / (cid + ".jsonl")
        backup = HERE / "completed-records" / p.name
        assert digest(p) == digest(backup), cid
        counts["matching_complete_backups"] += 1
        rows = load_rows(p)
        pl = by_plan[cid]
        assert len(rows) == meta["n"]
        if not pl["missing_k"]:
            assert digest(p) == pl["prefix_sha256"], cid
            counts["retained_rows_verified"] += len(rows)
        elif pl["retained_k"]:
            prior = HERE / "initial-prefixes" / p.name
            assert digest(prior) == pl["prefix_sha256"], cid
            saved = load_rows(prior)
            for k in pl["retained_k"]:
                assert saved[k] == rows[k], (cid, k)
                counts["retained_rows_verified"] += 1
        for k in pl["missing_k"]:
            origin = rows[k].get("recovery_origin")
            assert origin in ("missing_initial_log", "continuation_after_exit"), (cid, k, origin)
            origins[origin] += 1
        q = HERE / "resume-state" / (cid + ".json")
        if q.exists():
            state = json.loads(q.read_text())
            assert state.get("partial") is None and state.get("active_arm") is None, cid
            calls.update(state["new_calls"])
        raw = json.loads((ROOT / "jssa/difficulty/minima/raw-323" / (cid + ".json")).read_text())
        old_means.append(sum(r["cls"] == "hit" for r in raw["records"]) / meta["n"])
        for r in rows.values():
            counts["starts"] += 1
            counts["start_F_unknown"] += r["F"] is None
            counts["same_error_start_all_primary_arms"] += all(r[a]["cls"] == "error" for a in ARMS)
            for a in (*ARMS, "S"):
                if a not in r:
                    continue
                out = r[a]
                all_arm_counts[a] += 1
                counts[a + "_timed"] += "seconds" in out
                counts[a + "_wrong_answer_value_missing"] += out["cls"] == "wrong_answer" and out.get("ans") is None
                if out["cls"] == "error":
                    errors[(cid, a)] += 1
                    error_tags[(a, "|".join(out.get("tags", [])))] += 1
                if out["cls"] == "timeout":
                    timeouts[(cid, a)] += 1
            if "S" in r and r["B"]["cls"] != r["S"]["cls"]:
                stop_differences.append({"id": cid, "k": r["k"], "F": r["F"],
                    **{a: r[a]["cls"] for a in ("B", "N", "S")},
                    **{a + "_raw_info": r[a]["native"]["raw_info"] for a in ("B", "S")}})
    assert counts["starts"] == 55097
    assert counts["retained_rows_verified"] == recovery["counts"]["retained_initial_rows"]
    assert sum(origins.values()) == recovery["counts"]["continuation_rows"]
    assert dict(calls) == recovery["new_call_start_records"]
    assert sum(calls.values()) == sum(r["new_calls_planned"] for r in plan["cases"])
    assert all_arm_counts == Counter(B=55097, N=55097, G2=55097, S=3729)

    # Replace only the 127 initial summaries, never choose by better outcomes.
    mixed = []
    for row in table:
        rr = dict(row)
        cid = row["id"]
        initial = by_plan[cid]["initial_summary"]
        n = int(row["n"])
        for a in ARMS:
            cc = (initial["counts"][a] if initial is not None else
                  {cl: int(row[a + "_" + cl]) for cl in ("hit", "wrong_branch", "wrong_answer")})
            rr["p_" + a] = cc.get("hit", 0) / n
            rr[a + "_wrong"] = cc.get("wrong_branch", 0) + cc.get("wrong_answer", 0)
        rr["delta"] = rr["p_N"] - rr["p_B"]
        rr["bad"] = rr["delta"] <= -.05 + 1e-12
        rr["wrong_increase"] = rr["N_wrong"] > rr["B_wrong"]
        mixed.append(rr)
    sensitivity = copy.deepcopy(summary)
    sensitivity["means"] = {a: float(np.mean([r["p_" + a] for r in mixed])) for a in ARMS}
    sensitivity["delta_N"] = analyze.average_ci([r["delta"] for r in mixed])
    sensitivity["delta_G2"] = analyze.average_ci([r["p_G2"] - r["p_B"] for r in mixed])
    sensitivity["delta_counts"]["ge_0.10"] = sum(r["delta"] >= .10 - 1e-12 for r in mixed)
    bad = [r for r in mixed if r["bad"]]
    sensitivity["risk"] = {"bad_n": len(bad), "bad_fraction": len(bad)/len(mixed),
                           "bad_wrong_increase": sum(r["wrong_increase"] for r in bad)}
    for R in ("True", "False"):
        rr = [r for r in mixed if r["risk"] == R]
        nb = sum(r["bad"] for r in rr)
        sensitivity["risk"][R] = {"n": len(rr), "bad_n": nb, "rate": nb/len(rr)}
    for kind in ("phi", "phi_independent", "human"):
        rr = [r for r in mixed if r[kind] != ""]
        for a in ARMS:
            sensitivity["correlations"][kind][a] = {
                "spearman": analyze.rho([float(r[kind]) for r in rr], [r["p_"+a] for r in rr]),
                "partial_nvars": analyze.partial([float(r[kind]) for r in rr], [r["p_"+a] for r in rr], [int(r["n_vars"]) for r in rr])}
    sensitivity["ratio_G2"] = sensitivity["delta_G2"]["mean"] / sensitivity["delta_N"]["mean"] if sensitivity["delta_N"]["mean"] > 0 else None
    pv = {k: v for k, v in analyze.verdicts(sensitivity).items() if k.startswith("P")}
    primary = {k: v for k, v in summary["verdicts"].items() if k.startswith("P")}
    sensitivity_out = {"rule": "127 initial aggregate summaries plus final rows for remaining 165; P1-P5 only",
        "initial_cases": 127, "classification_mismatches": [r for r in recovery["comparisons"] if not r["counts_match"]],
        "means": sensitivity["means"], "delta_N": sensitivity["delta_N"], "delta_G2": sensitivity["delta_G2"],
        "risk": sensitivity["risk"], "correlations": sensitivity["correlations"], "ratio_G2": sensitivity["ratio_G2"],
        "primary_verdicts": primary, "initial_aggregate_mixture_verdicts": pv,
        "verdicts_match": pv == primary, "M1_initial_lost_traces_unrecoverable": True}
    analyze.write_json(HERE / "recovery-sensitivity.json", sensitivity_out)
    out = {"counts": dict(counts), "recovery_origins": dict(origins), "new_calls": dict(calls),
           "arm_counts": dict(all_arm_counts), "recovery_code_and_plan_hashes_unchanged": True,
           "errors_by_problem_arm": [{"id": k[0], "arm": k[1], "n": v} for k,v in sorted(errors.items())],
           "error_tags": [{"arm": k[0], "tags": k[1], "n": v} for k,v in sorted(error_tags.items())],
           "timeouts_by_problem_arm": [{"id": k[0], "arm": k[1], "n": v} for k,v in sorted(timeouts.items())],
           "B_S_class_differences": stop_differences,
           "old_B_problem_mean_reference": float(np.mean(old_means)),
           "N_minus_old_B_reference": summary["means"]["N"] - float(np.mean(old_means))}
    analyze.write_json(HERE / "final-checks.json", out)
    print(json.dumps({"checks": "passed", "retained_rows_verified": counts["retained_rows_verified"],
                      "primary_calls": sum(all_arm_counts[a] for a in ARMS), "S_calls": all_arm_counts["S"],
                      "initial_aggregate_P1_P5_match": pv == primary}))


if __name__ == "__main__":
    main()
