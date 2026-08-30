"""Generic and named triangle center operations."""

from typing import Any

from geosolver.geometry.entities.base import Point
from geosolver.geometry.operations.triangle_centers_core import (
    TriangleCenter,
    _TriangleCenter_mpmath,
    _TriangleCenter_numpy,
)
from geosolver.geometry.registry import geometry_symbol


@geometry_symbol("NinePointCenter", category="triangle")
def NinePointCenter(A: Point, B: Point, C: Point) -> Point | None:
    """9-Point Center (X5)."""
    return TriangleCenter(A, B, C, 5)


@NinePointCenter.set_numpy
def _NinePointCenter_numpy(A: Any, B: Any, C: Any):
    return _TriangleCenter_numpy(A, B, C, 5)


@NinePointCenter.set_mpmath
def _NinePointCenter_mpmath(A: Any, B: Any, C: Any):
    return _TriangleCenter_mpmath(A, B, C, 5)


@geometry_symbol("SymmedianPoint", category="triangle")
def SymmedianPoint(A: Point, B: Point, C: Point) -> Point | None:
    """Symmedian Point (Lemoine Point, X6)."""
    return TriangleCenter(A, B, C, 6)


@SymmedianPoint.set_numpy
def _SymmedianPoint_numpy(A: Any, B: Any, C: Any):
    return _TriangleCenter_numpy(A, B, C, 6)


@SymmedianPoint.set_mpmath
def _SymmedianPoint_mpmath(A: Any, B: Any, C: Any):
    return _TriangleCenter_mpmath(A, B, C, 6)


@geometry_symbol("GergonnePoint", category="triangle")
def GergonnePoint(A: Point, B: Point, C: Point) -> Point | None:
    """Gergonne Point (X7)."""
    return TriangleCenter(A, B, C, 7)


@GergonnePoint.set_numpy
def _GergonnePoint_numpy(A: Any, B: Any, C: Any):
    return _TriangleCenter_numpy(A, B, C, 7)


@GergonnePoint.set_mpmath
def _GergonnePoint_mpmath(A: Any, B: Any, C: Any):
    return _TriangleCenter_mpmath(A, B, C, 7)


@geometry_symbol("NagelPoint", category="triangle")
def NagelPoint(A: Point, B: Point, C: Point) -> Point | None:
    """Nagel Point (X8)."""
    return TriangleCenter(A, B, C, 8)


@NagelPoint.set_numpy
def _NagelPoint_numpy(A: Any, B: Any, C: Any):
    return _TriangleCenter_numpy(A, B, C, 8)


@NagelPoint.set_mpmath
def _NagelPoint_mpmath(A: Any, B: Any, C: Any):
    return _TriangleCenter_mpmath(A, B, C, 8)


@geometry_symbol("Mittenpunkt", category="triangle")
def Mittenpunkt(A: Point, B: Point, C: Point) -> Point | None:
    """Mittenpunkt (X9)."""
    return TriangleCenter(A, B, C, 9)


@Mittenpunkt.set_numpy
def _Mittenpunkt_numpy(A: Any, B: Any, C: Any):
    return _TriangleCenter_numpy(A, B, C, 9)


@Mittenpunkt.set_mpmath
def _Mittenpunkt_mpmath(A: Any, B: Any, C: Any):
    return _TriangleCenter_mpmath(A, B, C, 9)


@geometry_symbol("SpiekerCenter", category="triangle")
def SpiekerCenter(A: Point, B: Point, C: Point) -> Point | None:
    """Spieker Center (X10)."""
    return TriangleCenter(A, B, C, 10)


@SpiekerCenter.set_numpy
def _SpiekerCenter_numpy(A: Any, B: Any, C: Any):
    return _TriangleCenter_numpy(A, B, C, 10)


@SpiekerCenter.set_mpmath
def _SpiekerCenter_mpmath(A: Any, B: Any, C: Any):
    return _TriangleCenter_mpmath(A, B, C, 10)


@geometry_symbol("FeuerbachPoint", category="triangle")
def FeuerbachPoint(A: Point, B: Point, C: Point) -> Point | None:
    """Feuerbach Point (X11)."""
    return TriangleCenter(A, B, C, 11)


@FeuerbachPoint.set_numpy
def _FeuerbachPoint_numpy(A: Any, B: Any, C: Any):
    return _TriangleCenter_numpy(A, B, C, 11)


@FeuerbachPoint.set_mpmath
def _FeuerbachPoint_mpmath(A: Any, B: Any, C: Any):
    return _TriangleCenter_mpmath(A, B, C, 11)


@geometry_symbol("FermatPoint", category="triangle")
def FermatPoint(A: Point, B: Point, C: Point, first: bool = True) -> Point | None:
    """Fermat Point (X13/X14)."""
    return TriangleCenter(A, B, C, 13 if first else 14)


@FermatPoint.set_numpy
def _FermatPoint_numpy(A: Any, B: Any, C: Any, first: bool = True):
    return _TriangleCenter_numpy(A, B, C, 13 if first else 14)


@FermatPoint.set_mpmath
def _FermatPoint_mpmath(A: Any, B: Any, C: Any, first: bool = True):
    return _TriangleCenter_mpmath(A, B, C, 13 if first else 14)


@geometry_symbol("IsodynamicPoint", category="triangle")
def IsodynamicPoint(A: Point, B: Point, C: Point, first: bool = True) -> Point | None:
    """Isodynamic Point (X15/X16)."""
    return TriangleCenter(A, B, C, 15 if first else 16)


@IsodynamicPoint.set_numpy
def _IsodynamicPoint_numpy(A: Any, B: Any, C: Any, first: bool = True):
    return _TriangleCenter_numpy(A, B, C, 15 if first else 16)


@IsodynamicPoint.set_mpmath
def _IsodynamicPoint_mpmath(A: Any, B: Any, C: Any, first: bool = True):
    return _TriangleCenter_mpmath(A, B, C, 15 if first else 16)
