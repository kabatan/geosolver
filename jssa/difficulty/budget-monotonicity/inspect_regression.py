"""Extract recorded candidate/cutoff evidence only; never invoke a solver."""
from __future__ import annotations

import csv
import hashlib
import json

import isolated_stage2 as execution


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    execution.verify()
    base = execution.BASE
    pairs = list(csv.DictReader((base / "regressions.csv").open()))
    affected = sorted({r["id"] for r in pairs})
    runs = {}
    for cid in affected:
        for seed in (370101, 370201, 370301):
            for budget in (180, 360, 900):
                path = base / f"campaign/t{budget}/s{seed}/runs/{cid}/{seed}.json"
                raw = execution.read(path)
                diag = raw["solver_result"]["diagnostics"]
                pipeline = diag["pipeline_summary"]
                counters = diag["counters"]
                ordinary, chart = [], []
                for candidate in diag["candidate_records"]:
                    source = candidate["source"]
                    identity = {k: source.get(k) for k in (
                        "candidate_key", "x_float", "initial_point_decimal",
                        "origin_phase", "origin_backend", "origin_seed", "origin_start_point_index",
                    )}
                    if source.get("origin_backend") == "positive_scale_chart":
                        chart.append({**identity, "candidate_id": candidate["candidate_id"],
                                      "accepted": candidate.get("accepted")})
                    else:
                        ordinary.append(identity)
                runs[(cid, seed, budget)] = {
                    "id": cid, "seed": seed, "budget_seconds": budget,
                    "raw_path": str(path.relative_to(base)), "raw_sha256": execution.sha(path),
                    "initial_probe_sha256": digest(pipeline["initial_probe"]),
                    "ordinary_candidates": ordinary,
                    "ordinary_candidates_in_order_sha256": digest(ordinary),
                    "supplemental_chart_candidates": chart,
                    "selected_count": pipeline["search"]["selected_candidates"],
                    "search_evaluation_count": pipeline["search"]["evaluation_count"],
                    "chart_summary": pipeline["search"].get("positive_scale_chart"),
                    "chart_counters": {k: v for k, v in counters.items() if k.startswith("positive_scale_chart_")},
                    "returned_answer_values": sorted(set(pipeline["answer_candidate_values"])),
                    "return_wall_seconds": raw["solver_result"]["elapsed_seconds"],
                    "fallback_triggered": pipeline["search_staged_fallback"]["triggered"],
                    "rescue_triggered": pipeline["phase_rescue"]["triggered"],
                }
    comparisons = []
    for pair in pairs:
        cid, seed = pair["id"], int(pair["seed"])
        short = runs[cid, seed, int(pair["short_budget"])]
        long = runs[cid, seed, int(pair["long_budget"])]
        comparisons.append({
            "id": cid, "seed": seed, "short_budget": int(pair["short_budget"]),
            "long_budget": int(pair["long_budget"]),
            "same_initial_probe": short["initial_probe_sha256"] == long["initial_probe_sha256"],
            "same_ordinary_candidate_coordinates_origins_and_order": short["ordinary_candidates"] == long["ordinary_candidates"],
            "ordinary_candidate_counts": [len(short["ordinary_candidates"]), len(long["ordinary_candidates"])],
            "supplemental_chart_counts": [len(short["supplemental_chart_candidates"]), len(long["supplemental_chart_candidates"])],
            "long_stop_counters": {k: v for k, v in long["chart_counters"].items() if "stop_" in k or "interrupted_" in k or "timeout" in k},
            "missing_answer_values": sorted(set(short["returned_answer_values"]) - set(long["returned_answer_values"])),
        })
    sources = (
        "src/geosolver/engine/standard/search/scale_chart.py",
        "src/geosolver/engine/standard/search/algebraic_branches.py",
        "src/geosolver/engine/standard/orchestration/run_search.py",
    )
    result = {
        "utc": execution.now(), "solver_runs": 0, "frozen_commit": execution.FROZEN,
        "script_sha256": execution.sha(__file__),
        "source_files": {name: {"path": str(execution.ROOT / name), "sha256": execution.sha(execution.ROOT / name)} for name in sources},
        "runs": list(runs.values()), "comparisons": comparisons,
        "interpretation": "The first recorded divergence is in supplemental search proposals: the fixed 0.5 CPU-second symbolic limit interrupts chart discovery. Ordinary candidates match in coordinates, provenance and order. This does not establish that the total budget caused the cutoff; no same-budget repeats or interventions were added.",
    }
    execution.save(base / "mechanism-summary.json", result)
    print(json.dumps(comparisons, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
