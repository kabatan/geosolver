"""Heuristic search boxes; mathematical domains live in problem.domain_bounds."""

import ast

from geosolver.problem.domain_bounds import parameter_expressions, search_bounds


def infer_problem_bounds(bundle):
    plan = getattr(bundle, "analysis_plan", None)
    return list(plan.bounds) if plan is not None else search_bounds(bundle.spec)


def _infer_parametric_variable_names(bundle):
    """Search-family hint only; this does not create mathematical bounds."""
    names = set()
    for item in bundle.spec.construction:
        for node in ast.walk(ast.parse(item.expr, mode="eval")):
            if not isinstance(node, ast.Call):
                continue
            expressions = parameter_expressions(node, item.expr)
            if isinstance(node.func, ast.Name) and node.func.id == "PointOnCircle":
                parameter = next(
                    (k.value for k in node.keywords if k.arg == "t"),
                    node.args[1] if len(node.args) > 1 else None,
                )
                if parameter is not None:
                    expressions = (ast.get_source_segment(item.expr, parameter),)
            for expression in expressions:
                names.update(
                    n.id
                    for n in ast.walk(ast.parse(expression, mode="eval"))
                    if isinstance(n, ast.Name) and n.id in bundle.var_names
                )
    return names
