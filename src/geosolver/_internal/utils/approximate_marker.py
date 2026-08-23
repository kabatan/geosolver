"""Shared approximate-marker helpers."""

from __future__ import annotations

from typing import Any

APPROXIMATE_PREFIXES: tuple[str, ...] = (
    "approximately",
    "approx",
    "~=",
    "≈",
    "~",
)


def is_approximate_marker(value: Any) -> bool:
    """Return whether value is an approximate textual representation."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    text_lower = text.lower()
    return any(text_lower.startswith(prefix) for prefix in APPROXIMATE_PREFIXES)


def strip_approximate_marker_prefix(text: str) -> str:
    """Strip a supported approximate marker prefix from text."""
    normalized = text.strip()
    normalized_lower = normalized.lower()
    for prefix in APPROXIMATE_PREFIXES:
        if normalized_lower.startswith(prefix):
            return normalized[len(prefix):].strip()
    return normalized
