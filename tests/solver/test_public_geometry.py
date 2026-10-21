"""Public geometry contracts and numerical regressions."""

import pytest
from mpmath import mp

from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.problem.ir.compiler import safe_eval_expr_hp


@pytest.fixture(params=[15, 80, 180, 500])
def geometry(request):
    with mp.workdps(request.param), high_precision_mode():
        context = _get_high_precision_context(request.param)
        for name, expression in (
            ("A", "Point(0,0)"),
            ("B", "Point(4,0)"),
            ("C", "Point(0,3)"),
            ("P", "Point(3,4)"),
            ("W", "Circle(A,5)"),
            ("V", "Circle(Point(6,0),5)"),
            ("L", "Line(A,B)"),
        ):
            context[name] = safe_eval_expr_hp(expression, context)
        yield lambda expression: safe_eval_expr_hp(expression, context)


def close(actual, expected):
    expected = mp.mpf(expected)
    assert abs(actual - expected) <= 2000 * mp.eps * max(1, abs(expected))


def point_close(point, x, y):
    close(point.x, x)
    close(point.y, y)


def test_unused_metric_and_projection_kernels(geometry):
    ray = geometry("Ray(A,P)")
    point_close(ray.start, 0, 0)
    point_close(ray.through, 3, 4)
    point_close(geometry("ClosestPoint(P,L)"), 3, 0)
    close(geometry("Length(Segment(A,P))"), 5)
    close(geometry("Circumference(W)"), 10 * mp.pi)
    close(geometry("PowerOfPoint(P,W)"), 0)
    close(geometry("PowerOfPoint(A,W)"), -25)
    close(geometry("PowerOfPoint(Point(6,8),W)"), 75)
    close(geometry("ParallelismMeasure(L,Line(Point(0,2),Point(1,2)))"), 0)
    close(abs(geometry("ParallelismMeasure(L,Line(A,C))")), 1)
    close(geometry("acos(0)"), mp.pi / 2)
    close(geometry("asin(1)"), mp.pi / 2)
    close(geometry("atan2(1,-1)"), 3 * mp.pi / 4)
    close(geometry("max(-2,3,1)"), 3)
    close(geometry("IsPrime(17)"), 0)
    assert geometry("IsPrime(21)") > 0


def test_specialized_intersections_satisfy_independent_equations(geometry):
    circles = geometry("IntersectCircles(W,V)")
    assert len(circles) == 2
    for point in circles:
        close(point.x, 3)
        close(abs(point.y), 4)
        close(point.x**2 + point.y**2, 25)
        close((point.x - 6) ** 2 + point.y**2, 25)
    assert circles[0].y * circles[1].y < 0
    points = geometry("IntersectLineCircle(L,W)")
    assert len(points) == 2
    for point in points:
        close(abs(point.x), 5)
        close(point.y, 0)
    point_close(geometry("IntersectLines(L,Line(C,Point(3,0)))"), 3, 0)


def test_unused_circle_constructions_and_duality(geometry):
    circumcircle = geometry("CircleThroughThreePoints(A,B,C)")
    point_close(circumcircle.center, 2, mp.mpf(3) / 2)
    close(circumcircle.radius, mp.mpf(5) / 2)
    radical = geometry("RadicalAxis(W,V)")
    close(3 * radical.a + radical.c, 0)
    close(radical.b, 0)
    point_close(geometry("Pole(Line(Point(0,1),Point(1,1)),W)"), 0, 25)
    tangent = geometry("TangentLine(Point(10,0),W)")
    close(10 * tangent.a + tangent.c, 0)
    close(abs(tangent.c) / mp.sqrt(tangent.a**2 + tangent.b**2), 5)


def test_inscribed_regular_and_arc_points_have_geometric_properties(geometry):
    for expression in ("InscribedPolygon(W,0.25,0.5)", "InscribedPolygonVertices(W,0.25,0.5)"):
        result = geometry(expression)
        points = getattr(result, "vertices", result)
        assert len(points) == 3
        for point in points:
            close(point.x**2 + point.y**2, 25)
        assert len({(p.x._mpf_, p.y._mpf_) for p in points}) == 3
    result = geometry("RegularPolygon(A,B,6)")
    points = getattr(result, "vertices", result)
    assert len(points) == 6
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        close((p.x - q.x) ** 2 + (p.y - q.y) ** 2, 16)
    midpoint = geometry("PointOnArc(Arc(W,Point(5,0),Point(0,5)),0.5)")
    point_close(midpoint, 5 / mp.sqrt(2), 5 / mp.sqrt(2))


def test_unused_centers_on_the_three_four_five_triangle(geometry):
    point_close(geometry("FeuerbachPoint(A,B,C)"), 1, 2)
    point_close(geometry("GergonnePoint(A,B,C)"), mp.mpf(8) / 11, mp.mpf(9) / 11)
    point_close(geometry("NagelPoint(A,B,C)"), 2, 1)
    fermat = geometry("FermatPoint(A,B,C)")
    vertices = ((0, 0), (4, 0), (0, 3))
    for axis in (0, 1):
        gradient = mp.fsum(
            ((fermat.x, fermat.y)[axis] - point[axis])
            / mp.sqrt((fermat.x - point[0]) ** 2 + (fermat.y - point[1]) ** 2)
            for point in vertices
        )
        close(gradient, 0)
    isodynamic = geometry("IsodynamicPoint(A,B,C)")
    products = [
        side * mp.sqrt((isodynamic.x - p[0]) ** 2 + (isodynamic.y - p[1]) ** 2)
        for side, p in zip((5, 3, 4), vertices, strict=True)
    ]
    close(products[0], products[1])
    close(products[0], products[2])
    point_close(geometry("NinePointCenter(A,B,C)"), 1, mp.mpf(3) / 4)
    nine = geometry("NinePointCircle(A,B,C)")
    for x, y in ((2, 0), (0, mp.mpf(3) / 2), (2, mp.mpf(3) / 2)):
        close((x - nine.center.x) ** 2 + (y - nine.center.y) ** 2, nine.radius**2)
    # X9 is the symmedian point of the excentral triangle. Its 3-4-5
    # excenters (6,6),(-2,2),(3,-3) have opposite squared sides 50,90,80.
    point_close(geometry("Mittenpunkt(A,B,C)"), mp.mpf(18) / 11, mp.mpf(12) / 11)
    point_close(geometry("SymmedianPoint(A,B,C)"), mp.mpf(18) / 25, mp.mpf(24) / 25)
    point_close(geometry("TriangleCenter(A,B,C,6)"), mp.mpf(18) / 25, mp.mpf(24) / 25)
    excenter = geometry("Excenter(A,B,C)")
    distances = (abs(excenter.x), abs(excenter.y), abs(3 * excenter.x + 4 * excenter.y - 12) / 5)
    for distance in distances:
        close(distance, distances[0])
    # Spieker center is the incenter of the medial triangle: compare distances
    # to its three sides, independently of the center implementation.
    spieker = geometry("SpiekerCenter(A,B,C)")
    distances = (
        abs(spieker.x - 2),
        abs(spieker.y - mp.mpf(3) / 2),
        abs(3 * spieker.x + 4 * spieker.y - 6) / 5,
    )
    for distance in distances:
        close(distance, distances[0])
