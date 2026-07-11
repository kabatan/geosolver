"""Synthetic immutable-Git tests for the EXP-LOCAL-003 authority boundary."""

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

from jsonschema import Draft202012Validator

import authority


CARD = authority.CARD_SHA256
SOURCE = Path(__file__).resolve().parent


def _jcs(value: Any) -> bytes:
    return authority.canonical_bytes(value)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _record(path: str, payload: bytes) -> dict[str, Any]:
    return {"path": path, "sha256": _sha(payload), "byte_length": len(payload)}


def _artifact(path: str, raw: bytes, compressed: bytes) -> dict[str, Any]:
    return {
        "path": PurePath(path).name,
        "jcs_sha256": _sha(raw),
        "gzip_sha256": _sha(compressed),
        "jcs_bytes": len(raw),
        "gzip_bytes": len(compressed),
        "compression": "gzip-level-9-mtime-0",
    }


class PurePath:
    """Tiny POSIX basename helper that is independent of the host separator."""

    def __init__(self, value: str) -> None:
        self.name = value.rsplit("/", 1)[-1]


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / Path(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _git(root: Path, *args: str, input_bytes: bytes | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        input=input_bytes,
        capture_output=True,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr.decode("utf-8", "replace"))
    return completed.stdout.decode("ascii", "strict").strip()


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Authority Test")
    _git(root, "config", "user.email", "authority@example.invalid")


def _commit(root: Path, message: str) -> tuple[str, str]:
    _git(root, "add", "--all")
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
        }
    )
    completed = subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=root,
        check=False,
        capture_output=True,
        env=environment,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr.decode("utf-8", "replace"))
    return _git(root, "rev-parse", "HEAD"), _git(root, "rev-parse", "HEAD^{tree}")


def _commit_tree_object(root: Path, tree: str, message: str, *parents: str) -> str:
    arguments = ["commit-tree", tree]
    for parent in parents:
        arguments.extend(("-p", parent))
    return _git(root, *arguments, input_bytes=f"{message}\n".encode())


def _accounting() -> dict[str, Any]:
    return {
        "parent_process_cpu_nanoseconds_decimal": "11",
        "validation_child_cpu_nanoseconds_decimal": "5",
        "julia_capture_cpu_nanoseconds_decimal": "7",
        "total_process_cpu_nanoseconds_decimal": "23",
        "monotonic_elapsed_nanoseconds_decimal": "30",
        "epoch_started_nanoseconds_decimal": "100",
        "epoch_ended_nanoseconds_decimal": "130",
        "host_exclusion_observed": False,
        "primary_oracle_work_included": False,
        "count_in_end_to_end_exactly_once": True,
    }


class Fixture:
    def __init__(
        self,
        root: Path,
        stage: str = "development",
        *,
        assessor_extra: bool = False,
        c1_extra_mechanism: bool = False,
    ) -> None:
        self.root = root
        self.stage = stage
        self.main = root / "main"
        self.assessor = root / "assessor"
        _init_repo(self.main)
        _init_repo(self.assessor)
        self.candidate = (
            self.main
            / "research"
            / "experiments"
            / "EXP-LOCAL-003"
            / f"{stage}-candidate-inputs"
        )
        self.julia_runtime_root = root / "julia-runtime"
        self.julia_executable = self.julia_runtime_root / "bin" / "julia.exe"
        self.julia_executable.parent.mkdir(parents=True)
        self.julia_executable.write_bytes(b"synthetic pinned Julia runtime")
        self.julia_depot_root = root / "julia-depot"
        for name in ("packages", "artifacts"):
            (self.julia_depot_root / name).mkdir(parents=True)
        locked_julia_environment = {
            "SystemRoot": r"C:\Windows",
            "WINDIR": r"C:\Windows",
            "PATH": os.pathsep.join(
                (str(self.julia_executable.parent), r"C:\Windows\System32")
            ),
            "JULIA_LOAD_PATH": os.pathsep.join(("@", "@stdlib")),
            "JULIA_NUM_THREADS": "1",
            "JULIA_CPU_TARGET": "generic",
            "JULIA_PKG_OFFLINE": "true",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        self.environment_lock = {
            "schema_version": "exp-local-003-environment-lock/v1",
            "card_sha256": CARD,
            "julia": {
                "runtime_executable": str(self.julia_executable),
                "runtime_sha256": _sha(self.julia_executable.read_bytes()),
                "runtime_tree": {"root": str(self.julia_runtime_root)},
                "depot_tree": {"root": str(self.julia_depot_root)},
            },
            "execution": {
                "julia_depot_path": str(self.julia_depot_root),
                "julia_environment": locked_julia_environment,
                "python": {
                    "host_environment": {
                        "SystemRoot": r"C:\Windows",
                        "WINDIR": r"C:\Windows",
                    }
                },
            },
        }
        self.environment_lock_bytes = _jcs(self.environment_lock)
        _write(self.main, "C0_SOURCE", b"frozen C0\n")
        c0_paths = {
            *authority.C0_EQUIVALENCE_PROTOCOL_PATHS,
            "research/experiments/EXP-LOCAL-003/source/launch_candidate.py",
            "research/experiments/EXP-LOCAL-003/source/candidate_observer.py",
            "julia/Project.toml",
            "julia/Manifest.toml",
            "julia/GeoTargetBase/Project.toml",
            "julia/GeoTargetBase/src/GeoTargetBase.jl",
            "julia/GeoTargetCore/Project.toml",
            "julia/GeoTargetCore/src/GeoTargetCore.jl",
            "julia/GeoTargetGeometry/Project.toml",
            "julia/GeoTargetGeometry/src/GeoTargetGeometry.jl",
            authority.ENVIRONMENT_LOCK_PATH,
        }
        c0_payloads = {
            path: f"# synthetic immutable C0: {path}\n".encode()
            for path in sorted(c0_paths)
        }
        c0_payloads[authority.ENVIRONMENT_LOCK_PATH] = self.environment_lock_bytes
        for path, payload in c0_payloads.items():
            _write(self.main, path, payload)
        c0_commit, c0_tree = _commit(self.main, "C0 source")
        self.c0_commit = c0_commit
        self.c0_tree = c0_tree
        lock = _jcs(
            {
                "schema_version": "exp-local-003-preimplementation-lock/v1",
                "experiment_id": "EXP-LOCAL-003",
                "status": "frozen-before-one-shot-development-materialization",
                "card_sha256": CARD,
                "c0_source_commit": c0_commit,
                "c0_source_tree": c0_tree,
                "files": {path: _sha(payload) for path, payload in c0_payloads.items()},
                "experiment_source_files": sorted(
                    path
                    for path in c0_payloads
                    if path.startswith("research/experiments/EXP-LOCAL-003/source/")
                ),
                "forbidden_mechanism_paths": list(
                    authority.EXPECTED_FORBIDDEN_MECHANISM_PATHS
                ),
                "environment_lock_sha256": _sha(self.environment_lock_bytes),
                "local_options_sha256": "1" * 64,
            }
        )
        self.lock_sha = _sha(lock)
        _write(
            self.main,
            "research/experiments/EXP-LOCAL-003/preimplementation-lock.json",
            lock,
        )
        self.source_commit, _ = _commit(self.main, "source lock")
        synthetic_development_anchor = _jcs(
            {
                "schema_version": authority.DEVELOPMENT_AUTHORIZATION_SCHEMA,
                "experiment_id": "EXP-LOCAL-003",
                "card_sha256": CARD,
                "stage": "development",
                "synthetic_fixture": True,
            }
        )
        development_anchor_commit = "f" * 40
        if stage == "locked":
            _write(
                self.main,
                "research/experiments/EXP-LOCAL-003/"
                "C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json",
                synthetic_development_anchor,
            )
            development_anchor_commit, _ = _commit(
                self.main, "synthetic development authorization"
            )
        development_authority = {
            "development_authorization_anchor_commit": development_anchor_commit,
            "development_authorization_anchor_sha256": _sha(
                synthetic_development_anchor
            ),
            "development_stage_input_anchor_sha256": "8" * 64,
            "development_candidate_run_authority_sha256": "9" * 64,
            "development_assessor_stage_authority_sha256": "a" * 64,
            "development_assessment_commit": "b" * 40,
            "development_assessment_sha256": "c" * 64,
            "development_decision_commit": "d" * 40,
            "development_decision_record_sha256": "e" * 64,
            "selected_variant": "LX-BOUNDS",
            "selected_path": "recall",
        }

        candidate_input = _jcs(
            {
                "schema_version": (
                    "exp-local-003-candidate-inputs/v1"
                    if stage == "development"
                    else "exp-local-003-locked-candidate-inputs/v1"
                ),
                "card_sha256": CARD,
                "cases": [],
            }
        )
        candidate_gzip = authority.deterministic_gzip(candidate_input)
        input_name = f"{stage}-candidate-inputs.json.gz"
        plugin = b"module Local3FixturePlugin\nend\n"
        _write(self.candidate, input_name, candidate_gzip)
        _write(self.candidate, "plugin/Local3FixturePlugin.jl", plugin)
        selection_record: dict[str, Any] | None = None
        if stage == "locked":
            selection = _jcs(
                {
                    "schema_version": "geotarget.exp-local-003.locked-selection/v1",
                    "experiment_id": "EXP-LOCAL-003",
                    "card_sha256": CARD,
                    "stage": "locked",
                    "selected_variant": "LX-BOUNDS",
                    "candidate_input_sha256": _sha(candidate_input),
                }
            )
            _write(self.candidate, "locked-selection.json", selection)
            selection_record = {
                "path": "locked-selection.json",
                "sha256": _sha(selection),
                "bytes": len(selection),
            }
        candidate_manifest = {
            "schema_version": "exp-local-003-candidate-manifest/v1",
            "experiment_id": "EXP-LOCAL-003",
            "partition": stage,
            "case_count": 64 if stage == "development" else 96,
            "starts_per_case": 32,
            "calibration_points_per_case": 64,
            "card_sha256": CARD,
            "preimplementation_lock_sha256": self.lock_sha,
            "candidate_input_sha256": _sha(candidate_input),
            "artifact": _artifact(input_name, candidate_input, candidate_gzip),
            "fixture_plugin_artifact": {
                "path": "plugin/Local3FixturePlugin.jl",
                "sha256": _sha(plugin),
                "bytes": len(plugin),
            },
            "locked_selection_artifact": selection_record,
            "visible_tree": "candidate-only",
        }
        candidate_manifest_bytes = _jcs(candidate_manifest)
        _write(self.candidate, "manifest.json", candidate_manifest_bytes)
        candidate_completion = _jcs(
            {
                "schema_version": "exp-local-003-candidate-one-shot-completion/v1",
                "partition": stage,
                "candidate_manifest_sha256": _sha(candidate_manifest_bytes),
                "source_lock_commit": self.source_commit,
                "rerun_permitted": False,
                "contains_assessor_digest": False,
            }
        )
        _write(self.candidate, "ONE_SHOT_COMPLETE.json", candidate_completion)

        bootstrap = b"synthetic-bootstrap-" + stage.encode()
        truth = _jcs(
            {
                "schema_version": "geotarget.exp-local-003.assessor-truth/v1",
                "stage": stage,
                "candidate_input_sha256": _sha(candidate_input),
                "bootstrap_sha256": _sha(bootstrap),
                "local_options_sha256": "1" * 64,
                "locked_decision": (
                    None
                    if stage == "development"
                    else {
                        "candidate_id": development_authority["selected_variant"],
                        "development_path": development_authority["selected_path"],
                        "development_assessment_sha256": development_authority[
                            "development_assessment_sha256"
                        ],
                        "development_decision_record_sha256": development_authority[
                            "development_decision_record_sha256"
                        ],
                    }
                ),
                "cases": [],
            }
        )
        truth_gzip = authority.deterministic_gzip(truth)
        truth_name = f"{stage}-assessor-truth.json.gz"
        bootstrap_name = f"{stage}-bootstrap-indices.bin"
        _write(self.assessor, f"assessor/{truth_name}", truth_gzip)
        _write(self.assessor, f"assessor/{bootstrap_name}", bootstrap)
        nested = {
            "schema_version": "exp-local-003-assessor-manifest/v1",
            "experiment_id": "EXP-LOCAL-003",
            "partition": stage,
            "primary_case_count": 48 if stage == "development" else 96,
            "safety_case_count": 16 if stage == "development" else 0,
            "card_sha256": CARD,
            "preimplementation_lock_sha256": self.lock_sha,
            "truth_artifact": _artifact(truth_name, truth, truth_gzip),
            "bootstrap_artifact": {
                "path": bootstrap_name,
                "sha256": _sha(bootstrap),
                "bytes": len(bootstrap),
                "format": f"GTLOCAL3BOOT1-{stage}",
            },
            "visible_tree": "assessor-only-after-candidate-seal",
        }
        nested_bytes = _jcs(nested)
        _write(self.assessor, "assessor/manifest.json", nested_bytes)
        root_manifest = {
            "schema_version": "exp-local-003-assessor-vault-manifest/v1",
            "experiment_id": "EXP-LOCAL-003",
            "partition": stage,
            "card_sha256": CARD,
            "preimplementation_lock_sha256": self.lock_sha,
            "source_lock_commit": self.source_commit,
            "candidate_manifest_sha256": _sha(candidate_manifest_bytes),
            "assessor_manifest_sha256": _sha(nested_bytes),
            "c1_materialization_times": _accounting(),
            "candidate_process_argument": str(self.candidate),
            "candidate_repository_contains_vault": False,
            "assessor_open_order": "after sealed candidate raw output and process exit",
            "rerun_permitted": False,
            "locked_inputs_materialized": stage == "locked",
            "locked_authority": (
                None
                if stage == "development"
                else {
                    "development_assessment_sha256": development_authority[
                        "development_assessment_sha256"
                    ],
                    "development_decision_record_sha256": development_authority[
                        "development_decision_record_sha256"
                    ],
                    "decision_commit": development_authority[
                        "development_assessment_commit"
                    ],
                    "selected_variant": development_authority["selected_variant"],
                    "selected_path": development_authority["selected_path"],
                    "locked_selection_sha256": selection_record["sha256"],
                }
            ),
        }
        root_bytes = _jcs(root_manifest)
        _write(self.assessor, "manifest.json", root_bytes)
        completion = _jcs(
            {
                "schema_version": "exp-local-003-assessor-vault-one-shot-completion/v1",
                "partition": stage,
                "manifest_sha256": _sha(root_bytes),
                "source_lock_commit": self.source_commit,
                "rerun_permitted": False,
            }
        )
        _write(self.assessor, "ONE_SHOT_COMPLETE.json", completion)
        if assessor_extra:
            _write(self.assessor, "unexpected.txt", b"forbidden")
        self.assessor_commit, self.assessor_tree = _commit(
            self.assessor, "assessor inputs"
        )

        candidate_payloads = {
            path.relative_to(self.candidate).as_posix(): path.read_bytes()
            for path in self.candidate.rglob("*")
            if path.is_file()
        }
        candidate_tree = dict(authority._publication_tree(candidate_payloads))
        attempt = _jcs(
            {
                "schema_version": (
                    "exp-local-003-c1-attempt-claim/v1"
                    if stage == "development"
                    else "exp-local-003-locked-attempt-claim/v1"
                ),
                "card_sha256": CARD,
                "attempt_ordinal": 0,
                "rerun_permitted": False,
                "failure_is_terminal": True,
                "authority_validation_occurs_after_claim": True,
            }
        )
        private_anchor = _jcs(
            {
                "schema_version": "synthetic-private-audit-anchor/v1",
                "card_sha256": CARD,
                "private_visible_to_formal_assessor": False,
            }
        )
        experiment_prefix = "research/experiments/EXP-LOCAL-003"
        attempt_name = (
            "C1_ATTEMPT_CLAIM.json"
            if stage == "development"
            else "LOCKED_ATTEMPT_CLAIM.json"
        )
        private_name = (
            "C1_PRIVATE_AUDIT_ANCHOR.json"
            if stage == "development"
            else "C4_LOCKED_PRIVATE_AUDIT_ANCHOR.json"
        )
        stage_anchor_name = (
            "C1_STAGE_VAULT_ANCHOR.json"
            if stage == "development"
            else "C4_LOCKED_STAGE_VAULT_ANCHOR.json"
        )
        _write(self.main, f"{experiment_prefix}/{attempt_name}", attempt)
        _write(
            self.main,
            f"{experiment_prefix}/{private_name}",
            private_anchor,
        )
        if c1_extra_mechanism:
            _write(
                self.main,
                authority.RUNNER_SOURCE_PATH,
                b"forbidden mechanism introduced during C1\n",
            )
        anchor = {
            "schema_version": authority.ANCHOR_SCHEMA,
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD,
            "stage": stage,
            "source_lock_commit": self.source_commit,
            "preimplementation_lock_sha256": self.lock_sha,
            "materialization_attempt_claim_sha256": _sha(attempt),
            "assessor_vault_git_commit": self.assessor_commit,
            "assessor_vault_git_tree": self.assessor_tree,
            "assessor_vault_manifest_sha256": _sha(root_bytes),
            "assessor_vault_completion_sha256": _sha(completion),
            "assessor_manifest_sha256": _sha(nested_bytes),
            "candidate_manifest_sha256": _sha(candidate_manifest_bytes),
            "candidate_completion_sha256": _sha(candidate_completion),
            "candidate_publication_tree": candidate_tree,
            "c1_phase_accounting": _accounting(),
            "candidate_visible": False,
            "rerun_permitted": False,
        }
        if stage == "locked":
            anchor["development_authority"] = development_authority
        self.anchor_bytes = _jcs(anchor)
        self.anchor_path = f"{experiment_prefix}/{stage_anchor_name}"
        _write(self.main, self.anchor_path, self.anchor_bytes)
        self.anchor_commit, self.anchor_tree = _commit(self.main, "stage input anchor")
        self.candidate_input_sha = _sha(candidate_input)


def _build_locked_inputs(
    root: Path,
    fixture: Fixture,
    development: authority.DevelopmentAuthorization,
) -> SimpleNamespace:
    main = fixture.main
    candidate = (
        main / "research" / "experiments" / "EXP-LOCAL-003" / "locked-candidate-inputs"
    )
    assessor = root / "locked-assessor-input"
    _init_repo(assessor)
    development_decision = development.assessor_output.decision
    development_decision_file = development.assessor_output.decision_file
    if development_decision is None or development_decision_file is None:
        raise AssertionError("development decision is unavailable")
    development_authority = {
        "development_authorization_anchor_commit": (
            development.authorization_anchor_commit
        ),
        "development_authorization_anchor_sha256": (
            development.authorization_anchor_file.sha256
        ),
        "development_stage_input_anchor_sha256": (
            development.stage_input.anchor_file.sha256
        ),
        "development_candidate_run_authority_sha256": (
            development.candidate_run.authority_file.sha256
        ),
        "development_assessor_stage_authority_sha256": (
            development.assessor_output.authority_file.sha256
        ),
        "development_assessment_commit": (
            development.assessor_output.assessment_commit
        ),
        "development_assessment_sha256": (
            development.assessor_output.assessment_file.sha256
        ),
        "development_decision_commit": development.assessor_output.decision_commit,
        "development_decision_record_sha256": development_decision_file.sha256,
        "selected_variant": development_decision["selected_variant"],
        "selected_path": development_decision["selected_path"],
    }
    candidate_input = _jcs(
        {
            "schema_version": "exp-local-003-locked-candidate-inputs/v1",
            "card_sha256": CARD,
            "cases": [],
        }
    )
    candidate_gzip = authority.deterministic_gzip(candidate_input)
    input_name = "locked-candidate-inputs.json.gz"
    plugin = b"module Local3FixturePlugin\nend\n"
    selection = _jcs(
        {
            "schema_version": "geotarget.exp-local-003.locked-selection/v1",
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD,
            "stage": "locked",
            "selected_variant": development_authority["selected_variant"],
            "candidate_input_sha256": _sha(candidate_input),
        }
    )
    _write(candidate, input_name, candidate_gzip)
    _write(candidate, "plugin/Local3FixturePlugin.jl", plugin)
    _write(candidate, "locked-selection.json", selection)
    selection_record = {
        "path": "locked-selection.json",
        "sha256": _sha(selection),
        "bytes": len(selection),
    }
    candidate_manifest = {
        "schema_version": "exp-local-003-candidate-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": "locked",
        "case_count": 96,
        "starts_per_case": 32,
        "calibration_points_per_case": 64,
        "card_sha256": CARD,
        "preimplementation_lock_sha256": fixture.lock_sha,
        "candidate_input_sha256": _sha(candidate_input),
        "artifact": _artifact(input_name, candidate_input, candidate_gzip),
        "fixture_plugin_artifact": {
            "path": "plugin/Local3FixturePlugin.jl",
            "sha256": _sha(plugin),
            "bytes": len(plugin),
        },
        "locked_selection_artifact": selection_record,
        "visible_tree": "candidate-only",
    }
    candidate_manifest_bytes = _jcs(candidate_manifest)
    _write(candidate, "manifest.json", candidate_manifest_bytes)
    candidate_completion = _jcs(
        {
            "schema_version": "exp-local-003-candidate-one-shot-completion/v1",
            "partition": "locked",
            "candidate_manifest_sha256": _sha(candidate_manifest_bytes),
            "source_lock_commit": fixture.source_commit,
            "rerun_permitted": False,
            "contains_assessor_digest": False,
        }
    )
    _write(candidate, "ONE_SHOT_COMPLETE.json", candidate_completion)

    bootstrap = b"synthetic-bootstrap-locked"
    truth = _jcs(
        {
            "schema_version": "geotarget.exp-local-003.assessor-truth/v1",
            "stage": "locked",
            "candidate_input_sha256": _sha(candidate_input),
            "bootstrap_sha256": _sha(bootstrap),
            "local_options_sha256": "1" * 64,
            "locked_decision": {
                "candidate_id": development_authority["selected_variant"],
                "development_path": development_authority["selected_path"],
                "development_assessment_sha256": development_authority[
                    "development_assessment_sha256"
                ],
                "development_decision_record_sha256": development_authority[
                    "development_decision_record_sha256"
                ],
            },
            "cases": [],
        }
    )
    truth_gzip = authority.deterministic_gzip(truth)
    truth_name = "locked-assessor-truth.json.gz"
    bootstrap_name = "locked-bootstrap-indices.bin"
    _write(assessor, f"assessor/{truth_name}", truth_gzip)
    _write(assessor, f"assessor/{bootstrap_name}", bootstrap)
    assessor_manifest = {
        "schema_version": "exp-local-003-assessor-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": "locked",
        "primary_case_count": 96,
        "safety_case_count": 0,
        "card_sha256": CARD,
        "preimplementation_lock_sha256": fixture.lock_sha,
        "truth_artifact": _artifact(truth_name, truth, truth_gzip),
        "bootstrap_artifact": {
            "path": bootstrap_name,
            "sha256": _sha(bootstrap),
            "bytes": len(bootstrap),
            "format": "GTLOCAL3BOOT1-locked",
        },
        "visible_tree": "assessor-only-after-candidate-seal",
    }
    assessor_manifest_bytes = _jcs(assessor_manifest)
    _write(assessor, "assessor/manifest.json", assessor_manifest_bytes)
    root_manifest = {
        "schema_version": "exp-local-003-assessor-vault-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": "locked",
        "card_sha256": CARD,
        "preimplementation_lock_sha256": fixture.lock_sha,
        "source_lock_commit": fixture.source_commit,
        "candidate_manifest_sha256": _sha(candidate_manifest_bytes),
        "assessor_manifest_sha256": _sha(assessor_manifest_bytes),
        "c1_materialization_times": _accounting(),
        "candidate_process_argument": str(candidate),
        "candidate_repository_contains_vault": False,
        "assessor_open_order": "after sealed candidate raw output and process exit",
        "rerun_permitted": False,
        "locked_inputs_materialized": True,
        "locked_authority": {
            "development_assessment_sha256": development_authority[
                "development_assessment_sha256"
            ],
            "development_decision_record_sha256": development_authority[
                "development_decision_record_sha256"
            ],
            "decision_commit": development_authority["development_assessment_commit"],
            "selected_variant": development_authority["selected_variant"],
            "selected_path": development_authority["selected_path"],
            "locked_selection_sha256": _sha(selection),
        },
    }
    root_manifest_bytes = _jcs(root_manifest)
    _write(assessor, "manifest.json", root_manifest_bytes)
    completion = _jcs(
        {
            "schema_version": "exp-local-003-assessor-vault-one-shot-completion/v1",
            "partition": "locked",
            "manifest_sha256": _sha(root_manifest_bytes),
            "source_lock_commit": fixture.source_commit,
            "rerun_permitted": False,
        }
    )
    _write(assessor, "ONE_SHOT_COMPLETE.json", completion)
    assessor_commit, assessor_tree = _commit(assessor, "locked assessor inputs")

    candidate_payloads = {
        path.relative_to(candidate).as_posix(): path.read_bytes()
        for path in candidate.rglob("*")
        if path.is_file()
    }
    attempt = _jcs(
        {
            "schema_version": "exp-local-003-locked-attempt-claim/v1",
            "card_sha256": CARD,
            "attempt_ordinal": 0,
            "rerun_permitted": False,
            "failure_is_terminal": True,
            "authority_validation_occurs_after_claim": True,
        }
    )
    private_anchor = _jcs(
        {
            "schema_version": "synthetic-locked-private-audit-anchor/v1",
            "card_sha256": CARD,
            "private_visible_to_formal_assessor": False,
        }
    )
    prefix = "research/experiments/EXP-LOCAL-003"
    _write(main, f"{prefix}/LOCKED_ATTEMPT_CLAIM.json", attempt)
    _write(main, f"{prefix}/C4_LOCKED_PRIVATE_AUDIT_ANCHOR.json", private_anchor)
    anchor = {
        "schema_version": authority.ANCHOR_SCHEMA,
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": CARD,
        "stage": "locked",
        "source_lock_commit": fixture.source_commit,
        "preimplementation_lock_sha256": fixture.lock_sha,
        "materialization_attempt_claim_sha256": _sha(attempt),
        "assessor_vault_git_commit": assessor_commit,
        "assessor_vault_git_tree": assessor_tree,
        "assessor_vault_manifest_sha256": _sha(root_manifest_bytes),
        "assessor_vault_completion_sha256": _sha(completion),
        "assessor_manifest_sha256": _sha(assessor_manifest_bytes),
        "candidate_manifest_sha256": _sha(candidate_manifest_bytes),
        "candidate_completion_sha256": _sha(candidate_completion),
        "candidate_publication_tree": dict(
            authority._publication_tree(candidate_payloads)
        ),
        "c1_phase_accounting": _accounting(),
        "development_authority": development_authority,
        "candidate_visible": False,
        "rerun_permitted": False,
    }
    anchor_bytes = _jcs(anchor)
    anchor_path = f"{prefix}/C4_LOCKED_STAGE_VAULT_ANCHOR.json"
    _write(main, anchor_path, anchor_bytes)
    anchor_commit, anchor_tree = _commit(main, "C4 locked inputs")
    return SimpleNamespace(
        stage="locked",
        main=main,
        candidate=candidate,
        assessor=assessor,
        anchor_bytes=anchor_bytes,
        anchor_path=anchor_path,
        anchor_commit=anchor_commit,
        anchor_tree=anchor_tree,
        candidate_input_sha=_sha(candidate_input),
        c0_commit=fixture.c0_commit,
        c0_tree=fixture.c0_tree,
        environment_lock_bytes=fixture.environment_lock_bytes,
        julia_executable=fixture.julia_executable,
        julia_runtime_root=fixture.julia_runtime_root,
        julia_depot_root=fixture.julia_depot_root,
    )


def _build_run(
    root: Path,
    fixture: Fixture,
    stage_input: authority.StageInputRecord,
    *,
    bad_ack: bool = False,
    forged_observer: bool = False,
    legacy_anchor_fields: bool = False,
    legacy_execution_source_field: bool = False,
    bad_launcher_claim: bool = False,
    bad_candidate_denied_probe_manifest: bool = False,
    bad_c2_denied_probe_accounting: bool = False,
    extra_candidate_gold_grant: bool = False,
    candidate_command_drift: bool = False,
    candidate_environment_drift: bool = False,
    bad_c2_external_probe: bool = False,
    c2_extra_gold_grant: bool = False,
    c2_command_drift: bool = False,
    c2_environment_drift: bool = False,
    c2_test_command_drift: bool = False,
    c2_test_grant_drift: bool = False,
    c2_test_probe_drift: bool = False,
    c2_test_manifest_drift: bool = False,
) -> tuple[Path, str, str, authority.FileRecord]:
    source_payloads = {
        path: f"# frozen synthetic C2 source: {path}\n".encode()
        for path in authority.C2_REQUIRED_SOURCE_PATHS
    }
    for path, payload in source_payloads.items():
        _write(fixture.main, path, payload)
    if fixture.stage == "development":
        test_payloads = {
            path: f"# frozen synthetic C2 test: {path}\n".encode()
            for path in authority.C2_TEST_SOURCE_PATHS
        }
        for path, payload in test_payloads.items():
            _write(fixture.main, path, payload)
        runtime_records = [
            {
                "path": path,
                "sha256": _sha(payload),
                "byte_length": len(payload),
            }
            for path, payload in sorted(source_payloads.items())
        ]
        test_records = [
            {
                "path": path,
                "sha256": _sha(payload),
                "byte_length": len(payload),
            }
            for path, payload in sorted(test_payloads.items())
        ]

        def c0_records(paths: tuple[str, ...]) -> list[dict[str, Any]]:
            return [
                _record(path, (fixture.main / Path(*path.split("/"))).read_bytes())
                for path in sorted(paths)
            ]

        fixture_records = c0_records(authority.C0_EQUIVALENCE_FIXTURE_PATHS)
        golden_records = c0_records(authority.C0_EQUIVALENCE_GOLDEN_PATHS)
        protocol_records = c0_records(authority.C0_EQUIVALENCE_PROTOCOL_PATHS)
        c0_index = {
            path: identity
            for path, identity in authority.GitObjectRepository(
                fixture.main,
                authority.pin_git_executable(
                    Path(shutil.which("git") or ""),
                    _sha(Path(shutil.which("git") or "").read_bytes()),
                ),
            )
            .tree_index(fixture.c0_commit)
            .items()
        }
        fixed_capsule = {
            "julia/Project.toml",
            "julia/Manifest.toml",
            authority.C0_EQUIVALENCE_CHILD_PATH,
            authority.C0_EQUIVALENCE_PROTOCOL_PATHS[0],
            *authority.C0_EQUIVALENCE_FIXTURE_PATHS,
        }
        package_roots = (
            "julia/GeoTargetBase",
            "julia/GeoTargetCore",
            "julia/GeoTargetGeometry",
        )
        capsule_paths = tuple(
            sorted(
                path
                for path, (mode, _oid) in c0_index.items()
                if mode == "100644"
                and (
                    path in fixed_capsule
                    or any(
                        path == f"{package}/Project.toml"
                        or path.startswith(f"{package}/src/")
                        for package in package_roots
                    )
                )
            )
        )
        capsule_records = c0_records(capsule_paths)
        claim_reference = f"sha256:{'f' * 64}"

        def execution_record(
            mode: str, golden: dict[str, Any], ordinal: int
        ) -> dict[str, Any]:
            mechanism = mode == "mechanism-disabled"
            fixture_index = (ordinal - 1) // 2
            workspace = root / "c2-equivalence-workspace"
            capsule_root = workspace / "immutable-c0-baseline-capsule"
            scratch = workspace / f"scratch-{fixture_index}-{mode}"
            fixture_relative = fixture_records[(ordinal - 1) // 2]["path"]
            command = [
                str(fixture.julia_executable),
                "--startup-file=no",
                "--history-file=no",
                "--compiled-modules=no",
                "--pkgimages=no",
                f"--project={capsule_root / 'julia'}",
                str(
                    capsule_root.joinpath(
                        *authority.C0_EQUIVALENCE_CHILD_PATH.split("/")
                    )
                ),
                mode,
                str(capsule_root.joinpath(*fixture_relative.split("/"))),
                str(
                    capsule_root.joinpath(
                        *authority.C0_EQUIVALENCE_PROTOCOL_PATHS[0].split("/")
                    )
                ),
            ]
            if mechanism:
                command.append(
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C2_REQUIRED_SOURCE_PATHS[0].split("/")
                        )
                    )
                )
            if c2_command_drift and ordinal == 1:
                command[2] = "--history-file=yes"
            locked_environment = fixture.environment_lock["execution"][
                "julia_environment"
            ]
            request_environment = {
                key: locked_environment[key]
                for key in (
                    "SystemRoot",
                    "WINDIR",
                    "PATH",
                    "JULIA_LOAD_PATH",
                    "JULIA_NUM_THREADS",
                    "JULIA_CPU_TARGET",
                    "JULIA_PKG_OFFLINE",
                    "OPENBLAS_NUM_THREADS",
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                )
            }
            request_environment.update(
                {
                    "JULIA_DEPOT_PATH": str(fixture.julia_depot_root),
                    "JULIA_PKG_PRECOMPILE_AUTO": "0",
                    "JULIA_PROJECT": str(capsule_root / "julia"),
                }
            )
            environment_by_folded_name = {
                name.casefold(): (name, value)
                for name, value in request_environment.items()
            }
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            for name, value in {
                "COMSPEC": str(Path(system_root) / "System32" / "cmd.exe"),
                "PATH": str(Path(system_root) / "System32"),
                "PATHEXT": ".COM;.EXE;.BAT;.CMD",
                "SystemRoot": system_root,
                "HOME": str(scratch),
                "HOMEDRIVE": scratch.drive,
                "HOMEPATH": str(scratch)[len(scratch.drive) :],
                "USERPROFILE": str(scratch),
                "LOCALAPPDATA": str(scratch),
                "APPDATA": str(scratch),
                "TEMP": str(scratch),
                "TMP": str(scratch),
                "WINDIR": system_root,
            }.items():
                environment_by_folded_name.setdefault(name.casefold(), (name, value))
            environment = [
                {"name": name, "value": value}
                for name, value in sorted(
                    environment_by_folded_name.values(),
                    key=lambda item: (item[0].casefold(), item[0]),
                )
            ]
            if c2_environment_drift and ordinal == 1:
                environment[0] = {**environment[0], "value": "tampered"}
            experiment_root = authority._REPOSITORY_ROOT.joinpath(
                "research", "experiments", authority.EXPERIMENT_ID
            )
            probe_bindings = [
                (command[8], "allowed"),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(*golden["path"].split("/"))
                    ),
                    "denied",
                ),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C2_REQUIRED_SOURCE_PATHS[0].split("/")
                        )
                    ),
                    "allowed" if mechanism else "denied",
                ),
                (str(experiment_root), "denied"),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C2_EQUIVALENCE_EVIDENCE_PATH.split("/")
                        )
                    ),
                    "denied",
                ),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C1_CANDIDATE_OUTCOME_PATH.split("/")
                        )
                    ),
                    "denied",
                ),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C1_STAGE_VAULT_ANCHOR_PATH.split("/")
                        )
                    ),
                    "denied",
                ),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C1_ATTEMPT_CLAIM_PATH.split("/")
                        )
                    ),
                    "denied",
                ),
                *(
                    (str(path), "denied")
                    for path in authority._c1_external_fixed_roots()
                ),
                (str(authority._REPOSITORY_ROOT / ".git"), "denied"),
            ]
            if bad_c2_external_probe and ordinal == 1:
                probe_bindings[8] = (str(root / "forged-external-root"), "denied")
            probes = [
                {
                    "path": path,
                    "expected": expected,
                    "observed": expected,
                    "winerror": 0 if expected == "allowed" else 5,
                }
                for path, expected in probe_bindings
            ]
            manifest_sha = str(ordinal) * 64
            allowed_read_paths = [
                str(fixture.julia_runtime_root),
                str(fixture.julia_depot_root),
                str(fixture.julia_depot_root / "packages"),
                str(fixture.julia_depot_root / "artifacts"),
                str(capsule_root),
            ]
            if mechanism:
                allowed_read_paths.append(
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C2_REQUIRED_SOURCE_PATHS[0].split("/")
                        )
                    )
                )
            if c2_extra_gold_grant and ordinal == 1:
                allowed_read_paths.append(
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C0_EQUIVALENCE_GOLDEN_PATHS[0].split("/")
                        )
                    )
                )
            sandbox = {
                "schema_version": (
                    "geotarget.exp-local-003.appcontainer-attestation/v2"
                ),
                "claim_reference": claim_reference,
                "profile_name": f"GeoTarget.EXPLOCAL003.synthetic-{ordinal}-{mode}",
                "package_sid": f"S-1-15-2-{ordinal}",
                "profile_storage_path": str(root / f"absent-profile-{ordinal}-{mode}"),
                "capabilities": [],
                "allowed_read_paths": allowed_read_paths,
                "read_identity_manifest_entry_count": 3,
                "read_identity_manifest_sha256": manifest_sha,
                "scratch_directory": str(scratch),
                "environment": environment,
                "inherited_handle_roles": ["stdin", "stdout", "stderr"],
                "process_id": 1000 + ordinal,
                "token_is_appcontainer": True,
                "token_appcontainer_sid_verified": True,
                "token_integrity_rid": 4096,
                "token_elevated": False,
                "token_capability_count": 0,
                "access_probes": probes,
                "denied_probe_entry_count": (
                    1
                    if bad_c2_denied_probe_accounting and ordinal == 1
                    else sum(expected == "denied" for _, expected in probe_bindings)
                ),
                "denied_probe_manifest_sha256": "d" * 64,
                "read_only_probe_entry_count": 3,
                "read_only_probe_manifest_sha256": "a" * 64,
                "scratch_access_probe_manifest_sha256": "b" * 64,
                "max_processes": 1,
                "child_process_restricted": True,
                "job_assigned_at_creation": True,
                "job_membership_verified": True,
                "job_limit_flags": 0x00002008,
                "breakaway_allowed": False,
                "kill_on_job_close": True,
                "job_empty": True,
                "acl_entry_count": 4,
                "original_acl_manifest_sha256": "c" * 64,
                "restored_acl_manifest_sha256": "c" * 64,
                "acl_exactly_restored": True,
                "scratch_emptied": True,
                "profile_deleted": True,
                "profile_storage_deleted": True,
            }
            return {
                "mode": mode,
                "mechanism_source_granted": mechanism,
                "command": command,
                "environment": environment,
                "return_code": 0,
                "termination_reason": "completed",
                "stdout": {
                    "sha256": golden["sha256"],
                    "byte_length": golden["byte_length"],
                },
                "stderr": {"sha256": _sha(b""), "byte_length": 0},
                "wall_time_nanoseconds": 1,
                "total_user_time_100ns": 0,
                "total_kernel_time_100ns": 0,
                "total_processes": 1,
                "terminated_processes": 0,
                "io_accounting": {
                    "read_operation_count": 0,
                    "write_operation_count": 0,
                    "other_operation_count": 0,
                    "read_transfer_count": 0,
                    "write_transfer_count": 0,
                    "other_transfer_count": 0,
                },
                "sandbox": sandbox,
            }

        def isolated_test_execution_record() -> dict[str, Any]:
            scratch = root / "c2-equivalence-workspace" / "scratch-isolated-test"
            command = [
                str(fixture.julia_executable),
                "--startup-file=no",
                "--history-file=no",
                "--compiled-modules=no",
                "--pkgimages=no",
                f"--project={authority._REPOSITORY_ROOT / 'julia'}",
                str(
                    authority._REPOSITORY_ROOT.joinpath(
                        *authority.C2_TEST_SOURCE_PATHS[0].split("/")
                    )
                ),
            ]
            if c2_test_command_drift:
                command[2] = "--history-file=yes"
            locked_environment = fixture.environment_lock["execution"][
                "julia_environment"
            ]
            request_environment = {
                key: locked_environment[key]
                for key in (
                    "SystemRoot",
                    "WINDIR",
                    "PATH",
                    "JULIA_LOAD_PATH",
                    "JULIA_NUM_THREADS",
                    "JULIA_CPU_TARGET",
                    "JULIA_PKG_OFFLINE",
                    "OPENBLAS_NUM_THREADS",
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                )
            }
            request_environment.update(
                {
                    "JULIA_DEPOT_PATH": str(fixture.julia_depot_root),
                    "JULIA_PKG_PRECOMPILE_AUTO": "0",
                    "JULIA_PROJECT": str(authority._REPOSITORY_ROOT / "julia"),
                }
            )
            environment_by_folded_name = {
                name.casefold(): (name, value)
                for name, value in request_environment.items()
            }
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            for name, value in {
                "COMSPEC": str(Path(system_root) / "System32" / "cmd.exe"),
                "PATH": str(Path(system_root) / "System32"),
                "PATHEXT": ".COM;.EXE;.BAT;.CMD",
                "SystemRoot": system_root,
                "HOME": str(scratch),
                "HOMEDRIVE": scratch.drive,
                "HOMEPATH": str(scratch)[len(scratch.drive) :],
                "USERPROFILE": str(scratch),
                "LOCALAPPDATA": str(scratch),
                "APPDATA": str(scratch),
                "TEMP": str(scratch),
                "TMP": str(scratch),
                "WINDIR": system_root,
            }.items():
                environment_by_folded_name.setdefault(name.casefold(), (name, value))
            environment = [
                {"name": name, "value": value}
                for name, value in sorted(
                    environment_by_folded_name.values(),
                    key=lambda item: (item[0].casefold(), item[0]),
                )
            ]
            project_paths = ("julia/Project.toml", "julia/Manifest.toml")
            package_paths = tuple(
                path
                for package in (
                    "julia/GeoTargetBase",
                    "julia/GeoTargetCore",
                    "julia/GeoTargetGeometry",
                )
                for path in (f"{package}/Project.toml", f"{package}/src")
            )
            read_grants = [
                {"path": str(fixture.julia_runtime_root), "recursive": True},
                {"path": str(fixture.julia_depot_root), "recursive": False},
                {
                    "path": str(fixture.julia_depot_root / "packages"),
                    "recursive": True,
                },
                {
                    "path": str(fixture.julia_depot_root / "artifacts"),
                    "recursive": True,
                },
                {
                    "path": str(authority._REPOSITORY_ROOT),
                    "recursive": False,
                },
                {
                    "path": str(authority._REPOSITORY_ROOT / "julia"),
                    "recursive": False,
                },
                *(
                    {
                        "path": str(
                            authority._REPOSITORY_ROOT.joinpath(*path.split("/"))
                        ),
                        "recursive": False,
                    }
                    for path in project_paths
                ),
                *(
                    {
                        "path": str(
                            authority._REPOSITORY_ROOT.joinpath(*path.split("/"))
                        ),
                        "recursive": path.endswith("/src"),
                    }
                    for path in package_paths
                ),
                {
                    "path": str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C2_TEST_SOURCE_PATHS[0].split("/")
                        )
                    ),
                    "recursive": False,
                },
            ]
            if c2_test_grant_drift:
                read_grants[5] = {
                    "path": str(authority._REPOSITORY_ROOT / "julia"),
                    "recursive": True,
                }
            experiment_root = authority._REPOSITORY_ROOT.joinpath(
                "research", "experiments", authority.EXPERIMENT_ID
            )
            probe_bindings = [
                (command[6], "allowed"),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C2_REQUIRED_SOURCE_PATHS[0].split("/")
                        )
                    ),
                    "allowed",
                ),
                (str(experiment_root), "denied"),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C2_EQUIVALENCE_EVIDENCE_PATH.split("/")
                        )
                    ),
                    "denied",
                ),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C1_CANDIDATE_OUTCOME_PATH.split("/")
                        )
                    ),
                    "denied",
                ),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C1_STAGE_VAULT_ANCHOR_PATH.split("/")
                        )
                    ),
                    "denied",
                ),
                (
                    str(
                        authority._REPOSITORY_ROOT.joinpath(
                            *authority.C1_ATTEMPT_CLAIM_PATH.split("/")
                        )
                    ),
                    "denied",
                ),
                *(
                    (str(path), "denied")
                    for path in authority._c1_external_fixed_roots()
                ),
                (str(authority._REPOSITORY_ROOT / ".git"), "denied"),
            ]
            if c2_test_probe_drift:
                probe_bindings[7] = (str(root / "forged-test-denial"), "denied")
            probes = [
                {
                    "path": path,
                    "expected": expected,
                    "observed": expected,
                    "winerror": 0 if expected == "allowed" else 5,
                }
                for path, expected in probe_bindings
            ]
            sandbox = {
                "schema_version": (
                    "geotarget.exp-local-003.appcontainer-attestation/v2"
                ),
                "claim_reference": claim_reference,
                "profile_name": "GeoTarget.EXPLOCAL003.synthetic-5-isolated-test",
                "package_sid": "S-1-15-2-5",
                "profile_storage_path": str(root / "absent-profile-5-isolated-test"),
                "capabilities": [],
                "allowed_read_paths": [grant["path"] for grant in read_grants],
                "read_identity_manifest_entry_count": 15,
                "read_identity_manifest_sha256": "5" * 64,
                "scratch_directory": str(scratch),
                "environment": environment,
                "inherited_handle_roles": ["stdin", "stdout", "stderr"],
                "process_id": 1005,
                "token_is_appcontainer": True,
                "token_appcontainer_sid_verified": True,
                "token_integrity_rid": 4096,
                "token_elevated": False,
                "token_capability_count": 0,
                "access_probes": probes,
                "denied_probe_entry_count": sum(
                    expected == "denied" for _, expected in probe_bindings
                ),
                "denied_probe_manifest_sha256": "d" * 64,
                "read_only_probe_entry_count": 15,
                "read_only_probe_manifest_sha256": "a" * 64,
                "scratch_access_probe_manifest_sha256": "b" * 64,
                "max_processes": 1,
                "child_process_restricted": True,
                "job_assigned_at_creation": True,
                "job_membership_verified": True,
                "job_limit_flags": 0x00002008,
                "breakaway_allowed": False,
                "kill_on_job_close": True,
                "job_empty": True,
                "acl_entry_count": 16,
                "original_acl_manifest_sha256": "c" * 64,
                "restored_acl_manifest_sha256": "c" * 64,
                "acl_exactly_restored": True,
                "scratch_emptied": True,
                "profile_deleted": True,
                "profile_storage_deleted": True,
            }
            return {
                "mode": "isolated-test",
                "mechanism_source_granted": True,
                "command": command,
                "environment": environment,
                "read_grants": read_grants,
                "return_code": 0,
                "termination_reason": "completed",
                "stdout": {"sha256": _sha(b"test passed\n"), "byte_length": 12},
                "stderr": {"sha256": _sha(b""), "byte_length": 0},
                "wall_time_nanoseconds": 1,
                "total_user_time_100ns": 0,
                "total_kernel_time_100ns": 0,
                "total_processes": 1,
                "terminated_processes": 0,
                "io_accounting": {
                    "read_operation_count": 0,
                    "write_operation_count": 0,
                    "other_operation_count": 0,
                    "read_transfer_count": 0,
                    "write_transfer_count": 0,
                    "other_transfer_count": 0,
                },
                "sandbox": sandbox,
            }

        comparisons = []
        for index, fixture_id in enumerate(
            ("JULIA-CORE-DEFAULT", "OPAQUE-PLUGIN-DEFAULT")
        ):
            golden = golden_records[index]
            comparisons.append(
                {
                    "fixture_id": fixture_id,
                    "fixture": fixture_records[index],
                    "golden": golden,
                    "reference_execution": execution_record(
                        "reference", golden, index * 2 + 1
                    ),
                    "mechanism_disabled_execution": execution_record(
                        "mechanism-disabled", golden, index * 2 + 2
                    ),
                    "golden_output_sha256": golden["sha256"],
                    "reference_output_sha256": golden["sha256"],
                    "mechanism_disabled_output_sha256": golden["sha256"],
                    "output_byte_length": golden["byte_length"],
                    "reference_matches_golden": True,
                    "mechanism_disabled_matches_golden": True,
                    "byte_identical": True,
                }
            )
        source_manifest = {
            "runtime_sources": runtime_records,
            "test_sources": test_records,
            "fixture_sources": fixture_records,
            "golden_sources": golden_records,
            "c0_protocol_sources": protocol_records,
        }
        isolated_test_execution = isolated_test_execution_record()
        evidence = {
            "schema_version": ("geotarget.exp-local-003.c2-default-equivalence/v1"),
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD,
            "stage": "development",
            "stage_input_anchor_commit": stage_input.anchor_commit,
            "stage_input_anchor_sha256": stage_input.anchor_file.sha256,
            "preimplementation_lock_sha256": (
                stage_input.preimplementation_lock_sha256
            ),
            "local_options_sha256": "1" * 64,
            "claim_reference": claim_reference,
            "baseline_variant": "L0-SEMANTIC",
            "candidate_mechanism_enabled": False,
            "runtime_sources": runtime_records,
            "test_sources": test_records,
            "fixture_sources": fixture_records,
            "golden_sources": golden_records,
            "c0_reference_authority": {
                "source_lock_commit": stage_input.source_lock_commit,
                "c0_source_commit": fixture.c0_commit,
                "c0_source_tree": fixture.c0_tree,
                "environment_lock_sha256": _sha(fixture.environment_lock_bytes),
                "capsule_origin": "immutable-main-git-c0-source-tree",
                "capsule_files": capsule_records,
                "capsule_manifest_sha256": _sha(_jcs(capsule_records)),
                "protocol_sources": protocol_records,
                "protocol_manifest_sha256": _sha(_jcs(protocol_records)),
                "reference_child_c2_source_access": "kernel-denied",
            },
            "source_manifest_sha256": _sha(_jcs(source_manifest)),
            "comparisons": comparisons,
            "comparison_manifest_sha256": _sha(_jcs(comparisons)),
            "isolated_test_execution": isolated_test_execution,
            "isolated_test_execution_manifest_sha256": (
                "9" * 64
                if c2_test_manifest_drift
                else _sha(_jcs(isolated_test_execution))
            ),
            "passed": True,
        }
        _write(
            fixture.main,
            authority.C2_EQUIVALENCE_EVIDENCE_PATH,
            _jcs(evidence),
        )
    sources = [
        {
            "path": path,
            "sha256": (
                "3" * 64
                if forged_observer and path == authority.RUNNER_SOURCE_PATH
                else _sha(payload)
            ),
        }
        for path, payload in sorted(source_payloads.items())
    ]
    observer = next(
        item for item in sources if item["path"] == authority.RUNNER_SOURCE_PATH
    )
    execution_lock = {
        "schema_version": "geotarget.exp-local-003.candidate-execution-lock/v1",
        "card_sha256": CARD,
        "stage": fixture.stage,
        "candidate_input_sha256": stage_input.candidate_input_sha256,
        "local_options_sha256": "1" * 64,
        "stage_input_anchor_sha256": stage_input.anchor_file.sha256,
        "stage_input_anchor_commit": stage_input.anchor_commit,
        "runner_source_path": observer["path"],
        "runner_source_sha256": observer["sha256"],
        "source_manifest_sha256": _sha(_jcs(sources)),
        "allowed_sources": sources,
        "allowed_candidate_artifacts": [
            {"path": f"candidate/{path}", "sha256": record.sha256}
            for path, record in sorted(stage_input.candidate_files.items())
        ],
    }
    if legacy_anchor_fields:
        execution_lock["c1_vault_anchor_sha256"] = execution_lock.pop(
            "stage_input_anchor_sha256"
        )
        execution_lock["c1_vault_anchor_commit"] = execution_lock.pop(
            "stage_input_anchor_commit"
        )
    lock_bytes = _jcs(execution_lock)
    lock_path = (
        authority.C2_EXECUTION_LOCK_PATH
        if fixture.stage == "development"
        else authority.LOCKED_EXECUTION_LOCK_PATH
    )
    _write(fixture.main, lock_path, lock_bytes)
    if _git(fixture.main, "status", "--porcelain"):
        lock_commit, lock_tree = _commit(fixture.main, "execution lock")
    else:
        lock_commit = _git(fixture.main, "rev-parse", "HEAD")
        lock_tree = _git(fixture.main, "rev-parse", "HEAD^{tree}")
    lock_record = _record(lock_path, lock_bytes)
    stage_input_ref = {
        "commit": stage_input.anchor_commit,
        "tree": stage_input.anchor_tree,
        "file": {
            "path": stage_input.anchor_file.path,
            "sha256": stage_input.anchor_file.sha256,
            "byte_length": stage_input.anchor_file.byte_length,
        },
    }
    execution_lock_ref = {
        "commit": lock_commit,
        "tree": lock_tree,
        "file": lock_record,
    }

    run_suffix = (
        "legacy-anchor"
        if legacy_anchor_fields
        else (
            "legacy-execution-source"
            if legacy_execution_source_field
            else (
                "bad-launcher-claim"
                if bad_launcher_claim
                else (
                    "forged-observer"
                    if forged_observer
                    else ("bad" if bad_ack else "run")
                )
            )
        )
    )
    run = root / f"{fixture.stage}-{run_suffix}" / f"{fixture.stage}-candidate-run"
    _init_repo(run)
    marker_nonce = "8" * 64
    marker_bytes = _jcs(
        {
            "schema_version": "geotarget.exp-local-003.candidate-launch-attempt/v2",
            "card_sha256": CARD,
            "stage": fixture.stage,
            "nonce": marker_nonce,
            "rerun_permitted": False,
            "failure_is_terminal": True,
        }
    )
    marker_path = run.parent / f"{fixture.stage}-candidate-run.attempt"
    marker_path.write_bytes(marker_bytes)
    marker_info = marker_path.lstat()
    marker_claim = {
        "file": _record(marker_path.name, marker_bytes),
        "nonce_sha256": _sha(bytes.fromhex(marker_nonce)),
        "filesystem_identity": {
            "device_decimal": str(marker_info.st_dev),
            "inode_decimal": str(marker_info.st_ino),
            "empty_claim_ctime_nanoseconds_decimal": str(marker_info.st_ctime_ns),
            "link_count": 1,
        },
    }

    def c0_external(path: str) -> dict[str, Any]:
        payload = (fixture.main / Path(*path.split("/"))).read_bytes()
        return {
            "commit": fixture.c0_commit,
            "tree": fixture.c0_tree,
            "file": _record(path, payload),
        }

    launcher_authority = c0_external(
        "research/experiments/EXP-LOCAL-003/source/launch_candidate.py"
    )
    observer_authority = c0_external(
        "research/experiments/EXP-LOCAL-003/source/candidate_observer.py"
    )
    broker_authority = c0_external(authority.C0_SANDBOX_BROKER_PATH)
    candidate_root_name = (
        "development-candidate-inputs"
        if fixture.stage == "development"
        else "locked-candidate-inputs"
    )
    expected_candidate_root = authority._REPOSITORY_ROOT.joinpath(
        "research", "experiments", authority.EXPERIMENT_ID, candidate_root_name
    )
    expected_scratch = (
        authority._REPOSITORY_ROOT.with_name(
            f"{authority._REPOSITORY_ROOT.name}-sandbox-scratch"
        )
        / authority.EXPERIMENT_ID
        / f".{fixture.stage}-candidate-run-scratch.partial"
    )
    project_root = authority._REPOSITORY_ROOT / "julia"
    project_files = (project_root / "Project.toml", project_root / "Manifest.toml")
    package_roots = tuple(
        project_root / name
        for name in ("GeoTargetBase", "GeoTargetCore", "GeoTargetGeometry")
    )
    package_projects = tuple(path / "Project.toml" for path in package_roots)
    package_sources = tuple(path / "src" for path in package_roots)
    candidate_runner = authority._REPOSITORY_ROOT.joinpath(
        *authority.RUNNER_SOURCE_PATH.split("/")
    )
    recursive_roots = authority._collapse_recursive_roots(
        (fixture.julia_runtime_root, expected_candidate_root, *package_sources)
    )
    request_grants = [
        {"path": str(path), "recursive": True} for path in recursive_roots
    ]
    request_grants.append({"path": str(fixture.julia_depot_root), "recursive": False})
    for name in ("packages", "artifacts"):
        request_grants.append(
            {"path": str(fixture.julia_depot_root / name), "recursive": True}
        )
    for path in (
        authority._REPOSITORY_ROOT,
        project_root,
        candidate_runner,
        *project_files,
        *package_projects,
    ):
        if not any(path == root or root in path.parents for root in recursive_roots):
            request_grants.append({"path": str(path), "recursive": False})
    if extra_candidate_gold_grant:
        request_grants.append(
            {
                "path": str(
                    authority._REPOSITORY_ROOT.joinpath(
                        *authority.C0_EQUIVALENCE_GOLDEN_PATHS[0].split("/")
                    )
                ),
                "recursive": False,
            }
        )

    request_environment_mapping = {
        "SystemRoot": r"C:\Windows",
        "WINDIR": r"C:\Windows",
        "PATH": os.pathsep.join(
            (str(fixture.julia_executable.parent), r"C:\Windows\System32")
        ),
        "JULIA_DEPOT_PATH": str(fixture.julia_depot_root),
        "JULIA_LOAD_PATH": os.pathsep.join(("@", "@stdlib")),
        "JULIA_NUM_THREADS": "1",
        "JULIA_CPU_TARGET": "generic",
        "JULIA_PKG_OFFLINE": "true",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "LC_ALL": "C",
        "LANG": "C",
        "GEOTARGET_JULIA_PROJECT": str(project_root),
        "GEOTARGET_EXECUTION_LOCK_SHA256": _sha(lock_bytes),
        "GEOTARGET_C0_PREEXIT_PROTOCOL": (
            "u64be-frame-flush-close-stdout-crt-close-fd1-yield-read-ack/v3"
        ),
    }
    if candidate_environment_drift:
        request_environment_mapping["JULIA_NUM_THREADS"] = "2"
    request_environment = [
        {"name": name, "value": value}
        for name, value in sorted(request_environment_mapping.items())
    ]
    first_artifact = sorted(stage_input.candidate_files)[0]
    request_probes = [
        {
            "path": str(expected_candidate_root / first_artifact),
            "expected": "allowed",
        },
        {
            "path": str(
                authority._REPOSITORY_ROOT
                / "research"
                / "experiments"
                / authority.EXPERIMENT_ID
                / "source"
                / "candidate_observer.py"
            ),
            "expected": "denied",
        },
        {
            "path": str(
                authority._REPOSITORY_ROOT.with_name(
                    f"{authority._REPOSITORY_ROOT.name}-vault"
                )
                / authority.EXPERIMENT_ID
                / f"{fixture.stage}-assessor-vault"
            ),
            "expected": "denied",
        },
        {
            "path": str(
                authority._REPOSITORY_ROOT.with_name(
                    f"{authority._REPOSITORY_ROOT.name}-private-audit"
                )
                / authority.EXPERIMENT_ID
                / f"{fixture.stage}-generator-private-vault"
            ),
            "expected": "denied",
        },
        {"path": str(run.parent.absolute()), "expected": "denied"},
        {
            "path": str(
                run.parent.absolute()
                / f".{fixture.stage}-candidate-run-staging.partial"
            ),
            "expected": "denied",
        },
        {"path": str(marker_path.absolute()), "expected": "denied"},
        {
            "path": str(
                authority._REPOSITORY_ROOT.with_name(
                    f"{authority._REPOSITORY_ROOT.name}-assessment-evidence"
                )
                / authority.EXPERIMENT_ID
            ),
            "expected": "denied",
        },
        {
            "path": str(authority._REPOSITORY_ROOT / ".git"),
            "expected": "denied",
        },
    ]
    request_command = [
        str(fixture.julia_executable),
        "--startup-file=no",
        "--history-file=no",
        "--compiled-modules=no",
        "--pkgimages=no",
        f"--project={project_root}",
        str(candidate_runner),
        "--formal-appcontainer-child",
        fixture.stage,
        str(expected_candidate_root),
        str(expected_scratch),
    ]
    if candidate_command_drift:
        request_command[2] = "--history-file=yes"
    read_identity_sha = "9" * 64
    sandbox_request = {
        "backend": "windows-classic-appcontainer",
        "claim_reference": _sha(marker_bytes),
        "expected_read_identity_manifest_sha256": read_identity_sha,
        "command": request_command,
        "command_sha256": _sha(_jcs(request_command)),
        "working_directory": request_command[-1],
        "environment": request_environment,
        "environment_sha256": _sha(_jcs(request_environment)),
        "allowed_read": request_grants,
        "allowed_read_manifest_sha256": _sha(_jcs(request_grants)),
        "access_probes": request_probes,
        "access_probe_manifest_sha256": _sha(_jcs(request_probes)),
        "capabilities": [],
        "network_capabilities": [],
        "timeout_seconds": 21_600,
        "stdout_limit_bytes": 256 * 1024 * 1024,
        "stderr_limit_bytes": 1024 * 1024,
        "preexit_payload_limit_bytes": 256 * 1024 * 1024 - 8,
        "job": {
            "assigned_at_creation": True,
            "breakaway_allowed": False,
            "child_process_policy": "restricted-no-descendants",
            "kill_on_close": True,
            "max_processes": 1,
        },
    }
    environment_by_folded_name = {
        entry["name"].casefold(): (entry["name"], entry["value"])
        for entry in request_environment
    }
    scratch_path = Path(sandbox_request["working_directory"])
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    for name, value in {
        "COMSPEC": str(Path(system_root) / "System32" / "cmd.exe"),
        "PATH": str(Path(system_root) / "System32"),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "SystemRoot": system_root,
        "HOME": str(scratch_path),
        "HOMEDRIVE": scratch_path.drive,
        "HOMEPATH": str(scratch_path)[len(scratch_path.drive) :],
        "USERPROFILE": str(scratch_path),
        "LOCALAPPDATA": str(scratch_path),
        "APPDATA": str(scratch_path),
        "TEMP": str(scratch_path),
        "TMP": str(scratch_path),
        "WINDIR": system_root,
    }.items():
        environment_by_folded_name.setdefault(name.casefold(), (name, value))
    attested_environment = [
        {"name": name, "value": value}
        for name, value in sorted(
            environment_by_folded_name.values(),
            key=lambda item: (item[0].casefold(), item[0]),
        )
    ]
    attempt = {
        "schema_version": authority.ATTEMPT_SCHEMA,
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": CARD,
        "stage": fixture.stage,
        "candidate_input_sha256": stage_input.candidate_input_sha256,
        "stage_input_anchor": stage_input_ref,
        "candidate_execution_lock": execution_lock_ref,
        "execution_source": {"commit": lock_commit, "tree": lock_tree},
        "launcher_claim": marker_claim,
        "launcher_authority": launcher_authority,
        "observer_authority": observer_authority,
        "sandbox_broker_authority": broker_authority,
        "sandbox_request": sandbox_request,
        "rerun_permitted": False,
        "prelaunch_state": {
            "launch_not_started": True,
            "candidate_process_created": False,
            "repository_control": "c0-observer",
            "runner_evaluated_by_observer": False,
            "assessor_started": False,
            "assessor_vault_opened": False,
            "generator_private_vault_opened": False,
        },
    }
    if bad_launcher_claim:
        attempt["launcher_claim"] = {
            **marker_claim,
            "nonce_sha256": "0" * 64,
        }
    if legacy_execution_source_field:
        attempt["c2_source"] = attempt.pop("execution_source")
    attempt_bytes = _jcs(attempt)
    attempt_path = "run/attempt-claim.json"
    attempt_record = _record(attempt_path, attempt_bytes)
    _write(run, attempt_path, attempt_bytes)
    attempt_commit, attempt_tree = _commit(run, "candidate attempt claim")

    raw_jcs = _jcs(
        {
            "schema_version": "geotarget.exp-local-003.candidate-output/v1",
            "stage": fixture.stage,
            "candidate_input_sha256": stage_input.candidate_input_sha256,
            "candidate_process": {
                "runner_source_path": observer["path"],
                "runner_source_sha256": observer["sha256"],
                "observation_complete": True,
                "source_manifest_sha256": execution_lock["source_manifest_sha256"],
                "loaded_sources": sources,
                "opened_artifacts": execution_lock["allowed_candidate_artifacts"],
            },
            "cases": [],
            "report_only_times": {
                "process_cpu_seconds": 0,
                "end_to_end_cpu_seconds": 0,
                "formal_wall_seconds": None,
                "host_exclusion_passed": True,
            },
        }
    )
    raw_gzip = authority.deterministic_gzip(raw_jcs)
    raw_path = "run/candidate-output.json.gz"
    raw_record = _record(raw_path, raw_gzip)
    _write(run, raw_path, raw_gzip)
    raw_commit, raw_tree = _commit(run, "candidate raw output")
    preexit_pid = 12345
    raw_payload_sha = _sha(raw_jcs)
    process_id = _sha(
        b"GTLOCAL3C0PROCESS1\0"
        + bytes.fromhex(marker_nonce)
        + str(preexit_pid).encode("ascii")
        + bytes.fromhex(raw_payload_sha)
        + len(lock_commit).to_bytes(1, "big")
        + bytes.fromhex(lock_commit)
    )
    ack = "6" * 64
    seal = {
        "schema_version": authority.PREEXIT_SCHEMA,
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": CARD,
        "stage": fixture.stage,
        "process_instance_id": process_id,
        "candidate_input_sha256": stage_input.candidate_input_sha256,
        "launcher_claim": marker_claim,
        "observer_authority": observer_authority,
        "sandbox_request_sha256": _sha(_jcs(sandbox_request)),
        "preexit_observation": {
            "process_id": preexit_pid,
            "active_processes": 1,
            "root_process_still_active": True,
            "payload_sha256": raw_payload_sha,
            "payload_byte_length": len(raw_jcs),
            "observer_elapsed_nanoseconds_decimal": "17",
            "runner_evaluated_by_observer": False,
            "raw_output_stream_closed_before_ack": True,
            "ack_pending": True,
            "assessor_started": False,
            "assessor_vault_opened": False,
            "generator_private_vault_opened": False,
        },
        "event": {
            "kind": "candidate-output-preexit-seal",
            "ordinal": 2,
            "parent": {"kind": "candidate-raw-output", "sha256": raw_record["sha256"]},
        },
        "raw_output": raw_record,
        "changed_paths": [raw_path],
        "ack": {
            "token_sha256": ack,
            "raw_closed_ordinal": 1,
            "seal_persisted_ordinal": 2,
            "ack_released_ordinal": 3,
        },
    }
    seal_bytes = _jcs(seal)
    seal_path = "run/preexit-seal.json"
    seal_record = _record(seal_path, seal_bytes)
    _write(run, seal_path, seal_bytes)
    seal_commit, seal_tree = _commit(run, "candidate preexit seal")
    observed_probes = [
        {
            "path": probe["path"],
            "expected": probe["expected"],
            "observed": probe["expected"],
            "winerror": 0 if probe["expected"] == "allowed" else 5,
        }
        for probe in request_probes
    ]
    attestation = {
        "schema_version": "geotarget.exp-local-003.appcontainer-attestation/v2",
        "claim_reference": _sha(marker_bytes),
        "profile_name": "GeoTarget.EXPLOCAL003.synthetic-candidate",
        "package_sid": "S-1-15-2-12345",
        "profile_storage_path": str(run.parent / "deleted-profile"),
        "capabilities": [],
        "allowed_read_paths": [grant["path"] for grant in request_grants],
        "read_identity_manifest_entry_count": 2,
        "read_identity_manifest_sha256": read_identity_sha,
        "scratch_directory": sandbox_request["working_directory"],
        "environment": attested_environment,
        "inherited_handle_roles": ["stdin", "stdout", "stderr"],
        "process_id": preexit_pid,
        "token_is_appcontainer": True,
        "token_appcontainer_sid_verified": True,
        "token_integrity_rid": 4096,
        "token_elevated": False,
        "token_capability_count": 0,
        "access_probes": observed_probes,
        "denied_probe_entry_count": sum(
            probe["expected"] == "denied" for probe in request_probes
        ),
        "denied_probe_manifest_sha256": (
            "not-a-sha256" if bad_candidate_denied_probe_manifest else "d" * 64
        ),
        "read_only_probe_entry_count": 2,
        "read_only_probe_manifest_sha256": "a" * 64,
        "scratch_access_probe_manifest_sha256": "b" * 64,
        "max_processes": 1,
        "child_process_restricted": True,
        "job_assigned_at_creation": True,
        "job_membership_verified": True,
        "job_limit_flags": 0x00002008,
        "breakaway_allowed": False,
        "kill_on_job_close": True,
        "job_empty": True,
        "acl_entry_count": 3,
        "original_acl_manifest_sha256": "c" * 64,
        "restored_acl_manifest_sha256": "c" * 64,
        "acl_exactly_restored": True,
        "scratch_emptied": True,
        "profile_deleted": True,
        "profile_storage_deleted": True,
    }
    sandbox_result = {
        "command_sha256": sandbox_request["command_sha256"],
        "return_code": 0,
        "termination_reason": "completed",
        "stdout_sha256": raw_payload_sha,
        "stdout_byte_length": len(raw_jcs),
        "stderr_sha256": _sha(b""),
        "stderr_byte_length": 0,
        "preexit_receipt": {
            "payload_sha256": raw_payload_sha,
            "payload_byte_length": len(raw_jcs),
            "ack_sha256": ack,
            "ack_byte_length": 80,
            "active_processes_before_callback": 1,
            "root_active_before_callback": True,
            "active_processes_before_ack": 1,
            "root_active_before_ack": True,
            "callback_completed": True,
            "ack_released": True,
        },
        "job_accounting": {
            "wall_time_nanoseconds_decimal": "23",
            "total_user_time_100ns_decimal": "1",
            "total_kernel_time_100ns_decimal": "1",
            "total_processes": 1,
            "terminated_processes": 0,
            "read_operation_count_decimal": "0",
            "write_operation_count_decimal": "0",
            "other_operation_count_decimal": "0",
            "read_transfer_count_decimal": "0",
            "write_transfer_count_decimal": "0",
            "other_transfer_count_decimal": "0",
        },
        "appcontainer_attestation": attestation,
    }
    exit_document = {
        "schema_version": authority.EXIT_SCHEMA,
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": CARD,
        "stage": fixture.stage,
        "process_instance_id": process_id,
        "candidate_input_sha256": stage_input.candidate_input_sha256,
        "launcher_claim": marker_claim,
        "observer_authority": observer_authority,
        "termination_observation": {
            "wait_observed": True,
            "job_tree_empty": True,
            "ack_sent_after_preexit_commit": True,
            "candidate_access_revoked": True,
            "profile_deleted": True,
            "scratch_emptied": True,
            "runner_evaluated_by_observer": False,
            "assessor_started": False,
            "assessor_vault_opened": False,
            "generator_private_vault_opened": False,
        },
        "event": {
            "kind": "candidate-process-exit",
            "ordinal": 5,
            "parent": {
                "kind": "candidate-output-preexit-seal",
                "sha256": seal_record["sha256"],
            },
        },
        "raw_output": raw_record,
        "preexit_seal": seal_record,
        "changed_paths": [raw_path],
        "ack": {
            "token_sha256": ack,
            "ack_released_ordinal": 3,
            "successful_exit_after_ack_ordinal": 4,
            "job_empty_observed_ordinal": 6 if bad_ack else 5,
        },
        "exit_status": {"kind": "exited", "code": 0},
        "candidate_accounting": {
            "process_cpu_nanoseconds_decimal": "200",
            "observer_wall_nanoseconds_decimal": "23",
            "host_exclusion_passed": True,
            "count_in_end_to_end_exactly_once": True,
        },
        "sandbox_result": sandbox_result,
    }
    exit_bytes = _jcs(exit_document)
    exit_path = "run/process-exit.json"
    exit_record = _record(exit_path, exit_bytes)
    _write(run, exit_path, exit_bytes)
    exit_commit, exit_tree = _commit(run, "candidate process exit")
    manifest = {
        "schema_version": authority.MANIFEST_SCHEMA,
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": CARD,
        "stage": fixture.stage,
        "kind": "candidate-run",
        "files": [
            {
                "role": "raw_output",
                "file": raw_record,
                "media_type": "application/json",
                "content_encoding": "deterministic-gzip",
            },
            {
                "role": "preexit_seal",
                "file": seal_record,
                "media_type": "application/json",
                "content_encoding": "identity",
            },
            {
                "role": "process_exit",
                "file": exit_record,
                "media_type": "application/json",
                "content_encoding": "identity",
            },
        ],
    }
    manifest_bytes = _jcs(manifest)
    manifest_path = "run/manifest.json"
    manifest_record = _record(manifest_path, manifest_bytes)
    authority_document = {
        "schema_version": authority.CANDIDATE_AUTHORITY_SCHEMA,
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": CARD,
        "stage": fixture.stage,
        "process_instance_id": process_id,
        "candidate_input_sha256": stage_input.candidate_input_sha256,
        "stage_input_anchor": stage_input_ref,
        "candidate_execution_lock": execution_lock_ref,
        "candidate_publication_tree_sha256": stage_input.candidate_publication_tree_sha256,
        "launcher_claim_sha256": _sha(marker_bytes),
        "observer_authority": observer_authority,
        "sandbox_broker_authority": broker_authority,
        "sandbox_result_sha256": _sha(_jcs(sandbox_result)),
        "attempt_claim": attempt_record,
        "history": {
            "attempt_claim": {"commit": attempt_commit, "tree": attempt_tree},
            "raw_output": {"commit": raw_commit, "tree": raw_tree},
            "preexit_seal": {"commit": seal_commit, "tree": seal_tree},
            "process_exit": {"commit": exit_commit, "tree": exit_tree},
        },
        "event": {
            "kind": "candidate-run-authority",
            "ordinal": 6,
            "parent": {
                "kind": "candidate-process-exit",
                "sha256": exit_record["sha256"],
            },
        },
        "raw_output": raw_record,
        "preexit_seal": seal_record,
        "process_exit": exit_record,
        "changed_paths": [raw_path],
        "manifest": manifest_record,
    }
    authority_bytes = _jcs(authority_document)
    authority_path = "run/candidate-run-authority.json"
    authority_record = authority.FileRecord(
        path=authority_path,
        sha256=_sha(authority_bytes),
        byte_length=len(authority_bytes),
    )
    _write(run, manifest_path, manifest_bytes)
    _write(run, authority_path, authority_bytes)
    commit, tree = _commit(run, "candidate run")
    return run, commit, tree, authority_record


class AuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        git = Path(shutil.which("git") or "")
        if not git.is_absolute():
            raise unittest.SkipTest("Git is unavailable")
        cls.git = authority.pin_git_executable(git, _sha(git.read_bytes()))

    def test_strict_jcs_duplicate_noncanonical_and_gzip_fixture(self) -> None:
        with self.assertRaisesRegex(authority.AuthorityError, "duplicate"):
            authority.strict_jcs_bytes(b'{"a":1,"a":2}')
        with self.assertRaisesRegex(authority.AuthorityError, "not exact"):
            authority.strict_jcs_bytes(b'{"b": 1}')
        payload = b"EXP-LOCAL-003 deterministic gzip fixture\n"
        encoded = authority.deterministic_gzip(payload)
        self.assertEqual(
            _sha(encoded),
            "dc552c32bce72c83823b107364fdd21edaa4fff2f847b0d2eb804f8ca8bfaeae",
        )
        self.assertEqual(
            authority.decode_deterministic_gzip(encoded, context="fixture"), payload
        )
        mutated = bytearray(encoded)
        mutated[9] = 10
        with self.assertRaisesRegex(authority.AuthorityError, "deterministic"):
            authority.decode_deterministic_gzip(bytes(mutated), context="fixture")

    def test_development_and_locked_stage_inputs_resolve(self) -> None:
        for stage in ("development", "locked"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                fixture = Fixture(Path(temporary), stage)
                record = authority.resolve_stage_input_authority(
                    anchor_repository=fixture.main,
                    anchor_commit=fixture.anchor_commit,
                    anchor_path=fixture.anchor_path,
                    anchor_sha256=_sha(fixture.anchor_bytes),
                    candidate_publication_root=fixture.candidate,
                    assessor_vault_repository=fixture.assessor,
                    git_executable=self.git,
                )
                self.assertEqual(record.stage, stage)
                self.assertEqual(
                    record.candidate_input_sha256, fixture.candidate_input_sha
                )
                self.assertTrue(
                    record.bootstrap_indices.startswith(b"synthetic-bootstrap")
                )
                with self.assertRaises(TypeError):
                    record.assessor_truth["stage"] = "changed"  # type: ignore[index]
                run, commit, tree, authority_file = _build_run(
                    Path(temporary), fixture, record
                )
                candidate_run = authority.resolve_candidate_run_authority(
                    run,
                    git_executable=self.git,
                    commit=commit,
                    tree=tree,
                    authority_file=authority_file,
                    expected_stage=stage,
                    stage_input=record,
                    execution_lock_repository=fixture.main,
                )
                self.assertEqual(candidate_run.stage, stage)

    def test_worktree_tamper_and_extra_vault_tree_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            (fixture.candidate / "manifest.json").write_bytes(b"{}")
            with self.assertRaisesRegex(
                authority.AuthorityError,
                "tree differs|live candidate publication differs",
            ):
                authority.resolve_stage_input_authority(
                    anchor_repository=fixture.main,
                    anchor_commit=fixture.anchor_commit,
                    anchor_path=fixture.anchor_path,
                    anchor_sha256=_sha(fixture.anchor_bytes),
                    candidate_publication_root=fixture.candidate,
                    assessor_vault_repository=fixture.assessor,
                    git_executable=self.git,
                )

    def test_c1_commit_cannot_smuggle_candidate_mechanism(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary), c1_extra_mechanism=True)
            with self.assertRaisesRegex(
                authority.AuthorityError, "C1 commit additions|candidate mechanism"
            ):
                authority.resolve_stage_input_authority(
                    anchor_repository=fixture.main,
                    anchor_commit=fixture.anchor_commit,
                    anchor_path=fixture.anchor_path,
                    anchor_sha256=_sha(fixture.anchor_bytes),
                    candidate_publication_root=fixture.candidate,
                    assessor_vault_repository=fixture.assessor,
                    git_executable=self.git,
                )
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            for path in authority.C2_REQUIRED_SOURCE_PATHS:
                _write(fixture.main, path, f"C2 {path}\n".encode())
            for path in authority.C2_TEST_SOURCE_PATHS:
                _write(fixture.main, path, f"C2 test {path}\n".encode())
            _write(
                fixture.main,
                authority.C2_EQUIVALENCE_EVIDENCE_PATH,
                b"{}",
            )
            _write(fixture.main, authority.C2_EXECUTION_LOCK_PATH, b"{}")
            (fixture.candidate / "manifest.json").write_bytes(b"forged C1 input")
            malicious_c2, _ = _commit(fixture.main, "malicious C2")
            repository = authority.GitObjectRepository(fixture.main, self.git)
            with self.assertRaisesRegex(authority.AuthorityError, "modifies frozen C1"):
                authority._verify_c2_introduction(
                    repository,
                    stage_input_commit=fixture.anchor_commit,
                    c2_source_commit=malicious_c2,
                )
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary), assessor_extra=True)
            with self.assertRaisesRegex(authority.AuthorityError, "not closed"):
                authority.resolve_stage_input_authority(
                    anchor_repository=fixture.main,
                    anchor_commit=fixture.anchor_commit,
                    anchor_path=fixture.anchor_path,
                    anchor_sha256=_sha(fixture.anchor_bytes),
                    candidate_publication_root=fixture.candidate,
                    assessor_vault_repository=fixture.assessor,
                    git_executable=self.git,
                )

    def test_git_symlink_and_replace_ref_cannot_change_objects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            _init_repo(root)
            _write(root, "safe", b"one")
            first, first_tree = _commit(root, "first")
            _write(root, "safe", b"two")
            second, _ = _commit(root, "second")
            _git(root, "replace", first, second)
            repository = authority.GitObjectRepository(root, self.git)
            self.assertEqual(repository.commit_tree(first), first_tree)

            blob = _git(root, "hash-object", "-w", "--stdin", input_bytes=b"target")
            _git(root, "update-index", "--add", "--cacheinfo", f"120000,{blob},link")
            _git(root, "commit", "-q", "-m", "symlink")
            symlink_commit = _git(root, "rev-parse", "HEAD")
            symlink_tree = _git(root, "rev-parse", "HEAD^{tree}")
            with self.assertRaisesRegex(authority.AuthorityError, "symlink"):
                repository.snapshot(symlink_commit, symlink_tree)

    def test_candidate_run_dag_and_ack_order_are_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            stage_input = authority.resolve_stage_input_authority(
                anchor_repository=fixture.main,
                anchor_commit=fixture.anchor_commit,
                anchor_path=fixture.anchor_path,
                anchor_sha256=_sha(fixture.anchor_bytes),
                candidate_publication_root=fixture.candidate,
                assessor_vault_repository=fixture.assessor,
                git_executable=self.git,
            )
            run, commit, tree, record = _build_run(
                Path(temporary), fixture, stage_input
            )
            resolved = authority.resolve_candidate_run_authority(
                run,
                git_executable=self.git,
                commit=commit,
                tree=tree,
                authority_file=record,
                expected_stage="development",
                stage_input=stage_input,
                execution_lock_repository=fixture.main,
            )
            self.assertEqual(resolved.candidate_process_cpu_nanoseconds, 200)
            self.assertFalse(resolved.attempt_claim["rerun_permitted"])
            attempt_schema = json.loads(
                (SOURCE / "candidate-run-attempt.schema.json").read_text("utf-8")
            )
            attempt_validator = Draft202012Validator(attempt_schema)
            attempt_document = json.loads(
                (run / "run/attempt-claim.json").read_text("utf-8")
            )
            self.assertFalse(list(attempt_validator.iter_errors(attempt_document)))
            legacy_attempt = dict(attempt_document)
            legacy_attempt["c2_source"] = legacy_attempt.pop("execution_source")
            self.assertTrue(list(attempt_validator.iter_errors(legacy_attempt)))
            bad_run, bad_commit, bad_tree, bad_record = _build_run(
                Path(temporary), fixture, stage_input, bad_ack=True
            )
            with self.assertRaisesRegex(authority.AuthorityError, "ordering"):
                authority.resolve_candidate_run_authority(
                    bad_run,
                    git_executable=self.git,
                    commit=bad_commit,
                    tree=bad_tree,
                    authority_file=bad_record,
                    expected_stage="development",
                    stage_input=stage_input,
                    execution_lock_repository=fixture.main,
                )
            forged_run, forged_commit, forged_tree, forged_record = _build_run(
                Path(temporary), fixture, stage_input, forged_observer=True
            )
            with self.assertRaisesRegex(authority.AuthorityError, "source differs"):
                authority.resolve_candidate_run_authority(
                    forged_run,
                    git_executable=self.git,
                    commit=forged_commit,
                    tree=forged_tree,
                    authority_file=forged_record,
                    expected_stage="development",
                    stage_input=stage_input,
                    execution_lock_repository=fixture.main,
                )
            legacy_run, legacy_commit, legacy_tree, legacy_record = _build_run(
                Path(temporary), fixture, stage_input, legacy_anchor_fields=True
            )
            with self.assertRaisesRegex(
                authority.AuthorityError, "candidate execution lock keys differ"
            ):
                authority.resolve_candidate_run_authority(
                    legacy_run,
                    git_executable=self.git,
                    commit=legacy_commit,
                    tree=legacy_tree,
                    authority_file=legacy_record,
                    expected_stage="development",
                    stage_input=stage_input,
                    execution_lock_repository=fixture.main,
                )
            legacy_source_run, source_commit, source_tree, source_record = _build_run(
                Path(temporary),
                fixture,
                stage_input,
                legacy_execution_source_field=True,
            )
            with self.assertRaisesRegex(
                authority.AuthorityError, "candidate attempt claim keys differ"
            ):
                authority.resolve_candidate_run_authority(
                    legacy_source_run,
                    git_executable=self.git,
                    commit=source_commit,
                    tree=source_tree,
                    authority_file=source_record,
                    expected_stage="development",
                    stage_input=stage_input,
                    execution_lock_repository=fixture.main,
                )
            bad_claim_run, claim_commit, claim_tree, claim_record = _build_run(
                Path(temporary),
                fixture,
                stage_input,
                bad_launcher_claim=True,
            )
            with self.assertRaisesRegex(
                authority.AuthorityError, "launcher nonce binding"
            ):
                authority.resolve_candidate_run_authority(
                    bad_claim_run,
                    git_executable=self.git,
                    commit=claim_commit,
                    tree=claim_tree,
                    authority_file=claim_record,
                    expected_stage="development",
                    stage_input=stage_input,
                    execution_lock_repository=fixture.main,
                )

    def test_candidate_history_rejects_collapsed_reparented_and_mutated_trees(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            fixture = Fixture(temporary_root)
            stage_input = authority.resolve_stage_input_authority(
                anchor_repository=fixture.main,
                anchor_commit=fixture.anchor_commit,
                anchor_path=fixture.anchor_path,
                anchor_sha256=_sha(fixture.anchor_bytes),
                candidate_publication_root=fixture.candidate,
                assessor_vault_repository=fixture.assessor,
                git_executable=self.git,
            )
            run, commit, tree, record = _build_run(temporary_root, fixture, stage_input)

            def resolve(candidate_commit: str, candidate_tree: str) -> None:
                authority.resolve_candidate_run_authority(
                    run,
                    git_executable=self.git,
                    commit=candidate_commit,
                    tree=candidate_tree,
                    authority_file=record,
                    expected_stage="development",
                    stage_input=stage_input,
                    execution_lock_repository=fixture.main,
                )

            collapsed = _commit_tree_object(run, tree, "all evidence at once")
            with self.assertRaisesRegex(
                authority.AuthorityError, "final authority.*process-exit child"
            ):
                resolve(collapsed, tree)

            exit_commit = _git(run, "rev-parse", f"{commit}^")
            raw_commit = _git(run, "rev-parse", f"{commit}^^^")
            reparented = _commit_tree_object(
                run, tree, "authority with wrong parent", raw_commit
            )
            with self.assertRaisesRegex(
                authority.AuthorityError, "final authority.*process-exit child"
            ):
                resolve(reparented, tree)

            _write(run, "run/candidate-output.json.gz", b"mutated prior blob")
            _git(run, "add", "run/candidate-output.json.gz")
            mutated_tree = _git(run, "write-tree")
            mutated = _commit_tree_object(
                run, mutated_tree, "authority mutates prior evidence", exit_commit
            )
            with self.assertRaisesRegex(
                authority.AuthorityError, "changed an earlier blob"
            ):
                resolve(mutated, mutated_tree)

    def test_denied_probe_accounting_is_bound_by_both_authority_resolvers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = Fixture(root)
            stage_input = authority.resolve_stage_input_authority(
                anchor_repository=fixture.main,
                anchor_commit=fixture.anchor_commit,
                anchor_path=fixture.anchor_path,
                anchor_sha256=_sha(fixture.anchor_bytes),
                candidate_publication_root=fixture.candidate,
                assessor_vault_repository=fixture.assessor,
                git_executable=self.git,
            )
            run, commit, tree, record = _build_run(
                root,
                fixture,
                stage_input,
                bad_candidate_denied_probe_manifest=True,
            )
            with self.assertRaisesRegex(
                authority.AuthorityError, "denied_probe_manifest_sha256"
            ):
                authority.resolve_candidate_run_authority(
                    run,
                    git_executable=self.git,
                    commit=commit,
                    tree=tree,
                    authority_file=record,
                    expected_stage="development",
                    stage_input=stage_input,
                    execution_lock_repository=fixture.main,
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = Fixture(root)
            stage_input = authority.resolve_stage_input_authority(
                anchor_repository=fixture.main,
                anchor_commit=fixture.anchor_commit,
                anchor_path=fixture.anchor_path,
                anchor_sha256=_sha(fixture.anchor_bytes),
                candidate_publication_root=fixture.candidate,
                assessor_vault_repository=fixture.assessor,
                git_executable=self.git,
            )
            run, commit, tree, record = _build_run(
                root,
                fixture,
                stage_input,
                bad_c2_denied_probe_accounting=True,
            )
            candidate_run = authority.resolve_candidate_run_authority(
                run,
                git_executable=self.git,
                commit=commit,
                tree=tree,
                authority_file=record,
                expected_stage="development",
                stage_input=stage_input,
                execution_lock_repository=fixture.main,
            )
            repository = authority.GitObjectRepository(fixture.main, self.git)
            with self.assertRaisesRegex(
                authority.AuthorityError, "denied_probe_entry_count"
            ):
                authority._verify_c2_equivalence_evidence(
                    repository,
                    c2_source_commit=(candidate_run.candidate_execution_lock_commit),
                    stage_input=stage_input,
                    candidate_run=candidate_run,
                )

    def test_candidate_request_rejects_extra_gold_and_command_environment_drift(
        self,
    ) -> None:
        cases = (
            ({"extra_candidate_gold_grant": True}, "request semantics"),
            ({"candidate_command_drift": True}, "request semantics"),
            ({"candidate_environment_drift": True}, "request semantics"),
        )
        for options, message in cases:
            with (
                self.subTest(options=options),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                fixture = Fixture(root)
                stage_input = authority.resolve_stage_input_authority(
                    anchor_repository=fixture.main,
                    anchor_commit=fixture.anchor_commit,
                    anchor_path=fixture.anchor_path,
                    anchor_sha256=_sha(fixture.anchor_bytes),
                    candidate_publication_root=fixture.candidate,
                    assessor_vault_repository=fixture.assessor,
                    git_executable=self.git,
                )
                run, commit, tree, record = _build_run(
                    root, fixture, stage_input, **options
                )
                with self.assertRaisesRegex(authority.AuthorityError, message):
                    authority.resolve_candidate_run_authority(
                        run,
                        git_executable=self.git,
                        commit=commit,
                        tree=tree,
                        authority_file=record,
                        expected_stage="development",
                        stage_input=stage_input,
                        execution_lock_repository=fixture.main,
                    )

    def test_c2_execution_rejects_external_probe_gold_command_and_environment_drift(
        self,
    ) -> None:
        cases = (
            ({"bad_c2_external_probe": True}, "kernel access probe"),
            ({"c2_extra_gold_grant": True}, "AppContainer attestation differs"),
            ({"c2_command_drift": True}, "command/scratch boundary"),
            ({"c2_environment_drift": True}, "environment differs"),
            ({"c2_test_command_drift": True}, "isolated-test execution command"),
            ({"c2_test_grant_drift": True}, "isolated-test execution read grants"),
            ({"c2_test_probe_drift": True}, "recursive namespace probe"),
            ({"c2_test_manifest_drift": True}, "execution manifest"),
        )
        for options, message in cases:
            with (
                self.subTest(options=options),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                fixture = Fixture(root)
                stage_input = authority.resolve_stage_input_authority(
                    anchor_repository=fixture.main,
                    anchor_commit=fixture.anchor_commit,
                    anchor_path=fixture.anchor_path,
                    anchor_sha256=_sha(fixture.anchor_bytes),
                    candidate_publication_root=fixture.candidate,
                    assessor_vault_repository=fixture.assessor,
                    git_executable=self.git,
                )
                run, commit, tree, record = _build_run(
                    root, fixture, stage_input, **options
                )
                candidate_run = authority.resolve_candidate_run_authority(
                    run,
                    git_executable=self.git,
                    commit=commit,
                    tree=tree,
                    authority_file=record,
                    expected_stage="development",
                    stage_input=stage_input,
                    execution_lock_repository=fixture.main,
                )
                repository = authority.GitObjectRepository(fixture.main, self.git)
                with self.assertRaisesRegex(authority.AuthorityError, message):
                    authority._verify_c2_equivalence_evidence(
                        repository,
                        c2_source_commit=candidate_run.candidate_execution_lock_commit,
                        stage_input=stage_input,
                        candidate_run=candidate_run,
                    )

    def test_assessment_commit_and_single_child_decision_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            fixture = Fixture(temporary_root)
            stage_input = authority.resolve_stage_input_authority(
                anchor_repository=fixture.main,
                anchor_commit=fixture.anchor_commit,
                anchor_path=fixture.anchor_path,
                anchor_sha256=_sha(fixture.anchor_bytes),
                candidate_publication_root=fixture.candidate,
                assessor_vault_repository=fixture.assessor,
                git_executable=self.git,
            )
            run, run_commit, run_tree, run_file = _build_run(
                temporary_root, fixture, stage_input
            )
            candidate_run = authority.resolve_candidate_run_authority(
                run,
                git_executable=self.git,
                commit=run_commit,
                tree=run_tree,
                authority_file=run_file,
                expected_stage="development",
                stage_input=stage_input,
                execution_lock_repository=fixture.main,
            )

            def synthetic_assess(raw: Any, *_args: Any) -> dict[str, Any]:
                return {
                    "schema_version": "synthetic-assessment/v1",
                    "stage": raw["stage"],
                    "report_only_times": {
                        "process_cpu_seconds": 0,
                        "end_to_end_cpu_seconds": 0,
                        "formal_wall_seconds": None,
                        "host_exclusion_passed": False,
                    },
                }

            formal = authority.assess_with_authority(
                synthetic_assess,
                stage_input=stage_input,
                candidate_run=candidate_run,
            )
            output = temporary_root / "assessment-output"
            _init_repo(output)
            assessment_path = "assessment.json"
            authority_path = "assessor-stage-authority.json"
            _write(output, assessment_path, formal.assessment_jcs)
            _write(output, authority_path, formal.authority_jcs)
            assessment_commit, assessment_tree = _commit(output, "assessment")
            assessment_file = authority.FileRecord(
                assessment_path, _sha(formal.assessment_jcs), len(formal.assessment_jcs)
            )
            authority_file = authority.FileRecord(
                authority_path, _sha(formal.authority_jcs), len(formal.authority_jcs)
            )
            decision = _jcs(
                {
                    "schema_version": "geotarget.exp-local-003.development-decision-record/v1",
                    "experiment_id": "EXP-LOCAL-003",
                    "card_sha256": CARD,
                    "development_gate_passed": True,
                    "selected_variant": "LX-BOUNDS",
                    "selected_path": "recall",
                    "safety16_disagreement_count": 0,
                    "candidate_input_sha256": stage_input.candidate_input_sha256,
                    "development_assessment_sha256": assessment_file.sha256,
                    "decision_commit": assessment_commit,
                }
            )
            decision_path = "development-decision-record.json"
            _write(output, decision_path, decision)
            decision_commit, decision_tree = _commit(output, "decision")
            decision_file = authority.FileRecord(
                decision_path, _sha(decision), len(decision)
            )
            resolved = authority.resolve_assessor_stage_output(
                output,
                assess=synthetic_assess,
                build_development_decision=lambda *_args: json.loads(decision),
                assessment_commit=assessment_commit,
                assessment_tree=assessment_tree,
                assessment_file=assessment_file,
                authority_file=authority_file,
                stage_input=stage_input,
                candidate_run=candidate_run,
                git_executable=self.git,
                decision_commit=decision_commit,
                decision_tree=decision_tree,
                decision_file=decision_file,
            )
            self.assertEqual(resolved.decision["decision_commit"], assessment_commit)  # type: ignore[index]
            self.assertGreater(resolved.formal.end_to_end_cpu_nanoseconds, 0)
            development_anchor = {
                "schema_version": authority.DEVELOPMENT_AUTHORIZATION_SCHEMA,
                "experiment_id": "EXP-LOCAL-003",
                "card_sha256": CARD,
                "stage": "development",
                "stage_input_anchor": {
                    "commit": stage_input.anchor_commit,
                    "tree": stage_input.anchor_tree,
                    "file": {
                        "path": stage_input.anchor_file.path,
                        "sha256": stage_input.anchor_file.sha256,
                        "byte_length": stage_input.anchor_file.byte_length,
                    },
                },
                "c2_source_commit": candidate_run.candidate_execution_lock_commit,
                "candidate_evidence": {
                    "commit": run_commit,
                    "tree": run_tree,
                    "authority": {
                        "path": run_file.path,
                        "sha256": run_file.sha256,
                        "byte_length": run_file.byte_length,
                    },
                },
                "assessor_output": {
                    "assessment_commit": assessment_commit,
                    "assessment_tree": assessment_tree,
                    "assessment_file": {
                        "path": assessment_file.path,
                        "sha256": assessment_file.sha256,
                        "byte_length": assessment_file.byte_length,
                    },
                    "authority_file": {
                        "path": authority_file.path,
                        "sha256": authority_file.sha256,
                        "byte_length": authority_file.byte_length,
                    },
                    "decision_commit": decision_commit,
                    "decision_tree": decision_tree,
                    "decision_file": {
                        "path": decision_file.path,
                        "sha256": decision_file.sha256,
                        "byte_length": decision_file.byte_length,
                    },
                },
                "rerun_permitted": False,
            }
            development_anchor_path = (
                "research/experiments/EXP-LOCAL-003/"
                "C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json"
            )
            _write(fixture.main, development_anchor_path, _jcs(development_anchor))
            authorization_commit, _ = _commit(fixture.main, "C3 authorization")
            authorization = authority.resolve_development_authorization(
                fixture.main,
                fixture.assessor,
                run,
                output,
                authorization_anchor_commit=authorization_commit,
                assess=synthetic_assess,
                build_development_decision=lambda *_args: json.loads(decision),
                git_executable=self.git,
            )
            self.assertEqual(
                authorization.assessor_output.decision_commit, decision_commit
            )
            with self.assertRaisesRegex(
                authority.AuthorityError, "frozen recomputation"
            ):
                authority.resolve_assessor_stage_output(
                    output,
                    assess=lambda raw, *_args: {
                        **synthetic_assess(raw),
                        "forged": True,
                    },
                    build_development_decision=lambda *_args: json.loads(decision),
                    assessment_commit=assessment_commit,
                    assessment_tree=assessment_tree,
                    assessment_file=assessment_file,
                    authority_file=authority_file,
                    stage_input=stage_input,
                    candidate_run=candidate_run,
                    git_executable=self.git,
                    decision_commit=decision_commit,
                    decision_tree=decision_tree,
                    decision_file=decision_file,
                )

            locked_fixture = _build_locked_inputs(
                temporary_root, fixture, authorization
            )
            locked_stage_input = authority.resolve_stage_input_authority(
                anchor_repository=fixture.main,
                anchor_commit=locked_fixture.anchor_commit,
                anchor_path=locked_fixture.anchor_path,
                anchor_sha256=_sha(locked_fixture.anchor_bytes),
                candidate_publication_root=locked_fixture.candidate,
                assessor_vault_repository=locked_fixture.assessor,
                git_executable=self.git,
            )
            (
                locked_run,
                locked_run_commit,
                locked_run_tree,
                locked_run_file,
            ) = _build_run(temporary_root, locked_fixture, locked_stage_input)
            locked_candidate = authority.resolve_candidate_run_authority(
                locked_run,
                git_executable=self.git,
                commit=locked_run_commit,
                tree=locked_run_tree,
                authority_file=locked_run_file,
                expected_stage="locked",
                stage_input=locked_stage_input,
                execution_lock_repository=fixture.main,
            )
            locked_formal = authority.assess_with_authority(
                synthetic_assess,
                stage_input=locked_stage_input,
                candidate_run=locked_candidate,
            )
            locked_output = temporary_root / "locked-assessment-output"
            _init_repo(locked_output)
            locked_assessment_path = "assessment.json"
            locked_authority_path = "assessor-stage-authority.json"
            _write(
                locked_output,
                locked_assessment_path,
                locked_formal.assessment_jcs,
            )
            _write(
                locked_output,
                locked_authority_path,
                locked_formal.authority_jcs,
            )
            locked_assessment_commit, locked_assessment_tree = _commit(
                locked_output, "locked assessment"
            )
            locked_assessment_file = authority.FileRecord(
                locked_assessment_path,
                _sha(locked_formal.assessment_jcs),
                len(locked_formal.assessment_jcs),
            )
            locked_authority_file = authority.FileRecord(
                locked_authority_path,
                _sha(locked_formal.authority_jcs),
                len(locked_formal.authority_jcs),
            )
            final_document = {
                "schema_version": "geotarget.exp-local-003.final-connection/v1",
                "experiment_id": "EXP-LOCAL-003",
                "card_sha256": CARD,
                "development_assessment_sha256": assessment_file.sha256,
                "development_decision_record_sha256": decision_file.sha256,
                "locked_assessment_sha256": locked_assessment_file.sha256,
                "selected_variant": "LX-BOUNDS",
                "selected_path": "recall",
                "development_safety16_clear": False,
                "locked_stage_passed": False,
                "product_connection_allowed": False,
            }
            final_bytes = _jcs(final_document)
            final_path = "final-connection.json"
            _write(locked_output, final_path, final_bytes)
            final_commit, final_tree = _commit(locked_output, "final connection")
            final_file = authority.FileRecord(
                final_path, _sha(final_bytes), len(final_bytes)
            )
            c6_anchor = {
                "schema_version": authority.LOCKED_AUTHORIZATION_SCHEMA,
                "experiment_id": "EXP-LOCAL-003",
                "card_sha256": CARD,
                "stage": "locked",
                "development_authorization": {
                    "commit": authorization.authorization_anchor_commit,
                    "tree": authorization.authorization_anchor_tree,
                    "file": {
                        "path": authorization.authorization_anchor_file.path,
                        "sha256": authorization.authorization_anchor_file.sha256,
                        "byte_length": (
                            authorization.authorization_anchor_file.byte_length
                        ),
                    },
                },
                "locked_stage_input": {
                    "commit": locked_stage_input.anchor_commit,
                    "tree": locked_stage_input.anchor_tree,
                    "file": {
                        "path": locked_stage_input.anchor_file.path,
                        "sha256": locked_stage_input.anchor_file.sha256,
                        "byte_length": locked_stage_input.anchor_file.byte_length,
                    },
                },
                "locked_execution_lock": {
                    "commit": locked_candidate.candidate_execution_lock_commit,
                    "tree": locked_candidate.candidate_execution_lock_tree,
                    "file": {
                        "path": locked_candidate.candidate_execution_lock_file.path,
                        "sha256": (
                            locked_candidate.candidate_execution_lock_file.sha256
                        ),
                        "byte_length": (
                            locked_candidate.candidate_execution_lock_file.byte_length
                        ),
                    },
                },
                "candidate_evidence": {
                    "commit": locked_run_commit,
                    "tree": locked_run_tree,
                    "authority": {
                        "path": locked_run_file.path,
                        "sha256": locked_run_file.sha256,
                        "byte_length": locked_run_file.byte_length,
                    },
                },
                "assessor_output": {
                    "assessment_commit": locked_assessment_commit,
                    "assessment_tree": locked_assessment_tree,
                    "assessment_file": {
                        "path": locked_assessment_file.path,
                        "sha256": locked_assessment_file.sha256,
                        "byte_length": locked_assessment_file.byte_length,
                    },
                    "authority_file": {
                        "path": locked_authority_file.path,
                        "sha256": locked_authority_file.sha256,
                        "byte_length": locked_authority_file.byte_length,
                    },
                    "final_connection_commit": final_commit,
                    "final_connection_tree": final_tree,
                    "final_connection_file": {
                        "path": final_file.path,
                        "sha256": final_file.sha256,
                        "byte_length": final_file.byte_length,
                    },
                },
                "rerun_permitted": False,
            }
            c6_path = (
                "research/experiments/EXP-LOCAL-003/C6_FINAL_CONNECTION_ANCHOR.json"
            )
            _write(fixture.main, c6_path, _jcs(c6_anchor))
            c6_commit, _ = _commit(fixture.main, "C6 locked authorization")

            def synthetic_finalize(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
                return final_document

            locked_authorization = authority.resolve_locked_authorization(
                fixture.main,
                fixture.assessor,
                run,
                output,
                locked_fixture.assessor,
                locked_run,
                locked_output,
                authorization_anchor_commit=c6_commit,
                assess=synthetic_assess,
                build_development_decision=lambda *_args: json.loads(decision),
                finalize_product_connection=synthetic_finalize,
                git_executable=self.git,
            )
            self.assertFalse(locked_authorization.product_connection_allowed)
            with self.assertRaisesRegex(
                authority.AuthorityError, "frozen recomputation"
            ):
                authority.resolve_locked_authorization(
                    fixture.main,
                    fixture.assessor,
                    run,
                    output,
                    locked_fixture.assessor,
                    locked_run,
                    locked_output,
                    authorization_anchor_commit=c6_commit,
                    assess=synthetic_assess,
                    build_development_decision=lambda *_args: json.loads(decision),
                    finalize_product_connection=lambda *_args, **_kwargs: {
                        **final_document,
                        "product_connection_allowed": True,
                    },
                    git_executable=self.git,
                )
            _write(
                fixture.main,
                "research/experiments/EXP-LOCAL-003/C6_UNEXPECTED.json",
                b"{}",
            )
            _git(fixture.main, "add", "--all")
            malicious_tree = _git(fixture.main, "write-tree")
            malicious_commit = _commit_tree_object(
                fixture.main,
                malicious_tree,
                "C6 with an extra blob",
                locked_candidate.candidate_execution_lock_commit,
            )
            main_objects = authority.GitObjectRepository(fixture.main, self.git)
            with self.assertRaisesRegex(authority.AuthorityError, "changes more than"):
                authority._verify_single_blob_child(
                    main_objects,
                    parent_commit=locked_candidate.candidate_execution_lock_commit,
                    child_commit=malicious_commit,
                    added_path=c6_path,
                    added_blob=main_objects.blob_at(c6_commit, c6_path),
                    context="attacked C6",
                )

    def test_all_authority_schemas_are_closed_and_valid(self) -> None:
        names = (
            "candidate-execution-lock.schema.json",
            "c2-default-equivalence.schema.json",
            "candidate-run-attempt.schema.json",
            "candidate-output-preexit-seal.schema.json",
            "candidate-process-exit.schema.json",
            "stage-vault-anchor.schema.json",
            "candidate-run-authority.schema.json",
            "assessor-stage-authority.schema.json",
            "authority-file-manifest.schema.json",
            "development-authorization-anchor.schema.json",
            "assessment.schema.json",
            "development-decision-record.schema.json",
            "final-connection.schema.json",
            "final-connection-anchor.schema.json",
        )
        for name in names:
            with self.subTest(name=name):
                schema = json.loads((SOURCE / name).read_text("utf-8"))
                Draft202012Validator.check_schema(schema)
                self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
