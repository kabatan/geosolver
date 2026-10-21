"""
Arc-related entities extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import mp, mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPCircle, MPPoint


class MPExcludedPointError(Exception):
    pass


class MPArc:
    __slots__ = ["circle", "start", "end", "including", "excluding"]

    def __init__(
        self,
        circle: MPCircle,
        start: MPPoint,
        end: MPPoint,
        including: MPPoint | None = None,
        excluding: MPPoint | None = None,
    ):
        from geosolver.geometry.arc_parameters import arc_parameters

        arc_parameters(circle, start, end, including, excluding)
        self.circle = circle
        self.start = start
        self.end = end
        self.including = including
        self.excluding = excluding

    def __repr__(self):
        return f"MPArc(circle={self.circle}, start={self.start}, end={self.end})"


def mp_arc(
    circle: MPCircle,
    start: MPPoint,
    end: MPPoint,
    including: MPPoint | None = None,
    excluding: MPPoint | None = None,
) -> MPArc:
    return MPArc(circle, start, end, including, excluding)


def mp_check_excluded_points(point: MPPoint, exclude, tol=None):
    if exclude is None:
        return

    if tol is None:
        tol = mpf(10) ** (-(mp.dps - 5))

    exclude_list = exclude if isinstance(exclude, list | tuple) else [exclude]
    for excluded_pt in exclude_list:
        if excluded_pt is None:
            continue
        dist = point.distance_to(excluded_pt)
        if dist < tol:
            raise MPExcludedPointError("Generated point is too close to an excluded point.")
