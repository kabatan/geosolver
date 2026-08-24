"""Helper routines for IR parser section parsing."""

from __future__ import annotations

from typing import Any, List, Sequence, Tuple

from geosolver.problem.ir.compiler import validate_expr_safety
from geosolver.problem.ir.errors import IRValidationError
from geosolver.problem.ir.schema import IRConstruction


def parse_construction(construction_raw: Sequence[Any]) -> List[IRConstruction]:
    construction: List[IRConstruction] = []
    for i, item in enumerate(construction_raw):
        if not isinstance(item, dict):
            raise IRValidationError(f"construction[{i}] must be object")
        name = item.get("name")
        expr = item.get("expr")
        if not isinstance(name, str) or not name:
            raise IRValidationError(f"construction[{i}].name must be non-empty string")
        validate_expr_safety(expr)
        construction.append(IRConstruction(name=name, expr=str(expr).strip()))
    return construction


def parse_constraints_and_values(constraints_raw: Sequence[Any]) -> Tuple[List[str], List[Any]]:
    constraints: List[str] = []
    inferred_v: List[Any] = []

    for i, item in enumerate(constraints_raw):
        if isinstance(item, str):
            validate_expr_safety(item)
            constraints.append(item.strip())
            inferred_v.append(0)
            continue

        if isinstance(item, dict):
            def_expr = item.get("def")
            val_expr = item.get("value", 0)
            if not isinstance(def_expr, str):
                raise IRValidationError(f"constraints[{i}].def must be string")
            validate_expr_safety(def_expr)
            constraints.append(def_expr.strip())
            inferred_v.append(val_expr)
            continue

        raise IRValidationError(f"constraints[{i}] must be string or object")

    return constraints, inferred_v


def parse_guards(guards_raw: Sequence[Any]) -> List[str]:
    guards: List[str] = []
    for i, expr in enumerate(guards_raw):
        if not isinstance(expr, str):
            raise IRValidationError(f"guards[{i}] must be string")
        validate_expr_safety(expr)
        guards.append(expr.strip())
    return guards