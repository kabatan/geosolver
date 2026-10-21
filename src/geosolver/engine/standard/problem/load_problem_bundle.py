"""Load IR payload into an immutable problem bundle."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.interpreter.context import _get_geometry_context
from geosolver.engine.standard.problem.compile_problem_hard_feasibility import (
    compile_problem_hard_feasibility,
)
from geosolver.problem.domain_bounds import domain_guards, mathematical_bounds
from geosolver.problem.ir.errors import IRValidationError
from geosolver.problem.ir.parser import load_ir
from geosolver.problem.ir.schema import IRConstruction, IRSpec, IRVariableSpec


def _extract_problem_id(problem_ir: object) -> str | None:
    if not isinstance(problem_ir, Mapping):
        return None
    value = problem_ir.get("id")
    if isinstance(value, str) and value.strip():
        return value
    return None


def load_problem_bundle(
    problem_ir: object,
) -> ProblemBundle:
    """Create a ProblemBundle from an IR payload."""
    spec = problem_ir if isinstance(problem_ir, IRSpec) else load_ir(problem_ir)
    var_names = tuple(spec.variables.resolved_names())
    if spec.task != "solve" or spec.maximize or spec.post_process:
        raise IRValidationError("unsupported optimization or post-processing")
    names = list(var_names) + [item.name for item in spec.construction]
    if len(names) != len(set(names)):
        raise IRValidationError("duplicate variable or construction name")
    if spec.bounds is not None and len(spec.bounds) != len(var_names):
        raise IRValidationError("bounds length must equal variable count")
    targets = tuple(spec.v) if spec.v is not None else (0,) * len(spec.constraints)
    if len(targets) != len(spec.constraints):
        raise IRValidationError("v length must equal constraint count")
    if spec.m is not None and spec.m != len(spec.constraints):
        raise IRValidationError("m disagrees with constraint count")
    from geosolver.problem.construction_contracts import lower_construction_contracts
    from geosolver.problem.logical_equalities import lower_logical_equalities

    spec = lower_construction_contracts(spec)
    from geosolver.problem.incidence_residuals import lower_incidence_equalities

    spec = lower_incidence_equalities(spec)
    spec = lower_logical_equalities(spec)
    targets = tuple(spec.v) if spec.v is not None else (0,) * len(spec.constraints)
    spec = replace(spec, guards=list(dict.fromkeys([*spec.guards, *domain_guards(spec)])))
    domains = mathematical_bounds(spec)
    fixed = {name: axis.lower for name, axis in domains.items() if axis.fixed}
    if fixed:
        active = [i for i, name in enumerate(var_names) if name not in fixed]
        var_names = tuple(var_names[i] for i in active)
        spec = replace(
            spec,
            variables=IRVariableSpec(names=list(var_names)),
            bounds=None if spec.bounds is None else [spec.bounds[i] for i in active],
            construction=[IRConstruction(name, str(value)) for name, value in fixed.items()]
            + spec.construction,
        )
    base_context = dict(_get_geometry_context())
    hard_feasibility_checks = compile_problem_hard_feasibility(spec)
    return ProblemBundle(
        spec=spec,
        var_names=var_names,
        targets=targets,
        base_context=base_context,
        problem_id=_extract_problem_id(problem_ir),
        hard_feasibility_checks=hard_feasibility_checks,
    )
