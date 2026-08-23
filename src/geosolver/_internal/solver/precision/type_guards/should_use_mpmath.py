"""Precision threshold helper for mpmath execution paths."""

from __future__ import annotations


MPMATH_PRECISION_THRESHOLD = 16


def should_use_mpmath(precision: int) -> bool:
    """Return True when precision requires mpmath-backed execution."""
    return int(precision) >= MPMATH_PRECISION_THRESHOLD


def mpmath_precision_threshold() -> int:
    return int(MPMATH_PRECISION_THRESHOLD)


def precision_backend_name(precision: int) -> str:
    if should_use_mpmath(int(precision)):
        return "mpmath"
    return "numeric"
