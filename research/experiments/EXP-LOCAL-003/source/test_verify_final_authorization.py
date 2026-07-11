"""Read-only tests for the formal EXP-LOCAL-003 terminal verifier."""

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
from unittest import mock

import authority
import verify_final_authorization as verifier


def _resolved(allowed: bool) -> SimpleNamespace:
    return SimpleNamespace(
        authorization_anchor_commit="1" * 40,
        authorization_anchor_tree="2" * 40,
        authorization_anchor_file=SimpleNamespace(sha256="3" * 64),
        development=SimpleNamespace(
            stage_input=SimpleNamespace(
                assessor_vault_commit="4" * 40,
                assessor_vault_tree="5" * 40,
            ),
            candidate_run=SimpleNamespace(
                vault_commit="6" * 40,
                vault_tree="7" * 40,
            ),
            assessor_output=SimpleNamespace(
                decision_commit="8" * 40,
                decision_tree="9" * 40,
            ),
        ),
        stage_input=SimpleNamespace(
            assessor_vault_commit="a" * 40,
            assessor_vault_tree="b" * 40,
        ),
        candidate_run=SimpleNamespace(
            vault_commit="c" * 40,
            vault_tree="d" * 40,
        ),
        final_connection_commit="e" * 40,
        final_connection_tree="f" * 40,
        final_connection_file=SimpleNamespace(sha256="0" * 64),
        product_connection_allowed=allowed,
    )


class FinalAuthorizationVerifierTests(unittest.TestCase):
    def test_true_and_false_are_both_canonical_terminal_closures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = verifier.Layout.fixed(Path(temporary) / "solver")
            for allowed in (False, True):
                with self.subTest(allowed=allowed):
                    events: list[str] = []
                    resolved = _resolved(allowed)
                    resolve = mock.Mock(
                        side_effect=lambda *_args, **_kwargs: (
                            events.append("resolve") or resolved
                        )
                    )
                    materializer = SimpleNamespace(
                        verify_frozen_environment=lambda: events.append("environment")
                    )
                    authority_module = SimpleNamespace(
                        resolve_locked_authorization=resolve,
                        canonical_bytes=authority.canonical_bytes,
                    )
                    assessor_module = SimpleNamespace(
                        assess=mock.Mock(),
                        build_development_decision_record=mock.Mock(),
                        finalize_product_connection=mock.Mock(),
                    )
                    git = SimpleNamespace(path=Path("git.exe"), sha256="1" * 64)
                    observed_bindings: list[tuple[Path, str, str]] = []
                    private_anchors = {
                        "development": {
                            "generator_private_vault_manifest_sha256": "a" * 64,
                            "generator_private_vault_completion_sha256": "b" * 64,
                            "generator_private_manifest_sha256": "c" * 64,
                        },
                        "locked": {
                            "generator_private_vault_manifest_sha256": "d" * 64,
                            "generator_private_vault_completion_sha256": "e" * 64,
                            "generator_private_manifest_sha256": "f" * 64,
                        },
                    }

                    def private_binding(
                        _layout: verifier.Layout,
                        _git: object,
                        _authority: object,
                        _record: object,
                        stage: str,
                    ) -> tuple[str, str, object]:
                        prefix = "a" if stage == "development" else "b"
                        return (
                            prefix * 40,
                            ("c" if stage == "development" else "d") * 40,
                            private_anchors[stage],
                        )

                    def main_head(
                        _layout: verifier.Layout, _git: object
                    ) -> tuple[str, str]:
                        events.append("main-head")
                        return (
                            resolved.authorization_anchor_commit,
                            resolved.authorization_anchor_tree,
                        )

                    def bound_head(
                        _git: object, repository: Path, commit: str, tree: str
                    ) -> None:
                        observed_bindings.append((repository, commit, tree))

                    with (
                        mock.patch.object(
                            verifier, "_main_c6_head", side_effect=main_head
                        ),
                        mock.patch.object(
                            verifier, "_require_bound_head", side_effect=bound_head
                        ),
                        mock.patch.object(
                            verifier,
                            "_private_anchor_binding",
                            side_effect=private_binding,
                        ),
                        mock.patch.object(
                            verifier, "_verify_private_repository"
                        ) as verify_private,
                        mock.patch.object(verifier, "_git_text", return_value="main"),
                    ):
                        payload = verifier.verify(
                            layout=layout,
                            materializer_module=materializer,  # type: ignore[arg-type]
                            authority_module=authority_module,  # type: ignore[arg-type]
                            assessor_module=assessor_module,  # type: ignore[arg-type]
                            git_executable=git,
                        )

                    document = json.loads(payload)
                    self.assertEqual(payload, authority.canonical_bytes(document))
                    self.assertIs(document["product_connection_allowed"], allowed)
                    self.assertTrue(document["terminal_closure"])
                    self.assertFalse(document["rerun_permitted"])
                    self.assertEqual(
                        events[:4],
                        ["main-head", "environment", "main-head", "resolve"],
                    )
                    self.assertEqual(len(observed_bindings), 9)
                    self.assertEqual(
                        observed_bindings[0],
                        (
                            layout.main,
                            resolved.authorization_anchor_commit,
                            resolved.authorization_anchor_tree,
                        ),
                    )
                    self.assertEqual(
                        observed_bindings[-1],
                        (
                            layout.locked_output,
                            resolved.final_connection_commit,
                            resolved.final_connection_tree,
                        ),
                    )
                    self.assertEqual(
                        observed_bindings[2],
                        (layout.development_private, "a" * 40, "c" * 40),
                    )
                    self.assertEqual(
                        observed_bindings[6],
                        (layout.locked_private, "b" * 40, "d" * 40),
                    )
                    self.assertEqual(verify_private.call_count, 2)
                    self.assertEqual(
                        resolve.call_args.args,
                        (
                            layout.main,
                            layout.development_input,
                            layout.development_candidate,
                            layout.development_output,
                            layout.locked_input,
                            layout.locked_candidate,
                            layout.locked_output,
                        ),
                    )
                    self.assertEqual(
                        resolve.call_args.kwargs["authorization_anchor_commit"],
                        resolved.authorization_anchor_commit,
                    )

    def test_main_must_be_main_and_exact_c6_introduction(self) -> None:
        layout = verifier.Layout.fixed(Path("C:/synthetic/solver"))
        git = SimpleNamespace(path=Path("git.exe"), sha256="1" * 64)
        with mock.patch.object(verifier, "_git_text", return_value="topic"):
            with self.assertRaisesRegex(
                verifier.FinalVerificationError, "requires main branch"
            ):
                verifier._main_c6_head(layout, git)

        def git_text(_git: object, _repository: Path, *arguments: str) -> str:
            if arguments[:2] == ("branch", "--show-current"):
                return "main"
            if arguments and arguments[0] == "log":
                return "9" * 40
            raise AssertionError(arguments)

        with (
            mock.patch.object(verifier, "_git_text", side_effect=git_text),
            mock.patch.object(
                verifier, "_clean_head", return_value=("1" * 40, "2" * 40)
            ),
        ):
            with self.assertRaisesRegex(
                verifier.FinalVerificationError, "not the C6.*introduction"
            ):
                verifier._main_c6_head(layout, git)

    def test_bound_repository_must_be_clean_and_at_typed_head(self) -> None:
        git = SimpleNamespace(path=Path("git.exe"), sha256="1" * 64)
        repository = Path("C:/synthetic/external")
        with mock.patch.object(
            verifier, "_clean_head", return_value=("1" * 40, "2" * 40)
        ):
            verifier._require_bound_head(git, repository, "1" * 40, "2" * 40)
            with self.assertRaisesRegex(
                verifier.FinalVerificationError, "differs from C6 authority"
            ):
                verifier._require_bound_head(git, repository, "3" * 40, "2" * 40)

    def test_private_anchor_is_bound_to_public_stage_and_private_head(self) -> None:
        layout = verifier.Layout.fixed(Path("C:/synthetic/solver"))
        git = SimpleNamespace(path=Path("git.exe"), sha256="1" * 64)
        public_anchor = {
            "materialization_attempt_claim_sha256": "2" * 64,
            "candidate_manifest_sha256": "3" * 64,
        }
        stage_record = SimpleNamespace(
            anchor_commit="4" * 40,
            source_lock_commit="5" * 40,
            anchor_file=SimpleNamespace(sha256="6" * 64),
            anchor=public_anchor,
        )
        private_anchor = {
            "schema_version": (
                "geotarget.exp-local-003.generator-private-vault-anchor/v1"
            ),
            "experiment_id": verifier.EXPERIMENT_ID,
            "card_sha256": verifier.CARD_SHA256,
            "stage": "development",
            "source_lock_commit": "5" * 40,
            "materialization_attempt_claim_sha256": "2" * 64,
            "stage_vault_anchor_sha256": "6" * 64,
            "generator_private_vault_git_commit": "7" * 40,
            "generator_private_vault_git_tree": "8" * 40,
            "generator_private_vault_manifest_sha256": "9" * 64,
            "generator_private_vault_completion_sha256": "a" * 64,
            "generator_private_manifest_sha256": "b" * 64,
            "candidate_manifest_sha256": "3" * 64,
            "candidate_visible": False,
            "formal_assessor_input": False,
            "rerun_permitted": False,
        }
        payload = authority.canonical_bytes(private_anchor)
        with mock.patch.object(verifier, "_git_bytes", return_value=payload):
            commit, tree, observed = verifier._private_anchor_binding(
                layout,
                git,
                authority,
                stage_record,
                "development",
            )
        self.assertEqual((commit, tree), ("7" * 40, "8" * 40))
        self.assertEqual(observed, private_anchor)

        split = dict(private_anchor)
        split["candidate_manifest_sha256"] = "c" * 64
        with (
            mock.patch.object(
                verifier, "_git_bytes", return_value=authority.canonical_bytes(split)
            ),
            self.assertRaisesRegex(
                verifier.FinalVerificationError, "split from its formal stage anchor"
            ),
        ):
            verifier._private_anchor_binding(
                layout,
                git,
                authority,
                stage_record,
                "development",
            )

    def test_private_repository_requires_root_commit_and_bound_blobs(self) -> None:
        git = SimpleNamespace(path=Path("git.exe"), sha256="1" * 64)
        repository = Path("C:/synthetic/private")
        commit = "7" * 40
        blobs = {
            "manifest.json": b"manifest",
            "ONE_SHOT_COMPLETE.json": b"complete",
            "generator-private/manifest.json": b"private-manifest",
        }
        anchor = {
            "generator_private_vault_manifest_sha256": hashlib.sha256(
                blobs["manifest.json"]
            ).hexdigest(),
            "generator_private_vault_completion_sha256": hashlib.sha256(
                blobs["ONE_SHOT_COMPLETE.json"]
            ).hexdigest(),
            "generator_private_manifest_sha256": hashlib.sha256(
                blobs["generator-private/manifest.json"]
            ).hexdigest(),
        }

        def git_text(_git: object, _repository: Path, *arguments: str) -> str:
            if arguments == ("branch", "--show-current"):
                return "private-evidence"
            if arguments[:4] == ("rev-list", "--parents", "-n", "1"):
                return commit
            raise AssertionError(arguments)

        def git_bytes(_git: object, _repository: Path, *arguments: str) -> bytes:
            relative = arguments[-1].split(":", 1)[1]
            return blobs[relative]

        with (
            mock.patch.object(verifier, "_git_text", side_effect=git_text),
            mock.patch.object(verifier, "_git_bytes", side_effect=git_bytes),
        ):
            verifier._verify_private_repository(
                git, repository, commit, "8" * 40, anchor, "development"
            )

        bad = dict(anchor)
        bad["generator_private_manifest_sha256"] = "0" * 64
        with (
            mock.patch.object(verifier, "_git_text", side_effect=git_text),
            mock.patch.object(verifier, "_git_bytes", side_effect=git_bytes),
            self.assertRaisesRegex(
                verifier.FinalVerificationError, "anchor hash mismatch"
            ),
        ):
            verifier._verify_private_repository(
                git, repository, commit, "8" * 40, bad, "development"
            )

    def test_clean_head_independently_rejects_ignored_hardlink_and_alternates(
        self,
    ) -> None:
        git_path = Path(shutil.which("git") or "")
        if not git_path.is_file():
            self.skipTest("Git is unavailable")
        git = SimpleNamespace(
            path=git_path,
            sha256=hashlib.sha256(git_path.read_bytes()).hexdigest(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "evidence"
            repository.mkdir()

            def run(*arguments: str) -> None:
                completed = subprocess.run(
                    [
                        str(git_path),
                        "-c",
                        "core.autocrlf=false",
                        "-C",
                        str(repository),
                        *arguments,
                    ],
                    check=False,
                    capture_output=True,
                )
                if completed.returncode != 0:
                    self.fail(completed.stderr.decode(errors="replace"))

            run("init", "--quiet", "--initial-branch=main")
            run("config", "core.autocrlf", "false")
            (repository / "nested").mkdir()
            tracked = repository / "nested" / "authority.json"
            tracked.write_bytes(b'{"closed":true}')
            run("add", "--all")
            run(
                "-c",
                "user.name=Verifier Test",
                "-c",
                "user.email=verifier@invalid",
                "commit",
                "--quiet",
                "-m",
                "closed evidence",
            )
            commit, tree = verifier._clean_head(git, repository)
            self.assertTrue(commit)
            self.assertTrue(tree)

            (repository / ".git" / "info" / "exclude").write_text(
                "ignored.tmp\n", encoding="ascii"
            )
            ignored = repository / "ignored.tmp"
            ignored.write_bytes(b"hidden")
            with self.assertRaisesRegex(
                verifier.FinalVerificationError, "inventory differs"
            ):
                verifier._clean_head(git, repository)
            ignored.unlink()

            alias = root / "outside-hardlink.json"
            try:
                os.link(tracked, alias)
            except OSError:
                pass
            else:
                with self.assertRaisesRegex(
                    verifier.FinalVerificationError, "unaliased regular file"
                ):
                    verifier._clean_head(git, repository)
                alias.unlink()

            alternates = repository / ".git" / "objects" / "info" / "alternates"
            alternates.write_text(str(root / "elsewhere"), encoding="utf-8")
            with self.assertRaisesRegex(
                verifier.FinalVerificationError, "redirected/incomplete"
            ):
                verifier._clean_head(git, repository)


if __name__ == "__main__":
    unittest.main()
