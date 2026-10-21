"""Necessary mathematical intervals, distinct from heuristic search boxes."""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

from geosolver.problem.expression_source import source_expression
from geosolver.problem.logical_equalities import evaluation_sources

if TYPE_CHECKING:
    from sympy import Expr


@dataclass(frozen=True)
class AxisDomain:
    lower: Fraction | Expr | None = None
    upper: Fraction | Expr | None = None
    lower_closed: bool = True
    upper_closed: bool = True

    @property
    def fixed(self):
        return (
            self.lower is not None
            and self.lower == self.upper
            and self.lower_closed
            and self.upper_closed
        )


def parameter_expressions(node: ast.Call, source: str) -> tuple[str, ...]:
    name = node.func.id if isinstance(node.func, ast.Name) else ""
    keywords = {item.arg: item.value for item in node.keywords}
    if name in {"InscribedPolygon", "InscribedPolygonVertices"}:
        parameters = list(node.args[1:]) + [
            keywords[key] for key in ("t2", "t3") if key in keywords
        ]
        return tuple(source_expression(arg, source) for arg in parameters)
    if name not in {"PointOnSegment", "PointOnArc"}:
        return ()
    index = 2 if name == "PointOnSegment" else (1 if len(node.args) == 2 else 3)
    parameter = keywords.get("t")
    if parameter is None and len(node.args) > index:
        parameter = node.args[index]
    return () if parameter is None else (source_expression(parameter, source),)


def domain_guards(spec) -> tuple[str, ...]:
    result = []
    expressions = [item.expr for item in spec.construction] + [
        source
        for expression in spec.constraints
        for source in evaluation_sources(expression, spec.logical_plans)
    ]
    expressions += [spec.answer_expr] if spec.answer_expr else []
    for source in expressions:
        source = source.replace("^", "**")
        for node in ast.walk(ast.parse(source, mode="eval")):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else ""
            op = "<" if name in {"InscribedPolygon", "InscribedPolygonVertices"} else "<="
            for parameter in parameter_expressions(node, source):
                result.append(f"And(0 {op} ({parameter}), ({parameter}) {op} 1)")
    for name, entry in zip(spec.variables.resolved_names(), spec.bounds or (), strict=False):
        if entry is None:
            continue
        lo, hi = entry
        if lo is not None:
            result.append(f"({name}) >= ({lo})")
        if hi is not None:
            result.append(f"({name}) <= ({hi})")
    return tuple(dict.fromkeys(result))


def affine(expression: str, variables: set[str], *, symbolic_constants=False):
    """Exact affine coefficients; optionally allow closed real scalar constants.

    Rational-only callers (notably exact binary-coordinate checks) keep their
    original contract. Bounds may additionally contain pi, square roots, etc.
    """

    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return {}, Fraction(ast.get_source_segment(expression, node))
        if isinstance(node, ast.Name) and node.id in variables:
            return {node.id: Fraction(1)}, Fraction(0)
        if symbolic_constants and isinstance(node, ast.Name | ast.Call):
            from geosolver.engine.standard.evaluation.exact_constants import exact_constant

            constant = exact_constant(source_expression(node, expression))
            if constant is not None and constant.is_real is True and constant.is_finite is True:
                return {}, constant
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
            a, b = walk(node.operand)
            s = -1 if isinstance(node.op, ast.USub) else 1
            return {v: s * c for v, c in a.items()}, s * b
        if isinstance(node, ast.BinOp):
            a, b = walk(node.left)
            c, d = walk(node.right)
            if isinstance(node.op, ast.Add | ast.Sub):
                s = -1 if isinstance(node.op, ast.Sub) else 1
                keys = set(a) | set(c)
                return {
                    v: a.get(v, 0) + s * c.get(v, 0) for v in keys if a.get(v, 0) + s * c.get(v, 0)
                }, b + s * d
            if isinstance(node.op, ast.Mult) and (not a or not c):
                return (
                    ({v: k * d for v, k in a.items()}, b * d)
                    if not c
                    else ({v: b * k for v, k in c.items()}, b * d)
                )
            if isinstance(node.op, ast.Div) and not c and d:
                return {v: k / d for v, k in a.items()}, b / d
        raise ValueError("non-affine")

    try:
        return walk(ast.parse(expression, mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError):
        return None


def mathematical_bounds(spec) -> dict[str, AxisDomain]:
    from geosolver.engine.standard.interpreter.guards.compile import compile_guards

    names = set(spec.variables.resolved_names())
    result = {name: AxisDomain() for name in spec.variables.resolved_names()}

    def compare(left, op, right):
        pair = affine(f"({left})-({right})", names, symbolic_constants=True)
        if pair is None or len(pair[0]) != 1 or op == "!=":
            return
        ((name, coefficient),) = pair[0].items()
        if not coefficient:
            return
        limit = -pair[1] / coefficient
        if coefficient < 0:
            op = {">": "<", ">=": "<=", "<": ">", "<=": ">=", "==": "=="}[op]
        old = result[name]
        lo, hi, lc, hc = old.lower, old.upper, old.lower_closed, old.upper_closed
        closed = op in {">=", "<=", "=="}
        if op in {">", ">=", "=="}:
            if lo is None or limit > lo:
                lo, lc = limit, closed
            elif limit == lo:
                lc = lc and closed
        if op in {"<", "<=", "=="}:
            if hi is None or limit < hi:
                hi, hc = limit, closed
            elif limit == hi:
                hc = hc and closed
        result[name] = AxisDomain(lo, hi, lc, hc)

    def visit(guard, negate=False):
        if guard.kind == "logical_not":
            for child in guard.children:
                visit(child, not negate)
        elif (guard.kind == "logical_and" and not negate) or (
            guard.kind == "logical_or" and negate
        ):
            for child in guard.children:
                visit(child, negate)
        elif guard.kind == "compare":
            op = guard.operator
            if negate:
                op = {">": "<=", ">=": "<", "<": ">=", "<=": ">", "==": "!=", "!=": "=="}[op]
            compare(guard.lhs_expr, op, guard.rhs_expr)
        elif guard.kind in {"bound", "bound_open"} and not negate:
            closed = guard.kind == "bound"
            if guard.lower_expr is not None:
                compare(guard.lhs_expr, ">=" if closed else ">", guard.lower_expr)
            if guard.upper_expr is not None:
                compare(guard.lhs_expr, "<=" if closed else "<", guard.upper_expr)

    for guard in compile_guards([*spec.guards, *domain_guards(spec)]):
        visit(guard)
    return result


def search_bounds(spec) -> list[tuple[float, float]]:
    names = spec.variables.resolved_names()
    scales = {name: 10.0 for name in names}
    constructions = {item.name: item.expr for item in spec.construction}

    dependency_cache = {}
    variable_names = set(names)

    def dependencies(source, seen):
        if source in dependency_cache:
            return dependency_cache[source]
        tree = ast.parse(source.replace("^", "**"), mode="eval")
        variables = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } & variable_names
        constants = [0.0]

        def visit(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                constants[0] = max(constants[0], abs(float(node.value)))
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                visit(node.left)
            elif isinstance(node, ast.keyword) and node.arg in {"n", "use_first"}:
                return
            else:
                for child in ast.iter_child_nodes(node):
                    visit(child)

        visit(tree)
        references = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        for name in sorted(references & constructions.keys()):
            if name in seen:
                raise ValueError("cyclic construction dependency")
            if name in constructions:
                vs, cs = dependencies(constructions[name], seen | {name})
                variables.update(vs)
                constants[0] = max(constants[0], cs[0])
        result = frozenset(variables), tuple(constants)
        dependency_cache[source] = result
        return result

    for index, expr in enumerate(spec.constraints):
        target = (spec.v or [0] * len(spec.constraints))[index]
        variables, constants = set(), []
        for source in evaluation_sources(expr, spec.logical_plans):
            dependent, magnitudes = dependencies(f"({source})-({target})", set())
            variables.update(dependent)
            constants.extend(magnitudes)
        scale = min(20000.0, max([10.0] + [2 * c for c in constants]))
        for name in variables:
            scales[name] = max(scales[name], scale)
    domains = mathematical_bounds(spec)
    result = []
    for name in names:
        axis = domains[name]
        lo = -scales[name] if axis.lower is None else float(axis.lower)
        hi = scales[name] if axis.upper is None else float(axis.upper)
        # A float search box must not cut off an exact irrational boundary.
        # Original symbolic guards remain the final mathematical authority.
        if axis.lower is not None and not isinstance(axis.lower, Fraction):
            lo = math.nextafter(lo, -math.inf)
        if axis.upper is not None and not isinstance(axis.upper, Fraction):
            hi = math.nextafter(hi, math.inf)
        if axis.upper is None:
            hi = max(hi, lo + 2 * scales[name])
        if axis.lower is None:
            lo = min(lo, hi - 2 * scales[name])
        if lo > hi:
            # Guards keep an inconsistent domain infeasible during search.
            lo, hi = min(lo, hi) - 1, max(lo, hi) + 1
        result.append((lo, hi))
    return result
