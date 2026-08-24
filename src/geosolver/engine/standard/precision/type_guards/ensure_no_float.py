"""Runtime guard to reject float contamination in high-precision paths."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .high_precision_contamination_error import HighPrecisionContaminationError
from .high_precision_mode import is_high_precision_mode

try:
    import numpy as np

    _NUMPY_FLOATING_TYPES: tuple[type, ...] = (np.floating,)
except Exception:  # pragma: no cover
    _NUMPY_FLOATING_TYPES = ()

try:
    from sympy import Float as _SympyFloat
    _SYMPY_FLOAT_TYPES: tuple[type, ...] = (_SympyFloat,)
except Exception:  # pragma: no cover
    _SYMPY_FLOAT_TYPES = ()


def ensure_no_float(value: object, *, context: str) -> None:
    """Raise HighPrecisionContaminationError if value contains float/numpy.floating/sympy.Float."""
    if isinstance(value, float) or (
        _NUMPY_FLOATING_TYPES and isinstance(value, _NUMPY_FLOATING_TYPES)
    ) or (
        _SYMPY_FLOAT_TYPES and isinstance(value, _SYMPY_FLOAT_TYPES)
    ):
        raise HighPrecisionContaminationError(
            f"float contamination detected at {context}: {type(value).__name__}"
        )

    if isinstance(value, Mapping):
        for key, item in value.items():
            ensure_no_float(item, context=f"{context}.{key}")
        return

    if isinstance(value, (str, bytes, bytearray)):
        return

    if isinstance(value, Sequence):
        for index, item in enumerate(value):
            ensure_no_float(item, context=f"{context}[{index}]")


def ensure_high_precision_mode(*, context: str) -> None:
    if not is_high_precision_mode():
        raise HighPrecisionContaminationError(f"high_precision_mode is required at {context}")
