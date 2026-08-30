"""
Geometric Transforms
"""

from typing import Any

from sympy import cos, sin

from geosolver.geometry.entities.base import Line, Point
from geosolver.geometry.operations.constructions import FootOfPerpendicular
from geosolver.geometry.registry import geometry_symbol


@geometry_symbol("Rotate", category="transforms")
def Rotate(point: Point, angle: Any, center: Point | None = None) -> Point:
    """Rotate point around center by angle"""
    center = Point(0, 0) if center is None else center
    dx = point.x - center.x
    dy = point.y - center.y

    c = cos(angle)
    s = sin(angle)

    nx = dx * c - dy * s + center.x
    ny = dx * s + dy * c + center.y
    return Point(nx, ny)


@Rotate.set_numpy
def _Rotate_numpy(point, angle, center=None):
    """NumPy"""
    import numpy as np

    point = np.asarray(point)
    center = np.array([0.0, 0.0]) if center is None else np.asarray(center)

    dx = point[0] - center[0]
    dy = point[1] - center[1]

    c = np.cos(angle)
    s = np.sin(angle)

    nx = dx * c - dy * s + center[0]
    ny = dx * s + dy * c + center[1]
    return [nx, ny]


@Rotate.set_mpmath
def _Rotate_mpmath(point, angle, center=None):
    """mpmath"""
    from mpmath import cos, sin

    center = Point(0, 0) if center is None else center
    dx = point.x - center.x
    dy = point.y - center.y
    c = cos(angle)
    s = sin(angle)
    nx = dx * c - dy * s + center.x
    ny = dx * s + dy * c + center.y
    return Point(nx, ny)


@geometry_symbol("Reflect", category="transforms")
def Reflect(obj: Any, axis: Point | Line) -> Any:
    """Reflect object across axis (Point or Line)"""
    # Currently only supports Point reflection
    # Dispatch based on obj type?
    # For now, assume obj is Point. If obj is Line/Circle, need more logic.

    if isinstance(obj, Point):
        if isinstance(axis, Point):
            # Point reflection
            # P' = 2*C - P
            return Point(2 * axis.x - obj.x, 2 * axis.y - obj.y)
        elif isinstance(axis, Line):
            # Line reflection
            # Foot H
            H = FootOfPerpendicular(axis, obj)
            return Point(2 * H.x - obj.x, 2 * H.y - obj.y)

    # Future extension: support Line/Circle reflection
    raise NotImplementedError(f"Reflection for {type(obj)} not implemented yet")


@Reflect.set_numpy
def _Reflect_numpy(obj, axis):
    """NumPy"""
    import numpy as np

    # obj is Point vector
    obj = np.asarray(obj)

    # Check if axis is Point (len 2) or Line (len 3)
    axis = np.asarray(axis)
    if axis.shape == (2,):
        # Point reflection
        return 2 * axis - obj
    elif axis.shape == (3,):
        # Line reflection
        # Need FootOfPerpendicular numpy impl
        # Copy logic or import? Import from constructions might cause loop if not careful.
        # But we are inside function, so okay.
        from geosolver.geometry.operations.constructions import _FootOfPerpendicular_numpy

        H = _FootOfPerpendicular_numpy(axis, obj)
        H = np.asarray(H)
        return 2 * H - obj

    return None


@Reflect.set_mpmath
def _Reflect_mpmath(obj, axis):
    """mpmath"""
    if isinstance(obj, Point):
        if isinstance(axis, Point):
            return Point(2 * axis.x - obj.x, 2 * axis.y - obj.y)
        elif isinstance(axis, Line):
            from geosolver.geometry.operations.constructions import _FootOfPerpendicular_mpmath

            H = _FootOfPerpendicular_mpmath(axis, obj)
            return Point(2 * H.x - obj.x, 2 * H.y - obj.y)
    return None
