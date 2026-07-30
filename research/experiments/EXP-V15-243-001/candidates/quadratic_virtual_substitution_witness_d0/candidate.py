"""Disposable exact quadratic virtual-substitution witness D0."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import sympy as sp
from sympy.polys.polyerrors import PolynomialError


@dataclass(frozen=True)
class Source:
    variables: tuple[sp.Symbol, ...]
    equations: tuple[sp.Expr, ...]
    guards: tuple[sp.Relational, ...]
    denominators: tuple[sp.Expr, ...]
    target: sp.Expr
    endpoint: Mapping[sp.Symbol, float]
    branch_cap: int = 64


@dataclass(frozen=True)
class TargetDescriptor:
    coefficients_high_to_low: tuple[int, ...]
    real_root_index: int
    approximate_value: float


@dataclass(frozen=True)
class ExactConfiguration:
    values: Mapping[sp.Symbol, sp.Expr]
    target_value: sp.Expr
    target_descriptor: TargetDescriptor


@dataclass(frozen=True)
class Result:
    status: str
    configurations: tuple[ExactConfiguration, ...]
    branch_states_generated: int
    exact_replay_failures: int
    endpoint_used_for_pruning: bool
    fallback_required: bool


@dataclass
class _State:
    equations: tuple[sp.Expr, ...]
    conditions: tuple[sp.Relational, ...]
    denominators: tuple[sp.Expr, ...]
    remaining: tuple[sp.Symbol, ...]
    assignments: dict[sp.Symbol, sp.Expr]


class _Unsupported(Exception):
    pass


class _BranchCap(Exception):
    pass


def _normalize_expressions(expressions: Sequence[sp.Expr]) -> tuple[sp.Expr, ...]:
    answer = []
    for expression in expressions:
        value = sp.factor(sp.cancel(expression))
        if value == 0:
            continue
        answer.append(value)
    return tuple(answer)


def _validate_source(source: Source) -> None:
    for expression in (*source.equations, *source.denominators):
        try:
            polynomial = sp.Poly(expression, *source.variables, domain=sp.QQ)
        except PolynomialError as error:
            raise _Unsupported("non-polynomial-or-non-rational-source") from error
        if any(polynomial.degree(variable) > 2 for variable in source.variables):
            raise _Unsupported("individual-degree-exceeds-two")
    for guard in source.guards:
        expression = sp.expand(guard.lhs - guard.rhs)
        try:
            polynomial = sp.Poly(expression, *source.variables, domain=sp.QQ)
        except PolynomialError as error:
            raise _Unsupported("non-polynomial-guard") from error
        if any(polynomial.degree(variable) > 2 for variable in source.variables):
            raise _Unsupported("guard-degree-exceeds-two")


def _graph(equations: Sequence[sp.Expr], remaining: Sequence[sp.Symbol]):
    graph = {variable: set() for variable in remaining}
    remaining_set = set(remaining)
    for equation in equations:
        present = tuple(equation.free_symbols & remaining_set)
        for left in present:
            graph[left].update(right for right in present if right != left)
    return graph


def _choose_pair(state: _State) -> tuple[sp.Symbol, sp.Expr]:
    graph = _graph(state.equations, state.remaining)
    pairs = []
    for variable in state.remaining:
        neighbours = graph[variable]
        missing = sum(
            right not in graph[left]
            for index, left in enumerate(neighbours)
            for right in tuple(neighbours)[index + 1 :]
        )
        candidates = []
        for equation in state.equations:
            if variable not in equation.free_symbols:
                continue
            try:
                polynomial = sp.Poly(equation, variable, domain="EX")
            except PolynomialError:
                continue
            degree = polynomial.degree()
            if 1 <= degree <= 2:
                candidates.append(
                    (
                        len(equation.free_symbols & set(state.remaining)),
                        degree,
                        sp.count_ops(equation),
                        sp.srepr(equation),
                        equation,
                    )
                )
        if candidates:
            pairs.append(
                (
                    missing,
                    len(neighbours),
                    min(item[0] for item in candidates),
                    min(item[1] for item in candidates),
                    str(variable),
                    variable,
                    min(candidates)[-1],
                )
            )
    if not pairs:
        raise _Unsupported("no-linear-or-quadratic-elimination-pair")
    selected = min(pairs)
    return selected[-2], selected[-1]


def _condition_truth(condition: sp.Relational) -> bool | None:
    simplified = sp.simplify(condition)
    if simplified is sp.true:
        return True
    if simplified is sp.false:
        return False
    if not simplified.free_symbols:
        try:
            return bool(simplified)
        except TypeError:
            return False
    return None


def _possible(conditions: Sequence[sp.Relational]) -> bool:
    return all(_condition_truth(condition) is not False for condition in conditions)


def _root_branches(expression: sp.Expr, variable: sp.Symbol):
    polynomial = sp.Poly(expression, variable, domain="EX")
    degree = polynomial.degree()
    if degree > 2:
        raise _Unsupported("degree-grew-above-two")
    if degree == 1:
        leading, constant = polynomial.all_coeffs()
        if leading == 0:
            return []
        conditions = () if leading.is_nonzero else (sp.Ne(leading, 0),)
        return [(-constant / leading, conditions)]
    if degree != 2:
        return []
    leading, linear, constant = polynomial.all_coeffs()
    discriminant = sp.factor(linear**2 - 4 * leading * constant)
    branches = []
    if leading != 0:
        leading_conditions = () if leading.is_nonzero else (sp.Ne(leading, 0),)
        denominator_condition = sp.Ne(2 * leading, 0)
        real_condition = sp.Ge(discriminant, 0)
        for sign in (-1, 1):
            root = sp.cancel((-linear + sign * sp.sqrt(discriminant)) / (2 * leading))
            branches.append(
                (root, leading_conditions + (denominator_condition, real_condition))
            )
    if leading.is_zero is not False:
        degenerate_conditions = (sp.Eq(leading, 0),)
        if linear != 0:
            if linear.is_nonzero is not True:
                degenerate_conditions += (sp.Ne(linear, 0),)
            branches.append((-constant / linear, degenerate_conditions))
    return branches


def _substitute_state(
    state: _State,
    equation: sp.Expr,
    variable: sp.Symbol,
    root: sp.Expr,
    extra_conditions: Sequence[sp.Relational],
) -> _State | None:
    substitution = {variable: root}
    equations = _normalize_expressions(
        sp.cancel(value.subs(substitution))
        for value in state.equations
        if value != equation
    )
    conditions = tuple(
        sp.simplify(value.subs(substitution))
        for value in (*state.conditions, *extra_conditions)
    )
    denominators = tuple(
        sp.factor(value.subs(substitution)) for value in state.denominators
    )
    conditions += tuple(sp.Ne(value, 0) for value in denominators)
    if not _possible(conditions):
        return None
    assignments = {
        key: sp.cancel(value.subs(substitution))
        for key, value in state.assignments.items()
    }
    assignments[variable] = root
    return _State(
        equations=equations,
        conditions=conditions,
        denominators=denominators,
        remaining=tuple(value for value in state.remaining if value != variable),
        assignments=assignments,
    )


def _descriptor(value: sp.Expr) -> TargetDescriptor:
    polynomial = sp.Poly(sp.minpoly(value, sp.Symbol("target")), sp.Symbol("target"), domain=sp.QQ).monic()
    denominator = sp.ilcm(*(term.q for term in polynomial.all_coeffs()))
    coefficients = tuple(int(term * denominator) for term in polynomial.all_coeffs())
    common = math.gcd(*(abs(term) for term in coefficients if term))
    coefficients = tuple(term // common for term in coefficients)
    if coefficients[0] < 0:
        coefficients = tuple(-term for term in coefficients)
    roots = sp.real_roots(sp.Poly.from_list(coefficients, gens=sp.Symbol("target")).as_expr())
    approximate = float(sp.N(value, 50))
    ordinal = min(
        range(len(roots)),
        key=lambda index: abs(float(sp.N(roots[index], 50)) - approximate),
    )
    return TargetDescriptor(coefficients, ordinal, approximate)


def _exact_replay(source: Source, values: Mapping[sp.Symbol, sp.Expr]) -> bool:
    if set(values) != set(source.variables):
        return False
    if any(sp.expand(equation.subs(values)) != 0 for equation in source.equations):
        return False
    if any(sp.expand(denominator.subs(values)) == 0 for denominator in source.denominators):
        return False
    if any(_condition_truth(guard.subs(values)) is not True for guard in source.guards):
        return False
    return True


def solve(source: Source) -> Result:
    try:
        _validate_source(source)
    except _Unsupported as error:
        return Result(f"UNSUPPORTED:{error}", (), 0, 0, False, True)
    initial = _State(
        equations=_normalize_expressions(source.equations),
        conditions=source.guards,
        denominators=source.denominators,
        remaining=source.variables,
        assignments={},
    )
    stack = [initial]
    terminal: list[dict[sp.Symbol, sp.Expr]] = []
    generated = 1
    try:
        while stack:
            state = stack.pop()
            if not state.remaining:
                if not state.equations and _possible(state.conditions):
                    terminal.append(state.assignments)
                continue
            variable, equation = _choose_pair(state)
            branches = _root_branches(equation, variable)
            for root, conditions in reversed(branches):
                child = _substitute_state(
                    state, equation, variable, root, conditions
                )
                if child is not None:
                    generated += 1
                    if generated > source.branch_cap:
                        raise _BranchCap
                    stack.append(child)
    except _Unsupported as error:
        return Result(f"UNSUPPORTED:{error}", (), generated, 0, False, True)
    except _BranchCap:
        return Result("BRANCH_CAP", (), generated, 0, False, True)

    configurations = []
    failures = 0
    for values in terminal:
        fully_substituted = {
            variable: sp.simplify(expression.subs(values, simultaneous=True))
            for variable, expression in values.items()
        }
        # Resolve any residual assignment dependency to a fixed point.
        for _iteration in range(len(source.variables) + 1):
            updated = {
                variable: sp.simplify(expression.subs(fully_substituted))
                for variable, expression in fully_substituted.items()
            }
            if updated == fully_substituted:
                break
            fully_substituted = updated
        if not _exact_replay(source, fully_substituted):
            failures += 1
            continue
        target = sp.simplify(source.target.subs(fully_substituted))
        configurations.append(
            ExactConfiguration(
                values=fully_substituted,
                target_value=target,
                target_descriptor=_descriptor(target),
            )
        )
    configurations.sort(
        key=lambda configuration: sum(
            (
                float(sp.N(configuration.values[variable], 30))
                - float(source.endpoint.get(variable, 0.0))
            )
            ** 2
            for variable in source.variables
        )
    )
    if not configurations:
        return Result("NO_EXACT_CONFIGURATION", (), generated, failures, False, True)
    return Result(
        "EXACT_CONFIGURATIONS_READY",
        tuple(configurations),
        generated,
        failures,
        False,
        False,
    )


__all__ = ["ExactConfiguration", "Result", "Source", "TargetDescriptor", "solve"]
