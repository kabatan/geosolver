#!/usr/bin/env python3
"""Run one DSL case and emit only the solver's raw Phase C values.

Contest presentation transforms (for example AIME ``a+b``) deliberately do
not belong in this process.  The parent benchmark scores ``phasec.answer_values``
against the independently audited exact DSL target.
"""
import json
import sys
import time

from geosolver._internal.pipeline.contracts import ExternalPipelineConfig
from geosolver._internal.pipeline.orchestration.run_external_pipeline import run_external_pipeline


path, seed, budget = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
with open(path, encoding="utf-8") as stream:
    problem = json.load(stream)

# Some source-faithful records intentionally retain a figure-dependent clause
# that the current geometric IR cannot express without inventing coordinates.
# Keep these in the corpus and report them explicitly instead of letting an
# unconstrained numerical search manufacture a spurious answer.
if problem.get("solver_coverage", "").startswith("reference_only"):
    print(json.dumps({
        "status": "reference_only",
        "selected_answer": None,
        "accepted_answers": [],
        "accepted_count": 0,
        "elapsed_sec": 0.0,
        "phasec": {
            "accepted_count": 0,
            "answer_values": [],
            "rejected_false_positive_count": 0,
            "rejection_tags": ["source_clause_not_in_current_ir"],
        },
    }, ensure_ascii=False))
    raise SystemExit(0)


t0 = time.monotonic()
try:
    config = ExternalPipelineConfig.production_baseline_tier(
        seed=seed,
        total_time_budget_sec=budget,
    )
    result = run_external_pipeline(problem, pipeline_config=config)
    summary = result.summary if isinstance(result.summary, dict) else {}
    selected = result.selected_answer
    phasec = summary.get("phasec", {}) if isinstance(summary, dict) else {}
    print(json.dumps({
        "status": str(result.status),
        "selected_answer": str(selected) if selected is not None else None,
        "accepted_answers": [str(x) for x in result.accepted_answers],
        "accepted_count": int(getattr(result, "accepted_count", len(result.accepted_answers))),
        "elapsed_sec": time.monotonic() - t0,
        "phasec": phasec,
    }, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({
        "status": "exception",
        "error": repr(exc),
        "elapsed_sec": time.monotonic() - t0,
    }, ensure_ascii=False))
