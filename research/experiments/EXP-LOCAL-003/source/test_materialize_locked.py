"""Static C0 tests for the locked one-shot materializer.

These tests never call ``materialize`` and therefore cannot consume an attempt.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import materialize_locked as locked

from geotarget.canonical import canonical_bytes


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _init_repository(root: Path, git: Path, label: str) -> tuple[str, str]:
    root.mkdir(parents=True)
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "EXP-LOCAL-003 test",
        "GIT_AUTHOR_EMAIL": "exp-local-003@invalid",
        "GIT_COMMITTER_NAME": "EXP-LOCAL-003 test",
        "GIT_COMMITTER_EMAIL": "exp-local-003@invalid",
    }
    for arguments in (
        ("init", "--quiet", "--initial-branch=main"),
        ("add", "--", "authority.txt"),
        ("commit", "--quiet", "-m", label),
    ):
        if arguments[0] == "add":
            (root / "authority.txt").write_text(label, encoding="utf-8")
        completed = subprocess.run(
            [str(git), *arguments],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)
    commit = subprocess.check_output(
        [str(git), "rev-parse", "HEAD"], cwd=root, env=environment, text=True
    ).strip()
    tree = subprocess.check_output(
        [str(git), "rev-parse", "HEAD^{tree}"],
        cwd=root,
        env=environment,
        text=True,
    ).strip()
    return commit, tree


def _authority(*, safety_count: int = 7) -> tuple[dict[str, Any], dict[str, Any]]:
    assessment = {
        "stage": "development",
        "stage_passed": True,
        "global_hard_safety_passed": True,
        "locked_materialization_eligible": True,
        "selected_variant": "LR-MODEL",
        "selected_path": "efficiency",
        "orthogonal_safety_disagreement_count": safety_count,
        "candidate_input_sha256": _sha("development candidate input"),
    }
    decision = {
        "schema_version": "geotarget.exp-local-003.development-decision-record/v1",
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": locked.CARD_SHA256,
        "development_gate_passed": True,
        "selected_variant": assessment["selected_variant"],
        "selected_path": assessment["selected_path"],
        "safety16_disagreement_count": safety_count,
        "candidate_input_sha256": assessment["candidate_input_sha256"],
        "development_assessment_sha256": hashlib.sha256(
            canonical_bytes(assessment)
        ).hexdigest(),
        "decision_commit": "1" * 40,
    }
    return assessment, decision


def _typed_authorization(
    assessment: dict[str, Any], decision: dict[str, Any]
) -> SimpleNamespace:
    assessment_jcs = canonical_bytes(assessment)
    decision_jcs = canonical_bytes(decision)
    assessment_sha = hashlib.sha256(assessment_jcs).hexdigest()
    decision_sha = hashlib.sha256(decision_jcs).hexdigest()
    return SimpleNamespace(
        assessor_output=SimpleNamespace(
            formal=SimpleNamespace(assessment_jcs=assessment_jcs),
            assessment_commit=decision["decision_commit"],
            assessment_file=SimpleNamespace(sha256=assessment_sha),
            decision_jcs=decision_jcs,
            decision_file=SimpleNamespace(sha256=decision_sha),
            decision_commit="3" * 40,
        )
    )


class LockedClaimTests(unittest.TestCase):
    def test_claim_and_failure_make_retry_impossible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = {
                "attempt_path": root / "attempt.json",
                "failure_path": root / "failure.json",
                "stage_anchor_path": root / "stage-anchor.json",
                "private_anchor_path": root / "private-anchor.json",
                "candidate_output": root / "candidate",
                "candidate_staging": root / ".candidate.partial",
                "assessor_vault_output": root / "assessor-vault",
                "assessor_vault_staging": root / ".assessor-vault.partial",
                "private_vault_output": root / "private-vault",
                "private_vault_staging": root / ".private-vault.partial",
            }
            locked._refuse_previous_attempt(**paths)
            locked._claim_locked_attempt(paths["attempt_path"])
            locked._record_terminal_failure(
                RuntimeError("synthetic terminal failure"),
                path=paths["failure_path"],
                attempt_path=paths["attempt_path"],
            )
            failure = json.loads(paths["failure_path"].read_text(encoding="utf-8"))
            self.assertFalse(failure["rerun_permitted"])
            self.assertEqual(
                failure["attempt_claim_sha256"], _file_sha(paths["attempt_path"])
            )
            with self.assertRaisesRegex(
                locked.LockedMaterializationError, "retry refused"
            ):
                locked._refuse_previous_attempt(**paths)
            with self.assertRaises(locked.LockedMaterializationError):
                locked._claim_locked_attempt(paths["attempt_path"])


class LockedAuthorizationTests(unittest.TestCase):
    def test_wrapper_calls_the_four_repository_typed_development_resolver(self) -> None:
        authorization_commit = "4" * 40
        authorization = SimpleNamespace(
            authorization_anchor_commit=authorization_commit,
            authorization_anchor_file=SimpleNamespace(
                path=locked._relative_repository_path(
                    locked.DEVELOPMENT_AUTHORIZATION_ANCHOR_PATH
                ),
                sha256="5" * 64,
            ),
            stage_input=SimpleNamespace(
                stage="development",
                anchor_file=SimpleNamespace(
                    path=locked._relative_repository_path(locked.STAGE_ANCHOR_PATH),
                    sha256="6" * 64,
                ),
            ),
            candidate_run=SimpleNamespace(),
            assessor_output=SimpleNamespace(),
        )
        resolve = mock.Mock(return_value=authorization)
        pin_git = mock.Mock(return_value=SimpleNamespace(path="git", sha256="7" * 64))
        authority_module = SimpleNamespace(
            resolve_development_authorization=resolve,
            pin_git_executable=pin_git,
        )
        assessor_module = SimpleNamespace(
            assess=lambda *_args: None,
            build_development_decision_record=lambda *_args: None,
        )
        with tempfile.TemporaryDirectory() as temporary:
            git = Path(temporary) / "git.exe"
            git.write_bytes(b"pinned git")
            git_sha256 = _file_sha(git)
            with mock.patch.object(locked, "_pinned_git", return_value=git):
                observed = locked._resolve_development_authorization(
                    authority_module,  # type: ignore[arg-type]
                    assessor_module,  # type: ignore[arg-type]
                    authorization_anchor_commit=authorization_commit,
                )
        self.assertIs(observed, authorization)
        pin_git.assert_called_once_with(git, git_sha256)
        self.assertEqual(
            resolve.call_args.args,
            (
                locked.REPOSITORY_ROOT,
                locked.ASSESSOR_VAULT_ROOT,
                locked.DEVELOPMENT_CANDIDATE_EVIDENCE_ROOT,
                locked.DEVELOPMENT_ASSESSOR_OUTPUT_ROOT,
            ),
        )
        self.assertEqual(
            resolve.call_args.kwargs["authorization_anchor_commit"],
            authorization_commit,
        )

    def test_bound_development_repositories_require_exact_clean_heads(self) -> None:
        git_value = shutil.which("git")
        if git_value is None:
            self.skipTest("Git is unavailable")
        git = Path(git_value).resolve()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repositories = {
                name: root / name
                for name in (
                    "main",
                    "development-input",
                    "development-private",
                    "development-run",
                    "development-output",
                )
            }
            identities = {
                name: _init_repository(path, git, name)
                for name, path in repositories.items()
            }
            future = {
                "locked-input": root / "locked-input",
                "locked-private": root / "locked-private",
                "locked-run": root / "locked-run",
                "locked-output": root / "locked-output",
            }
            authorization = SimpleNamespace(
                stage_input=SimpleNamespace(
                    assessor_vault_commit=identities["development-input"][0],
                    assessor_vault_tree=identities["development-input"][1],
                ),
                candidate_run=SimpleNamespace(
                    vault_commit=identities["development-run"][0],
                    vault_tree=identities["development-run"][1],
                ),
                assessor_output=SimpleNamespace(
                    decision_commit=identities["development-output"][0],
                    decision_tree=identities["development-output"][1],
                ),
            )
            patches = {
                "REPOSITORY_ROOT": repositories["main"],
                "ASSESSOR_VAULT_ROOT": repositories["development-input"],
                "PRIVATE_VAULT_ROOT": repositories["development-private"],
                "DEVELOPMENT_CANDIDATE_EVIDENCE_ROOT": repositories["development-run"],
                "DEVELOPMENT_ASSESSOR_OUTPUT_ROOT": repositories["development-output"],
                "LOCKED_ASSESSOR_VAULT_ROOT": future["locked-input"],
                "ASSESSOR_VAULT_STAGING_PATH": root / ".locked-input.partial",
                "LOCKED_PRIVATE_VAULT_ROOT": future["locked-private"],
                "PRIVATE_VAULT_STAGING_PATH": root / ".locked-private.partial",
                "LOCKED_CANDIDATE_EVIDENCE_ROOT": future["locked-run"],
                "LOCKED_ASSESSOR_OUTPUT_ROOT": future["locked-output"],
            }
            with (
                mock.patch.multiple(locked, **patches),
                mock.patch.object(locked, "_pinned_git", return_value=git),
            ):
                locked._verify_bound_development_repositories(authorization)

                dirty = repositories["development-run"] / "untracked.txt"
                dirty.write_text("dirty", encoding="utf-8")
                with self.assertRaisesRegex(
                    locked.LockedMaterializationError, "worktree is not clean"
                ):
                    locked._verify_bound_development_repositories(authorization)
                dirty.unlink()

                alternates = (
                    repositories["development-output"]
                    / ".git"
                    / "objects"
                    / "info"
                    / "alternates"
                )
                alternates.parent.mkdir(parents=True, exist_ok=True)
                alternates.write_text(
                    str(repositories["main"] / ".git" / "objects"),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    locked.LockedMaterializationError, "uses object alternates"
                ):
                    locked._verify_bound_development_repositories(authorization)
                alternates.unlink()

                future["locked-run"].mkdir()
                with self.assertRaisesRegex(
                    locked.LockedMaterializationError,
                    "future locked authority repository already exists",
                ):
                    locked._verify_bound_development_repositories(authorization)
                future["locked-run"].rmdir()

                authorization.assessor_output.decision_commit = "f" * 40
                with self.assertRaisesRegex(
                    locked.LockedMaterializationError,
                    "HEAD/tree differs from the typed C3 authority",
                ):
                    locked._verify_bound_development_repositories(authorization)

    def test_passing_c3_authorizes_even_when_safety16_is_nonzero(self) -> None:
        assessment, decision = _authority(safety_count=11)
        authorization = _typed_authorization(assessment, decision)
        generator_decision, formal = locked._authorization_decisions(authorization)
        self.assertEqual(generator_decision, decision)
        self.assertEqual(generator_decision["safety16_disagreement_count"], 11)
        self.assertEqual(formal["candidate_id"], "LR-MODEL")
        self.assertEqual(formal["development_path"], "efficiency")
        self.assertEqual(
            formal["development_decision_record_sha256"],
            hashlib.sha256(canonical_bytes(decision)).hexdigest(),
        )

    def test_failed_or_nonreproducible_c3_cannot_authorize(self) -> None:
        assessment, decision = _authority()
        failed = dict(assessment, stage_passed=False)
        with self.assertRaisesRegex(locked.LockedMaterializationError, "does not pass"):
            locked._authorization_decisions(_typed_authorization(failed, decision))

        mismatching = _typed_authorization(
            dict(assessment, selected_variant="LX-BOUNDS"), decision
        )
        with self.assertRaisesRegex(
            locked.LockedMaterializationError, "does not exactly bind"
        ):
            locked._authorization_decisions(mismatching)

    def test_candidate_selection_has_no_assessor_identity_and_is_cross_bound(
        self,
    ) -> None:
        assessment, decision = _authority()
        candidate_input_sha = _sha("locked candidate input")
        selection = {
            "schema_version": "geotarget.exp-local-003.locked-selection/v1",
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": locked.CARD_SHA256,
            "stage": "locked",
            "selected_variant": decision["selected_variant"],
            "candidate_input_sha256": candidate_input_sha,
        }
        self.assertNotIn("development_assessment_sha256", selection)
        self.assertNotIn("development_decision_record_sha256", selection)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            assessor_vault = root / "assessor-vault"
            private_vault = root / "private-vault"
            candidate.mkdir()
            assessor_vault.mkdir()
            (private_vault / "generator-private").mkdir(parents=True)
            selection_path = candidate / "locked-selection.json"
            locked._write_json(selection_path, selection)
            selection_record = {
                "path": selection_path.name,
                "sha256": _file_sha(selection_path),
                "bytes": selection_path.stat().st_size,
            }
            candidate_manifest = {
                "partition": "locked",
                "candidate_input_sha256": candidate_input_sha,
                "locked_selection_artifact": selection_record,
            }
            locked._write_json(candidate / "manifest.json", candidate_manifest)
            candidate_manifest_sha = _file_sha(candidate / "manifest.json")
            locked._write_json(
                candidate / locked.COMPLETION_NAME,
                {
                    "partition": "locked",
                    "candidate_manifest_sha256": candidate_manifest_sha,
                },
            )
            authority = {
                "development_assessment_sha256": decision[
                    "development_assessment_sha256"
                ],
                "development_decision_record_sha256": hashlib.sha256(
                    canonical_bytes(decision)
                ).hexdigest(),
                "decision_commit": decision["decision_commit"],
                "selected_variant": decision["selected_variant"],
                "selected_path": decision["selected_path"],
                "locked_selection_sha256": selection_record["sha256"],
            }
            locked._write_json(
                assessor_vault / "manifest.json",
                {
                    "partition": "locked",
                    "candidate_manifest_sha256": candidate_manifest_sha,
                    "locked_authority": authority,
                },
            )
            assessor_manifest_sha = _file_sha(assessor_vault / "manifest.json")
            locked._write_json(
                assessor_vault / locked.COMPLETION_NAME,
                {
                    "partition": "locked",
                    "manifest_sha256": assessor_manifest_sha,
                },
            )
            locked._write_json(
                private_vault / "generator-private" / "manifest.json",
                {"partition": "locked"},
            )
            private_stage_manifest_sha = _file_sha(
                private_vault / "generator-private" / "manifest.json"
            )
            locked._write_json(
                private_vault / "manifest.json",
                {
                    "partition": "locked",
                    "generator_private_manifest_sha256": private_stage_manifest_sha,
                },
            )
            private_manifest_sha = _file_sha(private_vault / "manifest.json")
            locked._write_json(
                private_vault / locked.COMPLETION_NAME,
                {"partition": "locked", "manifest_sha256": private_manifest_sha},
            )
            binding = locked._verify_candidate_selection_bindings(
                candidate, assessor_vault, private_vault, selection, decision
            )
            self.assertEqual(binding["selection_sha256"], selection_record["sha256"])
            self.assertEqual(binding["assessor_manifest_sha256"], assessor_manifest_sha)
            self.assertEqual(binding["private_manifest_sha256"], private_manifest_sha)


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
