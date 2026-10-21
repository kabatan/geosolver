"""Autosolve execution context builders."""

from .geometry import _get_geometry_context
from .high_precision import _get_high_precision_context

__all__ = ["_get_geometry_context", "_get_high_precision_context"]
