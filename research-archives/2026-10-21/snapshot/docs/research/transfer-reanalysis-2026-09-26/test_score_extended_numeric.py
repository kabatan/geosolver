"""CPU-only synthetic tests for 32k/81k numeric-result reconciliation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from score_extended_numeric import CONDITIONS, GROUP, score_extended_run
from score_numeric import sha256_file


ANSWER_FORMAT = "End with a single line of the form Answer: <exact numerical expression>."
RUN_SETTINGS = {
    "model_revision": "synthetic-model-revision",
    "driver_sha256": "synthetic-generator-driver-hash",
    "batch_size": 4,
    "samples": 1,
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 20,
    "presence_penalty": 0.2,
    "enable_thinking": False,
}


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _jobs() -> list[dict]:
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


def _receipt(jobs_path: Path, subset_jobs_path: Path | None, condition: str, cap: int) -> dict:
    adapter = None if condition == "base" else f"/synthetic/adapter/{condition}"
    adapter_hash = None if condition == "base" else f"adapter-hash-{condition}"
    jobs_path_for_hash = subset_jobs_path if cap == 81920 else jobs_path
    rows = json.loads(jobs_path_for_hash.read_text())
    return {
        "status": "complete",
        **RUN_SETTINGS,
        "jobs_sha256": sha256_file(jobs_path_for_hash),
        "completed_jobs": len(rows),
        "cap": cap,
        "context": 98304 if cap == 81920 else 40960,
        "adapter": adapter,
        "adapter_sha256": adapter_hash,
        "model_metadata_sha256": "synthetic-model-metadata-hash",
    }


def _make_fixture(root: Path) -> tuple[Path, Path, Path, set[str]]:
    run_dir = root / "run"
    run_dir.mkdir()
    jobs_path = root / "jobs.json"
    key_path = root / "key.json"
    jobs = _jobs()
    _write(jobs_path, jobs)
    _write(
        key_path,
        [
            {"id": job["id"], "source_id": job["source_id"], "answer_exact": "15/4"}
            for job in jobs
        ],
    )
    capped_ids = {jobs[0]["id"], jobs[1]["id"]}
    subset = [job for job in jobs if job["id"] in capped_ids]
    subset_path = run_dir / f"{GROUP}-extended-jobs.json"
    _write(subset_path, subset)

    completed = []
    for condition_index, condition in enumerate(CONDITIONS):
        full_dir = run_dir / f"{GROUP}-{condition}-32768"
        full_dir.mkdir()
        _write(full_dir / "receipt.json", _receipt(jobs_path, None, condition, 32768))
        for index, job in enumerate(jobs):
            finish_reason = "length" if (condition == "base" and index == 0) or (condition == "code128" and index == 1) else "stop"
            answer = "4" if condition == "base" and index == 2 else "15/4"
            completion_ids = [index + 10, index + 20, index + 30]
            record = {
                **job,
                "sample": 0,
                "model": "synthetic-model",
                "revision": RUN_SETTINGS["model_revision"],
                "adapter": None if condition == "base" else f"/synthetic/adapter/{condition}",
                "prompt_ids": [500, index + 600],
                "raw_text": f"Reasoning.\nAnswer: {answer}",
                "completion_ids": completion_ids,
                "finish_reason": finish_reason,
            }
            _write(full_dir / f"{job['id']}-0.json", record)
        completed.append(f"{GROUP}-{condition}-32768")

        retry_dir = run_dir / f"{GROUP}-{condition}-81920"
        retry_dir.mkdir()
        _write(retry_dir / "receipt.json", _receipt(jobs_path, subset_path, condition, 81920))
        for job in subset:
            index = jobs.index(job)
            base_ids = [index + 10, index + 20, index + 30]
            retry_ids = list(base_ids) + [700 + condition_index]
            if condition == "opd32" and job["id"] == jobs[1]["id"]:
                retry_ids[0] += 9000  # Preserve and report prefix mismatch; do not relabel the job.
            finish_reason = "length" if condition == "opd32" and job["id"] == jobs[1]["id"] else "stop"
            record = {
                **job,
                "sample": 0,
                "model": "synthetic-model",
                "revision": RUN_SETTINGS["model_revision"],
                "adapter": None if condition == "base" else f"/synthetic/adapter/{condition}",
                "prompt_ids": [500, index + 600],
                "raw_text": "Longer reasoning.\nAnswer: 15/4",
                "completion_ids": retry_ids,
                "finish_reason": finish_reason,
            }
            _write(retry_dir / f"{job['id']}-0.json", record)
        completed.append(f"{GROUP}-{condition}-81920")

    run_receipt = {
        "status": "running",  # Numeric group is done while other groups may still run.
        "inputs": {str(jobs_path.resolve()): sha256_file(jobs_path)},
        "completed": completed,
        "extended_jobs": {
            GROUP: {
                "ids": sorted(capped_ids),
                "jobs_sha256": sha256_file(subset_path),
            }
        },
    }
    _write(run_dir / "receipt.json", run_receipt)
    return run_dir, jobs_path, key_path, capped_ids


class ExtendedNumericScoreTests(unittest.TestCase):
    def test_union_retry_rollup_provenance_and_prefix_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, jobs_path, key_path, capped_ids = _make_fixture(Path(temp))
            report = score_extended_run(run_dir, jobs_path, key_path)
            self.assertEqual(report["retry_union_ids"], sorted(capped_ids))
            self.assertEqual(report["retry_union_count"], 2)
            self.assertEqual(report["numeric_32k"]["conditions"]["base"]["overall"]["jobs"], 24)
            self.assertEqual(len(report["extended_budget_24_job_summary"]["conditions"]["base"]["jobs"]), 24)
            self.assertEqual(len(report["source_ledger"]), 24 * len(CONDITIONS))
            self.assertEqual(
                report["extended_budget_24_job_summary"]["conditions"]["base"]["overall"]["incorrect"],
                1,
            )
            self.assertEqual(report["extended_budget_natural_finish_counts"]["opd32"]["length_finish"], 1)
            ledger = {
                (row["condition"], row["job_id"]): row for row in report["source_ledger"]
            }
            mismatch = ledger[("opd32", sorted(capped_ids)[1])]
            self.assertFalse(mismatch["prefix_identical_to_32k"])
            self.assertEqual(mismatch["source_32k"]["cap"], 32768)
            self.assertEqual(mismatch["source_81k"]["cap"], 81920)
            unchanged = ledger[("base", _jobs()[2]["id"])]
            self.assertIsNone(unchanged["source_81k"])
            self.assertEqual(unchanged["selected_source"]["cap"], 32768)

    def test_changed_arm_adapter_hash_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir, jobs_path, key_path, _ = _make_fixture(Path(temp))
            receipt_path = run_dir / f"{GROUP}-numeric128-81920" / "receipt.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["adapter_sha256"] = "unexpected-new-adapter"
            _write(receipt_path, receipt)
            with self.assertRaisesRegex(ValueError, "adapter_sha256 changed"):
                score_extended_run(run_dir, jobs_path, key_path)


if __name__ == "__main__":
    unittest.main()
