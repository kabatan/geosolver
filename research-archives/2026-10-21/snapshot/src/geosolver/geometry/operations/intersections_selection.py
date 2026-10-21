"""Intersection candidate selection helpers extracted from intersections module."""

from __future__ import annotations

from math import sqrt
from typing import Any

from geosolver.errors import AmbiguousResultError, NoIntersectionError


def _emit_selection_trace(
    *,
    selector_kind: str,
    candidate_count: int,
    selected_index: int,
    candidates: tuple = (),
    margin: Any = None,
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
            candidates=candidates,
            margin=margin,
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
    selector_count = sum(value is not None for value in (n, exclude, near, far))
    if selector_count > 1:
        raise ValueError("Intersect accepts at most one of n, exclude, near, and far")
    if result is None:
        raise NoIntersectionError("No intersection found")

    candidates = result[:] if isinstance(result, list) else [result]

    if not candidates:
        raise NoIntersectionError("No intersection found")

    original = sorted(candidates, key=lambda point: (point.x, point.y))
    candidates = original[:]
    selector_kind = (
        "n"
        if n is not None
        else "exclude"
        if exclude is not None
        else "near"
        if near is not None
        else "far"
        if far is not None
        else "unique"
    )
    margin = float("inf")

    def finish(point):
        index = next(i for i, candidate in enumerate(original) if candidate is point)
        _emit_selection_trace(
            selector_kind=selector_kind,
            candidate_count=len(original),
            selected_index=index,
            candidates=tuple((p.x, p.y) for p in original),
            margin=margin,
        )
        return point

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
        removed = [p for p in original if all(p is not other for other in filtered)]
        margin = (
            min(sqrt(to_float_safe(dist_sq(p, exclude))) for p in filtered)
            - sqrt(to_float_safe(dist_sq(removed[0], exclude)))
            if len(removed) == 1
            else 0
        )

    if near is not None:
        candidates.sort(key=lambda p: to_float_safe(dist_sq(p, near)))
        if len(candidates) > 1:
            first = to_float_safe(dist_sq(candidates[0], near))
            second = to_float_safe(dist_sq(candidates[1], near))
            scale = max(abs(first), abs(second), 1.0)
            if abs(second - first) <= get_dynamic_tolerance() * scale:
                raise AmbiguousResultError("near selector is tied")
            margin = abs(sqrt(second) - sqrt(first))
    elif far is not None:
        candidates.sort(key=lambda p: to_float_safe(dist_sq(p, far)), reverse=True)
        if len(candidates) > 1:
            first = to_float_safe(dist_sq(candidates[0], far))
            second = to_float_safe(dist_sq(candidates[1], far))
            scale = max(abs(first), abs(second), 1.0)
            if abs(second - first) <= get_dynamic_tolerance() * scale:
                raise AmbiguousResultError("far selector is tied")
            margin = abs(sqrt(second) - sqrt(first))

    if n is not None:
        if 1 <= n <= len(candidates):
            return finish(candidates[n - 1])
        raise NoIntersectionError(f"Intersection #{n} does not exist (found {len(candidates)})")

    if near is not None or far is not None:
        return finish(candidates[0])

    if len(candidates) == 1:
        return finish(candidates[0])

    if exclude is not None:
        raise AmbiguousResultError("exclude selector leaves multiple intersections")
    raise AmbiguousResultError("multiple intersections require one selector")
