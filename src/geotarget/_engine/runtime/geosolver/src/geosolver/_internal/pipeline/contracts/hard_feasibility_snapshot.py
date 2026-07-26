"""Runtime snapshot of hard-feasibility evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


@dataclass(frozen=True)
class HardFeasibilitySnapshot:
    """Evaluation result for hard-feasibility checks."""

    hard_feasible: bool
    failure_tags: tuple[str, ...]
    min_margin: MPFloat | None
