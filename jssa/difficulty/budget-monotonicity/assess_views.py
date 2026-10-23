"""Isolate unscorable error records without altering any normal grading input.

First the sealed executor attempts the original 40-run campaigns unchanged.
For a campaign that raised on engine_error diagnostics=null, keep that error
and all original raws. A separate 40-run grading view uses byte-identical links
for normal runs and manifest-derived null-result placeholders only for unknown
engine errors. The frozen assess_campaign function itself is never replaced.
"""
from __future__ import annotations

import json
import os
import resource
import traceback

import execute_stage2 as execution


def main():
    resource.setrlimit(resource.RLIMIT_FSIZE, (execution.LIMIT, execution.LIMIT))
    execution.verify()
    end = execution.read(execution.EXEC / "execution-end.json")
    if end["completed"] != 360:
        raise RuntimeError("all locked runs must finish before this analysis")
    all_jobs = execution.jobs()
    receipts = []
    for error in end["grading_errors"]:
        budget, seed = error["budget"], error["seed"]
        original = execution.BASE / f"campaign/t{budget}/s{seed}"
        view = execution.BASE / f"grading-views/t{budget}/s{seed}"
        if view.exists():
            raise RuntimeError("existing grading view is immutable")
        view.mkdir(parents=True)
        manifest_src = original / "campaign-manifest.json"
        manifest_dst = view / "campaign-manifest.json"
        os.link(manifest_src, manifest_dst)
        substitutions, identical = [], []
        for job in all_jobs:
            if job["time_limit_seconds"] != budget or job["seed"] != seed:
                continue
            rawpath = execution.raw_path(job)
            raw = execution.read(rawpath)
            target = view / "runs" / job["id"] / f"{seed}.json"
            target.parent.mkdir(parents=True)
            try:
                execution.rr.read_run_outcome(raw)
            except AttributeError:
                result = raw.get("solver_result") or {}
                if result.get("status") != "engine_error" or result.get("diagnostics") is not None:
                    raise
                issue = {"id": job["id"], "seed": seed, "budget": budget,
                         "original_raw_sha256": execution.sha(rawpath),
                         "original_status": result["status"], "reason": "unscorable engine error remains unknown",
                         "reader_exception": traceback.format_exc(), "solver_result_reconstructed": False}
                cpu = raw.get("process", {}).get("assigned_cpu")
                minimal = execution.minimal_raw(job, cpu, "original_grader_null_diagnostics_exception", raw.get("process"))
                minimal["q37_grading_view"] = issue
                execution.save(target, minimal, new=True)
                issue["view_raw_sha256"] = execution.sha(target)
                substitutions.append(issue)
            else:
                os.link(rawpath, target)
                identical.append({"id": job["id"], "sha256": execution.sha(target)})
        if len(substitutions) + len(identical) != 40:
            raise RuntimeError("grading view must retain the original 40-case manifest")
        execution.rr.CANONICAL_TIME_LIMIT_SECONDS = budget
        execution.rr.assess_campaign(view, cases_path=execution.ROOT / "benchmarks/cases.jsonl")
        rows = [json.loads(line) for line in (view / "assessment.jsonl").read_text().splitlines()]
        for row in rows:
            if row["case_id"] in {r["id"] for r in substitutions}:
                if row["normal_completion"] or row["matched"]:
                    raise RuntimeError("unknown placeholder was graded as a normal result")
        receipt = {"utc": execution.now(), "budget": budget, "seed": seed,
                   "original_grading_exception": error, "substitutions_for_unknown_only": substitutions,
                   "byte_identical_original_runs": identical, "manifest_sha256": execution.sha(manifest_dst),
                   "assessment_sha256": execution.sha(view / "assessment.jsonl"),
                   "frozen_grader_sha256": execution.sha(execution.ROOT / "benchmarks/research_runner.py"),
                   "solver_runs": 0, "original_raws_modified": False, "case_count": len(rows)}
        execution.save(view / "view-receipt.json", receipt, new=True)
        receipts.append({"budget": budget, "seed": seed, "unknown_placeholders": len(substitutions), "unchanged_runs": len(identical)})
    execution.save(execution.BASE / "grading-views-summary.json", {"utc": execution.now(), "views": receipts,
                   "script_sha256": execution.sha(__file__), "solver_runs": 0}, new=True)
    print(json.dumps(receipts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
