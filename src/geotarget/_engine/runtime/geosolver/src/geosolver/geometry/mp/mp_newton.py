"""
High-precision Newton refinement utilities for geometry solving.
"""

from typing import Callable, List, Optional, Tuple

from mpmath import mp, mpf, sqrt as mp_sqrt

from geosolver._internal.observability.logging.compat import emit_legacy_log
from geosolver._internal.solver.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver._internal.solver.precision.type_guards.strict_to_mpf import strict_to_mpf


DAMPING_GROWTH_FACTOR = mpf(6) / 5
DAMPING_DECAY_FACTOR = mpf(1) / 2
DAMPING_MAX = mpf(1)
DAMPING_MIN = mpf(1) / 100


def _to_mpf(value) -> mpf:
    if isinstance(value, mpf):
        return value
    try:
        return strict_to_mpf(value, context="geometry.mp_newton")
    except HighPrecisionContaminationError:
        raise
    except Exception as exc:
        raise TypeError(f"Unsupported high precision numeric value in geometry.mp_newton: {value!r}") from exc


def _solve_linear_system(A: List[List[mpf]], b: List[mpf], n: int) -> Optional[List[mpf]]:
    """
    Solve Ax = b with Gaussian elimination.
    """
    aug = [[A[i][j] for j in range(n)] + [b[i]] for i in range(n)]

    for k in range(n):
        max_row = k
        for i in range(k + 1, n):
            if abs(aug[i][k]) > abs(aug[max_row][k]):
                max_row = i
        aug[k], aug[max_row] = aug[max_row], aug[k]

        if abs(aug[k][k]) < mpf("1e-100"):
            return None

        for i in range(k + 1, n):
            factor = aug[i][k] / aug[k][k]
            for j in range(k, n + 1):
                aug[i][j] -= factor * aug[k][j]

    x = [mpf("0")] * n
    for i in range(n - 1, -1, -1):
        x[i] = aug[i][n]
        for j in range(i + 1, n):
            x[i] -= aug[i][j] * x[j]
        x[i] /= aug[i][i]
    return x


def refine_to_high_precision(
    x0: List[float],
    f_mp: Callable,
    v: List[float],
    target_precision: int = 50,
    max_iterations: int = 100,
    verbose: bool = False,
) -> Tuple[List[mpf], mpf, int]:
    """
    Refine a numeric solution by high-precision Newton-style iterations.
    """
    mp.dps = target_precision + 30

    n = len(x0)
    m = len(v)
    x = [_to_mpf(xi) for xi in x0]
    v_mp = [_to_mpf(vi) for vi in v]

    best_x = x.copy()
    best_residual = mpf("inf")
    damping = mpf("1.0")

    for iteration in range(max_iterations):
        scales = [max(abs(xi), mpf("1")) for xi in x]
        try:
            result = f_mp(x)
            if any(r == mpf("inf") for r in result):
                break

            residual = [result[i] - v_mp[i] for i in range(m)]
            residual_norm = mp_sqrt(sum(r**2 for r in residual))

            if residual_norm < best_residual:
                best_x = x.copy()
                best_residual = residual_norm
                damping = min(damping * DAMPING_GROWTH_FACTOR, DAMPING_MAX)
            else:
                damping = max(damping * DAMPING_DECAY_FACTOR, DAMPING_MIN)

            if verbose and iteration % 10 == 0:
                precision_achieved = (
                    -mp.log10(residual_norm) if residual_norm > 0 else mp.mpf(target_precision)
                )
                residual_str = mp.nstr(residual_norm, 6)
                precision_str = mp.nstr(precision_achieved, 6)
                emit_legacy_log(
                    f"    iteration{iteration}: residual={residual_str} ({precision_str} digits)"
                )

            if residual_norm < mp.power(10, -target_precision):
                break

            jacobian = [[mpf("0")] * n for _ in range(m)]

            for j in range(n):
                h = scales[j] * mp.power(10, -min(target_precision // 3, 20))

                x_plus = x.copy()
                x_plus[j] += h
                x_minus = x.copy()
                x_minus[j] -= h

                result_plus = f_mp(x_plus)
                result_minus = f_mp(x_minus)

                if any(r == mpf("inf") for r in result_plus) or any(
                    r == mpf("inf") for r in result_minus
                ):
                    result_plus = f_mp(x_plus)
                    if any(r == mpf("inf") for r in result_plus):
                        continue
                    for i in range(m):
                        jacobian[i][j] = (result_plus[i] - result[i]) / h
                else:
                    for i in range(m):
                        jacobian[i][j] = (result_plus[i] - result_minus[i]) / (2 * h)

            JTJ = [[mpf("0")] * n for _ in range(n)]
            JTr = [mpf("0")] * n

            for i in range(n):
                for j in range(n):
                    for k in range(m):
                        JTJ[i][j] += jacobian[k][i] * jacobian[k][j]
                JTJ[i][i] += mpf("1e-20") * (mpf("1") + JTJ[i][i])

            for i in range(n):
                for k in range(m):
                    JTr[i] += jacobian[k][i] * residual[k]

            dx = _solve_linear_system(JTJ, [-r for r in JTr], n)
            if dx is None:
                break

            max_step = max(abs(d) for d in dx)
            if max_step > 0:
                max_rel_step = max(abs(dx[i]) / scales[i] for i in range(n))
                if max_rel_step > mpf("0.5"):
                    scale_factor = mpf("0.5") / max_rel_step
                    dx = [d * scale_factor for d in dx]

            x = [x[j] + damping * dx[j] for j in range(n)]

        except Exception as e:
            if verbose:
                emit_legacy_log(f"    failed at iteration{iteration}: {e}")
            break

    return best_x, best_residual, iteration + 1
