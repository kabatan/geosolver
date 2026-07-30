"""Product-owned corrections for high-precision geometry semantics.

The frozen reference closure is intentionally immutable.  Optimized workers
install these corrections before loading the frozen high-precision pipeline so
that its geometry operations remain equivalent to the ordinary evaluator.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def polar(point: Any, circle: Any) -> Any:
    """Return the polar of ``point`` with respect to ``circle``.

    For a circle with centre ``(cx, cy)`` and radius ``r``, the polar of
    ``(px, py)`` is

    ``(px-cx)(x-cx) + (py-cy)(y-cy) = r**2``.

    The frozen MP implementation accidentally used a perpendicular normal and
    therefore returned the radial line through the centre and ``point``.
    """

    from geosolver.geometry.mp.mp_impl import MPLine

    center = circle.center
    dx = point.x - center.x
    dy = point.y - center.y
    if dx * dx + dy * dy == 0:
        raise ValueError("Point cannot be at center of circle")
    constant = -(dx * center.x + dy * center.y + circle.radius * circle.radius)
    return MPLine(dx, dy, constant)


def install() -> None:
    """Install corrected functions into the optimized MP evaluation registry."""

    runtime_source = Path(__file__).resolve().parent / "_engine/runtime/geosolver/src"
    if str(runtime_source) not in sys.path:
        sys.path.insert(0, str(runtime_source))
    from geosolver.geometry.mp import mp_api, mp_api_geometry

    mp_api_geometry.MP_Polar = polar
    mp_api.MP_Polar = polar
    mp_api.MP_API["Polar"] = polar
