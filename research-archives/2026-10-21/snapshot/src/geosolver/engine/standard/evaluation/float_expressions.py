"""Float construction and residual evaluation for the search phase."""

from __future__ import annotations

import math
import sys
from typing import Any

from mpmath import mp

from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.ir.schema import IRSpec
from geosolver.runtime.deadline import check_deadline


def compute_residual_vector(
    values: list[float],
    *,
    spec: IRSpec,
    var_names: list[str],
    targets: list[Any],
    base_context: dict[str, Any],
) -> list[float]:
    # Use the numerical geometry kernels at ordinary (binary64) precision.
    # The symbolic API is for explicit symbolic work, never optimizer callbacks.
    with mp.workprec(53):
        try:
            snapshot = numerical_snapshot(spec, var_names, values, base_context, arithmetic="float")
            context = snapshot.for_expressions(
                [*spec.constraints, *(t for t in targets if isinstance(t, str))]
            )
        except TimeoutError:
            raise
        except Exception:
            return [math.nan for _ in spec.constraints]
        residuals: list[float] = []
        for index, constraint_expr in enumerate(spec.constraints):
            check_deadline()
            try:
                lhs = safe_eval_expr_hp(constraint_expr, context)
                target = targets[index]
                rhs = safe_eval_expr_hp(target, context) if isinstance(target, str) else target
                residuals.append(float(lhs) - float(rhs))
            except TimeoutError:
                raise
            except Exception:
                residuals.append(math.nan)
        return residuals


def residual_norm(residuals: list[float]) -> float:
    values = tuple(float(value) for value in residuals)
    # Preserve ordinary search ordering while avoiding overflow and loss of
    # subnormal residuals in the intermediate sum of squares.
    try:
        squared = sum(value**2 for value in values)
    except OverflowError:
        return math.hypot(*values)
    if not math.isfinite(squared) or squared < sys.float_info.min:
        return math.hypot(*values)
    return math.sqrt(squared)
