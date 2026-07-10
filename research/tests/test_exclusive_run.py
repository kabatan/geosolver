from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from research.harness.exclusive_run import (
    SCHEMA_VERSION,
    FormalRunBusy,
    FormalRunLease,
    run_command,
)


class FormalRunLeaseTests(unittest.TestCase):
    def test_lease_is_exclusive_and_exposes_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "formal.lock"
            first = FormalRunLease("first", lock).acquire()
            try:
                with self.assertRaises(FormalRunBusy) as captured:
                    FormalRunLease("second", lock).acquire()
                self.assertEqual(captured.exception.owner["label"], "first")
                self.assertEqual(captured.exception.owner["state"], "running")
            finally:
                first.release()
            with FormalRunLease("second", lock) as second:
                self.assertEqual(second.owner["label"], "second")

    def test_command_audit_is_atomic_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "audit.json"
            exit_code = run_command(
                [sys.executable, "-c", "print('formal-child-ok')"],
                label="unit-formal-run",
                audit_path=audit,
                lock_path=root / "formal.lock",
                cwd=root,
                heartbeat_seconds=0.05,
            )
            self.assertEqual(exit_code, 0)
            document = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(document["schema"], SCHEMA_VERSION)
            self.assertEqual(document["label"], "unit-formal-run")
            self.assertEqual(document["outcome"], "completed")
            self.assertEqual(document["exit_code"], 0)
            self.assertGreaterEqual(document["elapsed_seconds"], 0)
            self.assertEqual(document["cwd"], str(root.resolve()))
            self.assertIsInstance(document["child_pid"], int)

    def test_invalid_command_and_heartbeat_fail_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "cannot be empty"):
                run_command(
                    [],
                    label="empty",
                    audit_path=root / "audit.json",
                    lock_path=root / "formal.lock",
                )
            with self.assertRaisesRegex(ValueError, "finite and positive"):
                run_command(
                    [sys.executable, "-c", "pass"],
                    label="bad-heartbeat",
                    audit_path=root / "audit.json",
                    lock_path=root / "formal.lock",
                    heartbeat_seconds=0,
                )

    def test_nonzero_child_is_not_reported_as_completed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "audit.json"
            exit_code = run_command(
                [sys.executable, "-c", "raise SystemExit(7)"],
                label="failing-child",
                audit_path=audit,
                lock_path=root / "formal.lock",
                cwd=root,
                heartbeat_seconds=0.05,
            )
            self.assertEqual(exit_code, 7)
            document = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(document["outcome"], "child_failed")
            self.assertEqual(document["exit_code"], 7)


if __name__ == "__main__":
    unittest.main()
