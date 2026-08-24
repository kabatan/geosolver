"""Standard geometry execution context."""

import math
from typing import Any

import geosolver.geometry as geom
from geosolver.engine.standard.interpreter.context.legacy_aliases import apply_legacy_aliases


def _get_geometry_context(prefer_fast: bool = False) -> dict[str, Any]:
    """Build geometry context for IR execution."""
    _ = prefer_fast
    context = {name: getattr(geom, name) for name in geom.__all__}
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
    return apply_legacy_aliases(context)
