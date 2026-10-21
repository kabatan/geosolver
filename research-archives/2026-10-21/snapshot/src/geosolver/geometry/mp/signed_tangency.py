"""Internal signed zero test for local differentiation, not a public DSL symbol."""


def signed_tangency(first, second):
    """Have the same absolute value/domain as IsTangent, without its zero cusp.

    The line--circle residual is |signed distance|-r; near either tangent it
    is smooth.  Unlike a squared residual, its units and conditioning remain
    those of the public distance residual.  For circles choose the nearer
    tangency equation; coincident circles must never become a zero.
    """
    from geosolver.geometry.mp.mp_api import MP_IsTangent

    # IsTangent also accepts arcs and tests their supporting circles.
    first = getattr(first, "circle", first)
    second = getattr(second, "circle", second)

    if hasattr(first, "a") and hasattr(second, "radius"):
        line, circle = first, second
    elif hasattr(second, "a") and hasattr(first, "radius"):
        line, circle = second, first
    else:
        line = circle = None
    if line is not None:
        if circle.radius <= 0:
            return MP_IsTangent(first, second)
        distance = line.a * circle.center.x + line.b * circle.center.y + line.c
        return abs(distance) - circle.radius
    if hasattr(first, "radius") and hasattr(second, "radius"):
        distance = first.center.distance_to(second.center)
        if distance == 0 or first.radius <= 0 or second.radius <= 0:
            return MP_IsTangent(first, second)
        outer = distance - (first.radius + second.radius)
        inner = distance - abs(first.radius - second.radius)
        return outer if abs(outer) <= abs(inner) else inner
    return MP_IsTangent(first, second)
