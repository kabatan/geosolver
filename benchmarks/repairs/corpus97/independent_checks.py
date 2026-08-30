"""Independent exact checks for repaired references and geometric decompositions.

This module deliberately imports neither GeoSolver nor the DSL repair builders.
It is not a second numerical search and does not read campaign answers.
"""

import itertools

import sympy as s


def area(points):
    return (
        abs(
            sum(a.x * b.y - a.y * b.x for a, b in zip(points, points[1:] + points[:1], strict=True))
        )
        / 2
    )


def cross(a, b, p):
    return s.det(s.Matrix([[b.x - a.x, b.y - a.y], [p.x - a.x, p.y - a.y]]))


def clip(subject, boundary):
    """Exact convex polygon clipping; boundary is counterclockwise."""
    for a, b in zip(boundary, boundary[1:] + boundary[:1], strict=True):
        output = []
        if not subject:
            break
        prev = subject[-1]
        for current in subject:
            before, after = cross(a, b, prev), cross(a, b, current)
            if (before >= 0) != (after >= 0):
                output.append(s.simplify(prev + before / (before - after) * (current - prev)))
            if after >= 0:
                output.append(current)
            prev = current
        subject = output
    return subject


def hmmt_2022_rectangle_union():
    origin = s.Point(0, 0)
    rectangles = [[origin, s.Point(4, 0), s.Point(4, 3), s.Point(0, 3)]]
    for _ in range(3):
        previous = rectangles[-1]
        a = previous[2]
        c = previous[3] - s.Line(origin, a).projection(previous[3])
        rectangles.append([origin, a, a + c, c])
    # All 15 intersections, not just the three subtracted in the DSL formula.
    union = 0
    for count in range(1, 5):
        for chosen in itertools.combinations(rectangles, count):
            intersection = chosen[0]
            for polygon in chosen[1:]:
                intersection = clip(intersection, polygon)
            union += (-1) ** (count + 1) * area(intersection)
    assert s.simplify(union) == 30
    return union


def hmmt_2011_collinear_branches():
    a, d = s.Point(1, 0), s.Point(1, 1)
    values = []
    # A!=0 is forced by the circumcircle. Scaling by a permits A=(1,0).
    # The two distance-ratio possibilities are A-B=+/-2(B-C).
    for b, c in [
        (s.Point(s.Rational(2, 3), s.Rational(2, 3)), s.Point(s.Rational(1, 2), 1)),
        (s.Point(-2, -2), s.Point(s.Rational(-1, 2), -1)),
    ]:
        assert s.Line(a, b).contains(c) and a.distance(b) == 2 * b.distance(c)
        circle = s.Circle(a, d, c)
        e = next(p for p in circle.intersection(s.Line(s.Point(0, 0), s.Point(1, 1))) if p != d)
        f = s.Line(a, e).intersection(s.Line(s.Point(0, 0), s.Point(1, 2)))[0]
        assert (f - a).dot(e - a) > 0
        values.append(s.simplify(a.distance(e) / e.distance(f)))
    assert values == [7, s.Rational(35, 11)]
    return values


def jmo_2008_quad():
    answers = []
    for t in [8 - 4 * s.sqrt(2), 8 + 4 * s.sqrt(2)]:
        c = s.sqrt(t)
        a, cp = s.Point(0, 0), s.Point(c, 0)
        b = s.Point(c / 2, s.sqrt(4 - t / 4))
        d = s.Point((t + 8) / (2 * c), -s.sqrt(16 - t / 4 - 16 / t))
        assert s.simplify(a.distance(b) ** 2) == 4
        assert s.simplify(cp.distance(b) ** 2) == 4
        assert s.simplify(cp.distance(d) ** 2) == 12
        assert s.simplify(a.distance(d) ** 2) == 20
        midpoint_error = s.Segment(a, cp).midpoint.distance(s.Segment(b, d).midpoint) ** 2 - 2
        assert s.simplify(s.sqrtdenest(midpoint_error)) == 0
        turns = [
            s.simplify(cross(x, y, z))
            for x, y, z in [(a, b, cp), (b, cp, d), (cp, d, a), (d, a, b)]
        ]
        if all(v < 0 for v in turns) or all(v > 0 for v in turns):
            answers.append(s.radsimp(s.simplify(s.sqrtdenest(area([a, b, cp, d])))))
    assert len(answers) == 1 and s.simplify(answers[0] - (2 + 4 * s.sqrt(2))) == 0
    return answers


def jmo_2010_triangle():
    answers = []
    for u in [7 - 2 * s.sqrt(3), 7 + 2 * s.sqrt(3)]:
        t = s.sqrt(u)
        a, b, c = s.Point(0, 0), s.Point(2 * t, 0), s.Point(t / 2, s.sqrt(3) * t / 2)
        p = s.Point(t - 11 / (2 * t), 3 * s.sqrt(3) / (2 * t))
        assert all(
            s.simplify(p.distance(v) ** 2 - length) == 0 for v, length in [(a, 3), (b, 25), (c, 4)]
        )
        if all(s.simplify(cross(x, y, p)) > 0 for x, y in [(a, b), (b, c), (c, a)]):
            answers.append(s.simplify(area([a, b, c])))
    assert answers == [3 + 7 * s.sqrt(3) / 2]
    return answers


def main():
    print("HMMT rectangle union", hmmt_2022_rectangle_union())
    print("HMMT collinear branches", hmmt_2011_collinear_branches())
    print("JMO convex quadrilateral", jmo_2008_quad())
    print("JMO interior point", jmo_2010_triangle())


if __name__ == "__main__":
    main()
