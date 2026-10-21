"""
Polygon helper functions extracted from mp_impl.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from mpmath import cos as mp_cos
from mpmath import mp, mpf
from mpmath import pi as mp_pi
from mpmath import sin as mp_sin

from geosolver.geometry.mp.mp_conversion import to_mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPCircle, MPPoint


def _squared_distance(p: MPPoint, q: MPPoint) -> mpf:
    dx = q.x - p.x
    dy = q.y - p.y
    return dx * dx + dy * dy


def _polygon_relative_tolerance(
    points: tuple[MPPoint, ...],
) -> tuple[mpf, mpf]:
    """Return a dimensionless tolerance with a cancellation safety floor."""

    base = mpf(10) ** (-(mp.dps - 10))
    diameter_squared = max(
        _squared_distance(points[i], points[j])
        for i in range(len(points))
        for j in range(i + 1, len(points))
    )
    if diameter_squared == 0:
        return mp.inf, diameter_squared

    diameter = mp.sqrt(diameter_squared)
    coordinate_scale = max(max(abs(point.x), abs(point.y)) for point in points)
    cancellation_floor = mpf(16) * len(points) * mp.eps * coordinate_scale / diameter
    return max(base, cancellation_floor), diameter_squared


def _orientation(p: MPPoint, q: MPPoint, r: MPPoint, rel_tol: mpf) -> int:
    pqx = q.x - p.x
    pqy = q.y - p.y
    prx = r.x - p.x
    pry = r.y - p.y
    val = pqx * pry - pqy * prx
    scale_squared = (pqx * pqx + pqy * pqy) * (prx * prx + pry * pry)
    if scale_squared == 0 or val * val <= rel_tol * rel_tol * scale_squared:
        return 0
    return 1 if val > 0 else 2


def _on_segment(p: MPPoint, q: MPPoint, r: MPPoint, rel_tol: mpf) -> bool:
    segment_length = mp.sqrt(_squared_distance(p, r))
    coordinate_tol = rel_tol * segment_length
    return (
        min(p.x, r.x) - coordinate_tol <= q.x <= max(p.x, r.x) + coordinate_tol
        and min(p.y, r.y) - coordinate_tol <= q.y <= max(p.y, r.y) + coordinate_tol
    )


def _segments_intersect(p1: MPPoint, p2: MPPoint, p3: MPPoint, p4: MPPoint, rel_tol: mpf) -> bool:
    o1 = _orientation(p1, p2, p3, rel_tol)
    o2 = _orientation(p1, p2, p4, rel_tol)
    o3 = _orientation(p3, p4, p1, rel_tol)
    o4 = _orientation(p3, p4, p2, rel_tol)

    # The strict crossing test is reserved for four decisively non-collinear
    # orientations.  A tolerance-classified zero is handled by the explicit
    # on-segment cases below; otherwise a nearly collinear point outside the
    # finite segment could be mistaken for an intersection.
    if 0 not in (o1, o2, o3, o4) and o1 != o2 and o3 != o4:
        return True

    # Adjacent edges are filtered by the caller.  Therefore a collinear touch,
    # shared endpoint, or overlap here is a genuine self-intersection.
    if o1 == 0 and _on_segment(p1, p3, p2, rel_tol):
        return True
    if o2 == 0 and _on_segment(p1, p4, p2, rel_tol):
        return True
    if o3 == 0 and _on_segment(p3, p1, p4, rel_tol):
        return True
    return bool(o4 == 0 and _on_segment(p3, p2, p4, rel_tol))


def _is_convex_uncached(*points: MPPoint) -> bool | None:
    if len(points) < 3:
        return None

    n = len(points)
    rel_tol, polygon_scale_squared = _polygon_relative_tolerance(tuple(points))
    if polygon_scale_squared == 0:
        return False

    # A polygon with a repeated vertex is degenerate.  Checking every pair
    # also catches a repeated non-adjacent vertex that would otherwise appear
    # as a mere endpoint touch in the edge-intersection test.
    for i in range(n):
        for j in range(i + 1, n):
            if _squared_distance(points[i], points[j]) <= rel_tol * rel_tol * polygon_scale_squared:
                return False

    # Equal turn signs alone are insufficient: a star polygon can have the
    # same local turn at every vertex while still crossing itself.
    if mp_has_self_intersection(*points) is not False:
        return False

    sign = None
    for i in range(n):
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n]

        v1x = p2.x - p1.x
        v1y = p2.y - p1.y
        v2x = p3.x - p2.x
        v2y = p3.y - p2.y
        cross = v1x * v2y - v1y * v2x
        turn_scale_squared = (v1x * v1x + v1y * v1y) * (v2x * v2x + v2y * v2y)

        # ``AssumeConvex`` denotes strict convexity.  A zero turn leaves three
        # consecutive vertices collinear, so accepting it would admit a
        # degenerate boundary polygon.
        if turn_scale_squared == 0 or cross * cross <= rel_tol * rel_tol * turn_scale_squared:
            return False
        if sign is None:
            sign = cross > 0
        elif (cross > 0) != sign:
            return False

    if sign is None:
        return None
    return True


def _has_self_intersection_uncached(*points: MPPoint) -> bool | None:
    if len(points) < 3:
        return None

    n = len(points)
    rel_tol, _polygon_scale_squared = _polygon_relative_tolerance(tuple(points))
    edges = [(points[i], points[(i + 1) % n]) for i in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            if abs(i - j) == 1:
                continue
            if i == 0 and j == n - 1:
                continue

            p1, p2 = edges[i]
            p3, p4 = edges[j]
            if _segments_intersect(p1, p2, p3, p4, rel_tol):
                return True
    return False


def _polygon_coordinates(points):
    try:
        return tuple((p.x._mpf_, p.y._mpf_) for p in points)
    except AttributeError:
        return None


@lru_cache(maxsize=512)
def _cached_polygon_predicate(kind, precision, coordinates):
    # MPPoint is mutable and has tolerance-based equality. Retain exact numeric
    # values, never point identities or rounded decimal representations. The
    # active precision is part of the key because predicate tolerances use it.
    from geosolver.geometry.mp.mp_core_types import MPPoint

    points = tuple(MPPoint(mp.make_mpf(x), mp.make_mpf(y)) for x, y in coordinates)
    predicate = _is_convex_uncached if kind == "convex" else _has_self_intersection_uncached
    return predicate(*points)


def mp_is_convex(*points: MPPoint) -> bool | None:
    coordinates = _polygon_coordinates(points)
    if coordinates is None:
        return _is_convex_uncached(*points)
    return _cached_polygon_predicate("convex", mp.prec, coordinates)


def mp_has_self_intersection(*points: MPPoint) -> bool | None:
    coordinates = _polygon_coordinates(points)
    if coordinates is None:
        return _has_self_intersection_uncached(*points)
    return _cached_polygon_predicate("self_intersection", mp.prec, coordinates)


def mp_polygon_area(*points: MPPoint) -> mpf:
    if len(points) < 3:
        return mpf(0)

    n = len(points)
    area = mpf(0)
    for i in range(n):
        j = (i + 1) % n
        area += points[i].x * points[j].y
        area -= points[j].x * points[i].y
    return abs(area) / 2


def mp_inscribed_polygon_vertices(circle: MPCircle, *t_params: object) -> list[MPPoint]:
    if len(t_params) == 0:
        raise ValueError("At least one parameter is required for inscribed polygon")

    center = circle.center
    r = circle.radius
    point_cls = type(center)

    p1 = point_cls(center.x, center.y + r)
    vertices = [p1]

    theta_start = mp_pi / 2
    theta_prev = theta_start
    for i, t in enumerate(t_params):
        t_val = to_mpf(t)
        if t_val <= 0 or t_val >= 1:
            raise ValueError(f"Parameter t[{i}]={t} must be in range (0, 1)")

        remaining_angle = (theta_start + 2 * mp_pi) - theta_prev
        theta_new = theta_prev + t_val * remaining_angle
        new_vertex = point_cls(center.x + r * mp_cos(theta_new), center.y + r * mp_sin(theta_new))
        vertices.append(new_vertex)
        theta_prev = theta_new
    return vertices
