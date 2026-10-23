"""Audit inherited Q20c evidence without rerunning experiments or any solver.

Only verification-resume.json beside this file is written. No third-party imports.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main():
    started = time.perf_counter()
    inherited_names = [
        "registration-lock.json", "preregistration.md", "experiment.py",
        "experiment-rows.csv", "matrix-conditions.csv", "experiment-summary.json",
        "reanalyze.py", "source-hashes.json", "corpus-context.csv",
        "expansion-audit.csv", "existing-paired-effects.csv", "existing-summary.json",
    ]
    before = {name: digest(OUT / name) for name in inherited_names}
    lock = read_json(OUT / "registration-lock.json")
    assert before["preregistration.md"] == lock["preregistration_sha256"]
    assert before["experiment.py"] == lock["experiment_sha256"]
    source_hashes = read_json(OUT / "source-hashes.json")
    mismatches = [name for name, rec in source_hashes.items()
                  if not (ROOT / name).exists()
                  or digest(ROOT / name) != rec["sha256"]
                  or (ROOT / name).stat().st_size != rec["bytes"]]
    assert not mismatches, mismatches

    rows = read_csv(OUT / "experiment-rows.csv")
    matrix_rows = read_csv(OUT / "matrix-conditions.csv")
    old = read_json(OUT / "experiment-summary.json")
    ns = [4, 8, 12, 16, 24, 32, 40, 48, 56, 64]
    pairs = [(rep, solver) for rep in ["E", "E-row", "Y"] for solver in ["LU", "SVD"]]
    pairs += [("E-mode", "direct"), ("E-oracle", "direct"), ("E-mp", "LU-100dps")]
    expected = {(str(n), label, rep, solver) for n in ns for label in ["unit", "decimal"]
                for rep, solver in pairs}
    observed = {(r["N"], r["rhs"], r["representation"], r["solver"]) for r in rows}
    assert len(rows) == len(expected) == len(observed) == old["result_rows"] == 180
    assert observed == expected
    assert len(matrix_rows) == 30
    assert len({(r["N"], r["representation"]) for r in matrix_rows}) == 30
    for r in rows:
        assert math.isfinite(float(r["max_point_error"]))
        assert int(r["dimension"]) == (2 * (int(r["N"]) + 1) if r["representation"] == "Y" else 2)

    errors = {"E": [], "E-row": [], "Y_exact_row_sum": []}
    for r in matrix_rows:
        n = int(r["N"])
        observed_kappa = float(r["kappa_inf"])
        if r["representation"] == "E":
            theoretical = Fraction(2**n + 1)
            key = "E"
        elif r["representation"] == "E-row":
            theoretical = Fraction(2)
            key = "E-row"
        else:
            # Independent analytic row sums of B_Y^{-1}; no matrix inversion.
            theoretical = 3 * max(Fraction(3) - Fraction(1, 2**(n-i+1))
                                  - Fraction(3, 2**(i+1)) for i in range(n + 1))
            key = "Y_exact_row_sum"
        errors[key].append(abs(observed_kappa / float(theoretical) - 1))
    t1 = max(errors["E"] + errors["E-row"]) <= 1e-10 and all(
        float(r["kappa_inf"]) <= 9 * (1 + 1e-10)
        for r in matrix_rows if r["representation"] == "Y")
    assert max(errors["Y_exact_row_sum"]) <= 1e-10
    t2_examples = []
    for n in ns:
        for label in ["unit", "decimal"]:
            sample = {(r["representation"], r["solver"]): r for r in rows
                      if int(r["N"]) == n and r["rhs"] == label}
            if (n >= 56 and float(sample["E-oracle", "direct"]["max_point_error"]) >= .1
                    and float(sample["Y", "LU"]["max_point_error"]) <= 1e-10):
                t2_examples.append({"N": n, "rhs": label})
    mode_max = max(float(r["max_point_error"]) for r in rows if r["representation"] == "E-mode")
    mp_max = max(float(r["max_point_error"]) for r in rows if r["representation"] == "E-mp")
    t2 = bool(t2_examples)
    t3 = mode_max <= 1e-12 and mp_max <= 1e-25
    assert [t1, t2, t3] == [old[t]["passed"] for t in ["T1", "T2", "T3"]]
    assert t2_examples == old["T2"]["examples"]
    assert mode_max == old["T3"]["max_mode_error"]
    assert mp_max == old["T3"]["max_100digit_error"]

    paired = read_csv(OUT / "existing-paired-effects.csv")
    summaries = read_json(OUT / "existing-summary.json")
    paired_by_id = {r["id"]: r for r in paired}
    assert len(paired) == len(paired_by_id) == 57
    common = read_csv(ROOT / "jssa/difficulty/common-start/summary.csv")
    for r in common:
        saved = paired_by_id[r["case_id"]]
        assert int(saved["N"]) == int(r["n_x"])
        assert all(float(saved[f"p{m}"]) == float(r[f"p{m}"]) for m in "EYZ")
    exact_drops = []
    threshold_cases = []
    for r in paired:
        if r["source"] != "holdout-k2":
            continue
        raw = read_json(ROOT / "jssa/difficulty/holdout-1023/out" / (r["id"] + ".json"))
        count = len(raw["rows"])
        hits = {m: sum(x[m]["cls"] == "hit" for x in raw["rows"]) for m in "EYZ"}
        assert count == int(r["N"])
        assert all(hits[m] / count == float(r[f"p{m}"]) == raw["summary"][m]["p"] for m in "EYZ")
        drop = Fraction(hits["E"] - hits["Y"], count)
        if drop >= Fraction(1, 5):
            exact_drops.append(r["id"])
        if drop == Fraction(1, 5):
            pe, py = hits["E"] / count, hits["Y"] / count
            threshold_cases.append({"id": r["id"], "N": count, "E_hits": hits["E"],
                                    "Y_hits": hits["Y"], "exact_drop": str(drop),
                                    "float_difference": pe-py,
                                    "old_score_expression_py_le_pe_minus_0p2": py <= pe-.2})
    groups = {}
    for source in ["common-start-k3", "holdout-k2"]:
        rs = [r for r in paired if r["source"] == source]
        stats = {"problems": len(rs), "starts_per_representation": sum(int(r["N"]) for r in rs),
                 "human_labels": sum(bool(r["human"]) for r in rs),
                 "max_representation_range": max(float(r["range_EYZ"]) for r in rs)}
        for m in "EYZ":
            stats[f"median_p{m}"] = statistics.median(float(r[f"p{m}"]) for r in rs)
        assert all(value == summaries["paired_groups"][source][key] for key, value in stats.items())
        groups[source] = stats
    assert len(exact_drops) == summaries["paired_groups"]["holdout-k2"]["Y_decrease_at_least_0p2"] == 7
    for name in inherited_names:
        assert digest(OUT / name) == before[name]
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_seconds": time.perf_counter()-started,
        "registration_hashes_match": True,
        "inherited_evidence_sha256": before,
        "inherited_evidence_unchanged_during_audit": True,
        "source_files_checked": len(source_hashes), "source_hash_mismatches": mismatches,
        "parameter_instances": 20, "stored_rows_checked": len(rows),
        "fixed_decisions_from_stored_rows": {"T1": t1, "T2": t2, "T3": t3},
        "T2_examples": t2_examples,
        "condition_formula_max_relative_errors": {key: max(values) for key, values in errors.items()},
        "mode_max_point_error": mode_max, "mp_max_point_error": mp_max,
        "paired_summary_checks": groups,
        "holdout_drop_ge_one_fifth_exact_count": len(exact_drops),
        "holdout_exact_boundary_cases": threshold_cases,
        "original_holdout_P2_decisions_modified": False,
        "new_experiment_runs": 0, "new_local_searches": 0, "complete_solver_runs": 0,
        "limitation": "Validates saved records, formulas and hashes; does not rerun numerical solutions or validate original geometry-to-DSL equivalence.",
    }
    (OUT / "verification-resume.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ["audit_seconds", "source_files_checked", "stored_rows_checked",
                     "fixed_decisions_from_stored_rows", "condition_formula_max_relative_errors",
                     "holdout_drop_ge_one_fifth_exact_count", "new_experiment_runs"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
