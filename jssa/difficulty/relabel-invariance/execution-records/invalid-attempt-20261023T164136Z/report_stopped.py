"""Summarize the halted Q38 execution without solving or changing its grading.

All planned cells are retained. Contract-invalid and unattempted cells have no
correctness value. Detailed solver artifacts remain outside the checkout.
"""
from __future__ import annotations

import collections
import csv
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import stage2

BASE = Path(__file__).resolve().parent
EXTERNAL = stage2.EXTERNAL


def write_json(path, value):
    stage2.save(path, value)


def write_csv(path, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8", newline="")


def counts(records, field):
    return dict(sorted(collections.Counter(str(row.get(field)) for row in records).items()))


def main():
    lock_checks = {str(p): stage2.check_lock(p) for p in (BASE, stage2.INPUT)}
    plan = stage2.read(BASE / "execution-plan.json")
    receipts = [stage2.read(p) for p in sorted((EXTERNAL / "receipts").glob("*.json"))]
    preflight = stage2.read(EXTERNAL / "preflight.json")
    start = stage2.read(EXTERNAL / "execution-start.json")
    probe = (
        "import json,geosolver;from geosolver.runtime.integrity import source_tree_hash;"
        "print(json.dumps({'import_file':geosolver.__file__,'source_hash':source_tree_hash()}))"
    )
    command = [str(stage2.PYTHON), "-B", "-c", probe]
    parent_probe = json.loads(subprocess.check_output(command, cwd=stage2.CLEAN, env=stage2.environment(), text=True))
    with tempfile.TemporaryDirectory(prefix="q38-import-only-") as temporary:
        child_probe = json.loads(subprocess.check_output(command, cwd=temporary, env=stage2.environment(), text=True))
    pth = stage2.PYTHON.parent.parent / "lib/python3.12/site-packages/_editable_impl_geosolver.pth"
    write_json(BASE / "import-diagnostic.json", {
        "recorded_at_utc": stage2.now(), "solver_calls": 0, "operation": "import only; no solver entrypoint called",
        "argv": command, "PYTHONPATH": stage2.environment()["PYTHONPATH"],
        "clean_cwd": str(stage2.CLEAN), "clean_cwd_probe": parent_probe,
        "temporary_cwd_probe": child_probe, "editable_pth_path": str(pth),
        "editable_pth_content": pth.read_text(),
        "cause": "Relative PYTHONPATH=src does not identify the checkout after the worker switches to a temporary cwd; editable-install .pth supplies /home/kabatan/work/solver/src instead.",
    })
    rows, diagnostics, raw_manifest = [], [], []
    for batch in plan["batches"]:
        _, dest, _ = stage2.paths(batch["batch"])
        for identifier in batch["case_ids"]:
            path = dest / "runs" / identifier / f"{batch['seed']}.json"
            row = {
                "batch": batch["batch"], "block": batch["block"], "id": identifier,
                "mode": batch["mode"], "seed": batch["seed"],
                "state": "not_started", "matched": None, "assessment_available": False,
                "contract_issues": None, "solver_status_ungraded": None,
                "wall_seconds_ungraded": None, "process_wall_seconds": None,
                "cpu_seconds": None, "assigned_cpu": None,
                "actual_import_root": None, "raw_bytes": None, "raw_sha256": None,
            }
            if path.exists():
                raw = stage2.read(path)
                result = raw.get("solver_result") or {}
                diag = result.get("diagnostics", {})
                info = diag.get("process_info", {})
                process = raw.get("process", {})
                issues = raw.get("execution_contract_issues", [])
                summary = diag.get("pipeline_summary", {})
                candidates = diag.get("candidate_records", [])
                row.update(
                    state="contract_invalid" if issues else "unassessed",
                    contract_issues=";".join(issues), solver_status_ungraded=result.get("status"),
                    wall_seconds_ungraded=result.get("elapsed_seconds"),
                    process_wall_seconds=process.get("elapsed_seconds"),
                    cpu_seconds=info.get("cpu_seconds"), assigned_cpu=process.get("assigned_cpu"),
                    actual_import_root=info.get("import_root"), raw_bytes=path.stat().st_size,
                    raw_sha256=stage2.sha(path),
                )
                raw_manifest.append({"path": str(path), "bytes": row["raw_bytes"], "sha256": row["raw_sha256"]})
                diagnostics.append({
                    "case_id": identifier, "mode": batch["mode"], "seed": batch["seed"],
                    "state": row["state"], "matched": None, "answers_are_ungraded": True,
                    "answers_returned": result.get("answers"),
                    "execution_contract_issues": issues, "engine": result.get("engine"),
                    "config": raw.get("config"), "process": process, "process_info": info,
                    "phase_timings": diag.get("phase_timings", {}),
                    "counters": diag.get("counters", {}),
                    "candidate_source_counts": counts(candidates, "source"),
                    "accepted_candidate_source_counts": counts([c for c in candidates if c.get("accepted")], "source"),
                    "rejection_tags": diag.get("rejection_tags", []),
                    "search_summary": summary.get("search"),
                    "refinement_summary": summary.get("refinement"),
                    "exact_assembly_summary": summary.get("exact_assembly"),
                    "fallback_summary": summary.get("search_staged_fallback"),
                })
            rows.append(row)
    write_csv(BASE / "runs.csv", rows)
    write_json(BASE / "invalid-run-diagnostics.json", diagnostics)
    selection = list(csv.DictReader((BASE / "selection.csv").open()))
    problems = []
    for selected in selection:
        subset = [r for r in rows if r["id"] == selected["id"]]
        problems.append({
            **selected, "planned_runs": len(subset),
            "attempted_runs": sum(r["state"] != "not_started" for r in subset),
            "contract_invalid_runs": sum(r["state"] == "contract_invalid" for r in subset),
            "unattempted_runs": sum(r["state"] == "not_started" for r in subset),
            "valid_assessed_runs": 0, "A": None, "T": None,
            "timing_comparable_pairs": 0, "determination": "not_estimable_incomplete_campaign",
        })
    write_csv(BASE / "per-problem.csv", problems)
    strata = []
    for dimension, p_stratum in sorted({(p["dimension_stratum"], p["p_stratum"]) for p in problems}):
        group = [p for p in problems if (p["dimension_stratum"], p["p_stratum"]) == (dimension, p_stratum)]
        strata.append({
            "dimension_stratum": dimension, "p_stratum": p_stratum, "problems": len(group),
            "planned_runs": sum(p["planned_runs"] for p in group),
            "attempted_runs": sum(p["attempted_runs"] for p in group),
            "contract_invalid_runs": sum(p["contract_invalid_runs"] for p in group),
            "valid_assessed_runs": 0, "A_count": None, "T_count": None,
            "determination": "not_estimable_incomplete_campaign",
        })
    write_csv(BASE / "per-stratum.csv", strata)
    state_counts = counts(rows, "state")
    load_samples = [{"at_utc": start["execution_started_at_utc"], "loadavg": start["loadavg"]}]
    for receipt in receipts:
        load_samples.extend({"at_utc": s["at_utc"], "loadavg": s["loadavg"]} for s in receipt.get("load_samples", []))
        if receipt.get("final_loadavg"):
            load_samples.append({"at_utc": receipt["finished_at_utc"], "loadavg": receipt["final_loadavg"]})
    overview = {
        "task": "Q38", "status": "stopped_execution_contract_violation",
        "generated_at_utc": stage2.now(), "execution_started_at_utc": start["execution_started_at_utc"],
        "execution_stopped_at_utc": receipts[-1]["finished_at_utc"],
        "planned_problems": 40, "planned_runs": 840, "planned_batches": 210,
        "attempted_batches": len(receipts), "completed_batches": sum(r.get("state") == "complete" for r in receipts),
        "run_state_counts": state_counts, "solver_calls": len(diagnostics),
        "valid_assessed_runs": 0, "graded_correct": None, "graded_incorrect": None,
        "missing_artifacts_among_attempted_runs": 0,
        "A_count": None, "A_fraction_of_40": None, "T_count": None,
        "T_fraction_of_40": None, "time_comparable_problems": 0,
        "original_repeat_comparisons": 0, "predictions_tested": False,
        "reason": "All four runs in batch 0 have executed_import_root_mismatch; runner exited 2 before assess/summarize. No retries or later batches.",
        "required_import_root": str(stage2.CLEAN / "src/geosolver"),
        "observed_import_roots": sorted({r["actual_import_root"] for r in rows if r["actual_import_root"]}),
        "source_hashes_match": all(d["engine"]["source_hash"] == preflight["runtime_fingerprint"]["source_hash"] for d in diagnostics),
        "cpus": preflight["cpus"], "topology": preflight["topology"],
        "load_samples": load_samples,
        "loadavg_min": [min(s["loadavg"][i] for s in load_samples) for i in range(3)],
        "loadavg_max": [max(s["loadavg"][i] for s in load_samples) for i in range(3)],
        "file_limit_bytes": 4900000,
        "max_saved_raw_bytes": max((r["bytes"] for r in raw_manifest), default=0),
        "raw_manifest": raw_manifest, "raw_data_copied_to_repository": False,
        "prediction_rules_selection_plan_changes": False,
        "lock_checks_after_execution": lock_checks,
        "q34_comparison": "Not testable: no valid original/transformation/repeat pairs. No evidence for or against initial-condition or fractal sensitivity.",
    }
    write_json(BASE / "results-summary.json", overview)
    records = BASE / "execution-records"
    records.mkdir(exist_ok=True)
    for name in ("preflight.json", "execution-start.json", "resume-audit.json"):
        shutil.copyfile(EXTERNAL / name, records / name)
    for path in sorted((EXTERNAL / "receipts").glob("*")):
        if path.is_file():
            shutil.copyfile(path, records / path.name)
    print(json.dumps({"status": overview["status"], "states": state_counts, "rows": len(rows), "problems": len(problems)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
