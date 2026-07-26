"""Check stability of solution family set between iterations."""

from __future__ import annotations

from mpmath import mp

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver._internal.solver.families.solution_family import SolutionFamily


def check_family_set_stability(
    *,
    current: list[SolutionFamily],
    previous: list[SolutionFamily],
    tolerance: MPFloat | None = None,
) -> bool:
    """Check whether solution family set is stable.

    Stable means the same number of families with matching answer
    values (within tolerance).

    Args:
        current: Current iteration families.
        previous: Previous iteration families.
        tolerance: Answer value matching tolerance.

    Returns:
        True if family set is stable.
    """
    if tolerance is None:
        tolerance = mp.mpf("1e-6")

    if len(current) != len(previous):
        return False

    current_answers = sorted([f.answer_cluster for f in current])
    previous_answers = sorted([f.answer_cluster for f in previous])

    for curr, prev in zip(current_answers, previous_answers):
        if abs(curr - prev) > tolerance:
            return False

    return True
