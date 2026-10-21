"""One lazy, reusable symbolic subprocess per solve, sharing its deadline."""

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import ExitStack
from contextvars import ContextVar
from pathlib import Path

from geosolver.platform.processes import spawn_process, terminate_process_tree

_client = ContextVar("symbolic_client", default=None)


class OptionalSymbolicTimeout(TimeoutError):
    """Optional work exhausted its own budget; the solve may continue."""


class SymbolicClient:
    def __init__(self, deadline):
        self.deadline = deadline
        self._reset_worker_state()

    def _reset_worker_state(self):
        self.process = None
        self.output = queue.Queue()
        self.closed = False
        self.log = None
        self.resources = ExitStack()

    def _start(self):
        self.log = self.resources.enter_context(
            tempfile.TemporaryFile(mode="w+", encoding="utf-8")  # noqa: SIM115 - ExitStack owns it
        )
        env = os.environ.copy()
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            env[name] = "1"
        env["GEOSOLVER_SYMBOLIC_PARENT"] = str(os.getpid())
        self.process = spawn_process(
            [sys.executable, "-m", "geosolver.runtime.symbolic_worker"],
            cwd=Path.cwd(),
            env=env,
            stdin=subprocess.PIPE,
            stderr=self.log,
        )
        process = self.process
        output = self.output

        def drain():
            try:
                for line in process.stdout:
                    output.put(line)
            finally:
                output.put(None)

        self.reader = threading.Thread(target=drain, daemon=True)
        self.reader.start()

    def call(self, operation, payload, *, timeout_seconds=None):
        from geosolver.runtime.deadline import check_deadline, current_deadline

        check_deadline(self.deadline)
        optional_deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
        if self.closed:
            raise TimeoutError("symbolic worker is closed")
        if self.process is None:
            self._start()
        request = {"operation": operation, "payload": payload, "deadline": current_deadline()}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        global_limits = [d for d in (self.deadline, current_deadline()) if d is not None]
        limits = [*global_limits, *([] if optional_deadline is None else [optional_deadline])]
        remaining = max(0, min(limits) - time.monotonic()) if limits else None
        try:
            line = self.output.get(timeout=remaining)
        except queue.Empty as exc:
            optional_expired = optional_deadline is not None and (
                not global_limits or optional_deadline < min(global_limits)
            )
            self.close()
            check_deadline(self.deadline)
            if optional_expired:
                # The session owns this same client through final cleanup. A
                # fresh queue and captured drain queue prevent an old reader's
                # final sentinel from contaminating the restarted worker.
                self._reset_worker_state()
                raise OptionalSymbolicTimeout("optional symbolic work limit reached") from exc
            raise TimeoutError("symbolic computation reached solve deadline") from exc
        if line is None:
            self.close()
            raise RuntimeError("symbolic worker exited without a result")
        result = json.loads(line)
        if "error" in result:
            if result.get("error_type") == "TimeoutError":
                raise TimeoutError(result["error"])
            raise ValueError(result["error"])
        return result["result"]

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.process is not None:
            try:
                try:
                    terminate_process_tree(self.process, grace_seconds=0.1)
                except Exception:
                    # A transient cleanup failure must not leave the old child
                    # running alongside a replacement worker.
                    terminate_process_tree(self.process, grace_seconds=0.1)
            finally:
                try:
                    self.process.stdin.close()
                finally:
                    self.reader.join(timeout=0.2)
                    self.process.stdout.close()
                    self.resources.close()
        else:
            self.resources.close()


def request(operation, payload, *, timeout_seconds=None):
    client = _client.get()
    if client is not None:
        return client.call(operation, payload, timeout_seconds=timeout_seconds)
    # Pure algorithm unit tests need not create processes. Production always
    # enters runtime_session, which owns the reusable, deadline-bound child.
    from geosolver.runtime.symbolic_operations import dispatch

    return dispatch(operation, payload)
