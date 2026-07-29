"""Apply the frozen dataset runner's outer process contract to one case."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping
from pathlib import Path

from research.infrastructure.memory_safety.safe_subprocess import Limits, run_guarded

MIB = 1024**2
GIB = 1024**3
REFERENCE_ALGORITHM_SECONDS = 180.0
REFERENCE_FINALIZE_GRACE_SECONDS = 3.0


def _command_value(command: list[str], option: str) -> str | None:
    try:
        return command[command.index(option) + 1]
    except (ValueError, IndexError):
        return None


def _committed_result(command: list[str]) -> bool:
    """Recognize only an atomically committed frozen result after guard expiry.

    The memory guard may observe the process after its watchdog deadline even
    though the frozen worker has already replaced RESULT.json.  That file is a
    durable algorithm checkpoint; accepting it avoids turning a completed
    exact-authority prefix into an engine error.  A missing, partial, or
    source-mismatched document still fails closed.
    """

    raw_output = _command_value(command, "--output")
    expected_source = _command_value(command, "--source-sha256")
    if raw_output is None or expected_source is None:
        return False
    result_path = Path(raw_output).resolve() / "RESULT.json"
    try:
        document = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        isinstance(document, Mapping)
        and document.get("completed") is True
        and document.get("source_sha256") == expected_source
        and document.get("source_bytes_unchanged") is True
    )


def _limits(
    phase: str,
    rss_mib: float | None = None,
    *,
    algorithm_seconds: float = REFERENCE_ALGORITHM_SECONDS,
    startup_grace_seconds: float = 0.0,
    finalize_grace_seconds: float = REFERENCE_FINALIZE_GRACE_SECONDS,
) -> Limits:
    if phase == "dry":
        return Limits(
            timeout_seconds=8.0,
            rss_bytes=256 * MIB,
            address_space_bytes=2 * GIB,
            data_bytes=1536 * MIB,
            output_bytes=256 * 1024,
            tail_bytes=8 * 1024,
        )
    rss_bytes = int(rss_mib * MIB) if rss_mib is not None else 256 * MIB
    return Limits(
        timeout_seconds=(algorithm_seconds + startup_grace_seconds + finalize_grace_seconds),
        rss_bytes=rss_bytes,
        address_space_bytes=max(3 * GIB, rss_bytes * 2),
        data_bytes=max(2 * GIB, rss_bytes),
        output_bytes=256 * 1024,
        tail_bytes=8 * 1024,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("dry", "execute"), required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--rss-mib", type=float)
    parser.add_argument("--algorithm-seconds", type=float, default=REFERENCE_ALGORITHM_SECONDS)
    parser.add_argument("--startup-grace-seconds", type=float, default=0.0)
    parser.add_argument(
        "--finalize-grace-seconds",
        type=float,
        default=REFERENCE_FINALIZE_GRACE_SECONDS,
    )
    parser.add_argument("--accept-committed-on-timeout", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = arguments.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a child command is required after --")
    grace_values = (
        arguments.algorithm_seconds,
        arguments.startup_grace_seconds,
        arguments.finalize_grace_seconds,
    )
    if (
        any(not math.isfinite(value) for value in grace_values)
        or arguments.algorithm_seconds <= 0.0
        or arguments.startup_grace_seconds < 0.0
        or arguments.finalize_grace_seconds < 0.0
        or sum(grace_values) > 3600.0
    ):
        parser.error("invalid algorithm/watchdog deadline components")
    result = run_guarded(
        command,
        limits=_limits(
            arguments.phase,
            arguments.rss_mib,
            algorithm_seconds=arguments.algorithm_seconds,
            startup_grace_seconds=arguments.startup_grace_seconds,
            finalize_grace_seconds=arguments.finalize_grace_seconds,
        ),
        status_path=arguments.status,
    )
    if result.accepted_output:
        return 0
    if (
        arguments.phase == "execute"
        and arguments.accept_committed_on_timeout
        and result.classification == "TIMEOUT"
        and _committed_result(command)
    ):
        return 0
    print(
        json.dumps(
            {
                "classification": result.classification,
                "stdout_tail": result.stdout_tail,
                "stderr_tail": result.stderr_tail,
            },
            ensure_ascii=False,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
