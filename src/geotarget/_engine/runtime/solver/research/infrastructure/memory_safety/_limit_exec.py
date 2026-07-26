"""Apply process resource limits and replace this process with a command.

This module is an implementation detail of ``safe_subprocess.py``.  Keeping
``setrlimit`` in a tiny launcher avoids Python's unsafe ``preexec_fn`` path
when a research runner happens to use threads.
"""

from __future__ import annotations

import argparse
import os
import resource
import sys


LIMIT_SETUP_EXIT = 78
EXEC_FAILURE_EXIT = 127


def _set_limit(name: str, value: int) -> None:
    if value <= 0:
        return
    resource_name = f"RLIMIT_{name}"
    if not hasattr(resource, resource_name):
        raise RuntimeError(f"{resource_name} is unavailable")
    key = getattr(resource, resource_name)
    _soft, hard = resource.getrlimit(key)
    if hard != resource.RLIM_INFINITY:
        value = min(value, hard)
    resource.setrlimit(key, (value, value))


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--as-bytes", type=int, default=0)
    parser.add_argument("--data-bytes", type=int, default=0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = list(arguments.command)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        print("MEMSAFE_EXEC_ERROR: no command", file=sys.stderr)
        raise SystemExit(EXEC_FAILURE_EXIT)

    try:
        _set_limit("AS", arguments.as_bytes)
        _set_limit("DATA", arguments.data_bytes)
        if hasattr(resource, "RLIMIT_CORE"):
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"MEMSAFE_LIMIT_SETUP_ERROR: {error}", file=sys.stderr)
        raise SystemExit(LIMIT_SETUP_EXIT) from error

    try:
        os.execvpe(command[0], command, os.environ)
    except OSError as error:
        print(f"MEMSAFE_EXEC_ERROR: {error}", file=sys.stderr)
        raise SystemExit(EXEC_FAILURE_EXIT) from error


if __name__ == "__main__":
    main()
