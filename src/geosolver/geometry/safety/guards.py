"""Geometry-specific Assume guard implementations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _as_mp_point(point: Any, *, to_point_xy: Callable[[Any], tuple[float, float]]) -> Any:
    from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
        BoundaryOrigin,
        boundary_float_to_mpf,
    )
    from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
        HighPrecisionContaminationError,
    )
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
        is_high_precision_mode,
    )
    from geosolver.geometry.mp.mp_impl import MPPoint
    from geosolver.geometry.safety.numeric import to_point_xy as extract_coordinates

    if isinstance(point, MPPoint):
        return point
    x, y = extract_coordinates(point, to_float_fn=lambda value: value)
    try:
        # Preserve exact integers/rationals and already high-precision values.
        return MPPoint(x, y)
    except (HighPrecisionContaminationError, TypeError):
        if is_high_precision_mode():
            raise
    # The ordinary geometry API also accepts numerical SymPy/Python points.
    # Their existing float interpretation crosses an explicit boundary here;
    # the same conversion is forbidden in high-precision solver execution.
    x, y = to_point_xy(point)
    return MPPoint(
        boundary_float_to_mpf(x, origin=BoundaryOrigin.INITIAL_POINT),
        boundary_float_to_mpf(y, origin=BoundaryOrigin.INITIAL_POINT),
    )


def _triangle_cosines(
    A: Any,
    B: Any,
    C: Any,
    *,
    rel_tol: Any,
) -> tuple[Any, Any, Any] | None:
    """Return scale-free vertex cosines for a nondegenerate triangle."""

    from mpmath import mp

    abx = B.x - A.x
    aby = B.y - A.y
    acx = C.x - A.x
    acy = C.y - A.y
    bax = -abx
    bay = -aby
    bcx = C.x - B.x
    bcy = C.y - B.y
    cax = -acx
    cay = -acy
    cbx = -bcx
    cby = -bcy

    ab2 = abx * abx + aby * aby
    ac2 = acx * acx + acy * acy
    bc2 = bcx * bcx + bcy * bcy
    if ab2 == 0 or ac2 == 0 or bc2 == 0:
        return None

    cross = abx * acy - aby * acx
    sine = abs(cross) / mp.sqrt(ab2 * ac2)
    if sine <= rel_tol:
        return None

    cos_a = (abx * acx + aby * acy) / mp.sqrt(ab2 * ac2)
    cos_b = (bax * bcx + bay * bcy) / mp.sqrt(ab2 * bc2)
    cos_c = (cax * cbx + cay * cby) / mp.sqrt(ac2 * bc2)
    return cos_a, cos_b, cos_c


def _as_mp_triangle(
    A: Any,
    B: Any,
    C: Any,
    *,
    to_point_xy: Callable[[Any], tuple[float, float]],
) -> tuple[Any, Any, Any]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    converted = []
    for point in (A, B, C):
        if isinstance(point, MPPoint):
            converted.append(point)
        else:
            converted.append(_as_mp_point(point, to_point_xy=to_point_xy))
    return converted[0], converted[1], converted[2]


def assume_acute(
    *,
    A: Any,
    B: Any,
    C: Any,
    message: str | None,
    tol: float,
    assume_enabled: bool,
    handle_failure: Callable[[str], None],
    to_point_xy: Callable[[Any], tuple[float, float]],
) -> None:
    if not assume_enabled:
        return

    try:
        from mpmath import mp

        A, B, C = _as_mp_triangle(A, B, C, to_point_xy=to_point_xy)
        rel_tol = mp.mpf(str(tol))
        cosines = _triangle_cosines(A, B, C, rel_tol=rel_tol)
        if cosines is None or min(cosines) <= rel_tol:
            handle_failure(message or "Triangle is not acute")
    except TimeoutError:
        raise
    except Exception as exc:
        handle_failure(message or f"AssumeAcute undecidable: {exc}")


def assume_right(
    *,
    A: Any,
    B: Any,
    C: Any,
    message: str | None,
    tol: float,
    assume_enabled: bool,
    handle_failure: Callable[[str], None],
    to_point_xy: Callable[[Any], tuple[float, float]],
    to_float: Callable[[Any], float],
) -> None:
    if not assume_enabled:
        return

    try:
        from mpmath import mp

        A, B, C = _as_mp_triangle(A, B, C, to_point_xy=to_point_xy)
        rel_tol = mp.mpf(str(tol))
        cosines = _triangle_cosines(A, B, C, rel_tol=rel_tol)
        if cosines is None or min(abs(value) for value in cosines) > rel_tol:
            handle_failure(message or "Triangle is not right-angled")
    except TimeoutError:
        raise
    except Exception as exc:
        handle_failure(message or f"AssumeRight undecidable: {exc}")


def assume_obtuse(
    *,
    A: Any,
    B: Any,
    C: Any,
    message: str | None,
    tol: float,
    assume_enabled: bool,
    handle_failure: Callable[[str], None],
    to_point_xy: Callable[[Any], tuple[float, float]],
    to_float: Callable[[Any], float],
) -> None:
    if not assume_enabled:
        return

    try:
        from mpmath import mp

        A, B, C = _as_mp_triangle(A, B, C, to_point_xy=to_point_xy)
        rel_tol = mp.mpf(str(tol))
        cosines = _triangle_cosines(A, B, C, rel_tol=rel_tol)
        if cosines is None or min(cosines) >= -rel_tol:
            handle_failure(message or "Triangle is not obtuse")
    except TimeoutError:
        raise
    except Exception as exc:
        handle_failure(message or f"AssumeObtuse undecidable: {exc}")


def assume_convex(
    *,
    polygon: Any,
    message: str | None,
    assume_enabled: bool,
    handle_failure: Callable[[str], None],
    to_point_xy: Callable[[Any], tuple[float, float]],
) -> None:
    if not assume_enabled:
        return

    try:
        from geosolver.geometry.mp.mp_api import MP_IsConvex
        from geosolver.geometry.mp.mp_impl import MPPoint

        points_raw = getattr(polygon, "vertices", getattr(polygon, "points", polygon))
        if not isinstance(points_raw, list | tuple):
            points_raw = list(points_raw)

        mp_points = []
        for point in points_raw:
            if isinstance(point, MPPoint):
                mp_points.append(point)
            else:
                mp_points.append(_as_mp_point(point, to_point_xy=to_point_xy))

        is_convex = MP_IsConvex(*mp_points)
        if is_convex is not True:
            handle_failure(message or "Polygon is not convex")
    except TimeoutError:
        raise
    except Exception as exc:
        handle_failure(message or f"AssumeConvex undecidable: {exc}")


def assume_no_self_intersecting(
    *,
    polygon: Any,
    message: str | None,
    assume_enabled: bool,
    handle_failure: Callable[[str], None],
    to_point_xy: Callable[[Any], tuple[float, float]],
) -> None:
    if not assume_enabled:
        return

    try:
        from geosolver.geometry.mp.mp_api import MP_HasSelfIntersection
        from geosolver.geometry.mp.mp_impl import MPPoint

        points_raw = getattr(polygon, "vertices", getattr(polygon, "points", polygon))
        if not isinstance(points_raw, list | tuple):
            points_raw = list(points_raw)

        mp_points = []
        for point in points_raw:
            if isinstance(point, MPPoint):
                mp_points.append(point)
            else:
                mp_points.append(_as_mp_point(point, to_point_xy=to_point_xy))

        has_intersection = MP_HasSelfIntersection(*mp_points)
        if has_intersection is True:
            handle_failure(message or "Polygon has self-intersection")
    except TimeoutError:
        raise
    except Exception as exc:
        handle_failure(message or f"AssumeNoSelfIntersecting undecidable: {exc}")


def assume_order(
    *,
    P1: Any,
    P2: Any,
    P3: Any,
    message: str | None,
    tol: float,
    assume_enabled: bool,
    handle_failure: Callable[[str], None],
    to_float: Callable[[Any], float],
) -> None:
    if not assume_enabled:
        return

    try:
        from mpmath import mp

        from geosolver.geometry.safety.numeric import to_point_xy

        a, p, b = _as_mp_triangle(P1, P2, P3, to_point_xy=to_point_xy)
        dx, dy = b.x - a.x, b.y - a.y
        px, py = p.x - a.x, p.y - a.y
        length_squared = dx * dx + dy * dy
        if length_squared == 0:
            handle_failure(message or "Order requires distinct endpoints")
            return
        cross = (px * dy - py * dx) / length_squared
        projection = (px * dx + py * dy) / length_squared
        tolerance = mp.mpf(str(tol))
        if abs(cross) > tolerance or projection < -tolerance or projection > 1 + tolerance:
            handle_failure(message or "Points are not in order P1-P2-P3")
    except TimeoutError:
        raise
    except Exception as exc:
        handle_failure(message or f"AssumeOrder undecidable: {exc}")
