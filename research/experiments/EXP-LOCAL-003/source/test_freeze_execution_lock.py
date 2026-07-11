"""Closed, non-formal tests for the EXP-LOCAL-003 execution-lock freezer."""

from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import freeze_execution_lock as freezer


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _context(stage: str = "development") -> freezer.FreezeContext:
    candidate_files = {
        "ONE_SHOT_COMPLETE.json": SimpleNamespace(sha256="3" * 64),
        "development-candidate-inputs.json.gz": SimpleNamespace(sha256="2" * 64),
        "manifest.json": SimpleNamespace(sha256="1" * 64),
        "plugin/Local3FixturePlugin.jl": SimpleNamespace(sha256="4" * 64),
    }
    stage_input = SimpleNamespace(
        stage=stage,
        anchor_commit="a" * 40,
        anchor_file=SimpleNamespace(sha256="b" * 64),
        source_lock_commit="1" * 40,
        preimplementation_lock_sha256="c" * 64,
        candidate_input_sha256="d" * 64,
        candidate_files=candidate_files,
    )
    return freezer.FreezeContext(stage, "a" * 40, mock.Mock(), stage_input)


class FreezeExecutionLockTests(unittest.TestCase):
    def test_isolated_test_execution_exact_boundary_and_tamper_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime_root = root / "runtime"
            julia_executable = runtime_root / "bin" / "julia.exe"
            depot_root = root / "depot"
            scratch = root / "workspace" / "scratch-isolated-test"
            locked_environment = {
                name: f"locked-{name}"
                for name in (
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
            request_environment = dict(locked_environment)
            request_environment.update(
                {
                    "JULIA_DEPOT_PATH": str(depot_root),
                    "JULIA_PKG_PRECOMPILE_AUTO": "0",
                    "JULIA_PROJECT": str(root / "julia"),
                }
            )
            environment = freezer._broker_environment_records(
                request_environment, scratch
            )
            grants = [
                {"path": str(runtime_root), "recursive": True},
                {"path": str(depot_root), "recursive": False},
                {"path": str(depot_root / "packages"), "recursive": True},
                {"path": str(depot_root / "artifacts"), "recursive": True},
                {"path": str(root), "recursive": False},
                {"path": str(root / "julia"), "recursive": False},
                *(
                    {
                        "path": str(root.joinpath(*path.split("/"))),
                        "recursive": False,
                    }
                    for path in freezer.ISOLATED_TEST_PROJECT_PATHS
                ),
                *(
                    {
                        "path": str(root.joinpath(*path.split("/"))),
                        "recursive": path.endswith("/src"),
                    }
                    for path in freezer.ISOLATED_TEST_PACKAGE_PATHS
                ),
                {
                    "path": str(
                        root.joinpath(*freezer.TEST_SOURCE_PATHS[0].split("/"))
                    ),
                    "recursive": False,
                },
            ]
            command = [
                str(julia_executable),
                "--startup-file=no",
                "--history-file=no",
                "--compiled-modules=no",
                "--pkgimages=no",
                f"--project={root / 'julia'}",
                str(root.joinpath(*freezer.TEST_SOURCE_PATHS[0].split("/"))),
            ]
            probe_states = (
                (command[6], "allowed", "allowed", 0),
                (
                    str(root.joinpath(*freezer.RUNTIME_SOURCE_PATHS[0].split("/"))),
                    "allowed",
                    "allowed",
                    0,
                ),
                (
                    str(root.joinpath(*freezer.EXPERIMENT_PREFIX.split("/"))),
                    "denied",
                    "denied",
                    5,
                ),
                (
                    str(root.joinpath(*freezer.DEFAULT_EQUIVALENCE_PATH.split("/"))),
                    "denied",
                    "denied",
                    5,
                ),
                (
                    str(
                        root.joinpath(
                            *freezer.authority.C1_CANDIDATE_OUTCOME_PATH.split("/")
                        )
                    ),
                    "denied",
                    "denied",
                    5,
                ),
                (
                    str(
                        root.joinpath(
                            *freezer.authority.C1_STAGE_VAULT_ANCHOR_PATH.split("/")
                        )
                    ),
                    "denied",
                    "denied",
                    5,
                ),
                (
                    str(
                        root.joinpath(
                            *freezer.authority.C1_ATTEMPT_CLAIM_PATH.split("/")
                        )
                    ),
                    "denied",
                    "denied",
                    5,
                ),
                *(
                    (str(path), "denied", "denied", 5)
                    for path in freezer.authority._c1_external_fixed_roots(root)
                ),
                (str(root / ".git"), "denied", "denied", 5),
            )
            execution = {
                "mode": "isolated-test",
                "mechanism_source_granted": True,
                "command": command,
                "environment": environment,
                "read_grants": grants,
                "return_code": 0,
                "termination_reason": "completed",
                "stdout": {"sha256": _sha(b"passed\n"), "byte_length": 7},
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
                "sandbox": {
                    "schema_version": "geotarget.exp-local-003.appcontainer-attestation/v2",
                    "claim_reference": "sha256:" + "f" * 64,
                    "profile_name": "GeoTarget.EXPLOCAL003.synthetic-isolated",
                    "package_sid": "S-1-15-2-5",
                    "profile_storage_path": str(root / "absent-profile"),
                    "capabilities": [],
                    "allowed_read_paths": [grant["path"] for grant in grants],
                    "read_identity_manifest_entry_count": 15,
                    "read_identity_manifest_sha256": "1" * 64,
                    "scratch_directory": str(scratch),
                    "environment": environment,
                    "inherited_handle_roles": ["stdin", "stdout", "stderr"],
                    "process_id": 5,
                    "token_is_appcontainer": True,
                    "token_appcontainer_sid_verified": True,
                    "token_integrity_rid": 4096,
                    "token_elevated": False,
                    "token_capability_count": 0,
                    "access_probes": [
                        {
                            "path": path,
                            "expected": expected,
                            "observed": observed,
                            "winerror": winerror,
                        }
                        for path, expected, observed, winerror in probe_states
                    ],
                    "denied_probe_entry_count": 11,
                    "denied_probe_manifest_sha256": "2" * 64,
                    "read_only_probe_entry_count": 15,
                    "read_only_probe_manifest_sha256": "3" * 64,
                    "scratch_access_probe_manifest_sha256": "4" * 64,
                    "max_processes": 1,
                    "child_process_restricted": True,
                    "job_assigned_at_creation": True,
                    "job_membership_verified": True,
                    "job_limit_flags": 0x00002008,
                    "breakaway_allowed": False,
                    "kill_on_job_close": True,
                    "job_empty": True,
                    "acl_entry_count": 16,
                    "original_acl_manifest_sha256": "5" * 64,
                    "restored_acl_manifest_sha256": "5" * 64,
                    "acl_exactly_restored": True,
                    "scratch_emptied": True,
                    "profile_deleted": True,
                    "profile_storage_deleted": True,
                },
            }
            document = {
                "claim_reference": "sha256:" + "f" * 64,
                "isolated_test_execution": execution,
                "isolated_test_execution_manifest_sha256": _sha(
                    freezer.canonical_bytes(execution)
                ),
            }
            context = _context()
            with (
                mock.patch.object(freezer, "REPOSITORY_ROOT", root),
                mock.patch.object(
                    freezer.authority,
                    "_c0_environment_authority",
                    return_value=(
                        {},
                        julia_executable,
                        runtime_root,
                        depot_root,
                        locked_environment,
                    ),
                ),
            ):
                freezer._validate_isolated_test_execution(
                    document,
                    context,
                    c0_commit="2" * 40,
                    environment_lock_sha256="0" * 64,
                    runtime_records=tuple(
                        {"path": path} for path in freezer.RUNTIME_SOURCE_PATHS
                    ),
                    test_records=tuple(
                        {"path": path} for path in freezer.TEST_SOURCE_PATHS
                    ),
                )
                cases = (
                    ("command", "command/environment/grants"),
                    ("grant", "command/environment/grants"),
                    ("probe", "recursive namespace probes"),
                    ("manifest", "manifest digest"),
                )
                for mutation, message in cases:
                    tampered = copy.deepcopy(document)
                    if mutation == "command":
                        tampered["isolated_test_execution"]["command"][2] = (
                            "--history-file=yes"
                        )
                    elif mutation == "grant":
                        tampered["isolated_test_execution"]["read_grants"][5][
                            "recursive"
                        ] = True
                    elif mutation == "probe":
                        tampered["isolated_test_execution"]["sandbox"]["access_probes"][
                            7
                        ]["path"] = str(root / "forged")
                    if mutation == "manifest":
                        tampered["isolated_test_execution_manifest_sha256"] = "9" * 64
                    else:
                        tampered["isolated_test_execution_manifest_sha256"] = _sha(
                            freezer.canonical_bytes(tampered["isolated_test_execution"])
                        )
                    with (
                        self.subTest(mutation=mutation),
                        self.assertRaisesRegex(freezer.FreezeError, message),
                    ):
                        freezer._validate_isolated_test_execution(
                            tampered,
                            context,
                            c0_commit="2" * 40,
                            environment_lock_sha256="0" * 64,
                            runtime_records=tuple(
                                {"path": path} for path in freezer.RUNTIME_SOURCE_PATHS
                            ),
                            test_records=tuple(
                                {"path": path} for path in freezer.TEST_SOURCE_PATHS
                            ),
                        )

    def test_development_evidence_is_byte_bound_before_lock_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, relative in enumerate(
                (*freezer.RUNTIME_SOURCE_PATHS, *freezer.TEST_SOURCE_PATHS), start=1
            ):
                _write(root, relative, f"source-{index}\n".encode())
            context = _context()
            local_options_sha256 = "e" * 64
            with mock.patch.object(freezer, "REPOSITORY_ROOT", root):
                runtime_records = freezer._file_records(freezer.RUNTIME_SOURCE_PATHS)
                test_records = freezer._file_records(freezer.TEST_SOURCE_PATHS)
                c0_commit = "2" * 40
                c0_tree = "3" * 40
                c0_paths = {
                    *freezer.authority.C0_EQUIVALENCE_PROTOCOL_PATHS,
                    "julia/Project.toml",
                    "julia/Manifest.toml",
                    "julia/GeoTargetBase/Project.toml",
                    "julia/GeoTargetBase/src/GeoTargetBase.jl",
                    "julia/GeoTargetCore/Project.toml",
                    "julia/GeoTargetCore/src/GeoTargetCore.jl",
                    "julia/GeoTargetGeometry/Project.toml",
                    "julia/GeoTargetGeometry/src/GeoTargetGeometry.jl",
                }
                c0_payloads = {path: f"c0:{path}\n".encode() for path in c0_paths}
                preimplementation = freezer.canonical_bytes(
                    {
                        "c0_source_commit": c0_commit,
                        "c0_source_tree": c0_tree,
                        "environment_lock_sha256": "0" * 64,
                    }
                )
                context.stage_input.preimplementation_lock_sha256 = _sha(
                    preimplementation
                )

                class Repository:
                    @staticmethod
                    def commit_tree(commit: str) -> str:
                        if commit != c0_commit:
                            raise AssertionError(commit)
                        return c0_tree

                    @staticmethod
                    def blob_at(commit: str, path: str) -> SimpleNamespace:
                        if (
                            commit == context.stage_input.source_lock_commit
                            and path == freezer.PREIMPLEMENTATION_LOCK_PATH
                        ):
                            return SimpleNamespace(
                                mode="100644", data=preimplementation
                            )
                        if commit != c0_commit or path not in c0_payloads:
                            raise AssertionError((commit, path))
                        return SimpleNamespace(mode="100644", data=c0_payloads[path])

                    @staticmethod
                    def tree_index(commit: str) -> dict[str, tuple[str, str]]:
                        if commit != c0_commit:
                            raise AssertionError(commit)
                        return {
                            path: ("100644", _sha(payload)[:40])
                            for path, payload in c0_payloads.items()
                        }

                context = freezer.FreezeContext(
                    context.stage,
                    context.head,
                    Repository(),
                    context.stage_input,
                )
                fixture_records = [
                    {
                        "path": path,
                        "sha256": _sha(c0_payloads[path]),
                        "byte_length": len(c0_payloads[path]),
                    }
                    for path in sorted(freezer.authority.C0_EQUIVALENCE_FIXTURE_PATHS)
                ]
                golden_records = [
                    {
                        "path": path,
                        "sha256": _sha(c0_payloads[path]),
                        "byte_length": len(c0_payloads[path]),
                    }
                    for path in sorted(freezer.authority.C0_EQUIVALENCE_GOLDEN_PATHS)
                ]
                protocol_records = [
                    {
                        "path": path,
                        "sha256": _sha(c0_payloads[path]),
                        "byte_length": len(c0_payloads[path]),
                    }
                    for path in sorted(freezer.authority.C0_EQUIVALENCE_PROTOCOL_PATHS)
                ]
                capsule_paths = tuple(
                    sorted(
                        path
                        for path in c0_payloads
                        if path
                        in {
                            "julia/Project.toml",
                            "julia/Manifest.toml",
                            freezer.authority.C0_EQUIVALENCE_CHILD_PATH,
                            freezer.authority.C0_EQUIVALENCE_PROTOCOL_PATHS[0],
                            *freezer.authority.C0_EQUIVALENCE_FIXTURE_PATHS,
                        }
                        or any(
                            path == f"{package}/Project.toml"
                            or path.startswith(f"{package}/src/")
                            for package in (
                                "julia/GeoTargetBase",
                                "julia/GeoTargetCore",
                                "julia/GeoTargetGeometry",
                            )
                        )
                    )
                )
                capsule_records = [
                    {
                        "path": path,
                        "sha256": _sha(c0_payloads[path]),
                        "byte_length": len(c0_payloads[path]),
                    }
                    for path in capsule_paths
                ]
                claim_reference = f"sha256:{'f' * 64}"

                def execution(
                    mode: str, golden: dict[str, object]
                ) -> dict[str, object]:
                    return {
                        "mode": mode,
                        "mechanism_source_granted": mode == "mechanism-disabled",
                        "return_code": 0,
                        "termination_reason": "completed",
                        "total_processes": 1,
                        "terminated_processes": 0,
                        "stdout": {
                            "sha256": golden["sha256"],
                            "byte_length": golden["byte_length"],
                        },
                        "sandbox": {
                            "claim_reference": claim_reference,
                            "token_is_appcontainer": True,
                            "token_appcontainer_sid_verified": True,
                            "token_capability_count": 0,
                            "max_processes": 1,
                            "job_limit_flags": 0x00002008,
                            "job_empty": True,
                            "acl_exactly_restored": True,
                            "profile_deleted": True,
                            "profile_storage_deleted": True,
                        },
                    }

                comparisons = []
                for index, fixture_id in enumerate(freezer.COMPARISON_FIXTURE_IDS):
                    golden = golden_records[index]
                    comparisons.append(
                        {
                            "fixture_id": fixture_id,
                            "fixture": fixture_records[index],
                            "golden": golden,
                            "reference_execution": execution("reference", golden),
                            "mechanism_disabled_execution": execution(
                                "mechanism-disabled", golden
                            ),
                            "golden_output_sha256": golden["sha256"],
                            "reference_output_sha256": golden["sha256"],
                            "mechanism_disabled_output_sha256": golden["sha256"],
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
                evidence = {
                    "schema_version": (
                        "geotarget.exp-local-003.c2-default-equivalence/v1"
                    ),
                    "experiment_id": freezer.EXPERIMENT_ID,
                    "card_sha256": freezer.CARD_SHA256,
                    "stage": "development",
                    "stage_input_anchor_commit": context.stage_input.anchor_commit,
                    "stage_input_anchor_sha256": context.stage_input.anchor_file.sha256,
                    "preimplementation_lock_sha256": (
                        context.stage_input.preimplementation_lock_sha256
                    ),
                    "local_options_sha256": local_options_sha256,
                    "claim_reference": claim_reference,
                    "baseline_variant": "L0-SEMANTIC",
                    "candidate_mechanism_enabled": False,
                    "runtime_sources": runtime_records,
                    "test_sources": test_records,
                    "fixture_sources": fixture_records,
                    "golden_sources": golden_records,
                    "c0_reference_authority": {
                        "source_lock_commit": context.stage_input.source_lock_commit,
                        "c0_source_commit": c0_commit,
                        "c0_source_tree": c0_tree,
                        "environment_lock_sha256": "0" * 64,
                        "capsule_origin": "immutable-main-git-c0-source-tree",
                        "capsule_files": capsule_records,
                        "capsule_manifest_sha256": _sha(
                            freezer.canonical_bytes(capsule_records)
                        ),
                        "protocol_sources": protocol_records,
                        "protocol_manifest_sha256": _sha(
                            freezer.canonical_bytes(protocol_records)
                        ),
                        "reference_child_c2_source_access": "kernel-denied",
                    },
                    "source_manifest_sha256": _sha(
                        freezer.canonical_bytes(source_manifest)
                    ),
                    "comparisons": comparisons,
                    "comparison_manifest_sha256": _sha(
                        freezer.canonical_bytes(comparisons)
                    ),
                    "isolated_test_execution": {},
                    "isolated_test_execution_manifest_sha256": _sha(
                        freezer.canonical_bytes({})
                    ),
                    "passed": True,
                }
                _write(
                    root,
                    freezer.DEFAULT_EQUIVALENCE_PATH,
                    freezer.canonical_bytes(evidence),
                )
                with (
                    mock.patch.object(freezer, "_validate_schema"),
                    mock.patch.object(
                        freezer, "_validate_isolated_test_execution"
                    ) as isolated,
                ):
                    freezer._validate_default_equivalence(
                        context,
                        local_options_sha256=local_options_sha256,
                        runtime_records=runtime_records,
                        test_records=test_records,
                    )
                isolated.assert_called_once()

                evidence["comparisons"][0]["mechanism_disabled_output_sha256"] = (
                    "9" * 64
                )
                evidence["comparison_manifest_sha256"] = _sha(
                    freezer.canonical_bytes(evidence["comparisons"])
                )
                _write(
                    root,
                    freezer.DEFAULT_EQUIVALENCE_PATH,
                    freezer.canonical_bytes(evidence),
                )
                with (
                    mock.patch.object(freezer, "_validate_schema"),
                    mock.patch.object(freezer, "_validate_isolated_test_execution"),
                    self.assertRaisesRegex(freezer.FreezeError, "disabled/L0"),
                ):
                    freezer._validate_default_equivalence(
                        context,
                        local_options_sha256=local_options_sha256,
                        runtime_records=runtime_records,
                        test_records=test_records,
                    )

    def test_lock_contains_only_runtime_sources_and_exact_candidate_files(self) -> None:
        context = _context()
        runtime_records = [
            {"path": path, "sha256": str(index) * 64, "byte_length": index}
            for index, path in enumerate(freezer.RUNTIME_SOURCE_PATHS, start=5)
        ]
        document = freezer._build_document(
            context,
            local_options_sha256="e" * 64,
            runtime_records=runtime_records,
        )
        self.assertEqual(
            [item["path"] for item in document["allowed_sources"]],
            list(freezer.RUNTIME_SOURCE_PATHS),
        )
        self.assertFalse(
            set(freezer.TEST_SOURCE_PATHS)
            & {item["path"] for item in document["allowed_sources"]}
        )
        self.assertEqual(
            [item["path"] for item in document["allowed_candidate_artifacts"]],
            [
                "candidate/ONE_SHOT_COMPLETE.json",
                "candidate/development-candidate-inputs.json.gz",
                "candidate/manifest.json",
                "candidate/plugin/Local3FixturePlugin.jl",
            ],
        )
        self.assertEqual(
            set(document),
            {
                "schema_version",
                "card_sha256",
                "stage",
                "candidate_input_sha256",
                "local_options_sha256",
                "stage_input_anchor_sha256",
                "stage_input_anchor_commit",
                "runner_source_path",
                "runner_source_sha256",
                "source_manifest_sha256",
                "allowed_sources",
                "allowed_candidate_artifacts",
            },
        )

    def test_stage_status_contract_is_exact(self) -> None:
        development_paths = freezer.DEVELOPMENT_DIRTY_PATHS | {
            freezer.DEVELOPMENT_OUTPUT_PATH
        }
        payload = b"".join(
            f"?? {path}\0".encode() for path in sorted(development_paths)
        )
        entries = freezer._status_entries(payload)
        freezer._validate_status("development", entries)
        freezer._validate_status("locked", {freezer.LOCKED_OUTPUT_PATH: "??"})
        with self.assertRaisesRegex(freezer.FreezeError, "durable lock claim"):
            freezer._validate_status("development", {**entries, "extra": "??"})
        changed = dict(entries)
        changed[next(iter(changed))] = " M"
        with self.assertRaisesRegex(freezer.FreezeError, "durable lock claim"):
            freezer._validate_status("development", changed)
        with self.assertRaisesRegex(freezer.FreezeError, "exactly its durable"):
            freezer._validate_status("locked", {"tracked": " M"})

    def test_locked_runtime_retains_exact_c2_git_blob_identity(self) -> None:
        c2_commit = "2" * 40
        development_commit = "3" * 40
        head = "4" * 40

        def file_record(path: str) -> dict[str, object]:
            return {"path": path, "sha256": "5" * 64, "byte_length": 1}

        authorization = {
            "schema_version": (
                "geotarget.exp-local-003.development-authorization-anchor/v1"
            ),
            "experiment_id": freezer.EXPERIMENT_ID,
            "card_sha256": freezer.CARD_SHA256,
            "stage": "development",
            "stage_input_anchor": {
                "commit": "6" * 40,
                "tree": "7" * 40,
                "file": file_record(freezer.DEVELOPMENT_ANCHOR_PATH),
            },
            "c2_source_commit": c2_commit,
            "candidate_evidence": {
                "commit": "8" * 40,
                "tree": "9" * 40,
                "authority": file_record("run/candidate-run-authority.json"),
            },
            "assessor_output": {
                "assessment_commit": "a" * 40,
                "assessment_tree": "b" * 40,
                "assessment_file": file_record("assessment.json"),
                "authority_file": file_record("assessor-stage-authority.json"),
                "decision_commit": "c" * 40,
                "decision_tree": "d" * 40,
                "decision_file": file_record("development-decision-record.json"),
            },
            "rerun_permitted": False,
        }
        authorization_bytes = freezer.canonical_bytes(authorization)
        runtime_payloads = {
            path: f"runtime:{path}".encode() for path in freezer.RUNTIME_SOURCE_PATHS
        }

        class Repository:
            changed_path: str | None = None

            def commit_parents(self, commit: str) -> tuple[str, ...]:
                if commit == head:
                    return (development_commit,)
                if commit == development_commit:
                    return (c2_commit,)
                raise AssertionError(commit)

            def blob_at(self, commit: str, path: str) -> SimpleNamespace:
                if commit == development_commit:
                    self.assert_authorization_path(path)
                    return SimpleNamespace(
                        data=authorization_bytes, oid="e" * 40, mode="100644"
                    )
                payload = runtime_payloads[path]
                oid = _sha(payload)[:40]
                if commit == head and path == self.changed_path:
                    oid = "f" * 40
                return SimpleNamespace(data=payload, oid=oid, mode="100644")

            @staticmethod
            def assert_authorization_path(path: str) -> None:
                if path != freezer.DEVELOPMENT_AUTHORIZATION_PATH:
                    raise AssertionError(path)

        repository = Repository()
        stage_input = SimpleNamespace(
            development_authority={
                "development_authorization_anchor_commit": development_commit,
                "development_authorization_anchor_sha256": _sha(authorization_bytes),
            }
        )
        context = freezer.FreezeContext("locked", head, repository, stage_input)
        runtime_records = [
            {
                "path": path,
                "sha256": _sha(payload),
                "byte_length": len(payload),
            }
            for path, payload in runtime_payloads.items()
        ]
        freezer._verify_locked_runtime(context, runtime_records)
        repository.changed_path = freezer.RUNTIME_SOURCE_PATHS[0]
        with self.assertRaisesRegex(freezer.FreezeError, "changed since C2"):
            freezer._verify_locked_runtime(context, runtime_records)

    def test_claimed_canonical_write_refuses_nonempty_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = "evidence/execution-lock.json"
            (root / "evidence").mkdir()
            document = {"z": 1, "a": [True, False]}
            with mock.patch.object(freezer, "REPOSITORY_ROOT", root):
                (root / "evidence" / "execution-lock.json").write_bytes(b"")
                identity = freezer._verify_empty_claim(relative)
                freezer._write_claimed(relative, document, identity)
                self.assertEqual(
                    (root / "evidence" / "execution-lock.json").read_bytes(),
                    freezer.canonical_bytes(document),
                )
                with self.assertRaisesRegex(freezer.FreezeError, "regular, empty"):
                    freezer._verify_empty_claim(relative)

    def test_replaced_empty_claim_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = "evidence/execution-lock.json"
            path = root / "evidence" / "execution-lock.json"
            path.parent.mkdir()
            path.write_bytes(b"")
            with mock.patch.object(freezer, "REPOSITORY_ROOT", root):
                identity = freezer._verify_empty_claim(relative)
                path.unlink()
                path.write_bytes(b"")
                with self.assertRaisesRegex(freezer.FreezeError, "identity changed"):
                    freezer._write_claimed(relative, {"value": 1}, identity)

    def test_helper_rejects_unclaimed_and_direct_cli_paths(self) -> None:
        with self.assertRaisesRegex(freezer.FreezeError, "prior durable claim"):
            freezer.freeze("development", claim_already_created=False)
        with self.assertRaisesRegex(freezer.FreezeError, "direct execution"):
            freezer.main()

    def test_claim_confirmation_calls_full_environment_gate_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim = root.joinpath(*freezer.DEVELOPMENT_OUTPUT_PATH.split("/"))
            claim.parent.mkdir(parents=True)
            claim.write_bytes(b"")
            events: list[str] = []

            def environment_gate() -> None:
                events.append("environment")

            def stop_after_environment() -> None:
                events.append("formal-python")
                raise freezer.FreezeError("synthetic stop")

            with (
                mock.patch.object(freezer, "REPOSITORY_ROOT", root),
                mock.patch.object(
                    freezer.environment_contract,
                    "verify_frozen_environment",
                    side_effect=environment_gate,
                ) as verify,
                mock.patch.object(
                    freezer,
                    "_verify_formal_python",
                    side_effect=stop_after_environment,
                ),
            ):
                with self.assertRaisesRegex(freezer.FreezeError, "synthetic stop"):
                    freezer.freeze("development", claim_already_created=True)
            verify.assert_called_once_with()
            self.assertEqual(events, ["environment", "formal-python"])
            self.assertEqual(claim.read_bytes(), b"")

    def test_real_schemas_are_closed_and_local_options_are_c0_bound(self) -> None:
        for name in (
            "candidate-execution-lock.schema.json",
            "c2-default-equivalence.schema.json",
        ):
            with self.subTest(name=name):
                schema = freezer._schema(name)
                self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            freezer._verify_local_options(),
            "3c3cd79f568d7ce6abd188d74269d9bf5e4e8b1daab7f1df5c5ad3f129c1df58",
        )


if __name__ == "__main__":
    unittest.main()
