"""Opaque legacy-DSL runtime for disposable real61 algorithm experiments."""

from __future__ import annotations

import math
import ast
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np


LEGACY_REPO = Path("/home/kabatan/work/geosolver")
LEGACY_SOURCE = LEGACY_REPO / "src"


def load_legacy_runtime():
    source = str(LEGACY_SOURCE)
    if source not in sys.path:
        sys.path.insert(0, source)
    from geosolver._internal.pipeline.evaluator.ir_evaluator import build_ir_evaluator
    from geosolver._internal.pipeline.problem.infer_problem_bounds import infer_problem_bounds
    from geosolver._internal.pipeline.problem.load_problem_bundle import load_problem_bundle
    from geosolver._internal.autosolve.execution.interpreter_helpers import _guard_violation_penalty

    return load_problem_bundle, build_ir_evaluator, infer_problem_bounds, _guard_violation_penalty


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class OpaqueEvaluation:
    residual: np.ndarray
    finite: bool
    semantics_valid: bool
    violation: float
    violation_vector: np.ndarray


@dataclass(frozen=True)
class OpaqueCase:
    dimension: int
    residual_dimension: int
    lower: np.ndarray
    upper: np.ndarray
    origin: np.ndarray
    scales: np.ndarray
    legacy_lower: np.ndarray
    legacy_upper: np.ndarray
    strict_guard_lower: np.ndarray
    strict_guard_upper: np.ndarray
    circle_manifolds: tuple[tuple[tuple[int, int], tuple[float, float], float], ...]
    circle_intersections: tuple[tuple[tuple[int, int], tuple[float, float], tuple[float, float]], ...]
    evaluate: Callable[[np.ndarray], OpaqueEvaluation]
    progressive_residual: Callable[[np.ndarray], np.ndarray]


def _constant_guard_value(node: ast.AST) -> float | None:
    """Evaluate the deliberately tiny numeric language accepted in guard bounds."""

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in {"pi", "e"}:
        return math.pi if node.id == "pi" else math.e
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _constant_guard_value(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _constant_guard_value(node.left), _constant_guard_value(node.right)
        if left is None or right is None:
            return None
        try:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right
        except (OverflowError, ZeroDivisionError, ValueError):
            return None
    return None


def _strict_guard_bounds(document: dict[str, object], names: Sequence[str]):
    """Extract only direct affine one-variable strict bounds from guard syntax."""

    index = {name: position for position, name in enumerate(names)}
    lower = np.full(len(names), -math.inf)
    upper = np.full(len(names), math.inf)

    def add(variable: ast.AST, value_node: ast.AST, relation: str) -> None:
        if not isinstance(variable, ast.Name) or variable.id not in index:
            return
        value = _constant_guard_value(value_node)
        if value is None or not math.isfinite(value):
            return
        axis = index[variable.id]
        if relation == "gt":
            lower[axis] = max(lower[axis], value)
        else:
            upper[axis] = min(upper[axis], value)

    for text in document.get("guards") or ():
        try:
            node = ast.parse(str(text), mode="eval").body
        except (SyntaxError, TypeError):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"AssumeGt", "AssumeLt"} and len(node.args) == 2:
                add(node.args[0], node.args[1], "gt" if node.func.id == "AssumeGt" else "lt")
            elif node.func.id == "Bound" and len(node.args) >= 2:
                interval = node.args[1]
                if isinstance(interval, (ast.Tuple, ast.List)) and len(interval.elts) == 2:
                    add(node.args[0], interval.elts[0], "gt")
                    add(node.args[0], interval.elts[1], "lt")
            elif node.func.id == "Assume" and len(node.args) == 1:
                comparison = node.args[0]
                if isinstance(comparison, ast.Compare) and len(comparison.ops) == 1:
                    if isinstance(comparison.ops[0], ast.Gt):
                        add(comparison.left, comparison.comparators[0], "gt")
                    elif isinstance(comparison.ops[0], ast.Lt):
                        add(comparison.left, comparison.comparators[0], "lt")
        # Conflicting extracted guards are not charted; the evaluator remains authoritative.
    conflict = lower >= upper
    lower[conflict], upper[conflict] = -math.inf, math.inf
    return lower, upper


class EvaluationBudget:
    def __init__(
        self, evaluator, guard_violation_penalty, residual_dimension: int,
        callback_cap: int, deadline: float,
    ):
        self._evaluator = evaluator
        self._guard_violation_penalty = guard_violation_penalty
        self._residual_dimension = residual_dimension
        self._callback_cap = int(callback_cap)
        self._deadline = float(deadline)
        self.callbacks = 0
        self.finite = 0
        self.invalid = 0
        self.guard_failed = 0
        self.best_norm = math.inf

    def _charge(self) -> None:
        if self.callbacks >= self._callback_cap:
            raise BudgetExceeded("callback_cap")
        if time.monotonic() >= self._deadline:
            raise BudgetExceeded("deadline")
        self.callbacks += 1

    def __call__(self, point: np.ndarray) -> OpaqueEvaluation:
        self._charge()
        values = np.asarray(point, dtype=float)
        try:
            observation = self._evaluator.evaluate_float_residual(values.tolist())
            guard_ok, _ = self._evaluator.evaluate_guard(values.tolist())
            hard = self._evaluator.evaluate_float_hard_feasibility(values.tolist())
            residual = np.asarray(observation.residual_vector, dtype=float)
            finite = bool(
                observation.is_finite
                and residual.shape == (self._residual_dimension,)
                and np.all(np.isfinite(residual))
            )
            semantics = bool(guard_ok and hard.hard_feasible)
            guard_penalty = float(
                self._guard_violation_penalty(
                    values.tolist(),
                    spec=self._evaluator.bundle.spec,
                    var_names=list(self._evaluator.bundle.var_names),
                    base_context=dict(self._evaluator.bundle.base_context),
                    compiled_guards=self._evaluator.compiled_guards,
                )
            )
            try:
                from geosolver._internal.autosolve.execution.interpreter_helpers import (
                    _build_guard_context,
                )
                from geosolver._internal.autosolve.guards.compile import guard_violation_value

                context = _build_guard_context(
                    self._evaluator.bundle.spec,
                    list(self._evaluator.bundle.var_names),
                    values.tolist(),
                    dict(self._evaluator.bundle.base_context),
                )
                guard_vector = np.asarray(
                    [
                        float(guard_violation_value(guard, context))
                        for guard in self._evaluator.compiled_guards
                    ],
                    dtype=float,
                )
                guard_vector = np.where(np.isfinite(guard_vector), guard_vector, 1.0)
            except Exception:
                guard_vector = np.ones(len(self._evaluator.compiled_guards), dtype=float)
            hard_penalty = 0.0
            if not hard.hard_feasible:
                if hard.min_margin is not None and math.isfinite(float(hard.min_margin)):
                    hard_penalty = max(0.0, -float(hard.min_margin))
                else:
                    hard_penalty = 1.0
            violation_vector = np.concatenate(
                (guard_vector, np.asarray([hard_penalty], dtype=float))
            )
            violation = guard_penalty + hard_penalty
        except Exception:
            residual = np.full(self._residual_dimension, math.inf)
            finite = False
            semantics = False
            violation = 1.0
            violation_vector = np.ones(1, dtype=float)
        if finite:
            self.finite += 1
            self.best_norm = min(self.best_norm, float(np.linalg.norm(residual, ord=np.inf)))
        else:
            self.invalid += 1
        if finite and not semantics:
            self.guard_failed += 1
        return OpaqueEvaluation(
            residual,
            finite,
            semantics,
            max(0.0, float(violation)),
            np.maximum(0.0, violation_vector),
        )

    def progressive_residual(self, point: np.ndarray) -> np.ndarray:
        """Keep evaluable relation prefixes active when later constructions fail."""

        self._charge()
        values = np.asarray(point, dtype=float)
        from geosolver._internal.autosolve.execution.interpreter_helpers import (
            _assign_variables,
            _evaluate_target,
            _to_float,
        )
        from geosolver.ir.compiler import safe_eval_expr

        bundle = self._evaluator.bundle
        context = dict(bundle.base_context)
        _assign_variables(context, list(bundle.var_names), values.tolist())
        for item in bundle.spec.construction:
            try:
                context[item.name] = safe_eval_expr(item.expr, context)
            except Exception:
                continue
        residuals = []
        available = 0
        for index, expression in enumerate(bundle.spec.constraints):
            try:
                lhs = _to_float(safe_eval_expr(expression, context))
                rhs = _evaluate_target(bundle.targets[index], context)
                residual = float(lhs - rhs)
                if not math.isfinite(residual):
                    raise ValueError("nonfinite progressive residual")
                residuals.append(residual)
                available += 1
            except Exception:
                # A fixed missing-relation term preserves vector size.  Other
                # available equations retain their local directional signal.
                residuals.append(1.0e3)
        vector = np.asarray(residuals, dtype=float)
        if available:
            self.finite += 1
            finite_values = np.abs(vector[np.abs(vector) < 1.0e3])
            if finite_values.size:
                self.best_norm = min(self.best_norm, float(np.max(finite_values)))
        else:
            self.invalid += 1
        return vector


def _source_bounds(document: dict[str, object], dimension: int) -> tuple[np.ndarray, np.ndarray]:
    raw = document.get("bounds")
    if raw is None:
        return np.full(dimension, -math.inf), np.full(dimension, math.inf)
    if not isinstance(raw, list) or len(raw) != dimension:
        raise ValueError("source bounds do not match variables.names")
    lower = np.asarray([float(pair[0]) for pair in raw], dtype=float)
    upper = np.asarray([float(pair[1]) for pair in raw], dtype=float)
    if not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper)) or not np.all(lower < upper):
        raise ValueError("source bounds must be finite and ordered")
    return lower, upper


def _circle_manifolds(bundle) -> tuple[tuple[tuple[int, int], tuple[float, float], float], ...]:
    from geosolver.ir.compiler import safe_eval_expr

    variable_index = {name: index for index, name in enumerate(bundle.var_names)}
    variable_points: dict[str, tuple[int, int]] = {}
    fixed_points: dict[str, tuple[float, float]] = {}
    context = dict(bundle.base_context)
    for item in bundle.spec.construction:
        try:
            expression = ast.parse(item.expr, mode="eval").body
        except (SyntaxError, TypeError):
            continue
        if (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id == "Point"
            and len(expression.args) == 2
            and all(isinstance(argument, ast.Name) for argument in expression.args)
        ):
            axes = tuple(variable_index.get(argument.id) for argument in expression.args)
            if all(axis is not None for axis in axes):
                variable_points[item.name] = (int(axes[0]), int(axes[1]))
        try:
            value = safe_eval_expr(item.expr, context)
            context[item.name] = value
            x_value, y_value = float(value.x), float(value.y)
            if math.isfinite(x_value) and math.isfinite(y_value):
                fixed_points[item.name] = (x_value, y_value)
        except Exception:
            continue
    manifolds = []
    for constraint, target in zip(bundle.spec.constraints, bundle.targets, strict=True):
        try:
            expression = ast.parse(constraint, mode="eval").body
        except (SyntaxError, TypeError):
            continue
        if not (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id == "Distance"
            and len(expression.args) == 2
            and all(isinstance(argument, ast.Name) for argument in expression.args)
        ):
            continue
        left, right = expression.args[0].id, expression.args[1].id
        axes, center = variable_points.get(left), fixed_points.get(right)
        if axes is None or center is None:
            axes, center = variable_points.get(right), fixed_points.get(left)
        try:
            radius = float(target)
        except Exception:
            continue
        if axes is not None and center is not None and math.isfinite(radius) and radius > 0:
            manifolds.append((axes, center, radius))
    return tuple(dict.fromkeys(manifolds))


def _circle_intersections(manifolds):
    by_axes: dict[tuple[int, int], list[tuple[tuple[float, float], float]]] = {}
    for axes, center, radius in manifolds:
        by_axes.setdefault(axes, []).append((center, radius))
    intersections = []
    for axes, circles in by_axes.items():
        for first_index in range(len(circles)):
            for second_index in range(first_index + 1, len(circles)):
                (x0, y0), r0 = circles[first_index]
                (x1, y1), r1 = circles[second_index]
                dx, dy = x1 - x0, y1 - y0
                distance = math.hypot(dx, dy)
                if distance == 0 or distance > r0 + r1 or distance < abs(r0 - r1):
                    continue
                along = (r0 * r0 - r1 * r1 + distance * distance) / (2.0 * distance)
                height_squared = r0 * r0 - along * along
                if height_squared < -1.0e-12 * max(1.0, r0 * r0):
                    continue
                height = math.sqrt(max(0.0, height_squared))
                base_x = x0 + along * dx / distance
                base_y = y0 + along * dy / distance
                offset_x, offset_y = -dy * height / distance, dx * height / distance
                first = (base_x + offset_x, base_y + offset_y)
                second = (base_x - offset_x, base_y - offset_y)
                intersections.append((axes, first, second))
    return tuple(dict.fromkeys(intersections))


def build_opaque_case(
    document: dict[str, object], *, callback_cap: int, deadline: float
) -> tuple[OpaqueCase, EvaluationBudget, object]:
    (
        load_problem_bundle,
        build_ir_evaluator,
        infer_problem_bounds,
        guard_violation_penalty,
    ) = load_legacy_runtime()
    bundle = load_problem_bundle(document, prefer_fast=False)
    evaluator = build_ir_evaluator(bundle)
    dimension = len(bundle.var_names)
    residual_dimension = len(bundle.targets)
    lower, upper = _source_bounds(document, dimension)
    inferred = infer_problem_bounds(bundle)
    if len(inferred) != dimension:
        raise ValueError("legacy bounds inference returned the wrong dimension")
    legacy_lower = np.asarray([pair[0] for pair in inferred], dtype=float)
    legacy_upper = np.asarray([pair[1] for pair in inferred], dtype=float)
    source_bounded = np.isfinite(lower) & np.isfinite(upper)
    origin = legacy_lower / 2.0 + legacy_upper / 2.0
    scales = legacy_upper / 2.0 - legacy_lower / 2.0
    origin[source_bounded] = lower[source_bounded] / 2.0 + upper[source_bounded] / 2.0
    scales[source_bounded] = upper[source_bounded] / 2.0 - lower[source_bounded] / 2.0
    scales = np.clip(np.where(np.isfinite(scales), scales, 1.0), 1.0e-12, 1.0e6)
    budget = EvaluationBudget(
        evaluator, guard_violation_penalty, residual_dimension, callback_cap, deadline
    )
    manifolds = _circle_manifolds(bundle)
    strict_lower, strict_upper = _strict_guard_bounds(document, bundle.var_names)
    opaque = OpaqueCase(
        dimension,
        residual_dimension,
        lower,
        upper,
        origin,
        scales,
        legacy_lower,
        legacy_upper,
        strict_lower,
        strict_upper,
        manifolds,
        _circle_intersections(manifolds),
        budget,
        budget.progressive_residual,
    )
    return opaque, budget, evaluator


def validate_endpoint(evaluator, point: Sequence[float], precision: int = 140) -> dict[str, object]:
    values = [float(value) for value in point]
    try:
        residual = evaluator.evaluate_float_residual(values)
        guard_ok, violations = evaluator.evaluate_guard(values)
        hard = evaluator.evaluate_float_hard_feasibility(values)
        residual_norm = float(residual.residual_norm_float)
        safe = bool(
            residual.is_finite
            and guard_ok
            and hard.hard_feasible
            and math.isfinite(residual_norm)
            and residual_norm <= 1.0e-8
        )
    except Exception as error:
        return {
            "endpoint": values,
            "safe": False,
            "residual_inf": None,
            "guard_ok": False,
            "hard_feasible": False,
            "error": f"{type(error).__name__}: {error}",
            "diagnostic_target": None,
        }
    target = None
    if safe:
        try:
            from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
                BoundaryOrigin,
                boundary_float_to_mpf,
            )
            from geosolver._internal.solver.precision.type_guards.high_precision_mode import (
                high_precision_mode,
            )
            from mpmath import mp

            hp_values = [
                boundary_float_to_mpf(value, origin=BoundaryOrigin.SCIPY_OPTIMIZE)
                for value in values
            ]
            with mp.workdps(precision), high_precision_mode():
                answer = evaluator.evaluate_answer_hp(hp_values, precision=precision)
            if answer.answer_hp is not None and mp.isfinite(answer.answer_hp):
                target = mp.nstr(answer.answer_hp, 50)
        except Exception:
            target = None
    return {
        # This is experiment evidence, not a certified witness.  Persisting the
        # exact float endpoint lets the separate high-precision proposal stage
        # replay the finalist without rerunning or silently changing its start.
        "endpoint": values,
        "safe": safe,
        "residual_inf": residual_norm if math.isfinite(residual_norm) else None,
        "guard_ok": bool(guard_ok),
        "guard_violations": list(violations),
        "hard_feasible": bool(hard.hard_feasible),
        "hard_failure_tags": list(hard.failure_tags),
        "diagnostic_target": target,
        "diagnostic_target_is_exact": False,
    }
