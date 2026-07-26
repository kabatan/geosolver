"""Conversion helper for mapping mp-like sequences to float."""

from typing import Sequence


def mp_list_to_float(values: Sequence[object]) -> list[float]:
    """Convert numeric sequence to float list.

    Values that overflow are saturated to ``±inf``.
    """
    converted: list[float] = []
    for entry in values:
        try:
            converted.append(float(entry))
        except (ValueError, OverflowError):
            converted.append(float("inf") if entry > 0 else float("-inf"))
    return converted
