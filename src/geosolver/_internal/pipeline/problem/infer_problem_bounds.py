"""Infer and normalize search bounds for a problem bundle."""

from __future__ import annotations

import ast
import math
from typing import Any

from geosolver._internal.autosolve.compile.infer_bounds import (
    STRICT_PARAMETRIC_BOUND_FUNCS,
    _extract_call_name,
    _extract_param_variables,
    _iter_construction_exprs,
)
from geosolver._internal.autosolve.guards.compile import compile_guards, evaluate_bound_hint

from geosolver._internal.autosolve.execution.interpreter_helpers import _infer_bounds

from .load_problem_bundle import ProblemBundle

DEFAULT_BOUND_LOW = -48.0
DEFAULT_BOUND_HIGH = 48.0
DEFAULT_LITERAL_RELAX_SCALE = 10.0
MAX_LITERAL_RELAX_SCALE = 20000.0


def _default_bounds(size: int) -> list[tuple[float, float]]:
    return [(DEFAULT_BOUND_LOW, DEFAULT_BOUND_HIGH) for _ in range(size)]


def _extract_numeric_literal(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if not isinstance(node, ast.UnaryOp):
        return None
    operand = _extract_numeric_literal(node.operand)
    if operand is None:
        return None
    if isinstance(node.op, ast.UAdd):
        return float(operand)
    if isinstance(node.op, ast.USub):
        return float(-operand)
    return None


def _iter_spec_texts(spec: Any) -> tuple[str, ...]:
    texts: list[str] = list(_iter_construction_exprs(spec))
    constraints = getattr(spec, "constraints", None) or []
    for constraint in constraints:
        if isinstance(constraint, str) and constraint.strip():
            texts.append(constraint)
            continue
        if isinstance(constraint, dict):
            for key in ("def", "value", "expr", "definition"):
                value = constraint.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value)
            continue
        for attribute in ("def", "value", "expr", "definition"):
            value = getattr(constraint, attribute, None)
            if isinstance(value, str) and value.strip():
                texts.append(value)
    guards = getattr(spec, "guards", None) or []
    for guard in guards:
        if isinstance(guard, str) and guard.strip():
            texts.append(guard)
    return tuple(texts)


def _collect_literal_scale(bundle: ProblemBundle) -> float:
    max_abs_literal = 0.0
    for text in _iter_spec_texts(bundle.spec):
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            literal = _extract_numeric_literal(node)
            if literal is None or not math.isfinite(literal):
                continue
            max_abs_literal = max(max_abs_literal, abs(float(literal)))
    return max_abs_literal


def _collect_explicit_guard_bounds(
    bundle: ProblemBundle,
) -> tuple[dict[str, tuple[float | None, float | None]], set[str]]:
    explicit: dict[str, tuple[float | None, float | None]] = {}
    poisoned_variables: set[str] = set()
    compiled = compile_guards(getattr(bundle.spec, "guards", None) or [])
    for guard_ir in compiled:
        for hint in guard_ir.bounds_hints:
            evaluated = evaluate_bound_hint(hint, context=dict(bundle.base_context))
            if evaluated is None:
                continue
            variable_name, lower, upper = evaluated
            if variable_name in poisoned_variables:
                continue
            prev_lower, prev_upper = explicit.get(variable_name, (None, None))
            next_lower = prev_lower
            next_upper = prev_upper
            if lower is not None:
                lower_value = float(lower)
                next_lower = lower_value if prev_lower is None else max(prev_lower, lower_value)
            if upper is not None:
                upper_value = float(upper)
                next_upper = upper_value if prev_upper is None else min(prev_upper, upper_value)
            if next_lower is not None and next_upper is not None and next_lower >= next_upper:
                explicit.pop(variable_name, None)
                poisoned_variables.add(variable_name)
                continue
            explicit[variable_name] = (next_lower, next_upper)
    return explicit, poisoned_variables


def _infer_parametric_variable_names(bundle: ProblemBundle) -> set[str]:
    variable_names: set[str] = set()
    for expr in _iter_construction_exprs(bundle.spec):
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _extract_call_name(node) not in STRICT_PARAMETRIC_BOUND_FUNCS:
                continue
            variable_names.update(_extract_param_variables(node))
    return variable_names


def _expand_bounds_from_problem_scale(
    bundle: ProblemBundle,
    bounds: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    literal_scale = _collect_literal_scale(bundle)
    explicit_guard_bounds, _poisoned_variables = _collect_explicit_guard_bounds(bundle)
    parametric_variables = _infer_parametric_variable_names(bundle)
    expanded = list(bounds)
    relaxed_scale = min(
        max(literal_scale, DEFAULT_LITERAL_RELAX_SCALE),
        MAX_LITERAL_RELAX_SCALE,
    )

    for index, variable_name in enumerate(bundle.var_names):
        original_lower, original_upper = bounds[index]
        lower, upper = expanded[index]
        if variable_name in parametric_variables:
            continue

        explicit_lower, explicit_upper = explicit_guard_bounds.get(variable_name, (None, None))
        if explicit_lower is not None:
            lower = float(explicit_lower)
        if explicit_upper is not None:
            upper = float(explicit_upper)

        default_capped_axis = (
            max(abs(float(original_lower)), abs(float(original_upper)))
            <= DEFAULT_LITERAL_RELAX_SCALE
        )
        should_expand_unconstrained_axis = (
            explicit_lower is None
            and explicit_upper is None
            and default_capped_axis
            and literal_scale > max(abs(float(original_lower)), abs(float(original_upper)))
        )
        should_expand_one_sided_guard_axis = (
            default_capped_axis
            and ((explicit_lower is None) != (explicit_upper is None))
            and (
                lower != float(original_lower)
                or upper != float(original_upper)
                or literal_scale > max(abs(float(original_lower)), abs(float(original_upper)))
            )
        )
        current_range = upper - lower
        if (
            literal_scale > 0.0
            and current_range < relaxed_scale * 2.0
            and (should_expand_unconstrained_axis or should_expand_one_sided_guard_axis)
        ):
            if explicit_lower is None and explicit_upper is None:
                midpoint = (lower + upper) / 2.0
                lower = float(midpoint - relaxed_scale)
                upper = float(midpoint + relaxed_scale)
            elif explicit_lower is not None and explicit_upper is None:
                upper = max(upper, float(lower + relaxed_scale * 2.0))
            elif explicit_upper is not None and explicit_lower is None:
                lower = min(lower, float(upper - relaxed_scale * 2.0))

        if lower >= upper:
            expanded[index] = bounds[index]
            continue
        expanded[index] = (float(lower), float(upper))
    return expanded


def infer_problem_bounds(bundle: ProblemBundle) -> list[tuple[float, float]]:
    """Infer bounds and normalize invalid entries to default bounds."""
    size = len(bundle.var_names)
    if size == 0:
        return []
    raw_bounds = _infer_bounds(bundle.spec, size, bundle.base_context)
    if not isinstance(raw_bounds, list) or len(raw_bounds) != size:
        return _default_bounds(size)
    normalized: list[tuple[float, float]] = []
    for entry in raw_bounds:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            return _default_bounds(size)
        low = float(entry[0])
        high = float(entry[1])
        if (not math.isfinite(low)) or (not math.isfinite(high)) or low >= high:
            return _default_bounds(size)
        normalized.append((low, high))
    _, poisoned_variables = _collect_explicit_guard_bounds(bundle)
    defaults = _default_bounds(size)
    for index, variable_name in enumerate(bundle.var_names):
        if variable_name in poisoned_variables:
            normalized[index] = defaults[index]
    return _expand_bounds_from_problem_scale(bundle, normalized)

