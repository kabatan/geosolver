"""Kernel problem compiler scaffold for external pipeline backends."""

from .algebraize import algebraize_expression, algebraize_kernel_problem
from .compile import (
    compile_expression,
    compile_kernel_problem_spec,
    compile_problem_bundle,
)
from .schema import (
    AlgebraicConstraintSpec,
    AuxiliarySpec,
    BranchChoiceSpec,
    BranchPlanSpec,
    CertificatePolicySpec,
    ConstraintSpec,
    DiscreteConstraintSpec,
    ExpressionSpec,
    KernelProblemSpec,
    KernelVariableSpec,
    NumericPolicySpec,
    UnsupportedReason,
    UnsupportedReasonCode,
)

__all__ = [
    "AlgebraicConstraintSpec",
    "AuxiliarySpec",
    "BranchChoiceSpec",
    "BranchPlanSpec",
    "CertificatePolicySpec",
    "ConstraintSpec",
    "DiscreteConstraintSpec",
    "ExpressionSpec",
    "KernelProblemSpec",
    "KernelVariableSpec",
    "NumericPolicySpec",
    "UnsupportedReason",
    "UnsupportedReasonCode",
    "algebraize_expression",
    "algebraize_kernel_problem",
    "compile_expression",
    "compile_kernel_problem_spec",
    "compile_problem_bundle",
]
