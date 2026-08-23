"""Newton updates for single-solution refinement."""

from collections.abc import Sequence

from geosolver._internal.solver.precision.type_guards.ensure_mpf import ensure_mpf


def newton_refinement_step(point: Sequence[float], gradient: Sequence[float], step_size: float) -> list[float]:
    """Apply one float Newton-like gradient correction step."""
    return [float(value) - float(step_size) * float(grad) for value, grad in zip(point, gradient)]


def newton_refinement_step_hp(point: Sequence[object], gradient: Sequence[object], step_size: object) -> list[object]:
    """Apply one high-precision Newton-like step with strict mpf conversion."""
    safe_point = [ensure_mpf(value, context="point") for value in point]
    safe_gradient = [ensure_mpf(value, context="gradient") for value in gradient]
    safe_step_size = ensure_mpf(step_size, context="step_size")
    return [value - safe_step_size * grad for value, grad in zip(safe_point, safe_gradient)]
