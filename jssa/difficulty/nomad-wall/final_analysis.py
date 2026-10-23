"""Report supplementary completion separately from the registered initial analysis."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from benchmarks import research_runner as research
from geosolver.exact import describe_exact
from aggregate_robust import read_run_outcome
from aggregate import audit_summary, write_csv
from trace_diagnostics import summarize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory = json.loads((HERE / "initial-attempt-inventory.json").read_text())
    assert all(sha(HERE / p) == h for p, h in inventory["retained_raw_sha256"].items())
    pending = [r for r in inventory["missing_slots"] if not r["solver_started"]]
    missing = []
    for row in pending:
        raw = HERE / "completion" / row["mode"] / "runs" / row["id"] / f"{row['seed']}.json"
        if raw.exists():
            continue
        audit = raw.with_suffix(".audit.jsonl")
        assert row["id"] == "aime-2003-1-7" and row["seed"] == 1 and row["mode"] == "B"
        assert audit.exists(), "do not silently turn unstarted work into a completed run"
        missing.append({"id": row["id"], "seed": row["seed"], "mode": row["mode"],
                        "reason": "supplemental_final_result_missing", "audit_sha256": sha(audit)})
        research._atomic_json(raw, {
            "schema_version": 2, "case_id": row["id"], "seed": row["seed"],
            "failure_accounting_record": True, "observed_solver_result": False,
            "solver_started": True, "failure_reason": "supplemental_final_result_missing",
            "execution_contract_issues": ["supplemental_final_result_missing"],
            "process": {"returncode": None, "timed_out": False, "elapsed_seconds": None,
                        "stdout": "", "stderr": "Only hook audit is retained; no final solver result or receipt."},
            "solver_result": None,
        })
        research._atomic_json(raw.with_suffix(".receipt.json"), {
            "case_id": row["id"], "seed": row["seed"], "mode": row["mode"], "cpu": None,
            "started_unix": None, "finished_unix": None, "recorded_unix": time.time(),
            "runner_error": "supplemental_final_result_missing", "failure_accounting_record": True,
        })
    if missing:
        research._atomic_json(HERE / "completion-missing-result.json", missing)
    cases = {r.identifier: r for r in research._load_cases()}
    expected = {i: sorted({research._canonical_json(describe_exact(v).canonical_key())
                          for ref in case.references for v in research.reference_expressions(ref)})
                for i, case in cases.items() if i in {r["id"] for r in pending}}
    supplement = []
    for row in pending:
        path = HERE / "completion" / row["mode"] / "runs" / row["id"] / f"{row['seed']}.json"
        raw = json.loads(path.read_text())
        outcome = read_run_outcome(raw)
        audit, _ = audit_summary(path.with_suffix(".audit.jsonl"))
        receipt = json.loads(path.with_suffix(".receipt.json").read_text())
        supplement.append({"id": row["id"], "seed": row["seed"], "mode": row["mode"],
            "matched": int(outcome["normal_completion"] and research._answer_keys(raw.get("solver_result")) == expected[row["id"]]),
            "status": outcome["status"], "termination_reason": outcome["termination_reason"],
            "failure_accounting_record": bool(raw.get("failure_accounting_record")),
            "wall_seconds_reference": outcome["wall_seconds"], "cpu": receipt.get("cpu"),
            "load_start": (receipt.get("load_start") or [None])[0], **audit})
    assert len(supplement) == 22
    write_csv(HERE / "completion-per-run.csv", supplement)
    primary = list(csv.DictReader((HERE / "per-run.csv").open()))
    selected = list(csv.DictReader((HERE / "selected-cases.csv").open()))
    lookup = {(r["id"], int(r["seed"]), r["mode"]): r for r in supplement}
    merged = []
    for row in primary:
        key = (row["id"], int(row["seed"]), row["mode"])
        src = lookup.get(key, row)
        merged.append({"id": row["id"], "seed": int(row["seed"]), "mode": row["mode"],
                       "matched": int(src["matched"]), "status": src["status"],
                       "post_hoc_completion": key in lookup})
    assert len(merged) == 144
    write_csv(HERE / "completion-merged-per-run.csv", merged)
    problems = []
    for row in selected:
        arms = {m: sum(r["matched"] for r in merged if r["id"] == row["id"] and r["mode"] == m)
                for m in ("B", "N")}
        problems.append({"id": row["id"], "B_correct": arms["B"], "N_correct": arms["N"],
                         "delta": (arms["N"] - arms["B"]) / 3})
    write_csv(HERE / "completion-merged-per-problem.csv", problems)
    trace_pairs = []
    total_metrics = {m: Counter() for m in ("B", "N")}
    for case in selected:
        for seed in (0, 1, 2):
            observed = {}
            for mode in ("B", "N"):
                key = (case["id"], seed, mode)
                folder = (HERE / "completion" / mode / "runs" / case["id"] if key in lookup
                          else HERE / "runs" / mode / "runs" / case["id"])
                path = folder / f"{seed}.audit.jsonl"
                es = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
                stats, evaluations, starts = summarize(es)
                observed[mode] = (stats, evaluations, starts)
                total_metrics[mode].update({
                    "hook_observed": sum(e["event"] == "installed" for e in es),
                    "nomad_reached": int(bool(starts)), "finite_evaluations": len(evaluations),
                    "hard_feasible_evaluations": sum(e["hard"] for e in evaluations),
                    "changed_payloads": stats["changed"], "changed_payload_runs": int(stats["changed"] > 0),
                })
            bs, b, bstarts = observed["B"]
            ns, n, nstarts = observed["N"]
            if not bstarts or not nstarts:
                continue
            same = all(bstarts[0][k] == nstarts[0][k] for k in ("starts", "bounds", "seeds", "scales"))
            prefix = 0
            for be, ne in zip(b, n):
                if be["x"] != ne["x"] or be["count"] != ne["count"]:
                    break
                prefix += 1
            first_change = next((e["count"] for e in n if e["changed"]), None)
            first_different = n[prefix]["count"] if prefix < min(len(b), len(n)) else None
            bv, nv = bs["best_in_box_feasible_scaled_sq"], ns["best_in_box_feasible_scaled_sq"]
            direction = ("unavailable" if bv is None or nv is None else
                         "N_lower" if nv < bv else "N_higher" if nv > bv else "equal")
            trace_pairs.append({"id": case["id"], "seed": seed, "same_initial_inputs": same,
                "N_changed": ns["changed"], "common_finite_coordinate_prefix": prefix,
                "first_changed_N_evaluation": first_change, "first_different_finite_coordinate": first_different,
                "diverged_before_changed_payload": bool(first_different is not None and
                                                       (first_change is None or first_different <= first_change)),
                "best_in_box_direction": direction,
                "B_best_in_box_feasible_scaled_sq": bv, "N_best_in_box_feasible_scaled_sq": nv})
    write_csv(HERE / "completion-merged-trace-pairs.csv", trace_pairs)
    result = {
        "analysis_status": "post_hoc completion only; original registered analysis is summary.json",
        "supplemental_slots": 22,
        "supplemental_observed_raw": sum(not r["failure_accounting_record"] for r in supplement),
        "supplemental_arms": {m: {"slots": sum(r["mode"] == m for r in supplement),
            "correct": sum(r["matched"] for r in supplement if r["mode"] == m),
            "statuses": dict(Counter(r["status"] for r in supplement if r["mode"] == m))} for m in ("B", "N")},
        "merged_arms": {m: {"slots": 72, "correct": sum(r["matched"] for r in merged if r["mode"] == m),
                            "statuses": dict(Counter(r["status"] for r in merged if r["mode"] == m)),
                            **dict(total_metrics[m])} for m in ("B", "N")},
        "merged_mean_delta": statistics.mean(p["delta"] for p in problems),
        "nonzero_problem_deltas": [p for p in problems if p["delta"]],
        "paired_nomad_traces": len(trace_pairs),
        "same_initial_inputs": sum(p["same_initial_inputs"] for p in trace_pairs),
        "changed_N_pairs": sum(p["N_changed"] > 0 for p in trace_pairs),
        "residual_directions_in_changed_pairs": dict(Counter(p["best_in_box_direction"] for p in trace_pairs if p["N_changed"])),
        "diverged_before_changed_payload": sum(p["diverged_before_changed_payload"] for p in trace_pairs),
        "original_121_raw_unchanged": True,
    }
    research._atomic_json(HERE / "completion-summary.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
