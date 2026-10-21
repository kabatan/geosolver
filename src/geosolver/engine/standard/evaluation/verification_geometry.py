"""Geometric margins in coordinate units, including implicit predicate domains."""

from functools import lru_cache

from mpmath import mp

from geosolver.problem.dsl_spec import symbols_by_name
from geosolver.problem.ir.compiler import safe_eval_expr_hp


def _xy(point):
    if hasattr(point, "x") and hasattr(point, "y"):
        return point.x, point.y
    if isinstance(point, tuple | list) and len(point) == 2:
        return tuple(point)
    raise TypeError("expected a geometric point")


def _distance(a, b):
    ax, ay = _xy(a)
    bx, by = _xy(b)
    return mp.hypot(ax - bx, ay - by)


def triangle_margins(points):
    a, b, c = points
    ax, ay = _xy(a)
    bx, by = _xy(b)
    cx, cy = _xy(c)
    return {
        "edge:0": _distance(a, b),
        "edge:1": _distance(b, c),
        "edge:2": _distance(c, a),
        "noncollinear": abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)),
    }


def _point_segment_distance(p, a, b):
    px, py = _xy(p)
    ax, ay = _xy(a)
    bx, by = _xy(b)
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return _distance(p, a)
    t = max(mp.mpf(0), min(mp.mpf(1), ((px - ax) * dx + (py - ay) * dy) / length2))
    return mp.hypot(px - ax - t * dx, py - ay - t * dy)


def polygon_margins(points, *, simple, convex=False):
    """Edges cannot vanish; a passing simple polygon cannot touch another edge.

    Consecutive collinear vertices are permitted for a simple polygon.
    Nonincident vertex/edge clearances detect a change in topology without
    imposing noncollinearity on every triple.
    """
    points = tuple(points)
    margins = {
        f"edge:{i}": _distance(p, points[(i + 1) % len(points)]) for i, p in enumerate(points)
    }
    if simple:
        for i, point in enumerate(points):
            for j, start in enumerate(points):
                end = (j + 1) % len(points)
                if i not in (j, end):
                    margins[f"clearance:{i}:{j}"] = _point_segment_distance(
                        point, start, points[end]
                    )
    if convex:
        for i, point in enumerate(points):
            ax, ay = _xy(points[i - 1])
            bx, by = _xy(point)
            cx, cy = _xy(points[(i + 1) % len(points)])
            margins[f"turn:{i}"] = abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx))
    return margins


@lru_cache(maxsize=1)
def _triangle_functions():
    return frozenset(
        symbol.name
        for symbol in symbols_by_name().values()
        if symbol.category == "centers" or "three points are non-collinear" in symbol.domain
    ) | {
        "AssumeAcute",
        "AssumeObtuse",
        "AssumeRight",
        "AcuteTriangle",
        "ObtuseTriangle",
        "RightTriangle",
    }


def _bound_call(name, args, kwargs):
    symbol = symbols_by_name().get(name)
    if symbol is None:
        return name, args
    bound = list(args)
    for parameter in symbol.parameters[len(bound) :]:
        if parameter not in kwargs:
            break
        bound.append(kwargs[parameter])
    return symbol.name, tuple(bound)


def geometry_margins(calls, trace):
    margins = {}
    for index, (site, name, args, kwargs, result) in enumerate(calls):
        name, args = _bound_call(name, args, kwargs)
        key = f"{site}:{index}:{name}"
        if hasattr(result, "radius"):
            margins[key + ":positive_radius"] = result.radius
        if name == "Line" and len(args) == 3:
            # Coefficient form a*x+b*y+c=0 has no endpoint arguments. Its
            # forbidden boundary is the zero normal, not a distance between
            # the scalars a and b. Retain the unnormalised input coefficients.
            margins[key + ":coefficient_normal"] = mp.hypot(*args[:2])
        elif name in {"Line", "Segment", "Ray", "PointOnSegment"} and len(args) >= 2:
            margins[key + ":distinct"] = _distance(*args[:2])
        triangle_points = args
        if name == "Triangle" and len(args) == 1:
            triangle_points = args[0]
        if name in _triangle_functions() and len(triangle_points) >= 3:
            for suffix, value in triangle_margins(triangle_points[:3]).items():
                margins[f"{key}:{suffix}"] = value
        if name in {
            "ConvexPolygon",
            "SimplePolygon",
            "AssumeConvex",
            "AssumeStrictConvex",
            "AssumeSimplePolygon",
        }:
            polygon = args[0]
            points = getattr(polygon, "vertices", getattr(polygon, "points", polygon))
            # Legacy Assume* implementations return None on success and raise
            # on failure; public aliases can therefore also be void-valued.
            passed = result is None or bool(result)
            for suffix, value in polygon_margins(
                points,
                simple=passed,
                convex=passed and name != "SimplePolygon",
            ).items():
                margins[f"{key}:{suffix}"] = value
    for index, entry in enumerate(trace):
        if entry.margin is not None and mp.isfinite(entry.margin):
            margins[f"{entry.call_site_id}:{index}:selector"] = entry.margin
    return margins


def implicit_guard_margins(guard, context):
    # Compiled triangle predicates evaluate arguments without a runtime_call
    # for the predicate itself; retain their implicit nondegeneracy as well.
    if guard.kind == "triangle_class":
        points = tuple(safe_eval_expr_hp(source, context) for source in guard.argument_exprs)
        return triangle_margins(points)
    return {}
