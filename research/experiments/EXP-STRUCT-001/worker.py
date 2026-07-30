#!/usr/bin/env python3
"""Dry-run adapter from EXP-STRUCT-001 to the frozen champion contract.

Non-applicable sources are exec-delegated byte-for-byte to the frozen worker.
Applicable sources produce a sealed integration plan.  Execution is disabled
until a concrete block solver passes the common callback/wall budget gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Mapping, Sequence

from block_structure import extract_v15_structure


HERE = Path(__file__).resolve().parent
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
FROZEN_ROOT = Path(os.environ.get("GEOTARGET_FROZEN_ROOT", DEFAULT_FROZEN_ROOT))
FROZEN_PYTHON = FROZEN_ROOT / "python/.venv/bin/python"
FROZEN_WORKER = (
    FROZEN_ROOT
    / "research/experiments/EXP-V15-243-001/repro_20260722/workers/"
    "champion_v2_poc_preloaded.py"
)
EXPECTED_FROZEN_WORKER_SHA256 = (
    "e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _mechanism_hash() -> str:
    """Common arm contract: raw SHA-256 of this entrypoint."""

    return _sha256(Path(__file__).read_bytes())


def _overlay_closure_hash() -> str:
    payload = (HERE / "block_structure.py").read_bytes() + (HERE / "champion_overlay.py").read_bytes()
    return _sha256(payload)


def _verify_closure() -> None:
    if not FROZEN_PYTHON.is_file() or not FROZEN_WORKER.is_file():
        raise SystemExit("frozen Python champion closure is unavailable")
    if _sha256(FROZEN_WORKER.read_bytes()) != EXPECTED_FROZEN_WORKER_SHA256:
        raise SystemExit("frozen champion worker digest changed")
    arm = json.loads((HERE / "arm.json").read_text(encoding="utf-8"))
    if not isinstance(arm, Mapping) or arm.get("mechanism_hash") != _mechanism_hash():
        raise SystemExit("arm mechanism hash does not match the overlay closure")


def _source(source: Path, expected_sha256: str) -> tuple[bytes, dict[str, object]]:
    payload = source.read_bytes()
    if _sha256(payload) != expected_sha256:
        raise SystemExit("source SHA-256 mismatch")
    document = json.loads(payload)
    if not isinstance(document, dict) or document.get("task") != "solve":
        raise SystemExit("untouched solve formulation is required")
    return payload, document


def frozen_command(arguments: Sequence[str]) -> tuple[str, ...]:
    """Exact passthrough command used for every non-applicable formulation."""

    return (str(FROZEN_PYTHON), str(FROZEN_WORKER), *arguments)


def _base_dry_command(arguments: argparse.Namespace, output: Path) -> list[str]:
    return [
        str(FROZEN_PYTHON),
        str(FROZEN_WORKER),
        "--source",
        str(arguments.source),
        "--source-sha256",
        arguments.source_sha256,
        "--total-seconds",
        str(arguments.total_seconds),
        "--search-seconds",
        str(arguments.search_seconds),
        "--starts",
        str(arguments.starts),
        "--callbacks-per-start",
        str(arguments.callbacks_per_start),
        "--aggregate-callback-cap",
        str(arguments.aggregate_callback_cap),
        "--seed",
        str(arguments.seed),
        "--cpu",
        str(arguments.cpu),
        "--output",
        str(output),
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--total-seconds", type=float, default=180.0)
    parser.add_argument("--search-seconds", type=float, default=146.0)
    parser.add_argument("--starts", type=int, default=256)
    parser.add_argument("--callbacks-per-start", type=int, default=600)
    parser.add_argument("--aggregate-callback-cap", type=int, default=153600)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cpu", type=int, default=13)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan-sha256")
    return parser


def main() -> None:
    original_arguments = tuple(sys.argv[1:])
    arguments = _parser().parse_args()
    _verify_closure()
    _payload, document = _source(arguments.source, arguments.source_sha256)
    try:
        structure = extract_v15_structure(document)
    except (SyntaxError, TypeError, ValueError):
        # Unsupported or ambiguous dependency syntax is baseline-only. The
        # detector is never allowed to turn uncertainty into structure.
        os.execv(str(FROZEN_PYTHON), frozen_command(original_arguments))
    if not structure.plan.applicable:
        os.execv(str(FROZEN_PYTHON), frozen_command(original_arguments))

    if arguments.execute:
        raise SystemExit(
            "EXP-STRUCT-001 overlay is dry-run-only until a block solver passes "
            "the common callback/wall budget gate"
        )

    with tempfile.TemporaryDirectory(prefix="geotarget-struct-base-plan-") as temporary:
        temporary_output = Path(temporary) / "champion"
        completed = subprocess.run(
            _base_dry_command(arguments, temporary_output),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=8.0,
        )
        base_path = temporary_output / "PLAN.json"
        if completed.returncode != 0 or not base_path.is_file():
            raise SystemExit(
                "frozen champion dry plan failed: " + completed.stderr[-1000:]
            )
        base_plan = json.loads(base_path.read_text(encoding="utf-8"))
    if not isinstance(base_plan, dict):
        raise SystemExit("frozen champion emitted a malformed dry plan")
    # Remove the temporary-path difference before sealing the overlay plan.
    base_plan["output"] = str(arguments.output.resolve())

    plan = {
        "schema_version": "geotarget.exp-struct-001-champion-overlay-plan/v1",
        "status": "DRY_RUN_ONLY_NOT_EXECUTION_AUTHORIZED",
        "source_path": str(arguments.source.resolve()),
        "source_sha256": arguments.source_sha256,
        "arm_id": "EXP-STRUCT-001-BTF-CHAMPION-OVERLAY",
        "base_commit": "0967ff1cde5c2435fe0207da65e8779ff24a6da6",
        "mechanism_hash": _mechanism_hash(),
        "overlay_closure_hash": _overlay_closure_hash(),
        "frozen_worker": str(FROZEN_WORKER),
        "frozen_worker_sha256": EXPECTED_FROZEN_WORKER_SHA256,
        "structure": {
            "applicable": True,
            "reason": structure.plan.reason,
            "variable_count": structure.plan.variable_count,
            "relation_count": structure.plan.relation_count,
            "block_count": len(structure.plan.blocks),
            "maximum_block_size": structure.plan.maximum_block_size,
            "factor_work_ratio": structure.plan.factor_work_ratio,
            "blocks": [
                {
                    "relations": list(block.relation_indices),
                    "variables": list(block.variable_indices),
                    "predecessors": list(block.predecessor_blocks),
                }
                for block in structure.plan.blocks
            ],
        },
        "integration": {
            "baseline_search_starts": arguments.starts,
            "baseline_start_fraction": 1.0,
            "baseline_start_quota_at_least_half": True,
            "block_proposal_cap": 4,
            "injection_seam": "BASE._fresh_replay_candidates input endpoint stream",
            "block_endpoint_authority": "PROPOSAL_ONLY",
            "source_residual_guard_hard_feasibility_replay": "ORIGINAL_CHAMPION",
            "hp_and_exact_authority": "ORIGINAL_CHAMPION",
            "case_id_family_truth_known_target_count_routing": False,
            "execute_authorized": False,
        },
        "non_applicable_behavior": {
            "mode": "os.execv exact frozen command passthrough",
            "arguments_preserved": True,
            "descriptor_path_changed": False,
        },
        "frozen_base_plan": base_plan,
    }
    output = arguments.output.resolve()
    _atomic_write_json(output / "PLAN.json", plan)
    plan_sha256 = _sha256((output / "PLAN.json").read_bytes())
    print(json.dumps({"plan_sha256": plan_sha256, **plan}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
