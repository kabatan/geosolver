"""
Numeric conversion and rounding helpers for mpmath geometry code.
"""

from mpmath import mp, mpf

from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf


def to_mpf(value: object) -> mpf:
    """Convert a numeric value to mpf (fail-closed for unsupported types)."""
    if isinstance(value, mpf):
        return value
    try:
        return strict_to_mpf(value, context="geometry.mp_conversion.to_mpf")
    except HighPrecisionContaminationError:
        raise
    except Exception as exc:
        raise TypeError(f"Unsupported high precision numeric value: {value!r}") from exc


def mp_evalf(value: object, precision: int = 15) -> mpf:
    """Evaluate a numeric value as mpf."""
    del precision
    return to_mpf(value)


def round_to_nearest_int(value: object) -> int:
    """Round a numeric value to nearest integer without float conversion."""
    return int(mp.nint(to_mpf(value)))


def is_near_integer(value: object, rounded: int, tol: mpf) -> bool:
    """Check if value is within tolerance from an integer."""
    return abs(to_mpf(value) - rounded) < tol
