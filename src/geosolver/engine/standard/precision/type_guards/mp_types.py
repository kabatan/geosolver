"""Type aliases for high-precision numeric guards."""

from mpmath import mpf

type MPFloat = mpf
type NumericInput = mpf | str | int
