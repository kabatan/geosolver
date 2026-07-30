"""Applicability-gated cached structural coloring ablation.

Unlike the rejected unconditional colored-FD prototype, this route compiles a
source-only dependency plan once per canonical semantic document and activates
only when it saves at least 20% of perturbation directions.  Selectors,
non-differentiable operators, malformed source, probe shape/nonfinite failures,
or branch-trace changes fall back to the unchanged dense finite difference.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


SCHEMA_VERSION = "geotarget.exp-eval-001-cached-sparsity/v1"
MIN_DIRECTION_REDUCTION = 0.20
_CONSTANT_NAMES = frozenset({"pi", "e", "True", "False", "None"})
_NONDIFFERENTIABLE_CALLS = frozenset(
    {
        "Abs",
        "Min",
        "Max",
        "Intersect",
        "ClosestPoint",
        "ContactPoint",
        "AssumeEq",
        "AssumeNe",
        "AssumeGt",
        "AssumeGe",
        "AssumeLt",
        "AssumeLe",
    }
)


@dataclass(frozen=True)
class SparsityPlan:
    schema_version: str
    mechanism_sha256: str
    dimension: int
    residual_rows: tuple[frozenset[int], ...]
    colors: tuple[tuple[int, ...], ...]
    eligible: bool
    fallback_reason: str | None

    @property
    def direction_reduction_fraction(self) -> float:
        if self.dimension == 0:
            return 0.0
        return 1.0 - len(self.colors) / self.dimension


@dataclass(frozen=True)
class JacobianResult:
    jacobian: np.ndarray
    mode: str
    direction_evaluations: int
    dense_direction_evaluations: int
    cache_hit: bool
    fallback_reason: str | None


def _canonical_semantic_document(document: Mapping[str, Any]) -> str:
    variables = document.get("variables")
    payload = {
        "variables": variables,
        "construction": document.get("construction"),
        "constraints": document.get("constraints"),
        "guards": document.get("guards"),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _dependency(
    raw: object,
    environment: Mapping[str, frozenset[int]],
    dense: frozenset[int],
) -> tuple[frozenset[int], bool, bool]:
    try:
        parsed = ast.parse(str(raw), mode="eval")
    except (SyntaxError, TypeError, ValueError):
        return dense, True, True
    function_nodes = {
        id(node.func) for node in ast.walk(parsed) if isinstance(node, ast.Call)
    }
    axes: set[int] = set()
    unresolved = False
    nonsmooth = False
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call) and _call_name(node.func) in _NONDIFFERENTIABLE_CALLS:
            nonsmooth = True
        if not isinstance(node, ast.Name):
            continue
        if id(node) in function_nodes or node.id in _CONSTANT_NAMES:
            continue
        value = environment.get(node.id)
        if value is None:
            unresolved = True
            axes.update(dense)
        else:
            axes.update(value)
    return frozenset(axes), unresolved, nonsmooth


def _colors(rows: Sequence[frozenset[int]], dimension: int) -> tuple[tuple[int, ...], ...]:
    adjacency = [set() for _ in range(dimension)]
    for row in rows:
        for axis in row:
            adjacency[axis].update(row - {axis})
    assigned: dict[int, int] = {}
    while len(assigned) < dimension:
        axis = max(
            (value for value in range(dimension) if value not in assigned),
            key=lambda value: (
                len({assigned[item] for item in adjacency[value] if item in assigned}),
                len(adjacency[value]),
                -value,
            ),
        )
        occupied = {assigned[item] for item in adjacency[axis] if item in assigned}
        color = 0
        while color in occupied:
            color += 1
        assigned[axis] = color
    return tuple(
        tuple(axis for axis in range(dimension) if assigned[axis] == color)
        for color in range(max(assigned.values(), default=-1) + 1)
    )


@functools.lru_cache(maxsize=512)
def _compile_cached(canonical_document: str) -> SparsityPlan:
    document = json.loads(canonical_document)
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        return SparsityPlan(SCHEMA_VERSION, hashlib.sha256(canonical_document.encode()).hexdigest(), 0, (), (), False, "invalid variables")
    dimension = len(names)
    dense = frozenset(range(dimension))
    environment = {name: frozenset({index}) for index, name in enumerate(names)}
    nonsmooth = False
    unresolved = False
    construction = document.get("construction")
    if not isinstance(construction, list):
        construction = []
        unresolved = True
    for item in construction:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            unresolved = True
            continue
        dependency, missing, branch = _dependency(item.get("expr"), environment, dense)
        environment[item["name"]] = dependency
        unresolved |= missing
        nonsmooth |= branch
    rows: list[frozenset[int]] = []
    constraints = document.get("constraints")
    if not isinstance(constraints, list):
        constraints = []
        unresolved = True
    for constraint in constraints:
        if not isinstance(constraint, Mapping):
            rows.append(dense)
            unresolved = True
            continue
        left, left_missing, left_branch = _dependency(
            constraint.get("def"), environment, dense
        )
        right, right_missing, right_branch = _dependency(
            constraint.get("value"), environment, dense
        )
        rows.append(left | right)
        unresolved |= left_missing or right_missing
        nonsmooth |= left_branch or right_branch
    guards = document.get("guards")
    if isinstance(guards, list) and guards:
        # Guard penalties are piecewise and can couple into the augmented
        # residual.  Keep the dense FD authority until a captured trace is
        # explicitly separated by a future candidate.
        nonsmooth = True
    colors = _colors(rows, dimension) if dimension else ()
    reduction = 0.0 if dimension == 0 else 1.0 - len(colors) / dimension
    reason = None
    if dimension == 0 or not rows:
        reason = "empty derivative system"
    elif nonsmooth:
        reason = "branch or non-differentiable operation"
    elif unresolved:
        reason = "unresolved source dependency"
    elif reduction < MIN_DIRECTION_REDUCTION:
        reason = "predicted direction saving below 20 percent"
    mechanism = hashlib.sha256(canonical_document.encode()).hexdigest()
    return SparsityPlan(
        SCHEMA_VERSION,
        mechanism,
        dimension,
        tuple(rows),
        colors,
        reason is None,
        reason,
    )


def compile_plan(document: Mapping[str, Any]) -> tuple[SparsityPlan, bool]:
    """Return an immutable cached plan and whether this call hit the cache."""

    canonical = _canonical_semantic_document(document)
    before = _compile_cached.cache_info().hits
    plan = _compile_cached(canonical)
    return plan, _compile_cached.cache_info().hits > before


def cache_info():
    return _compile_cached.cache_info()


def clear_cache() -> None:
    _compile_cached.cache_clear()


def _dense_fd(
    evaluate: Callable[[np.ndarray], np.ndarray],
    point: np.ndarray,
    current: np.ndarray,
    steps: np.ndarray,
) -> tuple[np.ndarray, int]:
    jacobian = np.empty((current.size, point.size), dtype=float)
    for axis in range(point.size):
        trial = point.copy()
        trial[axis] += steps[axis]
        value = np.asarray(evaluate(trial), dtype=float)
        if value.shape != current.shape or not np.all(np.isfinite(value)):
            raise ValueError("dense finite-difference probe is invalid")
        jacobian[:, axis] = (value - current) / steps[axis]
    return jacobian, point.size


def cached_colored_forward_difference(
    document: Mapping[str, Any],
    evaluate: Callable[[np.ndarray], np.ndarray],
    point: Sequence[float],
    current: Sequence[float],
    steps: Sequence[float],
    *,
    trace: Callable[[np.ndarray], object] | None = None,
) -> JacobianResult:
    """Compute a colored FD Jacobian, failing closed to dense FD."""

    x = np.asarray(point, dtype=float)
    f0 = np.asarray(current, dtype=float)
    h = np.asarray(steps, dtype=float)
    if x.ndim != 1 or f0.ndim != 1 or h.shape != x.shape:
        raise ValueError("invalid finite-difference shapes")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(f0)) or not np.all(np.isfinite(h)) or np.any(h == 0.0):
        raise ValueError("finite-difference inputs must be finite with nonzero steps")
    plan, hit = compile_plan(document)
    if (
        not plan.eligible
        or plan.dimension != x.size
        or len(plan.residual_rows) != f0.size
    ):
        jacobian, evaluations = _dense_fd(evaluate, x, f0, h)
        return JacobianResult(
            jacobian,
            "dense-fallback",
            evaluations,
            evaluations,
            hit,
            plan.fallback_reason or "source/evaluator shape mismatch",
        )
    base_trace = trace(x) if trace is not None else None
    jacobian = np.zeros((f0.size, x.size), dtype=float)
    evaluations = 0
    for color in plan.colors:
        trial = x.copy()
        for axis in color:
            trial[axis] += h[axis]
        value = np.asarray(evaluate(trial), dtype=float)
        evaluations += 1
        invalid = value.shape != f0.shape or not np.all(np.isfinite(value))
        trace_changed = trace is not None and trace(trial) != base_trace
        if invalid or trace_changed:
            dense, dense_evaluations = _dense_fd(evaluate, x, f0, h)
            return JacobianResult(
                dense,
                "dense-fallback",
                evaluations + dense_evaluations,
                dense_evaluations,
                hit,
                "probe invalid or branch trace changed",
            )
        difference = value - f0
        for axis in color:
            affected = [row for row, dependency in enumerate(plan.residual_rows) if axis in dependency]
            jacobian[affected, axis] = difference[affected] / h[axis]
    return JacobianResult(jacobian, "colored", evaluations, x.size, hit, None)
