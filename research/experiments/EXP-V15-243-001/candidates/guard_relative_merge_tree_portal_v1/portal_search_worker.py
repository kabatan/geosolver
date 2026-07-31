#!/usr/bin/env python3
"""Frozen champion search with the candidate-specific 75/25 portal splice."""

from __future__ import annotations

import hashlib
import importlib.util
import json
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
LOCAL_BINDINGS = {
    "candidate.py": (
        HERE / "candidate.py",
        "5bc78be9bc8ace817f0e49ad9dfe918a90fe1b99c5d46d53459388d89029619d",
    ),
    "collect_connector.py": (
        HERE / "collect_connector.py",
        "42cb80ec5da32a0ca4c9aade9e19c6aa6c2c0d01b14a5c53a974f32ea7f2a518",
    ),
    "portal_connector.py": (
        HERE / "portal_connector.py",
        "4eb4ef4a4a82ceb5c3605651fd0c239077aedbf6ce56496f70c5468f4af53484",
    ),
    "REAL_GATE_STATUS.json": (
        HERE / "REAL_GATE_STATUS.json",
        "c3eac0146083ef2980aeeb57d4e02e5a147935dee256fe6a2378f0147df0da23",
    ),
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
    for name, (path, expected) in LOCAL_BINDINGS.items():
        if not path.is_file() or _sha256(path) != expected:
            raise SystemExit(f"portal repair local SHA-256 mismatch: {name}")


def _argument(name: str) -> str:
    try:
        return sys.argv[sys.argv.index(name) + 1]
    except (ValueError, IndexError):
        raise SystemExit(f"portal repair requires {name}") from None


def main() -> None:
    _verify()
    candidate = _load("geotarget_guard_merge_portal_candidate", LOCAL_BINDINGS["candidate.py"][0])
    collect = _load(
        "geotarget_guard_merge_portal_collect", LOCAL_BINDINGS["collect_connector.py"][0]
    )
    connector = _load(
        "geotarget_guard_merge_portal_connector", LOCAL_BINDINGS["portal_connector.py"][0]
    )
    baseline = _load(
        "geotarget_guard_merge_portal_baseline_search", BASELINE_SEARCH_WORKER
    )
    global_gate = json.loads(LOCAL_BINDINGS["REAL_GATE_STATUS.json"][0].read_text(encoding="utf-8"))
    collector = collect.Collector(_argument("--case-sha256"), candidate)
    baseline.BASE.build_source_case = collector.wrap_build_source_case(
        baseline.BASE.build_source_case
    )
    runtime = connector.PortalRuntime(
        collector=collector,
        candidate=candidate,
        point_key=collect._point_key,
        global_gate=global_gate,
    )
    baseline.BASE.run_local_arm = runtime.wrap_run_local_arm(
        baseline.BASE.run_local_arm
    )
    baseline.main()
    output = collect._output_argument(sys.argv)
    connector.write_portal_sidecar(
        runtime=runtime,
        output=output,
        atomic_write_json=baseline.BASE.atomic_write_json,
    )


if __name__ == "__main__":
    main()
