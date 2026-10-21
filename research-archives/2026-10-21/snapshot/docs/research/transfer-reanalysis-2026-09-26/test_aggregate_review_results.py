"""Synthetic CPU-only checks for aggregate_review_results.py."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from aggregate_review_results import AggregateError, CONDITIONS, _canonical_sha256, aggregate  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fixture(root: Path) -> dict[str, object]:
    jobs = json.loads((HERE / "eval-jobs-v2.json").read_text(encoding="utf-8"))
    sources = root / "synthetic-sources"
    packet_dir = root / "numeric-packet"
    audit_dir = root / "answer-audit"
    math_grade_reused = root / "reused-grades.json"
    math_grade_remaining = root / "remaining-grades.json"
    answer_grades_path = root / "answer-grades.json"

    source_by_identity: dict[tuple[str, str], Path] = {}
    for condition in sorted(CONDITIONS):
        for job in jobs:
            path = sources / f"{condition}-{job['id']}.json"
            _write_json(path, {"synthetic_only": True, "identity": [condition, job["id"]]})
            source_by_identity[(condition, job["id"])] = path.resolve()

    numeric_cases = []
    numeric_key_cases = {}
    for case_id, condition, job in (
        ("math_case_000", "base", jobs[0]),
        ("math_case_001", "code128", jobs[1]),
    ):
        numeric_cases.append({"case_id": case_id, "construction_id": job["source_id"]})
        source = source_by_identity[(condition, job["id"])]
        numeric_key_cases[case_id] = {
            "condition": condition,
            "job_id": job["id"],
            "source_file": str(source),
            "source_file_sha256": _sha(source),
        }
    packet_value = {"schema": "blind-numeric-packet-v1", "cases": numeric_cases}
    packet_path = packet_dir / "grader" / "blind_numeric_packet.json"
    packet_bytes = (json.dumps(packet_value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    packet_path.parent.mkdir(parents=True)
    packet_path.write_bytes(packet_bytes)
    _write_json(packet_path.parent / "packet-manifest.json", {
        "schema": "blind-numeric-packet-manifest-v1",
        "packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
        "case_count": len(numeric_cases),
        "case_sha256": {case["case_id"]: _canonical_sha256(case) for case in numeric_cases},
    })
    _write_json(packet_dir / "private-key.json", {
        "schema": "blind-numeric-private-key-v1", "cases": numeric_key_cases,
    })
    (packet_path.parent / "GRADING_INSTRUCTIONS.md").write_text("Synthetic only.\n", encoding="utf-8")

    _write_json(math_grade_reused, {"schema": "numeric-math-grades-v1", "cases": [{
        "case_id": "math_case_000", "manual_numeric_status": "correct",
        "derivation_status": "valid", "contains_valid_core_derivation": True,
    }]})
    _write_json(math_grade_remaining, {"cases": {
        "math_case_001": {"numeric_correct": False, "derivation_status": "invalid",
                          "contains_valid_core_derivation": False},
    }})

    index_cases = []
    answer_key_cases = {}
    answer_grade_rows = []
    target_case_ids: dict[tuple[str, str], str] = {}
    audit_case_dir = audit_dir / "grader" / "cases"
    for index, condition in enumerate(sorted(CONDITIONS)):
        for job in jobs:
            case_id = f"audit_case_{index:02d}_{job['id']}"
            source = source_by_identity[(condition, job["id"])]
            answer_key_cases[case_id] = {
                "condition": condition,
                "job_id": job["id"],
                "source_file": str(source),
                "source_file_sha256": _sha(source),
            }
            auto_status = "incorrect"
            index_cases.append({
                "case_id": case_id,
                "case_file": f"cases/{case_id}.json",
                "auto_numeric_status": auto_status,
                "auto_numeric_correct": False,
            })
            case_path = audit_case_dir / f"{case_id}.json"
            _write_json(case_path, {"synthetic_only": True, "case_id": case_id})
            answer_grade_rows.append({
                "case_id": case_id,
                "parser_relation": "disagrees",
                "manual_format_corrected_status": "incorrect",
                "committed_answer": "synthetic-answer",
                "reason": "synthetic fixture",
            })
            target_case_ids[(condition, job["id"])] = case_id
    # A manual correction for an audited math case stays represented there; a
    # correction for a different source is queued for a new math review.
    for identity in (("base", jobs[0]["id"]), ("base", jobs[1]["id"])):
        row = next(row for row in answer_grade_rows if row["case_id"] == target_case_ids[identity])
        row["manual_format_corrected_status"] = "correct"
        row["committed_answer"] = "synthetic-correct-answer"

    index_path = audit_dir / "grader" / "blind_answer_audit.json"
    index_bytes = (json.dumps({"schema": "blind-answer-audit-v1", "cases": index_cases},
                              ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    index_path.write_bytes(index_bytes)
    case_hashes = {case_id: _sha(audit_case_dir / f"{case_id}.json")
                   for case_id in target_case_ids.values()}
    instruction_path = audit_dir / "grader" / "GRADING_INSTRUCTIONS.md"
    instruction_path.write_text("Synthetic only.\n", encoding="utf-8")
    _write_json(audit_dir / "grader" / "packet-manifest.json", {
        "schema": "blind-answer-audit-manifest-v1",
        "index_file": index_path.name,
        "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "case_count": len(index_cases),
        "case_file_sha256": case_hashes,
        "grading_instructions_sha256": _sha(instruction_path),
    })
    _write_json(audit_dir / "private-key.json", {
        "schema": "blind-answer-audit-private-key-v1", "cases": answer_key_cases,
    })
    _write_json(answer_grades_path, {"cases": answer_grade_rows})
    return {
        "packet_dir": packet_dir,
        "math_grades": [math_grade_reused, math_grade_remaining],
        "audit_dir": audit_dir,
        "answer_grades": answer_grades_path,
        "jobs": jobs,
    }


def _snapshot(roots: list[Path]) -> dict[str, str]:
    return {
        str(path): _sha(path)
        for root in roots
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class AggregateReviewResultsTests(unittest.TestCase):
    def test_aggregates_synthetic_grades_and_keeps_auto_score_primary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = _fixture(root)
            before = _snapshot([fixture["packet_dir"], fixture["audit_dir"], root / "synthetic-sources"])
            before.update({str(path): _sha(path) for path in [*fixture["math_grades"], fixture["answer_grades"]]})
            output = root / "aggregate-out"

            aggregate(
                fixture["packet_dir"], fixture["math_grades"], fixture["audit_dir"],
                fixture["answer_grades"], output,
            )

            result = json.loads((output / "aggregate.json").read_text(encoding="utf-8"))
            self.assertEqual(result["coverage"]["numeric_math"]["graded_cases"], 2)
            self.assertEqual(result["numeric_math"]["overall"]["numeric_status"],
                             {"correct": 1, "incorrect": 1, "unparsed": 0})
            self.assertEqual(result["numeric_math"]["overall"]["valid_core_and_numeric_correct"], 1)
            answer = result["answer_audit"]
            self.assertEqual(answer["overall"]["primary_auto_score"]["incorrect"], 96)
            self.assertEqual(answer["overall"]["manual_format_sensitivity"]["correct"], 2)
            self.assertEqual(len(answer["newly_manual_correct_without_math_packet"]), 1)
            queued = answer["newly_manual_correct_without_math_packet"][0]
            self.assertEqual(queued["condition"], "base")
            self.assertEqual(queued["job_id"], fixture["jobs"][1]["id"])
            after = _snapshot([fixture["packet_dir"], fixture["audit_dir"], root / "synthetic-sources"])
            for path in [*fixture["math_grades"], fixture["answer_grades"]]:
                after[str(path)] = _sha(path)
            self.assertEqual(before, after)

    def test_missing_grade_coverage_fails_before_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = _fixture(root)
            grades = json.loads(fixture["answer_grades"].read_text(encoding="utf-8"))
            grades["cases"].pop()
            _write_json(fixture["answer_grades"], grades)
            output = root / "must-not-exist"
            with self.assertRaisesRegex(AggregateError, "coverage is incomplete"):
                aggregate(
                    fixture["packet_dir"], fixture["math_grades"], fixture["audit_dir"],
                    fixture["answer_grades"], output,
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
