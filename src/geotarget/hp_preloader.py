"""Per-core, fork-isolated preloader for the optimized frozen HP worker."""

from __future__ import annotations

import argparse
import atexit
import hashlib
import importlib.util
import json
import os
import resource
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import traceback
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path
from typing import Any

SOCKET_ENV = "GEOTARGET_HP_PRELOADER_DIRECTORY"
PROTOCOL = "geotarget.hp-preloader/v1"
THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "GOTO_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "JULIA_NUM_PRECOMPILE_TASKS": "1",
    "JULIA_PKG_PRECOMPILE_AUTO": "0",
    "RAYON_NUM_THREADS": "1",
    "MALLOC_ARENA_MAX": "2",
}
_HEADER = struct.Struct(">I")
_ACTIVE_CHILD = 0


def socket_path(directory: Path, cpu: int) -> Path:
    return directory / f"cpu-{cpu:03d}.sock"


class PersistentHpPool:
    """Own one restartable preloader process for every selected physical CPU."""

    def __init__(self, cpus: Sequence[int], worker: Path, environment: Mapping[str, str]):
        self.cpus = tuple(int(cpu) for cpu in cpus)
        self.worker = Path(worker).resolve()
        self.environment = {str(key): str(value) for key, value in environment.items()}
        self.directory = Path(tempfile.mkdtemp(prefix="geotarget-hp-preload-"))
        os.chmod(self.directory, 0o700)
        self.processes: dict[int, subprocess.Popen[bytes]] = {}
        self.closed = False

    def __enter__(self):
        if self.closed:
            raise RuntimeError("HP preloader pool is closed")
        self.ensure()
        return self

    def _start(self, cpu: int) -> None:
        path = socket_path(self.directory, cpu)
        path.unlink(missing_ok=True)
        environment = {**os.environ, **self.environment, **THREAD_ENV}
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--socket",
                str(path),
                "--cpu",
                str(cpu),
                "--worker",
                str(self.worker),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=False,
        )
        self.processes[cpu] = process
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                error = (process.stderr.read() if process.stderr else b"").decode(errors="replace")
                raise RuntimeError(f"HP preloader failed for CPU {cpu}: {error[-2000:]}")
            if path.exists():
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                        connection.settimeout(0.25)
                        connection.connect(str(path))
                        _send(connection, {"schema_version": PROTOCOL, "operation": "ping"})
                        if _receive(connection).get("ok") is True:
                            return
                except OSError:
                    pass
            time.sleep(0.02)
        process.terminate()
        raise RuntimeError(f"HP preloader readiness timeout for CPU {cpu}")

    def ensure(self) -> None:
        if self.closed:
            raise RuntimeError("HP preloader pool is closed")
        for cpu in self.cpus:
            process = self.processes.get(cpu)
            if (
                process is None
                or process.poll() is not None
                or not socket_path(self.directory, cpu).exists()
            ):
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=2.0)
                self._start(cpu)

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for process in self.processes.values():
            if process.poll() is None:
                process.terminate()
        for process in self.processes.values():
            try:
                process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            if process.stderr:
                process.stderr.close()
        shutil.rmtree(self.directory, ignore_errors=True)

    def close_at_process_exit(self) -> None:
        atexit.register(self.close)


def _send(connection: socket.socket, value: Mapping[str, Any]) -> None:
    payload = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    connection.sendall(_HEADER.pack(len(payload)) + payload)


def _receive(connection: socket.socket) -> dict[str, Any]:
    header = _read_exact(connection, _HEADER.size)
    size = _HEADER.unpack(header)[0]
    if size > 8 * 1024 * 1024:
        raise ValueError("HP preloader request is too large")
    value = json.loads(_read_exact(connection, size))
    if not isinstance(value, dict):
        raise ValueError("HP preloader message must be an object")
    return value


def _read_exact(connection: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = connection.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("HP preloader connection closed")
        chunks.extend(chunk)
    return bytes(chunks)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _prepare(worker: Path, cpu: int):
    """Reproduce the frozen POC wrapper's setup before any candidate fork."""
    wrapper = _load("geotarget_product_hp_poc_wrapper", worker)
    observed = hashlib.sha256(wrapper.BASE_WORKER.read_bytes()).hexdigest()
    if observed != wrapper.EXPECTED_BASE_SHA256:
        raise RuntimeError("adaptive HP composition worker digest changed")
    os.environ["GEOTARGET_ADAPTIVE_HP_ENABLE_FRESH_1280"] = "0"
    base = _load("geotarget_point_on_circle_adaptive_worker_base", wrapper.BASE_WORKER)
    integration = _load(
        "geotarget_point_on_circle_adaptive_worker_integration", wrapper.INTEGRATION
    )
    base.MANIFEST_PATH = wrapper.MANIFEST
    original_load = base._load

    def repaired_load(name: str, path: Path):
        module = original_load(name, path)
        if Path(path).resolve() == Path(base.ADAPTER_PATH).resolve():
            integration.install(module)
        return module

    base._load = repaired_load
    # Load the candidate-independent closure once.  The frozen main() still
    # verifies its manifest and configuration in every fork before authority
    # work, so this changes startup cost rather than the authority boundary.
    base._load(
        "geotarget_exp_v15_243_adaptive_hp_worker_manifest",
        base.MANIFEST_PATH,
    )
    base._load(
        "geotarget_exp_v15_243_adaptive_hp_champion_adapter",
        base.CHAMPION_ADAPTER_PATH,
    )
    base._load(
        "geotarget_exp_v15_243_adaptive_hp_implementation",
        base.ADAPTER_PATH,
    )
    base._load(
        "geotarget_exp_v15_243_adaptive_hp_champion_compatibility",
        base.CHAMPION_COMPAT_PATH,
    )
    return base.main


def _rss(process_group: int) -> int | None:
    pages = count = 0
    try:
        entries = os.scandir("/proc")
    except OSError:
        return None
    with entries:
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                fields = Path(entry.path, "stat").read_text(encoding="ascii")
                after = fields[fields.rfind(")") + 2 :].split()
                if len(after) < 3 or int(after[2]) != process_group:
                    continue
                pages += int(Path(entry.path, "statm").read_text().split()[1])
                count += 1
            except (OSError, ValueError, IndexError):
                continue
    return pages * os.sysconf("SC_PAGE_SIZE") if count else None


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _kill_group(pgid: int, grace: float) -> None:
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and _group_exists(pgid):
        time.sleep(0.01)
    if _group_exists(pgid):
        with suppress(ProcessLookupError):
            os.killpg(pgid, signal.SIGKILL)


def _tail(path: Path, size: int) -> tuple[int, str]:
    try:
        total = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(0, total - size))
            return total, handle.read().decode("utf-8", errors="replace")
    except OSError:
        return 0, ""


def _run_forked(request: Mapping[str, Any], worker: Path, prepared_main) -> dict[str, Any]:
    global _ACTIVE_CHILD
    command = [str(value) for value in request["command"]]
    limits = dict(request["limits"])
    cpu = int(request["cpu"])
    if len(command) < 5 or command[:3] != ["taskset", "-c", str(cpu)]:
        raise ValueError("unexpected HP worker command prefix")
    if Path(command[4]).resolve() != worker.resolve():
        raise ValueError("unexpected HP worker path")
    environment = dict(os.environ) if request.get("inherit_environment", True) else {}
    environment.update({str(k): str(v) for k, v in request.get("environment", {}).items()})
    environment.update(THREAD_ENV)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="geotarget-hp-fork-") as temporary:
        stdout_path, stderr_path = Path(temporary, "stdout"), Path(temporary, "stderr")
        pid = os.fork()
        if pid == 0:
            try:
                os.setsid()
                signal.signal(signal.SIGTERM, signal.SIG_DFL)
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                os.sched_setaffinity(0, {cpu})
                resource.setrlimit(resource.RLIMIT_AS, (int(limits["address_space_bytes"]),) * 2)
                resource.setrlimit(resource.RLIMIT_DATA, (int(limits["data_bytes"]),) * 2)
                os.environ.clear()
                os.environ.update(environment)
                if request.get("cwd"):
                    os.chdir(str(request["cwd"]))
                stdin = os.open(os.devnull, os.O_RDONLY)
                stdout = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                stderr = os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                os.dup2(stdin, 0)
                os.dup2(stdout, 1)
                os.dup2(stderr, 2)
                sys.argv = [str(worker), *command[5:]]
                code = 0
                try:
                    prepared_main()
                except SystemExit as exit_error:
                    code = exit_error.code if isinstance(exit_error.code, int) else 1
                except BaseException:
                    traceback.print_exc()
                    code = 1
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(code)
            except BaseException:
                traceback.print_exc()
                os._exit(78)
        _ACTIVE_CHILD = pid
        deadline = started + float(limits["timeout_seconds"])
        peak = 0
        timeout = rss_failed = rss_exceeded = output_exceeded = False
        status = None
        while status is None:
            waited, raw_status = os.waitpid(pid, os.WNOHANG)
            now = time.monotonic()
            if waited:
                status = raw_status
                if now >= deadline:
                    timeout = True
                break
            observed = _rss(pid)
            if observed is None:
                rss_failed = True
                break
            peak = max(peak, observed)
            if observed > int(limits["rss_bytes"]):
                rss_exceeded = True
                break
            out_size = stdout_path.stat().st_size if stdout_path.exists() else 0
            err_size = stderr_path.stat().st_size if stderr_path.exists() else 0
            if (
                out_size > int(limits["output_bytes"])
                or err_size > int(limits["output_bytes"])
                or out_size + err_size > int(limits["output_bytes"])
            ):
                output_exceeded = True
                break
            if now >= deadline:
                timeout = True
                break
            time.sleep(min(float(limits["poll_seconds"]), max(0.0, deadline - now)))
        descendant_leak = status is not None and _group_exists(pid)
        if (
            status is None
            or timeout
            or rss_failed
            or rss_exceeded
            or output_exceeded
            or descendant_leak
        ):
            _kill_group(pid, float(limits["terminate_grace_seconds"]))
            with suppress(ChildProcessError):
                _, status = os.waitpid(pid, 0)
        returncode = os.waitstatus_to_exitcode(status) if status is not None else None
        stdout_bytes, stdout_tail = _tail(stdout_path, int(limits["tail_bytes"]))
        stderr_bytes, stderr_tail = _tail(stderr_path, int(limits["tail_bytes"]))
        output_exceeded |= stdout_bytes + stderr_bytes > int(limits["output_bytes"])
        if timeout:
            classification = "TIMEOUT"
        elif rss_exceeded:
            classification = "RSS_LIMIT_EXCEEDED"
        elif rss_failed:
            classification = "RSS_MONITOR_FAILED"
        elif output_exceeded:
            classification = "OUTPUT_LIMIT_EXCEEDED"
        elif descendant_leak:
            classification = "DESCENDANT_LEAK"
        elif returncode == 78:
            classification = "LIMIT_SETUP_FAILED"
        elif returncode != 0:
            classification = "NONZERO_EXIT"
        else:
            classification = "SUCCESS"
        result = {
            "schema_version": "geotarget.memory-safe-subprocess/v1",
            "classification": classification,
            "accepted_output": classification == "SUCCESS",
            "command": command,
            "returncode": returncode,
            "elapsed_seconds": time.monotonic() - started,
            "peak_process_group_rss_bytes": peak,
            "timeout": timeout,
            "rss_cap_exceeded": rss_exceeded,
            "rss_monitor_failed": rss_failed,
            "output_cap_exceeded": output_exceeded,
            "descendant_leak": descendant_leak,
            "resource_limit_failure_possible": classification == "NONZERO_EXIT",
            "stdout_bytes": stdout_bytes,
            "stderr_bytes": stderr_bytes,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "limits": limits,
        }
        _ACTIVE_CHILD = 0
        return result


def serve(path: Path, cpu: int, worker: Path) -> None:
    os.environ.update(THREAD_ENV)
    os.sched_setaffinity(0, {cpu})
    prepared_main = _prepare(worker, cpu)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    os.chmod(path, 0o600)
    server.listen(4)

    def stop(_signum, _frame):
        if _ACTIVE_CHILD:
            _kill_group(_ACTIVE_CHILD, 0.25)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while True:
            connection, _ = server.accept()
            with connection:
                request = _receive(connection)
                if request.get("schema_version") != PROTOCOL:
                    raise ValueError("HP preloader protocol mismatch")
                if request.get("operation") == "ping":
                    _send(connection, {"schema_version": PROTOCOL, "ok": True})
                else:
                    _send(
                        connection,
                        {
                            "schema_version": PROTOCOL,
                            "result": _run_forked(request, worker, prepared_main),
                        },
                    )
    finally:
        server.close()
        path.unlink(missing_ok=True)


def delegated_run(
    command: Sequence[str],
    *,
    limits: Any,
    environment=None,
    cwd=None,
    status_path=None,
    inherit_environment=True,
    pass_fds=(),
    original=None,
):
    """Drop-in replacement for `_run_guarded_reserved`, with safe fallback."""
    directory = os.environ.get(SOCKET_ENV)
    command = [str(value) for value in command]
    dispatched = False
    broker_required = bool(os.environ.get("GEOTARGET_RUNTIME_BROKER_SESSION"))
    try:
        cpu = int(command[2])
        path = socket_path(Path(str(directory)), cpu)
        if pass_fds or command[:2] != ["taskset", "-c"]:
            raise ValueError
        request = {
            "schema_version": PROTOCOL,
            "operation": "run",
            "cpu": cpu,
            "command": command,
            "limits": asdict(limits),
            "environment": {
                **dict(environment or {}),
                **{
                    name: os.environ[name]
                    for name in (
                        "GEOTARGET_RUNTIME_BROKER_SOCKET",
                        "GEOTARGET_RUNTIME_BROKER_SESSION",
                    )
                    if name in os.environ
                },
            },
            "cwd": str(cwd) if cwd else None,
            "inherit_environment": bool(inherit_environment),
        }
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(float(limits.timeout_seconds) + 5.0)
            connection.connect(str(path))
            _send(connection, request)
            dispatched = True
            response = _receive(connection)
        result = response["result"]
        safe = sys.modules["research.infrastructure.memory_safety.safe_subprocess"]
        value = safe.RunResult(**result)
        if status_path is not None:
            safe.atomic_write_json(status_path, value.to_dict())
        return value
    except Exception as error:
        if dispatched or broker_required:
            safe = sys.modules["research.infrastructure.memory_safety.safe_subprocess"]
            value = safe.RunResult(
                schema_version="geotarget.memory-safe-subprocess/v1",
                classification="PRELOADER_ERROR",
                accepted_output=False,
                command=command,
                returncode=None,
                elapsed_seconds=0.0,
                peak_process_group_rss_bytes=0,
                timeout=False,
                rss_cap_exceeded=False,
                rss_monitor_failed=True,
                output_cap_exceeded=False,
                descendant_leak=True,
                resource_limit_failure_possible=True,
                stdout_bytes=0,
                stderr_bytes=0,
                stdout_tail="",
                stderr_tail=str(error),
                limits=asdict(limits),
            )
            if status_path is not None:
                safe.atomic_write_json(status_path, value.to_dict())
            return value
        if original is None:
            raise
        return original(
            command,
            limits=limits,
            environment=environment,
            cwd=cwd,
            status_path=status_path,
            inherit_environment=inherit_environment,
            pass_fds=pass_fds,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    args = parser.parse_args()
    serve(args.socket, args.cpu, args.worker)


if __name__ == "__main__":
    main()
