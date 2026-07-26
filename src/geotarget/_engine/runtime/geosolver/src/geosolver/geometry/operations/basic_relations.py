"""Delegated implementations for basic geometric relation operations."""

from __future__ import annotations

from typing import Any, Sequence

from sympy import pi, sqrt

from geosolver.geometry.entities import Circle, Line, Point


def perpendicular_impl(obj1: Any, obj2: Any) -> Any:
    if isinstance(obj1, Line) and isinstance(obj2, Line):
        return obj1.a * obj2.a + obj1.b * obj2.b
    raise TypeError("Perpendicular requires two Lines")


def parallel_impl(obj1: Any, obj2: Any) -> Any:
    if isinstance(obj1, Line) and isinstance(obj2, Line):
        return obj1.a * obj2.b - obj2.a * obj1.b
    raise TypeError("Parallel requires two Lines")


def slope_impl(obj1: Any, obj2: Any | None = None) -> Any:
    if obj2 is not None:
        return (obj2.y - obj1.y) / (obj2.x - obj1.x)
    if isinstance(obj1, Line):
        return -obj1.a / obj1.b
    raise TypeError("Slope requires a Line or two Points")


def length_impl(obj: Any) -> Any:
    if hasattr(obj, "length"):
        return obj.length()
    if hasattr(obj, "p1") and hasattr(obj, "p2"):
        return obj.p1.distance_to(obj.p2)
    raise TypeError(f"Length not supported for {type(obj)}")


def perimeter_impl(args: Sequence[Any]) -> Any:
    if len(args) == 1:
        obj = args[0]
        if hasattr(obj, "perimeter"):
            return obj.perimeter()
        if hasattr(obj, "points"):
            points = obj.points
        else:
            raise TypeError("Perimeter requires a Polygon or points")
    else:
        points = args

    total = 0
    for index in range(len(points)):
        total += points[index].distance_to(points[(index + 1) % len(points)])
    return total


def circumference_impl(circle: Any) -> Any:
    if isinstance(circle, Circle):
        return 2 * pi * circle.radius
    raise TypeError("Circumference requires a Circle")


def are_concyclic_impl(p1: Point, p2: Point, p3: Point, p4: Point) -> Any:
    from geosolver.geometry.operations.constructions import CircleThroughThreePoints

    circle = CircleThroughThreePoints(p1, p2, p3)
    if circle is None:
        return 1.0
    return circle.center.distance_to(p4) - circle.radius


def parallelism_measure_impl(l1: Any, l2: Any, method: str = "cross") -> Any:
    if not (isinstance(l1, Line) and isinstance(l2, Line)):
        raise TypeError("ParallelismMeasure requires two Lines")
    if method == "cross":
        return l1.a * l2.b - l1.b * l2.a
    distance_1 = sqrt(l1.a**2 + l1.b**2)
    distance_2 = sqrt(l2.a**2 + l2.b**2)
    return (l1.a * l2.b - l1.b * l2.a) / (distance_1 * distance_2)
