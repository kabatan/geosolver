"""Independent Euclidean arithmetic for the research-only GMB witness checker.

This module imports neither solver and never optimizes, repairs or projects a witness.
The arithmetic is implemented from dot/cross products using a private mpmath context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mpmath


@dataclass(frozen=True)
class Point:
    x: Any
    y: Any
    span: Any = None

    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Point(self.x - other.x, self.y - other.y)

    def times(self, factor):
        return Point(self.x * factor, self.y * factor)


@dataclass(frozen=True)
class Line:
    """Unit normal form; span/anchor are error references, not physical line data.

    An anchor need not lie exactly on an approximately reported line. Never use
    this metadata to compute the line's actual normal or offset.
    """

    n: Point
    c: Any
    span: Any
    anchor: Point | None = None


@dataclass(frozen=True)
class Circle:
    center: Point
    radius: Any
    span: Any = None


@dataclass(frozen=True)
class Number:
    value: Any
    scale: Any


class CheckError(ValueError):
    def __init__(self, code, message, status="failed", margin=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.margin = margin


def dot(a, b):
    return a.x * b.x + a.y * b.y


def cross(a, b):
    return a.x * b.y - a.y * b.x


def turn(a):
    return Point(-a.y, a.x)


class Geometry:
    def __init__(self, tolerance, dps):
        self.mp = mpmath.mp.clone()
        self.mp.dps = dps
        self.tolerance = self.mp.mpf(tolerance)
        self.roundoff = self.mp.power(10, -(dps - 15))
        self.path = "input"
        self.domain_evidence = []

    def scalar(self, value):
        if isinstance(value, bool) or not isinstance(value, str | int | float):
            raise CheckError("invalid_number", "expected a finite decimal scalar")
        try:
            result = self.mp.mpf(str(value))
        except ValueError as exc:
            raise CheckError("invalid_number", "invalid decimal scalar") from exc
        if not self.mp.isfinite(result):
            raise CheckError("nonfinite_number", "nonfinite witness value")
        return result

    def point(self, value):
        if isinstance(value, dict) and set(value) == {"x", "y"}:
            value = [value["x"], value["y"]]
        if not isinstance(value, list | tuple) or len(value) != 2:
            raise CheckError("invalid_point", "point must have exactly two coordinates")
        return Point(*(self.scalar(item) for item in value))

    def fmt(self, value):
        return self.mp.nstr(value, n=min(self.mp.dps, 50))

    def norm(self, vector):
        return self.mp.sqrt(dot(vector, vector))

    def dist(self, a, b):
        return self.norm(a - b)

    def normalized(self, value, scale):
        if scale == 0:
            return self.mp.zero if value == 0 else self.mp.inf
        return value / abs(scale)

    def positive(self, value, scale, code):
        margin = self.normalized(value, scale)
        if value <= 0:
            raise CheckError(code, "required positive geometric margin", margin=margin)
        if margin <= self.tolerance:
            raise CheckError(
                code, "positive margin unresolved at this tolerance", "unresolved", margin
            )
        self.domain_evidence.append(
            {"source_path": self.path, "code": code, "margin": self.fmt(margin)}
        )

    def separated(self, a, b, scale=None):
        distance = self.dist(a, b)
        self.positive(distance, distance if scale is None else scale, "coincident_points")
        return distance

    def spread(self, *points):
        return max(
            (self.dist(a, b) for i, a in enumerate(points) for b in points[i + 1 :]),
            default=self.mp.zero,
        )

    def through(self, a, b):
        distance = self.separated(a, b)
        n = turn(b - a).times(1 / distance)
        return Line(n, -dot(n, a), distance, a)

    def coefficients(self, values, scale=1):
        if not isinstance(values, list | tuple) or len(values) != 3:
            raise CheckError("invalid_line", "line requires [a,b,c] for ax+by+c=0")
        a, b, c = (self.scalar(v) for v in values)
        magnitude = self.mp.sqrt(a * a + b * b)
        if magnitude == 0:
            raise CheckError("invalid_line", "line normal cannot vanish")
        return Line(Point(a / magnitude, b / magnitude), c / magnitude, self.mp.mpf(scale))

    def side(self, p, line):
        return dot(line.n, p) + line.c

    def foot(self, p, line):
        return p - line.n.times(self.side(p, line))

    def reflect_point(self, p, line):
        return p - line.n.times(2 * self.side(p, line))

    def parallel_at(self, p, line):
        return Line(line.n, -dot(line.n, p), line.span, p)

    def perpendicular_at(self, p, line):
        normal = turn(line.n)
        return Line(normal, -dot(normal, p), line.span, p)

    def reflect_line(self, line, mirror):
        # Substitute the affine reflection into the actual implicit equation.
        # c' = c - 2*d*(n dot m). Metadata cannot alter the reflected line.
        projection = dot(line.n, mirror.n)
        normal = line.n - mirror.n.times(2 * projection)
        offset = line.c - 2 * mirror.c * projection
        reference = line.anchor if line.anchor is not None else line.n.times(-line.c)
        anchor = self.reflect_point(reference, mirror)
        return Line(normal, offset, min(line.span, mirror.span), anchor)

    def intersect_lines(self, first, second):
        determinant = cross(first.n, second.n)
        self.positive(abs(determinant), 1, "nonunique_line_intersection")
        return Point(
            (first.n.y * second.c - first.c * second.n.y) / determinant,
            (first.c * second.n.x - first.n.x * second.c) / determinant,
        )

    def triangle(self, a, b, c):
        scale = self.spread(a, b, c)
        area2 = cross(b - a, c - a)
        self.positive(abs(area2), scale * scale, "collinear_triangle")
        return scale

    def circumcenter(self, a, b, c):
        self.triangle(a, b, c)
        u, v = b - a, c - a
        denominator = 2 * cross(u, v)
        uu, vv = dot(u, u), dot(v, v)
        return a + Point(
            (uu * v.y - vv * u.y) / denominator,
            (u.x * vv - v.x * uu) / denominator,
        )

    def center(self, kind, a, b, c):
        self.triangle(a, b, c)
        if kind == "circumcenter":
            return self.circumcenter(a, b, c)
        if kind == "orthocenter":
            # Euler's vector identity, valid also when one angle is exactly right.
            return a + b + c - self.circumcenter(a, b, c).times(2)
        if kind == "centroid":
            return (a + b + c).times(self.mp.mpf(1) / 3)
        weights = [self.dist(b, c), self.dist(c, a), self.dist(a, b)]
        if kind == "excenter":
            weights[0] = -weights[0]
        elif kind != "incenter":
            raise CheckError("unsupported_center", kind, "unsupported")
        denominator = sum(weights)
        self.positive(denominator, sum(abs(v) for v in weights), "undefined_center")
        return (a.times(weights[0]) + b.times(weights[1]) + c.times(weights[2])).times(
            1 / denominator
        )

    def circle(self, center, radius):
        self.positive(radius, abs(radius), "nonpositive_radius")
        return Circle(center, radius, radius)

    def triangle_circle(self, kind, a, b, c):
        if kind in {"circ", "circumcircle"}:
            center = self.circumcenter(a, b, c)
            return self.circle(center, self.dist(center, a))
        center = self.center("incenter" if kind == "incircle" else "excenter", a, b, c)
        return self.circle(center, abs(self.side(center, self.through(b, c))))

    def bisector(self, a, vertex, c):
        scale = self.triangle(a, vertex, c)
        u, v = a - vertex, c - vertex
        direction = u.times(1 / self.norm(u)) + v.times(1 / self.norm(v))
        return self.through(vertex, vertex + direction.times(scale))

    def angle(self, a, vertex, c):
        u, v = a - vertex, c - vertex
        scale = max(self.norm(u), self.norm(v))
        self.separated(a, vertex, scale)
        self.separated(c, vertex, scale)
        return self.mp.atan2(abs(cross(u, v)), dot(u, v))

    def right_error(self, a, vertex, c):
        u, v = a - vertex, c - vertex
        scale = max(self.norm(u), self.norm(v))
        self.separated(a, vertex, scale)
        self.separated(c, vertex, scale)
        return abs(dot(u, v)) / (self.norm(u) * self.norm(v))

    def line_circle(self, line, circle):
        distance = self.side(circle.center, line)
        height2 = circle.radius**2 - distance**2
        scale2 = max(circle.radius**2, distance**2)
        relative = self.normalized(height2, scale2)
        if abs(relative) <= self.roundoff:
            height2 = self.mp.zero
        elif height2 < 0:
            status = "unresolved" if abs(relative) <= self.tolerance**2 else "failed"
            raise CheckError("no_real_intersection", "line and circle do not meet", status)
        foot = circle.center - line.n.times(distance)
        if height2 == 0:
            return [foot]
        shift = turn(line.n).times(self.mp.sqrt(height2))
        return [foot - shift, foot + shift]

    def circle_circle(self, first, second):
        direction = second.center - first.center
        distance = self.norm(direction)
        scale = max(first.radius, second.radius, distance)
        self.positive(distance, scale, "concentric_circles")
        normal = direction.times(1 / distance)
        # Radical axis formed in coordinates relative to the first center.
        offset = (distance**2 + first.radius**2 - second.radius**2) / (2 * distance)
        anchor = first.center + normal.times(offset)
        line = Line(normal, -dot(normal, anchor), scale, anchor)
        return self.line_circle(line, first)

    def arc_midpoint(self, b, c, a):
        circle = self.triangle_circle("circ", a, b, c)
        points = self.line_circle(self.bisector(b, a, c), circle)
        distances = [self.dist(p, a) for p in points]
        if len(points) != 2:
            raise CheckError("undefined_arc_midpoint", "arc midpoint needs a second intersection")
        return points[distances.index(max(distances))]

    def point_error(self, a, b, scale):
        return self.normalized(self.dist(a, b), scale)

    def line_error(self, first, second, scale):
        # Offset comparison at the global origin amplifies tiny angle errors when
        # that origin is far away. Check incidence at construction-local anchors.
        errors = [abs(cross(first.n, second.n))]
        if first.anchor is not None:
            point = self.foot(first.anchor, first)
            errors.append(self.normalized(abs(self.side(point, second)), scale))
        if second.anchor is not None:
            point = self.foot(second.anchor, second)
            errors.append(self.normalized(abs(self.side(point, first)), scale))
        if first.anchor is None and second.anchor is None:
            # A free line has no intrinsic anchor; use each line's own closest
            # point to the declared coordinate-chart origin and disclose that
            # limitation in the checker policy.
            errors.extend(
                [
                    self.normalized(abs(self.side(first.n.times(-first.c), second)), scale),
                    self.normalized(abs(self.side(second.n.times(-second.c), first)), scale),
                ]
            )
        return max(errors)

    def circle_error(self, first, second):
        scale = min(
            first.span if first.span is not None else first.radius,
            second.span if second.span is not None else second.radius,
        )
        return max(
            self.point_error(first.center, second.center, scale),
            self.normalized(abs(first.radius - second.radius), scale),
        )

    def on_line_error(self, point, line):
        return self.normalized(abs(self.side(point, line)), line.span)

    def on_circle_error(self, point, circle):
        return abs(self.dist(point, circle.center) - circle.radius) / circle.radius

    def side_margin(self, first, second, line, opposite=False):
        one, two = self.side(first, line), self.side(second, line)
        scale = max(line.span, self.dist(first, second))
        one, two = one / scale, two / scale
        if opposite:
            two = -two
        return min(abs(one), abs(two)) if one * two > 0 else -min(abs(one), abs(two))

    def segment_data(self, point, a, b):
        length = self.separated(a, b)
        u, v = b - a, point - a
        t = dot(u, v) / (length * length)
        error = abs(cross(u, v)) / (length * length)
        return error, t

    def convex_margins(self, points):
        if len(points) < 3:
            raise CheckError("invalid_polygon", "polygon requires at least three vertices")
        scale = self.spread(*points)
        turns = [
            cross(points[(i + 1) % len(points)] - a, points[(i + 2) % len(points)] - a)
            for i, a in enumerate(points)
        ]
        orientation = 1 if sum(turns) > 0 else -1
        margins = []
        for i, a in enumerate(points):
            b = points[(i + 1) % len(points)]
            self.separated(a, b, scale)
            for j, p in enumerate(points):
                if j not in {i, (i + 1) % len(points)}:
                    margins.append(orientation * cross(b - a, p - a) / scale**2)
        return margins

    def inside_margins(self, point, points):
        polygon_margins = self.convex_margins(points)
        for margin in polygon_margins:
            self.positive(margin, 1, "not_strictly_convex_polygon")
        scale = self.spread(*points)
        area2 = sum(cross(a, points[(i + 1) % len(points)]) for i, a in enumerate(points))
        orientation = 1 if area2 > 0 else -1
        return [
            orientation * cross(points[(i + 1) % len(points)] - a, point - a) / scale**2
            for i, a in enumerate(points)
        ]
