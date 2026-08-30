"""Contract type for immutable problem bundle."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver.engine.standard.contracts.hard_feasibility_check import HardFeasibilityCheck
from geosolver.problem.ir.schema import IRSpec


@dataclass(frozen=True)
class ProblemBundle:
    """Immutable data required to evaluate one problem IR."""

    spec: IRSpec
    var_names: tuple[str, ...]
    targets: tuple[object, ...]
    base_context: dict[str, object]
    problem_id: str | None
    hard_feasibility_checks: tuple[HardFeasibilityCheck, ...] = ()
