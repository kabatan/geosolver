#!/usr/bin/env python3
"""Truth-free differential and seam audit for cached structural coloring."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
from typing import Callable, Mapping

import numpy as np


HERE = Path(__file__).resolve().parent
S0_ROOT = HERE.parent / "EXP-EVAL-001"
if str(S0_ROOT) not in sys.path:
    sys.path.insert(0, str(S0_ROOT))

import cached_sparsity as candidate  # noqa: E402


FROZEN_AD = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-REAL61-006/analytic_jacobian/candidate.py"
)
FROZEN_SEARCH_WORKER = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/champion_v0/search_worker.py"
)
PINNED_OPTIMIZED_SEARCH = Path(
    "/home/kabatan/work/solver-wt/control-0967/src/geotarget/optimized_search.py"
)
PINNED_FULL_PREFIX = Path(
    "/home/kabatan/work/solver-wt/control-0967/src/geotarget/"
    "search_full_prefix_entrypoint.py"
)
PINNED_POOL_PREFIX = Path(
    "/home/kabatan/work/solver-wt/control-0967/src/geotarget/"
    "search_pool_worker_entrypoint.py"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _document(
    names: tuple[str, ...],
    pairs: tuple[tuple[str, str], ...],
    order: tuple[int, ...],
) -> dict[str, object]:
    constraints = [
        {"def": f"{left} * {left} + 0.25 * {right}", "value": 0}
        for left, right in pairs
    ]
    return {
        "variables": {"names": list(names)},
        "construction": [],
        "constraints": [constraints[index] for index in order],
        "guards": [],
    }


def _evaluator(
    names: tuple[str, ...],
    pairs: tuple[tuple[str, str], ...],
    order: tuple[int, ...],
) -> Callable[[np.ndarray], np.ndarray]:
    index = {name: ordinal for ordinal, name in enumerate(names)}

    def evaluate(point: np.ndarray) -> np.ndarray:
        values = [
            point[index[left]] * point[index[left]] + 0.25 * point[index[right]]
            for left, right in pairs
        ]
        return np.asarray([values[ordinal] for ordinal in order], dtype=float)

    return evaluate


def _same_bits(left: np.ndarray, right: np.ndarray) -> bool:
    return left.shape == right.shape and left.tobytes(order="C") == right.tobytes(order="C")


def _generated_differential(probes: int) -> dict[str, object]:
    randomizer = random.Random(772091)
    canonical_names = tuple(f"x{index}" for index in range(8))
    pairs = tuple((canonical_names[index], canonical_names[index + 1]) for index in range(0, 8, 2))
    variants = (
        (canonical_names, (0, 1, 2, 3), "identity"),
        (tuple(reversed(canonical_names)), (0, 1, 2, 3), "variable-permutation"),
        (canonical_names, (3, 1, 0, 2), "residual-permutation"),
        (tuple(canonical_names[index] for index in (2, 3, 0, 1, 6, 7, 4, 5)), (2, 0, 3, 1), "joint-permutation"),
    )
    matches = 0
    colored_directions = 0
    dense_directions = 0
    per_variant: dict[str, int] = {}
    for names, order, label in variants:
        document = _document(names, pairs, order)
        evaluate = _evaluator(names, pairs, order)
        variant_matches = 0
        for _ in range(probes):
            point = np.asarray([randomizer.uniform(-4.0, 4.0) for _ in names])
            steps = np.asarray(
                [randomizer.uniform(0.5, 1.5) * 1.0e-7 for _ in names]
            )
            current = evaluate(point)
            observed = candidate.cached_colored_forward_difference(
                document, evaluate, point, current, steps
            )
            control, control_calls = candidate._dense_fd(
                evaluate, point, current, steps
            )
            if observed.mode != "colored" or not _same_bits(observed.jacobian, control):
                raise AssertionError(f"positive-step differential mismatch: {label}")
            variant_matches += 1
            matches += 1
            colored_directions += observed.direction_evaluations
            dense_directions += control_calls
        per_variant[label] = variant_matches
    return {
        "seed": 772091,
        "probes_per_variant": probes,
        "variant_count": len(variants),
        "bit_identical_full_jacobians": matches,
        "mismatches": 0,
        "per_variant": per_variant,
        "colored_direction_evaluations": colored_directions,
        "dense_direction_evaluations": dense_directions,
        "direction_reduction_fraction": 1.0 - colored_directions / dense_directions,
    }


def _fallback_evidence() -> dict[str, object]:
    names = ("x", "y", "z", "w")
    point = np.asarray([1.5, -0.75, 2.0, -3.0])
    steps = np.full(4, 1.0e-7)
    documents: Mapping[str, tuple[dict[str, object], Callable[[np.ndarray], np.ndarray]]] = {
        "nondifferentiable": (
            {
                "variables": {"names": list(names)},
                "construction": [],
                "constraints": [{"def": "Abs(x)", "value": 0}],
                "guards": [],
            },
            lambda value: np.asarray([abs(value[0])]),
        ),
        "branch": (
            {
                "variables": {"names": list(names)},
                "construction": [],
                "constraints": [{"def": "x if x > 0 else y", "value": 0}],
                "guards": [],
            },
            lambda value: np.asarray([value[0] if value[0] > 0 else value[1]]),
        ),
        "opaque": (
            {
                "variables": {"names": list(names)},
                "construction": [],
                "constraints": [{"def": "OpaqueProjection(x)", "value": 0}],
                "guards": [],
            },
            lambda value: np.asarray([value[0] * value[0]]),
        ),
        "guard": (
            {
                "variables": {"names": list(names)},
                "construction": [],
                "constraints": [{"def": "x + y", "value": 0}],
                "guards": ["x > 0"],
            },
            lambda value: np.asarray([value[0] + value[1]]),
        ),
    }
    rows: dict[str, object] = {}
    for label, (document, evaluate) in documents.items():
        current = evaluate(point)
        observed = candidate.cached_colored_forward_difference(
            document, evaluate, point, current, steps
        )
        control, control_calls = candidate._dense_fd(evaluate, point, current, steps)
        rows[label] = {
            "mode": observed.mode,
            "bit_identical_to_dense": _same_bits(observed.jacobian, control),
            "candidate_direction_evaluations": observed.direction_evaluations,
            "dense_direction_evaluations": control_calls,
            "fallback_reason": observed.fallback_reason,
        }

    pure = _document(names, (("x", "y"), ("z", "w")), (0, 1))
    evaluate_pure = _evaluator(names, (("x", "y"), ("z", "w")), (0, 1))
    current = evaluate_pure(point)
    traced = candidate.cached_colored_forward_difference(
        pure,
        evaluate_pure,
        point,
        current,
        steps,
        trace=lambda value: tuple(value > point),
    )
    trace_control, trace_calls = candidate._dense_fd(
        evaluate_pure, point, current, steps
    )
    rows["runtime_branch_trace"] = {
        "mode": traced.mode,
        "bit_identical_to_dense": _same_bits(traced.jacobian, trace_control),
        "candidate_direction_evaluations": traced.direction_evaluations,
        "dense_direction_evaluations": trace_calls,
        "callback_neutral": traced.direction_evaluations == trace_calls,
        "fallback_reason": traced.fallback_reason,
    }
    return rows


def _signed_zero_counterexample() -> dict[str, object]:
    names = ("x", "y", "z", "w")
    pairs = (("x", "y"), ("z", "w"))
    document = _document(names, pairs, (0, 1))
    evaluate = _evaluator(names, pairs, (0, 1))
    point = np.asarray([1.0, 2.0, 3.0, 4.0])
    steps = np.asarray([-1.0e-7, 1.0e-7, -1.0e-7, 1.0e-7])
    current = evaluate(point)
    observed = candidate.cached_colored_forward_difference(
        document, evaluate, point, current, steps
    )
    control, _calls = candidate._dense_fd(evaluate, point, current, steps)
    unequal = np.argwhere(observed.jacobian.view(np.uint64) != control.view(np.uint64))
    numeric_equal = np.array_equal(observed.jacobian, control)
    signed_zero_only = all(
        observed.jacobian[tuple(index)] == 0.0
        and control[tuple(index)] == 0.0
        for index in unequal
    )
    return {
        "numeric_array_equal": bool(numeric_equal),
        "bit_identical": _same_bits(observed.jacobian, control),
        "differing_uint64_entries": int(len(unequal)),
        "differences_are_signed_zero_only": bool(signed_zero_only),
    }


def _seam_evidence() -> dict[str, object]:
    for required in (
        FROZEN_AD,
        FROZEN_SEARCH_WORKER,
        PINNED_OPTIMIZED_SEARCH,
        PINNED_FULL_PREFIX,
        PINNED_POOL_PREFIX,
    ):
        if not required.is_file():
            raise FileNotFoundError(required)
    source = FROZEN_AD.read_text(encoding="utf-8")
    specification = importlib.util.spec_from_file_location(
        "geotarget_exp_eval_002_search_audit", FROZEN_SEARCH_WORKER
    )
    if specification is None or specification.loader is None:
        raise ImportError(FROZEN_SEARCH_WORKER)
    search = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = search
    specification.loader.exec_module(search)
    strict_ad = search.ADAPTER.V2._KERNEL._ROW._AD
    retained_ad = search.ADAPTER.V1.CORRECTIVE_MODULE._PATCHED._ROW._AD
    return {
        "frozen_ad_path": str(FROZEN_AD),
        "frozen_ad_sha256": _sha256(FROZEN_AD),
        "hybrid_jacobian_definition_count": source.count("def _hybrid_jacobian("),
        "unsupported_dense_loop_present": (
            "for column in range(dimension):" in source
            and "jacobian[unsupported, column]" in source
        ),
        "retained_and_strict_tracks_share_module": strict_ad is retained_ad,
        "loaded_ad_module_path": str(Path(strict_ad.__file__).resolve()),
        "actual_jacobian_components": [
            "relation residuals",
            "compiled guard violations",
            "opaque hard-feasibility component",
        ],
        "cached_plan_components": ["relation constraints"],
        "parent_patch_crosses_search_subprocess": False,
        "single_core_entrypoint_sha256": _sha256(PINNED_FULL_PREFIX),
        "pool_entrypoint_sha256": _sha256(PINNED_POOL_PREFIX),
        "optimized_search_sha256": _sha256(PINNED_OPTIMIZED_SEARCH),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probes", type=int, default=128)
    arguments = parser.parse_args()
    if arguments.probes < 1:
        raise SystemExit("--probes must be positive")
    payload = {
        "schema_version": "geotarget.exp-eval-002-seam-audit/v1",
        "truth_used": False,
        "validation_or_sealed_used": False,
        "formal_solver_arm_executed": False,
        "generated_differential": _generated_differential(arguments.probes),
        "fallbacks": _fallback_evidence(),
        "signed_zero_counterexample": _signed_zero_counterexample(),
        "seam": _seam_evidence(),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
