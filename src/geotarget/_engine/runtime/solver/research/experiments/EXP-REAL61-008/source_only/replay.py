"""Untouched-evaluator endpoint replay for exploratory numerical scoring."""

from __future__ import annotations

import math
from typing import Sequence


def replay_endpoint(
    evaluator: object, point: Sequence[float], *, precision: int = 80
) -> dict[str, object]:
    values = [float(value) for value in point]
    try:
        residual = evaluator.evaluate_float_residual(values)
        guard_ok, violations = evaluator.evaluate_guard(values)
        hard = evaluator.evaluate_float_hard_feasibility(values)
        residual_norm = float(residual.residual_norm_float)
        safe = bool(
            residual.is_finite
            and guard_ok
            and hard.hard_feasible
            and math.isfinite(residual_norm)
            and residual_norm <= 1.0e-8
        )
    except Exception as error:
        return {
            "endpoint": values,
            "safe": False,
            "residual_inf": None,
            "guard_ok": False,
            "hard_feasible": False,
            "diagnostic_target": None,
            "error": f"{type(error).__name__}: {error}",
        }
    target = None
    if safe:
        try:
            from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
                BoundaryOrigin,
                boundary_float_to_mpf,
            )
            from geosolver._internal.solver.precision.type_guards.high_precision_mode import (
                high_precision_mode,
            )
            from mpmath import mp

            hp_values = [
                boundary_float_to_mpf(value, origin=BoundaryOrigin.SCIPY_OPTIMIZE)
                for value in values
            ]
            with mp.workdps(precision), high_precision_mode():
                answer = evaluator.evaluate_answer_hp(hp_values, precision=precision)
            if answer.answer_hp is not None and mp.isfinite(answer.answer_hp):
                target = mp.nstr(answer.answer_hp, 50)
        except Exception:
            target = None
    return {
        "endpoint": values,
        "safe": safe,
        "residual_inf": residual_norm if math.isfinite(residual_norm) else None,
        "guard_ok": bool(guard_ok),
        "guard_violations": list(violations),
        "hard_feasible": bool(hard.hard_feasible),
        "hard_failure_tags": list(hard.failure_tags),
        "diagnostic_target": target,
        "diagnostic_target_is_exact": False,
    }


__all__ = ["replay_endpoint"]
