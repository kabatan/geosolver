"""Minimal candidate-private containment; not a reusable runner."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import Any


PR_SET_PDEATHSIG = 1
HERE = Path(__file__).resolve().parent


def _child_setup() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_PDEATHSIG) failed")


def run_contained(request: dict[str, Any], timeout_seconds: float = 3.0) -> dict[str, Any]:
    if os.sched_getaffinity(0) != {15}:
        raise RuntimeError("D0 must be pinned exclusively to CPU15")
    parent_pgid = os.getpgid(0)
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "worker.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=False,
        preexec_fn=_child_setup,
        cwd=HERE,
    )
    try:
        stdout, stderr = proc.communicate(json.dumps(request), timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return {"timed_out": True, "authority_pass": False}
    if proc.returncode != 0:
        return {"crash": True, "authority_pass": False, "stderr": stderr[-1000:]}
    output = json.loads(stdout)
    containment = output["containment"]
    containment["same_process_group"] = containment["pgid"] == parent_pgid
    containment["start_new_session"] = False
    containment["timed_out"] = False
    return output
