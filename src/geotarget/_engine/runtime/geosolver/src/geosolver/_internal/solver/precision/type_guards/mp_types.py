"""Type aliases for high-precision numeric guards."""

from typing import TypeAlias, Union
from mpmath import mpf

MPFloat: TypeAlias = mpf
NumericInput: TypeAlias = Union[mpf, str, int]
