"""Shared numeric arc domain and branch rules for both evaluators."""

from mpmath import mp

from geosolver.errors import AmbiguousResultError, GeometryDomainError


def resolve_arc_arguments(circle, start, end, aliases):
    values = [circle, start, end]
    for key, value in aliases.items():
        if key not in ("omega", "A", "B"):
            raise TypeError(f"unknown Arc keyword: {key}")
        index = ("omega", "A", "B").index(key)
        if values[index] is not None:
            raise TypeError(f"duplicate Arc argument: {key}")
        values[index] = value
    if any(value is None for value in values):
        raise TypeError("Arc requires circle, start and end")
    return tuple(values)


def arc_parameters(circle, start, end, including=None, excluding=None, *, tolerance=None):
    def number(value):
        if hasattr(value, "evalf"):
            return mp.mpf(str(value.evalf(mp.dps)))
        return mp.mpf(value)

    if including is not None and excluding is not None:
        raise GeometryDomainError("choose only including or excluding")
    cx, cy, radius = number(circle.center.x), number(circle.center.y), number(circle.radius)
    tolerance = mp.power(10, -max(12, mp.dps - 10)) if tolerance is None else mp.mpf(tolerance)

    def angle(point):
        x, y = number(point.x) - cx, number(point.y) - cy
        if abs(mp.hypot(x, y) - radius) > tolerance * radius:
            raise GeometryDomainError("arc endpoints and selectors must lie on the circle")
        return mp.atan2(y, x)

    first, last = angle(start), angle(end)
    ccw = (last - first) % (2 * mp.pi)
    if min(ccw, 2 * mp.pi - ccw) <= tolerance:
        raise GeometryDomainError("arc endpoints must be distinct")
    if including is None and excluding is None:
        if abs(ccw - mp.pi) <= tolerance:
            raise AmbiguousResultError("antipodal arc endpoints require a selector")
        use_ccw = ccw < mp.pi
    else:
        relative = (angle(including if including is not None else excluding) - first) % (2 * mp.pi)
        if min(relative, 2 * mp.pi - relative, abs(relative - ccw)) <= tolerance:
            raise AmbiguousResultError("an endpoint does not select a unique arc")
        use_ccw = (relative < ccw) == (including is not None)
    return first, ccw if use_ccw else ccw - 2 * mp.pi
