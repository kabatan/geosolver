from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CLOSURE_PATH = (
    REPOSITORY_ROOT
    / "research"
    / "experiments"
    / "EXP-LOCAL-001"
    / "pilot-closure.json"
)
SUMMARY_PATH = (
    REPOSITORY_ROOT / "research" / "results" / "EXP-LOCAL-001" / "summary.json"
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class Local001ClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.closure = json.loads(CLOSURE_PATH.read_bytes())
        self.summary = json.loads(SUMMARY_PATH.read_bytes())

    def test_historical_artifact_bindings(self) -> None:
        self.assertEqual(
            self.closure["schema_version"], "exp-local-001-pilot-closure/v1"
        )
        for row in self.closure["artifact_bindings"]:
            payload = subprocess.check_output(
                ["git", "show", f"{row['git_commit']}:{row['path']}"],
                cwd=REPOSITORY_ROOT,
            )
            self.assertEqual(len(payload), row["size"])
            self.assertEqual(sha256(payload), row["sha256"])

    def test_no_formal_or_product_claim(self) -> None:
        boundary = self.closure["formal_boundary"]
        self.assertTrue(all(value is False for value in boundary.values()))
        self.assertIsNone(self.closure["decision"]["algorithm_conclusion"])
        self.assertFalse(
            self.closure["decision"]["same_experiment_formal_expansion_authorized"]
        )
        for relative in self.closure["required_absent_paths"]:
            self.assertFalse((REPOSITORY_ROOT / relative).exists())

    def test_summary_binds_closure(self) -> None:
        self.assertEqual(
            self.summary["schema_version"], "exp-local-001-governance-summary/v1"
        )
        self.assertEqual(
            self.summary["pilot_closure_sha256"], sha256(CLOSURE_PATH.read_bytes())
        )
        self.assertFalse(self.summary["formal_result_eligible"])
        self.assertEqual(self.summary["algorithm_conclusion"], "none")
        self.assertEqual(self.summary["successor_experiment_id"], "EXP-LOCAL-003")


if __name__ == "__main__":
    unittest.main()
