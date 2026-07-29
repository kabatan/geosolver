"""Parent-owned Python HP runtime shared by optimized solve subprocesses."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import struct
import tempfile
import threading
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from geotarget.hp_preloader import SOCKET_ENV, PersistentHpPool

PROTOCOL = "geotarget.product-runtime-broker/v1"
BROKER_SOCKET_ENV = "GEOTARGET_RUNTIME_BROKER_SOCKET"
BROKER_SESSION_ENV = "GEOTARGET_RUNTIME_BROKER_SESSION"
_HEADER = struct.Struct(">I")


def _read_exact(connection: socket.socket, size: int) -> bytes:
    value = bytearray()
    while len(value) < size:
        chunk = connection.recv(size - len(value))
        if not chunk:
            raise ConnectionError("runtime broker connection closed")
        value.extend(chunk)
    return bytes(value)


def _receive(connection: socket.socket) -> dict[str, Any]:
    size = _HEADER.unpack(_read_exact(connection, _HEADER.size))[0]
    if size > 1024 * 1024:
        raise ValueError("runtime broker message is too large")
    value = json.loads(_read_exact(connection, size))
    if not isinstance(value, dict):
        raise ValueError("runtime broker message must be an object")
    return value


def _send(connection: socket.socket, value: Mapping[str, Any]) -> None:
    payload = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    connection.sendall(_HEADER.pack(len(payload)) + payload)


@dataclass
class _Session:
    cpus: frozenset[int]
    pool_key: tuple[int, ...]
    hp_warm_at_start: bool
    cancelled: threading.Event = field(default_factory=threading.Event)


class ProductRuntimeBroker:
    """Keep immutable Python imports warm; solve state stays in forked children."""

    def __init__(
        self,
        *,
        cpus: Sequence[int],
        hp_worker: Path,
        hp_environment: Mapping[str, str] | None = None,
    ) -> None:
        cpu_tuple = tuple(int(cpu) for cpu in cpus)
        if not cpu_tuple or len(set(cpu_tuple)) != len(cpu_tuple):
            raise ValueError("broker requires distinct CPUs")
        self.cpus = cpu_tuple
        self._hp_worker = Path(hp_worker).resolve()
        self._hp_environment = dict(hp_environment or {})
        self._hp_pools: dict[tuple[int, ...], PersistentHpPool] = {}
        self._hp_lock = threading.Lock()
        self._sessions: dict[str, _Session] = {}
        self._sessions_lock = threading.Lock()
        self._solve_generation = 0
        self._directory = Path(tempfile.mkdtemp(prefix="geotarget-runtime-broker-"))
        os.chmod(self._directory, 0o700)
        self.socket_path = self._directory / "broker.sock"
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        self._server.listen(max(8, len(cpu_tuple) * 2))
        self._closed = threading.Event()
        self._thread = threading.Thread(
            target=self._serve, daemon=True, name="geotarget-runtime-broker"
        )
        self._thread.start()

    def _ensure_hp_pool(self, key: tuple[int, ...]) -> bool:
        with self._hp_lock:
            pool = self._hp_pools.get(key)
            warm = pool is not None and bool(pool.processes)
            if pool is None or pool.closed:
                pool = PersistentHpPool(key, self._hp_worker, self._hp_environment)
                self._hp_pools[key] = pool
                warm = False
            pool.ensure()
            return warm

    def begin_session(self, cpus: Sequence[int]) -> str:
        selected = frozenset(int(cpu) for cpu in cpus)
        if not selected or not selected.issubset(self.cpus):
            raise ValueError("session CPUs are outside the broker reservation")
        key = tuple(sorted(selected))
        warm = self._ensure_hp_pool(key)
        token = secrets.token_urlsafe(32)
        with self._sessions_lock:
            self._solve_generation += 1
            self._sessions[token] = _Session(selected, key, warm)
        return token

    def _session(self, token: str) -> _Session:
        with self._sessions_lock:
            session = self._sessions.get(token)
        if session is None:
            raise KeyError("unknown runtime broker session")
        return session

    def session_environment(self, token: str) -> dict[str, str]:
        session = self._session(token)
        pool = self._hp_pools[session.pool_key]
        return {
            BROKER_SOCKET_ENV: str(self.socket_path),
            BROKER_SESSION_ENV: token,
            SOCKET_ENV: str(pool.directory),
        }

    def session_metadata(self, token: str) -> dict[str, Any]:
        session = self._session(token)
        pool = self._hp_pools.get(session.pool_key)
        return {
            "solve_generation": self._solve_generation,
            "hp_preloader_warm": session.hp_warm_at_start,
            "hp_preloader_processes": len(pool.processes) if pool else 0,
        }

    def cancel_session(self, token: str) -> None:
        session = self._session(token)
        session.cancelled.set()
        with self._hp_lock:
            pool = self._hp_pools.pop(session.pool_key, None)
            if pool is not None:
                pool.close()

    def end_session(self, token: str) -> None:
        with self._sessions_lock:
            self._sessions.pop(token, None)

    def _serve(self) -> None:
        while not self._closed.is_set():
            try:
                connection, _ = self._server.accept()
            except OSError:
                return
            threading.Thread(
                target=self._handle,
                args=(connection,),
                daemon=True,
                name="geotarget-runtime-request",
            ).start()

    def _handle(self, connection: socket.socket) -> None:
        with connection:
            try:
                request = _receive(connection)
                if request.get("schema_version") != PROTOCOL:
                    raise ValueError("runtime broker protocol mismatch")
                session = self._session(str(request["session"]))
                cpu = int(request["cpu"])
                if cpu not in session.cpus:
                    raise PermissionError("CPU is not assigned to this solve session")
                if session.cancelled.is_set():
                    raise InterruptedError("solve session is cancelled")
                if request.get("operation") != "ensure_hp":
                    raise ValueError("unsupported runtime broker operation")
                warm = self._ensure_hp_pool(session.pool_key)
                pool = self._hp_pools[session.pool_key]
                _send(
                    connection,
                    {
                        "schema_version": PROTOCOL,
                        "ok": True,
                        "directory": str(pool.directory),
                        "warm": warm,
                    },
                )
            except BaseException as error:
                with suppress(OSError):
                    _send(
                        connection,
                        {
                            "schema_version": PROTOCOL,
                            "ok": False,
                            "error_type": type(error).__name__,
                            "error": str(error)[:512],
                        },
                    )

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        self._server.close()
        for pool in self._hp_pools.values():
            pool.close()
        self._hp_pools.clear()
        self._thread.join(timeout=1.0)
        shutil.rmtree(self._directory, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()


def ensure_hp_via_broker(cpus: Sequence[int]) -> Path:
    path = os.environ.get(BROKER_SOCKET_ENV)
    token = os.environ.get(BROKER_SESSION_ENV)
    cpu_tuple = tuple(int(cpu) for cpu in cpus)
    if not path or not token or not cpu_tuple:
        raise RuntimeError("runtime broker session is unavailable")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(25.0)
        connection.connect(path)
        _send(
            connection,
            {
                "schema_version": PROTOCOL,
                "operation": "ensure_hp",
                "session": token,
                "cpu": cpu_tuple[0],
            },
        )
        response = _receive(connection)
    if response.get("ok") is not True:
        raise RuntimeError(f"runtime broker HP error: {response.get('error', '')}")
    return Path(str(response["directory"]))
