"""Small CPU-only synthetic checks for score_numeric.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from score_numeric import (
    ScoreError,
    build_summary,
    grade_numeric_text,
    load_frozen_inputs,
    score_condition,
    sha256_file,
    validate_shared_runs,
)


ANSWER_FORMAT = "End with a single line of the form Answer: <exact numerical expression>."


def make_jobs() -> list[dict]:
    jobs = []
    for source_index in range(12):
        for replicate in (1, 2):
            source_id = f"C{source_index:02d}"
            job_id = f"numeric-{source_id.lower()}-s{replicate}"
            jobs.append(
                {
                    "id": job_id,
                    "source_id": source_id,
                    "variant": "v0",
                    "replicate": replicate,
                    "seed": 1000 + source_index * 10 + replicate,
                    "transfer_group": "synthetic",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Synthetic task {source_id}.\n\n{ANSWER_FORMAT}",
                        }
                    ],
                }
            )
    return jobs


def make_run(root: Path, name: str, jobs: list[dict], jobs_hash: str, *, adapted: bool) -> Path:
    out_dir = root / name
    out_dir.mkdir()
    receipt = {
        "status": "complete",
        "completed_jobs": 24,
        "jobs_sha256": jobs_hash,
        "model_revision": "synthetic-model-revision",
        "driver_sha256": "driver-hash",
        "cap": 32768,
        "context": 40960,
        "batch_size": 4,
        "samples": 1,
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 20,
        "presence_penalty": 0.2,
        "enable_thinking": False,
        "adapter": "synthetic-adapter" if adapted else None,
        "adapter_sha256": "adapter-hash" if adapted else None,
        "model_metadata_sha256": "model-metadata-hash",
    }
    (out_dir / "receipt.json").write_text(json.dumps(receipt) + "\n")
    for index, job in enumerate(jobs):
        if adapted and index == 0:
            raw_text = r"Earlier \boxed{15/4}" + "\nAnswer: 4"
            finish_reason = "length"
        elif adapted and index == 1:
            raw_text = "Answer: I cannot parse this value"
            finish_reason = "stop"
        else:
            raw_text = "Some reasoning.\nAnswer: 15/4"
            finish_reason = "stop"
        record = {
            **job,
            "sample": 0,
            "revision": "synthetic-model-revision",
            "adapter": "synthetic-adapter" if adapted else None,
            "prompt_ids": [3, index + 7],
            "raw_text": raw_text,
            "completion_ids": [5, 6, 7],
            "finish_reason": finish_reason,
        }
        (out_dir / f"{job['id']}-0.json").write_text(json.dumps(record) + "\n")
    return out_dir


class NumericScoreTests(unittest.TestCase):
    def test_last_commit_wins_and_unparsed_is_not_incorrect(self) -> None:
        corrected = grade_numeric_text(r"Earlier \boxed{15/4}" + "\nAnswer: 4", "15/4")
        self.assertEqual(corrected["numeric_status"], "incorrect")
        self.assertFalse(corrected["numeric_correct"])

        final_box = grade_numeric_text("Answer: 4\nCorrection: \\boxed{15/4}", "15/4")
        self.assertEqual(final_box["numeric_status"], "correct")
        self.assertTrue(final_box["numeric_correct"])

        unfinished_box = grade_numeric_text(
            "Earlier \\boxed{15/4}\nCorrection: \\boxed{4+", "15/4"
        )
        self.assertEqual(unfinished_box["numeric_status"], "unparsed")
        self.assertIsNone(unfinished_box["numeric_correct"])

        bold_header = grade_numeric_text("**Answer:** 15/4", "15/4")
        self.assertEqual(bold_header["numeric_status"], "correct")
        self.assertEqual(bold_header["answer_expression"], "15/4")

        unparsed = grade_numeric_text("Answer: the value is unclear", "15/4")
        self.assertEqual(unparsed["numeric_status"], "unparsed")
        self.assertIsNone(unparsed["numeric_correct"])

    def test_full_pairing_hashes_and_counts_on_synthetic_24_job_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jobs = make_jobs()
            jobs_path = root / "jobs.json"
            key_path = root / "key.json"
            jobs_path.write_text(json.dumps(jobs) + "\n")
            key_path.write_text(
                json.dumps(
                    [
                        {"id": job["id"], "source_id": job["source_id"], "answer_exact": "15/4"}
                        for job in jobs
                    ]
                )
                + "\n"
            )
            frozen_jobs, key_by_id = load_frozen_inputs(jobs_path, key_path)
            jobs_hash = sha256_file(jobs_path)
            base_dir = make_run(root, "base", jobs, jobs_hash, adapted=False)
            adapted_dir = make_run(root, "adapted", jobs, jobs_hash, adapted=True)

            base, base_receipt = score_condition("base", base_dir, frozen_jobs, key_by_id, jobs_hash)
            adapted, adapted_receipt = score_condition("adapted", adapted_dir, frozen_jobs, key_by_id, jobs_hash)
            validate_shared_runs(
                {"base": base, "adapted": adapted},
                {"base": base_receipt, "adapted": adapted_receipt},
            )
            summary = build_summary({"base": base, "adapted": adapted})

            self.assertEqual(base["receipt_sha256"], sha256_file(base_dir / "receipt.json"))
            self.assertEqual(base["jobs"][0]["raw_file_sha256"], sha256_file(base_dir / f"{jobs[0]['id']}-0.json"))
            self.assertEqual(summary["conditions"]["base"]["overall"]["correct"], 24)
            self.assertEqual(summary["conditions"]["adapted"]["overall"]["incorrect"], 1)
            self.assertEqual(summary["conditions"]["adapted"]["overall"]["unparsed"], 1)
            self.assertEqual(summary["conditions"]["adapted"]["overall"]["natural_end"], 23)
            self.assertEqual(summary["conditions"]["adapted"]["overall"]["length_finish"], 1)
            paired = summary["paired_comparisons"]["base_vs_adapted"]
            self.assertEqual((len(paired["wins"]), len(paired["losses"]), len(paired["ties"])), (1, 0, 22))
            self.assertEqual(len(paired["unparsed_pairs"]), 1)
            self.assertEqual(len(paired["per_source_id"]), 12)

    def test_missing_expected_output_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jobs = make_jobs()
            jobs_path = root / "jobs.json"
            key_path = root / "key.json"
            jobs_path.write_text(json.dumps(jobs) + "\n")
            key_path.write_text(
                json.dumps(
                    [
                        {"id": job["id"], "source_id": job["source_id"], "answer_exact": "15/4"}
                        for job in jobs
                    ]
                )
                + "\n"
            )
            frozen_jobs, key_by_id = load_frozen_inputs(jobs_path, key_path)
            jobs_hash = sha256_file(jobs_path)
            out_dir = make_run(root, "partial", jobs, jobs_hash, adapted=False)
            (out_dir / f"{jobs[-1]['id']}-0.json").unlink()
            with self.assertRaisesRegex(ScoreError, "expected 24 jobs"):
                score_condition("partial", out_dir, frozen_jobs, key_by_id, jobs_hash)


if __name__ == "__main__":
    unittest.main()
