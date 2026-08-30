"""Standard geometry execution context."""

import math
from typing import Any

import geosolver.geometry as geom
from geosolver.engine.standard.interpreter.context.aliases import apply_geometry_aliases
from geosolver.problem.dsl_spec import dsl_spec


def _get_geometry_context() -> dict[str, Any]:
    """Build geometry context for IR execution."""
    complete = {name: getattr(geom, name) for name in geom.__all__}
    complete = apply_geometry_aliases(complete)
    context: dict[str, Any] = {}
    for symbol in dsl_spec().symbols:
        if symbol.symbol_kind == "macro":
            continue
        implementation = symbol.standard_implementation or symbol.name
        value = complete.get(implementation)
        if value is None:
            value = complete.get(symbol.name)
        if value is None:
            continue
        context[symbol.name] = value
        for alias in symbol.aliases:
            context[alias] = value
    context.update(
        {
            "abs": abs,
            "min": min,
            "max": max,
            "int": int,
            "float": float,
            "sqrt": geom.sqrt,
            "pi": math.pi,
        }
    )
    return context
