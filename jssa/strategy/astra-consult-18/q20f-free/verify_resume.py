"""Verify inherited evidence without rerunning searches, policy selection, or bootstrap.

Only this directory's resume-verification.json is written. Standard library only.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import platform
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(name):
    return json.loads((HERE / name).read_text())


def read_csv(name):
    with (HERE / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def number(value):
    return math.inf if value == "inf" else float(value)


def same(a, b):
    a, b = number(a), number(b)
    assert (a == b) or math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-9), (a, b)


def main():
    start = time.monotonic()
    provenance = read_json("provenance.json")
    summary = read_json("summary.json")
    bootstrap = read_json("posthoc-bootstrap.json")
    inputs = provenance["inputs"]
    mismatch = [name for name, expected in inputs.items()
                if not (ROOT / name).is_file() or digest(ROOT / name) != expected]
    assert not mismatch, mismatch
    assert digest(HERE / "analyze_restarts.py") == provenance["script_sha256"]
    assert digest(HERE / "analysis-plan.md") == provenance["plan_sha256"]
    assert digest(HERE / "posthoc_check.py") == bootstrap["script_sha256"]
    assert digest(HERE / "posthoc-check-plan.md") == bootstrap["plan_sha256"]

    # Inventory and recorded labels only; do not call an optimizer or evaluator.
    totals, short_counts, case_ids = [0, 0], [0, 0], [set(), set()]
    raw_multi = {}
    for name in inputs:
        obj = json.loads((ROOT / name).read_text())
        seed = obj["seed"]
        assert seed in (0, 1) and obj["n_vars"] > 0
        cid = obj["case_id"]
        assert cid not in case_ids[seed]
        case_ids[seed].add(cid)
        records = obj["records"]
        totals[seed] += len(records)
        short_counts[seed] += len(records) < 200
        assert all(isinstance(r["nfev"], int) and r["nfev"] >= 0 for r in records)
        if len(obj["references"]) > 1:
            hits = [sum(r["cls"] == "hit" and r["ref"] == j for r in records)
                    for j in range(len(obj["references"]))]
            raw_multi[cid, seed] = dict(n=len(records), hits=hits)
    assert case_ids[0] == case_ids[1]
    assert len(case_ids[0]) == summary["n_cases"] == 292
    assert totals == [summary["n_records_seed0"], summary["n_records_seed1"]]
    assert short_counts == [summary["truncated_seed0"], summary["truncated_seed1"]]

    all_rows = read_csv("all-problems.csv")
    multi_rows = read_csv("multi-value.csv")
    curves = read_csv("cutoff-curves.csv")
    assert len(all_rows) == 584 and len(multi_rows) == 16 and len(curves) == 192
    key = lambda row: (row["case_id"], int(row["overhead"]))
    indexed = {key(row): row for row in all_rows}
    assert len(indexed) == len(all_rows)
    for row in multi_rows:
        assert row == indexed[key(row)]
    eligible, primary_r1 = [], []
    for row in summary["multi_no_overhead"]:
        cid = row["case_id"]
        for seed in (0, 1):
            assert row[f"n_seed{seed}"] == raw_multi[cid, seed]["n"]
            assert row[f"hits_seed{seed}"] == raw_multi[cid, seed]["hits"]
        if row["complete_seed0"] and row["complete_seed1"]:
            eligible.append(cid)
            if row["first_ratio"] <= 0.8 and row["all_firstcut_ratio"] >= 2:
                primary_r1.append(cid)
        stored = indexed[cid, 0]
        for field in ("first_baseline", "first_firstcut", "all_baseline", "all_firstcut",
                      "all_allcut", "all_adaptive"):
            same(stored[field], row[field])
    assert len(eligible) == summary["n_multi_all_observed_both_seeds"] == 5
    assert primary_r1 == summary["R1_ids"] == []
    assert summary["R1_pass"] is False and summary["R2_pass"] is False
    assert {row["case_id"] for row in bootstrap["rows"]} == set(eligible)

    # Independent fixed-policy check from saved sufficient statistics, not raw replay.
    max_error = 0.0
    for row in curves:
        cid, seed = row["case_id"], int(row["seed"])
        counts = json.loads(row["hits"])
        probabilities = [Fraction(n, raw_multi[cid, seed]["n"]) for n in counts]
        c = float(row["cost"])
        q = sum(probabilities)
        same(row["first"], c / float(q) if q else math.inf)
        if all(probabilities):
            # All finite cases here have exactly two reference values.
            assert len(probabilities) == 2
            p, q = probabilities
            expected = c * float(1 / p + 1 / q - 1 / (p + q))
            same(row["all"], expected)
            max_error = max(max_error, abs(number(row["all"]) - expected))
        else:
            assert number(row["all"]) == math.inf

    # Exact audit of the two inherited toy examples; these are not geometry runs.
    for row in read_json("theory-exact.json"):
        eps = Fraction(row["epsilon"])
        duration = row["slow_duration"]
        c = 1 - eps + eps * duration
        exact = {
            "short_first_exact": 1 / (1 - eps),
            "long_first_exact": c,
            "long_all_exact": c * (1 / (1 - eps) + 1 / eps - 1),
            "mixed_all_exact": (1 + c) / 2 *
                (1 / (1 - eps) + 2 / eps - 1 / (1 - eps / 2)),
        }
        assert all(Fraction(row[name]) == value for name, value in exact.items())
        assert row["short_all"] == "inf"

    primary_files = ["analysis-plan.md", "analyze_restarts.py", "summary.json",
                     "provenance.json", "all-problems.csv", "multi-value.csv",
                     "cutoff-curves.csv", "theory-exact.json", "posthoc-check-plan.md",
                     "posthoc_check.py", "posthoc-bootstrap.json", "posthoc-bootstrap.csv"]
    for path in HERE.glob("*.py"):
        ast.parse(path.read_text(), filename=str(path))
    result = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "status": "pass",
        "new_local_searches": 0, "primary_analysis_rerun": False,
        "bootstrap_rerun": False,
        "input_hash_checks": len(inputs), "hash_mismatches": mismatch,
        "script_and_plan_hash_checks": 4,
        "case_count": len(case_ids[0]), "records_by_seed": totals,
        "fewer_than_200_records_by_seed": short_counts,
        "multi_value_cases": len(raw_multi) // 2,
        "both_seeds_all_values_observed": eligible, "R1_ids": primary_r1,
        "curve_formula_checks": len(curves),
        "max_absolute_curve_formula_difference": max_error,
        "theory_exact_cases_verified": 2,
        "inherited_file_hashes": {name: digest(HERE / name) for name in primary_files},
        "audit_script_sha256": digest(Path(__file__)),
        "elapsed_seconds": time.monotonic() - start,
        "scope": "Integrity and arithmetic audit only; original labels are not re-certified.",
    }
    (HERE / "resume-verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("inherited_file_hashes", "both_seeds_all_values_observed")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
