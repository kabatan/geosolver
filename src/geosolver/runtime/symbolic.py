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


class SymbolicClient:
    def __init__(self, deadline):
        self.deadline = deadline
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

        def drain():
            try:
                for line in process.stdout:
                    self.output.put(line)
            finally:
                self.output.put(None)

        self.reader = threading.Thread(target=drain, daemon=True)
        self.reader.start()

    def call(self, operation, payload):
        from geosolver.runtime.deadline import check_deadline, current_deadline

        check_deadline(self.deadline)
        if self.closed:
            raise TimeoutError("symbolic worker is closed")
        if self.process is None:
            self._start()
        request = {"operation": operation, "payload": payload, "deadline": current_deadline()}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        limits = [d for d in (self.deadline, current_deadline()) if d is not None]
        remaining = max(0, min(limits) - time.monotonic()) if limits else None
        try:
            line = self.output.get(timeout=remaining)
        except queue.Empty as exc:
            self.close()
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
            terminate_process_tree(self.process, grace_seconds=0.1)
            self.process.stdin.close()
            self.reader.join(timeout=0.2)
            self.process.stdout.close()
        self.resources.close()


def request(operation, payload):
    client = _client.get()
    if client is not None:
        return client.call(operation, payload)
    # Pure algorithm unit tests need not create processes. Production always
    # enters runtime_session, which owns the reusable, deadline-bound child.
    from geosolver.runtime.symbolic_operations import dispatch

    return dispatch(operation, payload)
