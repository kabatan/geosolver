"""Search-bound inference helpers for autosolve execution."""

from __future__ import annotations

import ast
from typing import Any

from geosolver.engine.standard.interpreter.guards.compile import compile_guards, evaluate_bound_hint
from geosolver.ir.compiler import safe_eval_expr
from geosolver.ir.schema import IRSpec


DEFAULT_SCALE = 10.0
MAX_TARGET_VALUE = 1e6
TARGET_SCALE_MULTIPLIER = 2.0
ANGLE_MIN_SCALE = 5.0
STRICT_PARAMETRIC_BOUND_FUNCS = {
    "InscribedPolygon",
    "PointOnArc",
    "PointOnCircle",
    "PointOnSegment",
}


def _extract_call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _extract_param_variables(node: ast.Call) -> tuple[str, ...]:
    param_vars: list[str] = []
    for keyword in node.keywords:
        if keyword.arg:
            param_vars.append(keyword.arg)
    if param_vars or not node.args:
        return tuple(param_vars)
    last_arg = node.args[-1]
    if isinstance(last_arg, ast.Name):
        param_vars.append(last_arg.id)
    return tuple(param_vars)


def _iter_construction_exprs(spec: Any) -> tuple[str, ...]:
    construction = getattr(spec, "construction", None) or []
    exprs: list[str] = []
    for item in construction:
        expr = getattr(item, "expr", None)
        if isinstance(expr, str) and expr.strip():
            exprs.append(expr)
    return tuple(exprs)


def _tighten_parametric_construction_bounds(
    bounds: list[tuple[float, float]],
    *,
    spec: Any,
    name_to_index: dict[str, int],
) -> int:
    tightened = 0
    for expr in _iter_construction_exprs(spec):
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = _extract_call_name(node)
            if func_name not in STRICT_PARAMETRIC_BOUND_FUNCS:
                continue
            for variable_name in _extract_param_variables(node):
                index = name_to_index.get(variable_name)
                if index is None:
                    continue
                before = bounds[index]
                _tighten_bound(bounds, index=index, lower=0.0, upper=1.0)
                if bounds[index] != before:
                    tightened += 1
    return tightened


def _tighten_bound(
    bounds: list[tuple[float, float]],
    *,
    index: int,
    lower: float | None = None,
    upper: float | None = None,
) -> None:
    if index < 0 or index >= len(bounds):
        return
    current_lower, current_upper = bounds[index]
    next_lower = current_lower if lower is None else max(current_lower, float(lower))
    next_upper = current_upper if upper is None else min(current_upper, float(upper))
    if next_lower < next_upper:
        bounds[index] = (next_lower, next_upper)


def infer_bound_expansion_locks(
    spec: IRSpec,
    var_names: list[str] | tuple[str, ...],
    context: dict[str, Any],
) -> list[tuple[bool, bool]]:
    """Infer per-axis lower/upper expansion locks from semantic and explicit bounds.

    Args:
        spec: Problem IR whose bounds, guards, and constructions define domain semantics.
        var_names: Variable order used by the active search backend.
        context: Evaluation context for guard-bound expressions.

    Returns:
        List of ``(lower_locked, upper_locked)`` flags aligned with ``var_names``.
    """
    locks: list[tuple[bool, bool]] = [(False, False) for _ in var_names]
    if not var_names:
        return locks
    name_to_index = {name: index for index, name in enumerate(var_names)}
    try:
        explicit_bounds = getattr(spec, "bounds", None)
        if isinstance(explicit_bounds, list):
            for index, entry in enumerate(explicit_bounds[: len(var_names)]):
                if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                    continue
                low = float(entry[0])
                high = float(entry[1])
                if low >= high:
                    continue
                locks[index] = (True, True)
        compiled_guards = compile_guards(getattr(spec, "guards", None) or [])
        for guard_ir in compiled_guards:
            for hint in guard_ir.bounds_hints:
                evaluated = evaluate_bound_hint(hint, context=context)
                if evaluated is None:
                    continue
                variable, lower, upper = evaluated
                index = name_to_index.get(variable)
                if index is None:
                    continue
                lower_locked, upper_locked = locks[index]
                if lower is not None:
                    lower_locked = True
                if upper is not None:
                    upper_locked = True
                locks[index] = (lower_locked, upper_locked)
        for expr in _iter_construction_exprs(spec):
            try:
                tree = ast.parse(expr, mode="eval")
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func_name = _extract_call_name(node)
                if func_name not in STRICT_PARAMETRIC_BOUND_FUNCS:
                    continue
                for variable_name in _extract_param_variables(node):
                    index = name_to_index.get(variable_name)
                    if index is None:
                        continue
                    locks[index] = (True, True)
    except Exception:
        return locks
    return locks


def infer_bounds(
    spec: Any,
    n_vars: int,
    context: dict[str, Any],
    diagnostics: dict[str, Any] | None = None,
) -> list[tuple[float, float]]:
    """Infer numeric search bounds from IR constraints and guard hints."""
    default_scale = DEFAULT_SCALE
    max_scale = default_scale
    has_angle_constraint = False
    has_pi_value = False

    targets = getattr(spec, "v", None) or []
    for target in targets:
        if isinstance(target, str):
            if "pi" in target.lower():
                has_pi_value = True
                has_angle_constraint = True
            try:
                value = safe_eval_expr(target, context)
                value_f = float(value.evalf()) if hasattr(value, "evalf") else float(value)
                if 0 < value_f < MAX_TARGET_VALUE:
                    max_scale = max(max_scale, value_f * TARGET_SCALE_MULTIPLIER)
            except Exception:
                pass
        elif isinstance(target, (int, float)) and 0 < float(target) < MAX_TARGET_VALUE:
            max_scale = max(max_scale, float(target) * TARGET_SCALE_MULTIPLIER)

    constraints = getattr(spec, "constraints", None) or []
    for constraint in constraints:
        if "Angle" in str(constraint):
            has_angle_constraint = True

    scale = max_scale
    if has_angle_constraint or has_pi_value:
        scale = max(ANGLE_MIN_SCALE, scale)

    bounds: list[tuple[float, float]] = [(-scale, scale) for _ in range(n_vars)]

    compiled_guard_count = 0
    transformable_guard_count = 0
    ignored_guard_count = 0
    construction_param_bound_count = 0

    try:
        var_names: list[str] = []
        variables = getattr(spec, "variables", None)
        if isinstance(variables, dict):
            var_names = variables.get("names", []) or []
        else:
            var_names = getattr(variables, "names", []) or []
        if not var_names:
            if diagnostics is not None:
                diagnostics["compiled_guard_count"] = 0
                diagnostics["transformable_guard_count"] = 0
                diagnostics["ignored_guard_count"] = 0
                diagnostics["construction_param_bound_count"] = 0
            return bounds

        name_to_index = {name: index for index, name in enumerate(var_names)}
        compiled_guards = compile_guards(getattr(spec, "guards", None) or [])
        compiled_guard_count = len(compiled_guards)
        for guard_ir in compiled_guards:
            has_applicable_hint = False
            for hint in guard_ir.bounds_hints:
                evaluated = evaluate_bound_hint(hint, context=context)
                if evaluated is None:
                    continue
                variable, lower, upper = evaluated
                index = name_to_index.get(variable)
                if index is None:
                    continue
                _tighten_bound(bounds, index=index, lower=lower, upper=upper)
                has_applicable_hint = True
            if guard_ir.kind in ("bound", "bound_open"):
                if has_applicable_hint:
                    transformable_guard_count += 1
                else:
                    ignored_guard_count += 1
            elif guard_ir.kind == "compare" and guard_ir.bounds_hints:
                if has_applicable_hint:
                    transformable_guard_count += 1
                else:
                    ignored_guard_count += 1
            elif guard_ir.kind not in ("logical_and", "logical_or", "logical_not"):
                if not has_applicable_hint:
                    ignored_guard_count += 1
        construction_param_bound_count = _tighten_parametric_construction_bounds(
            bounds,
            spec=spec,
            name_to_index=name_to_index,
        )
    except Exception:
        pass

    if diagnostics is not None:
        diagnostics["compiled_guard_count"] = compiled_guard_count
        diagnostics["transformable_guard_count"] = transformable_guard_count
        diagnostics["ignored_guard_count"] = ignored_guard_count
        diagnostics["construction_param_bound_count"] = construction_param_bound_count

    return bounds
