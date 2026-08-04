#!/usr/bin/env python3
"""Fail-fast consistency checks for the manually audited corpus."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(name: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def audit_lookup(audits: list[dict]) -> dict[str, dict]:
    """Index canonical IDs, source-row IDs, and DSL stems to one audit row."""
    lookup: dict[str, dict] = {}
    for row in audits:
        keys = [row.get("problem_id"), row.get("dedupe_key")]
        if row.get("dsl_path"):
            keys.append(Path(row["dsl_path"]).stem)
        for key in keys:
            if key:
                lookup[key] = row
    return lookup


def main() -> None:
    rows = read("all_geometry.jsonl")
    inventory = read("scope_inventory.jsonl")
    audits = read("manual_audit.jsonl")
    assert len(rows) == len(inventory) == len(audits) == 548
    assert len({r["problem_id"] for r in rows}) == len(rows)
    source_by_id = {r["problem_id"]: r.get("source_statement", "") for r in audits}
    source_by_dedupe = {}
    for r in audits:
        source_by_dedupe.setdefault(r["dedupe_key"], r.get("source_statement", ""))
    audit_by_key = audit_lookup(audits)
    assert all(r.get("manual_audit") is True for r in rows)
    assert all(r["scope_status"] in {"in_scope", "out_scope", "metadata_only"} for r in rows)
    assert all(r["scope_status"] != "in_scope" or r.get("dedupe_key") for r in rows)
    unique_scope = {r["dedupe_key"] for r in inventory if r["scope_status"] == "in_scope"}
    assert len(unique_scope) == 296
    expected = {"AIME": 108, "HMMT": 132, "JMO preliminary": 56}
    for contest, count in expected.items():
        got = {r["dedupe_key"] for r in inventory if r["contest"] == contest and r["scope_status"] == "in_scope"}
        assert len(got) == count, (contest, len(got), count)
    dsl_dir = ROOT / "dsl"
    ready = [r for r in inventory if r["scope_status"] == "in_scope" and r["dsl_status"] == "ready"]
    dsl_files = {p.name for p in dsl_dir.glob("*.json")}
    cases = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in dsl_dir.glob("*.json")}
    case_stems = {Path(name).stem for name in cases}
    assert len({r["dsl_path"] for r in ready}) == len(dsl_files)
    assert all(Path(r["dsl_path"]).name in dsl_files for r in ready)
    assert all(r["dsl_status"] != "pending_source_faithful_encoding" for r in inventory)
    assert all(r["dsl_status"] != "pending_official_image_transcription" for r in inventory)
    for r in ready:
        p = ROOT / r["dsl_path"]
        assert p.exists(), p
        case = json.loads(p.read_text(encoding="utf-8"))
        assert case["id"] in {r["problem_id"], r["dedupe_key"]}
        audit = audit_by_key.get(case["id"])
        assert audit is not None, case["id"]
        assert audit["scope_status"] == "in_scope", case["id"]
        expected_source = source_by_id.get(case["id"], source_by_dedupe.get(case["id"]))
        assert expected_source is not None
        assert case.get("source_statement", "") == expected_source, case["id"]
        assert case.get("clause_ledger"), case["id"]
        assert case.get("source_statement"), case["id"]
        assert "published_answer" not in case and "expected_answer" not in case, case["id"]
    reference_files = {
        name for name, case in cases.items()
        if str(case.get("solver_coverage", "")).startswith("reference_only")
    }
    runnable_unique = {
        r["dedupe_key"] for r in ready
        if Path(r["dsl_path"]).name not in reference_files
    }
    assert len(dsl_files) == 302
    assert len(reference_files) == 17
    assert len(runnable_unique) == 279
    assert all(
        r["scope_status"] == "in_scope"
        or r["dsl_status"] in {"not_applicable", "metadata_only"}
        for r in inventory
    )

    # The final 180-second/one-core benchmark is the authoritative result for
    # the current DSL.  The older 3-second artifact remains available for
    # historical comparison, but its answer ledger predates the corrected
    # HMMT-2006 entry and must not gate the final corpus check.
    benchmark = json.loads((ROOT / "benchmark_results_180s_1core_final.json").read_text(encoding="utf-8"))
    benchmark_rows = benchmark["results"]
    assert benchmark["cases"] == len(dsl_files) == 302
    assert benchmark["runs"] == len(benchmark_rows) == len(dsl_files)
    assert benchmark["seeds"] == [7]
    assert benchmark["budget_sec"] == 180.0
    assert benchmark["jobs"] == 1
    assert benchmark["hard_timeout"] is True
    assert benchmark["cpu_affinity"] == [0]
    assert benchmark["one_core_enforced"] is True
    assert {r["case_id"] for r in benchmark_rows} == case_stems
    assert all(r["seed"] == 7 for r in benchmark_rows)
    assert all(r.get("expected_answer") == audit_by_key[r["case_id"]].get("published_answer") for r in benchmark_rows)
    status_counts = Counter(r.get("status") for r in benchmark_rows)
    assert status_counts == Counter({"success": 232, "no_solution": 36, "reference_only": 17, "timeout": 13, "exception": 4})
    assert benchmark["runnable_cases"] == 285
    assert benchmark["reference_only_cases"] == 17
    assert benchmark["success_runs"] == status_counts["success"]
    assert benchmark["no_solution_runs"] == status_counts["no_solution"]
    assert benchmark["reference_only_runs"] == status_counts["reference_only"]
    assert benchmark["exception_runs"] == status_counts["exception"]
    assert benchmark["timeout_runs"] == status_counts["timeout"]
    assert benchmark["correct_runs"] == sum(r.get("answer_match") is True for r in benchmark_rows) == 165
    assert benchmark["complete_answer_set_runs"] == sum(r.get("answer_set_complete") is True for r in benchmark_rows) == 128
    reference_case_ids = {Path(name).stem for name in reference_files}
    assert {r["case_id"] for r in benchmark_rows if r["status"] == "reference_only"} == reference_case_ids
    assert all(r["status"] != "reference_only" for r in benchmark_rows if r["case_id"] not in reference_case_ids)
    expected_total = sum(bool(audit_by_key[name].get("published_answer")) for name in case_stems)
    expected_runnable = sum(
        bool(audit_by_key[name].get("published_answer"))
        for name in case_stems
        if name not in reference_case_ids
    )
    assert (expected_total, expected_runnable) == (212, 206)
    assert sum(bool(r.get("status") == "success" and r.get("expected_answer")) for r in benchmark_rows) == 171
    print(json.dumps({
        "all_records": len(rows),
        "unique_scope": len(unique_scope),
        "dsl_ready_source_rows": len(ready),
        "dsl_files": len(dsl_files),
        "current_solver_scope_unique": len(runnable_unique),
        "reference_only_files": len(reference_files),
        "benchmark_runs": len(benchmark_rows),
        "benchmark_status_counts": dict(status_counts),
        "benchmark_correct_runs": benchmark["correct_runs"],
        "benchmark_complete_answer_set_runs": benchmark["complete_answer_set_runs"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
