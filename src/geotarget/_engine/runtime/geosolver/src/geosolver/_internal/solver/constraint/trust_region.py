"""Trust-region controls for constraint-projection updates."""

from collections.abc import Sequence

import math
from mpmath import mp

from geosolver._internal.solver.precision.type_guards.ensure_mpf import ensure_mpf


def apply_trust_region(step: Sequence[float], radius: float) -> list[float]:
    """Scale step to remain inside Euclidean trust-region radius."""
    norm = math.sqrt(sum(value * value for value in step))
    if norm <= radius or norm == 0.0:
        return [float(value) for value in step]
    scale = radius / norm
    return [float(value) * scale for value in step]


def apply_trust_region_hp(step: Sequence[object], radius: object) -> list[object]:
    """Scale high-precision step using mpf-safe operations."""
    safe_step = [ensure_mpf(value, context="step") for value in step]
    safe_radius = ensure_mpf(radius, context="radius")
    norm = mp.sqrt(sum(value * value for value in safe_step))
    if norm <= safe_radius or norm == mp.mpf("0"):
        return safe_step
    scale = safe_radius / norm
    return [value * scale for value in safe_step]
