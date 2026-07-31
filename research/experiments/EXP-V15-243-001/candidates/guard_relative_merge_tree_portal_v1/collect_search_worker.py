#!/usr/bin/env python3
"""Exact baseline search worker with a collect-only callback observer."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASELINE_SEARCH_WORKER = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/champion_v0/search_worker.py"
)
EXPECTED_BASELINE_SEARCH_WORKER_SHA256 = (
    "ce2dd5018037fbe5175fc63a2d20d9463243be58d4deeca3bc7cb1aed44e30bf"
)
COLLECT_CONNECTOR = HERE / "collect_connector.py"
CANDIDATE = HERE / "candidate.py"
EXPECTED_LOCAL_SHA256 = {
    "collect_connector.py": "42cb80ec5da32a0ca4c9aade9e19c6aa6c2c0d01b14a5c53a974f32ea7f2a518",
    "candidate.py": "5bc78be9bc8ace817f0e49ad9dfe918a90fe1b99c5d46d53459388d89029619d",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _verify() -> None:
    if (
        not BASELINE_SEARCH_WORKER.is_file()
        or _sha256(BASELINE_SEARCH_WORKER) != EXPECTED_BASELINE_SEARCH_WORKER_SHA256
    ):
        raise SystemExit("frozen baseline search worker SHA-256 mismatch")
    for name, path in (
        ("collect_connector.py", COLLECT_CONNECTOR),
        ("candidate.py", CANDIDATE),
    ):
        if not path.is_file() or _sha256(path) != EXPECTED_LOCAL_SHA256[name]:
            raise SystemExit(f"collect-only local SHA-256 mismatch: {name}")


def _argument(name: str) -> str:
    try:
        return sys.argv[sys.argv.index(name) + 1]
    except (ValueError, IndexError):
        raise SystemExit(f"collect-only connector requires {name}") from None


def main() -> None:
    _verify()
    connector = _load("geotarget_guard_merge_collect_connector", COLLECT_CONNECTOR)
    candidate = _load("geotarget_guard_merge_candidate", CANDIDATE)
    baseline = _load("geotarget_guard_merge_baseline_search_worker", BASELINE_SEARCH_WORKER)
    collector = connector.Collector(_argument("--case-sha256"), candidate)
    baseline.BASE.build_source_case = collector.wrap_build_source_case(
        baseline.BASE.build_source_case
    )
    baseline.main()
    output = connector._output_argument(sys.argv)
    connector.write_aggregate_sidecar(
        collector=collector,
        output=output,
        atomic_write_json=baseline.BASE.atomic_write_json,
    )


if __name__ == "__main__":
    main()
