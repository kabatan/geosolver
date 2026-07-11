from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SOURCE_ROOT = Path(__file__).resolve().parent
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import authority  # noqa: E402
import candidate_observer  # noqa: E402
import launch_candidate  # noqa: E402
import sandbox_broker  # noqa: E402


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _external(path: str, seed: str) -> dict[str, object]:
    payload = f"authority:{seed}:{path}".encode()
    return {
        "commit": seed * 40,
        "tree": chr(ord(seed) + 1) * 40,
        "file": {"path": path, "sha256": _sha(payload), "byte_length": len(payload)},
    }


class CandidateObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        git = Path(shutil.which("git") or "")
        if not git.is_absolute():
            raise unittest.SkipTest("Git is unavailable")
        cls.git = authority.pin_git_executable(git, _sha(git.read_bytes()))

    def _fixture(
        self, root: Path
    ) -> tuple[object, object, candidate_observer.RunContext]:
        evidence_root = root / "run-evidence"
        evidence_root.mkdir()
        assessment_root = root / "assessment-evidence"
        assessment_root.mkdir()
        paths = launch_candidate.EvidencePaths.fixed("development", root=evidence_root)
        paths.scratch_root.mkdir()
        claim = launch_candidate._claim("development", paths)
        probe_root = root / "probes"
        probe_root.mkdir()
        allowed = probe_root / "candidate.json"
        assessor = probe_root / "assessor-vault"
        private = probe_root / "private-vault"
        main_denied = probe_root / "main-c0.json"
        git_denied = root / ".git"
        for path in (allowed, main_denied):
            path.write_bytes(path.name.encode())
        assessor.mkdir()
        private.mkdir()
        git_denied.mkdir()
        request = sandbox_broker.SandboxRequest(
            command=(
                str(root / "julia" / "bin" / "julia.exe"),
                "--startup-file=no",
                "--history-file=no",
                "--compiled-modules=no",
                "--pkgimages=no",
                f"--project={root / 'julia'}",
                str(root / "candidate_runner.jl"),
                "--formal-appcontainer-child",
                "development",
                str(root / "candidate"),
                str(paths.scratch_directory),
            ),
            allowed_read=(sandbox_broker.ReadGrant(allowed),),
            scratch_directory=paths.scratch_directory,
            claim_reference=claim.sha256,
            expected_read_identity_manifest_sha256="b" * 64,
            timeout_seconds=candidate_observer.CANDIDATE_TIMEOUT_SECONDS,
            stdout_limit_bytes=candidate_observer.STDOUT_LIMIT_BYTES,
            stderr_limit_bytes=candidate_observer.STDERR_LIMIT_BYTES,
            preexit_payload_limit_bytes=candidate_observer.STDOUT_LIMIT_BYTES - 8,
            max_processes=candidate_observer.MAX_PROCESSES,
            environment=(
                (
                    "GEOTARGET_C0_PREEXIT_PROTOCOL",
                    "u64be-frame-flush-close-stdout-crt-close-fd1-yield-read-ack/v3",
                ),
                ("SystemRoot", r"C:\Windows"),
            ),
            access_probes=(
                sandbox_broker.AccessProbe(
                    allowed, sandbox_broker.PathProbeStatus.ALLOWED
                ),
                sandbox_broker.AccessProbe(
                    main_denied, sandbox_broker.PathProbeStatus.DENIED
                ),
                sandbox_broker.AccessProbe(
                    assessor, sandbox_broker.PathProbeStatus.DENIED
                ),
                sandbox_broker.AccessProbe(
                    private, sandbox_broker.PathProbeStatus.DENIED
                ),
                sandbox_broker.AccessProbe(
                    paths.root, sandbox_broker.PathProbeStatus.DENIED
                ),
                sandbox_broker.AccessProbe(
                    paths.staging_repository,
                    sandbox_broker.PathProbeStatus.DENIED,
                ),
                sandbox_broker.AccessProbe(
                    paths.attempt_marker,
                    sandbox_broker.PathProbeStatus.DENIED,
                ),
                sandbox_broker.AccessProbe(
                    assessment_root,
                    sandbox_broker.PathProbeStatus.DENIED,
                ),
                sandbox_broker.AccessProbe(
                    git_denied,
                    sandbox_broker.PathProbeStatus.DENIED,
                ),
            ),
        )
        context = candidate_observer.RunContext(
            stage="development",
            git_executable=self.git,
            head_commit="a" * 40,
            head_tree="b" * 40,
            stage_input_anchor=_external(
                "research/experiments/EXP-LOCAL-003/C1_STAGE_VAULT_ANCHOR.json", "1"
            ),
            execution_lock=_external(
                "research/experiments/EXP-LOCAL-003/candidate-execution-lock.json", "3"
            ),
            candidate_input_sha256="4" * 64,
            candidate_publication_tree_sha256="5" * 64,
            observer_authority=_external(candidate_observer.OBSERVER_PATH, "6"),
            launcher_authority=_external(candidate_observer.LAUNCHER_PATH, "7"),
            broker_authority=_external(candidate_observer.BROKER_PATH, "8"),
            sandbox_request=request,
            sandbox_request_document=candidate_observer._sandbox_request_document(
                request
            ),
            source_records=(
                {
                    "path": candidate_observer.TRANSFORM_PATH,
                    "sha256": "9" * 64,
                },
                {"path": candidate_observer.RUNNER_PATH, "sha256": "a" * 64},
            ),
            artifact_records=({"path": "candidate/input.json.gz", "sha256": "c" * 64},),
            immutable_files=(),
            environment_lock_sha256="d" * 64,
        )
        return paths, claim, context

    def test_runtime_request_uses_root_project_and_exact_package_grants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "solver"
            root.mkdir()
            runtime_root = root / "runtime"
            executable = runtime_root / "bin" / "julia.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"julia")
            depot = root / "depot"
            for name in ("packages", "artifacts"):
                (depot / name).mkdir(parents=True)
            project_root = root / "julia"
            for relative in ("Project.toml", "Manifest.toml"):
                path = project_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative, encoding="utf-8")
            for package in ("GeoTargetBase", "GeoTargetCore", "GeoTargetGeometry"):
                project = project_root / package / "Project.toml"
                source = project_root / package / "src" / f"{package}.jl"
                project.parent.mkdir(parents=True)
                source.parent.mkdir(parents=True)
                project.write_text(package, encoding="utf-8")
                source.write_text(f"module {package}\nend\n", encoding="utf-8")
            benchmarks = project_root / "GeoTargetBenchmarks" / "src"
            benchmarks.mkdir(parents=True)
            (benchmarks / "forbidden.jl").write_text("secret", encoding="utf-8")
            runner = root.joinpath(*candidate_observer.RUNNER_PATH.split("/"))
            runner.parent.mkdir(parents=True)
            runner.write_text("# runner", encoding="utf-8")
            observer = root.joinpath(*candidate_observer.OBSERVER_PATH.split("/"))
            observer.parent.mkdir(parents=True, exist_ok=True)
            observer.write_text("# observer", encoding="utf-8")
            candidate_root = (
                root
                / "research"
                / "experiments"
                / candidate_observer.EXPERIMENT_ID
                / "development-candidate-inputs"
            )
            plugin = candidate_root / "plugin" / "Local3FixturePlugin.jl"
            candidate_input = candidate_root / "development-candidate-inputs.json.gz"
            plugin.parent.mkdir(parents=True)
            plugin.write_text("module Local3FixturePlugin\nend\n", encoding="utf-8")
            candidate_input.write_bytes(b"deterministic-gzip")
            for suffix, leaf in (
                ("vault", "development-assessor-vault"),
                ("private-audit", "development-generator-private-vault"),
            ):
                manifest = (
                    root.with_name(f"{root.name}-{suffix}")
                    / candidate_observer.EXPERIMENT_ID
                    / leaf
                    / "manifest.json"
                )
                manifest.parent.mkdir(parents=True)
                manifest.write_text("{}", encoding="utf-8")
            assessment_root = (
                root.with_name(f"{root.name}-assessment-evidence")
                / candidate_observer.EXPERIMENT_ID
            )
            assessment_root.mkdir(parents=True)
            (root / ".git").mkdir()
            paths = SimpleNamespace(
                root=root.with_name(f"{root.name}-run-evidence")
                / candidate_observer.EXPERIMENT_ID,
                staging_repository=root / "candidate-staging",
                attempt_marker=root / "candidate.attempt",
                scratch_directory=root / "candidate-scratch",
            )
            environment_lock = {
                "julia": {
                    "runtime_executable": str(executable),
                    "runtime_tree": {"root": str(runtime_root)},
                    "depot_tree": {"root": str(depot)},
                },
                "execution": {
                    "python": {
                        "host_environment": {
                            "SystemRoot": r"C:\Windows",
                            "WINDIR": r"C:\Windows",
                        }
                    }
                },
            }
            artifacts = (
                {"path": "candidate/plugin/Local3FixturePlugin.jl", "sha256": "1" * 64},
                {
                    "path": "candidate/development-candidate-inputs.json.gz",
                    "sha256": "2" * 64,
                },
            )
            with (
                mock.patch.object(candidate_observer, "REPOSITORY_ROOT", root),
                mock.patch.object(
                    candidate_observer, "ASSESSMENT_EVIDENCE_ROOT", assessment_root
                ),
            ):
                request = candidate_observer._build_runtime_request(
                    "development",
                    paths,
                    SimpleNamespace(sha256="3" * 64),
                    environment_lock,
                    {"lock": True},
                    candidate_root,
                    artifacts,
                )
            self.assertEqual(request.command[5], f"--project={project_root}")
            self.assertEqual(
                dict(request.environment)["JULIA_LOAD_PATH"],
                os.pathsep.join(("@", "@stdlib")),
            )
            grants = {(grant.path, grant.recursive) for grant in request.allowed_read}
            self.assertIn((candidate_root, True), grants)
            self.assertIn((root, False), grants)
            self.assertIn((project_root, False), grants)
            for package in ("GeoTargetBase", "GeoTargetCore", "GeoTargetGeometry"):
                self.assertIn((project_root / package / "src", True), grants)
                self.assertIn((project_root / package / "Project.toml", False), grants)
                self.assertNotIn((project_root / package, False), grants)
            self.assertIn((project_root / "Project.toml", False), grants)
            self.assertIn((project_root / "Manifest.toml", False), grants)
            self.assertFalse(
                any("GeoTargetBenchmarks" in str(path) for path, _ in grants)
            )
            self.assertEqual(request.access_probes[-1].path, root / ".git")

    def test_bounded_git_timeout_fails_as_observer_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            deadline_ns = time.perf_counter_ns() + 10_000_000_000
            timeout = subprocess.TimeoutExpired(["git", "write-tree"], 1.0)
            with (
                mock.patch.object(
                    candidate_observer.subprocess,
                    "run",
                    side_effect=timeout,
                ),
                self.assertRaisesRegex(
                    candidate_observer.CandidateObservationError,
                    "deadline elapsed while pinned Git was running",
                ),
            ):
                candidate_observer._run_git(
                    self.git,
                    Path(temporary),
                    "write-tree",
                    deadline_ns=deadline_ns,
                )

    def test_evidence_append_bounds_every_git_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "evidence"
            vault = candidate_observer._EvidenceGit(root, self.git)
            real_run = subprocess.run
            observed_timeouts: list[float | None] = []

            def recording_run(*args: object, **kwargs: object) -> object:
                timeout = kwargs.get("timeout")
                observed_timeouts.append(
                    timeout if isinstance(timeout, float) else None
                )
                return real_run(*args, **kwargs)  # type: ignore[arg-type]

            with mock.patch.object(
                candidate_observer.subprocess,
                "run",
                side_effect=recording_run,
            ):
                vault.append(
                    "bounded attempt",
                    {candidate_observer.ATTEMPT_PATH: b"bounded"},
                    deadline_ns=time.perf_counter_ns() + 30_000_000_000,
                )
            self.assertGreaterEqual(len(observed_timeouts), 7)
            self.assertTrue(
                all(value is not None and value > 0 for value in observed_timeouts)
            )

    def _result(
        self,
        context: candidate_observer.RunContext,
        callback: object,
        *,
        bad_denied_winerror: bool = False,
        observer_elapsed_ns: int = 123,
    ) -> sandbox_broker.SandboxResult:
        payload = b'{"synthetic":"candidate-output"}'
        preexit_context = sandbox_broker.PreexitContext(
            process_id=4321,
            active_processes=1,
            root_process_still_active=True,
            payload_sha256=_sha(payload),
            payload_byte_length=len(payload),
            observer_elapsed_ns=observer_elapsed_ns,
        )
        acknowledgement = callback(payload, preexit_context)  # type: ignore[operator]
        receipt = sandbox_broker.PreexitReceipt(
            payload_sha256=_sha(payload),
            payload_byte_length=len(payload),
            ack_sha256=_sha(acknowledgement),
            ack_byte_length=len(acknowledgement),
            active_processes_before_callback=1,
            root_active_before_callback=True,
            active_processes_before_ack=1,
            root_active_before_ack=True,
            callback_completed=True,
            ack_released=True,
        )
        observations = tuple(
            sandbox_broker.AccessProbeObservation(
                path=str(Path(os.path.abspath(probe.path))),
                expected=probe.expected,
                observed=probe.expected,
                winerror=(
                    (0 if bad_denied_winerror else 5)
                    if probe.expected is sandbox_broker.PathProbeStatus.DENIED
                    else 0
                ),
            )
            for probe in context.sandbox_request.access_probes
        )
        attestation = sandbox_broker.SandboxAttestation(
            schema_version="geotarget.exp-local-003.appcontainer-attestation/v2",
            claim_reference=context.sandbox_request.claim_reference,
            profile_name="GeoTarget.EXPLOCAL003.synthetic",
            package_sid="S-1-15-2-1",
            profile_storage_path=str(Path(tempfile.gettempdir()) / "synthetic-profile"),
            capabilities=(),
            allowed_read_paths=tuple(
                str(grant.path) for grant in context.sandbox_request.allowed_read
            ),
            read_identity_manifest_entry_count=1,
            read_identity_manifest_sha256=(
                context.sandbox_request.expected_read_identity_manifest_sha256
            ),
            scratch_directory=str(context.sandbox_request.scratch_directory),
            environment=context.sandbox_request.environment,
            inherited_handle_roles=("stdin", "stdout", "stderr"),
            process_id=4321,
            token_is_appcontainer=True,
            token_appcontainer_sid_verified=True,
            token_integrity_rid=4096,
            token_elevated=False,
            token_capability_count=0,
            access_probes=observations,
            denied_probe_entry_count=sum(
                probe.expected is sandbox_broker.PathProbeStatus.DENIED
                for probe in context.sandbox_request.access_probes
            ),
            denied_probe_manifest_sha256="2" * 64,
            read_only_probe_entry_count=1,
            read_only_probe_manifest_sha256="f" * 64,
            scratch_access_probe_manifest_sha256="1" * 64,
            max_processes=1,
            child_process_restricted=True,
            job_assigned_at_creation=True,
            job_membership_verified=True,
            job_limit_flags=0x2008,
            breakaway_allowed=False,
            kill_on_job_close=True,
            job_empty=True,
            acl_entry_count=2,
            original_acl_manifest_sha256="e" * 64,
            restored_acl_manifest_sha256="e" * 64,
            acl_exactly_restored=True,
            scratch_emptied=True,
            profile_deleted=True,
            profile_storage_deleted=True,
        )
        return sandbox_broker.SandboxResult(
            command=context.sandbox_request.command,
            return_code=0,
            stdout=payload,
            stderr=b"",
            termination_reason=sandbox_broker.TerminationReason.COMPLETED,
            wall_time_ns=1000,
            total_user_time_100ns=11,
            total_kernel_time_100ns=12,
            total_processes=1,
            terminated_processes=0,
            read_operation_count=3,
            write_operation_count=4,
            other_operation_count=5,
            read_transfer_count=6,
            write_transfer_count=7,
            other_transfer_count=8,
            preexit=receipt,
            attestation=attestation,
        )

    def test_attempt_precedes_child_and_raw_seal_precede_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths, claim, context = self._fixture(root)
            events: list[str] = []

            def runner(
                request: object, *, on_preexit: object
            ) -> sandbox_broker.SandboxResult:
                events.append("child-created")
                repository = authority.GitObjectRepository(
                    paths.staging_repository.absolute(),
                    self.git,  # type: ignore[union-attr]
                )
                head = subprocess.check_output(
                    [
                        str(self.git.path),
                        "-C",
                        str(paths.staging_repository),
                        "rev-parse",
                        "HEAD",
                    ],
                    text=True,
                ).strip()
                self.assertEqual(
                    set(repository.tree_index(head)), {candidate_observer.ATTEMPT_PATH}
                )
                result = self._result(context, on_preexit)
                events.append("ack-returned")
                sealed_head = subprocess.check_output(
                    [
                        str(self.git.path),
                        "-C",
                        str(paths.staging_repository),
                        "rev-parse",
                        "HEAD",
                    ],
                    text=True,
                ).strip()
                self.assertEqual(
                    set(repository.tree_index(sealed_head)),
                    {
                        candidate_observer.ATTEMPT_PATH,
                        candidate_observer.RAW_PATH,
                        candidate_observer.SEAL_PATH,
                    },
                )
                return result

            with (
                mock.patch.object(candidate_observer, "_validate_raw", return_value={}),
                mock.patch.object(
                    candidate_observer.environment_contract,
                    "verify_frozen_environment",
                ),
            ):
                published = candidate_observer.observe_claimed(
                    stage="development",
                    paths=paths,
                    claim=claim,
                    context_loader=lambda *_: context,
                    sandbox_runner=runner,
                    context_revalidator=lambda _: events.append("revalidate"),
                )
            self.assertEqual(events[0:2], ["revalidate", "child-created"])
            self.assertIn("ack-returned", events)
            self.assertEqual(published.repository, paths.evidence_repository)
            self.assertFalse(paths.staging_repository.exists())
            self.assertFalse(paths.scratch_directory.exists())
            repository = authority.GitObjectRepository(
                published.repository.absolute(), self.git
            )
            self.assertEqual(
                set(repository.tree_index(published.commit)),
                candidate_observer.EVIDENCE_PATHS,
            )

            self.assertEqual(repository.commit_tree(published.commit), published.tree)
            self.assertEqual(
                subprocess.check_output(
                    [
                        str(self.git.path),
                        "-C",
                        str(published.repository),
                        "status",
                        "--porcelain=v1",
                        "--untracked-files=all",
                    ]
                ),
                b"",
            )
            attempt = json.loads(
                (published.repository / candidate_observer.ATTEMPT_PATH).read_bytes()
            )
            self.assertEqual(attempt["launcher_claim"]["file"]["sha256"], claim.sha256)
            self.assertEqual(attempt["observer_authority"], context.observer_authority)
            request = attempt["sandbox_request"]
            self.assertEqual(
                request["command"][1:5],
                [
                    "--startup-file=no",
                    "--history-file=no",
                    "--compiled-modules=no",
                    "--pkgimages=no",
                ],
            )
            self.assertTrue(request["command"][5].startswith("--project="))
            self.assertNotIn("candidate_execution.py", "\n".join(request["command"]))
            self.assertEqual(
                request["job"],
                {
                    "assigned_at_creation": True,
                    "breakaway_allowed": False,
                    "child_process_policy": "restricted-no-descendants",
                    "kill_on_close": True,
                    "max_processes": 1,
                },
            )
            environment = {
                item["name"]: item["value"] for item in request["environment"]
            }
            self.assertEqual(
                environment.get("GEOTARGET_C0_PREEXIT_PROTOCOL"),
                "u64be-frame-flush-close-stdout-crt-close-fd1-yield-read-ack/v3",
            )
            self.assertEqual(
                [
                    (item["path"], item["expected"])
                    for item in request["access_probes"][-5:]
                ],
                [
                    (str(paths.root), "denied"),
                    (str(paths.staging_repository), "denied"),
                    (str(paths.attempt_marker), "denied"),
                    (
                        str(context.sandbox_request.access_probes[-2].path),
                        "denied",
                    ),
                    (
                        str(context.sandbox_request.access_probes[-1].path),
                        "denied",
                    ),
                ],
            )
            self.assertNotIn(paths.root, paths.scratch_directory.parents)
            exit_document = json.loads(
                (published.repository / candidate_observer.EXIT_PATH).read_bytes()
            )
            probes = exit_document["sandbox_result"]["appcontainer_attestation"][
                "access_probes"
            ]
            self.assertEqual(
                [item["observed"] for item in probes],
                [
                    "allowed",
                    "denied",
                    "denied",
                    "denied",
                    "denied",
                    "denied",
                    "denied",
                    "denied",
                    "denied",
                ],
            )
            self.assertEqual(
                [item["winerror"] for item in probes],
                [0, 5, 5, 5, 5, 5, 5, 5, 5],
            )
            attestation = exit_document["sandbox_result"]["appcontainer_attestation"]
            self.assertGreaterEqual(attestation["denied_probe_entry_count"], 8)
            self.assertEqual(attestation["denied_probe_manifest_sha256"], "2" * 64)

    def test_preexit_elapsed_timeout_or_tamper_never_releases_ack(self) -> None:
        formal_timeout_ns = int(
            candidate_observer.CANDIDATE_TIMEOUT_SECONDS * 1_000_000_000
        )
        cases = (
            (formal_timeout_ns, "deadline elapsed"),
            (
                formal_timeout_ns
                - candidate_observer.PREEXIT_CALLBACK_DEADLINE_GUARD_NS,
                "deadline elapsed",
            ),
            (-1, "timing authority is malformed"),
        )
        for observer_elapsed_ns, message in cases:
            with self.subTest(observer_elapsed_ns=observer_elapsed_ns):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    paths, claim, context = self._fixture(root)
                    callback_returns: list[bytes] = []

                    def runner(
                        _request: object, *, on_preexit: object
                    ) -> sandbox_broker.SandboxResult:
                        result = self._result(
                            context,
                            on_preexit,
                            observer_elapsed_ns=observer_elapsed_ns,
                        )
                        callback_returns.append(result.preexit.ack_sha256.encode())  # type: ignore[union-attr]
                        return result

                    with (
                        mock.patch.object(
                            candidate_observer.environment_contract,
                            "verify_frozen_environment",
                        ),
                        mock.patch.object(candidate_observer, "_validate_raw") as raw,
                        self.assertRaisesRegex(
                            candidate_observer.CandidateObservationError,
                            message,
                        ),
                    ):
                        candidate_observer.observe_claimed(
                            stage="development",
                            paths=paths,
                            claim=claim,
                            context_loader=lambda *_: context,
                            sandbox_runner=runner,
                            context_revalidator=lambda _: None,
                        )
                    raw.assert_not_called()
                    self.assertEqual(callback_returns, [])
                    self.assertFalse(
                        (
                            paths.staging_repository / candidate_observer.RAW_PATH
                        ).exists()
                    )
                    self.assertFalse(
                        (
                            paths.staging_repository / candidate_observer.SEAL_PATH
                        ).exists()
                    )
                    repository = authority.GitObjectRepository(
                        paths.staging_repository.absolute(), self.git
                    )
                    head = subprocess.check_output(
                        [
                            str(self.git.path),
                            "-C",
                            str(paths.staging_repository),
                            "rev-parse",
                            "HEAD",
                        ],
                        text=True,
                    ).strip()
                    self.assertEqual(
                        set(repository.tree_index(head)),
                        {candidate_observer.ATTEMPT_PATH},
                    )

    def test_sandbox_failure_is_terminal_and_never_publishes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths, claim, context = self._fixture(root)

            def failure(_request: object, *, on_preexit: object) -> object:
                del on_preexit
                raise sandbox_broker.SandboxError("synthetic sandbox failure")

            with (
                mock.patch.object(
                    candidate_observer.environment_contract,
                    "verify_frozen_environment",
                ),
                self.assertRaisesRegex(sandbox_broker.SandboxError, "synthetic"),
            ):
                candidate_observer.observe_claimed(
                    stage="development",
                    paths=paths,
                    claim=claim,
                    context_loader=lambda *_: context,
                    sandbox_runner=failure,  # type: ignore[arg-type]
                    context_revalidator=lambda _: None,
                )
            self.assertTrue(paths.attempt_marker.is_file())
            self.assertTrue(paths.staging_repository.is_dir())
            self.assertFalse(paths.evidence_repository.exists())
            repository = authority.GitObjectRepository(
                paths.staging_repository.absolute(), self.git
            )
            head = subprocess.check_output(
                [
                    str(self.git.path),
                    "-C",
                    str(paths.staging_repository),
                    "rev-parse",
                    "HEAD",
                ],
                text=True,
            ).strip()
            self.assertEqual(
                set(repository.tree_index(head)), {candidate_observer.ATTEMPT_PATH}
            )

    def test_wrong_denied_probe_winerror_fails_after_seal_before_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths, claim, context = self._fixture(root)

            def runner(
                _request: object, *, on_preexit: object
            ) -> sandbox_broker.SandboxResult:
                return self._result(context, on_preexit, bad_denied_winerror=True)

            with (
                mock.patch.object(candidate_observer, "_validate_raw", return_value={}),
                mock.patch.object(
                    candidate_observer.environment_contract,
                    "verify_frozen_environment",
                ),
                self.assertRaisesRegex(
                    candidate_observer.CandidateObservationError,
                    "kernel path-access probe",
                ),
            ):
                candidate_observer.observe_claimed(
                    stage="development",
                    paths=paths,
                    claim=claim,
                    context_loader=lambda *_: context,
                    sandbox_runner=runner,
                    context_revalidator=lambda _: None,
                )
            repository = authority.GitObjectRepository(
                paths.staging_repository.absolute(), self.git
            )
            head = subprocess.check_output(
                [
                    str(self.git.path),
                    "-C",
                    str(paths.staging_repository),
                    "rev-parse",
                    "HEAD",
                ],
                text=True,
            ).strip()
            self.assertEqual(
                set(repository.tree_index(head)),
                {
                    candidate_observer.ATTEMPT_PATH,
                    candidate_observer.RAW_PATH,
                    candidate_observer.SEAL_PATH,
                },
            )

    def test_four_candidate_schemas_are_valid_draft_2020_12(self) -> None:
        from jsonschema import Draft202012Validator

        for name in (
            "candidate-run-attempt.schema.json",
            "candidate-output-preexit-seal.schema.json",
            "candidate-process-exit.schema.json",
            "candidate-run-authority.schema.json",
        ):
            with self.subTest(schema=name):
                schema = json.loads((SOURCE_ROOT / name).read_text("utf-8"))
                Draft202012Validator.check_schema(schema)


if __name__ == "__main__":
    unittest.main()
