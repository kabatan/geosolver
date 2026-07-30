"""Disposable local preconditioned Poincare--Miranda certificate D0."""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from typing import Mapping

import sympy as sp


T = sp.Symbol("T")
MAX_DIMENSION = 3
MAX_DEGREE = 6
MAX_FACE_COEFFICIENT_HEIGHT = 4096


@dataclass(frozen=True)
class Source:
    variables: tuple[sp.Symbol, ...]
    equations: tuple[sp.Expr, ...]
    box: Mapping[sp.Symbol, tuple[sp.Rational, sp.Rational]]
    active_indices: tuple[int, ...]
    omitted_consequences: tuple[tuple[sp.Rational, ...], ...]
    preconditioner: sp.ImmutableMatrix
    orientations: tuple[int, ...]
    guards_positive: tuple[sp.Expr, ...]
    branch_positive: tuple[sp.Expr, ...]
    defined_positive: tuple[sp.Expr, ...]
    principal_positive: tuple[sp.Expr, ...]
    cover_reversible: bool
    target_expression: sp.Expr
    target_constant: sp.Rational
    target_cofactors: tuple[sp.Rational, ...]
    target_isolator: tuple[sp.Rational, sp.Rational]
    typed_square: bool = True
    proposal_rounds: int = 1


@dataclass(frozen=True)
class Result:
    emitted: bool
    status: str
    descriptor: tuple[tuple[int, ...], int] | None
    max_face_coefficient_height: int
    det_j_interval_contains_zero: bool
    proposal_rounds: int
    subdivisions: int


def _zero(expression: sp.Expr) -> bool:
    value = sp.factor(sp.cancel(sp.together(expression)))
    return value == 0 or value.is_zero is True or value.equals(0) is True


def _coefficient_height(value: sp.Rational) -> int:
    value = sp.Rational(value)
    return max(abs(int(value.p)), int(value.q))


def _polynomial(expression, variables):
    try:
        polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    except Exception:
        return None
    if polynomial.total_degree() > MAX_DEGREE:
        return None
    return polynomial


def bernstein_range(expression, variables, box):
    if not variables:
        value = sp.Rational(sp.factor(expression))
        return value, value, _coefficient_height(value)
    unit = sp.symbols(f"u0:{len(variables)}", real=True)
    mapped = {
        variable: box[variable][0] + (box[variable][1] - box[variable][0]) * u
        for variable, u in zip(variables, unit, strict=True)
    }
    polynomial = _polynomial(sp.expand(expression.subs(mapped)), unit)
    if polynomial is None:
        raise ValueError("non-polynomial-or-degree")
    degrees = tuple(max(0, polynomial.degree(u)) for u in unit)
    powers = polynomial.as_dict()
    coefficients = []
    for beta in itertools.product(*(range(degree + 1) for degree in degrees)):
        value = sp.Rational(0)
        for alpha, coefficient in powers.items():
            if all(a <= b for a, b in zip(alpha, beta, strict=True)):
                factor = sp.Rational(1)
                for a, b, degree in zip(alpha, beta, degrees, strict=True):
                    factor *= sp.Rational(math.comb(b, a), math.comb(degree, a))
                value += coefficient * factor
        coefficients.append(sp.Rational(value))
    return min(coefficients), max(coefficients), max(map(_coefficient_height, coefficients))


def _fail(source, status, height=0, det_zero=False):
    return Result(False, status, None, height, det_zero, source.proposal_rounds, 0)


def solve(source: Source) -> Result:
    n = len(source.variables)
    if not source.typed_square or not 1 <= n <= MAX_DIMENSION:
        return _fail(source, "UNSUPPORTED_DIMENSION_OR_TYPE")
    if source.proposal_rounds != 1 or len(source.active_indices) != n:
        return _fail(source, "INVALID_PROPOSAL_CONTRACT")
    if set(source.box) != set(source.variables):
        return _fail(source, "INCOMPLETE_LOCAL_BOX")
    if any(lower >= upper for lower, upper in source.box.values()):
        return _fail(source, "EMPTY_LOCAL_BOX")
    expressions = (
        *source.equations,
        *source.guards_positive,
        *source.branch_positive,
        *source.defined_positive,
        *source.principal_positive,
        source.target_expression,
    )
    if any(_polynomial(expression, source.variables) is None for expression in expressions):
        return _fail(source, "NONCONTINUOUS_OR_UNTYPED_EXPRESSION")
    if not source.cover_reversible:
        return _fail(source, "NONREVERSIBLE_COVER")

    active = tuple(source.equations[index] for index in source.active_indices)
    omitted_indices = tuple(index for index in range(len(source.equations)) if index not in source.active_indices)
    if len(omitted_indices) != len(source.omitted_consequences):
        return _fail(source, "MISSING_OMITTED_CONSEQUENCE")
    for index, coefficients in zip(omitted_indices, source.omitted_consequences, strict=True):
        if len(coefficients) != n:
            return _fail(source, "MALFORMED_OMITTED_CONSEQUENCE")
        claimed = sum(c * f for c, f in zip(coefficients, active, strict=True))
        if not _zero(source.equations[index] - claimed):
            return _fail(source, "OMITTED_NOT_EXACT_CONSEQUENCE")

    A = sp.Matrix(source.preconditioner)
    if A.shape != (n, n) or _zero(A.det()):
        return _fail(source, "SINGULAR_PRECONDITIONER")
    G = tuple(sp.expand(value) for value in A * sp.Matrix(active))
    if len(source.orientations) != n or any(value not in (-1, 1) for value in source.orientations):
        return _fail(source, "INVALID_ORIENTATION")

    max_height = 0
    for index, (variable, expression, orientation) in enumerate(zip(source.variables, G, source.orientations, strict=True)):
        remaining = tuple(v for v in source.variables if v != variable)
        lower, upper = source.box[variable]
        low_range = bernstein_range(expression.subs(variable, lower), remaining, source.box)
        high_range = bernstein_range(expression.subs(variable, upper), remaining, source.box)
        max_height = max(max_height, low_range[2], high_range[2])
        if max_height > MAX_FACE_COEFFICIENT_HEIGHT:
            return _fail(source, "FACE_COEFFICIENT_HEIGHT", max_height)
        if orientation == 1:
            valid = low_range[1] < 0 and high_range[0] > 0
        else:
            valid = low_range[0] > 0 and high_range[1] < 0
        if not valid:
            return _fail(source, "FACE_SIGN_NOT_STRICT_OPPOSITE", max_height)

    face_height = max_height

    for expression in (
        *source.guards_positive,
        *source.branch_positive,
        *source.defined_positive,
        *source.principal_positive,
    ):
        lower, _upper, height = bernstein_range(expression, source.variables, source.box)
        max_height = max(max_height, height)
        if max_height > MAX_FACE_COEFFICIENT_HEIGHT or lower <= 0:
            return _fail(source, "SEMIALGEBRAIC_COVER_NOT_STRICT", face_height)

    if len(source.target_cofactors) != len(source.equations):
        return _fail(source, "MALFORMED_TARGET_IDENTITY", face_height)
    target_relation = source.target_expression - source.target_constant
    claimed = sum(c * f for c, f in zip(source.target_cofactors, source.equations, strict=True))
    if not _zero(target_relation - claimed):
        return _fail(source, "TARGET_IDENTITY_MUTATED", face_height)
    target_range = bernstein_range(source.target_expression, source.variables, source.box)
    max_height = max(max_height, target_range[2])
    isolator_lower, isolator_upper = source.target_isolator
    if not (isolator_lower < target_range[0] and target_range[1] < isolator_upper):
        return _fail(source, "TARGET_RANGE_NOT_STRICTLY_ISOLATED", face_height)
    target_polynomial = sp.Poly(T - source.target_constant, T, domain=sp.QQ)
    if target_polynomial.count_roots(isolator_lower, isolator_upper) != 1:
        return _fail(source, "TARGET_ISOLATOR_NOT_SINGLE_ROOT", face_height)

    det_j = sp.factor(sp.Matrix(active).jacobian(source.variables).det())
    det_range = bernstein_range(det_j, source.variables, source.box)
    det_contains_zero = bool(det_range[0] <= 0 <= det_range[1])
    coefficients = (int(source.target_constant.q), -int(source.target_constant.p))
    return Result(
        True,
        "LOCAL_PM_EXISTENCE_AND_TARGET_IDENTITY",
        (coefficients, 0),
        face_height,
        det_contains_zero,
        source.proposal_rounds,
        0,
    )


__all__ = ["Result", "Source", "T", "bernstein_range", "solve"]
