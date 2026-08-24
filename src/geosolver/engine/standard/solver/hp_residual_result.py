"""HP residual evaluation result (single-source-of-truth dataclass)."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


@dataclass(frozen=True)
class HPResidualResult:
    """Result of evaluating constraint residuals at high precision.

    All HP residual computations (candidate ledger, acceptance,
    fail diagnostics) must produce and consume this type to
    ensure consistency (FIX-0).

    Args:
        residual_vector: Per-constraint residuals f_i(x) - target_i.
        residual_norm: L2 norm of residual_vector.
        is_finite: Whether residual_norm is finite.
    """

    residual_vector: list[MPFloat]
    residual_norm: MPFloat
    is_finite: bool
