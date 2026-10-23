"""Read-only scoring of saved solver evidence; writes only derived reports here."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import sympy as sp
from mpmath import mp
from pydantic import TypeAdapter

from geosolver.problem.models import ExactAnswer
import run_experiment as experiment

OUT = Path(__file__).resolve().parent


def dump(name, value):
    experiment.dump(OUT / name, value)


def main():
    experiment.verify_lock()
    references = json.loads((OUT / "references.json").read_text())
    local = json.loads((OUT / "local-results.json").read_text())
    baseline = local["R1"]["rows"]
    local_summary = []
    for case_id in experiment.MAIN:
        data = local[case_id]
        rows = data["rows"]
        exact = sum((a.get("x"), a.get("residual"), a.get("evaluations")) ==
                    (b.get("x"), b.get("residual"), b.get("evaluations"))
                    for a, b in zip(rows, baseline))
        maxdiff = max(abs(x-y) for a, b in zip(rows, baseline) for x, y in zip(a["x"], b["x"]))
        local_summary.append({"id": case_id, "n": len(rows), "hits": sum(r["class"] == "hit" for r in rows),
                              "bitwise_endpoint_residual_evaluation_matches": exact,
                              "max_coordinate_difference": maxdiff,
                              "max_residual": max(r["residual"] for r in rows),
                              "evaluations": [r["evaluations"] for r in rows], "bounds": data["bounds"]})
    dump("local-summary.json", local_summary)
    adapter = TypeAdapter(ExactAnswer)
    all_rows = []
    with mp.workdps(220):
        # Each multi-quadratic reference is the unique largest conjugate (all positive signs).
        # CUBIC has exactly one real root. This independently fixes the root index.
        expected = {case_id: ("algebraic", tuple(str(c) for c in r["coefficients"]),
                              0 if case_id == "CUBIC" else r["degree"]-1)
                    for case_id, r in references.items()}
        decimals = {case_id: mp.mpf(str(sp.N(sp.sympify(r["expression"]), 180))) for case_id, r in references.items()}
        for case_id in experiment.IDS:
            for seed in experiment.SEEDS:
                folder = OUT / "runs-180" / f"{case_id}-{seed}"
                process = json.loads((folder / "execution.json").read_text())
                data = json.loads((folder / "result.json").read_text()) if (folder / "result.json").exists() else {}
                diagnostic = data.get("diagnostics", {})
                answers = data.get("answers", [])
                keys = [adapter.validate_python(a).canonical_key() for a in answers]
                exact_correct = keys == [expected[case_id]]
                ref = decimals[case_id]
                interval_contains_reference = []
                for answer in answers:
                    if answer["kind"] != "algebraic":
                        interval_contains_reference.append(False)
                        continue
                    a,b = answer["value"]["isolating_interval"]
                    def fraction(text):
                        num, den = sp.Rational(text).as_numer_denom()
                        return mp.mpf(int(num))/mp.mpf(int(den))
                    interval_contains_reference.append(fraction(a) <= ref <= fraction(b))
                candidates = diagnostic.get("candidate_records", [])
                numeric = []
                for candidate in candidates:
                    if candidate.get("answer_hp") is None:
                        continue
                    err = abs(mp.mpf(candidate["answer_hp"])-ref)/max(1,abs(ref))
                    verified = any(v.get("verified") is True and v.get("hard_feasible") is True
                                   for v in candidate.get("verification_history", []))
                    unc = candidate.get("answer_uncertainty")
                    valid_unc = unc is not None and mp.isfinite(mp.mpf(unc)) and mp.mpf(unc) >= 0
                    numeric.append({
                        "relative_reference_error": mp.nstr(err, 8),
                        "matches_60": bool(err <= mp.mpf("1e-60")),
                        "matches_100": bool(err <= mp.mpf("1e-100")),
                        "has_successful_numerical_verification": verified,
                        "hard_feasible": candidate.get("hard_feasible"),
                        "answer_precision_dps": candidate.get("answer_precision_dps"),
                        "relative_uncertainty": mp.nstr(mp.mpf(unc)/max(1,abs(ref)),8) if valid_unc else None,
                        "origin_backend": (candidate.get("source") or {}).get("origin_backend"),
                        "residual": candidate.get("residual_norm_hp"),
                    })
                confirmed = [c for c in numeric if c["matches_60"] and c["has_successful_numerical_verification"] and c["hard_feasible"] is True]
                summary = diagnostic.get("pipeline_summary", {})
                exact_records = summary.get("exact_candidate_records", [])
                methods = sorted({r.get("exact_result",{}).get("identification_method", "unknown") for r in exact_records})
                row = {
                    "id": case_id, "seed": seed, "degree": references[case_id]["degree"],
                    "status": data.get("status", "no_artifact"), "exact_correct": exact_correct,
                    "interval_contains_reference": bool(interval_contains_reference) and all(interval_contains_reference),
                    "numeric_confirmed": bool(confirmed), "candidates_matching_100": sum(c["matches_100"] for c in confirmed),
                    "candidate_count": len(candidates), "numeric_candidates": numeric,
                    "solver_seconds": data.get("elapsed_seconds"), "wall_seconds": process["elapsed_seconds"],
                    "termination": data.get("termination_reason"), "returncode": process["returncode"],
                    "outer_timeout": process["outer_timeout"],
                    "identification_methods": methods,
                    "rejection_tags": diagnostic.get("rejection_tags", []),
                    "phase_timings": diagnostic.get("phase_timings", {}),
                    "resource_request": data.get("requested_resources", {}),
                }
                all_rows.append(row)
        dump("scored-runs.json", all_rows)
        compact = [{k: v for k, v in row.items() if k not in {"numeric_candidates", "phase_timings", "resource_request"}}
                   for row in all_rows]
        for row in compact:
            for key in ("identification_methods", "rejection_tags"):
                row[key] = ";".join(row[key])
        with (OUT / "per-run.csv").open("w",newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(compact[0]))
            writer.writeheader()
            writer.writerows(compact)
        by_id = {}
        for case_id in experiment.IDS:
            rows = [r for r in all_rows if r["id"] == case_id]
            by_id[case_id] = {"runs": len(rows), "exact_correct": sum(r["exact_correct"] for r in rows),
                              "numeric_confirmed": sum(r["numeric_confirmed"] for r in rows),
                              "seconds": [r["solver_seconds"] for r in rows],
                              "methods": sorted({m for r in rows for m in r["identification_methods"]})}
        p1 = all(r["n"] == r["hits"] == r["bitwise_endpoint_residual_evaluation_matches"] == 16 for r in local_summary)
        controls = ["R1","R2","R3","DEP","S5","S13","S17"]
        p2 = all(by_id[i]["exact_correct"] == 2 for i in controls) and by_id["R4"]["exact_correct"] == 0 and by_id["R4"]["numeric_confirmed"] == 2
        identify = {}
        for mode in ("plain", "hint"):
            folder = OUT / "identification-180" / mode
            path = folder / "result.json"
            result = json.loads(path.read_text()) if path.exists() else {}
            same = result.get("selected_exact_value") is not None and sp.simplify(sp.sympify(result["selected_exact_value"])-sp.sympify(references["R4"]["expression"])) == 0
            identify[mode] = {"has_result": bool(result), "exact_status": result.get("exact_status"),
                              "method": result.get("identification_method"), "correct": bool(same),
                              "seconds": result.get("seconds"),
                              "execution": json.loads((folder/"execution.json").read_text()) if (folder/"execution.json").exists() else None}
        p5 = identify["plain"]["has_result"] and identify["plain"]["exact_status"] != "identified" and identify["hint"]["correct"]
        summary = {"local_calls": sum(r["n"] for r in local_summary), "local_hits": sum(r["hits"] for r in local_summary),
                   "full_calls": len(all_rows), "cli_setup_failures_before_correction": 20,
                   "full_exact_correct": sum(r["exact_correct"] for r in all_rows), "by_id": by_id,
                   "P1": p1, "P2_at_180_seconds": p2, "P3_at_180_seconds": by_id["FIXED4"]["exact_correct"] == 2,
                   "P4_at_180_seconds": by_id["CUBIC"]["exact_correct"] == 2,
                   "P5": bool(p5), "identification": identify,
                   "source_hash": experiment.source_hash(),
                   "references_are_independent_of_solver_outputs": True,
                   "reference_root_index_reason": "Largest real conjugate for each positive multiquadratic sum; the cubic has exactly one real root.",
                   "numeric_check_digits": 100, "canonical_identity_checked": True}
        dump("summary.json", summary)
        print(json.dumps({k:v for k,v in summary.items() if k not in {"identification","source_hash"}}, ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
