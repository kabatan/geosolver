"""Geometry-specific Assume guard implementations."""

from __future__ import annotations

from typing import Any, Callable


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
            x, y = to_point_xy(point)
            converted.append(MPPoint(x, y))
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

        points_raw = getattr(polygon, "points", polygon)
        if not isinstance(points_raw, (list, tuple)):
            points_raw = list(points_raw)

        mp_points = []
        for point in points_raw:
            if isinstance(point, MPPoint):
                mp_points.append(point)
            else:
                px, py = to_point_xy(point)
                mp_points.append(MPPoint(px, py))

        is_convex = MP_IsConvex(*mp_points)
        if is_convex is not True:
            handle_failure(message or "Polygon is not convex")
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

        points_raw = getattr(polygon, "points", polygon)
        if not isinstance(points_raw, (list, tuple)):
            points_raw = list(points_raw)

        mp_points = []
        for point in points_raw:
            if isinstance(point, MPPoint):
                mp_points.append(point)
            else:
                px, py = to_point_xy(point)
                mp_points.append(MPPoint(px, py))

        has_intersection = MP_HasSelfIntersection(*mp_points)
        if has_intersection is True:
            handle_failure(message or "Polygon has self-intersection")
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
        from geosolver.geometry.operations import OnLine

        residual = to_float(OnLine(P1, P2, P3, ordered=True))
        if residual > tol:
            handle_failure(message or f"Points are not in order P1-P2-P3 (residual: {residual})")
    except Exception as exc:
        handle_failure(message or f"AssumeOrder undecidable: {exc}")
