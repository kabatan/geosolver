"""Finite-difference Jacobian for high-precision refinement."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat

MAX_STEP_REDUCTIONS = 6
MAX_STEP_EXPONENT = 30


def _independent_column_groups(dependencies, columns):
    groups = []
    for column in range(columns):
        affected = {row for row, names in enumerate(dependencies) if column in names}
        if not affected:
            continue
        for members, rows in groups:
            if not rows.intersection(affected):
                members.append(column)
                rows.update(affected)
                break
        else:
            groups.append(([column], set(affected)))
    return tuple(tuple(members) for members, _ in groups)


def compute_finite_difference_jacobian(
    *,
    point: Sequence[MPFloat],
    dps: int,
    residual_fn: Callable[[list[MPFloat], int], list[MPFloat] | None],
    one_sided_at_cusp: bool = False,
    base_residual: Sequence[MPFloat] | None = None,
    row_dependencies: Sequence[frozenset[int]] | None = None,
) -> list[list[MPFloat]] | None:
    """Compute a Jacobian matrix by finite differences.

    Centered differences are the least biased choice for smooth residuals,
    but they cancel at an absolute-value/``atan2(abs(...), ...)`` cusp.  For
    explicitly marked nonsmooth systems, use a non-zero one-sided directional
    slope only when the two one-sided slopes have opposite signs and the
    centered slope is numerical zero.  The default remains the historical
    centered scheme so unrelated smooth problems retain their behavior.
    """
    with mp.workdps(int(dps)):
        base = (
            residual_fn(list(point), int(dps))
            if base_residual is None
            else [mp.mpf(value) for value in base_residual]
        )
        if base is None:
            return None
        rows = len(base)
        cols = len(point)
        jacobian: list[list[MPFloat]] = [[mp.mpf("0") for _ in range(cols)] for _ in range(rows)]
        completed_columns = set()
        if row_dependencies is not None and len(row_dependencies) == rows and not one_sided_at_cusp:
            active = frozenset().union(*row_dependencies)
            completed_columns.update(set(range(cols)) - active)
            for group in _independent_column_groups(row_dependencies, cols):
                if len(group) < 2:
                    continue
                exponent = min(max(int(dps) // 2, 1), MAX_STEP_EXPONENT)
                steps = {
                    column: max(mp.mpf(1), abs(point[column])) * mp.power(10, -exponent)
                    for column in group
                }
                plus, minus = list(point), list(point)
                for column in group:
                    plus[column] += steps[column]
                    minus[column] -= steps[column]
                plus_vec = residual_fn(plus, int(dps))
                minus_vec = residual_fn(minus, int(dps))
                if plus_vec is None or minus_vec is None:
                    # A boundary may invalidate a joint probe; use individual
                    # one-sided stencils below for those columns.
                    continue
                for row, dependencies in enumerate(row_dependencies):
                    for column in group:
                        if column in dependencies:
                            jacobian[row][column] = (plus_vec[row] - minus_vec[row]) / (
                                2 * steps[column]
                            )
                completed_columns.update(group)
        for column in range(cols):
            if column in completed_columns:
                continue
            exponent = min(max(int(dps) // 2, 1), MAX_STEP_EXPONENT)
            step = max(mp.mpf("1"), abs(point[column])) * mp.power(mp.mpf("10"), -exponent)
            success = False
            for _ in range(MAX_STEP_REDUCTIONS):
                plus = [mp.mpf(value) for value in point]
                minus = [mp.mpf(value) for value in point]
                plus[column] += step
                minus[column] -= step
                plus_vec = residual_fn(plus, int(dps))
                minus_vec = residual_fn(minus, int(dps))
                if plus_vec is None or minus_vec is None:
                    # At a domain boundary a centered stencil may never exist.
                    # A second-order one-sided stencil has the same truncation
                    # order, while leaving feasibility to the full verifier.
                    side = 1 if plus_vec is not None else -1
                    near = plus_vec if plus_vec is not None else minus_vec
                    far_point = list(plus if side == 1 else minus)
                    far_point[column] += side * step
                    far = residual_fn(far_point, int(dps)) if near is not None else None
                    if near is not None and far is not None:
                        for row in range(rows):
                            jacobian[row][column] = (
                                side * (-3 * base[row] + 4 * near[row] - far[row]) / (2 * step)
                            )
                        success = True
                        break
                    step /= mp.mpf("2")
                    continue
                denominator = mp.mpf("2") * step
                for row in range(rows):
                    centered = (plus_vec[row] - minus_vec[row]) / denominator
                    if one_sided_at_cusp:
                        forward = (plus_vec[row] - base[row]) / step
                        backward = (base[row] - minus_vec[row]) / step
                        scale = max(mp.mpf("1"), abs(forward), abs(backward), abs(centered))
                        tolerance = 100 * mp.eps * scale
                        if (
                            abs(centered) <= tolerance
                            and abs(forward) > tolerance
                            and abs(backward) > tolerance
                            and forward * backward < 0
                        ):
                            # A derivative does not exist at a true cusp.  A
                            # directional slope is still useful to Newton/LM;
                            # choose the stronger side deterministically.
                            centered = forward if abs(forward) >= abs(backward) else backward
                    jacobian[row][column] = centered
                success = True
                break
            if not success:
                return None
    return jacobian
