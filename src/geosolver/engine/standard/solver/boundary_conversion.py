"""Zone B boundary conversion helper for solve-engine candidates.

This module provides ``solve_boundary_mpf``, a Zone B utility that converts
a single candidate scalar from Zone A (float / numpy.floating) or Zone C
(mpf / int / Fraction) into an mpf value.

This replaces the former ``_strict_boundary_mpf`` private helper that was
defined inside ``engine.py``, resolving the duplicate-
implementation debt identified in REFACTORING_PLAN.md and WP4.
"""
# zone: b

from __future__ import annotations

from typing import Any

try:
    import numpy as np
    _NUMPY_FLOATING_TYPES: tuple[type, ...] = (np.floating,)
except Exception:  # pragma: no cover
    _NUMPY_FLOATING_TYPES = ()

from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf
from mpmath import mpf


def solve_boundary_mpf(value: Any, *, context: str) -> mpf:
    """Convert a solver candidate scalar to mpf at the Zone B boundary.

    Args:
        value: A ``float`` / ``numpy.floating`` from Zone A (e.g. scipy output),
            or an already-HP value (``mpf`` / ``int``) from Zone C.
        context: Diagnostic label for error messages.

    Returns:
        An ``mpf`` value.

    Raises:
        HighPrecisionContaminationError: If *value* is float-like and
            non-finite, or if HP mode is active when a float enters.
        TypeError: For unsupported input types.
    """
    if isinstance(value, float):
        return boundary_float_to_mpf(value, origin=BoundaryOrigin.SCIPY_OPTIMIZE)
    if _NUMPY_FLOATING_TYPES and isinstance(value, _NUMPY_FLOATING_TYPES):
        return boundary_float_to_mpf(value, origin=BoundaryOrigin.SCIPY_OPTIMIZE)
    return strict_to_mpf(value, context=context)
