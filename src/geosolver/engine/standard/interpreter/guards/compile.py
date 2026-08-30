"""Guard compilation and evaluation helpers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from mpmath import mp

from geosolver.problem.expression_source import source_expression
from geosolver.problem.ir.compiler import safe_eval_expr_hp

from .evaluate import _is_guard_satisfied
from .registry import (
    get_residual_guard_template,
    get_triangle_class,
    is_compare_guard,
)

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
    children: tuple[GuardIR, ...] = ()


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
    try:
        parsed = ast.parse(text, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(parsed, ast.Call) or not isinstance(parsed.func, ast.Name):
        return None
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


def _compile_compare_guard(source: str, lhs_expr: str, rhs_expr: str, operator: str) -> GuardIR:
    return GuardIR(
        source=source,
        kind="compare",
        operator=operator,
        lhs_expr=lhs_expr.strip(),
        rhs_expr=rhs_expr.strip(),
    )


def _compile_bound_call(source: str, body: str) -> GuardIR | None:
    """Compile a ``Bound`` call, including calls nested in ``Assume``.

    ``Bound`` exposes ``message`` as its only optional positional argument;
    ``inclusive`` and the tolerance knobs are keyword-only.  The guard IR
    only needs the interval and inclusivity, so message/tolerance arguments
    are accepted and ignored here while malformed calls remain raw guards.
    """
    try:
        parsed = ast.parse(f"Bound({body})", mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(parsed, ast.Call):
        return None
    keywords = {keyword.arg: keyword.value for keyword in parsed.keywords if keyword.arg}
    value_node = parsed.args[0] if parsed.args else keywords.get("value")
    interval_node = parsed.args[1] if len(parsed.args) > 1 else keywords.get("bounds")
    if value_node is None or interval_node is None:
        return None
    if not isinstance(interval_node, ast.Tuple | ast.List) or len(interval_node.elts) != 2:
        return None
    value_expr = source_expression(value_node, f"Bound({body})")
    lower_node, upper_node = interval_node.elts
    lower_expr = (
        None
        if isinstance(lower_node, ast.Constant) and lower_node.value is None
        else source_expression(lower_node, f"Bound({body})")
    )
    upper_expr = (
        None
        if isinstance(upper_node, ast.Constant) and upper_node.value is None
        else source_expression(upper_node, f"Bound({body})")
    )
    if lower_expr is None and upper_expr is None:
        return None
    inclusive = True
    inclusive_node = keywords.get("inclusive")
    if inclusive_node is not None:
        if not isinstance(inclusive_node, ast.Constant) or not isinstance(
            inclusive_node.value, bool
        ):
            return None
        inclusive = inclusive_node.value
    return GuardIR(
        source=source,
        kind="bound" if inclusive else "bound_open",
        operator="closed" if inclusive else "open",
        lhs_expr=value_expr,
        lower_expr=lower_expr,
        upper_expr=upper_expr,
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


def _compile_residual_template(
    source: str,
    template: str,
    body: str,
) -> GuardIR | None:
    """Compile a residual guard template after checking its arity."""
    expected_parts = template.count("{")
    parts = _split_top_level_args(body, expected_parts=expected_parts)
    if parts is None:
        return None
    return _compile_residual_guard(source, template.format(*parts))


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
    try:
        parsed = ast.parse(expr, mode="eval").body
    except SyntaxError:
        parsed = None
    if isinstance(parsed, ast.BoolOp):
        children = tuple(
            _compile_condition_expr(source_expression(n, expr), source_expression(n, expr))
            for n in parsed.values
        )
        is_and = isinstance(parsed.op, ast.And)
        return GuardIR(
            source=source,
            kind="logical_and" if is_and else "logical_or",
            children=children,
        )
    if isinstance(parsed, ast.UnaryOp) and isinstance(parsed.op, ast.Not):
        child = source_expression(parsed.operand, expr)
        return GuardIR(
            source=source, kind="logical_not", children=(_compile_condition_expr(child, child),)
        )
    if isinstance(parsed, ast.Compare):
        children: list[GuardIR] = []
        left = parsed.left
        operator_names = {
            ast.Gt: ">",
            ast.GtE: ">=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Eq: "==",
            ast.NotEq: "!=",
        }
        for operator_node, right in zip(parsed.ops, parsed.comparators, strict=True):
            operator = operator_names.get(type(operator_node))
            if operator is None:
                return _compile_raw_condition(source, expr)
            children.append(
                _compile_compare_guard(
                    source_expression(
                        ast.Compare(left=left, ops=[operator_node], comparators=[right]), expr
                    ),
                    source_expression(left, expr),
                    source_expression(right, expr),
                    operator,
                )
            )
            left = right
        if len(children) == 1:
            return children[0]
        return GuardIR(
            source=source,
            kind="logical_and",
            children=tuple(children),
        )
    call = _extract_call_signature(expr)
    if call is not None:
        func_name, body = call
        if func_name == "Bound":
            bound_guard = _compile_bound_call(source, body)
            if bound_guard is not None:
                return bound_guard
        if func_name == "And":
            parts = _split_top_level_args(body)
            if parts:
                children = tuple(_compile_condition_expr(part, part) for part in parts)
                return GuardIR(
                    source=source,
                    kind="logical_and",
                    children=children,
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
                    children=(_compile_condition_expr(parts[0], parts[0]),),
                )
        residual_template = get_residual_guard_template(func_name)
        if residual_template is not None:
            residual_guard = _compile_residual_template(
                source,
                residual_template,
                body,
            )
            if residual_guard is not None:
                return residual_guard
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


def compile_guard_expr(guard_expr: str) -> GuardIR:
    text = str(guard_expr).strip()
    call = _extract_call_signature(text)
    if call is None:
        return _compile_condition_expr(text, text)

    func_name, body = call
    if func_name == "Bound":
        bound_guard = _compile_bound_call(text, body)
        if bound_guard is not None:
            return bound_guard
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

    if func_name in {"And", "Or", "Not"}:
        return _compile_condition_expr(text, text)

    triangle_class = get_triangle_class(func_name)
    if triangle_class is not None:
        parts = _split_top_level_args(body, expected_parts=3)
        if parts:
            return _compile_triangle_class_guard(text, triangle_class, parts)
        return _compile_raw_condition(text, text)

    residual_template = get_residual_guard_template(func_name)
    if residual_template is not None:
        residual_guard = _compile_residual_template(text, residual_template, body)
        if residual_guard is not None:
            return residual_guard
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
    if isinstance(value, tuple | list) and len(value) == _POINT_COORDINATE_COUNT:
        return _as_mpf(value[0]), _as_mpf(value[1])
    raise TypeError("triangle-class guard requires point-like arguments")


def _triangle_class_measures(
    guard: GuardIR,
    context: dict[str, Any],
) -> tuple[Any, Any, Any]:
    if len(guard.argument_exprs) != _TRIANGLE_VERTEX_COUNT:
        raise ValueError("triangle-class guard requires exactly three arguments")

    points = tuple(_point_xy(_safe_eval_numeric(expr, context)) for expr in guard.argument_exprs)
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
    sine_measure = cross / cross_denominator if cross_denominator > 0 else mp.mpf("0")

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
        for dot, denominator in zip(dot_products, cosine_denominators, strict=False)
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
        return lhs > rhs
    if operator == ">=":
        return lhs >= rhs - tol
    if operator == "<":
        return lhs < rhs
    if operator == "<=":
        return lhs <= rhs + tol
    if operator == "==":
        return abs(lhs - rhs) <= tol
    if operator == "!=":
        return lhs != rhs
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


def _normalized_positive_margin(gap: Any, *scale_values: Any) -> Any:
    """Return a dimensionless distance from a strict guard boundary."""
    gap_mpf = _as_mpf(gap)
    if not mp.isfinite(gap_mpf):
        return mp.mpf("0")
    scale = mp.mpf("1")
    for value in scale_values:
        try:
            scale = max(scale, abs(_as_mpf(value)))
        except Exception:
            continue
    return max(mp.mpf("0"), gap_mpf) / scale


def _convexity_margin(guard: GuardIR, context: dict[str, Any]) -> Any:
    """Return the smallest strict turn margin for ``AssumeConvex``."""
    call = _extract_call_signature(str(guard.condition_expr or guard.source))
    if call is None or call[0] not in {"AssumeConvex", "AssumeStrictConvex"}:
        return mp.inf
    parts = _split_top_level_args(call[1])
    if not parts:
        return mp.inf
    try:
        raw_points = (
            _safe_eval_numeric(parts[0], context)
            if len(parts) == 1
            else [_safe_eval_numeric(part, context) for part in parts]
        )
        points = tuple(_point_xy(point) for point in raw_points)
    except Exception:
        return mp.inf
    if len(points) < 3:
        return mp.mpf("0")
    minimum = mp.inf
    for index in range(len(points)):
        previous = points[index - 1]
        current = points[index]
        following = points[(index + 1) % len(points)]
        first_x = current[0] - previous[0]
        first_y = current[1] - previous[1]
        second_x = following[0] - current[0]
        second_y = following[1] - current[1]
        denominator = mp.sqrt(first_x * first_x + first_y * first_y) * mp.sqrt(
            second_x * second_x + second_y * second_y
        )
        if denominator <= 0:
            return mp.mpf("0")
        minimum = min(
            minimum,
            abs(first_x * second_y - first_y * second_x) / denominator,
        )
    return minimum


def guard_margin_value(guard: GuardIR, context: dict[str, Any]) -> Any:
    """Return the geometric margin for a guard that has passed.

    Strict comparisons and open bounds receive a finite, dimensionless
    margin. Closed/equality predicates have an allowed boundary and therefore
    return ``+inf``. Unknown predicates retain the legacy ``+inf`` value;
    their truth is still checked by ``guard_hard_satisfied``.
    """
    if guard.kind == "compare":
        lhs = _as_mpf(_safe_eval_numeric(str(guard.lhs_expr), context))
        rhs = _as_mpf(_safe_eval_numeric(str(guard.rhs_expr), context))
        operator = str(guard.operator)
        if operator == ">":
            return _normalized_positive_margin(lhs - rhs, lhs, rhs)
        if operator == "<":
            return _normalized_positive_margin(rhs - lhs, lhs, rhs)
        if operator == "!=":
            return _normalized_positive_margin(abs(lhs - rhs), lhs, rhs)
        return mp.inf
    if guard.kind == "bound_open":
        value = _as_mpf(_safe_eval_numeric(str(guard.lhs_expr), context))
        margins: list[Any] = []
        if guard.lower_expr is not None:
            lower = _as_mpf(_safe_eval_numeric(guard.lower_expr, context))
            margins.append(_normalized_positive_margin(value - lower, value, lower))
        if guard.upper_expr is not None:
            upper = _as_mpf(_safe_eval_numeric(guard.upper_expr, context))
            margins.append(_normalized_positive_margin(upper - value, value, upper))
        return min(margins) if margins else mp.inf
    if guard.kind == "triangle_class":
        side_ratio, sine_measure, minimum_cosine = _triangle_class_measures(
            guard,
            context,
        )
        if guard.operator == "acute":
            return min(side_ratio, sine_measure, minimum_cosine)
        if guard.operator == "obtuse":
            return min(side_ratio, sine_measure, -minimum_cosine)
        if guard.operator == "right":
            return min(side_ratio, sine_measure)
        return mp.inf
    if guard.kind == "logical_and":
        return min(
            (guard_margin_value(child, context) for child in guard.children),
            default=mp.inf,
        )
    if guard.kind == "logical_or":
        passing = [
            guard_margin_value(child, context)
            for child in guard.children
            if guard_hard_satisfied(child, context)
        ]
        return max(passing) if passing else mp.mpf("0")
    if guard.kind == "raw_condition":
        return _convexity_margin(guard, context)
    return mp.inf


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
                if value <= lower:
                    return False
            else:
                if value < lower - tol:
                    return False
        if guard.upper_expr is not None:
            upper = _as_mpf(_safe_eval_numeric(guard.upper_expr, context))
            if is_open:
                if value >= upper:
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
