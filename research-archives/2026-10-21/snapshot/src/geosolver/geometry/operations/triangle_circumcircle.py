"""Circumcircle operations extracted from triangle module."""

from __future__ import annotations

from geosolver.geometry.entities.base import Circle, Point
from geosolver.geometry.registry import geometry_symbol

_NUMPY_SOFTCAP_MAX_RADIUS = 1e6
_MP_SOFTCAP_MAX_RADIUS = "1e6"


@geometry_symbol("Circumcircle", category="triangle")
def Circumcircle(A: Point, B: Point, C: Point) -> Circle | None:
    """Triangle circumcircle."""
    from geosolver.geometry.operations.triangle import Circumcenter

    center = Circumcenter(A, B, C)
    if center is None:
        return None
    r = center.distance_to(A)
    return Circle(center, r)


@Circumcircle.set_numpy
def _Circumcircle_numpy(A, B, C):
    """NumPy implementation with smooth radius soft-cap."""
    import numpy as np

    from geosolver.geometry.operations.triangle import _circumcenter_numpy_impl

    center = _circumcenter_numpy_impl(A, B, C)
    if center is None:
        return None
    dx = A[0] - center[0]
    dy = A[1] - center[1]
    r = np.sqrt(dx * dx + dy * dy)
    r = _NUMPY_SOFTCAP_MAX_RADIUS * np.tanh(r / _NUMPY_SOFTCAP_MAX_RADIUS)
    return [center[0], center[1], r]


@Circumcircle.set_mpmath
def _Circumcircle_mpmath(A, B, C):
    """mpmath implementation with smooth radius soft-cap."""
    from mpmath import mpf, sqrt, tanh

    from geosolver.geometry.operations.triangle import _Circumcenter_mpmath

    center = _Circumcenter_mpmath(A, B, C)
    if center is None:
        return None
    dx = A.x - center.x
    dy = A.y - center.y
    r = sqrt(dx**2 + dy**2)
    max_radius = mpf(_MP_SOFTCAP_MAX_RADIUS)
    r = max_radius * tanh(r / max_radius)
    return Circle(center, r)
