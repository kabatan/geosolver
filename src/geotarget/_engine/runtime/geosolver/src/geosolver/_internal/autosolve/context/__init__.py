"""Autosolve execution context builders."""

from .fast import _get_fast_geometry_context
from .geometry import _get_geometry_context
from .high_precision import _get_high_precision_context

__all__ = ["_get_fast_geometry_context", "_get_geometry_context", "_get_high_precision_context"]
