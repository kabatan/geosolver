from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from research.harness.exclusive_run import (
    SCHEMA_VERSION,
    FormalRunBusy,
    FormalRunLease,
    main,
    run_command,
)


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    stat = Path(f"/proc/{pid}/stat")
    if stat.is_file():
        try:
            fields = stat.read_text(encoding="utf-8").split()
        except OSError:
            return False
        if len(fields) >= 3 and fields[2] == "Z":
            return False
    return True


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
                timeout_seconds=2.0,
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
            self.assertEqual(document["configured_timeout_seconds"], 2.0)
            self.assertFalse(document["timed_out"])
            self.assertFalse(document["termination"]["attempted"])
            self.assertEqual(document["termination"]["child_returncode"], 0)
            self.assertIn("no in-process preemption", document["timeout_boundary"])
            self.assertEqual(list(root.glob(".audit.json.*.tmp")), [])

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
            for invalid in (0, -1, float("inf"), float("nan"), True):
                with self.subTest(timeout_seconds=invalid):
                    with self.assertRaisesRegex(ValueError, "finite and positive"):
                        run_command(
                            [sys.executable, "-c", "pass"],
                            label="bad-timeout",
                            audit_path=root / "timeout-audit.json",
                            lock_path=root / "formal.lock",
                            timeout_seconds=invalid,
                        )
            self.assertFalse((root / "timeout-audit.json").exists())
            with self.assertRaises(SystemExit) as captured:
                main(
                    [
                        "--label",
                        "bad-cli-timeout",
                        "--audit",
                        str(root / "cli-timeout-audit.json"),
                        "--lock",
                        str(root / "formal.lock"),
                        "--timeout-seconds",
                        "0",
                        "--",
                        sys.executable,
                        "-c",
                        "pass",
                    ]
                )
            self.assertEqual(captured.exception.code, 2)
            self.assertFalse((root / "cli-timeout-audit.json").exists())

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

    def test_cli_hard_timeout_returns_124_and_audits_termination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "timeout-audit.json"
            exit_code = main(
                [
                    "--label",
                    "cli-hard-timeout",
                    "--audit",
                    str(audit),
                    "--lock",
                    str(root / "formal.lock"),
                    "--cwd",
                    str(root),
                    "--heartbeat-seconds",
                    "0.05",
                    "--timeout-seconds",
                    "0.2",
                    "--",
                    sys.executable,
                    "-c",
                    "import time; time.sleep(60)",
                ]
            )
            self.assertEqual(exit_code, 124)
            document = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(document["outcome"], "hard_timeout")
            self.assertEqual(document["exit_code"], 124)
            self.assertEqual(document["configured_timeout_seconds"], 0.2)
            self.assertTrue(document["timed_out"])
            self.assertTrue(document["termination"]["attempted"])
            self.assertEqual(document["termination"]["reason"], "hard_timeout")
            self.assertIsInstance(document["termination"]["child_returncode"], int)
            self.assertEqual(list(root.glob(".timeout-audit.json.*.tmp")), [])

    @unittest.skipUnless(os.name == "posix", "POSIX process-group counterexample")
    def test_hard_timeout_kills_term_ignoring_grandchild(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "grandchild-audit.json"
            pid_path = root / "grandchild.pid"
            parent_source = "\n".join(
                (
                    "import pathlib, signal, subprocess, sys, time",
                    "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
                    "child = subprocess.Popen([sys.executable, '-c', "
                    "'import time; time.sleep(60)'])",
                    f"pathlib.Path({str(pid_path)!r}).write_text(str(child.pid), encoding='utf-8')",
                    "time.sleep(60)",
                )
            )
            grandchild_pid: int | None = None
            try:
                exit_code = run_command(
                    [sys.executable, "-c", parent_source],
                    label="grandchild-hard-timeout",
                    audit_path=audit,
                    lock_path=root / "formal.lock",
                    cwd=root,
                    heartbeat_seconds=0.05,
                    timeout_seconds=0.3,
                )
                self.assertEqual(exit_code, 124)
                self.assertTrue(pid_path.is_file())
                grandchild_pid = int(pid_path.read_text(encoding="utf-8"))
                deadline = time.monotonic() + 2.0
                while _pid_is_running(grandchild_pid) and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertFalse(_pid_is_running(grandchild_pid))
                document = json.loads(audit.read_text(encoding="utf-8"))
                self.assertEqual(document["outcome"], "hard_timeout")
                self.assertTrue(document["termination"]["term_sent"])
                self.assertTrue(document["termination"]["kill_sent"])
                self.assertEqual(
                    document["termination"]["strategy"],
                    "posix_process_group",
                )
            finally:
                if grandchild_pid is not None and _pid_is_running(grandchild_pid):
                    os.kill(grandchild_pid, signal.SIGKILL)

    @unittest.skipUnless(os.name == "posix", "POSIX interrupt delivery")
    def test_keyboard_interrupt_still_terminates_child_and_writes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "interrupt-audit.json"
            interrupt = threading.Timer(0.2, os.kill, args=(os.getpid(), signal.SIGINT))
            interrupt.start()
            try:
                with self.assertRaises(KeyboardInterrupt):
                    run_command(
                        [sys.executable, "-c", "import time; time.sleep(60)"],
                        label="keyboard-interrupt",
                        audit_path=audit,
                        lock_path=root / "formal.lock",
                        cwd=root,
                        heartbeat_seconds=0.05,
                        timeout_seconds=5.0,
                    )
            finally:
                interrupt.cancel()
                interrupt.join()
            document = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(document["outcome"], "interrupted")
            self.assertFalse(document["timed_out"])
            self.assertTrue(document["termination"]["attempted"])
            self.assertEqual(document["termination"]["reason"], "interrupted")
            self.assertIsInstance(document["termination"]["child_returncode"], int)


if __name__ == "__main__":
    unittest.main()
