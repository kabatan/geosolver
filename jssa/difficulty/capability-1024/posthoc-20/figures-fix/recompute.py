"""Recompute figure/campaign summaries from saved records, without solver execution."""

import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent


def load_csv(relative):
    with (ROOT / relative).open() as f:
        return list(csv.DictReader(f))


def source(relative):
    return {"path": relative,
            "sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}


def probability_summary(rows):
    return {"problems": len(rows), "starts_per_problem": sorted({int(r["n_x"]) for r in rows}),
            "medians": {k: median(float(r[k]) for r in rows) for k in ("pE", "pY", "pZ")}}


def time_summary(rows):
    ordered = sorted(rows, key=lambda r: float(r["wall_time_s"]))
    mid = ordered[len(ordered) // 2]
    value = median(float(r["wall_time_s"]) for r in rows)
    return {"runs": len(rows), "median_seconds": value,
            "rounded_1_decimal": f"{value:.1f}", "rounded_2_decimals": f"{value:.2f}",
            "median_run": {k: mid[k] for k in ("case_id", "seed", "correct", "wall_time_s")}}


common_path = "jssa/difficulty/common-start/summary.csv"
stage_path = "jssa/results/stage-profile-20261023/per-case.csv"
attribution_path = "jssa/results/mechanism-attribution/attribution.csv"
dsl_path = "benchmarks/dsl/AIME-2021-I-11.json"
common = load_csv(common_path)
stage = load_csv(stage_path)
attribution = load_csv(attribution_path)
key = lambda r: (r["case_id"], r["seed"])
stage_by_key = {key(r): r for r in stage}
attr_by_key = {key(r): r for r in attribution}
assert len(stage_by_key) == len(stage) == len(attr_by_key) == len(attribution) == 969
assert stage_by_key.keys() == attr_by_key.keys()
assert all(r["correct"] == attr_by_key[k]["matched"]
           and float(r["wall_time_s"]) == float(attr_by_key[k]["wall_s"])
           for k, r in stage_by_key.items())
assert len({r["case_id"] for r in stage}) == 323
assert {r["seed"] for r in stage} == {"0", "1", "2"}
correct = [r for r in stage if r["correct"] == "True"]
assert len(correct) == 953
dsl = json.loads((ROOT / dsl_path).read_text())
equations = [c for c in dsl["conditions"] if c.get("operator") == "="]
assert len(equations) == 5

# Follow construction dependencies, rather than checking direct point names only.
upper_ids = ["HMMT-2011-FEB-ALGGEO-08", "AIME-2014-II-14", "HMMT-2025-FEB-GEO-06",
             "JMO-2013-PRE-03", "AIME-2010-II-09", "AIME-2021-I-11"]
group_checks = []
for cid in upper_ids:
    base_path = f"benchmarks/extra-variables/dsl/{cid}.k0.json"
    expanded_path = f"benchmarks/extra-variables/dsl/{cid}.k3.json"
    base = json.loads((ROOT / base_path).read_text())
    expanded = json.loads((ROOT / expanded_path).read_text())
    picks = {v[2:] for v in expanded["variables"] if v not in base["variables"]}
    names = lambda s: set(re.findall(r"\b[A-Za-z_]\w*\b", str(s)))
    deps = {c["name"]: names(c["expression"]) for c in base["constructions"]}

    def closure(items):
        result = set(items)
        while True:
            more = result | set().union(*(deps.get(n, set()) for n in result))
            if more == result:
                return result
            result = more

    eq_deps = set().union(*(closure(names(c.get("left", "")) | names(c.get("right", "")))
                            for c in base["conditions"] if c.get("operator") == "="))
    other_deps = set().union(*(closure(names(c)) for c in base["conditions"]
                               if c.get("operator") != "="))
    assert not picks & eq_deps
    group_checks.append({"case_id": cid, "rewritten_points": sorted(picks),
                         "original_equality_dependencies": sorted(picks & eq_deps),
                         "other_condition_dependencies": sorted(picks & other_deps),
                         "sources": [source(base_path), source(expanded_path)]})

result = {
    "sources": [source(p) for p in (common_path, stage_path, attribution_path, dsl_path)],
    "dsl": {"id": dsl["id"], "variables": len(dsl["variables"]),
            "equalities": equations, "equality_count": len(equations),
            "non_equality_count": len(dsl["conditions"]) - len(equations),
            "redundant_equality": "Distance(A, B) = 4; A=(0,0), B=(4,0)",
            "all_four_feet_expanded": {"variables": 12, "written_equalities": 13}},
    "common_start_all": probability_summary(common),
    "common_start_excluding_JMO_2014_PRE_09": probability_summary(
        [r for r in common if r["case_id"] != "JMO-2014-PRE-09"]),
    "upper_group_checks": group_checks,
    "development_all": time_summary(stage),
    "development_correct_only": time_summary(correct),
    "cross_check": "All 969 case/seed keys, correctness labels and times agree between the two CSVs.",
    "limitation": "Original campaign result JSONs at the recorded path are unavailable; saved per-run CSVs are used.",
}
precision_sources = [
    "src/geosolver/engine/standard/refinement/refiner_config.py",
    "src/geosolver/engine/standard/refinement/mpmath_refiner.py",
    "src/geosolver/engine/standard/evaluation/final_verifier.py",
    "src/geosolver/engine/standard/orchestration/assemble_exact_results.py",
    dsl_path,
]
frozen_checks = []
for relative in precision_sources:
    frozen = subprocess.check_output(["git", "show", f"60db4b6:{relative}"], cwd=ROOT)
    assert frozen == (ROOT / relative).read_bytes()
    frozen_checks.append({**source(relative), "same_as_60db4b6": True})
result["precision_checks"] = {
    "sources": frozen_checks,
    "refinement_lm_dps": [50, 100, 120],
    "refinement_closure_dps": [120, 250, 350, 500],
    "final_verification_dps": [80, 120, 180, 250, 350, 500],
    "acceptance": "valid and previous_valid and precision >= 180; earliest pair is 120/180",
    "independent_confirmation": "For non-closed targets, use higher stages from 250/350/500 when at least two are available.",
}
(OUT / "recomputed.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ("common_start_all", "common_start_excluding_JMO_2014_PRE_09",
                                      "development_all", "development_correct_only")}, indent=2))
