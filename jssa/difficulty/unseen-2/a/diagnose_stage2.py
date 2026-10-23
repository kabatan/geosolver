"""Read saved failed-run evidence only; no solver, search or PSLQ invocation."""
from __future__ import annotations

from collections import Counter
import json

from mpmath import mp
import sympy as sp

from execute_stage2 import BASE, DEST, now, read, save


def sampled_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return value.get("first_6", []) + value.get("last_2", [])
    return []


def main():
    references = read(BASE / "references.json")
    rows = []
    for path in sorted((DEST / "runs").glob("*/*.json")):
        raw = read(path)
        a = raw.get("assessment")
        if a is None or a["matched"]:
            continue
        cid = raw["case_id"]
        evidence = raw.get("diagnostic_evidence", {})
        pipeline = evidence.get("pipeline_summary", {})
        assembly = pipeline.get("exact_assembly", {})
        candidates = sampled_list(evidence.get("candidate_records"))
        exact_records = sampled_list(pipeline.get("exact_candidate_records"))
        samples = []
        with mp.workdps(500):
            reference = mp.mpf(str(sp.N(sp.sympify(references[cid]["geometric_value"]), 500)))
            for c in candidates:
                if not c.get("hard_feasible") or c.get("answer_hp") is None:
                    continue
                answer = mp.mpf(c["answer_hp"])
                relative_error = abs(answer - reference) / max(mp.mpf(1), abs(reference))
                samples.append({"candidate_id": c.get("candidate_id"), "hard_feasible": c["hard_feasible"],
                                "answer_precision_dps": c.get("answer_precision_dps"),
                                "answer_prefix": mp.nstr(answer, 30),
                                "relative_error_to_fixed_reference": mp.nstr(relative_error, 12)})
        exact_states = Counter(r.get("exact_result", {}).get("exact_status", "missing") for r in exact_records)
        rows.append({"case_id": cid, "seed": raw["seed"], "runner_failure_stage": a["failure_stage"],
                     "status": a["status"], "termination_reason": a["termination_reason"],
                     "rejection_tags": a["rejection_tags"], "n_public_answers": a["n_answers"],
                     "normal_completion": a["normal_completion"], "numeric_feasible_count": assembly.get("numeric_feasible_count"),
                     "exact_accepted_count": assembly.get("accepted_count"),
                     "rejected_false_positive_count": assembly.get("rejected_false_positive_count"),
                     "exact_result_states_in_preserved_sample": dict(exact_states),
                     "phase_timings": a["phase_timings"], "cpu_seconds": a["cpu_seconds"],
                     "sampled_hard_feasible_candidates": samples,
                     "fixed_geometric_reference": references[cid]["geometric_value"],
                     "fixed_official_output": references[cid]["official_output"],
                     "dsl_review_card": f"cards/{cid}.md", "dsl_witness_audit": "audit/substitution.json",
                     "approximate_match_does_not_change_score": True})
    result = {"created_at_utc": now(), "solver_executions": 0, "local_search_executions": 0, "PSLQ_executions": 0,
              "method": "Read preserved diagnostics and compare already-returned candidate numbers to fixed reference at 500 decimal digits; never rerun or repair a case.",
              "limitation": "Candidate samples are compact evidence, not every search iterate. Approximation is diagnostic only and is not exact-set scoring.",
              "failed_runs": rows}
    save(BASE / "failure-analysis.json", result)
    print(json.dumps({"failed_runs": len(rows), "solver_executions": 0,
                      "rows": [{k: r[k] for k in ("case_id", "seed", "runner_failure_stage", "numeric_feasible_count",
                                                  "phase_timings", "sampled_hard_feasible_candidates")} for r in rows]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
