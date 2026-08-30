"""Delegated backend implementations for triangle circle-related operations."""

from __future__ import annotations

from collections.abc import Callable


def incenter_numpy_impl(A, B, C):
    import numpy as np

    A = np.asarray(A)
    B = np.asarray(B)
    C = np.asarray(C)
    a = np.linalg.norm(B - C)
    b = np.linalg.norm(C - A)
    c = np.linalg.norm(A - B)

    perimeter = a + b + c
    if perimeter < 1e-12:
        return A

    return (a * A + b * B + c * C) / perimeter


def incenter_mpmath_impl(A, B, C, *, point_class, distance_fn: Callable):
    a = distance_fn(B, C)
    b = distance_fn(C, A)
    c = distance_fn(A, B)
    perimeter = a + b + c
    return point_class(
        (a * A.x + b * B.x + c * C.x) / perimeter,
        (a * A.y + b * B.y + c * C.y) / perimeter,
    )


def incircle_numpy_impl(A, B, C, *, incenter_numpy_fn: Callable):
    import numpy as np

    center = incenter_numpy_fn(A, B, C)
    x1, y1 = A
    x2, y2 = B
    x3, y3 = C

    double_area = abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))

    a = np.linalg.norm(B - C)
    b = np.linalg.norm(C - A)
    c = np.linalg.norm(A - B)
    perimeter = a + b + c

    radius = double_area / perimeter
    return [center[0], center[1], radius]


def incircle_mpmath_impl(
    A,
    B,
    C,
    *,
    incenter_mpmath_fn: Callable,
    circle_class,
    distance_fn: Callable,
):
    center = incenter_mpmath_fn(A, B, C)
    x1, y1 = A.x, A.y
    x2, y2 = B.x, B.y
    x3, y3 = C.x, C.y
    double_area = abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))

    a = distance_fn(B, C)
    b = distance_fn(C, A)
    c = distance_fn(A, B)
    perimeter = a + b + c

    radius = double_area / perimeter
    return circle_class(center, radius)


def nine_point_circle_numpy_impl(
    A,
    B,
    C,
    *,
    circumcenter_numpy_fn: Callable,
    orthocenter_numpy_fn: Callable,
):
    import numpy as np

    circumcenter = circumcenter_numpy_fn(A, B, C)
    orthocenter = orthocenter_numpy_fn(A, B, C)

    if circumcenter is None or orthocenter is None:
        return None

    circumcenter = np.asarray(circumcenter)
    orthocenter = np.asarray(orthocenter)
    center = (circumcenter + orthocenter) / 2

    a_array = np.asarray(A)
    radius = np.linalg.norm(circumcenter - a_array)

    return [center[0], center[1], radius / 2]


def nine_point_circle_mpmath_impl(
    A,
    B,
    C,
    *,
    circumcenter_mpmath_fn: Callable,
    orthocenter_mpmath_fn: Callable,
    point_class,
    circle_class,
):
    from mpmath import sqrt

    circumcenter = circumcenter_mpmath_fn(A, B, C)
    orthocenter = orthocenter_mpmath_fn(A, B, C)
    if circumcenter is None or orthocenter is None:
        return None

    center = point_class(
        (circumcenter.x + orthocenter.x) / 2,
        (circumcenter.y + orthocenter.y) / 2,
    )
    radius = sqrt((circumcenter.x - A.x) ** 2 + (circumcenter.y - A.y) ** 2)
    return circle_class(center, radius / 2)
