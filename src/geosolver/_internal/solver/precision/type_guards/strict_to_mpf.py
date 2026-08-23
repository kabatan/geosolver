"""Strict mpf conversion utilities for high-precision critical paths."""

from __future__ import annotations

from mpmath import mp, mpf

from .high_precision_contamination_error import HighPrecisionContaminationError

try:
    import numpy as np

    _NUMPY_FLOATING_TYPES: tuple[type, ...] = (np.floating,)
except Exception:  # pragma: no cover
    _NUMPY_FLOATING_TYPES = ()

try:
    from sympy import Float as _SympyFloat
    from sympy import Rational as _SympyRational
    from sympy import Integer as _SympyInteger
except Exception:  # pragma: no cover
    _SympyFloat = ()
    _SympyRational = ()
    _SympyInteger = ()


def strict_to_mpf(value: object, *, context: str) -> mpf:
    """Convert value to ``mpf`` while rejecting float-like and str inputs.

    Allowed inputs are ``mpf``, ``int``, and sympy ``Rational``/``Integer``.
    Use ``boundary_float_to_mpf`` for Zone A float values, or
    ``mp.mpf(literal_string)`` for compile-time numeric literals.
    """
    if isinstance(value, mpf):
        return value
    if isinstance(value, int):
        integer_value = value
        return mp.mpf(integer_value)
    if isinstance(value, str):
        raise TypeError(
            f"strict_to_mpf no longer accepts str ({context}). "
            f"Use literal_code_to_mpf, mp.mpf(literal), or "
            f"boundary_float_to_mpf instead: {value!r}"
        )

    is_sympy_float = bool(_SympyFloat) and isinstance(value, _SympyFloat)
    is_sympy_rational = bool(_SympyRational) and isinstance(value, _SympyRational)
    is_sympy_integer = bool(_SympyInteger) and isinstance(value, _SympyInteger)

    if is_sympy_integer or is_sympy_rational:
        rational_value = value
        return mp.mpf(rational_value)

    if isinstance(value, float) or (
        _NUMPY_FLOATING_TYPES and isinstance(value, _NUMPY_FLOATING_TYPES)
    ) or is_sympy_float:
        raise HighPrecisionContaminationError(
            f"float-like value is forbidden in high precision path ({context}): {value}"
        )

    raise TypeError(
        f"strict_to_mpf accepts only mpf/int/sympy Rational/sympy Integer "
        f"({context}), got {type(value).__name__}: {value}"
    )
