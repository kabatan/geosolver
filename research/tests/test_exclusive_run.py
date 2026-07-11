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
from unittest.mock import patch

import research.harness.exclusive_run as exclusive_run_module
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
                    (
                        "linux_subreaper_process_tree"
                        if sys.platform.startswith("linux")
                        else "posix_process_group"
                    ),
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

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux subreaper custody")
    def test_successful_parent_cannot_abandon_a_running_grandchild(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "orphan-audit.json"
            pid_path = root / "orphan.pid"
            parent_source = "\n".join(
                (
                    "import pathlib, subprocess, sys",
                    "child = subprocess.Popen([sys.executable, '-c', "
                    "'import time; time.sleep(60)'])",
                    f"pathlib.Path({str(pid_path)!r}).write_text(str(child.pid), "
                    "encoding='utf-8')",
                )
            )
            orphan_pid: int | None = None
            try:
                exit_code = run_command(
                    [sys.executable, "-c", parent_source],
                    label="successful-parent-orphan",
                    audit_path=audit,
                    lock_path=root / "formal.lock",
                    cwd=root,
                    heartbeat_seconds=0.05,
                    timeout_seconds=0.3,
                )
                self.assertEqual(exit_code, 124)
                orphan_pid = int(pid_path.read_text(encoding="utf-8"))
                self.assertFalse(_pid_is_running(orphan_pid))
                document = json.loads(audit.read_text(encoding="utf-8"))
                self.assertEqual(document["outcome"], "hard_timeout")
                self.assertTrue(document["termination"]["tree_kill_confirmed"])
                self.assertGreaterEqual(
                    document["termination"]["tracked_identity_count"], 2
                )
            finally:
                if orphan_pid is not None and _pid_is_running(orphan_pid):
                    os.kill(orphan_pid, signal.SIGKILL)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux subreaper reaping")
    def test_successful_parent_reaps_an_already_dead_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "zombie-audit.json"
            pid_path = root / "zombie.pid"
            source = "\n".join(
                (
                    "import os, pathlib, time",
                    "child = os.fork()",
                    "if child == 0:",
                    f"    pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid()), "
                    "encoding='utf-8')",
                    "    os._exit(0)",
                    "deadline = time.monotonic() + 1.0",
                    f"while not pathlib.Path({str(pid_path)!r}).exists() and "
                    "time.monotonic() < deadline:",
                    "    time.sleep(0.001)",
                    "os._exit(0)",
                )
            )
            exit_code = run_command(
                [sys.executable, "-c", source],
                label="dead-orphan-reaping",
                audit_path=audit,
                lock_path=root / "formal.lock",
                cwd=root,
                heartbeat_seconds=0.05,
                timeout_seconds=2.0,
            )
            self.assertEqual(exit_code, 0)
            orphan_pid = int(pid_path.read_text(encoding="utf-8"))
            self.assertFalse(Path(f"/proc/{orphan_pid}").exists())
            document = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(document["outcome"], "completed")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux subreaper custody")
    def test_new_session_grandchild_cannot_escape_hard_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "escaped-audit.json"
            pid_path = root / "escaped.pid"
            parent_source = "\n".join(
                (
                    "import pathlib, subprocess, sys, time",
                    "child = subprocess.Popen([sys.executable, '-c', "
                    "'import time; time.sleep(60)'], start_new_session=True)",
                    f"pathlib.Path({str(pid_path)!r}).write_text(str(child.pid), "
                    "encoding='utf-8')",
                    "time.sleep(60)",
                )
            )
            escaped_pid: int | None = None
            try:
                exit_code = run_command(
                    [sys.executable, "-c", parent_source],
                    label="new-session-grandchild",
                    audit_path=audit,
                    lock_path=root / "formal.lock",
                    cwd=root,
                    heartbeat_seconds=0.05,
                    timeout_seconds=0.3,
                )
                self.assertEqual(exit_code, 124)
                escaped_pid = int(pid_path.read_text(encoding="utf-8"))
                self.assertFalse(_pid_is_running(escaped_pid))
                document = json.loads(audit.read_text(encoding="utf-8"))
                self.assertTrue(document["termination"]["tree_kill_confirmed"])
                self.assertEqual(
                    document["termination"]["strategy"],
                    "linux_subreaper_process_tree",
                )
            finally:
                if escaped_pid is not None and _pid_is_running(escaped_pid):
                    os.kill(escaped_pid, signal.SIGKILL)

    @unittest.skipUnless(sys.platform.startswith("linux"), "monotonic hard deadline")
    def test_completion_observed_after_deadline_is_a_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "strict-deadline-audit.json"
            exit_code = run_command(
                [sys.executable, "-c", "pass"],
                label="strict-deadline",
                audit_path=audit,
                lock_path=root / "formal.lock",
                cwd=root,
                heartbeat_seconds=0.05,
                timeout_seconds=0.000001,
            )
            self.assertEqual(exit_code, 124)
            document = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(document["outcome"], "hard_timeout")
            self.assertTrue(document["timed_out"])
            self.assertGreaterEqual(
                document["elapsed_seconds"],
                document["configured_timeout_seconds"],
            )

    @unittest.skipUnless(os.name == "posix", "POSIX repeated interrupt delivery")
    def test_repeated_keyboard_interrupt_cannot_interrupt_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "double-interrupt-audit.json"
            child_pid_path = root / "child.pid"
            child_source = "\n".join(
                (
                    "import os, pathlib, signal, time",
                    "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
                    f"pathlib.Path({str(child_pid_path)!r}).write_text(str(os.getpid()), "
                    "encoding='utf-8')",
                    "time.sleep(60)",
                )
            )
            interrupts = [
                threading.Timer(delay, os.kill, args=(os.getpid(), signal.SIGINT))
                for delay in (0.10, 0.15)
            ]
            for interrupt in interrupts:
                interrupt.start()
            child_pid: int | None = None
            try:
                with self.assertRaises(KeyboardInterrupt):
                    run_command(
                        [sys.executable, "-c", child_source],
                        label="double-keyboard-interrupt",
                        audit_path=audit,
                        lock_path=root / "formal.lock",
                        cwd=root,
                        heartbeat_seconds=0.05,
                        timeout_seconds=5.0,
                    )
            finally:
                for interrupt in interrupts:
                    interrupt.cancel()
                    interrupt.join()
                if child_pid_path.is_file():
                    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
                if child_pid is not None and _pid_is_running(child_pid):
                    os.kill(child_pid, signal.SIGKILL)
            self.assertIsNotNone(child_pid)
            self.assertFalse(_pid_is_running(child_pid or -1))
            document = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(document["outcome"], "interrupted")
            self.assertGreaterEqual(document["interrupt_signal_count"], 2)
            self.assertTrue(document["termination"]["attempted"])
            self.assertTrue(document["termination"]["tree_kill_confirmed"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux SIGTERM cleanup")
    def test_sigterm_audits_and_kills_new_session_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "sigterm-audit.json"
            pid_path = root / "sigterm-grandchild.pid"
            parent_source = "\n".join(
                (
                    "import pathlib, subprocess, sys, time",
                    "child = subprocess.Popen([sys.executable, '-c', "
                    "'import time; time.sleep(60)'], start_new_session=True)",
                    f"pathlib.Path({str(pid_path)!r}).write_text(str(child.pid), "
                    "encoding='utf-8')",
                    "time.sleep(60)",
                )
            )
            terminate = threading.Timer(
                0.2,
                os.kill,
                args=(os.getpid(), signal.SIGTERM),
            )
            terminate.start()
            grandchild_pid: int | None = None
            try:
                with self.assertRaises(SystemExit) as captured:
                    run_command(
                        [sys.executable, "-c", parent_source],
                        label="sigterm-cleanup",
                        audit_path=audit,
                        lock_path=root / "formal.lock",
                        cwd=root,
                        heartbeat_seconds=0.05,
                        timeout_seconds=5.0,
                    )
                self.assertEqual(captured.exception.code, 128 + signal.SIGTERM)
            finally:
                terminate.cancel()
                terminate.join()
                if pid_path.is_file():
                    grandchild_pid = int(pid_path.read_text(encoding="utf-8"))
                if grandchild_pid is not None and _pid_is_running(grandchild_pid):
                    os.kill(grandchild_pid, signal.SIGKILL)
            self.assertIsNotNone(grandchild_pid)
            self.assertFalse(_pid_is_running(grandchild_pid or -1))
            document = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(document["outcome"], "interrupted")
            self.assertGreaterEqual(document["termination_signal_count"], 1)
            self.assertTrue(document["termination"]["attempted"])
            self.assertTrue(document["termination"]["tree_kill_confirmed"])

    @unittest.skipUnless(os.name == "posix", "POSIX finalization signal delivery")
    def test_signal_during_audit_write_is_not_lost(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "finalization-signal-audit.json"
            original_write = exclusive_run_module._write_json_atomic

            def delayed_write(path: Path, document: dict[str, object]) -> None:
                time.sleep(0.2)
                original_write(path, document)

            original_sigterm = signal.getsignal(signal.SIGTERM)
            terminate = threading.Timer(
                0.05,
                os.kill,
                args=(os.getpid(), signal.SIGTERM),
            )
            terminate.start()
            try:
                with patch.object(
                    exclusive_run_module,
                    "_write_json_atomic",
                    delayed_write,
                ):
                    with self.assertRaises(SystemExit) as captured:
                        run_command(
                            [sys.executable, "-c", "pass"],
                            label="signal-during-finalization",
                            audit_path=audit,
                            lock_path=root / "formal.lock",
                            cwd=root,
                            heartbeat_seconds=0.05,
                            timeout_seconds=2.0,
                        )
                self.assertEqual(captured.exception.code, 128 + signal.SIGTERM)
            finally:
                terminate.cancel()
                terminate.join()
            self.assertEqual(signal.getsignal(signal.SIGTERM), original_sigterm)
            document = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(document["outcome"], "interrupted")
            self.assertGreaterEqual(document["termination_signal_count"], 1)
            self.assertTrue(document["termination"]["finalization_signal_observed"])


if __name__ == "__main__":
    unittest.main()
