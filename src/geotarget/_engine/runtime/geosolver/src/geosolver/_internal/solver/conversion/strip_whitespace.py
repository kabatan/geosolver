"""Whitespace normalization helpers for numeric string parsing."""

import re


def strip_whitespace(value: str) -> str:
    """Remove all whitespace characters from a string.

    Args:
        value: Input string that may include spaces or newlines.

    Returns:
        String with all whitespace removed.
    """
    return re.sub(r"\s+", "", value)
