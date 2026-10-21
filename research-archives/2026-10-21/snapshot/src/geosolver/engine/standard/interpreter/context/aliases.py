"""Legacy symbol aliases for autosolve execution contexts."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from geosolver.errors import GeometryDomainError


def _center_alias(obj: Any) -> Any:
    if hasattr(obj, "center"):
        return obj.center
    circle = getattr(obj, "circle", None)
    if circle is not None and hasattr(circle, "center"):
        return circle.center
    raise TypeError(f"Center is not defined for {type(obj)}")


def _triangle_vertices(points: tuple[Any, ...]) -> list[Any]:
    if len(points) == 1 and isinstance(points[0], list | tuple):
        points = tuple(points[0])
    if len(points) != 3:
        raise GeometryDomainError("Triangle requires exactly three vertices")
    a, b, c = points
    area2 = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
    if area2 == 0:
        raise GeometryDomainError("Triangle requires three non-collinear vertices")
    return list(points)


def _triangle_as_polygon(*points: Any, polygon_ctor: Callable[..., Any]) -> Any:
    # Both backends accept a single sequence. The ordinary Polygon constructor
    # does not accept the variadic historical spelling supported by MP_Polygon.
    return polygon_ctor(_triangle_vertices(points))


def _triangle_as_points(*points: Any) -> list[Any]:
    return _triangle_vertices(points)


def _contact_point_alias(
    obj: Any,
    ref: Any,
    *,
    intersect_fn: Callable[..., Any],
    closest_fn: Callable[..., Any] | None = None,
) -> Any:
    center = getattr(obj, "center", None)
    if (
        center is not None
        and hasattr(ref, "a")
        and hasattr(ref, "b")
        and hasattr(ref, "c")
        and callable(closest_fn)
    ):
        try:
            return closest_fn(center, ref)
        except Exception:
            pass

    try:
        result = intersect_fn(obj, ref)
    except Exception:
        result = intersect_fn(ref, obj)

    if isinstance(result, list | tuple):
        if not result:
            return []
        return result[0]
    return result


def _is_line_like(obj: Any) -> bool:
    return hasattr(obj, "a") and hasattr(obj, "b") and hasattr(obj, "c")


def _is_circle_like(obj: Any) -> bool:
    return hasattr(obj, "center") and hasattr(obj, "radius")


def _contact_point_compat(
    *args: Any,
    existing_fn: Callable[..., Any] | None,
    intersect_fn: Callable[..., Any] | None,
    closest_fn: Callable[..., Any] | None,
) -> Any:
    if len(args) == 2:
        left, right = args
        circle_obj = None
        line_obj = None
        if _is_circle_like(left) and _is_line_like(right):
            circle_obj, line_obj = left, right
        elif _is_circle_like(right) and _is_line_like(left):
            circle_obj, line_obj = right, left

        if circle_obj is not None and line_obj is not None:
            if callable(closest_fn):
                try:
                    return closest_fn(circle_obj.center, line_obj)
                except Exception:
                    pass
            if callable(intersect_fn):
                try:
                    result = intersect_fn(circle_obj, line_obj)
                except Exception:
                    result = intersect_fn(line_obj, circle_obj)
                if isinstance(result, list | tuple):
                    if not result:
                        return []
                    return result[0]
                return result

    if callable(existing_fn):
        return existing_fn(*args)

    if len(args) == 2 and callable(intersect_fn):
        return _contact_point_alias(
            args[0],
            args[1],
            intersect_fn=intersect_fn,
            closest_fn=closest_fn,
        )

    raise TypeError("ContactPoint の互換呼び出しに失敗しました")


def apply_geometry_aliases(context: dict[str, Any]) -> dict[str, Any]:
    if "Midpoint" in context and "MidPoint" not in context:
        context["MidPoint"] = context["Midpoint"]

    if "Triangle" not in context:
        polygon_ctor = context.get("Polygon")
        if callable(polygon_ctor):
            context["Triangle"] = partial(_triangle_as_polygon, polygon_ctor=polygon_ctor)
        else:
            context["Triangle"] = _triangle_as_points

    if "Center" not in context:
        context["Center"] = _center_alias

    if callable(context.get("Intersect")):
        context["ContactPoint"] = partial(
            _contact_point_compat,
            existing_fn=context.get("ContactPoint"),
            intersect_fn=context.get("Intersect"),
            closest_fn=context.get("ClosestPoint"),
        )

    return context
