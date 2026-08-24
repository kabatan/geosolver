"""Single-source-of-truth HP residual evaluator (FIX-0).

All code paths that compute HP residuals (candidate ledger, acceptance
judgment, fail diagnostics) MUST use this function to ensure the same
candidate point is evaluated at the same precision with the same
residual definition.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.ensure_mpf import ensure_mpf
from geosolver.engine.standard.precision.type_guards.ensure_no_float import (
    ensure_high_precision_mode,
    ensure_no_float,
)
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.engine.standard.solver.hp_residual_result import HPResidualResult


def evaluate_hp_residual(
    *,
    point: Sequence[MPFloat],
    f_hp: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: Sequence[MPFloat],
) -> HPResidualResult:
    """Evaluate constraint residual at high precision.

    Must be called inside ``high_precision_mode()``.

    Args:
        point: Candidate solution (mpf values).
        f_hp: High-precision constraint function.
        targets: Target values for each constraint.

    Returns:
        HPResidualResult with residual vector, norm, and finiteness.
    """
    ensure_high_precision_mode(context="evaluate_hp_residual")
    point_list = [ensure_mpf(v, context="evaluate_hp_residual.point") for v in point]
    target_list = [ensure_mpf(v, context="evaluate_hp_residual.target") for v in targets]
    ensure_no_float(point_list, context="evaluate_hp_residual.point")
    ensure_no_float(target_list, context="evaluate_hp_residual.target")

    hp_values = f_hp(point_list)
    ensure_no_float(hp_values, context="evaluate_hp_residual.hp_values")

    residual_vector: list[MPFloat] = [
        ensure_mpf(val, context="evaluate_hp_residual.residual") - tgt
        for val, tgt in zip(hp_values, target_list)
    ]
    squared_sum = mp.fsum([r * r for r in residual_vector])
    norm: MPFloat = mp.sqrt(squared_sum)
    finite = bool(mp.isfinite(norm))

    return HPResidualResult(
        residual_vector=residual_vector,
        residual_norm=norm,
        is_finite=finite,
    )
