"""Optional exact derivative plans for elementary Cartesian residuals.

Only Newton's derivative evaluation changes. Original residuals, hard gates,
precision stages and final certification remain the admission authority.
"""

import ast
from functools import lru_cache

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.precision.type_guards.hp_contract import hp_contract
from geosolver.problem.expression_source import annotate_source, source_expression
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.runtime.deadline import check_deadline, count_event


def compile_jacobian(payload):
    """Compile in the solve-owned, time-bounded symbolic worker."""
    import sympy as sp

    from geosolver.engine.standard.problem.zero_test_source import zero_test_call
    from geosolver.engine.standard.search.cartesian_polynomials import CartesianPolynomials

    names, construction, constraints, targets = payload
    construction = tuple((name, source) for name, source in construction)
    supported = {
        "Point",
        "Midpoint",
        "Vector",
        "PointOnSegment",
        "Distance",
        "OnSegment",
        "sqrt",
        "abs",
        "Abs",
        "Line",
        "Circle",
        "Circumcircle",
        "Circumcenter",
        "IsTangent",
    }
    try:
        definitions = dict(construction)
        sources = list((*constraints, *targets))
        visited = set()
        while sources:
            source = sources.pop()
            for node in ast.walk(ast.parse(source, mode="eval")):
                if isinstance(node, ast.Name) and node.id in definitions and node.id not in visited:
                    visited.add(node.id)
                    sources.append(definitions[node.id])
                if isinstance(node, ast.Call) and (
                    not isinstance(node.func, ast.Name)
                    or node.func.id not in supported
                    or node.keywords
                ):
                    return None
                if isinstance(node, ast.Compare | ast.BoolOp | ast.Subscript | ast.IfExp):
                    return None
        geometry = CartesianPolynomials(dict(construction))
        variables = tuple(sp.Symbol(name, real=True) for name in names)
        rows, conditions, nonzero = [], [], []
        requires_smoothing = False
        for source, target in zip(constraints, targets, strict=True):
            rhs = geometry.scalar(geometry.parse(target))
            node = zero_test_call(source) if rhs == 0 else None
            if node is not None:
                annotate_source(node, source)
            if node is not None and isinstance(node.func, ast.Name):
                if node.func.id == "Distance":
                    return None  # The local optimizer expands zero distance into two rows.
                if node.func.id == "IsTangent" and len(node.args) == 2:
                    from geosolver.engine.standard.problem.tangency_contacts import (
                        contact_tangency_source,
                    )

                    left, right = (source_expression(argument, source) for argument in node.args)
                    contact = contact_tangency_source(
                        left,
                        right,
                        tuple(construction),
                        tuple(zip(constraints, targets, strict=True)),
                    )
                    if contact is not None:
                        expression = geometry.scalar(geometry.parse(contact))
                    else:
                        try:
                            a, b, c = geometry.line(node.args[0])
                            center, radius_squared = geometry.circle(node.args[1])
                        except ValueError:
                            a, b, c = geometry.line(node.args[1])
                            center, radius_squared = geometry.circle(node.args[0])
                        length = a * a + b * b
                        nonzero.append(length)
                        expression = (
                            a * center[0] + b * center[1] + c
                        ) ** 2 / length - radius_squared
                    if sp.count_ops(expression) > 300:
                        return None
                    rows.append(expression)
                    requires_smoothing = True
                    continue
                if node.func.id == "OnSegment" and len(node.args) == 3:
                    if geometry.zero_relation(node) != 0:
                        return None
                    p, a, b = (geometry.point(arg) for arg in node.args)
                    length = sum((y - x) ** 2 for x, y in zip(a, b, strict=True))
                    projection = sum((v - x) * (y - x) for v, x, y in zip(p, a, b, strict=True))
                    conditions.append((length, projection / length))
                    rows.append(sp.Integer(0))
                    continue
            expression = geometry.scalar(geometry.parse(source)) - rhs
            if sp.count_ops(expression) > 300 or not expression.free_symbols <= set(variables):
                return None
            nonzero.extend(atom.args[0] for atom in expression.atoms(sp.Abs) if atom.free_symbols)
            rows.append(expression)
        derivatives = [sp.diff(row, variable) for row in rows for variable in variables]
        if sum(sp.count_ops(expr) for expr in derivatives) > 1500:
            return None
        prefix = "jacobian_aux_"
        while any(name.startswith(prefix) for name in names):
            prefix = "j" + prefix
        replacements, reduced = sp.cse(derivatives, symbols=sp.numbered_symbols(prefix))
        return {
            "names": names,
            "requires_smoothing": requires_smoothing,
            "rows": len(rows),
            "replacements": [(str(name), str(expr)) for name, expr in replacements],
            "derivatives": [str(expr) for expr in reduced],
            "conditions": [(str(length), str(projection)) for length, projection in conditions],
            "nonzero": [str(expr) for expr in nonzero],
        }
    except (ValueError, TypeError, ArithmeticError, NotImplementedError, KeyError, RecursionError):
        return None


@lru_cache(maxsize=128)
def _plan(key):
    from geosolver.runtime.symbolic import OptionalSymbolicTimeout, request

    try:
        return request("refinement_jacobian", key, timeout_seconds=1.5)
    except (
        OptionalSymbolicTimeout,
        ValueError,
        TypeError,
        ArithmeticError,
        KeyError,
        RecursionError,
    ):
        # A rejected optional plan must leave the original numerical Jacobian
        # available. The worker translates compiler errors to ValueError;
        # direct algorithm calls can retain their original exception type.
        # Ordinary TimeoutError is deliberately excluded: solve deadlines
        # still propagate to the completed-work retention path.
        return None


def derivative_plan(bundle):
    if bundle is None or not 2 <= len(bundle.var_names) <= 12 or bundle.spec.logical_plans:
        return None
    plan = _plan(
        (
            tuple(bundle.var_names),
            tuple((item.name, item.expr) for item in bundle.spec.construction),
            tuple(bundle.spec.constraints),
            tuple(str(target) for target in bundle.targets),
        )
    )
    count_event("analytic_jacobian_plan_requests")
    count_event(
        "analytic_jacobian_plan_available"
        if plan is not None
        else "analytic_jacobian_plan_unsupported"
    )
    return plan


@hp_contract(input_names=("point",))
def evaluate_jacobian(plan, point, dps):
    if plan is None or len(point) != len(plan["names"]):
        return None
    check_deadline()
    count_event("analytic_jacobian_evaluations")
    try:
        with mp.workdps(int(dps)), high_precision_mode():
            context = {
                "mpf": mp.mpf,
                "sqrt": mp.sqrt,
                "Abs": mp.fabs,
                "abs": mp.fabs,
                "sign": mp.sign,
            }
            context.update(zip(plan["names"], point, strict=True))
            for length, projection in plan["conditions"]:
                size = safe_eval_expr_hp(length, context)
                if not mp.isfinite(size) or size <= 0:
                    return None
                parameter = safe_eval_expr_hp(projection, context)
                if not mp.isfinite(parameter) or not 0 < parameter < 1:
                    return None
            for source in plan["nonzero"]:
                value = safe_eval_expr_hp(source, context)
                if not mp.isfinite(value) or value == 0:
                    return None
            for name, source in plan["replacements"]:
                check_deadline()
                context[name] = safe_eval_expr_hp(source, context)
            values = [mp.mpf(safe_eval_expr_hp(source, context)) for source in plan["derivatives"]]
            if not all(mp.isfinite(value) for value in values):
                return None
            width = len(point)
            return [values[index * width : (index + 1) * width] for index in range(plan["rows"])]
    except TimeoutError:
        raise
    except Exception:
        return None
