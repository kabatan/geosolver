"""Disposable Repair A for exact quadratic virtual substitution.

The repair changes branch representation only: a proven zero discriminant has
one branch, and semantically duplicate target descriptors are emitted once.
"""

from __future__ import annotations

import sympy as sp

import candidate as base


def _root_branches(expression: sp.Expr, variable: sp.Symbol):
    polynomial = sp.Poly(expression, variable, domain="EX")
    degree = polynomial.degree()
    if degree > 2:
        raise base._Unsupported("degree-grew-above-two")
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
        common_conditions = leading_conditions + (
            sp.Ne(2 * leading, 0),
            sp.Ge(discriminant, 0),
        )
        # The old representation emitted +/-sqrt(0) as separate branches.
        # That created duplicate authority and artificial branch-cap failures.
        signs = (1,) if sp.simplify(discriminant) == 0 else (-1, 1)
        for sign in signs:
            root = sp.cancel(
                (-linear + sign * sp.sqrt(discriminant)) / (2 * leading)
            )
            branches.append((root, common_conditions))
    if leading.is_zero is not False:
        degenerate_conditions = (sp.Eq(leading, 0),)
        if linear != 0:
            if linear.is_nonzero is not True:
                degenerate_conditions += (sp.Ne(linear, 0),)
            branches.append((-constant / linear, degenerate_conditions))
    return branches


def _substitute_state(*args, **kwargs):
    try:
        return _ORIGINAL_SUBSTITUTE_STATE(*args, **kwargs)
    except (TypeError, ValueError, ZeroDivisionError):
        # A branch whose unresolved leading coefficient later becomes zero can
        # turn its generic 1/a root into zoo while rebuilding strict guards.
        # That sheet is impossible under its carried a!=0 condition; discard it
        # fail-closed and leave the explicit a==0 linear sheet alive.
        return None


_ORIGINAL_SUBSTITUTE_STATE = base._substitute_state


def solve(source: base.Source) -> base.Result:
    original_roots = base._root_branches
    original_substitute = base._substitute_state
    base._root_branches = _root_branches
    base._substitute_state = _substitute_state
    try:
        result = base.solve(source)
    finally:
        base._root_branches = original_roots
        base._substitute_state = original_substitute

    if not result.configurations:
        return result

    unique = []
    seen_descriptors = set()
    for configuration in result.configurations:
        descriptor = (
            configuration.target_descriptor.coefficients_high_to_low,
            configuration.target_descriptor.real_root_index,
        )
        if descriptor in seen_descriptors:
            continue
        seen_descriptors.add(descriptor)
        unique.append(configuration)
    if len(unique) == len(result.configurations):
        return result
    return base.Result(
        status=result.status,
        configurations=tuple(unique),
        branch_states_generated=result.branch_states_generated,
        exact_replay_failures=result.exact_replay_failures,
        endpoint_used_for_pruning=result.endpoint_used_for_pruning,
        fallback_required=result.fallback_required,
    )


Source = base.Source
Result = base.Result
ExactConfiguration = base.ExactConfiguration
TargetDescriptor = base.TargetDescriptor

__all__ = ["ExactConfiguration", "Result", "Source", "TargetDescriptor", "solve"]
