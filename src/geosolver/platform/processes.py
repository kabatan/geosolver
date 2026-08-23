from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any

import psutil


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
) -> subprocess.Popen[str]:
    options: dict[str, Any] = {
        "cwd": str(cwd),
        "env": env,
        "stdout": stdout,
        "stderr": stderr,
        "text": True,
        "encoding": "utf-8",
    }
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(list(command), **options)


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
    if process.poll() is not None:
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
    try:
        process.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    targets = descendants + ([] if root is None else [root])
    for target in targets:
        with contextlib.suppress(psutil.Error):
            target.kill()
    try:
        process.wait(timeout=max(0.1, grace_seconds))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=max(0.1, grace_seconds))


def wait_interval(deadline: float, maximum: float = 0.05) -> None:
    remaining = deadline - time.monotonic()
    if remaining > 0:
        time.sleep(min(maximum, remaining))
