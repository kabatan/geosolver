"""Debug helper for detecting float contamination."""

import warnings
from typing import Any


def check_float_contamination(value: Any, *, warn_only: bool = False) -> bool:
    """Check and optionally raise when Python float is detected."""
    is_contaminated = isinstance(value, float)
    if not is_contaminated:
        return False
    message = f"float型混入検出: {value}"
    if warn_only:
        warnings.warn(message, RuntimeWarning, stacklevel=2)
        return True
    raise TypeError(message)
