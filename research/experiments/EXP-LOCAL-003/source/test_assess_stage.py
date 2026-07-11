from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from jsonschema import Draft202012Validator


SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
for source in (PYTHON_SOURCE, SOURCE_ROOT):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

import assess_stage  # noqa: E402
import authority  # noqa: E402
import test_authority as authority_fixtures  # noqa: E402


def _record(path: str, token: str) -> authority.FileRecord:
    payload = token.encode()
    return authority.FileRecord(path, assess_stage._sha256(payload), len(payload))


def _resolved(stage: assess_stage.Stage) -> assess_stage.ResolvedStage:
    input_file = _record(
        (
            "research/experiments/EXP-LOCAL-003/C1_STAGE_VAULT_ANCHOR.json"
            if stage == "development"
            else "research/experiments/EXP-LOCAL-003/C4_LOCKED_STAGE_VAULT_ANCHOR.json"
        ),
        f"{stage}-input",
    )
    lock_file = _record(
        "research/experiments/EXP-LOCAL-003/"
        + (
            "candidate-execution-lock.json"
            if stage == "development"
            else "locked-candidate-execution-lock.json"
        ),
        f"{stage}-lock",
    )
    stage_input = SimpleNamespace(
        stage=stage,
        assessor_truth={"stage": stage},
        bootstrap_indices=b"bootstrap",
        development_authority=(
            None
            if stage == "development"
            else {"development_authorization_anchor_commit": "d" * 40}
        ),
    )
    candidate = SimpleNamespace(
        raw_output={"stage": stage},
        candidate_execution_lock={"stage": stage},
        candidate_execution_lock_file=lock_file,
    )
    return assess_stage.ResolvedStage(
        head_commit="5" * 40,
        head_tree="6" * 40,
        input_commit="4" * 40,
        input_tree="7" * 40,
        input_file=input_file,
        stage_input=stage_input,
        candidate_run=candidate,
        candidate_commit="8" * 40,
        candidate_tree="9" * 40,
        candidate_authority_file=_record(
            "candidate-run-authority.json", f"{stage}-candidate"
        ),
    )


def _published(root: Path, stage: assess_stage.Stage) -> assess_stage.PublishedOutput:
    child = (
        assess_stage.DEVELOPMENT_DECISION_PATH
        if stage == "development"
        else assess_stage.FINAL_CONNECTION_PATH
    )
    return assess_stage.PublishedOutput(
        repository=root,
        assessment_commit="a" * 40,
        assessment_tree="b" * 40,
        assessment_file=_record(assess_stage.ASSESSMENT_PATH, f"{stage}-assessment"),
        authority_file=_record(
            assess_stage.ASSESSOR_AUTHORITY_PATH, f"{stage}-authority"
        ),
        child_commit="c" * 40,
        child_tree="e" * 40,
        child_file=_record(child, f"{stage}-child"),
    )


def _committed_repository(
    path: Path, git: authority.GitExecutable, files: dict[str, bytes]
) -> tuple[str, str]:
    path.mkdir(parents=True)
    assess_stage._git(git, path, "init", "--quiet")
    for relative, payload in files.items():
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return assess_stage._commit_files(
        path, git, tuple(sorted(files)), "synthetic immutable authority"
    )


def _dict_record(path: str, payload: bytes) -> dict[str, object]:
    return {
        "path": path,
        "sha256": assess_stage._sha256(payload),
        "byte_length": len(payload),
    }


def _fixed_candidate_evidence(
    source: Path,
    destination: Path,
    git: authority.GitExecutable,
) -> tuple[str, str, authority.FileRecord]:
    """Re-seal the authority test fixture under the production fixed paths."""

    destination.mkdir()
    assess_stage._git(git, destination, "init", "--quiet")
    attempt_path = "attempt-claim.json"
    raw_path = "candidate-output.json.gz"
    seal_path = "candidate-output-preexit-seal.json"
    exit_path = "candidate-process-exit.json"
    manifest_path = "manifest.json"
    authority_path = "candidate-run-authority.json"

    stage = destination.name.removesuffix("-candidate-run")
    source_marker = source.parent / f"{stage}-candidate-run.attempt"
    destination_marker = destination.parent / f"{stage}-candidate-run.attempt"
    marker_bytes = source_marker.read_bytes()
    destination_marker.write_bytes(marker_bytes)
    marker_info = destination_marker.lstat()
    attempt = json.loads((source / "run/attempt-claim.json").read_text("utf-8"))
    launcher_claim = dict(attempt["launcher_claim"])
    launcher_claim["file"] = _dict_record(destination_marker.name, marker_bytes)
    launcher_claim["filesystem_identity"] = {
        "device_decimal": str(marker_info.st_dev),
        "inode_decimal": str(marker_info.st_ino),
        "empty_claim_ctime_nanoseconds_decimal": str(marker_info.st_ctime_ns),
        "link_count": 1,
    }
    attempt["launcher_claim"] = launcher_claim
    request = attempt["sandbox_request"]
    probes = request["access_probes"]
    probes[4]["path"] = str(destination.parent.absolute())
    probes[5]["path"] = str(
        destination.parent.absolute() / f".{stage}-candidate-run-staging.partial"
    )
    probes[6]["path"] = str(destination_marker.absolute())
    request["access_probe_manifest_sha256"] = assess_stage._sha256(
        authority.canonical_bytes(probes)
    )
    request_sha256 = assess_stage._sha256(authority.canonical_bytes(request))
    attempt_bytes = authority.canonical_bytes(attempt)
    attempt_record = _dict_record(attempt_path, attempt_bytes)
    (destination / attempt_path).write_bytes(attempt_bytes)
    attempt_commit, attempt_tree = assess_stage._commit_files(
        destination, git, (attempt_path,), "candidate attempt claim"
    )

    raw_bytes = (source / "run/candidate-output.json.gz").read_bytes()
    raw_record = _dict_record(raw_path, raw_bytes)
    (destination / raw_path).write_bytes(raw_bytes)
    raw_commit, raw_tree = assess_stage._commit_files(
        destination, git, (raw_path,), "candidate raw output"
    )

    seal = json.loads((source / "run/preexit-seal.json").read_text("utf-8"))
    seal["launcher_claim"] = launcher_claim
    seal["raw_output"] = raw_record
    seal["changed_paths"] = [raw_path]
    seal["sandbox_request_sha256"] = request_sha256
    seal_bytes = authority.canonical_bytes(seal)
    seal_record = _dict_record(seal_path, seal_bytes)
    (destination / seal_path).write_bytes(seal_bytes)
    seal_commit, seal_tree = assess_stage._commit_files(
        destination, git, (seal_path,), "candidate pre-exit seal"
    )

    exit_document = json.loads((source / "run/process-exit.json").read_text("utf-8"))
    exit_document["launcher_claim"] = launcher_claim
    exit_document["raw_output"] = raw_record
    exit_document["preexit_seal"] = seal_record
    exit_document["changed_paths"] = [raw_path]
    exit_document["event"]["parent"]["sha256"] = seal_record["sha256"]
    exit_probes = exit_document["sandbox_result"]["appcontainer_attestation"][
        "access_probes"
    ]
    for index in (4, 5, 6):
        exit_probes[index]["path"] = probes[index]["path"]
    exit_bytes = authority.canonical_bytes(exit_document)
    exit_record = _dict_record(exit_path, exit_bytes)
    (destination / exit_path).write_bytes(exit_bytes)
    exit_commit, exit_tree = assess_stage._commit_files(
        destination, git, (exit_path,), "candidate process exit"
    )

    manifest = json.loads((source / "run/manifest.json").read_text("utf-8"))
    records = {
        "raw_output": raw_record,
        "preexit_seal": seal_record,
        "process_exit": exit_record,
    }
    for entry in manifest["files"]:
        entry["file"] = records[entry["role"]]
    manifest_bytes = authority.canonical_bytes(manifest)
    manifest_record = _dict_record(manifest_path, manifest_bytes)

    document = json.loads(
        (source / "run/candidate-run-authority.json").read_text("utf-8")
    )
    document["attempt_claim"] = attempt_record
    document["raw_output"] = raw_record
    document["preexit_seal"] = seal_record
    document["process_exit"] = exit_record
    document["changed_paths"] = [raw_path]
    document["manifest"] = manifest_record
    document["event"]["parent"]["sha256"] = exit_record["sha256"]
    document["sandbox_result_sha256"] = assess_stage._sha256(
        authority.canonical_bytes(exit_document["sandbox_result"])
    )
    document["history"] = {
        "attempt_claim": {"commit": attempt_commit, "tree": attempt_tree},
        "raw_output": {"commit": raw_commit, "tree": raw_tree},
        "preexit_seal": {"commit": seal_commit, "tree": seal_tree},
        "process_exit": {"commit": exit_commit, "tree": exit_tree},
    }
    authority_bytes = authority.canonical_bytes(document)
    authority_record = authority.FileRecord(
        authority_path,
        assess_stage._sha256(authority_bytes),
        len(authority_bytes),
    )
    (destination / manifest_path).write_bytes(manifest_bytes)
    (destination / authority_path).write_bytes(authority_bytes)
    commit, tree = assess_stage._commit_files(
        destination,
        git,
        (manifest_path, authority_path),
        "candidate run authority",
    )
    return commit, tree, authority_record


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(child) for child in value]
    return value


def _synthetic_assessment(raw: object, *_args: object) -> dict[str, object]:
    document = _thaw(raw)
    if not isinstance(document, dict):
        raise TypeError("synthetic raw document must be a mapping")
    return {
        "schema_version": "synthetic-assessment/v1",
        "stage": document["stage"],
        "candidate_input_sha256": document["candidate_input_sha256"],
        "report_only_times": {
            "process_cpu_seconds": 0,
            "end_to_end_cpu_seconds": 0,
            "formal_wall_seconds": None,
            "host_exclusion_passed": False,
        },
    }


def _synthetic_decision(
    assessment: object,
    _raw: object,
    _truth: object,
    _bootstrap: bytes,
    _lock: object,
    decision_commit: str,
) -> dict[str, object]:
    document = _thaw(assessment)
    if not isinstance(document, dict):
        raise TypeError("synthetic assessment must be a mapping")
    return {
        "schema_version": "geotarget.exp-local-003.development-decision-record/v1",
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": assess_stage.CARD_SHA256,
        "development_gate_passed": True,
        "selected_variant": "LX-BOUNDS",
        "selected_path": "recall",
        "safety16_disagreement_count": 0,
        "candidate_input_sha256": document["candidate_input_sha256"],
        "development_assessment_sha256": assess_stage._sha256(
            authority.canonical_bytes(document)
        ),
        "decision_commit": decision_commit,
    }


def _synthetic_finalizer(
    development: object,
    locked: object,
    decision: object,
    **_kwargs: object,
) -> dict[str, object]:
    development_document = _thaw(development)
    locked_document = _thaw(locked)
    decision_document = _thaw(decision)
    if not all(
        isinstance(document, dict)
        for document in (
            development_document,
            locked_document,
            decision_document,
        )
    ):
        raise TypeError("synthetic finalizer inputs must be mappings")
    return {
        "schema_version": "geotarget.exp-local-003.final-connection/v1",
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": assess_stage.CARD_SHA256,
        "development_assessment_sha256": assess_stage._sha256(
            authority.canonical_bytes(development_document)
        ),
        "development_decision_record_sha256": assess_stage._sha256(
            authority.canonical_bytes(decision_document)
        ),
        "locked_assessment_sha256": assess_stage._sha256(
            authority.canonical_bytes(locked_document)
        ),
        "selected_variant": decision_document["selected_variant"],
        "selected_path": decision_document["selected_path"],
        "development_safety16_clear": False,
        "locked_stage_passed": False,
        "product_connection_allowed": False,
    }


class AssessStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        git = Path(shutil.which("git") or "")
        if not git.is_absolute():
            raise unittest.SkipTest("Git is unavailable")
        cls.git = authority.pin_git_executable(
            git, assess_stage._sha256(git.read_bytes())
        )

    def test_fixed_layout_uses_physically_separate_sibling_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            main = Path(temporary) / "solver"
            layout = assess_stage.Layout.fixed(main)
            self.assertEqual(layout.repository_root, main.absolute())
            self.assertIn("solver-vault", str(layout.development_input_vault))
            self.assertIn(
                "solver-run-evidence", str(layout.development_candidate_evidence)
            )
            self.assertIn(
                "solver-assessment-evidence",
                str(layout.development_assessor_output),
            )
            self.assertEqual(
                layout.final_connection_anchor.name,
                "C6_FINAL_CONNECTION_ANCHOR.json",
            )

    def test_cli_rejects_missing_flags_and_extra_arguments_before_mutation(
        self,
    ) -> None:
        script = SOURCE_ROOT / "assess_stage.py"
        without_isolation = subprocess.run(
            [sys.executable, "-B", str(script), "development"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(without_isolation.returncode, 0)
        self.assertIn("requires exact Python flags -I -B", without_isolation.stderr)
        without_no_site = subprocess.run(
            [sys.executable, "-I", "-B", str(script), "development"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(without_no_site.returncode, 0)
        self.assertIn("flags -I -B -S", without_no_site.stderr)
        extra = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-S",
                str(script),
                "development",
                "extra",
            ],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(extra.returncode, 0)
        self.assertIn("usage:", extra.stderr)

    def test_formal_dependency_activation_occurs_only_after_durable_claim(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = assess_stage.Layout.fixed(Path(temporary) / "solver")
            events: list[str] = []

            def claim(*_args: object) -> tuple[Path, Path]:
                events.append("claim")
                return (
                    layout.development_assessor_output,
                    layout.development_assessor_output.with_name("staging"),
                )

            def activate() -> None:
                events.append("activate")

            with (
                mock.patch.object(assess_stage, "_claim_output", side_effect=claim),
                mock.patch.object(
                    assess_stage,
                    "_activate_claimed_import_paths",
                    side_effect=activate,
                ),
                mock.patch.object(
                    assess_stage,
                    "_bootstrap_pinned_git",
                    side_effect=RuntimeError("stop after import boundary"),
                ),
                self.assertRaisesRegex(RuntimeError, "import boundary"),
            ):
                assess_stage.run_stage(
                    "development",
                    layout=layout,
                    _activate_formal_imports=True,
                )
            self.assertEqual(events, ["claim", "activate"])

    def test_environment_lock_pins_exact_git_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = assess_stage.Layout.fixed(Path(temporary) / "solver")
            layout.environment_lock.parent.mkdir(parents=True)
            document = {
                "schema_version": "exp-local-003-environment-lock/v1",
                "card_sha256": assess_stage.CARD_SHA256,
                "tools": {
                    "git_executable": str(self.git.path),
                    "git_sha256": self.git.sha256,
                },
            }
            layout.environment_lock.write_bytes(authority.canonical_bytes(document))
            self.assertEqual(assess_stage._pinned_git(layout, authority), self.git)
            document["tools"]["git_sha256"] = "0" * 64
            layout.environment_lock.write_bytes(authority.canonical_bytes(document))
            with self.assertRaisesRegex(
                assess_stage.AssessmentStageError, "Git executable drift"
            ):
                assess_stage._pinned_git(layout, authority)

    def test_output_is_orphan_assessment_plus_exact_single_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = assess_stage.Layout.fixed(Path(temporary) / "solver")
            formal = SimpleNamespace(
                assessment_jcs=authority.canonical_bytes(
                    {"schema_version": "test-assessment/v1", "stage": "development"}
                ),
                authority_jcs=authority.canonical_bytes(
                    {"schema_version": "test-authority/v1", "stage": "development"}
                ),
            )

            def child(commit: str) -> dict[str, object]:
                return {
                    "schema_version": "test-decision/v1",
                    "decision_commit": commit,
                }

            layout.development_assessor_output.parent.mkdir(parents=True)
            claimed = assess_stage._claim_output("development", layout)
            assess_stage._initialize_output_repository(
                "development", claimed[1], self.git
            )
            published = assess_stage._publish_output(
                "development",
                layout=layout,
                authority_module=authority,
                git_executable=self.git,
                formal=formal,
                build_child=child,
                claimed_paths=claimed,
            )
            repository = authority.GitObjectRepository(published.repository, self.git)
            self.assertEqual(repository.commit_parents(published.assessment_commit), ())
            self.assertEqual(
                repository.commit_parents(published.child_commit),
                (published.assessment_commit,),
            )
            self.assertEqual(
                set(repository.tree_index(published.assessment_commit)),
                {assess_stage.ASSESSMENT_PATH, assess_stage.ASSESSOR_AUTHORITY_PATH},
            )
            self.assertEqual(
                set(repository.tree_index(published.child_commit)),
                {
                    assess_stage.ASSESSMENT_PATH,
                    assess_stage.ASSESSOR_AUTHORITY_PATH,
                    assess_stage.DEVELOPMENT_DECISION_PATH,
                },
            )
            with self.assertRaisesRegex(
                assess_stage.AssessmentStageError, "overwrite, resume, or retry"
            ):
                assess_stage._publish_output(
                    "development",
                    layout=layout,
                    authority_module=authority,
                    git_executable=self.git,
                    formal=formal,
                    build_child=child,
                )

    def test_output_verifier_rejects_child_that_rewrites_a_parent_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "assessment"
            repository.mkdir()
            assess_stage._git(self.git, repository, "init", "--quiet")
            expected_assessment = b'{"stage":"development"}'
            wrong_assessment = b'{"stage":"forged"}'
            authority_bytes = b'{"authority":true}'
            child_bytes = b'{"decision":true}'
            (repository / assess_stage.ASSESSMENT_PATH).write_bytes(wrong_assessment)
            (repository / assess_stage.ASSESSOR_AUTHORITY_PATH).write_bytes(
                authority_bytes
            )
            root_commit, root_tree = assess_stage._commit_files(
                repository,
                self.git,
                (
                    assess_stage.ASSESSMENT_PATH,
                    assess_stage.ASSESSOR_AUTHORITY_PATH,
                ),
                "forged assessment root",
            )
            (repository / assess_stage.ASSESSMENT_PATH).write_bytes(expected_assessment)
            (repository / assess_stage.DEVELOPMENT_DECISION_PATH).write_bytes(
                child_bytes
            )
            child_commit, child_tree = assess_stage._commit_files(
                repository,
                self.git,
                (
                    assess_stage.ASSESSMENT_PATH,
                    assess_stage.DEVELOPMENT_DECISION_PATH,
                ),
                "rewritten child",
            )
            with self.assertRaisesRegex(
                assess_stage.AssessmentStageError, "assessment root blob differs"
            ):
                assess_stage._verify_published_output(
                    authority_module=authority,
                    repository=repository,
                    git_executable=self.git,
                    assessment_commit=root_commit,
                    assessment_tree=root_tree,
                    assessment_file=assess_stage._file_record(
                        authority,
                        assess_stage.ASSESSMENT_PATH,
                        expected_assessment,
                    ),
                    authority_file=assess_stage._file_record(
                        authority,
                        assess_stage.ASSESSOR_AUTHORITY_PATH,
                        authority_bytes,
                    ),
                    child_commit=child_commit,
                    child_tree=child_tree,
                    child_file=assess_stage._file_record(
                        authority,
                        assess_stage.DEVELOPMENT_DECISION_PATH,
                        child_bytes,
                    ),
                    assessment_bytes=expected_assessment,
                    authority_bytes=authority_bytes,
                    child_bytes=child_bytes,
                )

    def test_partial_staging_is_a_terminal_no_retry_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = assess_stage.Layout.fixed(Path(temporary) / "solver")
            _output, staging, _anchor = assess_stage._stage_output_paths(
                "locked", layout
            )
            staging.parent.mkdir(parents=True)
            staging.mkdir()
            with self.assertRaisesRegex(
                assess_stage.AssessmentStageError, "overwrite, resume, or retry"
            ):
                assess_stage._claim_output("locked", layout)

    def test_candidate_evidence_head_is_the_exact_fixed_six_file_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "candidate"
            repository.mkdir()
            assess_stage._git(self.git, repository, "init", "--quiet")
            for path in assess_stage.CANDIDATE_EVIDENCE_PATHS:
                (repository / path).write_bytes(f"evidence:{path}".encode())
            assess_stage._commit_files(
                repository,
                self.git,
                tuple(sorted(assess_stage.CANDIDATE_EVIDENCE_PATHS)),
                "closed candidate evidence",
            )
            _commit, _tree, record = assess_stage._candidate_authority(
                authority, repository, self.git
            )
            self.assertEqual(record.path, "candidate-run-authority.json")
            (repository / "extra.json").write_bytes(b"forbidden")
            assess_stage._commit_files(
                repository, self.git, ("extra.json",), "smuggled extra"
            )
            with self.assertRaisesRegex(
                assess_stage.AssessmentStageError, "closed six-file tree"
            ):
                assess_stage._candidate_authority(authority, repository, self.git)

    def test_assessor_failure_leaves_terminal_staging_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = assess_stage.Layout.fixed(Path(temporary) / "solver")
            layout.development_assessor_output.parent.mkdir(parents=True)
            resolved = _resolved("development")
            assessor = SimpleNamespace(assess=mock.Mock())
            with (
                mock.patch.object(
                    assess_stage, "_bootstrap_pinned_git", return_value=self.git
                ),
                mock.patch.object(assess_stage, "_verify_contract_sources_at_head"),
                mock.patch.object(assess_stage, "_pinned_git", return_value=self.git),
                mock.patch.object(
                    assess_stage,
                    "_assert_clean_head",
                    return_value=("h" * 40, "t" * 40),
                ),
                mock.patch.object(
                    assess_stage, "_resolve_stage", return_value=resolved
                ),
                mock.patch.object(assess_stage, "_initialize_output_repository"),
                mock.patch.object(assess_stage, "_verify_repository_storage"),
                mock.patch.object(assess_stage, "_verify_main_branch"),
                mock.patch.object(assess_stage, "_verify_frozen_environment"),
                mock.patch.object(
                    authority,
                    "assess_with_authority",
                    side_effect=RuntimeError("synthetic assessor failure"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic assessor failure"):
                    assess_stage.run_stage(
                        "development",
                        layout=layout,
                        authority_module=authority,
                        assessor_module=assessor,
                    )
            _output, staging, _anchor = assess_stage._stage_output_paths(
                "development", layout
            )
            self.assertTrue(staging.is_dir())
            with self.assertRaisesRegex(
                assess_stage.AssessmentStageError, "overwrite, resume, or retry"
            ):
                assess_stage.run_stage(
                    "development",
                    layout=layout,
                    authority_module=authority,
                    assessor_module=assessor,
                )

    def test_project_import_failure_is_also_a_terminal_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = assess_stage.Layout.fixed(Path(temporary) / "solver")
            layout.development_assessor_output.parent.mkdir(parents=True)
            with (
                mock.patch.object(
                    assess_stage, "_bootstrap_pinned_git", return_value=self.git
                ),
                mock.patch.object(
                    assess_stage,
                    "_assert_clean_head",
                    return_value=("h" * 40, "t" * 40),
                ),
                mock.patch.object(assess_stage, "_verify_main_branch"),
                mock.patch.object(assess_stage, "_verify_contract_sources_at_head"),
                mock.patch.object(assess_stage, "_verify_frozen_environment"),
                mock.patch.object(
                    assess_stage,
                    "_load_contract_modules",
                    side_effect=ImportError("synthetic project import failure"),
                ),
            ):
                with self.assertRaisesRegex(ImportError, "project import failure"):
                    assess_stage.run_stage("development", layout=layout)
            _output, staging, _anchor = assess_stage._stage_output_paths(
                "development", layout
            )
            self.assertTrue(staging.is_dir())
            self.assertEqual(
                (staging / assess_stage.ATTEMPT_MARKER).read_bytes(),
                assess_stage._attempt_marker_bytes("development"),
            )
            with self.assertRaisesRegex(
                assess_stage.AssessmentStageError, "overwrite, resume, or retry"
            ):
                assess_stage.run_stage("development", layout=layout)

    def test_frozen_environment_failure_is_a_terminal_claim_before_assessor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = assess_stage.Layout.fixed(Path(temporary) / "solver")
            layout.development_assessor_output.parent.mkdir(parents=True)
            assessor = SimpleNamespace(assess=mock.Mock())
            with (
                mock.patch.object(
                    assess_stage, "_bootstrap_pinned_git", return_value=self.git
                ),
                mock.patch.object(assess_stage, "_verify_contract_sources_at_head"),
                mock.patch.object(assess_stage, "_pinned_git", return_value=self.git),
                mock.patch.object(assess_stage, "_initialize_output_repository"),
                mock.patch.object(assess_stage, "_verify_repository_storage"),
                mock.patch.object(
                    assess_stage,
                    "_assert_clean_head",
                    return_value=("h" * 40, "t" * 40),
                ),
                mock.patch.object(assess_stage, "_verify_main_branch"),
                mock.patch.object(
                    assess_stage,
                    "_verify_frozen_environment",
                    side_effect=RuntimeError("synthetic environment drift"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "environment drift"):
                    assess_stage.run_stage(
                        "development",
                        layout=layout,
                        authority_module=authority,
                        assessor_module=assessor,
                    )
            _output, staging, _anchor = assess_stage._stage_output_paths(
                "development", layout
            )
            self.assertTrue(staging.is_dir())
            assessor.assess.assert_not_called()

    def test_main_branch_must_be_named_main(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "main"
            repository.mkdir()
            assess_stage._git(self.git, repository, "init", "--quiet")
            (repository / "base").write_bytes(b"base")
            assess_stage._commit_files(repository, self.git, ("base",), "base")
            assess_stage._git(self.git, repository, "branch", "-M", "not-main")
            with self.assertRaisesRegex(
                assess_stage.AssessmentStageError, "branch must be main"
            ):
                assess_stage._verify_main_branch(repository, self.git)
            assess_stage._git(self.git, repository, "branch", "-M", "main")
            assess_stage._verify_main_branch(repository, self.git)

    def test_frozen_environment_verifier_loads_only_the_fixed_c0_module(
        self,
    ) -> None:
        module = SimpleNamespace()
        verifier = mock.Mock()

        class Loader:
            def exec_module(self, target: object) -> None:
                target.__file__ = str(SOURCE_ROOT / "materialize_development.py")
                target.verify_frozen_environment = verifier

        spec = SimpleNamespace(loader=Loader())
        with (
            mock.patch.object(
                assess_stage.importlib.util,
                "spec_from_file_location",
                return_value=spec,
            ) as locate,
            mock.patch.object(
                assess_stage.importlib.util,
                "module_from_spec",
                return_value=module,
            ),
        ):
            assess_stage._verify_frozen_environment()
        locate.assert_called_once_with(
            "_exp_local_003_frozen_environment_verifier",
            SOURCE_ROOT / "materialize_development.py",
        )
        verifier.assert_called_once_with()

    def test_uncommitted_anchor_requires_unchanged_head_and_only_one_new_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            main = Path(temporary) / "solver"
            main.mkdir()
            assess_stage._git(self.git, main, "init", "--quiet")
            assess_stage._git(self.git, main, "branch", "-M", "main")
            (main / "base.txt").write_bytes(b"base")
            head, tree = assess_stage._commit_files(
                main, self.git, ("base.txt",), "base"
            )
            layout = assess_stage.Layout.fixed(main)
            layout.development_anchor.parent.mkdir(parents=True)
            payload = b'{"anchor":true}'
            assess_stage._exclusive_write(layout.development_anchor, payload)
            assess_stage._verify_uncommitted_anchor(
                layout=layout,
                anchor=layout.development_anchor,
                payload=payload,
                expected_commit=head,
                expected_tree=tree,
                git_executable=self.git,
            )
            (main / "smuggled.txt").write_bytes(b"extra")
            with self.assertRaisesRegex(
                assess_stage.AssessmentStageError, "HEAD/worktree changed"
            ):
                assess_stage._verify_uncommitted_anchor(
                    layout=layout,
                    anchor=layout.development_anchor,
                    payload=payload,
                    expected_commit=head,
                    expected_tree=tree,
                    git_executable=self.git,
                )

    def test_development_run_glue_publishes_real_git_output_and_c3_anchor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = assess_stage.Layout.fixed(Path(temporary) / "solver")
            main = layout.repository_root
            main.mkdir()
            assess_stage._git(self.git, main, "init", "--quiet")
            assess_stage._git(self.git, main, "branch", "-M", "main")
            input_path = "research/experiments/EXP-LOCAL-003/C1_STAGE_VAULT_ANCHOR.json"
            input_bytes = b'{"synthetic":"c1"}'
            input_file_path = main / input_path
            input_file_path.parent.mkdir(parents=True)
            input_file_path.write_bytes(input_bytes)
            input_commit, input_tree = assess_stage._commit_files(
                main, self.git, (input_path,), "synthetic C1"
            )
            lock_path = (
                "research/experiments/EXP-LOCAL-003/candidate-execution-lock.json"
            )
            (main / lock_path).write_bytes(b'{"synthetic":"c2"}')
            head_commit, head_tree = assess_stage._commit_files(
                main, self.git, (lock_path,), "synthetic C2"
            )
            input_vault_commit, input_vault_tree = _committed_repository(
                layout.development_input_vault,
                self.git,
                {"vault.json": b"input"},
            )
            candidate_payload = b'{"synthetic":"candidate-authority"}'
            candidate_commit, candidate_tree = _committed_repository(
                layout.development_candidate_evidence,
                self.git,
                {"candidate-run-authority.json": candidate_payload},
            )
            stage_input = SimpleNamespace(
                assessor_vault_commit=input_vault_commit,
                assessor_vault_tree=input_vault_tree,
                assessor_truth={"stage": "development"},
                bootstrap_indices=b"bootstrap",
                development_authority=None,
            )
            candidate_run = SimpleNamespace(
                raw_output={"stage": "development"},
                candidate_execution_lock={"stage": "development"},
            )
            resolved = assess_stage.ResolvedStage(
                head_commit=head_commit,
                head_tree=head_tree,
                input_commit=input_commit,
                input_tree=input_tree,
                input_file=assess_stage._file_record(
                    authority, input_path, input_bytes
                ),
                stage_input=stage_input,
                candidate_run=candidate_run,
                candidate_commit=candidate_commit,
                candidate_tree=candidate_tree,
                candidate_authority_file=assess_stage._file_record(
                    authority,
                    "candidate-run-authority.json",
                    candidate_payload,
                ),
            )
            formal = SimpleNamespace(
                assessment={"stage": "development"},
                assessment_jcs=b'{"stage":"development"}',
                authority_jcs=b'{"stage":"development"}',
            )
            assessor = SimpleNamespace(
                assess=mock.Mock(),
                build_development_decision_record=mock.Mock(
                    return_value={
                        "schema_version": "synthetic-decision/v1",
                        "decision_commit": "placeholder",
                    }
                ),
            )
            layout.development_assessor_output.parent.mkdir(parents=True, exist_ok=True)
            with (
                mock.patch.object(
                    assess_stage, "_bootstrap_pinned_git", return_value=self.git
                ),
                mock.patch.object(assess_stage, "_verify_contract_sources_at_head"),
                mock.patch.object(assess_stage, "_pinned_git", return_value=self.git),
                mock.patch.object(
                    assess_stage, "_resolve_stage", return_value=resolved
                ),
                mock.patch.object(assess_stage, "_verify_frozen_environment"),
                mock.patch.object(
                    authority, "assess_with_authority", return_value=formal
                ),
            ):
                anchor = assess_stage.run_stage(
                    "development",
                    layout=layout,
                    authority_module=authority,
                    assessor_module=assessor,
                )
            self.assertEqual(anchor, layout.development_anchor)
            anchor_document = json.loads(anchor.read_text("utf-8"))
            schema = json.loads(
                (
                    SOURCE_ROOT / "development-authorization-anchor.schema.json"
                ).read_text("utf-8")
            )
            Draft202012Validator(schema).validate(anchor_document)
            output_head, _output_tree = assess_stage._assert_clean_head(
                layout.development_assessor_output, self.git
            )
            self.assertEqual(
                output_head,
                anchor_document["assessor_output"]["decision_commit"],
            )
            self.assertEqual(
                set(
                    authority.GitObjectRepository(
                        layout.development_assessor_output, self.git
                    ).tree_index(output_head)
                ),
                {
                    assess_stage.ASSESSMENT_PATH,
                    assess_stage.ASSESSOR_AUTHORITY_PATH,
                    assess_stage.DEVELOPMENT_DECISION_PATH,
                },
            )

    def test_locked_run_glue_publishes_real_git_output_and_c6_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = assess_stage.Layout.fixed(Path(temporary) / "solver")
            main = layout.repository_root
            main.mkdir()
            assess_stage._git(self.git, main, "init", "--quiet")
            assess_stage._git(self.git, main, "branch", "-M", "main")
            c4_path = (
                "research/experiments/EXP-LOCAL-003/C4_LOCKED_STAGE_VAULT_ANCHOR.json"
            )
            c4_bytes = b'{"synthetic":"c4"}'
            c4_file = main / c4_path
            c4_file.parent.mkdir(parents=True)
            c4_file.write_bytes(c4_bytes)
            c4_commit, c4_tree = assess_stage._commit_files(
                main, self.git, (c4_path,), "synthetic C4"
            )
            c5_path = (
                "research/experiments/EXP-LOCAL-003/"
                "locked-candidate-execution-lock.json"
            )
            c5_bytes = b'{"synthetic":"c5"}'
            (main / c5_path).write_bytes(c5_bytes)
            c5_commit, c5_tree = assess_stage._commit_files(
                main, self.git, (c5_path,), "synthetic C5"
            )
            dev_input_commit, dev_input_tree = _committed_repository(
                layout.development_input_vault,
                self.git,
                {"development-input.json": b"input"},
            )
            dev_candidate_commit, dev_candidate_tree = _committed_repository(
                layout.development_candidate_evidence,
                self.git,
                {"candidate-run-authority.json": b"development candidate"},
            )
            dev_output_commit, dev_output_tree = _committed_repository(
                layout.development_assessor_output,
                self.git,
                {"development-decision-record.json": b"decision"},
            )
            locked_input_commit, locked_input_tree = _committed_repository(
                layout.locked_input_vault,
                self.git,
                {"locked-input.json": b"input"},
            )
            locked_candidate_payload = b'{"synthetic":"locked-candidate"}'
            locked_candidate_commit, locked_candidate_tree = _committed_repository(
                layout.locked_candidate_evidence,
                self.git,
                {"candidate-run-authority.json": locked_candidate_payload},
            )
            development_anchor_file = _record(
                "research/experiments/EXP-LOCAL-003/"
                "C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json",
                "development-anchor",
            )
            development = SimpleNamespace(
                authorization_anchor_commit="d" * 40,
                authorization_anchor_tree="e" * 40,
                authorization_anchor_file=development_anchor_file,
                stage_input=SimpleNamespace(
                    assessor_vault_commit=dev_input_commit,
                    assessor_vault_tree=dev_input_tree,
                    assessor_truth={"stage": "development"},
                    bootstrap_indices=b"development-bootstrap",
                ),
                candidate_run=SimpleNamespace(
                    vault_commit=dev_candidate_commit,
                    vault_tree=dev_candidate_tree,
                    raw_output={"stage": "development"},
                    candidate_execution_lock={"stage": "development"},
                ),
                assessor_output=SimpleNamespace(
                    decision_commit=dev_output_commit,
                    decision_tree=dev_output_tree,
                    decision={"schema_version": "synthetic-decision/v1"},
                    formal=SimpleNamespace(assessment={"stage": "development"}),
                ),
            )
            locked_lock_file = assess_stage._file_record(authority, c5_path, c5_bytes)
            locked_stage_input = SimpleNamespace(
                assessor_vault_commit=locked_input_commit,
                assessor_vault_tree=locked_input_tree,
                assessor_truth={"stage": "locked"},
                bootstrap_indices=b"locked-bootstrap",
                development_authority={
                    "development_authorization_anchor_commit": "d" * 40
                },
            )
            locked_candidate_run = SimpleNamespace(
                raw_output={"stage": "locked"},
                candidate_execution_lock={"stage": "locked"},
                candidate_execution_lock_file=locked_lock_file,
            )
            resolved = assess_stage.ResolvedStage(
                head_commit=c5_commit,
                head_tree=c5_tree,
                input_commit=c4_commit,
                input_tree=c4_tree,
                input_file=assess_stage._file_record(authority, c4_path, c4_bytes),
                stage_input=locked_stage_input,
                candidate_run=locked_candidate_run,
                candidate_commit=locked_candidate_commit,
                candidate_tree=locked_candidate_tree,
                candidate_authority_file=assess_stage._file_record(
                    authority,
                    "candidate-run-authority.json",
                    locked_candidate_payload,
                ),
            )
            formal = SimpleNamespace(
                assessment={"stage": "locked"},
                assessment_jcs=b'{"stage":"locked"}',
                authority_jcs=b'{"stage":"locked"}',
            )
            assessor = SimpleNamespace(
                assess=mock.Mock(),
                build_development_decision_record=mock.Mock(),
                finalize_product_connection=mock.Mock(
                    return_value={
                        "schema_version": "geotarget.exp-local-003.final-connection/v1",
                        "product_connection_allowed": False,
                    }
                ),
            )
            with (
                mock.patch.object(
                    assess_stage, "_bootstrap_pinned_git", return_value=self.git
                ),
                mock.patch.object(assess_stage, "_verify_contract_sources_at_head"),
                mock.patch.object(assess_stage, "_pinned_git", return_value=self.git),
                mock.patch.object(
                    assess_stage, "_resolve_stage", return_value=resolved
                ),
                mock.patch.object(assess_stage, "_verify_frozen_environment"),
                mock.patch.object(
                    authority,
                    "resolve_development_authorization",
                    return_value=development,
                ),
                mock.patch.object(
                    authority, "assess_with_authority", return_value=formal
                ),
            ):
                anchor = assess_stage.run_stage(
                    "locked",
                    layout=layout,
                    authority_module=authority,
                    assessor_module=assessor,
                )
            self.assertEqual(anchor, layout.final_connection_anchor)
            assessor.finalize_product_connection.assert_called_once()
            anchor_document = json.loads(anchor.read_text("utf-8"))
            schema = json.loads(
                (SOURCE_ROOT / "final-connection-anchor.schema.json").read_text("utf-8")
            )
            Draft202012Validator(schema).validate(anchor_document)
            output_head, _output_tree = assess_stage._assert_clean_head(
                layout.locked_assessor_output, self.git
            )
            self.assertEqual(
                output_head,
                anchor_document["assessor_output"]["final_connection_commit"],
            )

    def test_full_typed_development_and_locked_one_shot_chains(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = authority_fixtures.Fixture(root / "fixture")
            development_input = authority.resolve_stage_input_authority(
                anchor_repository=fixture.main,
                anchor_commit=fixture.anchor_commit,
                anchor_path=fixture.anchor_path,
                anchor_sha256=assess_stage._sha256(fixture.anchor_bytes),
                candidate_publication_root=fixture.candidate,
                assessor_vault_repository=fixture.assessor,
                git_executable=self.git,
            )
            source_run, _commit, _tree, _file = authority_fixtures._build_run(
                root, fixture, development_input
            )
            authority_fixtures._git(fixture.main, "branch", "-M", "main")
            development_run = root / "development-candidate-run"
            _fixed_candidate_evidence(source_run, development_run, self.git)
            environment_lock = root / "environment-lock.json"
            environment_lock.write_bytes(
                authority.canonical_bytes(
                    {
                        "schema_version": "exp-local-003-environment-lock/v1",
                        "card_sha256": assess_stage.CARD_SHA256,
                        "tools": {
                            "git_executable": str(self.git.path),
                            "git_sha256": self.git.sha256,
                        },
                    }
                )
            )
            experiment = fixture.main / "research" / "experiments" / "EXP-LOCAL-003"
            development_output = root / "development-assessor-output"
            locked_output = root / "locked-assessor-output"
            layout = assess_stage.Layout(
                repository_root=fixture.main,
                experiment_root=experiment,
                environment_lock=environment_lock,
                development_input_vault=fixture.assessor,
                development_candidate_evidence=development_run,
                development_assessor_output=development_output,
                locked_input_vault=root / "locked-input-not-created-yet",
                locked_candidate_evidence=root / "locked-run-not-created-yet",
                locked_assessor_output=locked_output,
                development_anchor=(
                    experiment / "C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json"
                ),
                final_connection_anchor=(
                    experiment / "C6_FINAL_CONNECTION_ANCHOR.json"
                ),
            )
            assessor_module = SimpleNamespace(
                assess=_synthetic_assessment,
                build_development_decision_record=_synthetic_decision,
                finalize_product_connection=_synthetic_finalizer,
            )
            with (
                mock.patch.object(
                    assess_stage, "_verify_frozen_environment"
                ) as environment_verifier,
                mock.patch.object(assess_stage, "_verify_contract_sources_at_head"),
            ):
                development_anchor = assess_stage.run_stage(
                    "development",
                    layout=layout,
                    authority_module=authority,
                    assessor_module=assessor_module,
                )
            environment_verifier.assert_called_once_with()
            c3_commit, _c3_tree = assess_stage._commit_files(
                fixture.main,
                self.git,
                (development_anchor.relative_to(fixture.main).as_posix(),),
                "C3 development authorization",
            )
            development = authority.resolve_development_authorization(
                fixture.main,
                fixture.assessor,
                development_run,
                development_output,
                authorization_anchor_commit=c3_commit,
                assess=_synthetic_assessment,
                build_development_decision=_synthetic_decision,
                git_executable=self.git,
            )
            locked_fixture = authority_fixtures._build_locked_inputs(
                root, fixture, development
            )
            locked_input = authority.resolve_stage_input_authority(
                anchor_repository=fixture.main,
                anchor_commit=locked_fixture.anchor_commit,
                anchor_path=locked_fixture.anchor_path,
                anchor_sha256=assess_stage._sha256(locked_fixture.anchor_bytes),
                candidate_publication_root=locked_fixture.candidate,
                assessor_vault_repository=locked_fixture.assessor,
                git_executable=self.git,
            )
            locked_source_run, _commit, _tree, _file = authority_fixtures._build_run(
                root, locked_fixture, locked_input
            )
            locked_run = root / "locked-candidate-run"
            _fixed_candidate_evidence(locked_source_run, locked_run, self.git)
            locked_layout = assess_stage.Layout(
                repository_root=fixture.main,
                experiment_root=experiment,
                environment_lock=environment_lock,
                development_input_vault=fixture.assessor,
                development_candidate_evidence=development_run,
                development_assessor_output=development_output,
                locked_input_vault=locked_fixture.assessor,
                locked_candidate_evidence=locked_run,
                locked_assessor_output=locked_output,
                development_anchor=layout.development_anchor,
                final_connection_anchor=layout.final_connection_anchor,
            )
            with (
                mock.patch.object(
                    assess_stage, "_verify_frozen_environment"
                ) as environment_verifier,
                mock.patch.object(assess_stage, "_verify_contract_sources_at_head"),
            ):
                final_anchor = assess_stage.run_stage(
                    "locked",
                    layout=locked_layout,
                    authority_module=authority,
                    assessor_module=assessor_module,
                )
            environment_verifier.assert_called_once_with()
            c6_commit, _c6_tree = assess_stage._commit_files(
                fixture.main,
                self.git,
                (final_anchor.relative_to(fixture.main).as_posix(),),
                "C6 final connection",
            )
            locked_authorization = authority.resolve_locked_authorization(
                fixture.main,
                fixture.assessor,
                development_run,
                development_output,
                locked_fixture.assessor,
                locked_run,
                locked_output,
                authorization_anchor_commit=c6_commit,
                assess=_synthetic_assessment,
                build_development_decision=_synthetic_decision,
                finalize_product_connection=_synthetic_finalizer,
                git_executable=self.git,
            )
            self.assertFalse(locked_authorization.product_connection_allowed)

    def _run_with_fakes(
        self, stage: assess_stage.Stage, temporary_root: Path
    ) -> tuple[list[str], mock.Mock, mock.Mock, SimpleNamespace, MappingCapture]:
        layout = assess_stage.Layout.fixed(temporary_root / "solver")
        resolved = _resolved(stage)
        published = _published(
            (
                layout.development_assessor_output
                if stage == "development"
                else layout.locked_assessor_output
            ),
            stage,
        )
        formal = SimpleNamespace(
            assessment={"stage": stage},
            assessment_jcs=b"{}",
            authority_jcs=b"{}",
        )
        assessor = SimpleNamespace(
            assess=mock.Mock(name="assess"),
            build_development_decision_record=mock.Mock(
                name="build_development_decision_record",
                return_value={"schema_version": "decision/v1"},
            ),
            finalize_product_connection=mock.Mock(
                name="finalize_product_connection",
                return_value={"schema_version": "final/v1"},
            ),
        )
        development = SimpleNamespace(
            authorization_anchor_commit="d" * 40,
            authorization_anchor_tree="1" * 40,
            authorization_anchor_file=_record(
                "research/experiments/EXP-LOCAL-003/"
                "C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json",
                "development-anchor",
            ),
            stage_input=SimpleNamespace(
                assessor_vault_commit="2" * 40,
                assessor_truth={"stage": "development"},
                bootstrap_indices=b"development-bootstrap",
            ),
            candidate_run=SimpleNamespace(
                vault_commit="3" * 40,
                raw_output={"stage": "development"},
                candidate_execution_lock={"stage": "development"},
            ),
            assessor_output=SimpleNamespace(
                decision_commit="4" * 40,
                decision={"schema_version": "decision/v1"},
                formal=SimpleNamespace(assessment={"stage": "development"}),
            ),
        )
        timeline: list[str] = []
        authority_assess = mock.Mock(
            name="assess_with_authority",
            side_effect=lambda *_args, **_kwargs: (timeline.append("assess"), formal)[
                1
            ],
        )
        development_resolver = mock.Mock(
            name="resolve_development_authorization", return_value=development
        )

        def publish_side_effect(*_args: object, **kwargs: object) -> object:
            timeline.append("publish")
            build_child = kwargs["build_child"]
            assert callable(build_child)
            build_child("a" * 40)
            return published

        capture = MappingCapture()

        def fake_head(path: Path, _git: object) -> tuple[str, str]:
            if path == layout.development_input_vault:
                return development.stage_input.assessor_vault_commit, "a" * 40
            if path == layout.development_candidate_evidence:
                return development.candidate_run.vault_commit, "b" * 40
            if path == layout.development_assessor_output:
                return development.assessor_output.decision_commit, "c" * 40
            return "h" * 40, "t" * 40

        expected_output, expected_staging, _expected_anchor = (
            assess_stage._stage_output_paths(stage, layout)
        )
        claim_paths = (expected_output, expected_staging)

        def claim(*_args: object, **_kwargs: object) -> tuple[Path, Path]:
            timeline.append("claim")
            return claim_paths

        def verify_environment() -> None:
            timeline.append("environment")

        with (
            mock.patch.object(
                assess_stage, "_bootstrap_pinned_git", return_value=self.git
            ),
            mock.patch.object(assess_stage, "_verify_contract_sources_at_head"),
            mock.patch.object(assess_stage, "_pinned_git", return_value=self.git),
            mock.patch.object(
                assess_stage, "_assert_clean_head", side_effect=fake_head
            ),
            mock.patch.object(assess_stage, "_resolve_stage", return_value=resolved),
            mock.patch.object(assess_stage, "_claim_output", side_effect=claim),
            mock.patch.object(assess_stage, "_initialize_output_repository"),
            mock.patch.object(assess_stage, "_verify_repository_storage"),
            mock.patch.object(assess_stage, "_verify_main_branch"),
            mock.patch.object(
                assess_stage,
                "_verify_frozen_environment",
                side_effect=verify_environment,
            ),
            mock.patch.object(assess_stage, "_reverify_bound_heads"),
            mock.patch.object(assess_stage, "_verify_uncommitted_anchor"),
            mock.patch.object(
                assess_stage, "_publish_output", side_effect=publish_side_effect
            ),
            mock.patch.object(assess_stage, "_write_anchor", side_effect=capture.write),
            mock.patch.object(authority, "assess_with_authority", authority_assess),
            mock.patch.object(
                authority,
                "resolve_development_authorization",
                development_resolver,
            ),
        ):
            assess_stage.run_stage(
                stage,
                layout=layout,
                authority_module=authority,
                assessor_module=assessor,
            )
        return timeline, authority_assess, development_resolver, assessor, capture

    def test_development_runs_assessor_once_after_claim_and_writes_closed_c3(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            timeline, authority_assess, development_resolver, assessor, capture = (
                self._run_with_fakes("development", Path(temporary))
            )
            self.assertEqual(timeline, ["claim", "environment", "assess", "publish"])
            authority_assess.assert_called_once()
            development_resolver.assert_not_called()
            assessor.build_development_decision_record.assert_called_once()
            assessor.finalize_product_connection.assert_not_called()
            self.assertEqual(len(capture.documents), 1)
            path, document = capture.documents[0]
            self.assertEqual(path.name, "C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json")
            schema = json.loads(
                (
                    SOURCE_ROOT / "development-authorization-anchor.schema.json"
                ).read_text("utf-8")
            )
            Draft202012Validator(schema).validate(document)

    def test_locked_reresolves_development_then_finalizes_and_writes_closed_c6(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            timeline, authority_assess, development_resolver, assessor, capture = (
                self._run_with_fakes("locked", Path(temporary))
            )
            self.assertEqual(timeline, ["claim", "environment", "assess", "publish"])
            development_resolver.assert_called_once()
            authority_assess.assert_called_once()
            assessor.finalize_product_connection.assert_called_once()
            self.assertEqual(len(capture.documents), 1)
            path, document = capture.documents[0]
            self.assertEqual(path.name, "C6_FINAL_CONNECTION_ANCHOR.json")
            schema = json.loads(
                (SOURCE_ROOT / "final-connection-anchor.schema.json").read_text("utf-8")
            )
            Draft202012Validator(schema).validate(document)


class MappingCapture:
    def __init__(self) -> None:
        self.documents: list[tuple[Path, dict[str, object]]] = []

    def write(
        self, path: Path, document: dict[str, object], _authority: object
    ) -> None:
        self.documents.append((path, document))


if __name__ == "__main__":
    unittest.main()
