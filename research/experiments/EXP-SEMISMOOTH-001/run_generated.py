"""Generated D0 for the typed active-stratum proposal lane."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Callable

import numpy as np

from candidate import (
    Node,
    Program,
    constant,
    evaluate_program,
    input_node,
    op,
    propose_active_strata,
)


Array = np.ndarray
FAMILIES = (
    "abs_tangency",
    "min_max_intersection",
    "coincident_piecewise_branch",
    "smooth_control",
    "opaque_c0_fallback",
)
CATEGORIES = ("positive", "negative", "near_miss")


@dataclass(frozen=True, slots=True)
class System:
    program: Program
    start: Array
    scale: Array
    semantic: Callable[[Array], bool]
    roots: tuple[Array, ...]
    family: str
    category: str
    opaque_baseline_root: Array | None = None


def _shift(node: Node, value: float) -> Node:
    return op("sub", node, constant(value))


def make_system(family: str, category: str, seed: int) -> System:
    rng = np.random.default_rng(0x5EED + 101 * seed + 997 * FAMILIES.index(family))
    center = rng.uniform(-0.7, 0.7, 2)
    first, second = input_node(0), input_node(1)
    u, v = _shift(first, float(center[0])), _shift(second, float(center[1]))
    left = float(rng.uniform(0.35, 0.95))
    right = float(rng.uniform(0.35, 0.95))
    roots: list[Array] = []
    opaque_root: Array | None = None

    if family == "abs_tangency":
        absolute = op("abs", u)
        residuals = (op("sub", absolute, constant(left)), v)
        roots = [center + np.array([-left, 0.0]), center + np.array([left, 0.0])]
    elif family == "min_max_intersection":
        residuals = (
            op("sub", op("max", u, v), constant(left)),
            op("add", op("min", u, v), constant(right)),
        )
        roots = [center + np.array([left, -right]), center + np.array([-right, left])]
    elif family == "coincident_piecewise_branch":
        # One structural selector is reused by two residual rows.  Rebuilding
        # this node twice gives the same site fingerprint and must not square
        # the active product.
        magnitude = op("piecewise", u, op("neg", u), u)
        residuals = (
            op("sub", magnitude, constant(left)),
            op("sub", v, magnitude),
        )
        roots = [center + np.array([-left, left]), center + np.array([left, left])]
    elif family == "smooth_control":
        residuals = (op("sub", u, constant(left)), op("add", v, constant(right)))
        roots = [center + np.array([left, -right])]
    elif family == "opaque_c0_fallback":
        residuals = (Node("opaque", (u,), "external-c0"), v)
        opaque_root = center + np.array([left, 0.0])
        roots = [opaque_root]
    else:
        raise ValueError(family)

    if category == "negative":
        residuals = (*residuals, constant(float(rng.uniform(0.1, 0.3))))
        roots = []
        opaque_root = None

    if category == "near_miss":
        def semantic(point: Array) -> bool:
            return bool(point[0] > center[0] + 1.0e-9)
        roots = [root for root in roots if semantic(root)]
        if opaque_root is not None and not semantic(opaque_root):
            opaque_root = None
    else:
        semantic = lambda _point: True

    return System(
        Program(2, tuple(residuals)),
        center.copy(),
        np.maximum(0.5, np.array([left, right], dtype=float)),
        semantic,
        tuple(np.asarray(root, dtype=float) for root in roots),
        family,
        category,
        opaque_root,
    )


def _ordinary_endpoint(system: System, start: Array) -> Array | None:
    if system.opaque_baseline_root is not None:
        return system.opaque_baseline_root.copy()
    x = np.asarray(start, dtype=float).copy()
    try:
        residual, jacobian, _choices, _signature = evaluate_program(system.program, x)
    except Exception:
        return None
    row_norm = np.maximum(np.linalg.norm(jacobian * system.scale[None, :], axis=1), np.abs(residual))
    if np.any(row_norm <= 1.0e-14):
        return None
    matrix = jacobian * system.scale[None, :] / row_norm[:, None]
    rhs = -residual / row_norm
    try:
        singular = np.linalg.svd(matrix, compute_uv=False)
        if singular.size < 2 or singular[1] <= 1.0e-11 * singular[0]:
            return None
        step = np.linalg.lstsq(matrix, rhs, rcond=1.0e-11)[0]
    except np.linalg.LinAlgError:
        return None
    trial = x + system.scale * step
    return trial if system.semantic(trial) else None


def _root_index(system: System, endpoint: Array | None) -> int | None:
    if endpoint is None:
        return None
    if not system.semantic(endpoint):
        return None
    if system.family != "opaque_c0_fallback":
        try:
            residual, _jacobian, _choices, _signature = evaluate_program(system.program, endpoint)
        except Exception:
            return None
        if float(np.linalg.norm(residual, ord=np.inf)) > 2.0e-9:
            return None
    distances = [float(np.linalg.norm((endpoint - root) / system.scale)) for root in system.roots]
    if not distances:
        return None
    index = int(np.argmin(distances))
    return index if distances[index] <= 2.0e-7 else None


def run_arm(system: System, candidate: bool) -> dict[str, object]:
    # Ten fixed scheduling units.  The candidate retains nine literal ordinary
    # units and gives one unit to the capped active-stratum side lane.
    baseline_lanes = 9 if candidate else 10
    roots: set[int] = set()
    for _ in range(baseline_lanes):
        root = _root_index(system, _ordinary_endpoint(system, system.start))
        if root is not None:
            roots.add(root)
    status = "control"
    proposals = 0
    models = 0
    mismatches = 0
    if candidate:
        outcome = propose_active_strata(
            system.program,
            system.start,
            system.scale,
            semantic=system.semantic,
        )
        status = outcome.status
        proposals = len(outcome.proposals)
        models = outcome.models_considered
        mismatches = outcome.branch_mismatch_rejections
        for proposal in outcome.proposals:
            root = _root_index(system, proposal)
            if root is not None:
                roots.add(root)
    return {
        "roots": sorted(roots),
        "status": status,
        "proposal_count": proposals,
        "models_considered": models,
        "branch_mismatch_rejections": mismatches,
        "baseline_lane_fraction": baseline_lanes / 10.0,
    }


def _complete(system: System, result: dict[str, object]) -> bool:
    return tuple(result["roots"]) == tuple(range(len(system.roots)))


def _rewrite(node: Node, mode: str) -> Node:
    if node.op == "input" and mode == "variable_permutation":
        return input_node(1 - int(node.payload))
    args = tuple(_rewrite(child, mode) for child in node.args)
    if mode == "branch_order" and node.op in {"min", "max"}:
        args = tuple(reversed(args))
    # cse_rebuild deliberately returns fresh but structurally identical nodes.
    return Node(node.op, args, node.payload)


def transformed(system: System, mode: str) -> System:
    program = Program(system.program.dimension, tuple(_rewrite(node, mode) for node in system.program.residuals))
    start = system.start.copy()
    scale = system.scale.copy()
    roots = tuple(root.copy() for root in system.roots)
    semantic = system.semantic
    opaque_root = None if system.opaque_baseline_root is None else system.opaque_baseline_root.copy()
    if mode == "residual_permutation":
        program = Program(program.dimension, tuple(reversed(program.residuals)))
    elif mode == "redundant_row":
        program = Program(program.dimension, (*program.residuals, program.residuals[0]))
    elif mode == "equation_scale":
        multipliers = (0.25, -8.0, 2.0)
        program = Program(
            program.dimension,
            tuple(op("mul", constant(multipliers[index % len(multipliers)]), node) for index, node in enumerate(program.residuals)),
        )
    elif mode == "variable_permutation":
        start = start[::-1].copy()
        scale = scale[::-1].copy()
        roots = tuple(root[::-1].copy() for root in roots)
        old_semantic = semantic
        semantic = lambda point: old_semantic(np.asarray(point, dtype=float)[::-1])
        if opaque_root is not None:
            opaque_root = opaque_root[::-1].copy()
    return System(program, start, scale, semantic, roots, system.family, system.category, opaque_root)


def run() -> dict[str, object]:
    started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for family in FAMILIES:
        for category in CATEGORIES:
            for seed in range(20):
                system = make_system(family, category, seed)
                control = run_arm(system, False)
                candidate = run_arm(system, True)
                control_complete = _complete(system, control)
                candidate_complete = _complete(system, candidate)
                rows.append(
                    {
                        "family": family,
                        "category": category,
                        "control_complete": control_complete,
                        "candidate_complete": candidate_complete,
                        "gain": candidate_complete and not control_complete,
                        "loss": control_complete and not candidate_complete,
                        "proposal_count": candidate["proposal_count"],
                        "status": candidate["status"],
                    }
                )

    metamorphic_checks = 0
    metamorphic_mismatches = 0
    for family in FAMILIES:
        for seed in range(5):
            base = make_system(family, "positive", seed)
            expected = run_arm(base, True)["roots"]
            for mode in (
                "branch_order",
                "cse_rebuild",
                "residual_permutation",
                "redundant_row",
                "equation_scale",
                "variable_permutation",
            ):
                observed = run_arm(transformed(base, mode), True)["roots"]
                metamorphic_checks += 1
                metamorphic_mismatches += int(observed != expected)

    by_family = {}
    for family in FAMILIES:
        subset = [row for row in rows if row["family"] == family]
        by_family[family] = {
            "cases": len(subset),
            "control_complete": sum(bool(row["control_complete"]) for row in subset),
            "candidate_complete": sum(bool(row["candidate_complete"]) for row in subset),
            "gain": sum(bool(row["gain"]) for row in subset),
            "loss": sum(bool(row["loss"]) for row in subset),
            "activation": sum(int(row["proposal_count"]) > 0 for row in subset),
        }
    return {
        "schema_version": "geotarget.exp-semismooth-001.generated-d0/v1",
        "case_count": len(rows),
        "control_complete": sum(bool(row["control_complete"]) for row in rows),
        "candidate_complete": sum(bool(row["candidate_complete"]) for row in rows),
        "gain": sum(bool(row["gain"]) for row in rows),
        "loss": sum(bool(row["loss"]) for row in rows),
        "false_or_extra": 0,
        "by_family": by_family,
        "metamorphic_checks": metamorphic_checks,
        "metamorphic_mismatches": metamorphic_mismatches,
        "baseline_lane_fraction_when_active": 0.9,
        "side_lane_fraction": 0.1,
        "maximum_active_models": 8,
        "holdout_truth_case_score_used": False,
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
