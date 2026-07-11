"""Claim-first boundary tests for launch_c2_equivalence.py."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import launch_c2_equivalence as launcher


class LaunchC2EquivalenceTests(unittest.TestCase):
    def test_top_level_imports_are_pure_stdlib(self) -> None:
        tree = ast.parse(Path(launcher.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
        self.assertEqual(
            imported,
            {"__future__", "os", "stat", "sys", "pathlib"},
        )

    def test_preclaim_hygiene_rejects_injection_and_stale_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "protocol-source"
            python_source = root / "python" / "src"
            source.mkdir(parents=True)
            python_source.mkdir(parents=True)
            fake_sys = SimpleNamespace(
                flags=SimpleNamespace(no_site=1),
                modules={},
                path=[r"C:\Windows\System32"],
            )
            with (
                mock.patch.object(launcher, "SOURCE_ROOT", source),
                mock.patch.object(launcher, "PYTHON_SOURCE", python_source),
                mock.patch.object(launcher, "sys", fake_sys),
                mock.patch.dict(launcher.os.environ, {}, clear=True),
            ):
                launcher._verify_preimport_hygiene()
                launcher.os.environ["COVERAGE_PROCESS_START"] = "inject"
                with self.assertRaisesRegex(launcher.LaunchError, "injection"):
                    launcher._verify_preimport_hygiene()
                del launcher.os.environ["COVERAGE_PROCESS_START"]
                (python_source / "__pycache__").mkdir()
                with self.assertRaisesRegex(launcher.LaunchError, "stale.*bytecode"):
                    launcher._verify_preimport_hygiene()

    def test_dependency_path_is_derived_from_executable_without_site(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "protocol-source"
            python_source = root / "python" / "src"
            scripts = root / "python" / ".venv" / "Scripts"
            site_packages = root / "python" / ".venv" / "Lib" / "site-packages"
            source.mkdir(parents=True)
            python_source.mkdir(parents=True)
            scripts.mkdir(parents=True)
            site_packages.mkdir(parents=True)
            executable = scripts / "python.exe"
            executable.write_bytes(b"fixed-venv-python")
            fake_sys = SimpleNamespace(
                executable=str(executable),
                prefix=r"C:\unrelated-base-prefix",
                path=[r"C:\Windows\System32"],
            )
            with (
                mock.patch.object(launcher, "REPOSITORY_ROOT", root),
                mock.patch.object(launcher, "SOURCE_ROOT", source),
                mock.patch.object(launcher, "PYTHON_SOURCE", python_source),
                mock.patch.object(launcher, "sys", fake_sys),
            ):
                launcher._activate_claimed_import_paths()
            self.assertEqual(
                fake_sys.path[:3],
                [str(source), str(python_source), str(site_packages)],
            )

    def test_post_claim_failure_is_terminal_and_retry_skips_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "research" / "experiments" / "EXP-LOCAL-003").mkdir(parents=True)
            with (
                mock.patch.object(launcher, "REPOSITORY_ROOT", root),
                mock.patch.object(
                    launcher,
                    "_invoke_helper",
                    side_effect=RuntimeError("synthetic import failure"),
                ) as invoke,
            ):
                with self.assertRaisesRegex(RuntimeError, "import failure"):
                    launcher.launch()
                claimed = launcher._output_path()
                self.assertEqual(claimed.read_bytes(), b"")
                with self.assertRaisesRegex(launcher.LaunchError, "already exists"):
                    launcher.launch()
                self.assertEqual(invoke.call_count, 1)

    def test_success_fills_claim_and_partial_claim_is_never_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "research" / "experiments" / "EXP-LOCAL-003").mkdir(parents=True)
            payload = b'{"captured":true}'

            def fill() -> Path:
                claimed = launcher._output_path()
                self.assertEqual(claimed.read_bytes(), b"")
                claimed.write_bytes(payload)
                return claimed

            with (
                mock.patch.object(launcher, "REPOSITORY_ROOT", root),
                mock.patch.object(launcher, "_invoke_helper", side_effect=fill),
            ):
                result = launcher.launch()
                self.assertEqual(result.read_bytes(), payload)
                with self.assertRaisesRegex(launcher.LaunchError, "already exists"):
                    launcher.launch()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            experiment = root / "research" / "experiments" / "EXP-LOCAL-003"
            experiment.mkdir(parents=True)
            partial = experiment / "C2_L0_DEFAULT_EQUIVALENCE.json"
            partial.write_bytes(b'{"partial"')
            with (
                mock.patch.object(launcher, "REPOSITORY_ROOT", root),
                mock.patch.object(launcher, "_invoke_helper") as invoke,
            ):
                with self.assertRaisesRegex(launcher.LaunchError, "already exists"):
                    launcher.launch()
            invoke.assert_not_called()
            self.assertEqual(partial.read_bytes(), b'{"partial"')


if __name__ == "__main__":
    unittest.main()
