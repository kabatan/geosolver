#!/usr/bin/env python3
"""Validate the pinned GeoTarget developer toolchain and repository identity."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, Sequence


ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN_FILE = ROOT / "toolchain.toml"


class DoctorError(RuntimeError):
    """Raised when the local environment does not satisfy the repository contract."""


@dataclass(frozen=True)
class Environment:
    root: Path
    git: str
    julia: str
    uv: str
    julia_version: str
    python_version: str
    uv_version: str
    git_version: str


def _fail(message: str) -> NoReturn:
    raise DoctorError(message)


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.search(r"\d+(?:\.\d+)+", value)
    if match is None:
        _fail(f"Could not parse a version from {value!r}.")
    return tuple(int(part) for part in match.group(0).split("."))


def _find_command(name: str, *user_relative_candidates: str) -> str:
    discovered = shutil.which(name)
    if discovered is not None:
        return discovered
    for relative in user_relative_candidates:
        candidate = Path.home() / relative
        if candidate.is_file():
            return str(candidate.resolve())
    _fail(f"Required command {name!r} was not found.")


def _capture(command: Sequence[str], *, label: str) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stdout", None)
        suffix = (
            f": {detail.strip()}" if isinstance(detail, str) and detail.strip() else ""
        )
        _fail(f"{label} failed{suffix}")
    return completed.stdout.strip()


def check_environment() -> Environment:
    """Check the environment and return resolved executable paths for CI."""

    with TOOLCHAIN_FILE.open("rb") as handle:
        contract = tomllib.load(handle)

    expected_julia = str(contract["julia"]["version"])
    julia_channel = str(contract["julia"]["channel"])
    expected_python = _version_tuple(str(contract["python"]["tested"]))
    expected_uv = str(contract["tools"]["uv"])
    minimum_git = _version_tuple(str(contract["tools"]["git_minimum"]))

    git = _find_command("git")
    julia = _find_command(
        "julia",
        ".juliaup/bin/julia.exe" if sys.platform == "win32" else ".juliaup/bin/julia",
    )
    uv = _find_command(
        "uv", ".local/bin/uv.exe" if sys.platform == "win32" else ".local/bin/uv"
    )

    julia_output = _capture(
        [
            julia,
            f"+{julia_channel}",
            "--startup-file=no",
            "--history-file=no",
            "--version",
        ],
        label="Julia discovery",
    )
    expected_julia_output = f"julia version {expected_julia}"
    if julia_output != expected_julia_output:
        _fail(f"Expected Julia {expected_julia}, got {julia_output!r}.")

    running_python = sys.version_info[:3]
    if running_python != expected_python:
        _fail(
            "Expected the doctor runner to use Python "
            f"{'.'.join(map(str, expected_python))}, got "
            f"{'.'.join(map(str, running_python))}."
        )
    python_version = ".".join(map(str, running_python))

    uv_output = _capture([uv, "--version"], label="uv discovery")
    uv_version = ".".join(map(str, _version_tuple(uv_output)))
    if uv_version != expected_uv:
        _fail(f"Expected uv {expected_uv}, got {uv_output!r}.")

    git_output = _capture([git, "--version"], label="Git discovery")
    git_version_tuple = _version_tuple(git_output)
    if git_version_tuple < minimum_git:
        _fail(f"Expected Git >= {'.'.join(map(str, minimum_git))}, got {git_output!r}.")
    git_version = ".".join(map(str, git_version_tuple))

    reported_root = Path(
        _capture(
            [git, "-C", str(ROOT), "rev-parse", "--show-toplevel"],
            label="Git root check",
        )
    ).resolve()
    if reported_root != ROOT:
        _fail(f"Repository root mismatch: expected {ROOT!s}, got {reported_root!s}.")

    remotes = _capture([git, "-C", str(ROOT), "remote"], label="Git remote check")
    if remotes:
        _fail(f"Bootstrap repository must not have a remote; found: {remotes!r}.")

    return Environment(
        root=ROOT,
        git=git,
        julia=julia,
        uv=uv,
        julia_version=expected_julia,
        python_version=python_version,
        uv_version=uv_version,
        git_version=git_version,
    )


def main() -> int:
    try:
        environment = check_environment()
    except (DoctorError, KeyError, OSError, tomllib.TOMLDecodeError) as error:
        print(f"GeoTarget doctor: FAILED: {error}", file=sys.stderr)
        return 1
    print(
        "GeoTarget doctor: OK "
        f"(Julia {environment.julia_version}, Python {environment.python_version}, "
        f"uv {environment.uv_version}, Git {environment.git_version}, no remotes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
