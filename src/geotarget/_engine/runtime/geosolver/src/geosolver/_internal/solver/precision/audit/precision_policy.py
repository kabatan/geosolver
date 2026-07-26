"""Precision policy for controlling which origins are allowed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrecisionPolicy:
    """Policy controlling which boundary conversions are allowed.

    Args:
        min_precision_for_enforcement: Only enforce at this precision or above.
        blocked_origins: Set of origin strings that trigger violations.
    """

    min_precision_for_enforcement: int = 60
    blocked_origins: frozenset[str] = frozenset({
        "scipy.optimize",
        "differential_evolution",
    })


def default_precision_policy() -> PrecisionPolicy:
    """Return the default precision policy."""
    return PrecisionPolicy()
