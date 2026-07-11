"""Synthetic and host-reference tests for independent C2 equivalence."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import capture_c2_equivalence as capture
import generator
from geotarget import ProblemBuilder, canonical_bytes, validate_document


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _core_fixture() -> dict[str, object]:
    geometry = generator._geometry_lock()
    scalar = f"{generator.GEOMETRY_PLUGIN_ID}::scalar"
    builder = ProblemBuilder(plugins=(geometry,))
    x = builder.variable(
        "x",
        type_id=scalar,
        node_id="x_ref",
        origin=0.0,
        scale=1.0,
        lower=-2.0,
        upper=2.0,
    )
    zero = builder.literal(0.0, type_id=scalar, node_id="zero")
    relation = builder.call(
        f"{generator.GEOMETRY_PLUGIN_ID}::scalar_equality",
        x,
        zero,
        node_id="root_relation",
    )
    builder.relation(relation, scale_override=1.0)
    builder.target(x)
    problem = builder.build().to_dict()
    validate_document(problem)
    return {
        "schema_version": "geotarget.exp-local-003.c2-equivalence-fixture/v1",
        "fixture_id": "JULIA-CORE-DEFAULT",
        "registry": "geometry",
        "problem": problem,
        "start": [1.25],
    }


def _opaque_fixture() -> dict[str, object]:
    geometry = generator._geometry_lock()
    opaque = generator._local3_lock()
    scalar = f"{generator.GEOMETRY_PLUGIN_ID}::scalar"
    program_type = f"{generator.LOCAL3_PLUGIN_ID}::opaque_program"
    builder = ProblemBuilder(plugins=(geometry, opaque))
    x = builder.variable(
        "x",
        type_id=scalar,
        node_id="x_ref",
        origin=0.0,
        scale=0.75,
        lower=-1.5,
        upper=1.5,
    )

    def opaque_step(loops: int) -> dict[str, object]:
        return {"op": "opaque", "loops": loops, "mixing": 0.125, "bias": 0.03125}

    relation_program = {
        "version": 1,
        "instructions": [
            {"op": "input", "index": 0},
            opaque_step(7),
            {"op": "constant", "value": 0.5},
            opaque_step(7),
            {"op": "sub"},
        ],
    }
    target_program = {
        "version": 1,
        "instructions": [{"op": "input", "index": 0}, opaque_step(5)],
    }
    guard_program = {
        "version": 1,
        "instructions": [
            {"op": "input", "index": 0},
            {"op": "constant", "value": 2.0},
            {"op": "add"},
        ],
    }
    domain_program = {
        "version": 1,
        "instructions": [{"op": "constant", "value": 1.0}],
    }
    relation_literal = builder.literal(
        relation_program, type_id=program_type, node_id="relation_program"
    )
    relation = builder.call(
        f"{generator.LOCAL3_PLUGIN_ID}::program_relation",
        relation_literal,
        x,
        node_id="root_relation",
    )
    builder.relation(relation, scale_override=1.0)
    guard_literal = builder.literal(
        guard_program, type_id=program_type, node_id="guard_program"
    )
    guard = builder.call(
        f"{generator.LOCAL3_PLUGIN_ID}::program_guard",
        guard_literal,
        x,
        node_id="guard_margin",
    )
    builder.guard(guard, strict=True, scale_override=1.0)
    domain_literal = builder.literal(
        domain_program, type_id=program_type, node_id="domain_program"
    )
    domain = builder.call(
        f"{generator.LOCAL3_PLUGIN_ID}::program_domain",
        domain_literal,
        x,
        node_id="domain_margin",
    )
    builder.domain(domain, strict=True)
    target_literal = builder.literal(
        target_program, type_id=program_type, node_id="target_program"
    )
    target = builder.call(
        f"{generator.LOCAL3_PLUGIN_ID}::program_target",
        target_literal,
        x,
        node_id="target_value",
    )
    builder.target(target)
    problem = builder.build().to_dict()
    validate_document(problem)
    return {
        "schema_version": "geotarget.exp-local-003.c2-equivalence-fixture/v1",
        "fixture_id": "OPAQUE-PLUGIN-DEFAULT",
        "registry": "geometry+opaque",
        "problem": problem,
        "start": [-0.75],
    }


def _fake_result(
    request: capture.sandbox_broker.SandboxRequest,
    stdout: bytes,
    *,
    bad_denied_winerror: bool = False,
) -> capture.sandbox_broker.SandboxResult:
    probe_records = tuple(
        capture.sandbox_broker.AccessProbeObservation(
            path=str(probe.path),
            expected=probe.expected,
            observed=probe.expected,
            winerror=(
                (32 if bad_denied_winerror else 5)
                if probe.expected is capture.sandbox_broker.PathProbeStatus.DENIED
                else 0
            ),
        )
        for probe in request.access_probes
    )
    digest = "a" * 64
    entry_paths = {
        str(path)
        for grant in request.allowed_read
        for path in capture.sandbox_broker._expand_grant(grant)
    }
    entry_count = len(entry_paths)
    attestation = capture.sandbox_broker.SandboxAttestation(
        schema_version="geotarget.exp-local-003.appcontainer-attestation/v2",
        claim_reference=request.claim_reference,
        profile_name="GeoTarget.EXPLOCAL003.synthetic",
        package_sid="S-1-15-2-1",
        profile_storage_path=str(request.scratch_directory.parent / "profile-storage"),
        capabilities=(),
        allowed_read_paths=tuple(str(grant.path) for grant in request.allowed_read),
        read_identity_manifest_entry_count=entry_count,
        read_identity_manifest_sha256=(request.expected_read_identity_manifest_sha256),
        scratch_directory=str(request.scratch_directory),
        environment=request.environment,
        inherited_handle_roles=("stdin", "stdout", "stderr"),
        process_id=101,
        token_is_appcontainer=True,
        token_appcontainer_sid_verified=True,
        token_integrity_rid=4096,
        token_elevated=False,
        token_capability_count=0,
        access_probes=probe_records,
        denied_probe_entry_count=sum(
            probe.expected is capture.sandbox_broker.PathProbeStatus.DENIED
            for probe in request.access_probes
        ),
        denied_probe_manifest_sha256="b" * 64,
        read_only_probe_entry_count=entry_count,
        read_only_probe_manifest_sha256=digest,
        scratch_access_probe_manifest_sha256=digest,
        max_processes=1,
        child_process_restricted=True,
        job_assigned_at_creation=True,
        job_membership_verified=True,
        job_limit_flags=0x2008,
        breakaway_allowed=False,
        kill_on_job_close=True,
        job_empty=True,
        acl_entry_count=entry_count + 1,
        original_acl_manifest_sha256=digest,
        restored_acl_manifest_sha256=digest,
        acl_exactly_restored=True,
        scratch_emptied=True,
        profile_deleted=True,
        profile_storage_deleted=True,
    )
    return capture.sandbox_broker.SandboxResult(
        command=request.command,
        return_code=0,
        stdout=stdout,
        stderr=b"",
        termination_reason=capture.sandbox_broker.TerminationReason.COMPLETED,
        wall_time_ns=1,
        total_user_time_100ns=2,
        total_kernel_time_100ns=3,
        total_processes=1,
        terminated_processes=0,
        read_operation_count=4,
        write_operation_count=5,
        other_operation_count=6,
        read_transfer_count=7,
        write_transfer_count=8,
        other_transfer_count=9,
        preexit=None,
        attestation=attestation,
    )


class CaptureC2EquivalenceTests(unittest.TestCase):
    def test_c2_capture_topology_is_exactly_two_runtime_one_test_and_claim(
        self,
    ) -> None:
        self.assertEqual(
            capture.C2_RUNTIME_SOURCE_PATHS,
            (
                "julia/GeoTargetCore/src/local_model_transform.jl",
                "research/experiments/EXP-LOCAL-003/source/candidate_runner.jl",
            ),
        )
        self.assertEqual(
            capture.C2_TEST_SOURCE_PATHS,
            ("julia/GeoTargetCore/test/test_local_model_transform.jl",),
        )
        self.assertEqual(
            capture.DIRTY_PATHS,
            frozenset(
                (
                    *capture.C2_RUNTIME_SOURCE_PATHS,
                    *capture.C2_TEST_SOURCE_PATHS,
                    capture.contract.DEFAULT_EQUIVALENCE_PATH,
                )
            ),
        )
        self.assertNotIn("candidate_execution.py", "\n".join(capture.DIRTY_PATHS))

    def test_fixtures_are_exact_python_problem_builder_documents(self) -> None:
        for fixture, expected_document in zip(
            capture.FIXTURES, (_core_fixture(), _opaque_fixture()), strict=True
        ):
            with self.subTest(fixture=fixture.fixture_id):
                expected = canonical_bytes(expected_document) + b"\n"
                actual = capture._path(fixture.fixture_path).read_bytes()
                self.assertEqual(actual, expected)
                self.assertEqual(
                    validate_document(expected_document["problem"]),
                    "geotarget.problem/v1",
                )
        self.assertIn(
            "program_relation",
            capture._path(capture.FIXTURE_PATHS[1]).read_text(encoding="utf-8"),
        )

    def test_checked_in_goldens_are_fresh_reference_child_observations(self) -> None:
        julia = shutil.which("julia")
        if julia is None:
            self.skipTest("Julia is unavailable")
        child = capture._path(capture.CHILD_SOURCE_PATH)
        plugin = capture._path(capture.PLUGIN_SOURCE_PATH)
        julia_environment = dict(os.environ)
        julia_environment.update(
            {
                "JULIA_NUM_THREADS": "1",
                "JULIA_CPU_TARGET": "generic",
                "JULIA_PKG_OFFLINE": "true",
                "JULIA_PKG_PRECOMPILE_AUTO": "0",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
            }
        )
        mechanism_source = """module GeoTargetLocalModelTransform
using GeoTargetCore
const LOCAL_MODEL_TRANSFORM_API_VERSION = v\"1.0.0\"
function solve_local_variant(evaluate_fn, start, variant; kwargs...)
    variant === :L0_SEMANTIC || error(\"test mechanism variant differs\")
    return GeoTargetCore.solve_local(evaluate_fn, start; kwargs...)
end
end
"""
        with tempfile.TemporaryDirectory() as temporary:
            mechanism = Path(temporary) / "local_model_transform.jl"
            mechanism.write_text(mechanism_source, encoding="utf-8", newline="\n")
            for fixture in capture.FIXTURES:
                golden = capture._path(fixture.golden_path).read_bytes()
                for mode in ("reference", "mechanism-disabled"):
                    with self.subTest(fixture=fixture.fixture_id, mode=mode):
                        command = [
                            julia,
                            "--startup-file=no",
                            "--history-file=no",
                            "--compiled-modules=no",
                            "--pkgimages=no",
                            f"--project={capture.REPOSITORY_ROOT / 'julia'}",
                            str(child),
                            mode,
                            str(capture._path(fixture.fixture_path)),
                            str(plugin),
                        ]
                        if mode == "mechanism-disabled":
                            command.append(str(mechanism))
                        completed = subprocess.run(
                            command,
                            cwd=capture.REPOSITORY_ROOT,
                            check=False,
                            capture_output=True,
                            env=julia_environment,
                            timeout=180,
                        )
                        self.assertEqual(
                            completed.returncode, 0, completed.stderr.decode()
                        )
                        self.assertEqual(completed.stderr, b"")
                        self.assertEqual(completed.stdout, golden)

    def test_observation_parser_requires_one_jcs_line_and_accepted_validation(
        self,
    ) -> None:
        payload = capture._path(capture.GOLDEN_PATHS[0]).read_bytes()
        capture._validate_observed(payload, capture.FIXTURE_IDS[0], "synthetic")
        with self.assertRaisesRegex(capture.CaptureError, "canonical JSON line"):
            capture._validate_observed(payload + b"\n", capture.FIXTURE_IDS[0], "bad")
        with self.assertRaisesRegex(capture.CaptureError, "fixture"):
            capture._validate_observed(payload, capture.FIXTURE_IDS[1], "bad fixture")

    def test_reference_and_disabled_use_fresh_sandbox_requests_and_asymmetric_acl(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capsule_root = root / "capsule"
            fixture = capture.FIXTURES[0]
            fixture_path = capsule_root.joinpath(*fixture.fixture_path.split("/"))
            fixture_path.parent.mkdir(parents=True)
            fixture_path.write_bytes(capture._path(fixture.fixture_path).read_bytes())
            golden_path = root.joinpath(*fixture.golden_path.split("/"))
            golden_path.parent.mkdir(parents=True)
            golden = capture._path(fixture.golden_path).read_bytes()
            golden_path.write_bytes(golden)
            mechanism = root.joinpath(*capture.MECHANISM_SOURCE_PATH.split("/"))
            mechanism.parent.mkdir(parents=True)
            mechanism.write_bytes(b"module GeoTargetLocalModelTransform end\n")
            executable = root / "runtime" / "bin" / "julia.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"runtime")
            depot = root / "depot"
            depot.mkdir()
            environment = tuple((f"KEY_{index}", str(index)) for index in range(11))
            runtime = capture.RuntimeAuthority(
                executable,
                executable.parent.parent,
                depot,
                environment,
                (capture.sandbox_broker.ReadGrant(depot, recursive=False),),
            )
            capsule = capture.CapsuleAuthority(capsule_root, (), "a" * 64)
            requests: list[capture.sandbox_broker.SandboxRequest] = []

            def run(request: capture.sandbox_broker.SandboxRequest):
                requests.append(request)
                return _fake_result(request, golden)

            with (
                mock.patch.object(capture, "REPOSITORY_ROOT", root),
                mock.patch.object(
                    capture.sandbox_broker, "run_sandboxed", side_effect=run
                ),
            ):
                expected_external_roots = capture._c1_external_denied_roots()
                reference = capture._run_observation(
                    runtime,
                    capsule,
                    fixture,
                    "reference",
                    root / "scratch-reference",
                    "sha256:" + "b" * 64,
                )
                disabled = capture._run_observation(
                    runtime,
                    capsule,
                    fixture,
                    "mechanism-disabled",
                    root / "scratch-disabled",
                    "sha256:" + "b" * 64,
                )
                comparison = capture._comparison(fixture, reference, disabled)

            self.assertEqual(len(requests), 2)
            self.assertNotEqual(
                requests[0].scratch_directory, requests[1].scratch_directory
            )
            self.assertNotIn(str(mechanism), requests[0].command)
            self.assertIn(str(mechanism), requests[1].command)
            self.assertFalse(
                any(grant.path == mechanism for grant in requests[0].allowed_read)
            )
            self.assertTrue(
                any(grant.path == mechanism for grant in requests[1].allowed_read)
            )
            self.assertEqual(requests[0].access_probes[2].expected.value, "denied")
            self.assertEqual(requests[1].access_probes[2].expected.value, "allowed")
            for request in requests:
                self.assertEqual(
                    [probe.expected.value for probe in request.access_probes[3:]],
                    ["denied"] * 11,
                )
                self.assertEqual(
                    [probe.path for probe in request.access_probes[3:]],
                    [
                        capture.EXPERIMENT_ROOT,
                        root.joinpath(
                            *capture.contract.DEFAULT_EQUIVALENCE_PATH.split("/")
                        ),
                        root.joinpath(*capture.C1_CANDIDATE_OUTCOME_PATH.split("/")),
                        root.joinpath(*capture.C1_STAGE_VAULT_ANCHOR_PATH.split("/")),
                        root.joinpath(*capture.C1_ATTEMPT_CLAIM_PATH.split("/")),
                        *expected_external_roots,
                        root / ".git",
                    ],
                )
            self.assertTrue(comparison["byte_identical"])

            def bad_run(request: capture.sandbox_broker.SandboxRequest):
                return _fake_result(request, golden, bad_denied_winerror=True)

            with (
                mock.patch.object(capture, "REPOSITORY_ROOT", root),
                mock.patch.object(
                    capture.sandbox_broker,
                    "run_sandboxed",
                    side_effect=bad_run,
                ),
                self.assertRaisesRegex(capture.CaptureError, "ACL probes differ"),
            ):
                capture._run_observation(
                    runtime,
                    capsule,
                    fixture,
                    "reference",
                    root / "scratch-bad-winerror",
                    "sha256:" + "b" * 64,
                )

    def test_future_julia_test_uses_exact_fifth_appcontainer_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "solver"
            root.mkdir()
            executable = root / "runtime" / "bin" / "julia.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"runtime")
            depot = root / "depot"
            (depot / "packages").mkdir(parents=True)
            (depot / "artifacts").mkdir()
            for relative in capture.TEST_PROJECT_GRANT_PATHS:
                path = root.joinpath(*relative.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"project")
            for relative in capture.TEST_PACKAGE_GRANT_PATHS:
                path = root.joinpath(*relative.split("/"))
                if relative.endswith("/src"):
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"package")
            mechanism = root.joinpath(*capture.MECHANISM_SOURCE_PATH.split("/"))
            mechanism.write_bytes(b"module GeoTargetLocalModelTransform end\n")
            test_source = root.joinpath(*capture.C2_TEST_SOURCE_PATHS[0].split("/"))
            test_source.parent.mkdir(parents=True, exist_ok=True)
            test_source.write_bytes(b"using Test\n@test true\n")
            environment = tuple((f"KEY_{index}", str(index)) for index in range(11))
            runtime = capture.RuntimeAuthority(
                executable,
                executable.parent.parent,
                depot,
                environment,
                (
                    capture.sandbox_broker.ReadGrant(depot, recursive=False),
                    capture.sandbox_broker.ReadGrant(
                        depot / "packages", recursive=True
                    ),
                    capture.sandbox_broker.ReadGrant(
                        depot / "artifacts", recursive=True
                    ),
                ),
            )
            requests: list[capture.sandbox_broker.SandboxRequest] = []

            def run(request: capture.sandbox_broker.SandboxRequest):
                requests.append(request)
                capture.sandbox_broker._validate_request(request)
                return _fake_result(request, b"Test Summary: | Pass  Total\n")

            def identity(**kwargs: object):
                allowed = kwargs["allowed_read"]
                entry_count = len(
                    {
                        str(path)
                        for grant in allowed
                        for path in capture.sandbox_broker._expand_grant(grant)
                    }
                )
                return capture.sandbox_broker.ReadIdentityManifest(
                    "geotarget.exp-local-003.read-identity/v1",
                    entry_count,
                    "c" * 64,
                )

            experiment_root = root / "research" / "experiments" / "EXP-LOCAL-003"
            with (
                mock.patch.object(capture, "REPOSITORY_ROOT", root),
                mock.patch.object(capture, "EXPERIMENT_ROOT", experiment_root),
                mock.patch.object(
                    capture.sandbox_broker,
                    "capture_read_identity_manifest",
                    side_effect=identity,
                ),
                mock.patch.object(
                    capture.sandbox_broker, "run_sandboxed", side_effect=run
                ),
            ):
                expected_external = capture._c1_external_denied_roots()
                experiment_root.mkdir(parents=True, exist_ok=True)
                for relative in (
                    capture.contract.DEFAULT_EQUIVALENCE_PATH,
                    capture.C1_STAGE_VAULT_ANCHOR_PATH,
                    capture.C1_ATTEMPT_CLAIM_PATH,
                ):
                    path = root.joinpath(*relative.split("/"))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"probe")
                root.joinpath(*capture.C1_CANDIDATE_OUTCOME_PATH.split("/")).mkdir(
                    parents=True, exist_ok=True
                )
                for path in expected_external:
                    path.mkdir(parents=True, exist_ok=True)
                (root / ".git").mkdir()
                (parent / "sandbox-work").mkdir()
                observation = capture._run_isolated_test(
                    runtime,
                    parent / "sandbox-work" / "scratch-isolated-test",
                    "sha256:" + "d" * 64,
                )
            self.assertEqual(len(requests), 1)
            request = requests[0]
            self.assertEqual(
                request.command,
                (
                    str(executable),
                    "--startup-file=no",
                    "--history-file=no",
                    "--compiled-modules=no",
                    "--pkgimages=no",
                    f"--project={root / 'julia'}",
                    str(test_source),
                ),
            )
            self.assertEqual(len(request.allowed_read), 15)
            self.assertEqual(
                [grant.recursive for grant in request.allowed_read],
                [
                    True,
                    False,
                    True,
                    True,
                    False,
                    False,
                    False,
                    False,
                    False,
                    True,
                    False,
                    True,
                    False,
                    True,
                    False,
                ],
            )
            self.assertEqual(
                [probe.path for probe in request.access_probes],
                [
                    test_source,
                    mechanism,
                    experiment_root,
                    root.joinpath(
                        *capture.contract.DEFAULT_EQUIVALENCE_PATH.split("/")
                    ),
                    root.joinpath(*capture.C1_CANDIDATE_OUTCOME_PATH.split("/")),
                    root.joinpath(*capture.C1_STAGE_VAULT_ANCHOR_PATH.split("/")),
                    root.joinpath(*capture.C1_ATTEMPT_CLAIM_PATH.split("/")),
                    *expected_external,
                    root / ".git",
                ],
            )
            self.assertEqual(
                [probe.expected.value for probe in request.access_probes],
                ["allowed", "allowed", *("denied" for _ in range(11))],
            )
            record = capture._isolated_test_execution_record(observation)
            self.assertEqual(record["mode"], "isolated-test")
            self.assertEqual(record["total_processes"], 1)
            self.assertEqual(record["read_grants"][14]["path"], str(test_source))

    def test_c0_observer_rejects_any_reference_disabled_or_golden_difference(
        self,
    ) -> None:
        fixture = capture.FIXTURES[0]
        golden = capture._path(fixture.golden_path).read_bytes()
        request = SimpleNamespace()
        good = SimpleNamespace(stdout=golden)
        reference = SimpleNamespace(fixture=fixture, mode="reference", result=good)
        disabled = SimpleNamespace(
            fixture=fixture,
            mode="mechanism-disabled",
            result=SimpleNamespace(stdout=golden + b" "),
        )
        with self.assertRaisesRegex(capture.CaptureError, "disabled mechanism"):
            capture._comparison(fixture, reference, disabled)
        del request

    def test_evidence_schema_binds_independent_execution_and_has_no_candidate_input(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "runtime" / "bin" / "julia.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"runtime")
            depot = root / "depot"
            depot.mkdir()
            capsule_root = root / "capsule"
            capsule_root.mkdir()
            environment = tuple((f"KEY_{index}", str(index)) for index in range(11))
            runtime = capture.RuntimeAuthority(
                executable,
                executable.parent.parent,
                depot,
                environment,
                (capture.sandbox_broker.ReadGrant(depot, recursive=False),),
            )
            comparisons = []
            for index, fixture in enumerate(capture.FIXTURES):
                fixture_path = root.joinpath(*fixture.fixture_path.split("/"))
                fixture_path.parent.mkdir(parents=True, exist_ok=True)
                fixture_path.write_bytes(
                    capture._path(fixture.fixture_path).read_bytes()
                )
                capsule_fixture = capsule_root.joinpath(
                    *fixture.fixture_path.split("/")
                )
                capsule_fixture.parent.mkdir(parents=True, exist_ok=True)
                capsule_fixture.write_bytes(fixture_path.read_bytes())
                golden_path = root.joinpath(*fixture.golden_path.split("/"))
                golden_path.parent.mkdir(parents=True, exist_ok=True)
                golden_path.write_bytes(capture._path(fixture.golden_path).read_bytes())
                mechanism = root.joinpath(*capture.MECHANISM_SOURCE_PATH.split("/"))
                mechanism.parent.mkdir(parents=True, exist_ok=True)
                mechanism.write_bytes(b"mechanism")

                def run(request: capture.sandbox_broker.SandboxRequest):
                    return _fake_result(request, golden_path.read_bytes())

                with (
                    mock.patch.object(capture, "REPOSITORY_ROOT", root),
                    mock.patch.object(
                        capture.sandbox_broker, "run_sandboxed", side_effect=run
                    ),
                ):
                    reference = capture._run_observation(
                        runtime,
                        capture.CapsuleAuthority(capsule_root, (), "a" * 64),
                        fixture,
                        "reference",
                        root / f"scratch-{index}-reference",
                        "sha256:" + "b" * 64,
                    )
                    disabled = capture._run_observation(
                        runtime,
                        capture.CapsuleAuthority(capsule_root, (), "a" * 64),
                        fixture,
                        "mechanism-disabled",
                        root / f"scratch-{index}-disabled",
                        "sha256:" + "b" * 64,
                    )
                    comparisons.append(
                        capture._comparison(fixture, reference, disabled)
                    )

            def records(paths: tuple[str, ...], offset: int = 0):
                return [
                    {
                        "path": path,
                        "sha256": f"{index + offset:x}" * 64,
                        "byte_length": 1,
                    }
                    for index, path in enumerate(paths, start=1)
                ]

            capsule_files = tuple(
                {
                    "path": f"capsule/file-{index}",
                    "sha256": f"{index:x}" * 64,
                    "byte_length": 1,
                }
                for index in range(1, 11)
            )
            protocol_paths = tuple(f"protocol/file-{index}" for index in range(8))
            binding = SimpleNamespace(
                anchor_commit="a" * 40,
                anchor_file=SimpleNamespace(sha256="b" * 64),
                preimplementation_lock_sha256="c" * 64,
                source_lock_commit="2" * 40,
                c0_source_commit="d" * 40,
                c0_source_tree="e" * 40,
                environment_lock_sha256="3" * 64,
            )
            grant_paths = tuple(root / f"isolated-grant-{index}" for index in range(15))
            for path in grant_paths:
                path.write_bytes(b"grant")
            isolated_request = capture.sandbox_broker.SandboxRequest(
                command=tuple(f"command-{index}" for index in range(7)),
                allowed_read=tuple(
                    capture.sandbox_broker.ReadGrant(path, recursive=False)
                    for path in grant_paths
                ),
                scratch_directory=root / "scratch-isolated-test",
                claim_reference="sha256:" + "f" * 64,
                expected_read_identity_manifest_sha256="c" * 64,
                environment=environment,
                access_probes=tuple(
                    capture.sandbox_broker.AccessProbe(
                        root / f"denied-{index}",
                        capture.sandbox_broker.PathProbeStatus.DENIED,
                    )
                    for index in range(13)
                ),
            )
            isolated_execution = capture._isolated_test_execution_record(
                capture.IsolatedTestObservation(
                    isolated_request,
                    _fake_result(isolated_request, b"isolated test passed\n"),
                )
            )
            with mock.patch.object(capture, "REPOSITORY_ROOT", root):
                evidence = capture._build_evidence(
                    binding,
                    claim_reference="sha256:" + "f" * 64,
                    local_options_sha256="1" * 64,
                    runtime_records=records(
                        tuple(sorted(capture.C2_RUNTIME_SOURCE_PATHS))
                    ),
                    test_records=records(
                        tuple(sorted(capture.C2_TEST_SOURCE_PATHS)), 3
                    ),
                    fixture_records=[item["fixture"] for item in comparisons],
                    golden_records=[item["golden"] for item in comparisons],
                    protocol_records=records(protocol_paths, 5),
                    capsule=capture.CapsuleAuthority(
                        capsule_root,
                        capsule_files,
                        _sha(canonical_bytes(list(capsule_files))),
                    ),
                    comparisons=comparisons,
                    isolated_test_execution=isolated_execution,
                )
            self.assertNotIn("candidate_input_sha256", evidence)
            self.assertEqual(len(evidence["comparisons"]), 2)
            self.assertEqual(
                evidence["isolated_test_execution_manifest_sha256"],
                _sha(canonical_bytes(isolated_execution)),
            )
            self.assertEqual(
                evidence["c0_reference_authority"]["reference_child_c2_source_access"],
                "kernel-denied",
            )

    def test_c1_repository_state_requires_exact_four_untracked_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            head = "a" * 40
            status = b"".join(
                f"?? {path}\0".encode() for path in sorted(capture.DIRTY_PATHS)
            )

            def git_text(_git: object, *arguments: str) -> str:
                if arguments == ("rev-parse", "--show-toplevel"):
                    return str(root)
                if arguments == ("branch", "--show-current"):
                    return "main"
                if arguments == ("rev-parse", "HEAD"):
                    return head
                raise AssertionError(arguments)

            repository = SimpleNamespace(tree_index=lambda _head: {})
            with (
                mock.patch.object(capture, "REPOSITORY_ROOT", root),
                mock.patch.object(capture.contract, "_git_text", side_effect=git_text),
                mock.patch.object(capture.contract, "_git_bytes", return_value=status),
            ):
                capture._validate_repository_state(mock.Mock(), repository, head)
                with (
                    mock.patch.object(
                        capture.contract,
                        "_git_bytes",
                        return_value=status + b"?? unexpected\0",
                    ),
                    self.assertRaisesRegex(capture.CaptureError, "exactly runtime2"),
                ):
                    capture._validate_repository_state(mock.Mock(), repository, head)

    def test_result_blind_resolver_never_calls_outcome_context_resolver(self) -> None:
        head = "a" * 40
        anchor = SimpleNamespace(data=b"anchor")
        repository = SimpleNamespace(blob_at=lambda commit, path: anchor)
        expected = object()
        with (
            mock.patch.object(
                capture.contract.authority,
                "resolve_result_blind_stage_binding",
                return_value=expected,
            ) as blind,
            mock.patch.object(capture.contract, "_resolve_context") as outcome,
        ):
            observed = capture._result_blind_binding(mock.Mock(), repository, head)
        self.assertIs(observed, expected)
        outcome.assert_not_called()
        self.assertEqual(blind.call_args.kwargs["anchor_commit"], head)
        self.assertEqual(
            blind.call_args.kwargs["anchor_path"],
            capture.contract.DEVELOPMENT_ANCHOR_PATH,
        )

    def test_claim_and_full_environment_gate_precede_other_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim = root.joinpath(*capture.contract.DEFAULT_EQUIVALENCE_PATH.split("/"))
            claim.parent.mkdir(parents=True)
            claim.write_bytes(b"")
            events: list[str] = []

            def environment_gate() -> None:
                events.append("environment")

            def stop() -> None:
                events.append("launcher-context")
                raise capture.CaptureError("synthetic stop")

            with (
                mock.patch.object(capture, "REPOSITORY_ROOT", root),
                mock.patch.object(capture.contract, "REPOSITORY_ROOT", root),
                mock.patch.object(
                    capture.contract.environment_contract,
                    "verify_frozen_environment",
                    side_effect=environment_gate,
                ) as verify,
                mock.patch.object(
                    capture, "_verify_launcher_context", side_effect=stop
                ),
            ):
                with self.assertRaisesRegex(capture.CaptureError, "synthetic stop"):
                    capture.capture(claim_already_created=True)
            verify.assert_called_once_with()
            self.assertEqual(events, ["environment", "launcher-context"])
            self.assertEqual(claim.read_bytes(), b"")

    def test_direct_and_unclaimed_helper_calls_are_forbidden(self) -> None:
        with self.assertRaisesRegex(capture.CaptureError, "prior durable claim"):
            capture.capture(claim_already_created=False)
        with self.assertRaisesRegex(capture.CaptureError, "direct execution"):
            capture.main()


if __name__ == "__main__":
    unittest.main()
