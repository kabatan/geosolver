"""Fixed Q14 scores; timing is descriptive under shared high load."""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks import research_runner as research
from geosolver.exact import describe_exact


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit_summary(path):
    events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    installed = [e for e in events if e["event"] == "installed"]
    starts = [e for e in events if e["event"] == "nomad_start" and e["scope"] == "disco_mads"]
    ends = [e for e in events if e["event"] == "nomad_end" and e["scope"] == "disco_mads"]
    evals = [e for e in events if e["event"] == "evaluation"]
    failures = [e for e in events if e["event"] == "evaluation_failure"]
    best_f = float("inf")
    conflicts = 0
    for e in evals:
        if e["hard"]:
            best_f = min(best_f, e["equality_sq"])
        elif e["equality_sq"] < best_f < e["original_score"]:
            conflicts += 1
    mismatches = [e for e in evals if e["preserved_record_score"] != e["original_score"]
                  or (e["mode"] == "B" and e["sent_score"] != e["original_score"])
                  or (e["mode"] == "N" and e["sent_score"] != e["equality_sq"])]
    return {
        "hook_count": len(installed), "primary_nomad_calls": len(starts),
        "primary_nomad_completed": len(ends), "finite_evaluations": len(evals),
        "failed_evaluations": len(failures),
        "hard_feasible_evaluations": sum(e["hard"] for e in evals),
        "infeasible_evaluations": sum(not e["hard"] for e in evals),
        "changed_payloads": sum(e["changed"] for e in evals),
        "score_conflicts_vs_best_feasible_seen": conflicts,
        "ledger_candidates": sum(e["ledger"] for e in ends),
        "audit_mismatches": len(mismatches),
        "nomad_exception_count": sum(e["event"] == "nomad_exception" for e in events),
    }, starts


def main():
    selected = list(csv.DictReader((HERE / "selected-cases.csv").open()))
    cases = {c.identifier: c for c in research._load_cases()}
    runs, starts_by_key = [], {}
    for selected_case in selected:
        identifier = selected_case["id"]
        case = cases[identifier]
        expected = sorted({research._canonical_json(describe_exact(value).canonical_key())
                           for ref in case.references for value in research.reference_expressions(ref)})
        for seed in (0, 1, 2):
            for mode in ("B", "N"):
                folder = HERE / "runs" / mode / "runs" / identifier
                path = folder / f"{seed}.json"
                if not path.exists():
                    continue
                raw = json.loads(path.read_text())
                outcome = research.read_run_outcome(raw)
                audit, starts = audit_summary(folder / f"{seed}.audit.jsonl")
                receipt_path = folder / f"{seed}.receipt.json"
                receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
                match = outcome["normal_completion"] and research._answer_keys(raw.get("solver_result")) == expected
                runs.append({"id": identifier, "n_vars": int(selected_case["n_vars"]),
                    "seed": seed, "mode": mode, "matched": int(match), "status": outcome["status"],
                    "termination_reason": outcome["termination_reason"],
                    "wall_seconds_reference": outcome["wall_seconds"],
                    "process_seconds_reference": outcome["process_wall_seconds"],
                    "cpu": receipt.get("cpu"),
                    "load_start": (receipt.get("load_start") or [None])[0],
                    "contract_issues": json.dumps(raw.get("execution_contract_issues", [])),
                    "runner_error": bool(receipt.get("runner_error")), **audit})
                starts_by_key[(identifier, seed, mode)] = starts
    write_csv(HERE / "per-run.csv", runs)
    indexed = {(r["id"], r["seed"], r["mode"]): r for r in runs}
    problems = []
    for row in selected:
        identifier = row["id"]
        keys = [(identifier, seed, mode) for seed in (0, 1, 2) for mode in ("B", "N")]
        if not all(key in indexed for key in keys):
            continue
        b = [indexed[identifier, seed, "B"] for seed in (0, 1, 2)]
        n = [indexed[identifier, seed, "N"] for seed in (0, 1, 2)]
        problems.append({"id": identifier, "n_vars": int(row["n_vars"]),
            "B_correct": sum(r["matched"] for r in b), "N_correct": sum(r["matched"] for r in n),
            "delta": sum(y["matched"] - x["matched"] for x, y in zip(b, n)) / 3,
            "B_nomad_reached": sum(r["primary_nomad_calls"] > 0 for r in b),
            "N_nomad_reached": sum(r["primary_nomad_calls"] > 0 for r in n),
            "N_changed_payloads": sum(r["changed_payloads"] for r in n)})
    write_csv(HERE / "per-problem.csv", problems)
    paired = []
    for row in selected:
        for seed in (0, 1, 2):
            kb, kn = (row["id"], seed, "B"), (row["id"], seed, "N")
            if kb not in indexed or kn not in indexed:
                continue
            b, n = indexed[kb], indexed[kn]
            sb, sn = starts_by_key[kb], starts_by_key[kn]
            paired.append({"id": row["id"], "seed": seed, "B_correct": b["matched"],
                "N_correct": n["matched"], "same_cpu": b["cpu"] == n["cpu"],
                "both_nomad_reached": bool(sb and sn),
                "initial_starts_equal": (sb[0]["starts"] == sn[0]["starts"] if sb and sn else None),
                "initial_scales_equal": (sb[0]["scales"] == sn[0]["scales"] if sb and sn else None),
                "initial_bounds_equal": (sb[0]["bounds"] == sn[0]["bounds"] if sb and sn else None),
                "initial_seeds_equal": (sb[0]["seeds"] == sn[0]["seeds"] if sb and sn else None)})
    write_csv(HERE / "paired-checks.csv", paired)
    final = len(runs) == 144 and len(problems) == 24
    delta = np.array([r["delta"] for r in problems])
    interval = None
    if final:
        rng = np.random.default_rng(102314)
        draws = delta[rng.integers(0, len(delta), size=(10000, len(delta)))].mean(axis=1)
        interval = np.quantile(draws, [.025, .975]).tolist()
    improved = sum(p["delta"] > 0 for p in problems)
    harmed = sum(p["delta"] < 0 for p in problems)
    arms = {}
    for mode in ("B", "N"):
        arm = [r for r in runs if r["mode"] == mode]
        arms[mode] = {"runs": len(arm), "correct": sum(r["matched"] for r in arm),
            "status_counts": dict(Counter(r["status"] for r in arm)),
            "nomad_reached": sum(r["primary_nomad_calls"] > 0 for r in arm),
            "payload_changed_runs": sum(r["changed_payloads"] > 0 for r in arm),
            **{key: sum(r[key] for r in arm) for key in (
                "finite_evaluations", "failed_evaluations", "hard_feasible_evaluations",
                "infeasible_evaluations", "changed_payloads", "score_conflicts_vs_best_feasible_seen",
                "audit_mismatches", "ledger_candidates", "nomad_exception_count")},
            "hook_missing": sum(r["hook_count"] != 1 for r in arm),
            "median_seconds_reference": statistics.median(r["wall_seconds_reference"] for r in arm) if arm else None}
    result = {"complete": final, "runs": len(runs), "complete_problems": len(problems),
        "arms": arms, "mean_delta": float(delta.mean()) if len(delta) else None,
        "problem_bootstrap_95ci": interval, "improved_problems": improved, "harmed_problems": harmed,
        "P1": bool(delta.mean() >= .10 and interval[0] > 0) if final else None,
        "P2": bool(improved >= 4 and harmed <= 2) if final else None,
        "rescued_pairs": sum(p["N_correct"] > p["B_correct"] for p in paired),
        "lost_pairs": sum(p["N_correct"] < p["B_correct"] for p in paired),
        "pair_delivery_mismatches": [p for p in paired if not p["same_cpu"] or any(
            p[key] is False for key in ("initial_starts_equal", "initial_scales_equal", "initial_bounds_equal", "initial_seeds_equal"))],
        "timing_is_reference_only": True}
    (HERE / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
