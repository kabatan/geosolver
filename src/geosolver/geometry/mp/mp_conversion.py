"""
Numeric conversion and rounding helpers for mpmath geometry code.
"""

from collections.abc import Sequence

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


def _is_mpf_instance(value: object) -> bool:
    return type(value).__name__ == "mpf" or (
        hasattr(value, "__class__") and value.__class__.__name__ == "mpf"
    )


def convert_sympy_input(vec: Sequence[object]) -> list[object]:
    """Normalize sequence values for high-precision math without float demotion."""
    has_mpf = any(_is_mpf_instance(v) for v in vec)
    if has_mpf:
        return [v for v in vec]
    return [to_mpf(v) for v in vec]


def round_to_nearest_int(value: object) -> int:
    """Round a numeric value to nearest integer without float conversion."""
    return int(mp.nint(to_mpf(value)))


def is_near_integer(value: object, rounded: int, tol: mpf) -> bool:
    """Check if value is within tolerance from an integer."""
    return abs(to_mpf(value) - rounded) < tol
