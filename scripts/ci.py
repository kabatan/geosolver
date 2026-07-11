#!/usr/bin/env python3
"""Cross-platform source of truth for the GeoTarget repository gates."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from doctor import DoctorError, Environment, check_environment


ROOT = Path(__file__).resolve().parents[1]
JULIA_PROJECT = ROOT / "julia"
BENCHMARK_PROJECT = JULIA_PROJECT / "GeoTargetBenchmarks"
EXACT_PROJECT = JULIA_PROJECT / "GeoTargetExact"
TIERS = ("Smoke", "Pr", "Nightly")


class CiError(RuntimeError):
    """Raised when a repository gate fails."""


def _tier(value: str) -> str:
    normalized = value.casefold()
    for candidate in TIERS:
        if candidate.casefold() == normalized:
            return candidate
    raise argparse.ArgumentTypeError(f"tier must be one of {', '.join(TIERS)}")


def _run(command: Sequence[str], *, label: str, environment: dict[str, str]) -> None:
    print(f"==> {label}", flush=True)
    try:
        subprocess.run(command, cwd=ROOT, env=environment, check=True)
    except OSError as error:
        raise CiError(f"{label} could not start: {error}") from error
    except subprocess.CalledProcessError as error:
        raise CiError(f"{label} failed with exit code {error.returncode}") from error


def _julia_command(tools: Environment, *arguments: str) -> list[str]:
    return [
        tools.julia,
        f"+{tools.julia_version}",
        "--startup-file=no",
        "--history-file=no",
        *arguments,
    ]


def run_ci(tier: str) -> None:
    tools = check_environment()
    print(
        "GeoTarget doctor: OK "
        f"(Julia {tools.julia_version}, Python {tools.python_version}, "
        f"uv {tools.uv_version}, Git {tools.git_version}, no remotes)",
        flush=True,
    )

    environment = os.environ.copy()
    environment["JULIA_NUM_THREADS"] = "1"
    environment["OPENBLAS_NUM_THREADS"] = "1"

    _run(
        [sys.executable, str(ROOT / "scripts" / "governance_lint.py")],
        label="Governance lint",
        environment=environment,
    )
    _run(
        [sys.executable, str(ROOT / "scripts" / "architecture_lint.py")],
        label="Architecture lint",
        environment=environment,
    )
    _run(
        [sys.executable, str(ROOT / "research" / "validate.py")],
        label="Research contract validation",
        environment=environment,
    )
    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(ROOT / "research" / "tests"),
            "-v",
        ],
        label="Research harness tests",
        environment=environment,
    )

    _run(
        _julia_command(
            tools,
            f"--project={JULIA_PROJECT}",
            "-e",
            "using Pkg; Pkg.instantiate()",
        ),
        label="Julia instantiate",
        environment=environment,
    )
    _run(
        _julia_command(
            tools,
            f"--project={JULIA_PROJECT}",
            str(JULIA_PROJECT / "integration" / "runtests.jl"),
        ),
        label="Julia tests",
        environment=environment,
    )
    _run(
        _julia_command(
            tools,
            f"--project={EXACT_PROJECT}",
            "-e",
            "using Pkg; Pkg.instantiate(); Pkg.test()",
        ),
        label="Optional exact-backend tests",
        environment=environment,
    )

    benchmark_expression = (
        "using Pkg; Pkg.instantiate(); using GeoTargetBenchmarks"
        if tier == "Smoke"
        else "using Pkg; Pkg.instantiate(); Pkg.test()"
    )
    _run(
        _julia_command(
            tools,
            f"--project={BENCHMARK_PROJECT}",
            "-e",
            benchmark_expression,
        ),
        label="Analytic benchmark tests",
        environment=environment,
    )

    python_project = ROOT / "python"
    _run(
        [
            tools.uv,
            "sync",
            "--project",
            str(python_project),
            "--frozen",
            "--group",
            "dev",
        ],
        label="Python environment sync",
        environment=environment,
    )
    _run(
        [
            tools.uv,
            "run",
            "--project",
            str(python_project),
            "ruff",
            "format",
            "--check",
            str(python_project),
        ],
        label="ruff format check",
        environment=environment,
    )
    _run(
        [
            tools.uv,
            "run",
            "--project",
            str(python_project),
            "ruff",
            "check",
            str(python_project),
        ],
        label="ruff check",
        environment=environment,
    )
    _run(
        [
            tools.uv,
            "run",
            "--project",
            str(python_project),
            "mypy",
            str(python_project / "src"),
        ],
        label="mypy",
        environment=environment,
    )
    _run(
        [
            tools.uv,
            "run",
            "--project",
            str(python_project),
            "pytest",
            str(python_project / "tests"),
        ],
        label="pytest",
        environment=environment,
    )

    qa02_arguments = {
        "Smoke": [
            "--graph-evaluations",
            "20",
            "--solve-executions",
            "4",
            "--skip-isolation",
        ],
        "Pr": [
            "--graph-evaluations",
            "60",
            "--solve-executions",
            "20",
            "--skip-isolation",
        ],
        "Nightly": [
            "--graph-evaluations",
            "10000",
            "--solve-executions",
            "1000",
            "--require-nightly-minimum",
        ],
    }[tier]
    _run(
        _julia_command(
            tools,
            f"--project={JULIA_PROJECT}",
            str(JULIA_PROJECT / "qa" / "run_qa02.jl"),
            *qa02_arguments,
        ),
        label="QA-02 deterministic fuzz/metamorphic suite",
        environment=environment,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", type=_tier, default="Pr", metavar="TIER")
    arguments = parser.parse_args(argv)
    try:
        run_ci(arguments.tier)
    except (CiError, DoctorError, KeyError, OSError) as error:
        print(f"GeoTarget CI tier {arguments.tier!r}: FAILED: {error}", file=sys.stderr)
        return 1
    print(f"GeoTarget CI tier {arguments.tier!r}: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
