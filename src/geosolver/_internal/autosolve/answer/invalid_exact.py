"""Validation helpers for exact-value strings."""

from __future__ import annotations

import re
from typing import Any

from geosolver._internal.utils.approximate_marker import is_approximate_marker


def is_invalid_exact(value: Any) -> bool:
    """Return whether an exact-value representation should be treated as invalid."""
    if value is None:
        return True
    try:
        text = str(value).strip().lower()
    except Exception:
        return True
    if text == "" or "nan" in text or text in {"inf", "+inf", "-inf"} or text == "none":
        return True
    if is_approximate_marker(text):
        return True
    return bool(re.match(r"^[-+]?[0-9]*\.[0-9]+([eE][-+]?[0-9]+)?$", text))
