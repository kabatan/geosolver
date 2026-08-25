from __future__ import annotations

import re
from typing import Any

from geosolver.problem.models import GeometryProblem, PredicateCondition, RelationCondition

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
    constraints: list[dict[str, object]] = []
    guards: list[str] = []
    for condition in problem.conditions:
        if isinstance(condition, RelationCondition):
            if condition.operator == "=":
                constraints.append({"def": condition.left, "value": condition.right})
            else:
                guard = RELATION_GUARDS[condition.operator]
                guards.append(f"{guard}({condition.left}, {_source(condition.right)})")
        elif isinstance(condition, PredicateCondition):
            guards.append(_predicate_to_engine(condition.predicate))
    return {
        "task": "solve",
        "id": problem.id,
        "variables": {"names": list(problem.variables)},
        "construction": [
            {"name": item.name, "expr": item.expression} for item in problem.constructions
        ],
        "constraints": constraints,
        "guards": guards,
        "answer": _target_to_engine(problem.target),
        "post_process": "",
    }
