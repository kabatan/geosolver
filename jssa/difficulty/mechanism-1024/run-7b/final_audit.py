"""Read-only regrading and integrity audit after all 648 registered solves."""
import csv
import gzip
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
SCRATCH = Path(M["scratch"])
sys.path[:0] = [str(Path(M["frozen_grader"]) / "src"), M["frozen_grader"]]
from benchmarks.research_runner import _answer_keys, read_run_outcome


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    revision = json.loads((OUT / "reporting-revision.json").read_text())
    allowed_reporting_change = str(OUT / "analyze.py")
    for path, expected in M["files"].items():
        if path == allowed_reporting_change:
            assert sha(revision["pre_run_copy"]) == expected == revision["pre_run_sha256"]
            assert sha(path) == revision["current_sha256"]
        else:
            assert sha(path) == expected, path
    for relative, expected in M["source_files"].items():
        assert sha(Path(M["clean_source"]) / relative) == expected, relative
    for problem in M["inputs"]:
        assert sha(problem["dsl_path"]) == sha(problem["input_copy"]) == problem["sha256"]
    fixed = subprocess.check_output(["git", "show", "00d2ac95:jssa/difficulty/mechanism-1024/problem-set/problem-set.json"])
    assert fixed == (OUT.parent / "problem-set/problem-set.json").read_bytes()
    assert not subprocess.check_output(["git", "-C", "/tmp/switch-impl", "status", "--porcelain"]).strip()
    assert subprocess.check_output(["git", "-C", "/tmp/switch-impl", "rev-parse", "HEAD"], text=True).strip() == M["source_commit"]
    rows = [json.loads(p.read_text()) for p in SCRATCH.glob("runs/*/*/*/record.json")]
    assert len(rows) == 648
    expected_keys = {(p["case_id"], s, a) for p in M["inputs"] for s in M["seeds"] for a in M["arms"]}
    assert {(r["case_id"], r["seed"], r["arm"]) for r in rows} == expected_keys
    assert len(list(SCRATCH.glob("runs/*/*/*/start.json"))) == 648
    truth = {p["case_id"]: p["expected_keys"] for p in M["inputs"]}
    events = []
    stage_missing = Counter()
    status_counts = Counter()
    selection_calls = 0
    missing_worker_identity = []
    for row in rows:
        assert sha(row["raw_path"]) == row["raw_sha256"]
        with gzip.open(row["raw_path"], "rt") as stream:
            raw = json.load(stream)
        outcome = read_run_outcome(raw)
        actual = _answer_keys(raw.get("solver_result"))
        match = bool(raw.get("solver_result") and outcome["normal_completion"] and actual == truth[row["case_id"]])
        assert match == row["matched"]
        assert not row["execution_contract_issues"], row
        assert row["probe_available"], row
        if row["source_hash"] is not None:
            assert row["actual_affinity"] == [row["cpu"]], row
            assert row["source_hash"] == M["source_hash"], row
        else:
            assert not row["normal_completion"]
            missing_worker_identity.append([row["case_id"], row["seed"], row["arm"], row["status"]])
        if row["arm"] == "NO_RESIDUAL_REWRITE":
            assert row["smooth_calls"] == 0
        if row["arm"] == "NO_DIVERSE_SELECTION":
            for event in raw["probe_events"]:
                if event["kind"] == "selection":
                    selection_calls += 1
                    assert event["selected"] <= 20
                    assert event["norms"] == sorted(event["norms"])
        summary = (((raw.get("solver_result") or {}).get("worker_artifact") or {}).get("diagnostics") or {}).get("pipeline_summary") or {}
        for key in ("search_staged_fallback", "phase_rescue", "initial_probe", "refinement"):
            if key not in summary:
                stage_missing[key] += 1
        events.extend([(row["started_utc"], 1), (row["ended_utc"], -1)])
        status_counts[row["category"]] += 1
    active = maximum = 0
    for _, delta in sorted(events):
        active += delta
        maximum = max(maximum, active)
    assert active == 0 and maximum <= 16
    # Re-run only the original reporting code on existing raw; no solver calls.
    namespace = {"__name__": "original_reporting", "__file__": str(OUT / "analyze.py")}
    original_code = Path(revision["pre_run_copy"]).read_text()
    exec(compile(original_code, revision["pre_run_copy"], "exec"), namespace)
    original_reports = SCRATCH / "original-report-audit"
    original_reports.mkdir(exist_ok=True)
    namespace["OUT"] = original_reports
    original_write_csv = namespace["write_csv"]
    core_fields = ("case_id", "seed", "arm", "matched", "category", "C", "wall_seconds", "smooth_calls", "selected_candidates")
    def write_original_core(name, values):
        if name == "per-run.csv":
            values = [{k: value[k] for k in core_fields} for value in values]
        original_write_csv(name, values)
    namespace["write_csv"] = write_original_core
    namespace["main"]()
    assert json.loads((original_reports / "summary.json").read_text()) == json.loads((OUT / "summary.json").read_text())
    assert (original_reports / "per-problem.csv").read_bytes() == (OUT / "per-problem.csv").read_bytes()
    original_rows = list(csv.DictReader((original_reports / "per-run.csv").open()))
    export_rows = list(csv.DictReader((OUT / "per-run.csv").open()))
    for first, second in zip(original_rows, export_rows, strict=True):
        for key in ("case_id", "seed", "arm", "matched", "category", "C", "wall_seconds", "smooth_calls", "selected_candidates"):
            assert first[key] == second[key], key
    oversized = [str(p) for p in OUT.rglob("*") if p.is_file() and p.stat().st_size > 3_000_000]
    assert not oversized, oversized
    report = {"completed_utc": datetime.now(timezone.utc).isoformat(), "runs": len(rows),
              "distinct_registered_keys": len(expected_keys), "solver_start_receipts": 648,
              "maximum_observed_concurrency": maximum, "fixed_pool_size": 16,
              "source_and_input_hashes_unchanged": True, "switch_impl_unchanged_clean": True,
              "frozen_regrading_matches": True, "original_reporting_verdicts_and_per_problem_identical": True,
              "original_reporting_core_per_run_fields_identical": True,
              "execution_contract_issues": 0, "probe_missing": 0,
              "missing_worker_identity": missing_worker_identity,
              "residual_only_selection_calls_checked": selection_calls,
              "categories": dict(status_counts), "stage_summary_missing": dict(stage_missing),
              "oversized_repository_files": oversized, "audit_script_sha256": sha(__file__)}
    (OUT / "final-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
