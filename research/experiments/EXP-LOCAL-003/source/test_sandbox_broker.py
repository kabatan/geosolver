"""Tests for the C0-owned stable Windows AppContainer broker."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import sandbox_broker as sandbox


class _FakeBackend:
    def __init__(self) -> None:
        self.requests: list[sandbox.SandboxRequest] = []

    def run(
        self,
        request: sandbox.SandboxRequest,
        on_preexit: object = None,
    ) -> object:
        if on_preexit is not None:
            raise AssertionError("unexpected pre-exit callback")
        self.requests.append(request)
        return object()


class SandboxBrokerTests(unittest.TestCase):
    def _layout(self, root: Path) -> tuple[Path, Path, Path]:
        executable = root / "capsule" / "synthetic.exe"
        executable.parent.mkdir()
        executable.write_bytes(b"synthetic")
        scratch = root / "scratch"
        scratch.mkdir()
        denied = root / "denied.bin"
        denied.write_bytes(b"private")
        return executable, scratch, denied

    def test_validation_closes_environment_and_checks_probe_partition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            executable, scratch, denied = self._layout(Path(temporary))
            request = sandbox.SandboxRequest(
                command=(str(executable), "--fixed"),
                allowed_read=(sandbox.ReadGrant(executable),),
                scratch_directory=scratch,
                claim_reference="claim-1",
                environment=(("CUSTOM", "closed"),),
                access_probes=(
                    sandbox.AccessProbe(executable, sandbox.PathProbeStatus.ALLOWED),
                    sandbox.AccessProbe(denied, sandbox.PathProbeStatus.DENIED),
                ),
            )
            validated = sandbox._validate_request(request)
            environment = dict(validated.environment)
            self.assertEqual(environment["CUSTOM"], "closed")
            self.assertEqual(environment["USERPROFILE"], str(scratch))
            self.assertEqual(environment["LOCALAPPDATA"], str(scratch))
            self.assertEqual(environment["APPDATA"], str(scratch))
            self.assertEqual(environment["TEMP"], str(scratch))
            self.assertNotIn("PYTHONPATH", environment)
            self.assertEqual(
                [probe.expected for probe in validated.probes],
                [sandbox.PathProbeStatus.ALLOWED, sandbox.PathProbeStatus.DENIED],
            )

            with self.assertRaisesRegex(
                sandbox.SandboxError, "denied access probe is inside"
            ):
                sandbox._validate_request(
                    sandbox.SandboxRequest(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="claim-2",
                        access_probes=(
                            sandbox.AccessProbe(
                                executable, sandbox.PathProbeStatus.DENIED
                            ),
                        ),
                    )
                )

    def test_hardlinks_overlap_and_case_duplicate_environment_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable, scratch, _denied = self._layout(root)
            alias = root / "alias.exe"
            try:
                os.link(executable, alias)
            except OSError as error:
                self.skipTest(f"hardlinks unavailable: {error}")
            with self.assertRaisesRegex(sandbox.SandboxError, "hardlink"):
                sandbox._validate_request(
                    sandbox.SandboxRequest(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="hardlink",
                    )
                )
            alias.unlink()

            capsule = executable.parent
            with self.assertRaisesRegex(sandbox.SandboxError, "must not overlap"):
                sandbox._validate_request(
                    sandbox.SandboxRequest(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(root, recursive=True),),
                        scratch_directory=scratch,
                        claim_reference="overlap",
                    )
                )
            self.assertTrue(capsule.is_dir())

            with self.assertRaisesRegex(
                sandbox.SandboxError, "duplicate case-insensitive environment"
            ):
                sandbox._validate_request(
                    sandbox.SandboxRequest(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="duplicate-env",
                        environment=(("KEY", "1"), ("key", "2")),
                    )
                )

    def test_injected_backend_does_not_enable_a_subprocess_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            executable, scratch, _denied = self._layout(Path(temporary))
            request = sandbox.SandboxRequest(
                command=(str(executable),),
                allowed_read=(sandbox.ReadGrant(executable),),
                scratch_directory=scratch,
                claim_reference="fake-backend",
            )
            backend = _FakeBackend()
            sentinel = sandbox.run_sandboxed(request, _api=backend)  # type: ignore[arg-type]
            self.assertIsInstance(sentinel, object)
            self.assertEqual(backend.requests, [request])

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_real_appcontainer_token_job_probes_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "capsule" / "whoami.exe"
            executable.parent.mkdir()
            shutil.copyfile(
                Path(os.environ.get("SystemRoot", r"C:\Windows"))
                / "System32"
                / "whoami.exe",
                executable,
            )
            scratch = root / "scratch"
            scratch.mkdir()
            denied = root / "private.txt"
            denied.write_bytes(b"must remain denied")
            result = sandbox.run_sandboxed(
                sandbox.SandboxRequest(
                    command=(str(executable),),
                    allowed_read=(sandbox.ReadGrant(executable),),
                    scratch_directory=scratch,
                    claim_reference="unit-real-appcontainer",
                    timeout_seconds=10.0,
                    access_probes=(
                        sandbox.AccessProbe(
                            executable, sandbox.PathProbeStatus.ALLOWED
                        ),
                        sandbox.AccessProbe(denied, sandbox.PathProbeStatus.DENIED),
                    ),
                )
            )
            attestation = result.attestation
            self.assertEqual(result.return_code, 0)
            self.assertEqual(result.stderr, b"")
            self.assertTrue(result.stdout)
            self.assertTrue(attestation.token_is_appcontainer)
            self.assertTrue(attestation.token_appcontainer_sid_verified)
            self.assertEqual(attestation.token_integrity_rid, 0x1000)
            self.assertFalse(attestation.token_elevated)
            self.assertEqual(attestation.token_capability_count, 0)
            self.assertTrue(attestation.job_assigned_at_creation)
            self.assertTrue(attestation.job_membership_verified)
            self.assertEqual(attestation.job_limit_flags, 0x2008)
            self.assertTrue(attestation.job_empty)
            self.assertEqual(
                [
                    (probe.observed, probe.winerror)
                    for probe in attestation.access_probes
                ],
                [
                    (sandbox.PathProbeStatus.ALLOWED, 0),
                    (sandbox.PathProbeStatus.DENIED, 5),
                ],
            )
            self.assertTrue(attestation.acl_exactly_restored)
            self.assertTrue(attestation.scratch_emptied)
            self.assertTrue(attestation.profile_deleted)
            self.assertEqual(denied.read_bytes(), b"must remain denied")
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_preexit_frame_is_callback_sealed_before_ack_and_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capsule = root / "python-capsule"
            capsule.mkdir()
            base = Path(sys.base_prefix)
            for name in (
                "python.exe",
                "python3.dll",
                f"python{sys.version_info.major}{sys.version_info.minor}.dll",
                "vcruntime140.dll",
                "vcruntime140_1.dll",
                "vcruntime140_threads.dll",
            ):
                source = base / name
                if source.is_file():
                    shutil.copyfile(source, capsule / name)
            shutil.copyfile(base / "Library" / "bin" / "zlib.dll", capsule / "zlib.dll")
            shutil.copytree(base / "Lib" / "encodings", capsule / "Lib" / "encodings")
            (
                capsule / f"python{sys.version_info.major}{sys.version_info.minor}._pth"
            ).write_text("Lib\n.\n", encoding="ascii")
            child = capsule / "child.py"
            child.write_text(
                "import sys\n"
                "payload=b'candidate-output'\n"
                "sys.stdout.buffer.write(len(payload).to_bytes(8,'big')+payload)\n"
                "sys.stdout.buffer.flush()\n"
                "ack=sys.stdin.buffer.read()\n"
                "raise SystemExit(0 if ack==b'C0-SEALED-ACK' else 23)\n",
                encoding="ascii",
            )
            executable = capsule / "python.exe"
            scratch = root / "scratch"
            scratch.mkdir()
            callbacks: list[sandbox.PreexitContext] = []

            def seal(payload: bytes, context: sandbox.PreexitContext) -> bytes:
                self.assertEqual(payload, b"candidate-output")
                self.assertGreaterEqual(context.active_processes, 1)
                self.assertTrue(context.root_process_still_active)
                callbacks.append(context)
                return b"C0-SEALED-ACK"

            result = sandbox.run_sandboxed(
                sandbox.SandboxRequest(
                    command=(str(executable), "-I", "-S", str(child)),
                    allowed_read=(sandbox.ReadGrant(capsule, recursive=True),),
                    scratch_directory=scratch,
                    claim_reference="unit-preexit-handshake",
                    timeout_seconds=10.0,
                    stdout_limit_bytes=4096,
                    stderr_limit_bytes=4096,
                    preexit_payload_limit_bytes=1024,
                ),
                on_preexit=seal,
            )
            self.assertEqual(result.return_code, 0)
            self.assertEqual(result.stdout, b"candidate-output")
            self.assertEqual(result.stderr, b"")
            self.assertEqual(len(callbacks), 1)
            self.assertIsNotNone(result.preexit)
            assert result.preexit is not None
            self.assertTrue(result.preexit.callback_completed)
            self.assertTrue(result.preexit.ack_released)
            self.assertGreaterEqual(result.preexit.active_processes_before_callback, 1)
            self.assertEqual(
                result.preexit.active_processes_before_callback,
                result.preexit.active_processes_before_ack,
            )
            self.assertTrue(result.preexit.root_active_before_ack)


if __name__ == "__main__":
    unittest.main()
