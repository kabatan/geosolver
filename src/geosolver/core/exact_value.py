"""Exact answer wrapper utilities."""

from __future__ import annotations

from typing import Any


class ExactValue(str):
    """Exact answer wrapper that behaves like a numeric value for post-process code."""

    def __new__(cls, value: str, numeric_override: Any = None) -> "ExactValue":
        obj = super().__new__(cls, str(value))
        obj._numeric_cache = None
        obj._numeric_override = numeric_override
        return obj

    def _to_numeric(self) -> Any:
        if getattr(self, "_numeric_override", None) is not None:
            try:
                return float(self._numeric_override)
            except Exception:
                return self._numeric_override
        if getattr(self, "_numeric_cache", None) is not None:
            return self._numeric_cache

        try:
            from fractions import Fraction

            value = str(self).strip()
            if "/" in value and all(char not in value for char in "()"):
                fraction = Fraction(value)
                self._numeric_cache = float(fraction)
                return self._numeric_cache
        except Exception:
            pass

        try:
            import sympy as _sympy  # type: ignore

            expr = _sympy.sympify(str(self), evaluate=True)
            value = float(expr.evalf(50))
            self._numeric_cache = value
            return value
        except Exception:
            pass

        try:
            value = float(str(self))
        except Exception:
            value = float("nan")
        self._numeric_cache = value
        return value

    def __float__(self) -> float:
        return float(self._to_numeric())

    def __int__(self) -> int:
        return int(round(float(self)))

    def __round__(self, ndigits: int | None = None) -> float | int:
        if ndigits is None:
            return round(float(self))
        return round(float(self), ndigits)

    def __pow__(self, power: Any, modulo: Any = None) -> Any:
        if modulo is None:
            return float(self) ** power
        return pow(float(self), power, modulo)

    def __rpow__(self, other: Any) -> Any:
        return other ** float(self)

    def __add__(self, other: Any) -> Any:
        return float(self) + other

    def __radd__(self, other: Any) -> Any:
        return other + float(self)

    def __sub__(self, other: Any) -> Any:
        return float(self) - other

    def __rsub__(self, other: Any) -> Any:
        return other - float(self)

    def __mul__(self, other: Any) -> Any:
        return float(self) * other

    def __rmul__(self, other: Any) -> Any:
        return other * float(self)

    def __truediv__(self, other: Any) -> Any:
        return float(self) / other

    def __rtruediv__(self, other: Any) -> Any:
        return other / float(self)