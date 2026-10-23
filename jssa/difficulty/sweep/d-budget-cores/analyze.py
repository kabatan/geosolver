"""Summarize all fixed Q43d cells; never remove failures from denominators."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import datetime as dt
import json
import math
from pathlib import Path
import statistics as st

BASE = Path(__file__).resolve().parent


def write_csv(name, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (BASE / name).open("w") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                        if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()})


def stats(values):
    values = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return {"n": len(values), "min": min(values), "median": st.median(values), "max": max(values)} if values else {"n": 0}


def analyze(partial=False):
    manifest = json.loads((BASE / "manifest.json").read_text())
    receipts = {r["job"]: r for p in (BASE / "receipts").glob("*.json") if (r := json.loads(p.read_text()))}
    missing = [j["job"] for j in manifest["jobs"] if j["job"] not in receipts]
    if missing and not partial:
        raise ValueError(f"unfinished jobs: {missing}")
    rows, lookup = [], {}
    for job in manifest["jobs"]:
        case = manifest["cases"][job["case_index"]]
        r = receipts.get(job["job"], {})
        cpu = (r.get("process_info") or {}).get("cpu_seconds")
        wall = r.get("solver_elapsed")
        row = {**job, "group": case["group"], "n_vars": case["n_vars"], "observed": bool(r),
               "matched": bool(r.get("matched")), "status": r.get("status", "not_observed"),
               "normal": bool(r.get("normal")), "outer_timeout": r.get("outer_timeout"),
               "termination": r.get("termination"), "returncode": r.get("returncode"),
               "answer_keys": r.get("answer_keys", []), "answer_count": len(r.get("answer_keys", [])),
               "wall_seconds": r.get("wall_seconds"), "solver_seconds": wall, "cpu_seconds": cpu,
               "cpu_wall_ratio": cpu / wall if cpu is not None and wall else None,
               "used_cores": (r.get("used_resources") or {}).get("cores"), "cpu": r.get("cpu"),
               "load_start": (r.get("load_start") or [None])[0], "load_end": (r.get("load_end") or [None])[0],
               "accepted_count": r.get("accepted_count"), "candidate_count": r.get("candidate_count"),
               "numeric_feasible": r.get("numeric_feasible"), "contract_issues": r.get("contract_issues", []),
               "phase_timings": r.get("phase_timings", {}), "counters": r.get("counters", {}),
               "raw_bytes": r.get("raw_bytes"), "started_utc": r.get("started_utc"), "finished_utc": r.get("finished_utc")}
        rows.append(row)
        lookup[(job["id"], job["seed"], job["budget"], job["cores"])] = row
    seeds = manifest["seeds"]
    core_pairs, core_blocks, seed_rows, budget_pairs, budget_blocks, cases = [], [], [], [], [], []
    for case in manifest["cases"]:
        cid = case["id"]
        patterns = []
        for seed in seeds[:2]:
            block = [lookup[(cid, seed, 180, c)] for c in (1, 2, 4, 8)]
            pattern = "".join("1" if r["matched"] else "0" if r["observed"] else "?" for r in block)
            patterns.append(pattern)
            core_blocks.append({"id": cid, "group": case["group"], "seed": seed, "pattern_1_2_4_8": pattern,
                                "all_observed": all(r["observed"] for r in block),
                                "same_answer_set": all(r["answer_keys"] == block[0]["answer_keys"] for r in block),
                                "same_counters": all(r["counters"] == block[0]["counters"] for r in block),
                                "answer_sets": [r["answer_keys"] for r in block],
                                "times": [r["wall_seconds"] for r in block]})
            for low, high in ((1, 2), (1, 4), (1, 8), (2, 4), (2, 8), (4, 8)):
                a, b = lookup[(cid, seed, 180, low)], lookup[(cid, seed, 180, high)]
                core_pairs.append({"id": cid, "group": case["group"], "seed": seed, "low": low, "high": high,
                                   "all_observed": a["observed"] and b["observed"], "both_normal": a["normal"] and b["normal"],
                                   "loss": a["observed"] and b["observed"] and a["matched"] and not b["matched"],
                                   "gain": a["observed"] and b["observed"] and not a["matched"] and b["matched"],
                                   "answer_change": a["answer_keys"] != b["answer_keys"],
                                   "time_delta": b["wall_seconds"] - a["wall_seconds"] if a["observed"] and b["observed"] else None,
                                   "time_ratio": b["wall_seconds"] / a["wall_seconds"] if a["observed"] and b["observed"] else None})
            if case["time_sweep"]:
                block_t = [lookup[(cid, seed, t, 1)] for t in (180, 360, 900)]
                budget_blocks.append({"id": cid, "group": case["group"], "seed": seed,
                                      "pattern_180_360_900": "".join("1" if r["matched"] else "0" if r["observed"] else "?" for r in block_t),
                                      "answer_sets": [r["answer_keys"] for r in block_t],
                                      "times": [r["wall_seconds"] for r in block_t]})
                for lo, hi in ((180, 360), (180, 900), (360, 900)):
                    a, b = lookup[(cid, seed, lo, 1)], lookup[(cid, seed, hi, 1)]
                    budget_pairs.append({"id": cid, "seed": seed, "low": lo, "high": hi,
                                         "all_observed": a["observed"] and b["observed"], "both_normal": a["normal"] and b["normal"],
                                         "loss": a["observed"] and b["observed"] and a["matched"] and not b["matched"],
                                         "gain": a["observed"] and b["observed"] and not a["matched"] and b["matched"],
                                         "answer_change": a["answer_keys"] != b["answer_keys"],
                                         "time_delta": b["wall_seconds"] - a["wall_seconds"] if a["observed"] and b["observed"] else None})
        base = [lookup[(cid, seed, 180, 1)] for seed in seeds]
        for label, indices in [("a1", [0]), ("a2", [0, 1]), ("b1", [2]), ("b2", [2, 3]), ("all4", [0, 1, 2, 3])]:
            block = [base[i] for i in indices]
            union = sorted({k for r in block for k in r["answer_keys"]})
            seed_rows.append({"id": cid, "group": case["group"], "n_vars": case["n_vars"], "label": label,
                              "seeds": [r["seed"] for r in block], "n": len(block),
                              "all_observed": all(r["observed"] for r in block),
                              "any_correct": any(r["matched"] for r in block),
                              "union_correct": union == case["expected_keys"] and all(r["observed"] for r in block),
                              "union": union, "extra": sorted(set(union) - set(case["expected_keys"])),
                              "missing": sorted(set(case["expected_keys"]) - set(union)),
                              "sum_wall_seconds": sum(r["wall_seconds"] or 0 for r in block),
                              "successful_runs": sum(r["matched"] for r in block), "normal_runs": sum(r["normal"] for r in block)})
        all_runs = [r for r in rows if r["id"] == cid]
        cases.append({"id": cid, "group": case["group"], "n_vars": case["n_vars"], "scheduled": len(all_runs),
                      "observed": sum(r["observed"] for r in all_runs), "correct": sum(r["matched"] for r in all_runs),
                      "core_pattern_seed_a": patterns[0], "core_pattern_seed_b": patterns[1],
                      "seed_pattern_1core": "".join("1" if r["matched"] else "0" if r["observed"] else "?" for r in base),
                      "distinct_public_answer_sets": len({tuple(r["answer_keys"]) for r in all_runs if r["observed"]}),
                      "base_time_min": min((r["wall_seconds"] for r in base if r["observed"]), default=None),
                      "base_time_max": max((r["wall_seconds"] for r in base if r["observed"]), default=None)})
    telemetry_path = Path(manifest["raw_root"]) / "host-telemetry.jsonl"
    telemetry = [json.loads(line) for line in telemetry_path.read_text().splitlines()] if telemetry_path.exists() else []
    affinity = json.loads((BASE / "cpu-selection.json").read_text()) if (BASE / "cpu-selection.json").exists() else {}
    chosen = affinity.get("chosen", [])
    for row in rows:
        samples = [t for t in telemetry if row["observed"] and row["started_utc"] <= t["utc"] <= row["finished_utc"]]
        siblings = next((g for g in affinity.get("physical_siblings", []) if row["cpu"] in g), [])
        other_siblings = [c for c in siblings if c != row["cpu"]]
        row.update(host_samples_during_run=len(samples),
                   host_load_mean=st.mean(t["load"][0] for t in samples) if samples else None,
                   assigned_cpu_mean_percent=st.mean(t["percpu"][row["cpu"]] for t in samples) if samples else None,
                   sibling_cpu_mean_percent=st.mean(t["percpu"][c] for t in samples for c in other_siblings)
                   if samples and other_siblings else None)
    env = {"host_samples": len(telemetry), "load_1m": stats([r["load"][0] for r in telemetry]),
           "system_cpu_mean_percent": stats([st.mean(r["percpu"]) for r in telemetry]),
           "assigned_cpu_percent": {str(c): stats([r["percpu"][c] for r in telemetry]) for c in chosen},
           "min_tmp_free_bytes": min((r["tmp_free"] for r in telemetry), default=None),
           "min_available_memory_bytes": min((r["available_memory"] for r in telemetry), default=None),
           "worker_cpu_wall_ratio": stats([r["cpu_wall_ratio"] for r in rows]),
           "interference_caveat": "Worker CPU seconds exclude symbolic child processes; CPU/wall <1 includes child work, I/O and waits. Host usage includes other jobs and our jobs. See interference.json for recorded concurrent Q37 intervals; no causal correction."}
    condition_rows = []
    for budget, cores, seed_group in [(180, c, seeds[:2]) for c in (1, 2, 4, 8)] + [(180, 1, seeds[2:])] + [(t, 1, seeds[:2]) for t in (360, 900)]:
        block = [r for r in rows if r["budget"] == budget and r["cores"] == cores and r["seed"] in seed_group]
        condition_rows.append({"budget": budget, "cores_requested": cores, "seeds": seed_group,
                               "scheduled": len(block), "observed": sum(r["observed"] for r in block),
                               "correct": sum(r["matched"] for r in block), "status_counts": dict(Counter(r["status"] for r in block)),
                               "wall_seconds": stats([r["wall_seconds"] for r in block]),
                               "sum_wall_seconds": sum(r["wall_seconds"] or 0 for r in block)})
    summary = {"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "partial": bool(missing),
               "scheduled": len(rows), "observed": len(receipts), "missing_jobs": missing,
               "correct": sum(r["matched"] for r in rows), "condition_summary": condition_rows,
               "status_counts": dict(Counter(r["status"] for r in rows)),
               "core_effective_counts": dict(Counter(r["used_cores"] for r in rows if r["observed"])),
               "core_patterns": dict(Counter(r["pattern_1_2_4_8"] for r in core_blocks)),
               "core_any_loss_problems": sorted({r["id"] for r in core_pairs if r["loss"]}),
               "core_any_gain_problems": sorted({r["id"] for r in core_pairs if r["gain"]}),
               "core_same_answer_blocks": sum(r["all_observed"] and r["same_answer_set"] for r in core_blocks),
               "core_same_counter_blocks": sum(r["all_observed"] and r["same_counters"] for r in core_blocks),
               "core_1to8_loss_problems": sorted({r["id"] for r in core_pairs if r["loss"] and (r["low"], r["high"]) == (1, 8)}),
               "core_1to8_time_ratios": stats([r["time_ratio"] for r in core_pairs if (r["low"], r["high"]) == (1, 8)]),
               "seed_summary": {label: {"denominator": 20, "observed_cases": sum(r["all_observed"] for r in seed_rows if r["label"] == label),
                                           "any_correct": sum(r["any_correct"] for r in seed_rows if r["label"] == label),
                                           "union_correct": sum(r["union_correct"] for r in seed_rows if r["label"] == label)}
                                for label in ("a1", "a2", "b1", "b2", "all4")},
               "budget_patterns": dict(Counter(r["pattern_180_360_900"] for r in budget_blocks)),
               "budget_loss_problems": sorted({r["id"] for r in budget_pairs if r["loss"]}),
               "seed_mixed_success_problems": [r["id"] for r in cases if "0" in r["seed_pattern_1core"] and "1" in r["seed_pattern_1core"]],
               "seed_primary_pair_discordant": [r["id"] for r in cases if set(r["seed_pattern_1core"][:2]) == {"0", "1"}],
               "seed_extra_pair_discordant": [r["id"] for r in cases if set(r["seed_pattern_1core"][2:]) == {"0", "1"}],
               "environment": env}
    if partial:
        print(json.dumps({"observed": len(receipts), "scheduled": len(rows), "status_counts": summary["status_counts"],
                          "core_losses_so_far": summary["core_any_loss_problems"], "seed_summary": summary["seed_summary"]}, ensure_ascii=False))
        return
    seed_timing = []
    for case in manifest["cases"]:
        block_a = [lookup[(case["id"], seeds[0], 180, c)] for c in (1, 2, 4, 8)]
        block_b = [lookup[(case["id"], seeds[1], 180, c)] for c in (1, 2, 4, 8)]
        ca, cb = lookup[(case["id"], seeds[2], 180, 1)], lookup[(case["id"], seeds[3], 180, 1)]
        ma, mb = st.median(r["wall_seconds"] for r in block_a), st.median(r["wall_seconds"] for r in block_b)
        seed_timing.append({"id": case["id"], "group": case["group"], "seed_a": seeds[0], "seed_b": seeds[1],
                            "a_times": [r["wall_seconds"] for r in block_a], "b_times": [r["wall_seconds"] for r in block_b],
                            "a_median": ma, "b_median": mb, "ratio_b_over_a": mb / ma,
                            "large_over_small_ratio": max(ma, mb) / min(ma, mb),
                            "a_correct_of4": sum(r["matched"] for r in block_a), "b_correct_of4": sum(r["matched"] for r in block_b),
                            "seed_c_seconds": ca["wall_seconds"], "seed_d_seconds": cb["wall_seconds"],
                            "cd_large_over_small_ratio": max(ca["wall_seconds"], cb["wall_seconds"]) / min(ca["wall_seconds"], cb["wall_seconds"]),
                            "c_correct": ca["matched"], "d_correct": cb["matched"]})
    for name, data in [("per-run.csv", rows), ("per-problem.csv", cases), ("core-pairs.csv", core_pairs),
                       ("core-blocks.csv", core_blocks), ("seed-aggregation.csv", seed_rows),
                       ("budget-pairs.csv", budget_pairs), ("budget-blocks.csv", budget_blocks)]:
        write_csv(name, data)
    write_csv("seed-timing.csv", seed_timing)
    (BASE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "condition_summary"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--partial", action="store_true")
    analyze(parser.parse_args().partial)
