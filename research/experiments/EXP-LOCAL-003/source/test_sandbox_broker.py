"""Tests for the C0-owned stable Windows AppContainer broker."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from ctypes import wintypes

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


class _SlowBackend(_FakeBackend):
    def __init__(self, state_lock: threading.Lock, state: dict[str, int]) -> None:
        super().__init__()
        self.state_lock = state_lock
        self.state = state

    def run(
        self,
        request: sandbox.SandboxRequest,
        on_preexit: object = None,
    ) -> object:
        with self.state_lock:
            self.state["active"] += 1
            self.state["maximum"] = max(self.state["maximum"], self.state["active"])
        try:
            time.sleep(0.1)
            return super().run(request, on_preexit)
        finally:
            with self.state_lock:
                self.state["active"] -= 1


class _ChunkedPipeApi:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = iter(chunks)

    def read_pipe(self, _handle: int) -> bytes | None:
        return next(self._chunks, None)


class _DeleteSequence:
    def __init__(self, results: list[int]) -> None:
        self._results = iter(results)
        self.calls = 0

    def DeleteAppContainerProfile(self, _name: str) -> int:
        self.calls += 1
        return next(self._results)


class SandboxBrokerTests(unittest.TestCase):
    @staticmethod
    def _set_test_extended_attribute(path: Path) -> bool:
        """Set one ordinary NTFS EA; return false only when unsupported."""

        class _IoStatusBlock(ctypes.Structure):
            _fields_ = (
                ("Status", ctypes.c_void_p),
                ("Information", ctypes.c_size_t),
            )

        api = sandbox._WindowsApi()
        flags = (
            sandbox._FILE_FLAG_BACKUP_SEMANTICS
            if path.is_dir()
            else sandbox._FILE_ATTRIBUTE_NORMAL
        )
        handle = api.kernel32.CreateFileW(
            str(path),
            sandbox._FILE_READ_EA
            | sandbox._FILE_WRITE_EA
            | sandbox._FILE_READ_ATTRIBUTES,
            sandbox._FILE_SHARE_READ
            | sandbox._FILE_SHARE_WRITE
            | sandbox._FILE_SHARE_DELETE,
            None,
            sandbox._OPEN_EXISTING,
            flags,
            None,
        )
        value = ctypes.cast(handle, ctypes.c_void_p).value
        if value in {None, sandbox._INVALID_HANDLE_VALUE}:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ntdll = ctypes.WinDLL("ntdll")
            ntdll.NtSetEaFile.argtypes = (
                wintypes.HANDLE,
                ctypes.POINTER(_IoStatusBlock),
                wintypes.LPVOID,
                wintypes.ULONG,
            )
            ntdll.NtSetEaFile.restype = ctypes.c_long
            name = b"GeoTarget.Test"
            value_bytes = b"nonempty"
            payload = (
                (0).to_bytes(4, "little")
                + bytes((0, len(name)))
                + len(value_bytes).to_bytes(2, "little")
                + name
                + b"\x00"
                + value_bytes
            )
            buffer = ctypes.create_string_buffer(payload)
            status = ntdll.NtSetEaFile(
                wintypes.HANDLE(value),
                ctypes.byref(_IoStatusBlock()),
                buffer,
                len(payload),
            )
            unsigned_status = ctypes.c_uint32(status).value
            if unsigned_status == 0:
                return True
            if unsigned_status in {0xC0000010, 0xC000004F, 0xC00000BB}:
                return False
            raise OSError(f"NtSetEaFile failed with NTSTATUS 0x{unsigned_status:08x}")
        finally:
            api.close_handle(value)

    def _request(
        self,
        *,
        command: tuple[str, ...],
        allowed_read: tuple[sandbox.ReadGrant, ...],
        **options: object,
    ) -> sandbox.SandboxRequest:
        manifest_sha256 = "0" * 64
        if os.name == "nt":
            manifest_sha256 = sandbox.capture_read_identity_manifest(
                executable=Path(command[0]), allowed_read=allowed_read
            ).sha256
        return sandbox.SandboxRequest(
            command=command,
            allowed_read=allowed_read,
            expected_read_identity_manifest_sha256=manifest_sha256,
            **options,  # type: ignore[arg-type]
        )

    def _layout(self, root: Path) -> tuple[Path, Path, Path]:
        executable = root / "capsule" / "synthetic.exe"
        executable.parent.mkdir()
        executable.write_bytes(b"synthetic")
        scratch = root / "scratch"
        scratch.mkdir()
        denied = root / "denied.bin"
        denied.write_bytes(b"private")
        return executable, scratch, denied

    def _python_capsule(self, root: Path) -> tuple[Path, Path]:
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
        return capsule, capsule / "python.exe"

    def test_validation_closes_environment_and_checks_probe_partition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            executable, scratch, denied = self._layout(Path(temporary))
            request = self._request(
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
                    self._request(
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

            with self.assertRaisesRegex(
                sandbox.SandboxError, "executable must be covered"
            ):
                sandbox._validate_request(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable.parent),),
                        scratch_directory=scratch,
                        claim_reference="nonrecursive-directory",
                    )
                )

            with self.assertRaisesRegex(sandbox.SandboxError, "max_processes == 1"):
                sandbox._validate_request(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="process-policy",
                        max_processes=2,
                    )
                )

    def test_relative_executable_and_case_colliding_authority_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable, scratch, denied = self._layout(root)
            relative = executable.relative_to(root)
            request = sandbox.SandboxRequest(
                command=(str(relative),),
                allowed_read=(sandbox.ReadGrant(executable),),
                scratch_directory=scratch,
                claim_reference="relative-executable",
                expected_read_identity_manifest_sha256="0" * 64,
            )
            with mock.patch("sandbox_broker.os.getcwd", return_value=str(root)):
                with self.assertRaisesRegex(
                    sandbox.SandboxError, "executable must be absolute"
                ):
                    sandbox._validate_request(request)

            collision_request = sandbox.SandboxRequest(
                command=(str(executable),),
                allowed_read=(
                    sandbox.ReadGrant(executable),
                    sandbox.ReadGrant(denied),
                ),
                scratch_directory=scratch,
                claim_reference="case-collision",
                expected_read_identity_manifest_sha256="0" * 64,
            )
            with (
                mock.patch(
                    "sandbox_broker._normalize_existing",
                    side_effect=lambda path, **_options: Path(path),
                ),
                mock.patch(
                    "sandbox_broker.os.path.normcase", return_value="one-folded-path"
                ),
            ):
                with self.assertRaisesRegex(sandbox.SandboxError, "case-colliding"):
                    sandbox._validate_request(collision_request)

    def test_denied_tree_intersection_and_aliased_descendants_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable, scratch, _denied = self._layout(root)
            denied_tree = root / "denied-tree"
            denied_tree.mkdir()
            allowed_child = denied_tree / "allowed-child.bin"
            allowed_child.write_bytes(b"allowed")
            grants = (
                sandbox.ReadGrant(executable),
                sandbox.ReadGrant(allowed_child),
            )
            with self.assertRaisesRegex(
                sandbox.SandboxError, "recursive denied access probe intersects"
            ):
                sandbox._validate_request(
                    self._request(
                        command=(str(executable),),
                        allowed_read=grants,
                        scratch_directory=scratch,
                        claim_reference="denied-tree-read-intersection",
                        access_probes=(
                            sandbox.AccessProbe(
                                denied_tree, sandbox.PathProbeStatus.DENIED
                            ),
                        ),
                    )
                )

            hardlink_tree = root / "hardlink-tree"
            hardlink_tree.mkdir()
            first = hardlink_tree / "first.bin"
            alias = hardlink_tree / "alias.bin"
            first.write_bytes(b"one identity")
            try:
                os.link(first, alias)
            except OSError as error:
                self.skipTest(f"hardlinks unavailable: {error}")
            with self.assertRaisesRegex(sandbox.SandboxError, "hardlinked file"):
                sandbox._validate_request(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="denied-tree-hardlink",
                        access_probes=(
                            sandbox.AccessProbe(
                                hardlink_tree, sandbox.PathProbeStatus.DENIED
                            ),
                        ),
                    )
                )

            collision_tree = root / "collision-tree"
            collision_tree.mkdir()
            (collision_tree / "Alpha").write_bytes(b"a")
            (collision_tree / "Beta").write_bytes(b"b")
            collision_root = str(collision_tree)

            def fold_tree_entries(value: str) -> str:
                return "root" if str(value) == collision_root else "one-child"

            with (
                mock.patch(
                    "sandbox_broker.os.path.realpath",
                    side_effect=lambda value: str(value),
                ),
                mock.patch(
                    "sandbox_broker.os.path.normcase", side_effect=fold_tree_entries
                ),
            ):
                with self.assertRaisesRegex(sandbox.SandboxError, "case-colliding"):
                    sandbox._expand_recursive_tree(
                        collision_tree, context="synthetic denied tree"
                    )

    def test_denied_tree_reparse_descendant_fails_closed_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable, scratch, _denied = self._layout(root)
            denied_tree = root / "denied-tree"
            denied_tree.mkdir()
            outside = root / "outside"
            outside.mkdir()
            link = denied_tree / "alias"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as symlink_error:
                if os.name != "nt":
                    self.skipTest(f"directory symlinks unavailable: {symlink_error}")
                junction = subprocess.run(
                    [
                        "cmd.exe",
                        "/d",
                        "/c",
                        "mklink",
                        "/J",
                        str(link),
                        str(outside),
                    ],
                    capture_output=True,
                    text=True,
                )
                if junction.returncode != 0:
                    self.skipTest(
                        "directory links unavailable: "
                        f"symlink={symlink_error}; junction={junction.stderr}"
                    )
            with self.assertRaisesRegex(sandbox.SandboxError, "link/reparse alias"):
                sandbox._validate_request(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="denied-tree-reparse",
                        access_probes=(
                            sandbox.AccessProbe(
                                denied_tree, sandbox.PathProbeStatus.DENIED
                            ),
                        ),
                    )
                )

    def test_profile_delete_is_one_shot_then_only_polls_storage(self) -> None:
        userenv = _DeleteSequence([0])
        api = mock.Mock(userenv=userenv)
        with (
            mock.patch(
                "sandbox_broker.os.path.lexists", side_effect=[True, False]
            ) as lexists,
            mock.patch("sandbox_broker.time.sleep") as sleep,
        ):
            sandbox._WindowsApi.delete_profile(
                api, "GeoTarget.EXPLOCAL003.test", Path("profile-storage")
            )
        self.assertEqual(userenv.calls, 1)
        self.assertEqual(lexists.call_count, 2)
        sleep.assert_called_once()

        userenv = _DeleteSequence([sandbox._HRESULT_FROM_WIN32_ERROR_NOT_FOUND])
        api = mock.Mock(userenv=userenv)
        with (
            mock.patch("sandbox_broker.os.path.lexists", return_value=False),
            mock.patch("sandbox_broker.time.sleep") as sleep,
        ):
            sandbox._WindowsApi.delete_profile(
                api, "GeoTarget.EXPLOCAL003.absent", Path("profile-storage")
            )
        self.assertEqual(userenv.calls, 1)
        sleep.assert_not_called()

    def test_pipe_reader_incrementally_parses_one_frame_and_rejects_trailing(
        self,
    ) -> None:
        payload = b"x" * (2 * 1024 * 1024)
        frame = len(payload).to_bytes(8, "big") + payload
        chunks = [
            frame[:3],
            frame[3:8],
            *[frame[i : i + 4093] for i in range(8, len(frame), 4093)],
        ]
        reader = sandbox._PipeReader(  # type: ignore[arg-type]
            _ChunkedPipeApi(chunks),
            1,
            len(frame),
            "stdout",
            frame_limit=len(payload),
        )
        reader.start()
        reader.join(timeout=5.0)
        self.assertFalse(reader.is_alive())
        self.assertFalse(hasattr(reader, "_chunks"))
        self.assertEqual(reader.frame(), (payload, None))
        self.assertEqual(reader.result().payload, frame)

        trailing = sandbox._PipeReader(  # type: ignore[arg-type]
            _ChunkedPipeApi([frame, b"trailing"]),
            1,
            len(frame) + 8,
            "stdout",
            frame_limit=len(payload),
        )
        trailing.start()
        trailing.join(timeout=5.0)
        self.assertFalse(trailing.is_alive())
        self.assertEqual(
            trailing.frame()[1],
            "pre-exit stdout contains bytes after its single frame",
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
                    self._request(
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
                    self._request(
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
                    self._request(
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
            request = self._request(
                command=(str(executable),),
                allowed_read=(sandbox.ReadGrant(executable),),
                scratch_directory=scratch,
                claim_reference="fake-backend",
            )
            backend = _FakeBackend()
            sentinel = sandbox.run_sandboxed(request, _api=backend)  # type: ignore[arg-type]
            self.assertIsInstance(sentinel, object)
            self.assertEqual(backend.requests, [request])

    def test_in_process_broker_runs_are_serialized_from_validation_to_return(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            executable, scratch, _denied = self._layout(Path(temporary))
            request = self._request(
                command=(str(executable),),
                allowed_read=(sandbox.ReadGrant(executable),),
                scratch_directory=scratch,
                claim_reference="thread-serialization",
            )
            state_lock = threading.Lock()
            state = {"active": 0, "maximum": 0}
            backends = [
                _SlowBackend(state_lock, state),
                _SlowBackend(state_lock, state),
            ]
            barrier = threading.Barrier(3)
            errors: list[BaseException] = []

            def invoke(backend: _SlowBackend) -> None:
                try:
                    barrier.wait()
                    sandbox.run_sandboxed(request, _api=backend)
                except BaseException as error:
                    errors.append(error)

            threads = [
                threading.Thread(target=invoke, args=(backend,)) for backend in backends
            ]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=5.0)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertEqual(state["maximum"], 1)
            self.assertEqual([len(backend.requests) for backend in backends], [1, 1])

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
                self._request(
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
            self.assertTrue(attestation.child_process_restricted)
            self.assertTrue(attestation.job_empty)
            self.assertEqual(result.total_processes, 1)
            self.assertEqual(result.terminated_processes, 0)
            self.assertEqual(attestation.read_only_probe_entry_count, 1)
            self.assertEqual(attestation.read_identity_manifest_entry_count, 1)
            self.assertEqual(
                attestation.read_identity_manifest_sha256,
                sandbox.capture_read_identity_manifest(
                    executable=executable,
                    allowed_read=(sandbox.ReadGrant(executable),),
                ).sha256,
            )
            self.assertEqual(len(attestation.read_only_probe_manifest_sha256), 64)
            self.assertEqual(
                attestation.denied_probe_entry_count, 1 + len(denied.parents)
            )
            self.assertEqual(len(attestation.denied_probe_manifest_sha256), 64)
            self.assertEqual(len(attestation.scratch_access_probe_manifest_sha256), 64)
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
            self.assertTrue(attestation.profile_storage_deleted)
            self.assertFalse(os.path.lexists(attestation.profile_storage_path))
            self.assertEqual(denied.read_bytes(), b"must remain denied")
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_denied_directory_binds_every_preexisting_descendant(self) -> None:
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
            denied = root / "denied-tree"
            nested = denied / "nested"
            nested.mkdir(parents=True)
            child = nested / "private.bin"
            child.write_bytes(b"immutable descendant")
            result = sandbox.run_sandboxed(
                self._request(
                    command=(str(executable),),
                    allowed_read=(sandbox.ReadGrant(executable),),
                    scratch_directory=scratch,
                    claim_reference="unit-denied-descendant-binding",
                    access_probes=(
                        sandbox.AccessProbe(denied, sandbox.PathProbeStatus.DENIED),
                    ),
                )
            )
            denied_entries = sandbox._expand_denied_probe_target(denied)
            self.assertEqual(result.return_code, 0)
            self.assertEqual(
                result.attestation.denied_probe_entry_count,
                len(denied_entries) + len(denied.parents),
            )
            self.assertEqual(len(result.attestation.denied_probe_manifest_sha256), 64)
            self.assertEqual(child.read_bytes(), b"immutable descendant")
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_denied_directory_rejects_protected_ambient_child_acl(self) -> None:
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
            denied = root / "denied-tree"
            denied.mkdir()
            child = denied / "protected-child.bin"
            child.write_bytes(b"immutable descendant")
            subprocess.run(
                [
                    "icacls.exe",
                    str(child),
                    "/inheritance:d",
                    "/grant",
                    "*S-1-15-2-1:(M)",
                ],
                check=True,
                capture_output=True,
            )
            with self.assertRaisesRegex(
                sandbox.SandboxError, "denied descendant right.*winerror=0"
            ):
                sandbox.run_sandboxed(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="unit-denied-protected-child",
                        access_probes=(
                            sandbox.AccessProbe(denied, sandbox.PathProbeStatus.DENIED),
                        ),
                    )
                )
            self.assertEqual(child.read_bytes(), b"immutable descendant")
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_denied_probe_rejects_ambient_app_packages_target_write(self) -> None:
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
            denied = root / "write-only-target.bin"
            denied.write_bytes(b"immutable")
            subprocess.run(
                [
                    "icacls.exe",
                    str(denied),
                    "/grant",
                    "*S-1-15-2-1:(M)",
                    "/deny",
                    "*S-1-15-2-1:(RD,X)",
                ],
                check=True,
                capture_output=True,
            )
            with self.assertRaisesRegex(
                sandbox.SandboxError, "denied target right.*winerror=0"
            ):
                sandbox.run_sandboxed(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="unit-denied-target-ambient-write",
                        access_probes=(
                            sandbox.AccessProbe(denied, sandbox.PathProbeStatus.DENIED),
                        ),
                    )
                )
            self.assertEqual(denied.read_bytes(), b"immutable")
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_denied_probe_rejects_ambient_parent_namespace_mutation(self) -> None:
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
            forbidden = root / "forbidden"
            forbidden.mkdir()
            denied = forbidden / "private.bin"
            denied.write_bytes(b"immutable")
            subprocess.run(
                [
                    "icacls.exe",
                    str(forbidden),
                    "/grant",
                    "*S-1-15-2-1:(M)",
                ],
                check=True,
                capture_output=True,
            )
            with self.assertRaisesRegex(
                sandbox.SandboxError, "denied ancestor right.*winerror=0"
            ):
                sandbox.run_sandboxed(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="unit-denied-parent-ambient-mutation",
                        access_probes=(
                            sandbox.AccessProbe(denied, sandbox.PathProbeStatus.DENIED),
                        ),
                    )
                )
            self.assertEqual(denied.read_bytes(), b"immutable")
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_scratch_probe_rejects_ambient_parent_namespace_mutation(self) -> None:
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
            subprocess.run(
                [
                    "icacls.exe",
                    str(root),
                    "/grant",
                    "*S-1-15-2-1:(M)",
                ],
                check=True,
                capture_output=True,
            )
            with self.assertRaisesRegex(
                sandbox.SandboxError,
                "scratch ancestor mutation right.*winerror=0",
            ):
                sandbox.run_sandboxed(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="unit-scratch-parent-ambient-mutation",
                    )
                )
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_clean_file_and_directory_metadata_manifest_v2_is_deterministic(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            capsule = Path(temporary) / "capsule"
            nested = capsule / "nested"
            nested.mkdir(parents=True)
            executable = capsule / "synthetic.exe"
            executable.write_bytes(b"synthetic")
            (nested / "payload.bin").write_bytes(b"payload")
            grants = (sandbox.ReadGrant(capsule, recursive=True),)
            first = sandbox.capture_read_identity_manifest(
                executable=executable, allowed_read=grants
            )
            second = sandbox.capture_read_identity_manifest(
                executable=executable, allowed_read=grants
            )
            self.assertEqual(
                first.schema_version,
                "geotarget.exp-local-003.read-identity-manifest/v2",
            )
            self.assertEqual(first.entry_count, 4)
            self.assertEqual(first, second)

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_named_data_stream_on_any_read_entry_is_rejected_at_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capsule = root / "capsule"
            capsule.mkdir()
            executable = capsule / "synthetic.exe"
            executable.write_bytes(b"synthetic")
            descendant = capsule / "nested.bin"
            descendant.write_bytes(b"nested")
            for target in (capsule, executable, descendant):
                stream_path = f"{target}:hidden"
                with self.subTest(target=target):
                    with open(stream_path, "wb") as stream:
                        stream.write(b"private metadata")
                    try:
                        with self.assertRaisesRegex(
                            sandbox.SandboxError, "contains named data streams"
                        ):
                            sandbox.capture_read_identity_manifest(
                                executable=executable,
                                allowed_read=(
                                    sandbox.ReadGrant(capsule, recursive=True),
                                ),
                            )
                    finally:
                        os.remove(stream_path)

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_read_grant_would_expose_ads_if_metadata_check_were_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capsule, executable = self._python_capsule(root)
            payload = capsule / "payload.bin"
            payload.write_bytes(b"public")
            with open(f"{payload}:hidden", "wb") as stream:
                stream.write(b"hidden-readable")
            child = capsule / "read-ads.py"
            child.write_text(
                "import os,sys\n"
                "with open(sys.argv[1]+':hidden','rb') as stream:\n"
                " os.write(1,stream.read())\n",
                encoding="ascii",
            )
            scratch = root / "scratch"
            scratch.mkdir()
            grants = (sandbox.ReadGrant(capsule, recursive=True),)

            def model_omitted_ads_check(
                _api: sandbox._WindowsApi,
                _handle: int,
                _path: Path,
                identity: sandbox._Win32FileIdentity,
            ) -> tuple[int, int]:
                is_directory = bool(
                    identity.attributes & sandbox._FILE_ATTRIBUTE_DIRECTORY
                )
                return (0 if is_directory else 1), 0

            # This patch intentionally models the former broker omission.  It
            # proves that the AppContainer read ACE covers a named stream and
            # therefore that capture-time rejection is a security boundary.
            with mock.patch.object(
                sandbox._WindowsApi,
                "_clean_metadata_observation",
                new=model_omitted_ads_check,
            ):
                manifest = sandbox.capture_read_identity_manifest(
                    executable=executable, allowed_read=grants
                )
                result = sandbox.run_sandboxed(
                    sandbox.SandboxRequest(
                        command=(
                            str(executable),
                            "-I",
                            "-S",
                            "-B",
                            str(child),
                            str(payload),
                        ),
                        allowed_read=grants,
                        scratch_directory=scratch,
                        claim_reference="unit-ads-threat-regression",
                        expected_read_identity_manifest_sha256=manifest.sha256,
                    )
                )
            self.assertEqual(result.return_code, 0)
            self.assertEqual(result.stdout, b"hidden-readable")

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_nonempty_extended_attribute_is_rejected_at_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "synthetic.exe"
            executable.write_bytes(b"synthetic")
            if not self._set_test_extended_attribute(executable):
                self.skipTest("the temporary filesystem does not support EAs")
            with self.assertRaisesRegex(
                sandbox.SandboxError, "contains extended attributes"
            ):
                sandbox.capture_read_identity_manifest(
                    executable=executable,
                    allowed_read=(sandbox.ReadGrant(executable),),
                )

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_executable_content_swap_is_rejected_before_profile_or_acl(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "whoami.exe"
            shutil.copyfile(
                Path(os.environ.get("SystemRoot", r"C:\Windows"))
                / "System32"
                / "whoami.exe",
                executable,
            )
            scratch = root / "scratch"
            scratch.mkdir()
            grants = (sandbox.ReadGrant(executable),)
            expected = sandbox.capture_read_identity_manifest(
                executable=executable, allowed_read=grants
            )
            payload = bytearray(executable.read_bytes())
            payload[-1] ^= 1
            executable.write_bytes(payload)
            request = sandbox.SandboxRequest(
                command=(str(executable),),
                allowed_read=grants,
                scratch_directory=scratch,
                claim_reference="unit-executable-swap",
                expected_read_identity_manifest_sha256=expected.sha256,
            )
            with mock.patch.object(
                sandbox._WindowsApi,
                "create_profile",
                side_effect=AssertionError("profile creation must not be reached"),
            ) as create_profile:
                with self.assertRaisesRegex(
                    sandbox.SandboxError, "read identity manifest differs"
                ):
                    sandbox.run_sandboxed(request)
            create_profile.assert_not_called()
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_scratch_swap_after_validation_preserves_replacement_sentinel(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "whoami.exe"
            shutil.copyfile(
                Path(os.environ.get("SystemRoot", r"C:\Windows"))
                / "System32"
                / "whoami.exe",
                executable,
            )
            scratch = root / "scratch"
            scratch.mkdir()
            moved = root / "validated-scratch"
            grants = (sandbox.ReadGrant(executable),)
            manifest = sandbox.capture_read_identity_manifest(
                executable=executable, allowed_read=grants
            )
            request = sandbox.SandboxRequest(
                command=(str(executable),),
                allowed_read=grants,
                scratch_directory=scratch,
                claim_reference="unit-scratch-validation-race",
                expected_read_identity_manifest_sha256=manifest.sha256,
            )
            original = sandbox._WindowsApi._acquire_scratch_identity_guard

            def replace_before_guard(
                api: sandbox._WindowsApi,
                path: Path,
                expected: sandbox._ValidationIdentity,
            ) -> tuple[int, int, sandbox._Win32FileIdentity]:
                path.rename(moved)
                path.mkdir()
                (path / "DO-NOT-DELETE.txt").write_bytes(b"replacement sentinel")
                return original(api, path, expected)

            with mock.patch.object(
                sandbox._WindowsApi,
                "_acquire_scratch_identity_guard",
                new=replace_before_guard,
            ):
                with self.assertRaisesRegex(
                    sandbox.SandboxError, "scratch identity guard acquisition"
                ):
                    sandbox.run_sandboxed(request)
            sentinel = scratch / "DO-NOT-DELETE.txt"
            self.assertEqual(sentinel.read_bytes(), b"replacement sentinel")
            self.assertTrue(moved.is_dir())

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_held_scratch_guard_blocks_swap_until_acl_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "whoami.exe"
            shutil.copyfile(
                Path(os.environ.get("SystemRoot", r"C:\Windows"))
                / "System32"
                / "whoami.exe",
                executable,
            )
            scratch = root / "scratch"
            scratch.mkdir()
            moved = root / "scratch-moved"
            replacement = root / "replacement"
            replacement.mkdir()
            sentinel = replacement / "DO-NOT-DELETE.txt"
            sentinel.write_bytes(b"replacement sentinel")
            request = self._request(
                command=(str(executable),),
                allowed_read=(sandbox.ReadGrant(executable),),
                scratch_directory=scratch,
                claim_reference="unit-held-scratch-guard",
            )
            original = sandbox._WindowsApi.create_profile
            swap_errors: list[int | None] = []

            def attempt_swap(
                api: sandbox._WindowsApi, name: str
            ) -> tuple[int, int, str, Path]:
                try:
                    scratch.rename(moved)
                except OSError as error:
                    swap_errors.append(error.winerror)
                else:
                    replacement.rename(scratch)
                    raise AssertionError("held scratch guard allowed path replacement")
                return original(api, name)

            with mock.patch.object(
                sandbox._WindowsApi, "create_profile", new=attempt_swap
            ):
                result = sandbox.run_sandboxed(request)
            self.assertEqual(result.return_code, 0)
            self.assertEqual(swap_errors, [32])
            self.assertEqual(sentinel.read_bytes(), b"replacement sentinel")
            self.assertFalse(moved.exists())
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_preexisting_app_packages_write_right_is_rejected_and_restored(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "whoami.exe"
            shutil.copyfile(
                Path(os.environ.get("SystemRoot", r"C:\Windows"))
                / "System32"
                / "whoami.exe",
                executable,
            )
            scratch = root / "scratch"
            scratch.mkdir()
            subprocess.run(
                [
                    "icacls.exe",
                    str(executable),
                    "/grant",
                    "*S-1-15-2-1:(WA)",
                ],
                check=True,
                capture_output=True,
            )
            api = sandbox._WindowsApi()
            baseline = api.snapshot_dacl(executable)
            with self.assertRaisesRegex(
                sandbox.SandboxError, "right=write_attributes_winerror"
            ):
                sandbox.run_sandboxed(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(executable),),
                        scratch_directory=scratch,
                        claim_reference="unit-write-right-rejected",
                    )
                )
            restored = api.snapshot_dacl(executable)
            self.assertEqual(restored.payload, baseline.payload)
            self.assertEqual(restored.control, baseline.control)
            self.assertFalse(any(scratch.iterdir()))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_recursive_grant_crosses_protected_descendant_and_restores_exactly(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capsule = root / "capsule"
            protected = capsule / "protected"
            protected.mkdir(parents=True)
            executable = capsule / "whoami.exe"
            shutil.copyfile(
                Path(os.environ.get("SystemRoot", r"C:\Windows"))
                / "System32"
                / "whoami.exe",
                executable,
            )
            (protected / "fixture.json").write_text("{}", encoding="ascii")
            subprocess.run(
                ["icacls.exe", str(capsule), "/inheritance:e"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["icacls.exe", str(protected), "/inheritance:d"],
                check=True,
                capture_output=True,
            )
            scratch = root / "scratch"
            scratch.mkdir()
            api = sandbox._WindowsApi()
            entries = sandbox._expand_grant(sandbox.ReadGrant(capsule, recursive=True))
            baseline = {str(path): api.snapshot_dacl(path) for path in entries}
            self.assertTrue(
                baseline[str(capsule)].control & sandbox._SE_DACL_AUTO_INHERITED
            )
            self.assertTrue(baseline[str(protected)].protected)
            original_grant = sandbox._WindowsApi.grant_sid
            observed_grants: list[tuple[str, int]] = []

            def record_grant(
                windows: sandbox._WindowsApi,
                snapshot: sandbox._SecurityDescriptorSnapshot,
                sid: int,
                access_mask: int,
                inheritance: int,
            ) -> None:
                observed_grants.append((snapshot.path, inheritance))
                original_grant(windows, snapshot, sid, access_mask, inheritance)

            with mock.patch.object(sandbox._WindowsApi, "grant_sid", new=record_grant):
                result = sandbox.run_sandboxed(
                    self._request(
                        command=(str(executable),),
                        allowed_read=(sandbox.ReadGrant(capsule, recursive=True),),
                        scratch_directory=scratch,
                        claim_reference="unit-protected-descendant",
                    )
                )
            self.assertEqual(result.return_code, 0)
            self.assertEqual(
                result.attestation.read_only_probe_entry_count, len(entries)
            )
            read_grants = [
                grant for grant in observed_grants if grant[0] != str(scratch)
            ]
            self.assertEqual(
                read_grants,
                [(str(entry), sandbox._NO_INHERITANCE) for entry in entries],
            )
            for path, original in baseline.items():
                restored = api.snapshot_dacl(Path(path))
                self.assertEqual(restored.payload, original.payload, path)
                self.assertEqual(restored.control, original.control, path)

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_read_acl_restore_is_depth_sorted_and_scratch_is_last(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capsule = root / "capsule"
            child = capsule / "child"
            child.mkdir(parents=True)
            executable = child / "whoami.exe"
            shutil.copyfile(
                Path(os.environ.get("SystemRoot", r"C:\Windows"))
                / "System32"
                / "whoami.exe",
                executable,
            )
            (child / "fixture.json").write_text("{}", encoding="ascii")
            scratch = root / "scratch"
            scratch.mkdir()
            grants = (
                sandbox.ReadGrant(child, recursive=True),
                # This ancestor-after-child order is legal because the
                # ancestor grant is nonrecursive.  Cleanup must not inherit
                # the request order.
                sandbox.ReadGrant(capsule),
            )
            entries: list[Path] = []
            seen: set[str] = set()
            for grant in grants:
                for entry in sandbox._expand_grant(grant):
                    key = os.path.normcase(str(entry))
                    if key not in seen:
                        seen.add(key)
                        entries.append(entry)
            expected = sorted(
                entries,
                key=lambda path: (
                    len(path.parts),
                    os.path.normcase(str(path)),
                    str(path),
                ),
            )
            original_restore = sandbox._WindowsApi.restore_dacl_propagating
            observed: list[str] = []

            def record_restore(
                windows: sandbox._WindowsApi,
                snapshot: sandbox._SecurityDescriptorSnapshot,
            ) -> None:
                observed.append(snapshot.path)
                original_restore(windows, snapshot)

            with mock.patch.object(
                sandbox._WindowsApi,
                "restore_dacl_propagating",
                new=record_restore,
            ):
                result = sandbox.run_sandboxed(
                    self._request(
                        command=(str(executable),),
                        allowed_read=grants,
                        scratch_directory=scratch,
                        claim_reference="unit-depth-sorted-acl-restore",
                    )
                )
            self.assertEqual(result.return_code, 0)
            self.assertEqual(observed[:-1], [str(path) for path in expected])
            self.assertEqual(observed[-1], str(scratch))

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_child_creation_is_denied_and_scratch_root_cannot_be_mutated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capsule, executable = self._python_capsule(root)
            child = capsule / "child.py"
            child.write_text(
                "import os,sys\n"
                "try:\n"
                " os.spawnv(os.P_WAIT,sys.executable,[sys.executable,'-c','pass'])\n"
                "except OSError as error:\n"
                " os.write(1,b'denied')\n"
                " raise SystemExit(0)\n"
                "raise SystemExit(91)\n",
                encoding="ascii",
            )
            scratch = root / "scratch"
            scratch.mkdir()
            result = sandbox.run_sandboxed(
                self._request(
                    command=(str(executable), "-I", "-S", "-B", str(child)),
                    allowed_read=(sandbox.ReadGrant(capsule, recursive=True),),
                    scratch_directory=scratch,
                    claim_reference="unit-child-process-denied",
                )
            )
            self.assertEqual(result.return_code, 0)
            self.assertEqual(result.stdout, b"denied")
            self.assertEqual(result.total_processes, 1)
            self.assertEqual(result.terminated_processes, 0)

            baseline_attributes = scratch.stat().st_file_attributes
            child.write_text(
                "import os\n"
                "os.mkdir('nested')\n"
                "with open('nested/probe.bin','wb') as stream: stream.write(b'ok')\n"
                "os.remove('nested/probe.bin')\n"
                "os.rmdir('nested')\n"
                "errors=[]\n"
                "for action in (lambda:os.chmod(os.getcwd(),0o777),"
                "lambda:os.rename(os.getcwd(),os.getcwd()+'-moved')):\n"
                " try: action()\n"
                " except OSError as error: errors.append(error.winerror)\n"
                "os.write(1,(','.join(map(str,errors))).encode('ascii'))\n"
                "raise SystemExit(0 if len(errors)==2 else 92)\n",
                encoding="ascii",
            )
            result = sandbox.run_sandboxed(
                self._request(
                    command=(str(executable), "-I", "-S", "-B", str(child)),
                    allowed_read=(sandbox.ReadGrant(capsule, recursive=True),),
                    scratch_directory=scratch,
                    claim_reference="unit-minimal-scratch-rights",
                )
            )
            self.assertEqual(result.return_code, 0)
            self.assertEqual(result.stdout, b"5,5")
            self.assertFalse(any(scratch.iterdir()))
            self.assertEqual(scratch.stat().st_file_attributes, baseline_attributes)

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_cross_process_runs_on_one_recursive_tree_serialize_and_restore(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capsule, executable = self._python_capsule(root)
            child = capsule / "sleep.py"
            child.write_text(
                "import time\ntime.sleep(0.35)\n",
                encoding="ascii",
            )
            scratch = root / "scratch"
            scratch.mkdir()
            start = root / "start"
            ready = (root / "ready-0", root / "ready-1")
            worker = root / "worker.py"
            worker.write_text(
                "import sys,time\n"
                "from pathlib import Path\n"
                "import sandbox_broker as sandbox\n"
                f"capsule=Path({str(capsule)!r})\n"
                f"executable=Path({str(executable)!r})\n"
                f"child=Path({str(child)!r})\n"
                f"scratch=Path({str(scratch)!r})\n"
                f"start=Path({str(start)!r})\n"
                "ready=Path(sys.argv[1])\n"
                "grants=(sandbox.ReadGrant(capsule,recursive=True),)\n"
                "manifest=sandbox.capture_read_identity_manifest("
                "executable=executable,allowed_read=grants)\n"
                "ready.write_text('ready',encoding='ascii')\n"
                "while not start.exists(): time.sleep(0.01)\n"
                "result=sandbox.run_sandboxed(sandbox.SandboxRequest("
                "command=(str(executable),'-I','-S','-B',str(child)),"
                "allowed_read=grants,scratch_directory=scratch,"
                "claim_reference='cross-process-'+ready.name,"
                "expected_read_identity_manifest_sha256=manifest.sha256,"
                "timeout_seconds=15.0))\n"
                "print(result.return_code)\n",
                encoding="utf-8",
            )
            api = sandbox._WindowsApi()
            entries = sandbox._expand_grant(sandbox.ReadGrant(capsule, recursive=True))
            baseline = {
                str(path): api.snapshot_dacl(path) for path in (*entries, scratch)
            }
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(Path(sandbox.__file__).parent)
            processes = [
                subprocess.Popen(
                    [sys.executable, str(worker), str(marker)],
                    cwd=Path(sandbox.__file__).parent,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for marker in ready
            ]
            deadline = time.monotonic() + 30.0
            while not all(marker.exists() for marker in ready):
                failures = [process.poll() for process in processes]
                if any(code is not None for code in failures):
                    diagnostics = [process.communicate() for process in processes]
                    self.fail(
                        f"worker exited before start: {failures!r} {diagnostics!r}"
                    )
                if time.monotonic() >= deadline:
                    for process in processes:
                        process.kill()
                    self.fail("workers did not finish read identity capture")
                time.sleep(0.01)
            start.write_text("start", encoding="ascii")
            observations = [process.communicate(timeout=60.0) for process in processes]
            self.assertEqual([process.returncode for process in processes], [0, 0])
            self.assertEqual(
                [stdout.strip() for stdout, _stderr in observations], ["0", "0"]
            )
            self.assertEqual([stderr for _stdout, stderr in observations], ["", ""])
            self.assertFalse(any(scratch.iterdir()))
            for path, original in baseline.items():
                restored = api.snapshot_dacl(Path(path))
                self.assertEqual(restored.payload, original.payload, path)
                self.assertEqual(restored.control, original.control, path)

    @unittest.skipUnless(os.name == "nt", "classic AppContainer is Windows-only")
    def test_preexit_frame_is_callback_sealed_before_ack_and_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capsule, executable = self._python_capsule(root)
            child = capsule / "child.py"
            child.write_text(
                "import os,msvcrt,sys\n"
                "os.set_handle_inheritable(msvcrt.get_osfhandle(1),False)\n"
                "payload=b'candidate-output'\n"
                "sys.stdout.buffer.write(len(payload).to_bytes(8,'big')+payload)\n"
                "sys.stdout.buffer.flush()\n"
                "os.close(1)\n"
                "ack=sys.stdin.buffer.read()\n"
                "raise SystemExit(0 if ack==b'C0-SEALED-ACK' else 23)\n",
                encoding="ascii",
            )
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
                self._request(
                    command=(str(executable), "-I", "-S", "-B", str(child)),
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

            child.write_text(
                "import os,msvcrt,sys,time\n"
                "os.set_handle_inheritable(msvcrt.get_osfhandle(1),False)\n"
                "payload=b'candidate-output'\n"
                "sys.stdout.buffer.write(len(payload).to_bytes(8,'big')+payload)\n"
                "sys.stdout.buffer.flush()\n"
                "time.sleep(0.05)\n"
                "os.write(1,b'TRAILING')\n"
                "os.close(1)\n"
                "sys.stdin.buffer.read()\n",
                encoding="ascii",
            )
            callbacks.clear()
            with self.assertRaisesRegex(
                sandbox.SandboxError, "bytes after its single frame"
            ):
                sandbox.run_sandboxed(
                    self._request(
                        command=(
                            str(executable),
                            "-I",
                            "-S",
                            "-B",
                            str(child),
                        ),
                        allowed_read=(sandbox.ReadGrant(capsule, recursive=True),),
                        scratch_directory=scratch,
                        claim_reference="unit-preexit-trailing-rejected",
                        timeout_seconds=10.0,
                        stdout_limit_bytes=4096,
                        stderr_limit_bytes=4096,
                        preexit_payload_limit_bytes=1024,
                    ),
                    on_preexit=seal,
                )
            self.assertEqual(callbacks, [])


if __name__ == "__main__":
    unittest.main()
