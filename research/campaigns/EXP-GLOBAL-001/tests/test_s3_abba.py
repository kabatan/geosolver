from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
SPEC = importlib.util.spec_from_file_location(
    "exp_global_001_s3_abba", CAMPAIGN / "run_s3_abba.py"
)
assert SPEC is not None and SPEC.loader is not None
ORCH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ORCH
SPEC.loader.exec_module(ORCH)


FAKE_RUNNER = r'''#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


p = argparse.ArgumentParser()
p.add_argument("--arm", type=Path, required=True)
p.add_argument("--partition", required=True)
p.add_argument("--dataset", type=Path, required=True)
p.add_argument("--frozen-root", type=Path, required=True)
p.add_argument("--python", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--jobs", type=int, required=True)
p.add_argument("--cpus", required=True)
p.add_argument("--total-seconds", type=float, required=True)
p.add_argument("--search-seconds", type=float, required=True)
p.add_argument("--starts", type=int, required=True)
p.add_argument("--callbacks-per-start", type=int, required=True)
p.add_argument("--aggregate-callback-cap", type=int, required=True)
p.add_argument("--seed", type=int, required=True)
p.add_argument("--execute", action="store_true")
a = p.parse_args()
arm = json.loads(a.arm.read_text())
entrypoint = Path(arm["entrypoint"])
if not entrypoint.is_absolute():
    entrypoint = (a.arm.parent / entrypoint).resolve()
log = Path(os.environ["FAKE_ABBA_LOG"])
rows = log.read_text().splitlines() if log.exists() else []
index = len(rows)
record = {
    "index": index,
    "arm": arm["id"],
    "seed": a.seed,
    "execute": a.execute,
    "partition": a.partition,
    "jobs": a.jobs,
    "cpus": a.cpus,
    "total": a.total_seconds,
    "search": a.search_seconds,
    "starts": a.starts,
    "callbacks": a.callbacks_per_start,
    "aggregate": a.aggregate_callback_cap,
    "output": str(a.output),
}
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, sort_keys=True) + "\n")
if os.environ.get("FAKE_FAIL_AT") == str(index):
    print("synthetic failure", file=sys.stderr)
    raise SystemExit(9)
plan = {
    "schema_version": "fake-arm-plan/v1",
    "execute": a.execute,
    "arm": arm,
    "entrypoint": str(entrypoint),
    "entrypoint_sha256": digest(entrypoint),
    "partition": a.partition,
    "case_count": 145,
    "development_dataset_sha256": digest(a.dataset),
    "selected_dataset_sha256": "2" * 64,
    "archived_input_manifest_sha256": "3" * 64,
    "canonical_formulations_verified": 145,
    "runner_sha256": "4" * 64,
    "truth_passed_to_worker": False,
    "validation_or_sealed_supported": False,
    "jobs": a.jobs,
    "cpus": a.cpus,
    "total_seconds": a.total_seconds,
    "search_seconds": a.search_seconds,
    "starts": a.starts,
    "callbacks_per_start": a.callbacks_per_start,
    "aggregate_callback_cap": a.aggregate_callback_cap,
    "seed": a.seed,
}
if a.execute:
    a.output.mkdir(parents=True)
    (a.output / "CAMPAIGN_PLAN.json").write_text(
        json.dumps(plan, sort_keys=True) + "\n", encoding="utf-8"
    )
    result = {
        "status": "COMPLETE",
        "rows": [{} for _ in range(145)],
        "plan": {
            "execute": True,
            "dataset_sha256": plan["selected_dataset_sha256"],
            "case_count": 145,
            "jobs": a.jobs,
            "cpus": [int(a.cpus)],
            "total_seconds": a.total_seconds,
            "search_seconds": a.search_seconds,
            "starts": a.starts,
            "callbacks_per_start": a.callbacks_per_start,
            "aggregate_callback_cap": a.aggregate_callback_cap,
            "seed": a.seed,
            "worker": str(entrypoint),
            "worker_sha256": digest(entrypoint),
            "truth_or_known_target_count_passed_to_solver": False,
            "formulation_content_modified": False,
        },
    }
    (a.output / "RESULT.json").write_text(
        json.dumps(result, sort_keys=True) + "\n", encoding="utf-8"
    )
else:
    print(json.dumps(plan, sort_keys=True))
if os.environ.get("FAKE_MUTATE_AT") == str(index):
    Path(os.environ["FAKE_MUTATE_PATH"]).write_text("mutated\n", encoding="utf-8")
'''


class S3ABBAOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="exp-global-s3-abba-")
        self.root = Path(self.temporary.name)
        self.frozen = self.root / "frozen"
        self.frozen.mkdir()
        self.dataset = self.root / "development145.jsonl"
        self.dataset.write_text("synthetic-development-only\n", encoding="utf-8")
        self.runner = self.root / "fake_run_arm.py"
        self.runner.write_text(FAKE_RUNNER, encoding="utf-8")
        self.log = self.root / "calls.jsonl"
        self.control_worker = self.root / "control_worker.py"
        self.control_worker.write_text("# synthetic control\n", encoding="utf-8")
        self.candidate_worker = self.root / "candidate_worker.py"
        self.candidate_worker.write_text("# synthetic candidate\n", encoding="utf-8")
        self.control_arm = self._arm("synthetic-control", self.control_worker, "a")
        self.candidate_arm = self._arm(
            "synthetic-candidate", self.candidate_worker, "b"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _arm(self, arm_id: str, worker: Path, base: str) -> Path:
        path = self.root / f"{arm_id}.json"
        path.write_text(
            json.dumps(
                {
                    "id": arm_id,
                    "base_commit": base * 40,
                    "entrypoint": worker.name,
                    "mechanism_hash": hashlib.sha256(worker.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        return path

    def _argv(self, raw_root: Path, execute: bool = False) -> list[str]:
        result = [
            "--control-arm",
            str(self.control_arm),
            "--candidate-arm",
            str(self.candidate_arm),
            "--raw-root",
            str(raw_root),
            "--cpu",
            "3",
            "--seeds",
            "0",
            "--runner",
            str(self.runner),
            "--frozen-root",
            str(self.frozen),
            "--dataset",
            str(self.dataset),
            "--python",
            sys.executable,
            "--launcher-python",
            sys.executable,
        ]
        if execute:
            result.append("--execute")
        return result

    def _run(self, raw_root: Path, execute: bool = False, **environment: str) -> int:
        values = {"FAKE_ABBA_LOG": str(self.log), **environment}
        with mock.patch.dict(os.environ, values, clear=False):
            return ORCH.main(self._argv(raw_root, execute))

    def _calls(self) -> list[dict[str, object]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_default_is_dry_and_orders_a_b_b_a(self) -> None:
        raw = self.root / "raw-dry"
        self.assertEqual(self._run(raw), 0)
        calls = self._calls()
        self.assertEqual(
            [call["arm"] for call in calls],
            [
                "synthetic-control",
                "synthetic-candidate",
                "synthetic-candidate",
                "synthetic-control",
            ],
        )
        self.assertTrue(all(call["execute"] is False for call in calls))
        self.assertTrue(all(call["partition"] == "development" for call in calls))
        self.assertTrue(all(call["jobs"] == 1 and call["cpus"] == "3" for call in calls))
        self.assertTrue(all(call["total"] == 180 and call["search"] == 146 for call in calls))
        manifest = json.loads((raw / ORCH.MANIFEST_NAME).read_text())
        self.assertEqual(manifest["status"], "dry_planned")
        self.assertTrue(all(leg["status"] == "dry_planned" for leg in manifest["legs"]))
        self.assertFalse(any((raw / "legs").glob("*")))

    def test_execute_resume_skips_four_verified_completed_legs(self) -> None:
        raw = self.root / "raw-resume"
        self.assertEqual(self._run(raw, execute=True), 0)
        self.assertEqual(len(self._calls()), 4)
        self.assertEqual(self._run(raw, execute=True), 0)
        self.assertEqual(len(self._calls()), 4)
        manifest = json.loads((raw / ORCH.MANIFEST_NAME).read_text())
        self.assertEqual(manifest["status"], "complete")
        self.assertTrue(all(leg["status"] == "completed" for leg in manifest["legs"]))
        self.assertTrue(all(leg["resume_verified"] for leg in manifest["legs"]))

    def test_resume_rejects_result_mismatch(self) -> None:
        raw = self.root / "raw-mismatch"
        self._run(raw, execute=True)
        result_path = raw / "legs/seed-00-a1-control/RESULT.json"
        result = json.loads(result_path.read_text())
        result["status"] = "BROKEN"
        result_path.write_text(json.dumps(result), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "absent or incomplete"):
            self._run(raw, execute=True)

    def test_resume_rejects_campaign_plan_mismatch(self) -> None:
        raw = self.root / "raw-plan-mismatch"
        self._run(raw, execute=True)
        plan_path = raw / "legs/seed-00-a1-control/CAMPAIGN_PLAN.json"
        plan = json.loads(plan_path.read_text())
        plan["seed"] = 999
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "campaign plan mismatch at seed"):
            self._run(raw, execute=True)

    def test_entrypoint_hash_mutation_stops_before_second_leg(self) -> None:
        raw = self.root / "raw-mutation"
        with self.assertRaisesRegex(SystemExit, "mechanism hash mismatch"):
            self._run(
                raw,
                FAKE_MUTATE_AT="0",
                FAKE_MUTATE_PATH=str(self.candidate_worker),
            )
        self.assertEqual(len(self._calls()), 1)
        manifest = json.loads((raw / ORCH.MANIFEST_NAME).read_text())
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["legs"][0]["status"], "dry_planned")
        self.assertEqual(manifest["legs"][1]["status"], "failed")

    def test_runner_failure_stops_remaining_legs(self) -> None:
        raw = self.root / "raw-failure"
        with self.assertRaisesRegex(SystemExit, "exit 9"):
            self._run(raw, FAKE_FAIL_AT="1")
        self.assertEqual(len(self._calls()), 2)
        statuses = [
            leg["status"]
            for leg in json.loads((raw / ORCH.MANIFEST_NAME).read_text())["legs"]
        ]
        self.assertEqual(statuses, ["dry_planned", "failed", "pending", "pending"])

    def test_path_guards_reject_repo_and_holdout_names(self) -> None:
        with self.assertRaisesRegex(SystemExit, "outside the repository"):
            self._run(ORCH.HERE / "synthetic-raw")
        for name in ("validation-run", "sealed-corpus-run", "holdout-run"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(SystemExit, "forbidden holdout name"):
                    self._run(self.root / name)

    def test_default_seed_schedule_is_zero_through_four(self) -> None:
        parsed = ORCH.parser().parse_args(
            [
                "--control-arm",
                str(self.control_arm),
                "--candidate-arm",
                str(self.candidate_arm),
                "--raw-root",
                str(self.root / "raw-default-seeds"),
                "--cpu",
                "3",
            ]
        )
        self.assertEqual(parsed.seeds, [0, 1, 2, 3, 4])

    def test_solver_python_virtualenv_symlink_is_preserved(self) -> None:
        linked_python = self.root / "venv-python"
        linked_python.symlink_to(Path(sys.executable).resolve())
        argv = self._argv(self.root / "raw-python-link")
        argv[argv.index("--python") + 1] = str(linked_python)
        arguments = ORCH.parser().parse_args(argv)

        _, campaign = ORCH.prepare_campaign(arguments)

        self.assertEqual(
            campaign["config"]["solver_python"], str(linked_python.absolute())
        )


if __name__ == "__main__":
    unittest.main()
