from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any

import psutil

_POPEN_TYPE = subprocess.Popen


def available_physical_cores() -> int:
    return max(1, psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 1)


def default_memory_limit_bytes() -> int:
    available = int(psutil.virtual_memory().available)
    return max(1024**3, int(available * 0.8))


def process_tree_memory_bytes(process_id: int) -> int:
    try:
        root = psutil.Process(process_id)
        processes = [root, *root.children(recursive=True)]
    except psutil.Error:
        return 0
    total = 0
    for process in processes:
        try:
            total += int(process.memory_info().rss)
        except psutil.Error:
            continue
    return total


def spawn_process(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout: IO[Any] | int | None = subprocess.PIPE,
    stderr: IO[Any] | int | None = subprocess.PIPE,
    stdin: IO[Any] | int | None = None,
) -> subprocess.Popen[str]:
    options: dict[str, Any] = {
        "cwd": str(cwd),
        "env": env,
        "stdout": stdout,
        "stderr": stderr,
        "stdin": stdin,
        "text": True,
        "encoding": "utf-8",
    }
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    job = None
    if os.name == "nt":
        from geosolver.platform.windows_job import WindowsJob

        job = WindowsJob()
        command = [sys.executable, "-m", "geosolver.runtime.process_gate", job.event_name, *command]
    try:
        process = subprocess.Popen(list(command), **options)
        if job is not None:
            try:
                job.assign_and_release(process.pid)
                process._geosolver_job = job
            except BaseException:
                process.kill()
                process.wait()
                raise
    except BaseException:
        if job is not None:
            job.close()
        raise
    if isinstance(process, _POPEN_TYPE):
        process._geosolver_owned_group = True
    return process


def set_affinity(process_id: int, cores: int) -> None:
    if sys.platform == "darwin":
        return
    try:
        process = psutil.Process(process_id)
        eligible = process.cpu_affinity()
        if eligible:
            process.cpu_affinity(eligible[: max(1, min(cores, len(eligible)))])
    except (AttributeError, OSError, psutil.Error):
        return


def terminate_process_tree(process: subprocess.Popen[str], grace_seconds: float = 2.0) -> None:
    job = getattr(process, "_geosolver_job", None)
    if job is not None:
        job.close()
        process.wait(timeout=max(0.1, grace_seconds))
        return
    if process.poll() is not None and not getattr(process, "_geosolver_owned_group", False):
        return
    try:
        root = psutil.Process(process.pid)
        descendants = root.children(recursive=True)
    except psutil.Error:
        descendants = []
        root = None
    if sys.platform != "win32":
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGTERM)
    else:
        for child in descendants:
            with contextlib.suppress(psutil.Error):
                child.terminate()
        if root is not None:
            with contextlib.suppress(psutil.Error):
                root.terminate()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=grace_seconds)
    targets = descendants + ([] if root is None else [root])
    for target in targets:
        with contextlib.suppress(psutil.Error):
            target.kill()
    if sys.platform != "win32":
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=max(0.1, grace_seconds))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=max(0.1, grace_seconds))
