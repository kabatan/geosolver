"""Main single-solution refinement entry point."""

from collections.abc import Callable, Sequence

from .newton import newton_refinement_step, newton_refinement_step_hp


def refine_single_solution(
    point: Sequence[object], gradient_fn: Callable[[Sequence[object]], Sequence[object]], *, step_size: object, high_precision: bool
) -> list[object]:
    """Refine one solution by applying a single Newton-like correction."""
    gradient = gradient_fn(point)
    if high_precision:
        return newton_refinement_step_hp(point, gradient, step_size)
    return [float(value) for value in newton_refinement_step(point, gradient, float(step_size))]
