"""Compile hard-feasibility checks from IR structure."""

from __future__ import annotations

import ast

from geosolver.engine.standard.contracts.hard_feasibility_check import (
    KIND_GUARD,
    KIND_INTERSECTION_EXCLUDE_DISTINCT,
    KIND_INTERSECTION_SELECTION_TRACE,
    KIND_LINE_DISTINCT,
    KIND_TRIANGLE_NONDEGENERATE,
    HardFeasibilityCheck,
)
from geosolver.problem.ir.schema import IRSpec

_LINE_FUNCTION_NAMES = ("Line", "LineThrough")
_TRIANGLE_FUNCTION_NAMES = ("Circumcircle", "TriangleCenter", "Incircle", "Incenter")


def _parse_call(expr: str) -> ast.Call | None:
    try:
        parsed = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    if not isinstance(parsed, ast.Expression):
        return None
    if not isinstance(parsed.body, ast.Call):
        return None
    return parsed.body


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _arg_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _first_n_name_args(call: ast.Call, count: int) -> tuple[str, ...]:
    selected: list[str] = []
    for arg in call.args[:count]:
        name = _arg_name(arg)
        if name is None:
            return ()
        selected.append(name)
    if len(selected) != count:
        return ()
    return tuple(selected)


def _keyword_name(call: ast.Call, key: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg != key:
            continue
        return _arg_name(keyword.value)
    return None


def compile_problem_hard_feasibility(spec: IRSpec) -> tuple[HardFeasibilityCheck, ...]:
    """Compile hard-feasibility checks from guards and constructions."""
    checks: list[HardFeasibilityCheck] = []
    for index, _guard in enumerate(spec.guards):
        checks.append(
            HardFeasibilityCheck(
                check_id=f"guard:{index}",
                kind=KIND_GUARD,
                symbol_names=(),
                reference_symbol=None,
            )
        )
    for item in spec.construction:
        call = _parse_call(item.expr)
        if call is None:
            continue
        func_name = _call_name(call.func)
        if func_name in _LINE_FUNCTION_NAMES:
            names = _first_n_name_args(call, 2)
            if names:
                checks.append(
                    HardFeasibilityCheck(
                        check_id=f"line_distinct:{item.name}",
                        kind=KIND_LINE_DISTINCT,
                        symbol_names=names,
                        reference_symbol=item.name,
                    )
                )
            continue
        if func_name in _TRIANGLE_FUNCTION_NAMES:
            names = _first_n_name_args(call, 3)
            if names:
                checks.append(
                    HardFeasibilityCheck(
                        check_id=f"triangle_nondegenerate:{item.name}",
                        kind=KIND_TRIANGLE_NONDEGENERATE,
                        symbol_names=names,
                        reference_symbol=item.name,
                    )
                )
            continue
        if func_name != "Intersect":
            continue
        exclude_symbol = _keyword_name(call, "exclude")
        if exclude_symbol is not None:
            checks.append(
                HardFeasibilityCheck(
                    check_id=f"intersection_exclude_distinct:{item.name}:{exclude_symbol}",
                    kind=KIND_INTERSECTION_EXCLUDE_DISTINCT,
                    symbol_names=(item.name, exclude_symbol),
                    reference_symbol=item.name,
                )
            )
        near_symbol = _keyword_name(call, "near")
        if near_symbol is not None:
            checks.append(
                HardFeasibilityCheck(
                    check_id=f"intersection_selection_trace:{item.name}:near",
                    kind=KIND_INTERSECTION_SELECTION_TRACE,
                    symbol_names=(item.name, near_symbol),
                    reference_symbol=item.name,
                )
            )
        far_symbol = _keyword_name(call, "far")
        if far_symbol is not None:
            checks.append(
                HardFeasibilityCheck(
                    check_id=f"intersection_selection_trace:{item.name}:far",
                    kind=KIND_INTERSECTION_SELECTION_TRACE,
                    symbol_names=(item.name, far_symbol),
                    reference_symbol=item.name,
                )
            )
    return tuple(checks)
