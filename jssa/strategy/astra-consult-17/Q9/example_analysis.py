"""Explicitly post-hoc inspection of the strongest G-versus-X example. No solves."""
import csv
import json

from experiment import OUT, METHODS, SEEDS, save


def main():
    cid = "AIME-2011-II-04"
    with (OUT / "per-start.csv").open() as handle:
        scored = {(int(r["seed"]), r["method"], int(r["k"])): r for r in csv.DictReader(handle) if r["id"] == cid}
    rows = []
    for seed in SEEDS:
        task = json.loads((OUT / "raw" / f"{cid}__{seed}.json").read_text())
        for method in METHODS:
            result = task["methods"][method]
            j = result["var_names"].index("t")
            for raw in result["rows"]:
                t = raw["start"][j]
                rows.append({"seed": seed, "method": method, "k": raw["k"],
                    "t": t, "inside_segment": 0 < t < 1,
                    "status": scored[seed, method, raw["k"]]["status"],
                    "start_feasible": raw["start_feasible"]})
    stats = {}
    for method in METHODS:
        rs = [r for r in rows if r["method"] == method]
        stats[method] = {"inside_segment_starts": sum(r["inside_segment"] for r in rs),
                         "inside_segment_hits": sum(r["inside_segment"] and r["status"] == "hit" for r in rs),
                         "outside_segment_hits": sum(not r["inside_segment"] and r["status"] == "hit" for r in rs),
                         "total": len(rs), "all_start_feasible": all(r["start_feasible"] for r in rs)}
    save(OUT / "example-analysis.json", {"id": cid, "posthoc": True, "selection_reason": "largest G-X S8 seed-count gain",
        "t_box": [-22, 22], "uniform_measure_of_0_t_1": 1/44,
        "angle_bisector_t_from_input_lengths": "20/31", "methods": stats, "rows": rows})
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
