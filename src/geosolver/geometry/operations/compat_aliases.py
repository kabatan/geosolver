"""Legacy compatibility aliases for geometry operations."""

from __future__ import annotations

from typing import Any

from geosolver.geometry.entities.base import Circle, Line
from geosolver.geometry.operations.basic import OnLine
from geosolver.geometry.operations.intersections import Intersect
from geosolver.geometry.operations.intersections_closest import ClosestPoint
from geosolver.geometry.operations.triangle import IncircleContactPoint


def Center(obj: Any) -> Any:
    if hasattr(obj, "center"):
        return obj.center
    circle = getattr(obj, "circle", None)
    if circle is not None and hasattr(circle, "center"):
        return circle.center
    raise TypeError(f"Center is not defined for {type(obj)}")


def Collinear(point1: Any, point2: Any, point3: Any, ordered: bool = False) -> Any:
    from geosolver.geometry.runtime import get_backend, BackendType
    try:
        if get_backend() == BackendType.MPMATH:
            from geosolver.geometry.mp.mp_api import MP_Collinear
            return MP_Collinear(point1, point2, point3, ordered=ordered)
    except Exception:
        pass
    return OnLine(point1, point2, point3, ordered=ordered)


def _resolve_circle_line_pair(arg1: Any, arg2: Any) -> tuple[Circle, Line] | None:
    if isinstance(arg1, Circle) and isinstance(arg2, Line):
        return arg1, arg2
    if isinstance(arg2, Circle) and isinstance(arg1, Line):
        return arg2, arg1
    return None


def _contact_point_circle_line(circle_obj: Circle, line_obj: Line) -> Any:
    try:
        return ClosestPoint(circle_obj.center, line_obj)
    except Exception:
        pass

    try:
        result = Intersect(circle_obj, line_obj)
    except Exception:
        result = Intersect(line_obj, circle_obj)

    if isinstance(result, (list, tuple)):
        if not result:
            return []
        return result[0]
    return result


def ContactPoint(*args: Any, **kwargs: Any) -> Any:
    if len(args) == 2 and not kwargs:
        pair = _resolve_circle_line_pair(args[0], args[1])
        if pair is not None:
            circle_obj, line_obj = pair
            return _contact_point_circle_line(circle_obj, line_obj)
    return IncircleContactPoint(*args, **kwargs)