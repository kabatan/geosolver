from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import launch_candidate  # noqa: E402


def _paths(stage: launch_candidate.Stage, root: Path) -> launch_candidate.EvidencePaths:
    paths = launch_candidate.EvidencePaths.fixed(stage, root=root)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.scratch_root.mkdir(parents=True, exist_ok=True)
    return paths


class CandidateLauncherTests(unittest.TestCase):
    def test_empty_claim_then_nonce_uses_same_file_identity(self) -> None:
        for stage in ("development", "locked"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                paths = _paths(stage, Path(temporary) / "evidence")
                calls: list[tuple[str, int]] = []
                real_empty = launch_candidate._exclusive_empty
                real_fill = launch_candidate._fill_existing

                def empty(path: Path) -> None:
                    real_empty(path)
                    calls.append(("empty", path.stat().st_ino))
                    self.assertEqual(path.read_bytes(), b"")

                def fill(path: Path, payload: bytes) -> None:
                    calls.append(("fill-before", path.stat().st_ino))
                    self.assertEqual(path.read_bytes(), b"")
                    real_fill(path, payload)
                    calls.append(("fill-after", path.stat().st_ino))

                with (
                    mock.patch.object(
                        launch_candidate, "_exclusive_empty", side_effect=empty
                    ),
                    mock.patch.object(
                        launch_candidate, "_fill_existing", side_effect=fill
                    ),
                    mock.patch.object(
                        launch_candidate.secrets,
                        "token_hex",
                        return_value="ab" * 32,
                    ),
                ):
                    claim = launch_candidate._claim(stage, paths)
                self.assertEqual(
                    [name for name, _ in calls], ["empty", "fill-before", "fill-after"]
                )
                self.assertEqual(len({inode for _, inode in calls}), 1)
                self.assertEqual(claim.identity.inode, calls[0][1])
                document = json.loads(claim.payload)
                self.assertEqual(
                    document,
                    {
                        "schema_version": launch_candidate.CLAIM_SCHEMA,
                        "card_sha256": launch_candidate.CARD_SHA256,
                        "stage": stage,
                        "nonce": "ab" * 32,
                        "rerun_permitted": False,
                        "failure_is_terminal": True,
                    },
                )
                self.assertEqual(
                    launch_candidate._canonical_bytes(document), claim.payload
                )
                launch_candidate.verify_claim(claim, paths)
                self.assertNotEqual(paths.root, paths.scratch_root)
                self.assertNotIn(paths.root, paths.scratch_root.parents)
                self.assertNotIn(paths.scratch_root, paths.root.parents)

    def test_missing_c0_scratch_namespace_fails_before_marker_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "evidence"
            root.mkdir()
            paths = launch_candidate.EvidencePaths.fixed("development", root=root)
            self.assertFalse(paths.scratch_root.exists())
            with self.assertRaisesRegex(
                launch_candidate.CandidateLaunchError, "scratch namespace"
            ):
                launch_candidate._claim("development", paths)
            self.assertFalse(paths.attempt_marker.exists())

    def test_claim_precedes_only_c0_observer_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths("development", Path(temporary) / "evidence")
            calls: list[str] = []

            def observe_claimed(**kwargs: object) -> str:
                calls.append("observe")
                self.assertEqual(kwargs["stage"], "development")
                self.assertIs(kwargs["paths"], paths)
                claim = kwargs["claim"]
                self.assertEqual(claim.path.read_bytes(), claim.payload)  # type: ignore[union-attr]
                return "published"

            def loader() -> object:
                calls.append("import-c0-observer")
                self.assertTrue(paths.attempt_marker.is_file())
                self.assertFalse(paths.evidence_repository.exists())
                return SimpleNamespace(
                    C0_OBSERVER_OWNS_CANDIDATE_PROCESS=True,
                    observe_claimed=observe_claimed,
                )

            result = launch_candidate.launch(
                "development",
                paths=paths,
                module_loader=loader,  # type: ignore[arg-type]
            )
            self.assertEqual(result, "published")
            self.assertEqual(calls, ["import-c0-observer", "observe"])

    def test_marker_replacement_is_rejected_even_with_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths("development", Path(temporary) / "evidence")
            claim = launch_candidate._claim("development", paths)
            payload = claim.payload
            paths.attempt_marker.unlink()
            paths.attempt_marker.write_bytes(payload)
            with self.assertRaisesRegex(
                launch_candidate.CandidateLaunchError, "marker differs"
            ):
                launch_candidate.verify_claim(claim, paths)

    def test_default_loader_imports_only_fixed_c0_observer(self) -> None:
        fake = SimpleNamespace(
            __file__=str(SOURCE_ROOT / "candidate_observer.py"),
            C0_OBSERVER_OWNS_CANDIDATE_PROCESS=True,
            observe_claimed=mock.Mock(),
        )
        original = list(sys.path)
        sys.path[:] = [entry for entry in sys.path if entry != str(SOURCE_ROOT)]
        try:
            with (
                mock.patch.object(
                    launch_candidate.importlib,
                    "import_module",
                    return_value=fake,
                ) as importer,
                mock.patch.object(
                    launch_candidate, "_activate_claimed_import_paths"
                ) as activate,
            ):
                self.assertIs(launch_candidate._load_observer(), fake)
        finally:
            sys.path[:] = original
        importer.assert_called_once_with("candidate_observer")
        activate.assert_called_once_with()

    def test_import_failure_leaves_nonce_bound_terminal_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths("locked", Path(temporary) / "evidence")
            failure = mock.Mock(side_effect=ImportError("synthetic C0 import failure"))
            with self.assertRaisesRegex(ImportError, "synthetic C0 import failure"):
                launch_candidate.launch("locked", paths=paths, module_loader=failure)
            marker = json.loads(paths.attempt_marker.read_bytes())
            self.assertEqual(marker["stage"], "locked")
            self.assertRegex(marker["nonce"], r"^[0-9a-f]{64}$")
            retry = mock.Mock()
            with self.assertRaisesRegex(
                launch_candidate.CandidateLaunchError, "overwrite, resume, or retry"
            ):
                launch_candidate.launch("locked", paths=paths, module_loader=retry)
            retry.assert_not_called()

    def test_every_fixed_occupied_name_is_terminal_before_import(self) -> None:
        for occupied_name in (
            "evidence_repository",
            "staging_repository",
            "attempt_marker",
            "scratch_directory",
        ):
            with (
                self.subTest(occupied=occupied_name),
                tempfile.TemporaryDirectory() as temporary,
            ):
                paths = _paths("development", Path(temporary) / "evidence")
                occupied = getattr(paths, occupied_name)
                if occupied_name == "attempt_marker":
                    occupied.write_bytes(b"prior")
                else:
                    occupied.mkdir()
                loader = mock.Mock()
                with self.assertRaisesRegex(
                    launch_candidate.CandidateLaunchError, "overwrite, resume, or retry"
                ):
                    launch_candidate.launch(
                        "development", paths=paths, module_loader=loader
                    )
                loader.assert_not_called()

    def test_observer_contract_fails_closed(self) -> None:
        cases = (
            SimpleNamespace(observe_claimed=mock.Mock()),
            SimpleNamespace(C0_OBSERVER_OWNS_CANDIDATE_PROCESS=True),
        )
        for index, module in enumerate(cases):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as temporary:
                paths = _paths("locked", Path(temporary) / "evidence")
                with self.assertRaises(launch_candidate.CandidateLaunchError):
                    launch_candidate.launch(
                        "locked",
                        paths=paths,
                        module_loader=lambda module=module: module,  # type: ignore[arg-type,return-value]
                    )
                self.assertTrue(paths.attempt_marker.is_file())

    def test_cli_rejects_wrong_flags_and_extra_arguments_before_claim(self) -> None:
        script = SOURCE_ROOT / "launch_candidate.py"
        wrong_flags = subprocess.run(
            [sys.executable, "-B", str(script), "development"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(wrong_flags.returncode, 0)
        self.assertIn("requires `python -I -B -S", wrong_flags.stderr)
        extra = subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(script), "locked", "extra"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(extra.returncode, 0)
        self.assertIn("usage:", extra.stderr)


if __name__ == "__main__":
    unittest.main()
