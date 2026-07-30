#!/usr/bin/env python3
"""Audit the one authorized current-control bind point, without importing it."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


BOUND_WORKER = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/exact_outer_decorator/worker.py"
)
BOUND_SHA256 = "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7"


def _function_names(tree: ast.AST) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def audit(path: Path = BOUND_WORKER) -> dict[str, Any]:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != BOUND_SHA256:
        raise RuntimeError("bound current-control worker SHA-256 changed")
    text = payload.decode("utf-8")
    tree = ast.parse(text, filename=str(path))
    names = _function_names(tree)
    required = {"_fallback_command", "_consume_fallback", "_run_exact_outer"}
    if not required <= names:
        raise RuntimeError("bound worker protocol changed")

    command_inputs = {
        token: token in text
        for token in (
            '"--source"',
            '"--source-sha256"',
            '"--endpoint"',
            '"--endpoint-sha256"',
            '"--timeout-seconds"',
            '"--output"',
        )
    }
    missing_command_input = [key for key, present in command_inputs.items() if not present]
    if missing_command_input:
        raise RuntimeError("bound fallback command protocol changed")

    angle_hooks = {
        token: token in text
        for token in (
            "typed_angle_equality_obligation",
            "exact_angle_operands",
            "angle_relation_ledger",
            "EXACT_TYPED_ANGLE_EQUALITY_REPAIRED",
        )
    }
    qreflect_hooks = {
        token: token in text
        for token in (
            "qreflect_obligation",
            "reflected_source_replay",
            "qreflect_used",
        )
    }
    return {
        "schema_version": "geotarget.current-exact-connector-audit/v1",
        "bound_worker": str(path),
        "bound_worker_sha256": digest,
        "source_only": True,
        "current_protocol": {
            "fallback_command_inputs": command_inputs,
            "frozen_child_path_and_hash_checked_by_bound_worker": (
                "EXPECTED_EXACT_SHA256" in text and "verify_exact_freeze" in text
            ),
            "accepted_authority_is_final_descriptor_only": (
                "nested_exact_authority_matches_source" in text
                and "return descriptor if accepted else None" in text
            ),
        },
        "typed_angle_hooks": angle_hooks,
        "qreflect_hooks": qreflect_hooks,
        "typed_angle_connector_decision": (
            "STOP_NO_EXACT_OPERAND_OBLIGATION_SEAM"
            if not any(angle_hooks.values())
            else "REVIEW_REQUIRED"
        ),
        "qreflect_connector_decision": (
            "STOP_NO_REFLECTION_OBLIGATION_SEAM"
            if not any(qreflect_hooks.values())
            else "REVIEW_REQUIRED"
        ),
        "reason": (
            "The bound outer worker delegates source and endpoint to a frozen "
            "child, then consumes only a fully replayed descriptor. It exports "
            "no versioned typed-relation operands, exact ledger, or pre-"
            "descriptor callback. A thin post-decorator cannot reconstruct all "
            "exact preconditions without duplicating the canonical replay."
        ),
        "baseline_byte_identical_fallback_implementable": True,
        "additional_authority_implementable_with_thin_decorator": False,
        "formal_benchmark_run": False,
        "truth_scorer_or_result_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bound-worker", type=Path, default=BOUND_WORKER)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.bound_worker)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
