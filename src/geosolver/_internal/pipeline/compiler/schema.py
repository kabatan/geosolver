"""Stable JSON-compatible kernel problem schema."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, replace
from enum import Enum

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class UnsupportedReasonCode(str, Enum):
    """Fixed reason codes for unsupported algebraization/compiler features."""

    AST_UNSUPPORTED = "AST_UNSUPPORTED"
    CALL_UNSUPPORTED = "CALL_UNSUPPORTED"
    KEYWORD_UNSUPPORTED = "KEYWORD_UNSUPPORTED"
    ATTRIBUTE_UNSUPPORTED = "ATTRIBUTE_UNSUPPORTED"
    SUBSCRIPT_UNSUPPORTED = "SUBSCRIPT_UNSUPPORTED"
    BOOLEAN_UNSUPPORTED = "BOOLEAN_UNSUPPORTED"
    COMPARISON_UNSUPPORTED = "COMPARISON_UNSUPPORTED"
    NON_POLYNOMIAL_FUNCTION = "NON_POLYNOMIAL_FUNCTION"
    ANGLE_NOT_REDUCIBLE = "ANGLE_NOT_REDUCIBLE"


@dataclass(frozen=True)
class UnsupportedReason:
    """One non-fatal reason a kernel feature cannot be used exactly."""

    code: UnsupportedReasonCode
    expression_id: str
    detail: str

    def to_data(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "expression_id": self.expression_id,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ExpressionSpec:
    """Prefix expression node.

    `op` identifies the node operation. Leaf nodes use `literal`, `symbol`, or
    `var`; function calls use normalized lower-case operation names.
    """

    op: str
    args: tuple["ExpressionSpec", ...] = ()
    value: str | int | float | bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.op, str) or not self.op.strip():
            raise ValueError("ExpressionSpec.op must be a non-empty string")
        for arg in self.args:
            if not isinstance(arg, ExpressionSpec):
                raise ValueError("ExpressionSpec.args must contain ExpressionSpec values")
        if self.op in {"literal", "symbol", "var"} and self.value is None:
            raise ValueError(f"ExpressionSpec({self.op!r}) requires value")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {"op": self.op}
        if self.value is not None:
            data["value"] = self.value
        if self.args:
            data["args"] = [arg.to_data() for arg in self.args]
        return data


@dataclass(frozen=True)
class KernelVariableSpec:
    """Scalar kernel variable with optional finite search bounds."""

    name: str
    kind: str = "scalar"
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        if not _NAME_RE.fullmatch(self.name):
            raise ValueError(f"invalid kernel variable name: {self.name!r}")
        if self.kind != "scalar":
            raise ValueError(f"unsupported kernel variable kind: {self.kind!r}")
        if self.lower is not None and not math.isfinite(float(self.lower)):
            raise ValueError(f"lower bound for {self.name!r} must be finite or None")
        if self.upper is not None and not math.isfinite(float(self.upper)):
            raise ValueError(f"upper bound for {self.name!r} must be finite or None")
        if self.lower is not None and self.upper is not None and not (self.lower < self.upper):
            raise ValueError(f"bounds for {self.name!r} must satisfy lower < upper")

    def to_data(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "lower": self.lower,
            "upper": self.upper,
        }


@dataclass(frozen=True)
class ConstraintSpec:
    """Kernel equality constraint expression."""

    constraint_id: str
    expression: ExpressionSpec
    target: ExpressionSpec = field(
        default_factory=lambda: ExpressionSpec(op="literal", value=0)
    )
    relation: str = "eq"
    raw: str | None = None

    def __post_init__(self) -> None:
        if not self.constraint_id:
            raise ValueError("ConstraintSpec.constraint_id must be non-empty")
        if self.relation != "eq":
            raise ValueError("only equality constraints are supported in this slice")

    def to_data(self) -> dict[str, object]:
        return {
            "constraint_id": self.constraint_id,
            "expression": self.expression.to_data(),
            "target": self.target.to_data(),
            "relation": self.relation,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class DiscreteConstraintSpec:
    """Discrete or finite-domain constraint placeholder."""

    constraint_id: str
    kind: str
    expression: ExpressionSpec | None = None
    values: tuple[object, ...] = ()

    def to_data(self) -> dict[str, object]:
        return {
            "constraint_id": self.constraint_id,
            "kind": self.kind,
            "expression": None if self.expression is None else self.expression.to_data(),
            "values": list(self.values),
        }


@dataclass(frozen=True)
class BranchChoiceSpec:
    """One branch choice descriptor."""

    branch_id: str
    kind: str
    source: str
    alternatives: tuple[str, ...] = ()

    def to_data(self) -> dict[str, object]:
        return {
            "branch_id": self.branch_id,
            "kind": self.kind,
            "source": self.source,
            "alternatives": list(self.alternatives),
        }


@dataclass(frozen=True)
class BranchPlanSpec:
    """Planned branch dimensions for later branch-aware solving."""

    choices: tuple[BranchChoiceSpec, ...] = ()

    def to_data(self) -> dict[str, object]:
        return {"choices": [choice.to_data() for choice in self.choices]}


@dataclass(frozen=True)
class NumericPolicySpec:
    """Numeric precision/budget policy for kernel execution."""

    precision_dps: int = 120
    residual_tolerance: str = "1e-30"
    time_budget_sec: float | None = None

    def __post_init__(self) -> None:
        if int(self.precision_dps) <= 0:
            raise ValueError("precision_dps must be positive")
        if self.time_budget_sec is not None and float(self.time_budget_sec) < 0.0:
            raise ValueError("time_budget_sec must be non-negative or None")

    def to_data(self) -> dict[str, object]:
        return {
            "precision_dps": int(self.precision_dps),
            "residual_tolerance": self.residual_tolerance,
            "time_budget_sec": self.time_budget_sec,
        }


@dataclass(frozen=True)
class CertificatePolicySpec:
    """Certification flags. All heavy certificate paths default off."""

    enable_interval_local_certification: bool = False
    enable_box_exhaustion: bool = False
    strict: bool = False

    def to_data(self) -> dict[str, object]:
        return {
            "enable_interval_local_certification": bool(
                self.enable_interval_local_certification
            ),
            "enable_box_exhaustion": bool(self.enable_box_exhaustion),
            "strict": bool(self.strict),
        }


@dataclass(frozen=True)
class AuxiliarySpec:
    """Auxiliary variable introduced by algebraization."""

    name: str
    relation: str
    expression: ExpressionSpec

    def to_data(self) -> dict[str, object]:
        return {
            "name": self.name,
            "relation": self.relation,
            "expression": self.expression.to_data(),
        }


@dataclass(frozen=True)
class AlgebraicConstraintSpec:
    """Algebraized constraint plus auxiliary sqrt/polynomialization state."""

    constraint_id: str
    expression: ExpressionSpec
    auxiliary_variables: tuple[AuxiliarySpec, ...] = ()
    exact: bool = True

    def to_data(self) -> dict[str, object]:
        return {
            "constraint_id": self.constraint_id,
            "expression": self.expression.to_data(),
            "auxiliary_variables": [aux.to_data() for aux in self.auxiliary_variables],
            "exact": bool(self.exact),
        }


@dataclass(frozen=True)
class KernelProblemSpec:
    """Stable kernel problem description shared by Python and Julia adapters."""

    schema_version: int
    problem_id: str | None
    task: str
    variables: tuple[KernelVariableSpec, ...]
    constructions: tuple[ConstraintSpec, ...]
    constraints: tuple[ConstraintSpec, ...]
    discrete_constraints: tuple[DiscreteConstraintSpec, ...] = ()
    branch_plan: BranchPlanSpec = field(default_factory=BranchPlanSpec)
    numeric_policy: NumericPolicySpec = field(default_factory=NumericPolicySpec)
    certificate_policy: CertificatePolicySpec = field(default_factory=CertificatePolicySpec)
    algebraic_constraints: tuple[AlgebraicConstraintSpec, ...] = ()
    unsupported_reasons: tuple[UnsupportedReason, ...] = ()
    stable_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")
        if self.task not in {"solve", "optimize"}:
            raise ValueError(f"unsupported task: {self.task!r}")
        names = [variable.name for variable in self.variables]
        if len(names) != len(set(names)):
            raise ValueError("kernel variable names must be unique")
        expected_hash = self.compute_stable_hash()
        if not self.stable_hash:
            object.__setattr__(self, "stable_hash", expected_hash)
        elif self.stable_hash != expected_hash:
            raise ValueError("stable_hash does not match canonical spec data")

    def to_data(self, *, include_stable_hash: bool = True) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": int(self.schema_version),
            "problem_id": self.problem_id,
            "task": self.task,
            "variables": [variable.to_data() for variable in self.variables],
            "constructions": [construction.to_data() for construction in self.constructions],
            "constraints": [constraint.to_data() for constraint in self.constraints],
            "discrete_constraints": [
                constraint.to_data() for constraint in self.discrete_constraints
            ],
            "branch_plan": self.branch_plan.to_data(),
            "numeric_policy": self.numeric_policy.to_data(),
            "certificate_policy": self.certificate_policy.to_data(),
            "algebraic_constraints": [
                constraint.to_data() for constraint in self.algebraic_constraints
            ],
            "unsupported_reasons": [reason.to_data() for reason in self.unsupported_reasons],
        }
        if include_stable_hash:
            data["stable_hash"] = self.stable_hash
        return data

    def compute_stable_hash(self) -> str:
        encoded = json.dumps(
            self.to_data(include_stable_hash=False),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def with_algebraization(
        self,
        *,
        algebraic_constraints: tuple[AlgebraicConstraintSpec, ...],
        unsupported_reasons: tuple[UnsupportedReason, ...],
    ) -> "KernelProblemSpec":
        return replace(
            self,
            algebraic_constraints=algebraic_constraints,
            unsupported_reasons=unsupported_reasons,
            stable_hash="",
        )


def literal_expression(value: object) -> ExpressionSpec:
    if isinstance(value, bool):
        return ExpressionSpec(op="literal", value=bool(value))
    if isinstance(value, int):
        return ExpressionSpec(op="literal", value=int(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("literal float must be finite")
        return ExpressionSpec(op="literal", value=float(value))
    if isinstance(value, str):
        stripped = value.strip()
        try:
            parsed = float(stripped)
        except ValueError:
            return ExpressionSpec(op="symbol", value=stripped)
        if not math.isfinite(parsed):
            raise ValueError("literal string float must be finite")
        return ExpressionSpec(op="literal", value=parsed)
    raise ValueError(f"unsupported literal value: {value!r}")
