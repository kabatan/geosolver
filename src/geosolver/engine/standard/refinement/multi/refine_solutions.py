"""Orchestrate multi-solution refinement."""

from collections.abc import Callable, Sequence
from typing import Any

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.ensure_mpf import ensure_mpf
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    boundary_float_to_mpf,
    BoundaryOrigin,
)

from .workers import refine_with_workers


_REFINE_DEDUPE_TOLERANCE_DEFAULT = mp.mpf("1e-9")
_REFINE_IMPROVEMENT_TOLERANCE_DEFAULT = mp.mpf("1e-12")


def _dedupe_refined_solutions(
    solutions: Sequence[Sequence[object]],
    *,
    tolerance: object = _REFINE_DEDUPE_TOLERANCE_DEFAULT,
) -> list[list[object]]:
    tolerance_mpf = tolerance if isinstance(tolerance, mp.mpf) else boundary_float_to_mpf(tolerance, origin=BoundaryOrigin.DEDUPE_TOLERANCE)
    unique: list[list[object]] = []
    for solution in solutions:
        candidate = list(solution)
        is_duplicate = False
        for accepted in unique:
            if len(candidate) != len(accepted):
                continue
            diffs: list[Any] = []
            comparable = True
            for left, right in zip(candidate, accepted):
                try:
                    left_mpf = strict_to_mpf(left, context="refine_dedupe_left")
                    right_mpf = strict_to_mpf(right, context="refine_dedupe_right")
                    diffs.append(abs(left_mpf - right_mpf))
                except Exception:
                    comparable = False
                    break
            if comparable and all(
                diff <= tolerance_mpf
                for diff in diffs
            ):
                is_duplicate = True
                break
            if not comparable and candidate == accepted:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(candidate)
    return unique


def _safe_residual_norm(
    solution: Sequence[object],
    residual_vector: Callable[[list[object]], Sequence[object]],
) -> Any:
    try:
        values = list(solution)
        residuals = residual_vector(values)
    except Exception:
        return mp.mpf("inf")

    squared_sum = mp.mpf("0")
    for residual in residuals:
        try:
            value = ensure_mpf(residual, context="refine_residual")
        except Exception:
            return mp.mpf("inf")
        if not mp.isfinite(value):
            return mp.mpf("inf")
        squared_sum += value * value
    return mp.sqrt(squared_sum)


def _sort_by_residual(
    solutions: Sequence[Sequence[object]],
    residual_vector: Callable[[list[object]], Sequence[object]],
) -> tuple[list[list[object]], Any]:
    scored: list[tuple[Any, list[object]]] = []
    best_norm = mp.mpf("inf")
    for solution in solutions:
        norm = _safe_residual_norm(solution, residual_vector)
        scored.append((norm, list(solution)))
        if norm < best_norm:
            best_norm = norm
    scored.sort(key=lambda item: item[0])
    return [solution for _, solution in scored], best_norm


def _has_converged_by_tolerance(
    best_norm: Any,
    residual_tolerance: Any,
) -> bool:
    if not mp.isfinite(best_norm):
        return False
    _tol = residual_tolerance if isinstance(residual_tolerance, mp.mpf) else boundary_float_to_mpf(residual_tolerance, origin=BoundaryOrigin.REFINE_TOLERANCE)
    return best_norm <= _tol


def _is_improvement_too_small(
    previous_best: Any,
    current_best: Any,
    improvement_tolerance: Any,
) -> bool:
    if not mp.isfinite(previous_best):
        return False
    if not mp.isfinite(current_best):
        return True
    improvement = previous_best - current_best
    _imp_tol = improvement_tolerance if isinstance(improvement_tolerance, mp.mpf) else boundary_float_to_mpf(improvement_tolerance, origin=BoundaryOrigin.REFINE_TOLERANCE)
    return improvement <= _imp_tol


def refine_multiple_solutions(
    solutions: Sequence[Sequence[object]],
    refine_one: Callable[[Sequence[object]], list[object]],
    *,
    use_parallel: bool = False,
    max_workers: int = 1,
    max_solutions: int | None = None,
) -> list[list[object]]:
    """Refine all provided solutions with configurable worker execution."""
    refined = refine_with_workers(
        solutions,
        refine_one,
        use_parallel=use_parallel,
        max_workers=max_workers,
    )
    unique = _dedupe_refined_solutions(refined)
    if max_solutions is None:
        return unique
    return unique[: max(0, int(max_solutions))]


def iterative_refine_multiple_solutions(
    solutions: Sequence[Sequence[object]],
    refine_one: Callable[[Sequence[object]], list[object]],
    *,
    residual_vector: Callable[[list[object]], Sequence[object]],
    residual_tolerance: object,
    max_iterations: int = 5,
    improvement_tolerance: object = _REFINE_IMPROVEMENT_TOLERANCE_DEFAULT,
    use_parallel: bool = False,
    max_workers: int = 1,
    max_solutions: int | None = None,
) -> list[list[object]]:
    current = [list(solution) for solution in solutions]
    if not current:
        return []

    ordered_current, best_norm = _sort_by_residual(current, residual_vector)
    current = ordered_current
    previous_best = best_norm

    max_iter = max(1, int(max_iterations))
    for _ in range(max_iter):
        refined = refine_multiple_solutions(
            current,
            refine_one,
            use_parallel=use_parallel,
            max_workers=max_workers,
            max_solutions=max_solutions,
        )
        if not refined:
            break

        ordered_refined, best_refined_norm = _sort_by_residual(refined, residual_vector)
        current = ordered_refined
        if _has_converged_by_tolerance(best_refined_norm, residual_tolerance):
            break

        if _is_improvement_too_small(previous_best, best_refined_norm, improvement_tolerance):
            break
        previous_best = best_refined_norm

    if max_solutions is None:
        return current
    return current[: max(0, int(max_solutions))]
