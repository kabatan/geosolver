"""Classify evaluator outputs into structured statuses."""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum

from mpmath import mp


class EvaluationStatus(str, Enum):
    """Normalized evaluation status."""

    OK = "ok"
    NON_FINITE = "non_finite"
    EVALUATION_FAILED = "evaluation_failed"


def _is_finite(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    try:
        return bool(mp.isfinite(value))
    except Exception:
        return False


def classify_evaluation_failure(values: Sequence[object]) -> EvaluationStatus:
    """Classify an evaluated vector."""
    if not values:
        return EvaluationStatus.OK
    for value in values:
        if not _is_finite(value):
            return EvaluationStatus.NON_FINITE
    return EvaluationStatus.OK
