"""Descriptive, post-hoc trace audit; never changes preregistered P1/P2."""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def events(identifier, seed, mode):
    folder = HERE / "runs" / mode / "runs" / identifier
    path = folder / f"{seed}.audit.jsonl"
    if not (folder / f"{seed}.json").exists() or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def summarize(evs):
    evaluations = [e for e in evs if e["event"] == "evaluation"]
    starts = [e for e in evs if e["event"] == "nomad_start" and e["scope"] == "disco_mads"]
    feasible = [e for e in evaluations if e["hard"] and e["guard"]]
    best = min((e["equality_sq"] for e in feasible), default=None)
    in_box = []
    if starts:
        bounds = starts[0]["bounds"]
        in_box = [e for e in feasible if all(lo <= x <= hi for x, (lo, hi) in zip(e["x"], bounds))]
    return {
        "calls": len(starts), "finite_evals": len(evaluations),
        "feasible_evals": len(feasible), "in_box_feasible_evals": len(in_box),
        "best_feasible_scaled_sq": best,
        "best_in_box_feasible_scaled_sq": min((e["equality_sq"] for e in in_box), default=None),
        "best_any_scaled_sq": min((e["equality_sq"] for e in evaluations), default=None),
        "changed": sum(e["changed"] for e in evaluations),
    }, evaluations, starts


def main():
    selected = list(csv.DictReader((HERE / "selected-cases.csv").open()))
    rows, examples = [], []
    for case in selected:
        for seed in (0, 1, 2):
            be, ne = events(case["id"], seed, "B"), events(case["id"], seed, "N")
            bs, b, bstarts = summarize(be)
            ns, n, nstarts = summarize(ne)
            if not bstarts or not nstarts:
                continue
            same_start = all(bstarts[0][key] == nstarts[0][key]
                             for key in ("starts", "bounds", "scales", "seeds"))
            prefix = 0
            for x, y in zip(b, n):
                if x["x"] != y["x"] or x["count"] != y["count"]:
                    break
                prefix += 1
            first_change = next((e["count"] for e in n if e["changed"]), None)
            first_different_x = n[prefix]["count"] if prefix < min(len(b), len(n)) else None
            best_b, best_n = bs["best_in_box_feasible_scaled_sq"], ns["best_in_box_feasible_scaled_sq"]
            direction = "unavailable"
            if best_b is not None and best_n is not None:
                direction = "N_lower" if best_n < best_b else "N_higher" if best_n > best_b else "equal"
            rows.append({"id": case["id"], "seed": seed, "same_initial_inputs": same_start,
                "common_finite_coordinate_prefix": prefix,
                "first_changed_N_evaluation": first_change,
                "first_different_finite_coordinate": first_different_x,
                "diverged_before_any_changed_payload": bool(
                    first_different_x is not None and (first_change is None or first_different_x <= first_change)),
                "best_in_box_direction": direction,
                **{f"B_{k}": v for k, v in bs.items()}, **{f"N_{k}": v for k, v in ns.items()}})
            # Objective ordering, not a native acceptance/rejection flag.
            best_feasible = None
            for e in b:
                if e["hard"]:
                    if best_feasible is None or e["equality_sq"] < best_feasible["equality_sq"]:
                        best_feasible = e
                elif best_feasible and e["equality_sq"] < best_feasible["equality_sq"] < e["original_score"]:
                    examples.append({"id": case["id"], "seed": seed,
                        "feasible_evaluation": best_feasible["count"], "infeasible_evaluation": e["count"],
                        "feasible_x": best_feasible["x"], "infeasible_x": e["x"],
                        "feasible_equality_sq": best_feasible["equality_sq"],
                        "infeasible_equality_sq": e["equality_sq"],
                        "infeasible_penalized_score": e["original_score"], "tags": e["tags"]})
    if rows:
        with (HERE / "trace-pairs.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (HERE / "objective-ordering-examples.json").write_text(json.dumps(examples, ensure_ascii=False, indent=2))
    useful = [r for r in rows if r["same_initial_inputs"] and r["N_changed"]]
    comparison = Counter(r["best_in_box_direction"] for r in useful)
    result = {
        "analysis_status": "post_hoc_descriptive_only; not a new pass criterion",
        "paired_primary_nomad_traces": len(rows), "same_initial_inputs": sum(r["same_initial_inputs"] for r in rows),
        "paired_with_N_changed_payload": len(useful), "best_in_box_direction_when_changed": dict(comparison),
        "median_feasible_evals_when_changed_B": statistics.median(r["B_feasible_evals"] for r in useful) if useful else None,
        "median_feasible_evals_when_changed_N": statistics.median(r["N_feasible_evals"] for r in useful) if useful else None,
        "diverged_before_any_changed_payload": sum(r["diverged_before_any_changed_payload"] for r in rows),
        "objective_ordering_conflicts_in_paired_B": len(examples),
        "objective_ordering_conflict_problems": len({e["id"] for e in examples}),
        "native_poll_acceptance_observed": False,
        "candidate_accuracy_not_checked_by_this_script": True,
        "scaled_residual_is_not_answer_set_accuracy": True,
    }
    (HERE / "trace-summary.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
