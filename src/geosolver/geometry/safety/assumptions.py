"""Geometry-oriented assume helpers extracted from safety module."""

from __future__ import annotations

from typing import Any, Optional

from geosolver.geometry.safety.guards import (
    assume_acute,
    assume_convex,
    assume_no_self_intersecting,
    assume_obtuse,
    assume_order,
    assume_right,
)


def AssumeAcute(
    A: Any,
    B: Any,
    C: Any,
    message: Optional[str] = None,
    *,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> None:
    from geosolver.geometry import safety as _s

    assume_acute(
        A=A,
        B=B,
        C=C,
        message=message,
        tol=_s._get_tolerance(1.0, rel_floor, abs_floor),
        assume_enabled=_s._ASSUME_ENABLED.get(),
        handle_failure=_s._handle_failure,
        to_point_xy=_s._to_point_xy,
    )


def AssumeRight(
    A: Any,
    B: Any,
    C: Any,
    message: Optional[str] = None,
    *,
    tol: Optional[float] = None,
) -> None:
    from geosolver.geometry import safety as _s

    effective_tol = (
        _s._get_tolerance(1.0, None, None) if tol is None else tol
    )
    assume_right(
        A=A,
        B=B,
        C=C,
        message=message,
        tol=effective_tol,
        assume_enabled=_s._ASSUME_ENABLED.get(),
        handle_failure=_s._handle_failure,
        to_point_xy=_s._to_point_xy,
        to_float=_s._to_float,
    )


def AssumeObtuse(
    A: Any,
    B: Any,
    C: Any,
    message: Optional[str] = None,
    *,
    tol: Optional[float] = None,
) -> None:
    from geosolver.geometry import safety as _s

    effective_tol = (
        _s._get_tolerance(1.0, None, None) if tol is None else tol
    )
    assume_obtuse(
        A=A,
        B=B,
        C=C,
        message=message,
        tol=effective_tol,
        assume_enabled=_s._ASSUME_ENABLED.get(),
        handle_failure=_s._handle_failure,
        to_point_xy=_s._to_point_xy,
        to_float=_s._to_float,
    )


def AssumeConvex(
    polygon: Any,
    message: Optional[str] = None,
    *,
    tol: float = 1e-6,
) -> None:
    from geosolver.geometry import safety as _s

    assume_convex(
        polygon=polygon,
        message=message,
        assume_enabled=_s._ASSUME_ENABLED.get(),
        handle_failure=_s._handle_failure,
        to_point_xy=_s._to_point_xy,
    )


def AssumeNoSelfIntersecting(
    polygon: Any,
    message: Optional[str] = None,
    *,
    tol: float = 1e-6,
) -> None:
    from geosolver.geometry import safety as _s

    assume_no_self_intersecting(
        polygon=polygon,
        message=message,
        assume_enabled=_s._ASSUME_ENABLED.get(),
        handle_failure=_s._handle_failure,
        to_point_xy=_s._to_point_xy,
    )


def AssumeOrder(
    P1: Any,
    P2: Any,
    P3: Any,
    message: Optional[str] = None,
    *,
    tol: float = 1e-6,
) -> None:
    from geosolver.geometry import safety as _s

    assume_order(
        P1=P1,
        P2=P2,
        P3=P3,
        message=message,
        tol=tol,
        assume_enabled=_s._ASSUME_ENABLED.get(),
        handle_failure=_s._handle_failure,
        to_float=_s._to_float,
    )
