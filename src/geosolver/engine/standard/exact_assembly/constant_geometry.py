"""Bounded, untrusted exact proposals for constant geometric targets.

The ordinary numerical verifier and independent confirmation still run.
Proposals are compared with their resulting answer error interval before use.
"""

import ast

import sympy as sp

from geosolver.engine.standard.search.algebraic_branches import (
    AlgebraicWorkLimit,
    _bounded_symbolic_work,
)
from geosolver.engine.standard.search.cartesian_polynomials import CartesianPolynomials


class ConstantGeometry(CartesianPolynomials):
    def scalar(self, node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Area"
            and len(node.args) == 1
            and not node.keywords
        ):
            return sp.pi * self.circle(node.args[0])[1]
        return super().scalar(node)


def constant_geometry_expression(payload):
    try:
        with _bounded_symbolic_work(0.25) as bounded:
            if not bounded:
                return None
            geometry = ConstantGeometry(dict(payload["constructions"]))
            expression = geometry.scalar(geometry.parse(payload["source"]))
            if (
                expression.free_symbols
                or expression.is_real is not True
                or expression.is_finite is not True
                or sp.count_ops(expression) > 200
            ):
                return None
            return str(expression)
    except (AlgebraicWorkLimit, ArithmeticError, ValueError, TypeError, KeyError, RecursionError):
        return None


def geometry_hint(evaluator):
    """Compute once per solve, and leave variable-dependent targets untouched."""
    bundle = evaluator.bundle
    if bundle.var_names:
        return None
    plan = getattr(bundle, "analysis_plan", None)
    if plan is not None and hasattr(plan, "constant_geometry_hint"):
        return plan.constant_geometry_hint
    from geosolver.runtime.symbolic import OptionalSymbolicTimeout, request

    try:
        hint = request(
            "constant_geometry",
            {
                "source": bundle.spec.answer_expr,
                "constructions": [(item.name, item.expr) for item in bundle.spec.construction],
            },
            timeout_seconds=1.5,
        )
    except (OptionalSymbolicTimeout, ValueError, ArithmeticError):
        hint = None
    if plan is not None:
        plan.constant_geometry_hint = hint
    return hint
