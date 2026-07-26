"""Fast geometry execution context."""

from typing import Any

from .geometry import _get_geometry_context


def _get_fast_geometry_context() -> dict[str, Any]:
    """Build fast geometry context without legacy interpreter dependency."""
    try:
        from geosolver.geometry.geometry2d.fast import FastGeometryContext

        geometry_context = FastGeometryContext()
        context: dict[str, Any] = {}
        for name in dir(geometry_context):
            if name.startswith("_"):
                continue
            context[name] = getattr(geometry_context, name)
        context["N"] = geometry_context.N
        context["evalf"] = geometry_context.evalf
        return context
    except ImportError:
        return _get_geometry_context(prefer_fast=True)
