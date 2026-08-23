"""Delegated center-wrapper functions extracted from mp_api_geometry."""

from __future__ import annotations

from typing import Any

from .mp_impl import mp_triangle_center


def MP_SymmedianPoint(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 6)


def MP_GergonnePoint(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 7)


def MP_NagelPoint(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 8)


def MP_MittenPunkt(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 9)


def MP_SpiekerCenter(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 10)


def MP_FeuerbachPoint(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 11)


def MP_FirstFermatPoint(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 13)


def MP_SecondFermatPoint(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 14)


def MP_FirstIsodynamicPoint(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 15)


def MP_SecondIsodynamicPoint(A: Any, B: Any, C: Any) -> Any:
    return mp_triangle_center(A, B, C, 16)


def MP_FermatPoint(A: Any, B: Any, C: Any, first: bool = True) -> Any:
    if first:
        return MP_FirstFermatPoint(A, B, C)
    return MP_SecondFermatPoint(A, B, C)


def MP_IsodynamicPoint(A: Any, B: Any, C: Any, first: bool = True) -> Any:
    if first:
        return mp_triangle_center(A, B, C, 15)
    return mp_triangle_center(A, B, C, 16)
