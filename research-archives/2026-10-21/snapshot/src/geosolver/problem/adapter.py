from __future__ import annotations

import re
from typing import Any

from geosolver.problem.compiler import (
    CompiledPredicate,
    CompiledRelation,
    compile_problem,
    predicate_guard_source,
)
from geosolver.problem.models import GeometryProblem

RELATION_GUARDS = {
    "!=": "AssumeNe",
    "<": "AssumeLt",
    "<=": "AssumeLe",
    ">": "AssumeGt",
    ">=": "AssumeGe",
}

PREDICATE_ALIASES = {
    "AcuteTriangle": "AssumeAcute",
    "RightTriangle": "AssumeRight",
    "ObtuseTriangle": "AssumeObtuse",
    "ConvexPolygon": "AssumeConvex",
    "SimplePolygon": "AssumeNoSelfIntersecting",
    "Order": "AssumeOrder",
}


def _target_to_engine(expression: str) -> str:
    stripped = expression.strip()
    match = re.fullmatch(r"Degrees\s*\((.*)\)", stripped, flags=re.DOTALL)
    if match is None:
        return expression
    return f"(({match.group(1)}) * 180 / pi)"


def _source(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        raise TypeError("boolean is not a scalar expression")
    return repr(value)


def _predicate_to_engine(expression: str) -> str:
    stripped = expression.strip()
    # ``Bound`` is already a solver-native guard.  Keeping it at the top
    # level lets the guard compiler represent it as a bound constraint rather
    # than evaluating it as a nested Python call in the HP context.
    if re.match(r"^Bound\s*\(", stripped):
        return stripped
    for public_name, engine_name in PREDICATE_ALIASES.items():
        if re.match(rf"^{re.escape(public_name)}\s*\(", stripped):
            return re.sub(
                rf"^{re.escape(public_name)}",
                engine_name,
                stripped,
                count=1,
            )
    return f"Assume({stripped})"


def to_engine_document(problem: GeometryProblem) -> dict[str, Any]:
    compiled = compile_problem(problem)
    constraints: list[dict[str, object]] = []
    guards: list[str] = []
    for condition in compiled.conditions:
        if isinstance(condition, CompiledRelation):
            right_value: object = (
                condition.right.source
                if condition.right_literal is None
                else condition.right_literal
            )
            if condition.operator == "=":
                constraints.append({"def": condition.left.source, "value": right_value})
            else:
                guard = RELATION_GUARDS[condition.operator]
                guards.append(f"{guard}({condition.left.source}, {_source(right_value)})")
        elif isinstance(condition, CompiledPredicate):
            guards.append(_predicate_to_engine(predicate_guard_source(condition.expression)))
    return {
        "task": "solve",
        "id": compiled.identifier,
        "variables": {"names": list(compiled.variables)},
        "construction": [
            {"name": item.name, "expr": item.expression.source} for item in compiled.constructions
        ],
        "constraints": constraints,
        "guards": guards,
        "answer": _target_to_engine(compiled.target.source),
        "post_process": "",
    }
