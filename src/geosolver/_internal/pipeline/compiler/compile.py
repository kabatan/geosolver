"""ProblemBundle -> KernelProblemSpec compiler."""

from __future__ import annotations

from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle

from .algebraize import algebraize_kernel_problem
from .expression import compile_expression, compile_value_expression
from .schema import (
    BranchChoiceSpec,
    BranchPlanSpec,
    CertificatePolicySpec,
    ConstraintSpec,
    KernelProblemSpec,
    KernelVariableSpec,
    NumericPolicySpec,
    UnsupportedReason,
)

_KERNEL_SCHEMA_VERSION = 1


def _compile_variables(bundle: ProblemBundle) -> tuple[KernelVariableSpec, ...]:
    bounds = bundle.spec.bounds or []
    variables: list[KernelVariableSpec] = []
    for index, name in enumerate(bundle.var_names):
        lower = None
        upper = None
        if index < len(bounds) and bounds[index] is not None:
            lower, upper = bounds[index]  # type: ignore[misc]
        variables.append(
            KernelVariableSpec(
                name=name,
                lower=None if lower is None else float(lower),
                upper=None if upper is None else float(upper),
            )
        )
    return tuple(variables)


def _compile_constructions(
    bundle: ProblemBundle,
) -> tuple[tuple[ConstraintSpec, ...], tuple[UnsupportedReason, ...]]:
    variable_names = set(bundle.var_names)
    constructions: list[ConstraintSpec] = []
    unsupported: list[UnsupportedReason] = []
    for index, construction in enumerate(bundle.spec.construction):
        expression_id = f"construction:{construction.name}"
        expression, reasons = compile_expression(
            construction.expr,
            variables=variable_names,
            expression_id=expression_id,
        )
        unsupported.extend(reasons)
        constructions.append(
            ConstraintSpec(
                constraint_id=expression_id,
                expression=expression,
                raw=construction.expr,
            )
        )
    return tuple(constructions), tuple(unsupported)


def _compile_constraints(
    bundle: ProblemBundle,
) -> tuple[tuple[ConstraintSpec, ...], tuple[UnsupportedReason, ...]]:
    variable_names = set(bundle.var_names)
    constraints: list[ConstraintSpec] = []
    unsupported: list[UnsupportedReason] = []
    for index, expression_text in enumerate(bundle.spec.constraints):
        expression_id = f"constraint:{index}"
        expression, expression_reasons = compile_expression(
            expression_text,
            variables=variable_names,
            expression_id=expression_id,
        )
        target_value = bundle.targets[index] if index < len(bundle.targets) else 0
        target, target_reasons = compile_value_expression(
            target_value,
            variables=variable_names,
            expression_id=f"{expression_id}:target",
        )
        unsupported.extend(expression_reasons)
        unsupported.extend(target_reasons)
        constraints.append(
            ConstraintSpec(
                constraint_id=expression_id,
                expression=expression,
                target=target,
                raw=expression_text,
            )
        )
    return tuple(constraints), tuple(unsupported)


def _compile_branch_plan(bundle: ProblemBundle) -> BranchPlanSpec:
    choices: list[BranchChoiceSpec] = []
    for index, guard in enumerate(bundle.spec.guards):
        lowered = guard.lower()
        if "abs(" in lowered:
            kind = "abs_equality"
            alternatives = ("positive", "negative")
        elif "area" in lowered or "orientation" in lowered:
            kind = "area_sign"
            alternatives = ("positive", "negative", "zero")
        else:
            kind = "guard"
            alternatives = ()
        choices.append(
            BranchChoiceSpec(
                branch_id=f"guard:{index}",
                kind=kind,
                source=guard,
                alternatives=alternatives,
            )
        )
    return BranchPlanSpec(choices=tuple(choices))


def compile_kernel_problem_spec(
    bundle: ProblemBundle,
    *,
    numeric_policy: NumericPolicySpec | None = None,
    certificate_policy: CertificatePolicySpec | None = None,
    algebraize: bool = True,
) -> KernelProblemSpec:
    """Compile a loaded ProblemBundle into a stable KernelProblemSpec."""

    variables = _compile_variables(bundle)
    constructions, construction_reasons = _compile_constructions(bundle)
    constraints, constraint_reasons = _compile_constraints(bundle)
    problem = KernelProblemSpec(
        schema_version=_KERNEL_SCHEMA_VERSION,
        problem_id=bundle.problem_id,
        task=bundle.spec.task,
        variables=variables,
        constructions=constructions,
        constraints=constraints,
        branch_plan=_compile_branch_plan(bundle),
        numeric_policy=NumericPolicySpec() if numeric_policy is None else numeric_policy,
        certificate_policy=(
            CertificatePolicySpec() if certificate_policy is None else certificate_policy
        ),
        unsupported_reasons=tuple(construction_reasons + constraint_reasons),
    )
    if not algebraize:
        return problem
    return algebraize_kernel_problem(problem)


compile_problem_bundle = compile_kernel_problem_spec
