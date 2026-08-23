"""Automatic bound-size estimation from target values."""

from typing import Sequence
import numpy as np


def _auto_bounds(values: Sequence[float], n: int) -> list[tuple[float, float]]:
    """Estimate symmetric search bounds using finite non-zero target scales."""
    scales: list[float] = []
    for value in values:
        try:
            numeric = float(value)
            if numeric != 0.0 and np.isfinite(numeric):
                scales.append(abs(numeric))
        except (TypeError, ValueError):
            continue
    max_scale = max(scales) if scales else 1.0
    scale = min(max(100.0, max_scale * 100.0), 1e12)
    return [(-scale, scale) for _ in range(n)]
