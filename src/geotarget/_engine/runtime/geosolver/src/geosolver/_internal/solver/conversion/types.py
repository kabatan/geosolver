"""Type definitions for numeric conversion utilities."""

from typing import Protocol, Union
from mpmath import mpf


class EvalfLike(Protocol):
    """Protocol for objects that support SymPy-style evalf."""

    def evalf(self, n: int):
        """Evaluate numerically with n digits of precision."""


NumericValue = Union[mpf, int, float, str, EvalfLike]
