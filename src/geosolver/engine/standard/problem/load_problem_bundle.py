"""Load IR payload into an immutable problem bundle."""

from __future__ import annotations

from collections.abc import Mapping

from geosolver.engine.standard.interpreter.execution.interpreter_helpers import (
    _build_base_context,
    _load_spec,
    _prepare_targets,
)

from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.problem.compile_problem_hard_feasibility import (
    compile_problem_hard_feasibility,
)


def _extract_problem_id(problem_ir: object) -> str | None:
    if not isinstance(problem_ir, Mapping):
        return None
    value = problem_ir.get("id")
    if isinstance(value, str) and value.strip():
        return value
    return None


def load_problem_bundle(
    problem_ir: object,
    *,
    prefer_fast: bool = False,
) -> ProblemBundle:
    """Create a ProblemBundle from an IR payload."""
    spec = _load_spec(problem_ir)
    var_names = tuple(spec.variables.resolved_names())
    targets = tuple(_prepare_targets(spec))
    base_context = dict(_build_base_context(prefer_fast=prefer_fast))
    hard_feasibility_checks = compile_problem_hard_feasibility(spec)
    return ProblemBundle(
        spec=spec,
        var_names=var_names,
        targets=targets,
        base_context=base_context,
        problem_id=_extract_problem_id(problem_ir),
        hard_feasibility_checks=hard_feasibility_checks,
    )

