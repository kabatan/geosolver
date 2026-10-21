from __future__ import annotations

import pytest
from mpmath import mp

from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
from geosolver.engine.standard.interpreter.context.high_precision import (
    _get_high_precision_context,
)
from geosolver.errors import (
    AmbiguousResultError,
    InfiniteSolutionsError,
    InvalidCircleError,
    NoIntersectionError,
)
from geosolver.geometry import (
    AreConcyclic,
    Circle,
    Intersect,
    IntersectCircles,
    IntersectLineCircle,
    Line,
    Point,
    Tangent,
)
from geosolver.geometry.mp.mp_core_types import MPCircle, MPPoint


def _cross_at_contact(point, center, line) -> object:
    # The contact point is the foot from the center to the normalized tangent.
    signed = line.a * center.x + line.b * center.y + line.c
    tx = center.x - signed * line.a
    ty = center.y - signed * line.b
    return (point.x - center.x) * (ty - center.y) - (point.y - center.y) * (tx - center.x)


@pytest.mark.parametrize("radius", [0, -1])
def test_circles_require_positive_radius_in_both_contexts(radius: int) -> None:
    with pytest.raises(InvalidCircleError):
        Circle(Point(0, 0), radius)
    with pytest.raises(InvalidCircleError):
        MPCircle(MPPoint(0, 0), radius)


def test_specialized_intersections_return_zero_one_or_two_distinct_points() -> None:
    circle = Circle(Point(0, 0), 1)

    assert IntersectLineCircle(Line(Point(-1, 2), Point(1, 2)), circle) == []
    tangent = IntersectLineCircle(Line(Point(-1, 1), Point(1, 1)), circle)
    secant = IntersectLineCircle(Line(Point(-2, 0), Point(2, 0)), circle)

    assert len(tangent) == 1
    assert len(secant) == 2
    assert [(point.x, point.y) for point in secant] == [(-1, 0), (1, 0)]


def test_generic_intersection_rejects_missing_ambiguous_and_infinite_results() -> None:
    circle = Circle(Point(0, 0), 1)
    with pytest.raises(NoIntersectionError):
        Intersect(Line(Point(-1, 2), Point(1, 2)), circle)
    with pytest.raises(AmbiguousResultError):
        Intersect(Line(Point(-2, 0), Point(2, 0)), circle)
    with pytest.raises(InfiniteSolutionsError):
        IntersectCircles(circle, Circle(Point(0, 0), 1))


def test_near_and_far_selector_ties_are_ambiguous() -> None:
    circle = Circle(Point(0, 0), 1)
    line = Line(Point(-2, 0), Point(2, 0))
    with pytest.raises(AmbiguousResultError):
        Intersect(line, circle, near=Point(0, 0))
    with pytest.raises(AmbiguousResultError):
        Intersect(line, circle, far=Point(0, 0))


def test_tangent_branch_orientation_matches_standard_and_high_precision() -> None:
    point = Point(2, 0)
    center = Point(0, 0)
    circle = Circle(center, 1)
    assert _cross_at_contact(point, center, Tangent(point, circle, True)) > 0
    assert _cross_at_contact(point, center, Tangent(point, circle, False)) < 0

    hp = _get_high_precision_context(80)
    hp_point = hp["Point"](2, 0)
    hp_center = hp["Point"](0, 0)
    hp_circle = hp["Circle"](hp_center, 1)
    assert _cross_at_contact(hp_point, hp_center, hp["Tangent"](hp_point, hp_circle, True)) > 0
    assert _cross_at_contact(hp_point, hp_center, hp["Tangent"](hp_point, hp_circle, False)) < 0


def test_tangent_on_circle_is_unique_and_inside_has_no_solution() -> None:
    circle = Circle(Point(0, 0), 1)
    first = Tangent(Point(1, 0), circle, True)
    second = Tangent(Point(1, 0), circle, False)
    assert first == second
    with pytest.raises(NoIntersectionError):
        Tangent(Point(0, 0), circle)


def test_are_concyclic_is_a_zero_residual_not_a_boolean() -> None:
    points = (Point(1, 0), Point(0, 1), Point(-1, 0), Point(0, -1))
    assert AreConcyclic(*points) == 0
    assert AreConcyclic(*points[:3], Point(0, -2)) != 0

    hp = _get_high_precision_context(80)
    hp_points = tuple(hp["Point"](point.x, point.y) for point in points)
    result = hp["AreConcyclic"](*hp_points)
    assert isinstance(result, mp.mpf)
    assert result == 0


def test_public_float_and_hp_contexts_have_callable_parity_without_mp_leakage() -> None:
    standard = _get_geometry_context()
    high_precision = _get_high_precision_context(80)
    standard_callables = {name for name, value in standard.items() if callable(value)}

    assert standard_callables <= {name for name, value in high_precision.items() if callable(value)}
    assert not any(name.startswith("MP_") for name in high_precision)


def test_tiny_but_distinct_lines_are_not_rejected_by_an_absolute_epsilon() -> None:
    standard = Line(Point(0, 0), Point(mp.mpf("1e-100"), 0))
    assert standard is not None
    hp = _get_high_precision_context(180)
    assert hp["Line"](hp["Point"](0, 0), hp["Point"](mp.mpf("1e-100"), 0)) is not None
