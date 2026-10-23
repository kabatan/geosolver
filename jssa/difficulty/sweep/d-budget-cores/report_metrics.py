"""Reproduce the descriptive counts and effect sizes quoted in answer.md.

The twofold timing cutoff is post hoc, not a preregistered hypothesis.
No solver calls, additional seeds, resampling, or outcome-based case selection.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import statistics as st

BASE = Path(__file__).resolve().parent


def read_csv(name):
    with (BASE / name).open() as f:
        return list(csv.DictReader(f))


def ratio(a, b):
    return max(a, b) / min(a, b)


def main():
    manifest = json.loads((BASE / "manifest.json").read_text())
    summary = json.loads((BASE / "summary.json").read_text())
    assert summary["observed"] == summary["scheduled"] == 216 and not summary["partial"]
    receipts = {p.stem: json.loads(p.read_text()) for p in (BASE / "receipts").glob("*.json")}
    timing = read_csv("seed-timing.csv")
    primary = [r["id"] for r in timing if r["a_correct_of4"] == r["b_correct_of4"] == "4"
               and float(r["large_over_small_ratio"]) >= 2]
    extra = [r["id"] for r in timing if r["c_correct"] == r["d_correct"] == "True"
             and float(r["cd_large_over_small_ratio"]) >= 2]
    seed_rows = read_csv("seed-aggregation.csv")
    costs = {}
    for label in ("a1", "a2", "b1", "b2", "all4"):
        block = [r for r in seed_rows if r["label"] == label]
        assert len(block) == 20 and all(r["all_observed"] == "True" for r in block)
        costs[label] = {"any_correct": sum(r["any_correct"] == "True" for r in block),
                        "union_correct": sum(r["union_correct"] == "True" for r in block),
                        "summed_wall_seconds": sum(float(r["sum_wall_seconds"]) for r in block)}
    figures = {r["job"]: r for r in read_csv("figure-per-run.csv")}
    available, changed = [[], []], [[], []]
    for case in manifest["cases"]:
        jobs = {j["seed"]: j["job"] for j in manifest["jobs"]
                if j["id"] == case["id"] and j["budget"] == 180 and j["cores"] == 1}
        for i, (a, b) in enumerate(((430401, 430501), (430601, 430701))):
            ja, jb = jobs[a], jobs[b]
            sa, sb = json.loads(figures[ja]["shape_classes"]), json.loads(figures[jb]["shape_classes"])
            if sa and sb and receipts[ja]["matched"] and receipts[jb]["matched"]:
                available[i].append(case["id"])
                if sa != sb:
                    changed[i].append(case["id"])
    details = json.loads((Path(manifest["raw_root"]) / "evaluated-figures.json").read_text())
    scale_case = details["HMMT-2023-FEB-GEO-04"]
    scales = [c["variables"][0] for c in scale_case["configurations"]]
    example = next(r for r in timing if r["id"] == "AIME-2008-II-11")
    blocks = [[r for r in receipts.values() if r["id"] == example["id"] and r["budget"] == 180
               and r["seed"] == seed] for seed in manifest["seeds"]]
    primary_cpu = [st.median(r["process_info"]["cpu_seconds"] for r in block) for block in blocks[:2]]
    extra_cpu = [block[0]["process_info"]["cpu_seconds"] for block in blocks[2:]]
    overlap = {r["job"]: r for r in read_csv("per-run-interference.csv")}
    budget_rows = []
    for budget in (180, 360, 900):
        r = next(r for r in receipts.values() if r["id"] == "aime-2000-2-6"
                 and r["seed"] == 430401 and r["cores"] == 1 and r["budget"] == budget)
        budget_rows.append({"job": r["job"], "budget": budget, "matched": r["matched"],
                            "wall_seconds": r["wall_seconds"], "worker_cpu_seconds": r["process_info"]["cpu_seconds"],
                            "evaluation_count": r["counters"]["evaluation_count"],
                            "same_cpu_q37_overlap_fraction": float(overlap[r["job"]]["q37_same_cpu_overlap_fraction"])})
    counter_sets = [receipts[r["job"]]["counters"] for r in budget_rows]
    inputs = ("manifest.json", "summary.json", "seed-timing.csv", "seed-aggregation.csv", "figure-per-run.csv",
              "figure-summary.json", "per-run-interference.csv")
    metrics = {
        "denominator_problems": 20, "timing_cutoff": 2, "timing_cutoff_is_posthoc": True,
        "timing_meaning": "Ratio of median return times across four primary runs (requested cores 1/2/4/8, effective one); extra pair has one run per seed. Only all-correct comparisons count as timing replication; all 20 problems remain in the denominator.",
        "primary_timing_twofold_problems": primary, "extra_timing_twofold_problems": extra,
        "timing_replicated_problems": sorted(set(primary) & set(extra)),
        "timing_example": {**example, "primary_worker_cpu_medians": primary_cpu,
                           "primary_worker_cpu_ratio": ratio(*primary_cpu),
                           "extra_worker_cpu_seconds": extra_cpu, "extra_worker_cpu_ratio": ratio(*extra_cpu)},
        "seed_costs": costs,
        "four_seed_cost_over_one": costs["all4"]["summed_wall_seconds"] / costs["a1"]["summed_wall_seconds"],
        "seed_success_discordance": {"any_of_four": summary["seed_mixed_success_problems"],
                                      "primary_pair": summary["seed_primary_pair_discordant"],
                                      "extra_pair": summary["seed_extra_pair_discordant"],
                                      "both_pairs": sorted(set(summary["seed_primary_pair_discordant"]) & set(summary["seed_extra_pair_discordant"]))},
        "shape_available_problems_by_seed_pair": available, "shape_changed_problems_by_seed_pair": changed,
        "shape_replicated_problems": sorted(set(changed[0]) & set(changed[1])),
        "shape_empty_set_rule": "No saved figure is missing geometric evidence; do not count presence-versus-absence as a different geometry with the same correct answer.",
        "scale_example": {"id": "HMMT-2023-FEB-GEO-04", "shape_count": len(scales),
                          "scale_min": min(scales), "scale_max": max(scales), "scale_ratio": max(scales)/min(scales),
                          "shapes_by_seed": {str(j["seed"]): j["shape_count"] for j in scale_case["jobs"] if j["budget"] == 180 and j["cores"] == 1}},
        "budget_interference_example": {"id": "aime-2000-2-6", "seed": 430401, "runs": budget_rows,
                                        "all_counters_equal": all(c == counter_sets[0] for c in counter_sets)},
        "input_sha256": {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest() for name in inputs},
    }
    (BASE / "findings.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"timing_primary": primary, "timing_replicated": metrics["timing_replicated_problems"],
                      "seed_costs": costs, "cost_ratio": metrics["four_seed_cost_over_one"],
                      "shape_changed": changed, "shape_replicated": metrics["shape_replicated_problems"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
