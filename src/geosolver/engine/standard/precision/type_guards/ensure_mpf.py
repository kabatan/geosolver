"""Conversion guards that prevent float contamination in mpmath workflows."""

from mpmath import mp, mpf
from .high_precision_contamination_error import HighPrecisionContaminationError
from .mp_types import NumericInput

try:
    import numpy as np

    _NUMPY_FLOATING_TYPES: tuple[type, ...] = (np.floating,)
except Exception:  # pragma: no cover
    _NUMPY_FLOATING_TYPES = ()


def ensure_mpf(value: NumericInput, *, context: str = "") -> mpf:
    """Convert value to ``mpf`` while rejecting Python ``float`` inputs."""
    if isinstance(value, float) or (
        _NUMPY_FLOATING_TYPES and isinstance(value, _NUMPY_FLOATING_TYPES)
    ):
        message = "float型が高精度計算に混入しました"
        if context:
            message += f" (context: {context})"
        message += f". 値: {value}. mp.mpf('{value}')を使用してください。"
        raise HighPrecisionContaminationError(message)
    if isinstance(value, mpf):
        return value
    if isinstance(value, (str, int)):
        return mp.mpf(value)
    raise TypeError(
        f"mpfに変換できない型です: {type(value).__name__} = {value}. "
        "許可される入力は mpf / str / int のみです。"
    )


def ensure_mpf_list(values: list[NumericInput], *, context: str = "") -> list[mpf]:
    """Convert a list of numeric inputs to ``mpf`` values with index context."""
    return [ensure_mpf(v, context=f"{context}[{i}]") for i, v in enumerate(values)]
