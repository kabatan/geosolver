"""Candidate-private active-stratum semismooth Newton proposal lane.

Only the small typed scalar DAG below is admitted.  Branch models are built as
whole Jacobian matrices keyed by structural branch sites, so a repeated/CSE or
redundant residual row cannot multiply the branch Cartesian product.  Returned
points are proposals only; callers still own semantic and canonical replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
import math
from typing import Callable, Mapping, Sequence

import numpy as np


Array = np.ndarray
Semantic = Callable[[Array], bool]


@dataclass(frozen=True, slots=True)
class Node:
    op: str
    args: tuple["Node", ...] = ()
    payload: float | int | str | None = None


def input_node(index: int) -> Node:
    return Node("input", payload=int(index))


def constant(value: float) -> Node:
    return Node("constant", payload=float(value))


def op(name: str, *args: Node) -> Node:
    return Node(name, tuple(args))


@dataclass(frozen=True, slots=True)
class Program:
    dimension: int
    residuals: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Configuration:
    maximum_active_models: int = 8
    maximum_proposals: int = 8
    branch_relative_tolerance: float = 1.0e-10
    rank_relative_tolerance: float = 1.0e-11
    maximum_normalized_step: float = 4.0
    duplicate_relative_tolerance: float = 1.0e-9
    side_budget_fraction: float = 0.10


@dataclass(frozen=True, slots=True)
class ProposalResult:
    proposals: tuple[Array, ...]
    status: str
    active_sites: int
    models_considered: int
    models_accepted: int
    branch_mismatch_rejections: int


class UnsupportedTypedDAG(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _Jet:
    value: float
    gradient: Array


COMMUTATIVE = frozenset({"add", "mul", "min", "max"})
BRANCH_OPS = frozenset({"abs", "min", "max", "piecewise"})
SUPPORTED = frozenset(
    {
        "input",
        "constant",
        "add",
        "sub",
        "mul",
        "neg",
        "abs",
        "min",
        "max",
        "piecewise",
    }
)


def _key(node: Node) -> tuple:
    if node.op not in SUPPORTED:
        raise UnsupportedTypedDAG(node.op)
    child_keys = [_key(child) for child in node.args]
    if node.op in COMMUTATIVE:
        child_keys.sort(key=repr)
    return node.op, node.payload, tuple(child_keys)


def _ordered_args(node: Node) -> tuple[Node, ...]:
    if node.op not in COMMUTATIVE:
        return node.args
    return tuple(sorted(node.args, key=lambda child: repr(_key(child))))


def _site(node: Node) -> str:
    payload = json.dumps(_key(node), separators=(",", ":"), sort_keys=False)
    return sha256(payload.encode()).hexdigest()[:20]


def _near(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def _evaluate_node(
    node: Node,
    point: Array,
    forced: Mapping[str, str],
    tolerance: float,
    choices: dict[str, tuple[str, ...]],
    signature: dict[str, str],
) -> _Jet:
    if node.op not in SUPPORTED:
        raise UnsupportedTypedDAG(node.op)
    if node.op == "input":
        index = int(node.payload)  # type: ignore[arg-type]
        if not 0 <= index < point.size:
            raise UnsupportedTypedDAG("input-out-of-range")
        gradient = np.zeros(point.size, dtype=float)
        gradient[index] = 1.0
        return _Jet(float(point[index]), gradient)
    if node.op == "constant":
        return _Jet(float(node.payload), np.zeros(point.size, dtype=float))

    args = tuple(
        _evaluate_node(child, point, forced, tolerance, choices, signature)
        for child in _ordered_args(node)
    )
    if node.op == "add":
        return _Jet(args[0].value + args[1].value, args[0].gradient + args[1].gradient)
    if node.op == "sub":
        return _Jet(args[0].value - args[1].value, args[0].gradient - args[1].gradient)
    if node.op == "mul":
        return _Jet(
            args[0].value * args[1].value,
            args[0].gradient * args[1].value + args[1].gradient * args[0].value,
        )
    if node.op == "neg":
        return _Jet(-args[0].value, -args[0].gradient)

    site = _site(node)
    if node.op == "abs":
        available = ("negative", "positive") if _near(args[0].value, 0.0, tolerance) else (("negative",) if args[0].value < 0.0 else ("positive",))
        selected = forced.get(site, "negative" if args[0].value < 0.0 else "positive")
        if selected not in available and site in forced:
            # Forced adjacent extensions are legal only at the ambiguous anchor.
            available = tuple(sorted(set((*available, selected))))
        choices[site] = available
        signature[site] = selected
        sign = -1.0 if selected == "negative" else 1.0
        return _Jet(sign * args[0].value, sign * args[0].gradient)

    if node.op in {"min", "max"}:
        ambiguous = _near(args[0].value, args[1].value, tolerance)
        if ambiguous:
            available = ("first", "second")
        elif node.op == "min":
            available = ("first",) if args[0].value < args[1].value else ("second",)
        else:
            available = ("first",) if args[0].value > args[1].value else ("second",)
        selected = forced.get(site, available[0])
        if selected not in available and site in forced:
            available = tuple(sorted(set((*available, selected))))
        choices[site] = available
        signature[site] = selected
        return args[0] if selected == "first" else args[1]

    if node.op == "piecewise":
        if len(args) != 3:
            raise UnsupportedTypedDAG("piecewise-arity")
        selector, negative, positive = args
        available = ("negative", "positive") if _near(selector.value, 0.0, tolerance) else (("negative",) if selector.value < 0.0 else ("positive",))
        selected = forced.get(site, "negative" if selector.value < 0.0 else "positive")
        if selected not in available and site in forced:
            available = tuple(sorted(set((*available, selected))))
        choices[site] = available
        signature[site] = selected
        return negative if selected == "negative" else positive

    raise UnsupportedTypedDAG(node.op)


def evaluate_program(
    program: Program,
    point: Sequence[float],
    *,
    forced: Mapping[str, str] | None = None,
    branch_relative_tolerance: float = 1.0e-10,
) -> tuple[Array, Array, dict[str, tuple[str, ...]], dict[str, str]]:
    values = np.asarray(point, dtype=float)
    if values.shape != (program.dimension,) or not np.all(np.isfinite(values)):
        raise UnsupportedTypedDAG("invalid-point")
    choices: dict[str, tuple[str, ...]] = {}
    signature: dict[str, str] = {}
    jets = tuple(
        _evaluate_node(
            residual,
            values,
            forced or {},
            branch_relative_tolerance,
            choices,
            signature,
        )
        for residual in program.residuals
    )
    residual = np.asarray([jet.value for jet in jets], dtype=float)
    jacobian = np.vstack([jet.gradient for jet in jets])
    if not residual.size or jacobian.shape != (residual.size, program.dimension):
        raise UnsupportedTypedDAG("malformed-program")
    if not np.all(np.isfinite(residual)) or not np.all(np.isfinite(jacobian)):
        raise UnsupportedTypedDAG("nonfinite-program")
    return residual, jacobian, choices, signature


def _normalized_step(residual: Array, jacobian: Array, scale: Array, cfg: Configuration) -> Array | None:
    scaled = jacobian * scale[None, :]
    row_norm = np.maximum(np.linalg.norm(scaled, axis=1), np.abs(residual))
    if np.any(~np.isfinite(row_norm)) or np.any(row_norm <= 1.0e-14):
        return None
    matrix = scaled / row_norm[:, None]
    rhs = -residual / row_norm
    try:
        singular = np.linalg.svd(matrix, compute_uv=False)
        if not singular.size or singular[0] <= 0.0:
            return None
        rank = int(np.count_nonzero(singular > cfg.rank_relative_tolerance * singular[0]))
        if rank < scale.size:
            return None
        step = np.linalg.lstsq(matrix, rhs, rcond=cfg.rank_relative_tolerance)[0]
    except np.linalg.LinAlgError:
        return None
    norm = float(np.linalg.norm(step))
    if not np.all(np.isfinite(step)) or norm <= 1.0e-14:
        return None
    if norm > cfg.maximum_normalized_step:
        step = step * (cfg.maximum_normalized_step / norm)
    return step


def propose_active_strata(
    program: Program,
    point: Sequence[float],
    coordinate_scale: Sequence[float],
    *,
    semantic: Semantic | None = None,
    configuration: Configuration | None = None,
) -> ProposalResult:
    cfg = configuration or Configuration()
    x = np.asarray(point, dtype=float)
    scale = np.asarray(coordinate_scale, dtype=float)
    if x.shape != (program.dimension,) or scale.shape != x.shape or np.any(scale <= 0.0) or not np.all(np.isfinite(scale)):
        return ProposalResult((), "invalid_input", 0, 0, 0, 0)
    try:
        _residual, _jacobian, choices, _signature = evaluate_program(
            program,
            x,
            branch_relative_tolerance=cfg.branch_relative_tolerance,
        )
    except UnsupportedTypedDAG:
        return ProposalResult((), "opaque_or_unsupported_fallback", 0, 0, 0, 0)

    ambiguous = tuple(sorted(site for site, options in choices.items() if len(options) > 1))
    if not ambiguous:
        return ProposalResult((), "smooth_or_inactive_fallback", 0, 0, 0, 0)
    option_count = math.prod(len(choices[site]) for site in ambiguous)
    if option_count > cfg.maximum_active_models:
        return ProposalResult((), "too_many_active_strata_fallback", len(ambiguous), option_count, 0, 0)

    proposals: list[Array] = []
    accepted = 0
    mismatches = 0
    model_fingerprints: set[bytes] = set()
    for selected in product(*(choices[site] for site in ambiguous)):
        assignment = dict(zip(ambiguous, selected, strict=True))
        try:
            residual, jacobian, _model_choices, model_signature = evaluate_program(
                program,
                x,
                forced=assignment,
                branch_relative_tolerance=cfg.branch_relative_tolerance,
            )
        except UnsupportedTypedDAG:
            continue
        # Whole-matrix identity, not a row-wise Cartesian bundle.  Row order
        # and exact duplicate rows do not create additional model slots.
        normalized_rows = []
        for value, row in zip(residual, jacobian, strict=True):
            divisor = max(abs(float(value)), float(np.linalg.norm(row * scale)), 1.0e-300)
            normalized_rows.append(np.concatenate(([value / divisor], row * scale / divisor)))
        fingerprint = np.asarray(sorted((tuple(np.round(row, 13)) for row in normalized_rows)), dtype=float).tobytes()
        if fingerprint in model_fingerprints:
            continue
        model_fingerprints.add(fingerprint)
        step = _normalized_step(residual, jacobian, scale, cfg)
        if step is None:
            continue
        trial = x + scale * step
        try:
            _actual_r, _actual_j, _actual_choices, actual_signature = evaluate_program(
                program,
                trial,
                branch_relative_tolerance=cfg.branch_relative_tolerance,
            )
        except UnsupportedTypedDAG:
            continue
        if any(actual_signature.get(site) != model_signature.get(site) for site in ambiguous):
            mismatches += 1
            continue
        if semantic is not None and not bool(semantic(trial.copy())):
            continue
        accepted += 1
        tolerance = cfg.duplicate_relative_tolerance * max(1.0, float(np.linalg.norm(trial / scale)))
        if any(float(np.linalg.norm((trial - old) / scale)) <= tolerance for old in proposals):
            continue
        proposals.append(trial.copy())
        if len(proposals) >= cfg.maximum_proposals:
            break
    return ProposalResult(
        tuple(proposals),
        "ok" if proposals else "no_branch_consistent_regular_proposal",
        len(ambiguous),
        option_count,
        accepted,
        mismatches,
    )


__all__ = (
    "Configuration",
    "Node",
    "Program",
    "ProposalResult",
    "constant",
    "evaluate_program",
    "input_node",
    "op",
    "propose_active_strata",
)
