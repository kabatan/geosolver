#!/usr/bin/env python3
"""Exec a child with Linux parent-death SIGKILL containment."""

from __future__ import annotations

import argparse
import ctypes
import os
import signal


PR_SET_PDEATHSIG = 1


def arm_parent_death_signal(expected_parent_pid: int) -> None:
    """Kill this process if its exact current parent exits."""

    if os.getppid() != expected_parent_pid:
        raise RuntimeError("expected parent exited before child containment")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    # Close the race where the parent exits between the first check and prctl.
    if os.getppid() != expected_parent_pid:
        os.kill(os.getpid(), signal.SIGKILL)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = list(arguments.command)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        raise SystemExit("missing command")
    try:
        arm_parent_death_signal(arguments.parent_pid)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
