"""Guard compilation and evaluation helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from mpmath import mp

from geosolver.ir.compiler import safe_eval_expr, safe_eval_expr_hp

from .evaluate import _is_guard_satisfied
from .registry import (
    get_residual_guard_template,
    get_triangle_class,
    is_compare_guard,
)

_VARIABLE_NAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
_COMPARISON_OPERATORS: tuple[str, ...] = (">=", "<=", "!=", "==", ">", "<")
_POINT_COORDINATE_COUNT = 2
_TRIANGLE_VERTEX_COUNT = 3
_COMPARE_GUARD_OPERATOR_MAP: dict[str, str] = {
    "AssumeGt": ">",
    "AssumeGe": ">=",
    "AssumeLt": "<",
    "AssumeLe": "<=",
    "AssumeEq": "==",
    "AssumeNe": "!=",
}


@dataclass(frozen=True)
class GuardBoundHint:
    variable: str
    lower_expr: str | None = None
    upper_expr: str | None = None


@dataclass(frozen=True)
class GuardIR:
    source: str
    kind: str
    operator: str | None = None
    lhs_expr: str | None = None
    rhs_expr: str | None = None
    lower_expr: str | None = None
    upper_expr: str | None = None
    residual_expr: str | None = None
    condition_expr: str | None = None
    argument_exprs: tuple[str, ...] = ()
    children: tuple["GuardIR", ...] = ()
    bounds_hints: tuple[GuardBoundHint, ...] = ()


def _split_top_level_args(arg_text: str, expected_parts: int | None = None) -> list[str] | None:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in arg_text:
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        current.append(char)
    parts.append("".join(current).strip())
    if expected_parts is not None and len(parts) != int(expected_parts):
        return None
    return parts


def _extract_call_signature(expr: str) -> tuple[str, str] | None:
    text = expr.strip()
    if not text.endswith(")"):
        return None
    depth = 0
    first_open = -1
    for index, char in enumerate(text):
        if char == "(":
            if depth == 0:
                first_open = index
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return None
    if depth != 0 or first_open <= 0:
        return None
    name = text[:first_open].strip()
    body = text[first_open + 1 : -1].strip()
    if not name:
        return None
    return name, body


def _is_simple_variable(expr: str) -> bool:
    text = expr.strip()
    if not text:
        return False
    if text[0].isdigit():
        return False
    return all(char in _VARIABLE_NAME_CHARS for char in text)


def _make_bounds_hints_for_compare(lhs_expr: str, rhs_expr: str, operator: str) -> tuple[GuardBoundHint, ...]:
    lhs_is_var = _is_simple_variable(lhs_expr)
    rhs_is_var = _is_simple_variable(rhs_expr)
    if lhs_is_var == rhs_is_var:
        return ()
    if lhs_is_var:
        if operator in (">", ">="):
            return (GuardBoundHint(variable=lhs_expr, lower_expr=rhs_expr),)
        if operator in ("<", "<="):
            return (GuardBoundHint(variable=lhs_expr, upper_expr=rhs_expr),)
        return ()
    if operator in (">", ">="):
        return (GuardBoundHint(variable=rhs_expr, upper_expr=lhs_expr),)
    if operator in ("<", "<="):
        return (GuardBoundHint(variable=rhs_expr, lower_expr=lhs_expr),)
    return ()


def _compile_compare_guard(source: str, lhs_expr: str, rhs_expr: str, operator: str) -> GuardIR:
    return GuardIR(
        source=source,
        kind="compare",
        operator=operator,
        lhs_expr=lhs_expr.strip(),
        rhs_expr=rhs_expr.strip(),
        bounds_hints=_make_bounds_hints_for_compare(lhs_expr.strip(), rhs_expr.strip(), operator),
    )


def _compile_bound_guard(
    source: str,
    value_expr: str,
    interval_expr: str,
    *,
    inclusive: bool = True,
) -> GuardIR:
    interval_text = interval_expr.strip()
    if interval_text.startswith("(") and interval_text.endswith(")"):
        parts = _split_top_level_args(interval_text[1:-1], expected_parts=2)
    else:
        parts = None
    lower_expr = parts[0].strip() if parts else None
    upper_expr = parts[1].strip() if parts else None
    bounds_hints: tuple[GuardBoundHint, ...] = ()
    if _is_simple_variable(value_expr.strip()):
        bounds_hints = (
            GuardBoundHint(
                variable=value_expr.strip(),
                lower_expr=lower_expr,
                upper_expr=upper_expr,
            ),
        )
    kind = "bound" if inclusive else "bound_open"
    operator = "closed" if inclusive else "open"
    return GuardIR(
        source=source,
        kind=kind,
        operator=operator,
        lhs_expr=value_expr.strip(),
        lower_expr=lower_expr,
        upper_expr=upper_expr,
        bounds_hints=bounds_hints,
    )


def _compile_residual_guard(source: str, residual_expr: str) -> GuardIR:
    return GuardIR(
        source=source,
        kind="residual",
        residual_expr=residual_expr,
    )


def _compile_triangle_class_guard(
    source: str,
    triangle_class: str,
    argument_exprs: list[str],
) -> GuardIR:
    return GuardIR(
        source=source,
        kind="triangle_class",
        operator=triangle_class,
        argument_exprs=tuple(expr.strip() for expr in argument_exprs),
    )


def _compile_raw_condition(source: str, condition_expr: str) -> GuardIR:
    return GuardIR(
        source=source,
        kind="raw_condition",
        condition_expr=condition_expr.strip(),
    )


def _split_top_level_compare(expr: str) -> tuple[str, str, str] | None:
    text = expr.strip()
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0:
            for operator in _COMPARISON_OPERATORS:
                if text.startswith(operator, index):
                    lhs = text[:index].strip()
                    rhs = text[index + len(operator) :].strip()
                    if lhs and rhs:
                        return lhs, operator, rhs
        index += 1
    return None


def _compile_condition_expr(source: str, expr: str) -> GuardIR:
    call = _extract_call_signature(expr)
    if call is not None:
        func_name, body = call
        if func_name == "And":
            parts = _split_top_level_args(body)
            if parts:
                return GuardIR(
                    source=source,
                    kind="logical_and",
                    children=tuple(_compile_condition_expr(part, part) for part in parts),
                )
        if func_name == "Or":
            parts = _split_top_level_args(body)
            if parts:
                return GuardIR(
                    source=source,
                    kind="logical_or",
                    children=tuple(_compile_condition_expr(part, part) for part in parts),
                )
        if func_name == "Not":
            parts = _split_top_level_args(body, expected_parts=1)
            if parts:
                return GuardIR(
                    source=source,
                    kind="logical_not",
                    children=( _compile_condition_expr(parts[0], parts[0]), ),
                )
        if func_name in _COMPARE_GUARD_OPERATOR_MAP:
            parts = _split_top_level_args(body, expected_parts=2)
            if parts:
                return _compile_compare_guard(
                    source,
                    parts[0],
                    parts[1],
                    _COMPARE_GUARD_OPERATOR_MAP[func_name],
                )
    compare = _split_top_level_compare(expr)
    if compare is not None:
        lhs_expr, operator, rhs_expr = compare
        return _compile_compare_guard(source, lhs_expr, rhs_expr, operator)
    return _compile_raw_condition(source, expr)


def _parse_inclusive_kwarg(expr: str) -> bool:
    """Parse inclusive=True/False from a Bound third argument."""
    text = expr.strip()
    if "=" in text:
        text = text.split("=", 1)[1].strip()
    return text != "False"


def compile_guard_expr(guard_expr: str) -> GuardIR:
    text = str(guard_expr).strip()
    call = _extract_call_signature(text)
    if call is None:
        return _compile_condition_expr(text, text)

    func_name, body = call
    if func_name == "Bound":
        parts_2 = _split_top_level_args(body, expected_parts=2)
        if parts_2:
            return _compile_bound_guard(text, parts_2[0], parts_2[1])
        parts_3 = _split_top_level_args(body, expected_parts=3)
        if parts_3:
            inclusive = _parse_inclusive_kwarg(parts_3[2])
            return _compile_bound_guard(text, parts_3[0], parts_3[1], inclusive=inclusive)
        return _compile_raw_condition(text, text)

    if is_compare_guard(func_name):
        parts = _split_top_level_args(body, expected_parts=2)
        if parts:
            return _compile_compare_guard(
                text,
                parts[0],
                parts[1],
                _COMPARE_GUARD_OPERATOR_MAP[func_name],
            )
        return _compile_raw_condition(text, text)

    if func_name == "Assume":
        parts = _split_top_level_args(body, expected_parts=1)
        if parts:
            return _compile_condition_expr(text, parts[0])
        return _compile_raw_condition(text, text)

    triangle_class = get_triangle_class(func_name)
    if triangle_class is not None:
        parts = _split_top_level_args(body, expected_parts=3)
        if parts:
            return _compile_triangle_class_guard(text, triangle_class, parts)
        return _compile_raw_condition(text, text)

    residual_template = get_residual_guard_template(func_name)
    if residual_template is not None:
        parts = _split_top_level_args(body)
        if parts:
            return _compile_residual_guard(text, residual_template.format(*parts))
        return _compile_raw_condition(text, text)

    return _compile_raw_condition(text, text)


def compile_guards(guards: list[str] | tuple[str, ...] | None) -> tuple[GuardIR, ...]:
    if not guards:
        return ()
    return tuple(compile_guard_expr(str(guard_expr)) for guard_expr in guards)


def _guard_numeric_tolerance() -> Any:
    return mp.power(mp.mpf("10"), -max(12, int(mp.dps // 2)))


def _safe_eval_numeric(expr: str, context: dict[str, Any]) -> Any:
    return safe_eval_expr_hp(expr, context)


def _as_mpf(value: Any) -> Any:
    if isinstance(value, mp.mpf):
        return value
    return mp.mpf(value)


def _point_xy(value: Any) -> tuple[Any, Any]:
    if hasattr(value, "x") and hasattr(value, "y"):
        return _as_mpf(value.x), _as_mpf(value.y)
    if (
        isinstance(value, (tuple, list))
        and len(value) == _POINT_COORDINATE_COUNT
    ):
        return _as_mpf(value[0]), _as_mpf(value[1])
    raise TypeError("triangle-class guard requires point-like arguments")


def _triangle_class_measures(
    guard: GuardIR,
    context: dict[str, Any],
) -> tuple[Any, Any, Any]:
    if len(guard.argument_exprs) != _TRIANGLE_VERTEX_COUNT:
        raise ValueError("triangle-class guard requires exactly three arguments")

    points = tuple(
        _point_xy(_safe_eval_numeric(expr, context))
        for expr in guard.argument_exprs
    )
    (ax, ay), (bx, by), (cx, cy) = points

    abx, aby = bx - ax, by - ay
    acx, acy = cx - ax, cy - ay
    bax, bay = ax - bx, ay - by
    bcx, bcy = cx - bx, cy - by
    cax, cay = ax - cx, ay - cy
    cbx, cby = bx - cx, by - cy

    ab2 = abx * abx + aby * aby
    ac2 = acx * acx + acy * acy
    bc2 = bcx * bcx + bcy * bcy
    maximum_side2 = max(ab2, ac2, bc2)
    if maximum_side2 <= 0:
        return mp.mpf("0"), mp.mpf("0"), mp.mpf("0")

    side_ratio = min(ab2, ac2, bc2) / maximum_side2
    cross = abs(abx * acy - aby * acx)
    cross_denominator = mp.sqrt(ab2 * ac2)
    sine_measure = (
        cross / cross_denominator
        if cross_denominator > 0
        else mp.mpf("0")
    )

    cosine_denominators = (
        mp.sqrt(ab2 * ac2),
        mp.sqrt(ab2 * bc2),
        mp.sqrt(ac2 * bc2),
    )
    dot_products = (
        abx * acx + aby * acy,
        bax * bcx + bay * bcy,
        cax * cbx + cay * cby,
    )
    cosines = tuple(
        dot / denominator if denominator > 0 else mp.mpf("0")
        for dot, denominator in zip(dot_products, cosine_denominators)
    )
    return side_ratio, sine_measure, min(cosines)


def _triangle_class_hard_satisfied(
    guard: GuardIR,
    context: dict[str, Any],
) -> bool:
    side_ratio, sine_measure, minimum_cosine = _triangle_class_measures(
        guard,
        context,
    )
    tol = _guard_numeric_tolerance()
    if side_ratio <= tol or sine_measure <= tol:
        return False
    if guard.operator == "acute":
        return minimum_cosine > tol
    if guard.operator == "obtuse":
        return minimum_cosine < -tol
    if guard.operator == "right":
        return abs(minimum_cosine) <= tol
    return False


def _triangle_class_violation(
    guard: GuardIR,
    context: dict[str, Any],
) -> Any:
    side_ratio, sine_measure, minimum_cosine = _triangle_class_measures(
        guard,
        context,
    )
    tol = _guard_numeric_tolerance()
    degeneracy = max(
        mp.mpf("0"),
        tol - side_ratio,
        tol - sine_measure,
    )
    if guard.operator == "acute":
        relation = max(mp.mpf("0"), tol - minimum_cosine)
    elif guard.operator == "obtuse":
        relation = max(mp.mpf("0"), minimum_cosine + tol)
    elif guard.operator == "right":
        relation = max(mp.mpf("0"), abs(minimum_cosine) - tol)
    else:
        return mp.mpf("1")
    return max(degeneracy, relation)


def _compare_hard_satisfied(lhs_value: Any, rhs_value: Any, operator: str) -> bool:
    lhs = _as_mpf(lhs_value)
    rhs = _as_mpf(rhs_value)
    tol = _guard_numeric_tolerance()
    if operator == ">":
        return lhs > rhs + tol
    if operator == ">=":
        return lhs >= rhs - tol
    if operator == "<":
        return lhs < rhs - tol
    if operator == "<=":
        return lhs <= rhs + tol
    if operator == "==":
        return abs(lhs - rhs) <= tol
    if operator == "!=":
        return abs(lhs - rhs) > tol
    return False


def _compare_violation(lhs_value: Any, rhs_value: Any, operator: str) -> Any:
    lhs = _as_mpf(lhs_value)
    rhs = _as_mpf(rhs_value)
    tol = _guard_numeric_tolerance()
    if operator == ">":
        return max(mp.mpf("0"), rhs - lhs + tol)
    if operator == ">=":
        return max(mp.mpf("0"), rhs - lhs - tol)
    if operator == "<":
        return max(mp.mpf("0"), lhs - rhs + tol)
    if operator == "<=":
        return max(mp.mpf("0"), lhs - rhs - tol)
    if operator == "==":
        return max(mp.mpf("0"), abs(lhs - rhs) - tol)
    if operator == "!=":
        return max(mp.mpf("0"), tol - abs(lhs - rhs))
    return mp.mpf("1")


def guard_hard_satisfied(guard: GuardIR, context: dict[str, Any]) -> bool:
    if guard.kind == "triangle_class":
        return _triangle_class_hard_satisfied(guard, context)
    if guard.kind == "compare":
        lhs_value = _safe_eval_numeric(str(guard.lhs_expr), context)
        rhs_value = _safe_eval_numeric(str(guard.rhs_expr), context)
        return _compare_hard_satisfied(lhs_value, rhs_value, str(guard.operator))
    if guard.kind in ("bound", "bound_open"):
        value = _as_mpf(_safe_eval_numeric(str(guard.lhs_expr), context))
        tol = _guard_numeric_tolerance()
        is_open = guard.kind == "bound_open"
        if guard.lower_expr is not None:
            lower = _as_mpf(_safe_eval_numeric(guard.lower_expr, context))
            if is_open:
                if value <= lower + tol:
                    return False
            else:
                if value < lower - tol:
                    return False
        if guard.upper_expr is not None:
            upper = _as_mpf(_safe_eval_numeric(guard.upper_expr, context))
            if is_open:
                if value >= upper - tol:
                    return False
            else:
                if value > upper + tol:
                    return False
        return True
    if guard.kind == "residual":
        residual_value = _as_mpf(_safe_eval_numeric(str(guard.residual_expr), context))
        return abs(residual_value) <= _guard_numeric_tolerance()
    if guard.kind == "logical_and":
        return all(guard_hard_satisfied(child, context) for child in guard.children)
    if guard.kind == "logical_or":
        return any(guard_hard_satisfied(child, context) for child in guard.children)
    if guard.kind == "logical_not":
        return not guard_hard_satisfied(guard.children[0], context)
    expr = guard.condition_expr if guard.condition_expr is not None else guard.source
    return _is_guard_satisfied(safe_eval_expr_hp(expr, context))


def guard_violation_value(guard: GuardIR, context: dict[str, Any]) -> Any:
    if guard.kind == "triangle_class":
        return _triangle_class_violation(guard, context)
    if guard.kind == "compare":
        lhs_value = _safe_eval_numeric(str(guard.lhs_expr), context)
        rhs_value = _safe_eval_numeric(str(guard.rhs_expr), context)
        return _compare_violation(lhs_value, rhs_value, str(guard.operator))
    if guard.kind in ("bound", "bound_open"):
        value = _as_mpf(_safe_eval_numeric(str(guard.lhs_expr), context))
        tol = _guard_numeric_tolerance()
        total = mp.mpf("0")
        if guard.lower_expr is not None:
            lower = _as_mpf(_safe_eval_numeric(guard.lower_expr, context))
            if guard.kind == "bound_open":
                total += max(mp.mpf("0"), lower - value + tol)
            else:
                total += max(mp.mpf("0"), lower - value - tol)
        if guard.upper_expr is not None:
            upper = _as_mpf(_safe_eval_numeric(guard.upper_expr, context))
            if guard.kind == "bound_open":
                total += max(mp.mpf("0"), value - upper + tol)
            else:
                total += max(mp.mpf("0"), value - upper - tol)
        return total
    if guard.kind == "residual":
        residual_value = _as_mpf(_safe_eval_numeric(str(guard.residual_expr), context))
        return max(mp.mpf("0"), abs(residual_value) - _guard_numeric_tolerance())
    if guard.kind == "logical_and":
        if not guard.children:
            return mp.mpf("0")
        return max(guard_violation_value(child, context) for child in guard.children)
    if guard.kind == "logical_or":
        if not guard.children:
            return mp.mpf("0")
        return min(guard_violation_value(child, context) for child in guard.children)
    if guard.kind == "logical_not":
        child_value = guard_violation_value(guard.children[0], context)
        return mp.mpf("0") if child_value > 0 else mp.mpf("1")
    return mp.mpf("0") if guard_hard_satisfied(guard, context) else mp.mpf("1")


def evaluate_bound_hint(
    hint: GuardBoundHint,
    *,
    context: dict[str, Any],
) -> tuple[str, float | None, float | None] | None:
    lower_value: float | None = None
    upper_value: float | None = None
    try:
        if hint.lower_expr is not None:
            lower_raw = safe_eval_expr(hint.lower_expr, context)
            lower_value = float(lower_raw.evalf()) if hasattr(lower_raw, "evalf") else float(lower_raw)
        if hint.upper_expr is not None:
            upper_raw = safe_eval_expr(hint.upper_expr, context)
            upper_value = float(upper_raw.evalf()) if hasattr(upper_raw, "evalf") else float(upper_raw)
    except Exception:
        return None
    if lower_value is not None and not math.isfinite(lower_value):
        return None
    if upper_value is not None and not math.isfinite(upper_value):
        return None
    if lower_value is not None and upper_value is not None and lower_value >= upper_value:
        return None
    return hint.variable, lower_value, upper_value
