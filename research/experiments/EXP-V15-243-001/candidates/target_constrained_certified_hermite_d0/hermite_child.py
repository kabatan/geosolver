#!/usr/bin/env python3
"""One-shot Hermite repair child; authority is published atomically only."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from repair_adapter import attempt_repair


ARCHIVE_ROOT = Path(
    os.environ.get("GEOTARGET_ARCHIVE_RUNTIME_ROOT", "/home/kabatan/work/solver-experiment-runtime/solver")
).resolve()
SAFE_SUBPROCESS = ARCHIVE_ROOT / "research/infrastructure/memory_safety/safe_subprocess.py"
EXPECTED_SAFE_SUBPROCESS_SHA256 = "76aa547f235bd0ae11c8b567461384b22537a9b98c990db2ed126db0a19b55c5"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_module():
    if not SAFE_SUBPROCESS.is_file() or _sha256(SAFE_SUBPROCESS) != EXPECTED_SAFE_SUBPROCESS_SHA256:
        raise RuntimeError("safe-subprocess-digest-mismatch")
    name = "geotarget_hermite_child_pinned_safe_subprocess"
    specification = importlib.util.spec_from_file_location(name, SAFE_SUBPROCESS)
    if specification is None or specification.loader is None:
        raise RuntimeError("safe-subprocess-load-failed")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _fault(mode: str, output: Path, late_marker: Path | None) -> None:
    """Generated S0 faults; unreachable unless the private CLI flag is supplied."""

    if mode == "sleep":
        time.sleep(30.0)
    elif mode == "partial-json":
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("{", encoding="utf-8")
        return
    elif mode == "output":
        sys.stdout.write("x" * (2 * 1024 * 1024))
        sys.stdout.flush()
        time.sleep(1.0)
    elif mode == "rss":
        allocation = bytearray(384 * 1024 * 1024)
        for index in range(0, len(allocation), 4096):
            allocation[index] = 1
        time.sleep(5.0)
    elif mode == "leak-late-artifact":
        marker = late_marker if late_marker is not None else output
        code = (
            "import pathlib,time;time.sleep(1.0);"
            f"pathlib.Path({str(marker)!r}).write_text('late',encoding='utf-8')"
        )
        subprocess.Popen([sys.executable, "-c", code])  # noqa: S603 - containment probe
        return
    else:
        raise RuntimeError(f"unknown generated fault: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--fault",
        choices=("sleep", "partial-json", "output", "rss", "leak-late-artifact"),
    )
    parser.add_argument("--late-marker", type=Path)
    arguments = parser.parse_args()
    if arguments.fault:
        _fault(arguments.fault, arguments.output, arguments.late_marker)
        return
    request = json.loads(arguments.request.read_bytes())
    expected_request_sha256 = request.pop("request_file_sha256", None)
    canonical_request = json.dumps(
        request, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if hashlib.sha256(canonical_request).hexdigest() != expected_request_sha256:
        raise SystemExit("request digest mismatch")
    result = attempt_repair(
        source=Path(request["source"]),
        source_sha256=request["source_sha256"],
        descriptor=request["descriptor"],
        endpoint=request["endpoint"],
        deadline_monotonic=float(request["deadline_monotonic"]),
    )
    result["hard_child_contract"] = {
        "schema": "geotarget.hermite-hard-child/v1",
        "atomic_final_artifact": True,
        "partial_artifact_can_authorize": False,
        "hard_guard_is_parent_owned": True,
    }
    _safe_module().atomic_write_json(arguments.output, result)


if __name__ == "__main__":
    main()
