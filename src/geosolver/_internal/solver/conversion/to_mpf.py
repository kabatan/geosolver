"""Conversion helper for robust mpf casting."""

import re
from typing import Optional
from mpmath import mp, mpf
from .types import NumericValue
from .strip_whitespace import strip_whitespace


def to_mpf_sanitized(value: NumericValue, *, dps: Optional[int] = None) -> mpf:
    """Convert numeric-like input to ``mpf`` and return ``nan`` on failure."""
    if isinstance(value, mpf):
        return value
    try:
        return mpf(value)
    except Exception:
        pass
    if hasattr(value, "evalf"):
        try:
            use_dps = int(dps) if dps is not None else int(getattr(mp, "dps", 50))
            return mpf(strip_whitespace(str(value.evalf(use_dps))))
        except Exception:
            pass
    try:
        text = strip_whitespace(str(value))
        matched = re.fullmatch(r"mpf\((['\"])(.*)\1\)", text)
        return mpf(matched.group(2) if matched else text)
    except Exception:
        return mpf("nan")
