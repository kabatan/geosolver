from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import formal_publication_guard_a2 as guard  # noqa: E402


AMENDMENT = HERE.parent / "formal-publication-binding-amendment-a2.json"


class NoReplaceTests(unittest.TestCase):
    def test_existing_target_is_never_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "receipt.json"
            target.write_text("sentinel", encoding="utf-8")
            with self.assertRaises(guard.PublicationBindingError):
                guard._write_json_no_replace(target, {"passed": True})
            self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")

    def test_creation_race_preserves_competing_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "receipt.json"
            real_link = os.link

            def raced_link(source: Path, destination: Path) -> None:
                Path(destination).write_text("competitor", encoding="utf-8")
                real_link(source, destination)

            with (
                mock.patch.object(guard.os, "link", side_effect=raced_link),
                self.assertRaises(guard.PublicationBindingError),
            ):
                guard._write_json_no_replace(target, {"passed": True})
            self.assertEqual(target.read_text(encoding="utf-8"), "competitor")

    def test_success_is_read_back_and_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "receipt.json"
            digest = guard._write_json_no_replace(target, {"passed": True})
            self.assertEqual(digest, hashlib.sha256(target.read_bytes()).hexdigest())


class HygieneTests(unittest.TestCase):
    @staticmethod
    def _clean_status(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")

    def test_ignored_source_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with (
                mock.patch.object(guard.subprocess, "run", side_effect=self._clean_status),
                mock.patch.object(
                    guard,
                    "_git_z_paths",
                    side_effect=[
                        [],
                        ["research/experiments/EXP-JAC-003/source/__pycache__/json.pyc"],
                    ],
                ),
                self.assertRaises(guard.PublicationBindingError),
            ):
                guard._verify_worktree_hygiene(
                    Path(raw),
                    allowed_staging="research/results/staging",
                    allowed_exact=(),
                )

    def test_only_exact_results_are_allowed_post(self) -> None:
        files = [
            "research/results/staging/capture.json",
            "research/results/outer.json",
            "research/results/host.json",
            "research/results/source.json",
        ]
        with tempfile.TemporaryDirectory() as raw:
            with (
                mock.patch.object(guard.subprocess, "run", side_effect=self._clean_status),
                mock.patch.object(guard, "_git_z_paths", side_effect=[files, []]),
            ):
                result = guard._verify_worktree_hygiene(
                    Path(raw),
                    allowed_staging="research/results/staging",
                    allowed_exact=(
                        "research/results/outer.json",
                        "research/results/host.json",
                        "research/results/source.json",
                    ),
                )
        self.assertEqual(result["rejected_file_count"], 0)
        self.assertEqual(result["output_file_count"], 4)

    def test_pre_requires_zero_ignored_and_untracked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with (
                mock.patch.object(guard.subprocess, "run", side_effect=self._clean_status),
                mock.patch.object(
                    guard, "_git_z_paths", side_effect=[[".ruff_cache/cache"], []]
                ),
                self.assertRaises(guard.PublicationBindingError),
            ):
                guard._verify_worktree_hygiene(Path(raw), allowed_staging=None)


class InventoryTests(unittest.TestCase):
    def test_inventory_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            payload = root / "opaque-segment.json"
            payload.write_bytes(b"opaque-a")
            frozen = guard._inventory(root)
            payload.write_bytes(b"opaque-b")
            with self.assertRaises(guard.PublicationBindingError):
                guard._verify_inventory_rows(root, frozen)

    def test_membership_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "capture.json").write_bytes(b"capture")
            frozen = guard._inventory(root)
            (root / "unexpected.json").write_bytes(b"unexpected")
            with self.assertRaises(guard.PublicationBindingError):
                guard._verify_inventory_rows(root, frozen)

    def test_inventory_hashes_opaque_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            payload = root / "segment.json"
            payload.write_bytes(b"not JSON and not interpreted")
            inventory = guard._inventory(root)
        self.assertEqual(inventory["file_count"], 1)
        self.assertEqual(
            inventory["files"][0]["sha256"],
            hashlib.sha256(b"not JSON and not interpreted").hexdigest(),
        )


class FrozenPlanTests(unittest.TestCase):
    def test_amendment_binds_executing_checker(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        checker_sha = hashlib.sha256(
            (HERE / "formal_publication_guard_a2.py").read_bytes()
        ).hexdigest()
        self.assertEqual(amendment["checker"]["sha256"], checker_sha)
        self.assertEqual(
            amendment["v1_authority"]["checker_sha256"],
            hashlib.sha256((HERE / "formal_binding_guard.py").read_bytes()).hexdigest(),
        )

    def test_wrong_finalizer_tokens_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            v1_path = root / "v1.json"
            expected = ["python", "finalizer.py", "--repo", "repo"]
            v1_path.write_text(
                json.dumps(
                    {"execution_plan": {"exact_finalizer_command_tokens": expected}}
                ),
                encoding="utf-8",
            )
            amendment = {
                "execution": {
                    "exact_finalizer_command_tokens": [*expected, "--extra"]
                }
            }
            paths = {
                "v1_amendment": v1_path,
                "python": Path("python"),
                "finalizer": Path("finalizer.py"),
            }
            with self.assertRaises(guard.PublicationBindingError):
                guard._finalizer_tokens(amendment, paths)

    def test_finalizer_environment_disables_bytecode_and_python_injection(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        with mock.patch.dict(
            os.environ,
            {"PYTHONPATH": "injected", "PYTHONHOME": "injected"},
            clear=False,
        ):
            environment, audit = guard._finalizer_environment(amendment)
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("PYTHONHOME", environment)
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(audit["fixed_overrides"]["PYTHONNOUSERSITE"], "1")

    def test_phase_token_arrays_have_no_duplicate_flags(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        for phase in ("pre", "publish", "archive"):
            tokens = guard._phase_tokens(amendment, phase)
            flags = [token for token in tokens if token.startswith("--")]
            self.assertEqual(len(flags), len(set(flags)))


class AnchorTests(unittest.TestCase):
    def test_anchor_detects_post_seal_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            seal = Path(raw) / "seal.json"
            seal.write_bytes(b"sealed")
            expected = hashlib.sha256(seal.read_bytes()).hexdigest()
            seal.write_bytes(b"mutated")
            with self.assertRaises(guard.PublicationBindingError):
                guard._verify_file_hash(seal, expected, "seal")

    def test_archive_copy_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            copied = Path(raw) / "audit.json"
            copied.write_bytes(b"wrong archive copy")
            expected = hashlib.sha256(b"expected archive copy").hexdigest()
            with self.assertRaises(guard.PublicationBindingError):
                guard._verify_file_hash(copied, expected, "archived audit")


if __name__ == "__main__":
    unittest.main()
