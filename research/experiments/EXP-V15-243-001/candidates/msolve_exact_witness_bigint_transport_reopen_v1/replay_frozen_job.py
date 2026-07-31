#!/usr/bin/env python3.12
"""Replay the frozen old msolve RUR job through lossless integer transport."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import lossless_transport


FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
FROZEN_REPLAY = FROZEN_ROOT / "research/experiments/EXP-REAL61-004/msolve_exact_witness/replay_rur_qqbar.py"
FROZEN_REPLAY_SHA256 = "a373273b08bafcae746f57a9362be8f6b499c04bc9de07a6061829a324c400ad"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_replay():
    if sha256(FROZEN_REPLAY) != FROZEN_REPLAY_SHA256:
        raise RuntimeError("frozen replay worker hash changed")
    name = "frozen_msolve_rur_qqbar_replay_bigint_transport_reopen"
    specification = importlib.util.spec_from_file_location(name, FROZEN_REPLAY)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load frozen replay worker")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--proposal-index", type=int, required=True)
    parser.add_argument("--compiled-cover", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--msolve-input", type=Path, required=True)
    parser.add_argument("--msolve-output", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--factor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--transport-sidecar", type=Path, required=True)
    arguments = parser.parse_args()
    frozen = load_frozen_replay()

    def patched_run(job):
        return lossless_transport.run_julia_lossless(
            job,
            julia_project=frozen.QQBAR_WORKER.JULIA_PROJECT,
            julia_worker=frozen.QQBAR_WORKER.JULIA_WORKER,
            timeout_seconds=frozen.QQBAR_WORKER.INNER_TIMEOUT_SECONDS,
        )

    frozen.QQBAR_WORKER._run_julia = patched_run
    old_argv = sys.argv
    try:
        sys.argv = [
            str(FROZEN_REPLAY),
            "--source", str(arguments.source),
            "--proposal", str(arguments.proposal),
            "--proposal-index", str(arguments.proposal_index),
            "--compiled-cover", str(arguments.compiled_cover),
            "--prepared", str(arguments.prepared),
            "--msolve-input", str(arguments.msolve_input),
            "--msolve-output", str(arguments.msolve_output),
            "--selection", str(arguments.selection),
            "--factor", str(arguments.factor),
            "--output", str(arguments.output),
        ]
        frozen.main()
    finally:
        sys.argv = old_argv

    result = json.loads(arguments.output.read_text(encoding="utf-8"))
    attestation = lossless_transport.LAST_ATTESTATION
    complete = bool(
        isinstance(attestation, dict)
        and attestation.get("complete_qqbar_source_replay") is True
        and result.get("status") == "EXACT_V2_WITNESS_REPLAY_VERIFIED"
        and result.get("qqbar_replay", {}).get("status") == "EXACT_REPLAY_ACCEPTED"
        and result.get("original_dsl_replay", {}).get("exact_replay_passed") is True
    )
    sidecar = {
        "schema_version": "geotarget.msolve-bigint-transport-frozen-replay/v1",
        "status": "PASS" if complete else "FAIL",
        "authority": complete,
        "authority_scope": "COMPLETE_QQBAR_SOURCE_REPLAY_ONLY",
        "collector_authority": False,
        "development_proposal_only": True,
        "case_id": result.get("case_id"),
        "transport": attestation,
        "output_artifact_sha256": sha256(arguments.output),
        "truth_used": False,
        "formal_scorer_used": False,
        "case_routing_used": False,
    }
    arguments.transport_sidecar.parent.mkdir(parents=True, exist_ok=True)
    arguments.transport_sidecar.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not complete:
        raise RuntimeError("frozen replay did not complete exact QQBar source replay")


if __name__ == "__main__":
    main()
