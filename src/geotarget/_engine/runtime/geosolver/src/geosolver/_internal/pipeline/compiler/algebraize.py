"""Algebraization helpers for KernelProblemSpec."""

from __future__ import annotations

from dataclasses import dataclass

from .schema import (
    AlgebraicConstraintSpec,
    AuxiliarySpec,
    ConstraintSpec,
    ExpressionSpec,
    KernelProblemSpec,
    UnsupportedReason,
    UnsupportedReasonCode,
)

_POLYNOMIAL_FUNCTIONS = {
    "point",
    "line",
    "circle",
    "squareddistance",
    "distancesquared",
    "dot",
    "cross",
    "collinear",
    "perpendicular",
    "parallel",
    "oncircle",
}

_NON_POLYNOMIAL_SUPPORTED_WITH_AUX = {
    "distance",
    "sqrt",
}

_ANGLE_NAMES = {"angle"}
_UNARY_ARITY = 1
_BINARY_ARITY = 2
_TERNARY_ARITY = 3


@dataclass(frozen=True)
class _AlgebraizeState:
    expression_id: str
    aux_prefix: str
    aux_index: int = 0

    def next_aux(self, relation: str, expression: ExpressionSpec) -> tuple["_AlgebraizeState", AuxiliarySpec]:
        name = f"{self.aux_prefix}_{self.aux_index}"
        next_state = _AlgebraizeState(
            expression_id=self.expression_id,
            aux_prefix=self.aux_prefix,
            aux_index=self.aux_index + 1,
        )
        return next_state, AuxiliarySpec(name=name, relation=relation, expression=expression)


def _call_op(expr: ExpressionSpec) -> str:
    return expr.op.lower()


def _squared_distance(args: tuple[ExpressionSpec, ...]) -> ExpressionSpec:
    return ExpressionSpec(op="squared_distance", args=args)


def _angle_equal(left: ExpressionSpec, right: ExpressionSpec) -> ExpressionSpec | None:
    if _call_op(left) in _ANGLE_NAMES and _call_op(right) in _ANGLE_NAMES:
        return ExpressionSpec(op="angle_equal_reduced", args=(left, right))
    return None


def _literal_number(expr: ExpressionSpec) -> float | int | None:
    if expr.op != "literal" or isinstance(expr.value, bool):
        return None
    if isinstance(expr.value, (int, float)):
        return expr.value
    return None


def _is_nonzero_literal_number(expr: ExpressionSpec) -> bool:
    value = _literal_number(expr)
    return value is not None and value != 0


def _is_non_negative_integer_literal(expr: ExpressionSpec) -> bool:
    value = _literal_number(expr)
    if isinstance(value, int):
        return value >= 0
    if isinstance(value, float):
        return value >= 0.0 and value.is_integer()
    return False


def _append_non_polynomial(
    unsupported: list[UnsupportedReason],
    *,
    expression_id: str,
    detail: str,
) -> None:
    unsupported.append(
        UnsupportedReason(
            code=UnsupportedReasonCode.NON_POLYNOMIAL_FUNCTION,
            expression_id=expression_id,
            detail=detail,
        )
    )


def _algebraize_node(
    expr: ExpressionSpec,
    *,
    state: _AlgebraizeState,
    unsupported: list[UnsupportedReason],
) -> tuple[ExpressionSpec, tuple[AuxiliarySpec, ...], _AlgebraizeState]:
    raw_op = _call_op(expr)
    if raw_op == "eq" and len(expr.args) == _BINARY_ARITY:
        angle_rewrite = _angle_equal(expr.args[0], expr.args[1])
        if angle_rewrite is not None:
            return angle_rewrite, (), state

    args: list[ExpressionSpec] = []
    aux: list[AuxiliarySpec] = []
    next_state = state
    for child in expr.args:
        child_expr, child_aux, child_state = _algebraize_node(
            child,
            state=next_state,
            unsupported=unsupported,
        )
        args.append(child_expr)
        aux.extend(child_aux)
        next_state = child_state

    op = _call_op(expr)
    args_tuple = tuple(args)
    rewritten = ExpressionSpec(op=expr.op, args=args_tuple, value=expr.value)

    if op == "distance" and len(args_tuple) == _BINARY_ARITY:
        squared = _squared_distance(args_tuple)
        next_state, aux_spec = next_state.next_aux("sqrt", squared)
        aux.append(aux_spec)
        return ExpressionSpec(op="sqrt_aux", args=(squared,), value=aux_spec.name), tuple(aux), next_state

    if op in {"squareddistance", "distancesquared"} and len(args_tuple) == _BINARY_ARITY:
        return _squared_distance(args_tuple), tuple(aux), next_state

    if op == "sqrt" and len(args_tuple) == _UNARY_ARITY:
        next_state, aux_spec = next_state.next_aux("sqrt", args_tuple[0])
        aux.append(aux_spec)
        return ExpressionSpec(op="sqrt_aux", args=args_tuple, value=aux_spec.name), tuple(aux), next_state

    if op == "collinear" and len(args_tuple) == _TERNARY_ARITY:
        return ExpressionSpec(op="collinear_det", args=args_tuple), tuple(aux), next_state

    if op == "perpendicular" and len(args_tuple) == _BINARY_ARITY:
        return ExpressionSpec(op="perpendicular_dot", args=args_tuple), tuple(aux), next_state

    if op == "parallel" and len(args_tuple) == _BINARY_ARITY:
        return ExpressionSpec(op="parallel_cross", args=args_tuple), tuple(aux), next_state

    if op == "oncircle" and len(args_tuple) == _BINARY_ARITY:
        return ExpressionSpec(op="circle_membership", args=args_tuple), tuple(aux), next_state

    if op == "eq" and len(args_tuple) == _BINARY_ARITY:
        angle_rewrite = _angle_equal(args_tuple[0], args_tuple[1])
        if angle_rewrite is not None:
            return angle_rewrite, tuple(aux), next_state
        return rewritten, tuple(aux), next_state

    if op == "div" and len(args_tuple) == _BINARY_ARITY:
        if not _is_nonzero_literal_number(args_tuple[1]):
            _append_non_polynomial(
                unsupported,
                expression_id=state.expression_id,
                detail="division is polynomial only for non-zero literal denominators",
            )
        return rewritten, tuple(aux), next_state

    if op == "pow" and len(args_tuple) == _BINARY_ARITY:
        if not _is_non_negative_integer_literal(args_tuple[1]):
            _append_non_polynomial(
                unsupported,
                expression_id=state.expression_id,
                detail="power is polynomial only for non-negative integer literal exponents",
            )
        return rewritten, tuple(aux), next_state

    if op in _ANGLE_NAMES:
        unsupported.append(
            UnsupportedReason(
                code=UnsupportedReasonCode.ANGLE_NOT_REDUCIBLE,
                expression_id=state.expression_id,
                detail="Angle is only reduced for direct equality in this slice",
            )
        )
        return rewritten, tuple(aux), next_state

    if expr.args and op not in _POLYNOMIAL_FUNCTIONS and op not in _NON_POLYNOMIAL_SUPPORTED_WITH_AUX:
        allowed_operator = op in {
            "add",
            "sub",
            "mul",
            "neg",
            "pos",
            "eq",
            "ne",
            "lt",
            "le",
            "gt",
            "ge",
            "tuple",
            "list",
        }
        if not allowed_operator:
            unsupported.append(
                UnsupportedReason(
                    code=UnsupportedReasonCode.NON_POLYNOMIAL_FUNCTION,
                    expression_id=state.expression_id,
                    detail=f"{expr.op} is not algebraized in this slice",
                )
            )
    return rewritten, tuple(aux), next_state


def algebraize_expression(
    expression: ExpressionSpec,
    *,
    expression_id: str = "expr",
) -> tuple[ExpressionSpec, tuple[AuxiliarySpec, ...], tuple[UnsupportedReason, ...]]:
    unsupported: list[UnsupportedReason] = []
    algebraic, auxiliary, _ = _algebraize_node(
        expression,
        state=_AlgebraizeState(expression_id=expression_id, aux_prefix=f"{expression_id}_aux"),
        unsupported=unsupported,
    )
    return algebraic, auxiliary, tuple(unsupported)


def _constraint_residual(constraint: ConstraintSpec) -> ExpressionSpec:
    return ExpressionSpec(op="sub", args=(constraint.expression, constraint.target))


def algebraize_kernel_problem(problem: KernelProblemSpec) -> KernelProblemSpec:
    algebraic_constraints: list[AlgebraicConstraintSpec] = []
    unsupported_reasons = list(problem.unsupported_reasons)
    for constraint in problem.constraints:
        residual = _constraint_residual(constraint)
        expression, aux, unsupported = algebraize_expression(
            residual,
            expression_id=constraint.constraint_id,
        )
        unsupported_reasons.extend(unsupported)
        algebraic_constraints.append(
            AlgebraicConstraintSpec(
                constraint_id=constraint.constraint_id,
                expression=expression,
                auxiliary_variables=aux,
                exact=not unsupported,
            )
        )
    return problem.with_algebraization(
        algebraic_constraints=tuple(algebraic_constraints),
        unsupported_reasons=tuple(unsupported_reasons),
    )
