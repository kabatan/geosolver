"""Zone B boundary conversion: float → mpf for Zone A → Zone C transition.

This is the **only** sanctioned path for converting Zone A float values
(e.g. scipy optimizer output) into mpf values that enter Zone C.

Design notes:
- Uses ``mp.mpf(float_value)`` directly (IEEE 754 exact read, no str bridge).
- Must be called **outside** ``high_precision_mode()`` to avoid WP6_5
  constructor guard collision.
- Includes ``origin`` in conversion errors for traceability.
"""

from __future__ import annotations

import enum
from typing import Any

from mpmath import mp, mpf

from .high_precision_contamination_error import HighPrecisionContaminationError
from .high_precision_mode import _boundary_conversion_context

try:
    import numpy as np

    _NUMPY_FLOATING_TYPES: tuple[type, ...] = (np.floating,)
except Exception:  # pragma: no cover
    _NUMPY_FLOATING_TYPES = ()


# ---------------------------------------------------------------------------
# Boundary conversion error origins
# ---------------------------------------------------------------------------


class BoundaryOrigin(str, enum.Enum):
    """Identifies the Zone A component that produced the float value."""

    SCIPY_OPTIMIZE = "scipy.optimize"
    INITIAL_POINT = "initial_point"
    LEGACY_BOUND = "legacy_bound"
    OBJECTIVE_VALUE = "objective_value"


# ---------------------------------------------------------------------------
# Conversion function
# ---------------------------------------------------------------------------


def boundary_float_to_mpf(
    value: Any,
    *,
    origin: BoundaryOrigin,
    allow_nonfinite: bool = False,
) -> mpf:
    """Convert a Zone A float to mpf at the Zone B boundary.

    Args:
        value: A ``float`` or ``numpy.floating`` from Zone A.
        origin: Which Zone A component produced this value.
        allow_nonfinite: If False (default), reject NaN/±inf.

    Returns:
        An ``mpf`` value.

    Raises:
        TypeError: If *value* is not float/numpy.floating.
        HighPrecisionContaminationError: If *value* is non-finite and
            *allow_nonfinite* is False.
    """
    # --- INV-14: must NOT be called inside high_precision_mode ---
    from .high_precision_mode import is_high_precision_mode

    if is_high_precision_mode():
        raise HighPrecisionContaminationError(
            f"boundary_float_to_mpf called inside high_precision_mode (precision laundering "
            f"is forbidden — call boundary_float_to_mpf before entering Stage C). "
            f"origin={origin.value}, value={value!r}"
        )

    # --- Input type validation ---
    if isinstance(value, float):
        float_value = value
    elif _NUMPY_FLOATING_TYPES and isinstance(value, _NUMPY_FLOATING_TYPES):
        float_value = float(value)
    else:
        raise TypeError(
            f"boundary_float_to_mpf accepts only float/numpy.floating, "
            f"got {type(value).__name__}: {value!r} (origin={origin.value})"
        )

    # --- Non-finite rejection ---
    import math

    if not allow_nonfinite and not math.isfinite(float_value):
        raise HighPrecisionContaminationError(
            f"Non-finite float value is rejected at boundary "
            f"(origin={origin.value}): {float_value!r}"
        )

    # --- Direct IEEE 754 conversion (no str bridge) ---
    # Bypass WP6_5 constructor guard via boundary context manager.
    with _boundary_conversion_context():
        return mp.mpf(float_value)
