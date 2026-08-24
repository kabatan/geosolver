"""Variable transform dataclass for guard reparameterization."""

from __future__ import annotations

from dataclasses import dataclass

import mpmath as mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.engine.standard.refinement.reparameterization.mp_sigmoid import (
    mp_sigmoid,
    mp_sigmoid_inverse,
)
from geosolver.engine.standard.refinement.reparameterization.mp_softplus import (
    mp_softplus,
    mp_softplus_inverse,
)


@dataclass(frozen=True)
class VariableTransform:
    """Transform for a single variable from unconstrained u-space to x-space.

    Args:
        original_index: Index of the variable in the original x vector.
        transform_kind: One of "sigmoid", "softplus_lower", "softplus_upper", "identity".
        lower_bound: Lower bound (for sigmoid and softplus_lower).
        upper_bound: Upper bound (for sigmoid and softplus_upper).
    """

    original_index: int
    transform_kind: str
    lower_bound: MPFloat | None = None
    upper_bound: MPFloat | None = None

    def forward(self, u: MPFloat) -> MPFloat:
        """Map unconstrained u to constrained x."""
        if self.transform_kind in ("sigmoid", "sigmoid_open"):
            a = self.lower_bound
            b = self.upper_bound
            return a + (b - a) * mp_sigmoid(u)
        if self.transform_kind == "softplus_lower":
            return self.lower_bound + mp_softplus(u)
        if self.transform_kind == "softplus_upper":
            return self.upper_bound - mp_softplus(u)
        return u

    def inverse(self, x: MPFloat) -> MPFloat:
        """Map constrained x to unconstrained u."""
        if self.transform_kind in ("sigmoid", "sigmoid_open"):
            a = self.lower_bound
            b = self.upper_bound
            t = (x - a) / (b - a)
            return mp_sigmoid_inverse(t)
        if self.transform_kind == "softplus_lower":
            return mp_softplus_inverse(x - self.lower_bound)
        if self.transform_kind == "softplus_upper":
            return mp_softplus_inverse(self.upper_bound - x)
        return x
