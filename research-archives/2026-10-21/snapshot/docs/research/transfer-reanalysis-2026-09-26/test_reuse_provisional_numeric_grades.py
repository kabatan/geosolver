"""Synthetic CPU-only checks for provisional numeric grade reuse."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prepare_blind_numeric import GRADING_INSTRUCTIONS, PacketError, _canonical_sha256
from reuse_provisional_numeric_grades import reuse_grades


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_case(case_id: str, *, cap: int = 32768) -> dict:
    return {
        "case_id": case_id,
        "construction_id": "synthetic-construction",
        "messages": [{"role": "user", "content": "Synthetic fixture prompt; no answer is evaluated."}],
        "expected_numeric": "synthetic-label",
        "final_text": "Synthetic generated portion.",
        "raw_response": "Synthetic response only.",
        "selected_cap": cap,
        "finish_reason": "stop",
    }


def _write_packet_dir(
    root: Path,
    name: str,
    cases: list[dict],
    source_paths: dict[str, Path],
    *,
    provisional: bool,
    grades: list[dict] | None = None,
) -> Path:
    out = root / name
    grader = out / "grader"
    grader.mkdir(parents=True)
    packet = {"schema": "blind-numeric-packet-v1", "cases": cases}
    packet_bytes = (json.dumps(packet, ensure_ascii=False, indent=2) + "\n").encode()
    packet_path = grader / "blind_numeric_packet.json"
    packet_path.write_bytes(packet_bytes)
    case_hashes = {case["case_id"]: _canonical_sha256(case) for case in cases}
    manifest = {
        "schema": "provisional-blind-numeric-manifest-v1" if provisional else "blind-numeric-packet-manifest-v1",
        "packet_sha256": _sha(packet_bytes),
        "case_count": len(cases),
        "case_sha256": case_hashes,
    }
    (grader / "packet-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (grader / "GRADING_INSTRUCTIONS.md").write_text(GRADING_INSTRUCTIONS)

    private_cases = {}
    for case in cases:
        source = source_paths[case["case_id"]].resolve()
        entry = {"source_file": str(source), "source_file_sha256": _sha(source.read_bytes())}
        if provisional:
            entry.update({"job_id": f"synthetic-job-{case['case_id']}", "condition": "synthetic-condition"})
        else:
            entry.update({"job_id": f"synthetic-job-{case['case_id']}", "condition": "synthetic-condition"})
        private_cases[case["case_id"]] = entry
    private_key = {
        "schema": "provisional-blind-numeric-private-key-v1" if provisional else "blind-numeric-private-key-v1",
        "cases": private_cases,
    }
    if provisional:
        private_key["source_condition"] = "synthetic-condition"
    (out / "private-key.json").write_text(json.dumps(private_key, indent=2) + "\n")
    if provisional:
        grade_doc = {"schema": "numeric-math-grades-v1", "cases": grades or []}
        (grader / "numeric-math-grades.json").write_text(json.dumps(grade_doc, indent=2) + "\n")
    return out


def _snapshot(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): _sha(path.read_bytes())
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


class ReuseProvisionalNumericGradesTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path]:
        same_source = root / "source-same.json"
        cap_source = root / "source-cap.json"
        old_source = root / "source-old.json"
        new_source = root / "source-new.json"
        for path, marker in (
            (same_source, "same"),
            (cap_source, "cap"),
            (old_source, "old"),
            (new_source, "new"),
        ):
            path.write_text(json.dumps({"synthetic_marker": marker}) + "\n")

        provisional_cases = [
            _make_case("prov-match"),
            _make_case("prov-cap"),
            _make_case("prov-source"),
            _make_case("prov-missing"),
        ]
        provisional_sources = {
            "prov-match": same_source,
            "prov-cap": cap_source,
            "prov-source": old_source,
            "prov-missing": root / "source-missing.json",
        }
        provisional_sources["prov-missing"].write_text(json.dumps({"synthetic_marker": "missing"}) + "\n")
        grade_rows = [
            {"case_id": "prov-match", "review_marker": "original-synthetic-grade", "manual_numeric_status": "synthetic"},
            {"case_id": "prov-cap", "review_marker": "cap-case-grade"},
            {"case_id": "prov-source", "review_marker": "source-case-grade"},
        ]
        provisional = _write_packet_dir(
            root, "provisional", provisional_cases, provisional_sources, provisional=True, grades=grade_rows
        )

        final_cases = [
            _make_case("final-match"),
            _make_case("final-cap-changed", cap=81920),
            _make_case("final-source-changed"),
            _make_case("final-grade-missing"),
        ]
        final_sources = {
            "final-match": same_source,
            "final-cap-changed": cap_source,
            "final-source-changed": new_source,
            "final-grade-missing": provisional_sources["prov-missing"],
        }
        final = _write_packet_dir(root, "final", final_cases, final_sources, provisional=False)
        adjudications = root / "adjudications.json"
        adjudications.write_text(
            json.dumps({"cases": [{"case_id": "prov-match", "review_marker": "adjudicated-synthetic-grade"}]})
            + "\n"
        )
        return final, provisional, adjudications

    def test_reuses_exact_match_remaps_id_and_leaves_other_cases_for_grading(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            final, provisional, adjudications = self._fixture(root)
            before_final = _snapshot(final)
            before_provisional = _snapshot(provisional)
            out = root / "result"

            result = reuse_grades(final, [provisional], out, adjudications)

            self.assertEqual(result["reused_cases"], 1)
            self.assertEqual(result["remaining_cases"], 3)
            reused = json.loads((out / "reused-grades.json").read_text())
            self.assertEqual([row["case_id"] for row in reused["cases"]], ["final-match"])
            self.assertEqual(reused["cases"][0]["review_marker"], "adjudicated-synthetic-grade")
            self.assertNotIn("condition", reused["cases"][0])
            self.assertNotIn("synthetic-condition", json.dumps(reused))

            remaining_path = out / "remaining" / "grader" / "blind_numeric_packet.json"
            remaining = json.loads(remaining_path.read_text())
            self.assertEqual(
                {case["case_id"] for case in remaining["cases"]},
                {"final-cap-changed", "final-source-changed", "final-grade-missing"},
            )
            self.assertEqual(
                (out / "remaining" / "grader" / "GRADING_INSTRUCTIONS.md").read_text(),
                (final / "grader" / "GRADING_INSTRUCTIONS.md").read_text(),
            )
            coverage = json.loads((out / "researcher-only" / "coverage.json").read_text())
            self.assertEqual(coverage["remaining_by_reason"], {
                "no_matching_provisional_source": 1,
                "provisional_grade_missing": 1,
                "selected_cap_mismatch": 1,
            })
            provenance = json.loads((out / "researcher-only" / "provenance.json").read_text())
            self.assertEqual(provenance["reused_cases"][0]["provisional_case_id"], "prov-match")
            self.assertEqual(_snapshot(final), before_final)
            self.assertEqual(_snapshot(provisional), before_provisional)

    def test_corrupt_private_key_hash_is_rejected_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            final, provisional, _ = self._fixture(root)
            key_path = final / "private-key.json"
            key = json.loads(key_path.read_text())
            key["cases"]["final-match"]["source_file_sha256"] = "0" * 64
            key_path.write_text(json.dumps(key) + "\n")
            out = root / "must-not-exist"
            with self.assertRaisesRegex(PacketError, "source_file hash differs"):
                reuse_grades(final, [provisional], out)
            self.assertFalse(out.exists())

    def test_duplicate_and_unknown_grade_ids_are_rejected(self) -> None:
        for mutation, expected in (
            ("duplicate", "duplicate grade"),
            ("unknown", "unknown grade case_id"),
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                final, provisional, _ = self._fixture(root)
                grade_path = provisional / "grader" / "numeric-math-grades.json"
                grade_doc = json.loads(grade_path.read_text())
                if mutation == "duplicate":
                    grade_doc["cases"].append(dict(grade_doc["cases"][0]))
                else:
                    grade_doc["cases"].append({"case_id": "unknown-provisional-case", "review_marker": "synthetic"})
                grade_path.write_text(json.dumps(grade_doc) + "\n")
                with self.assertRaisesRegex(PacketError, expected):
                    reuse_grades(final, [provisional], root / "result")

    def test_adjudication_for_a_missing_grade_is_not_silently_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            final, provisional, _ = self._fixture(root)
            path = root / "missing-grade-adjudication.json"
            path.write_text(json.dumps({"cases": [{"case_id": "prov-missing", "review_marker": "synthetic"}]}) + "\n")
            with self.assertRaisesRegex(PacketError, "provisional grade is missing"):
                reuse_grades(final, [provisional], root / "result", path)


if __name__ == "__main__":
    unittest.main()
