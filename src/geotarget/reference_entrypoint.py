"""Apply the frozen dataset runner's outer process contract to one case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.infrastructure.memory_safety.safe_subprocess import Limits, run_guarded

MIB = 1024**2
GIB = 1024**3


def _limits(phase: str) -> Limits:
    if phase == "dry":
        return Limits(
            timeout_seconds=8.0,
            rss_bytes=256 * MIB,
            address_space_bytes=2 * GIB,
            data_bytes=1536 * MIB,
            output_bytes=256 * 1024,
            tail_bytes=8 * 1024,
        )
    return Limits(
        timeout_seconds=183.0,
        rss_bytes=256 * MIB,
        address_space_bytes=3 * GIB,
        data_bytes=2 * GIB,
        output_bytes=256 * 1024,
        tail_bytes=8 * 1024,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("dry", "execute"), required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = arguments.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a child command is required after --")
    result = run_guarded(
        command,
        limits=_limits(arguments.phase),
        status_path=arguments.status,
    )
    if result.accepted_output:
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
