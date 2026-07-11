"""Git-transaction tests for the closed EXP-LOCAL-003 main-stage sealer."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import seal_main_stage as sealer


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _Repository:
    def __init__(self, root: Path) -> None:
        self.root = root
        executable = shutil.which("git")
        if executable is None:
            raise unittest.SkipTest("Git is unavailable")
        self.git = Path(executable).resolve()
        self.run("init", "-b", "main")
        (root / "base.txt").write_bytes(b"immutable-base\n")
        self.run("add", "--", "base.txt")
        self.run(
            "-c",
            "user.name=synthetic test",
            "-c",
            "user.email=synthetic@invalid",
            "commit",
            "-m",
            "synthetic base",
        )

    def run(
        self, *arguments: str, allowed_returncodes: tuple[int, ...] = (0,)
    ) -> subprocess.CompletedProcess[bytes]:
        completed = subprocess.run(
            [str(self.git), *arguments],
            cwd=self.root,
            check=False,
            capture_output=True,
        )
        if completed.returncode not in allowed_returncodes:
            raise AssertionError(
                f"git {' '.join(arguments)} failed: "
                f"{completed.stderr.decode('utf-8', 'replace')}"
            )
        return completed

    def text(self, *arguments: str) -> str:
        return self.run(*arguments).stdout.decode("utf-8", "strict").strip()

    @property
    def experiment(self) -> Path:
        return self.root / "research" / "experiments" / "EXP-LOCAL-003"

    @property
    def environment_lock(self) -> Path:
        return self.experiment / "environment-lock.json"

    def create_environment_lock(self, *, digest: str | None = None) -> None:
        self.environment_lock.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "tools": {
                "git_executable": str(self.git),
                "git_sha256": _sha256(self.git) if digest is None else digest,
            }
        }
        self.environment_lock.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def create_stage_files(self, stage: sealer.Stage) -> None:
        for index, relative in enumerate(sealer._STAGE_PATHS[stage]):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if stage == "c0-environment":
                self.create_environment_lock()
            else:
                path.write_bytes(f"{stage}:{index}:{relative}\n".encode())


@contextmanager
def _patched_repository() -> Iterator[_Repository]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        repository = _Repository(root)
        previous_cwd = Path.cwd()
        os.chdir(root)
        try:
            with (
                mock.patch.object(sealer, "REPOSITORY_ROOT", root),
                mock.patch.object(sealer, "EXPERIMENT_ROOT", repository.experiment),
                mock.patch.object(
                    sealer, "ENVIRONMENT_LOCK_PATH", repository.environment_lock
                ),
            ):
                yield repository
        finally:
            os.chdir(previous_cwd)


class SealMainStageTests(unittest.TestCase):
    def test_all_eight_stages_form_the_exact_linear_single_parent_chain(self) -> None:
        with _patched_repository() as repository:
            verification_stages: list[sealer.Stage] = []
            previous = repository.text("rev-parse", "HEAD")
            previous_epoch = int(
                repository.text("show", "-s", "--format=%ct", previous)
            )

            for stage in sealer.STAGES:
                repository.create_stage_files(stage)

                def verify(current: sealer.Stage = stage) -> None:
                    verification_stages.append(current)
                    self.assertEqual(repository.text("rev-parse", "HEAD"), previous)
                    self.assertEqual(
                        repository.run(
                            "diff", "--cached", "--name-only", "HEAD", "--"
                        ).stdout,
                        b"",
                    )

                with mock.patch.object(
                    sealer.materialization,
                    "verify_frozen_environment",
                    side_effect=verify,
                ):
                    commit = sealer.seal_stage(stage)
                self.assertEqual(repository.text("rev-parse", "HEAD"), commit)
                self.assertEqual(
                    repository.text("rev-list", "--parents", "-n", "1", commit),
                    f"{commit} {previous}",
                )
                changed = set(
                    repository.text(
                        "diff-tree",
                        "--no-commit-id",
                        "--name-only",
                        "-r",
                        commit,
                    ).splitlines()
                )
                self.assertEqual(changed, set(sealer._STAGE_PATHS[stage]))
                for relative in sealer._STAGE_PATHS[stage]:
                    entry = repository.text("ls-tree", commit, "--", relative)
                    self.assertTrue(entry.startswith("100644 blob "), entry)
                    committed = repository.run("show", f"{commit}:{relative}").stdout
                    self.assertEqual(
                        committed, (repository.root / relative).read_bytes()
                    )
                observed_epoch = int(
                    repository.text("show", "-s", "--format=%ct", commit)
                )
                self.assertEqual(observed_epoch, previous_epoch + 1)
                self.assertEqual(
                    repository.run(
                        "status", "--porcelain=v1", "--untracked-files=all"
                    ).stdout,
                    b"",
                )
                previous = commit
                previous_epoch = observed_epoch

            self.assertEqual(verification_stages, list(sealer.STAGES))
            self.assertEqual(
                len(repository.text("rev-list", "--first-parent", "HEAD").splitlines()),
                1 + len(sealer.STAGES),
            )

    def test_extra_or_non_addition_state_is_rejected_before_verification(self) -> None:
        with _patched_repository() as repository:
            repository.create_stage_files("c0-environment")
            (repository.root / "unexpected.txt").write_bytes(b"unexpected")
            verifier = mock.Mock()
            with (
                mock.patch.object(
                    sealer.materialization,
                    "verify_frozen_environment",
                    side_effect=verifier,
                ),
                self.assertRaisesRegex(sealer.MainStageSealError, "closed stage set"),
            ):
                sealer.seal_stage("c0-environment")
            verifier.assert_not_called()
            self.assertEqual(
                repository.run("diff", "--cached", "--name-only", "HEAD", "--").stdout,
                b"",
            )

        with _patched_repository() as repository:
            repository.create_stage_files("c0-environment")
            repository.run("add", "--", str(repository.environment_lock))
            verifier = mock.Mock()
            with (
                mock.patch.object(
                    sealer.materialization,
                    "verify_frozen_environment",
                    side_effect=verifier,
                ),
                self.assertRaisesRegex(sealer.MainStageSealError, "index|Git diff"),
            ):
                sealer.seal_stage("c0-environment")
            verifier.assert_not_called()

    def test_environment_failure_occurs_before_the_first_git_mutation(self) -> None:
        with _patched_repository() as repository:
            repository.create_stage_files("c0-environment")
            index_before = (repository.root / ".git" / "index").read_bytes()
            objects_before = {
                path.relative_to(repository.root / ".git" / "objects").as_posix(): (
                    path.read_bytes()
                )
                for path in (repository.root / ".git" / "objects").rglob("*")
                if path.is_file()
            }

            def fail() -> None:
                raise RuntimeError("synthetic frozen-environment failure")

            with (
                mock.patch.object(
                    sealer.materialization,
                    "verify_frozen_environment",
                    side_effect=fail,
                ),
                self.assertRaisesRegex(RuntimeError, "frozen-environment"),
            ):
                sealer.seal_stage("c0-environment")
            self.assertEqual(
                repository.run("diff", "--cached", "--name-only", "HEAD", "--").stdout,
                b"",
            )
            self.assertEqual(
                (repository.root / ".git" / "index").read_bytes(), index_before
            )
            self.assertEqual(
                {
                    path.relative_to(repository.root / ".git" / "objects").as_posix(): (
                        path.read_bytes()
                    )
                    for path in (repository.root / ".git" / "objects").rglob("*")
                    if path.is_file()
                },
                objects_before,
            )
            self.assertEqual(
                repository.text("status", "--porcelain=v1", "--untracked-files=all"),
                "?? research/experiments/EXP-LOCAL-003/environment-lock.json",
            )

    def test_each_stage_requires_head_to_introduce_the_immediate_predecessor(
        self,
    ) -> None:
        with _patched_repository() as repository:
            repository.create_stage_files("c0-environment")
            with mock.patch.object(sealer.materialization, "verify_frozen_environment"):
                sealer.seal_stage("c0-environment")
            (repository.root / "intervening.txt").write_bytes(b"forbidden\n")
            repository.run("add", "--", "intervening.txt")
            repository.run(
                "-c",
                "user.name=synthetic test",
                "-c",
                "user.email=synthetic@invalid",
                "commit",
                "-m",
                "intervening commit",
            )
            repository.create_stage_files("c0-lock")
            verifier = mock.Mock()
            with (
                mock.patch.object(
                    sealer.materialization,
                    "verify_frozen_environment",
                    side_effect=verifier,
                ),
                self.assertRaisesRegex(sealer.MainStageSealError, "preceding"),
            ):
                sealer.seal_stage("c0-lock")
            verifier.assert_not_called()

    def test_pinned_git_hash_main_root_and_replace_refs_are_closed(self) -> None:
        with self.subTest("Git digest"):
            with _patched_repository() as repository:
                repository.create_environment_lock(digest="0" * 64)
                with self.assertRaisesRegex(
                    sealer.MainStageSealError, "Git executable changed"
                ):
                    sealer.seal_stage("c0-environment")

        with self.subTest("branch"):
            with _patched_repository() as repository:
                repository.create_stage_files("c0-environment")
                repository.run("switch", "-c", "not-main")
                with self.assertRaisesRegex(sealer.MainStageSealError, "main branch"):
                    sealer.seal_stage("c0-environment")

        with self.subTest("cwd"):
            with _patched_repository() as repository:
                repository.create_stage_files("c0-environment")
                child = repository.root / "child"
                child.mkdir()
                os.chdir(child)
                with self.assertRaisesRegex(
                    sealer.MainStageSealError, "repository root"
                ):
                    sealer.seal_stage("c0-environment")

        with self.subTest("replace"):
            with _patched_repository() as repository:
                repository.create_stage_files("c0-environment")
                head = repository.text("rev-parse", "HEAD")
                replacement = repository.text(
                    "-c",
                    "user.name=synthetic test",
                    "-c",
                    "user.email=synthetic@invalid",
                    "commit-tree",
                    f"{head}^{{tree}}",
                )
                repository.run("replace", head, replacement)
                with self.assertRaisesRegex(sealer.MainStageSealError, "replace refs"):
                    sealer.seal_stage("c0-environment")

        with self.subTest("object alternates"):
            with _patched_repository() as repository:
                repository.create_stage_files("c0-environment")
                info = repository.root / ".git" / "objects" / "info"
                info.mkdir(parents=True, exist_ok=True)
                (info / "alternates").write_text(
                    str(repository.root / "external-objects"), encoding="utf-8"
                )
                verifier = mock.Mock()
                with (
                    mock.patch.object(
                        sealer.materialization,
                        "verify_frozen_environment",
                        side_effect=verifier,
                    ),
                    self.assertRaisesRegex(sealer.MainStageSealError, "alternates"),
                ):
                    sealer.seal_stage("c0-environment")
                verifier.assert_not_called()

    def test_linked_worktree_is_not_a_formal_main_object_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            container = Path(temporary).resolve()
            primary_root = container / "primary"
            primary_root.mkdir()
            primary = _Repository(primary_root)
            primary.run("switch", "--detach")
            linked_root = container / "linked"
            primary.run("worktree", "add", str(linked_root), "main")
            experiment = linked_root / "research" / "experiments" / "EXP-LOCAL-003"
            environment_lock = experiment / "environment-lock.json"
            experiment.mkdir(parents=True)
            environment_lock.write_text(
                json.dumps(
                    {
                        "tools": {
                            "git_executable": str(primary.git),
                            "git_sha256": _sha256(primary.git),
                        }
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            previous_cwd = Path.cwd()
            os.chdir(linked_root)
            try:
                with (
                    mock.patch.object(sealer, "REPOSITORY_ROOT", linked_root),
                    mock.patch.object(sealer, "EXPERIMENT_ROOT", experiment),
                    mock.patch.object(
                        sealer, "ENVIRONMENT_LOCK_PATH", environment_lock
                    ),
                    mock.patch.object(
                        sealer.materialization, "verify_frozen_environment"
                    ) as verifier,
                    self.assertRaisesRegex(
                        sealer.MainStageSealError, "direct .git object database"
                    ),
                ):
                    sealer.seal_stage("c0-environment")
                verifier.assert_not_called()
            finally:
                os.chdir(previous_cwd)

    def test_cli_accepts_only_one_closed_stage_name(self) -> None:
        for arguments in ([], ["--help"], ["c1", "--force"], ["C1"]):
            with (
                self.subTest(arguments=arguments),
                self.assertRaisesRegex(sealer.MainStageSealError, "usage"),
            ):
                sealer.main(arguments)

    def test_cli_requires_isolated_direct_unoptimized_invocation(self) -> None:
        valid_flags = SimpleNamespace(
            isolated=1,
            ignore_environment=1,
            no_user_site=1,
            safe_path=True,
            dont_write_bytecode=True,
            no_site=1,
            optimize=0,
        )
        with _patched_repository():
            with (
                mock.patch.object(sealer.sys, "flags", valid_flags),
                mock.patch.object(sealer.sys, "argv", [str(Path(sealer.__file__))]),
                mock.patch.object(sealer, "seal_stage", return_value="a" * 40) as seal,
            ):
                self.assertEqual(sealer.main(["c0-environment"]), 0)
            seal.assert_called_once_with("c0-environment")

            invalid_flags = SimpleNamespace(**vars(valid_flags))
            invalid_flags.optimize = 1
            with (
                mock.patch.object(sealer.sys, "flags", invalid_flags),
                mock.patch.object(sealer.sys, "argv", [str(Path(sealer.__file__))]),
                self.assertRaisesRegex(sealer.MainStageSealError, "Python -I -B"),
            ):
                sealer.main(["c0-environment"])

            with (
                mock.patch.object(sealer.sys, "flags", valid_flags),
                mock.patch.object(sealer.sys, "argv", ["different-script.py"]),
                self.assertRaisesRegex(sealer.MainStageSealError, "directly"),
            ):
                sealer.main(["c0-environment"])


if __name__ == "__main__":
    unittest.main()
