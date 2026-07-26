"""Create reparameterized function wrapper for u-space optimization."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver._internal.solver.reparameterization.variable_transform import (
    VariableTransform,
)


def create_reparameterized_function(
    *,
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    transforms: list[VariableTransform],
) -> Callable[[list[MPFloat]], list[MPFloat]]:
    """Wrap f so it operates in unconstrained u-space.

    Args:
        f: Original function f(x) -> values.
        transforms: Variable transforms (one per variable).

    Returns:
        Function f_u(u) that maps unconstrained u to f(x).
    """
    def f_u(u: list[MPFloat]) -> list[MPFloat]:
        x = [t.forward(u[i]) for i, t in enumerate(transforms)]
        return list(f(x))
    return f_u
