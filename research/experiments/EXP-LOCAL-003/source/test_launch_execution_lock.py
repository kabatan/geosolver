"""Claim-first production-boundary tests for launch_execution_lock.py."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import launch_execution_lock as launcher


class LaunchExecutionLockTests(unittest.TestCase):
    def test_module_has_no_project_or_third_party_top_level_import(self) -> None:
        tree = ast.parse(Path(launcher.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
        self.assertEqual(
            imported,
            {"__future__", "os", "stat", "sys", "pathlib", "typing"},
        )

    def test_failure_after_claim_is_terminal_and_retry_never_invokes_helper(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            experiment = root / "research" / "experiments" / "EXP-LOCAL-003"
            experiment.mkdir(parents=True)
            with (
                mock.patch.object(launcher, "REPOSITORY_ROOT", root),
                mock.patch.object(
                    launcher,
                    "_invoke_helper",
                    side_effect=RuntimeError("synthetic post-claim failure"),
                ) as invoke,
            ):
                with self.assertRaisesRegex(RuntimeError, "post-claim"):
                    launcher.launch("development")
                claimed = launcher._output_path("development")
                self.assertTrue(claimed.is_file())
                self.assertEqual(claimed.read_bytes(), b"")
                with self.assertRaisesRegex(launcher.LaunchError, "already exists"):
                    launcher.launch("development")
                self.assertEqual(invoke.call_count, 1)

    def test_success_fills_the_already_existing_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            experiment = root / "research" / "experiments" / "EXP-LOCAL-003"
            experiment.mkdir(parents=True)
            payload = b'{"canonical":true}'

            def fill_claim(stage: launcher.Stage) -> Path:
                claimed = launcher._output_path(stage)
                self.assertTrue(claimed.is_file())
                self.assertEqual(claimed.read_bytes(), b"")
                claimed.write_bytes(payload)
                return claimed

            with (
                mock.patch.object(launcher, "REPOSITORY_ROOT", root),
                mock.patch.object(launcher, "_invoke_helper", side_effect=fill_claim),
            ):
                result = launcher.launch("locked")
                self.assertEqual(result, launcher._output_path("locked"))
                self.assertEqual(result.read_bytes(), payload)
                with self.assertRaisesRegex(launcher.LaunchError, "already exists"):
                    launcher.launch("locked")

    def test_partial_claim_is_never_reused_or_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            experiment = root / "research" / "experiments" / "EXP-LOCAL-003"
            experiment.mkdir(parents=True)
            partial = experiment / "candidate-execution-lock.json"
            partial.write_bytes(b'{"partial"')
            with (
                mock.patch.object(launcher, "REPOSITORY_ROOT", root),
                mock.patch.object(launcher, "_invoke_helper") as invoke,
            ):
                with self.assertRaisesRegex(launcher.LaunchError, "already exists"):
                    launcher.launch("development")
            invoke.assert_not_called()
            self.assertEqual(partial.read_bytes(), b'{"partial"')


if __name__ == "__main__":
    unittest.main()
