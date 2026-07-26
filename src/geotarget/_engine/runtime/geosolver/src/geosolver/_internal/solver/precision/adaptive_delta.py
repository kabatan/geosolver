"""Adaptive finite-difference delta helpers."""

from mpmath import mpf


def _adaptive_delta(precision: int) -> mpf:
    """Return precision-aware finite-difference step in mpf."""
    exp = max((int(precision) * 35) // 100, 30)
    return mpf(10) ** (-exp)
