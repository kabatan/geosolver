"""Intersection candidate selection helpers extracted from intersections module."""

from __future__ import annotations

from typing import Any

from geosolver.core.errors import NoIntersectionError
from geosolver.geometry.mp.mp_primitives_intersections import _next_frozen_selector_entry


def _emit_selection_trace(
    *,
    selector_kind: str,
    candidate_count: int,
    selected_index: int,
) -> None:
    try:
        from geosolver.engine.standard.evaluation.selection_trace import (
            record_selection_trace,
        )
    except Exception:
        return
    try:
        record_selection_trace(
            selector_kind=selector_kind,
            candidate_count=int(candidate_count),
            selected_index=int(selected_index),
        )
    except Exception:
        return


def to_float_safe(expr: Any) -> float:
    expr_type = type(expr).__name__
    if expr_type == "mpf" or (hasattr(expr, "__class__") and expr.__class__.__name__ == "mpf"):
        try:
            return float(expr)
        except Exception:
            return 1e100

    try:
        return float(expr)
    except (TypeError, ValueError):
        pass

    try:
        from sympy import N as _N

        try:
            import mpmath

            dps = max(50, int(mpmath.mp.dps * 0.8))
        except Exception:
            dps = 50
        return float(_N(expr, dps))
    except Exception:
        pass

    try:
        if hasattr(expr, "evalf"):
            try:
                import mpmath

                dps = max(50, int(mpmath.mp.dps * 0.8))
                return float(expr.evalf(dps))
            except Exception:
                return float(expr.evalf())
    except Exception:
        pass

    return 1e100


def dist_sq(p1: Any, p2: Any) -> Any:
    dx = p1.x - p2.x
    dy = p1.y - p2.y
    return dx * dx + dy * dy


def get_dynamic_tolerance() -> float:
    try:
        import mpmath

        dps = mpmath.mp.dps
        return 10 ** (-dps + 10)
    except Exception:
        return 1e-18


def select_intersection(result: Any, n: Any, exclude: Any, near: Any, far: Any) -> Any:
    if result is None:
        if n is not None or exclude or near or far:
            raise NoIntersectionError("No intersection found")
        return None

    if isinstance(result, list):
        candidates = result[:]
    else:
        candidates = [result]

    if not candidates:
        if n is not None or exclude or near or far:
            raise NoIntersectionError("No intersection found")
        return []

    if n is not None or exclude is not None or near is not None or far is not None:
        frozen = _next_frozen_selector_entry()
        if frozen is not None and 0 <= int(frozen.branch_index) < len(candidates):
            _emit_selection_trace(
                selector_kind=(
                    "exclude"
                    if exclude is not None
                    else ("near" if near is not None else ("far" if far is not None else "exclude"))
                ),
                candidate_count=len(candidates),
                selected_index=int(frozen.branch_index),
            )
            return candidates[int(frozen.branch_index)]

    if exclude is not None:
        filtered = []
        tol = get_dynamic_tolerance()
        tol_sq = tol * tol
        for p in candidates:
            try:
                if p == exclude:
                    continue
            except Exception:
                pass
            try:
                dist_sq_val = to_float_safe(dist_sq(p, exclude))
                if dist_sq_val > tol_sq:
                    filtered.append(p)
            except Exception:
                filtered.append(p)
        candidates = filtered

        if not candidates:
            raise NoIntersectionError("No intersection found after exclusion")

    if near is not None:
        try:
            candidates.sort(key=lambda p: to_float_safe(dist_sq(p, near)))
        except Exception:
            pass
    elif far is not None:
        try:
            candidates.sort(key=lambda p: to_float_safe(dist_sq(p, far)), reverse=True)
        except Exception:
            pass

    if n is not None:
        if 1 <= n <= len(candidates):
            if near is not None:
                _emit_selection_trace(
                    selector_kind="near",
                    candidate_count=len(candidates),
                    selected_index=int(n - 1),
                )
            elif far is not None:
                _emit_selection_trace(
                    selector_kind="far",
                    candidate_count=len(candidates),
                    selected_index=int(n - 1),
                )
            elif exclude is not None:
                _emit_selection_trace(
                    selector_kind="exclude",
                    candidate_count=len(candidates),
                    selected_index=int(n - 1),
                )
            return candidates[n - 1]
        raise NoIntersectionError(f"Intersection #{n} does not exist (found {len(candidates)})")

    if near is not None or far is not None:
        _emit_selection_trace(
            selector_kind="near" if near is not None else "far",
            candidate_count=len(candidates),
            selected_index=0,
        )
        return candidates[0]

    if len(candidates) == 1:
        if exclude is not None:
            _emit_selection_trace(
                selector_kind="exclude",
                candidate_count=len(candidates),
                selected_index=0,
            )
        return candidates[0]

    if exclude is not None:
        _emit_selection_trace(
            selector_kind="exclude",
            candidate_count=len(candidates),
            selected_index=0,
        )
    return candidates


def _to_float_safe(expr: Any) -> float:
    return to_float_safe(expr)


def _dist_sq(p1: Any, p2: Any) -> Any:
    return dist_sq(p1, p2)


def _get_dynamic_tolerance() -> float:
    return get_dynamic_tolerance()


def _select_intersection(result: Any, n: Any, exclude: Any, near: Any, far: Any) -> Any:
    return select_intersection(result, n, exclude, near, far)
