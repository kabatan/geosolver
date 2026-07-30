"""Exact two-variable polynomial fiber transport; fail closed outside subset."""

from __future__ import annotations

import ast
from fractions import Fraction
from typing import Any, Mapping, Sequence

import sympy as sp
from sympy.polys.polyerrors import CoercionFailed, PolynomialError


MAX_PROPOSALS = 4
MAX_DENOMINATOR = 16


class Unsupported(ValueError):
    pass


def _expr(node: ast.AST, symbols: Mapping[str, sp.Symbol]) -> sp.Expr:
    if isinstance(node, ast.Name) and node.id in symbols:
        return symbols[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return sp.Rational(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _expr(node.operand, symbols)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _expr(node.left, symbols), _expr(node.right, symbols)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div) and not right.free_symbols:
            return left / right
        if isinstance(node.op, ast.Pow) and right.is_Integer and 0 <= int(right) <= 8:
            return left ** int(right)
    raise Unsupported("nonpolynomial source expression")


def _parse(source: object, symbols: Mapping[str, sp.Symbol]) -> sp.Expr:
    if isinstance(source, bool):
        raise Unsupported("Boolean scalar is not a polynomial")
    if isinstance(source, (int, float)):
        source = repr(source)
    if not isinstance(source, str):
        raise Unsupported("source scalar is not an expression")
    try:
        return sp.expand(_expr(ast.parse(source, mode="eval").body, symbols))
    except SyntaxError as error:
        raise Unsupported("invalid source expression") from error


def _strict_guard(source: str, symbols: Mapping[str, sp.Symbol]):
    try:
        node = ast.parse(source, mode="eval").body
    except SyntaxError as error:
        raise Unsupported("invalid guard") from error
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        raise Unsupported("guard is not one strict comparison")
    left = _expr(node.left, symbols)
    right = _expr(node.comparators[0], symbols)
    if isinstance(node.ops[0], ast.Lt):
        return sp.StrictLessThan(left, right)
    if isinstance(node.ops[0], ast.Gt):
        return sp.StrictGreaterThan(left, right)
    raise Unsupported("guard is not strict")


def _model(document: Mapping[str, Any]):
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(names, list) or len(names) != 2 or not all(isinstance(x, str) for x in names):
        raise Unsupported("exact univariate fiber requires two variables")
    if document.get("construction") not in (None, []):
        raise Unsupported("constructed geometry is outside polynomial subset")
    symbols_tuple = sp.symbols(" ".join(names), real=True)
    symbols = dict(zip(names, symbols_tuple, strict=True))
    constraints = document.get("constraints")
    if not isinstance(constraints, list) or not constraints:
        raise Unsupported("source constraints are absent")
    polynomials = []
    for item in constraints:
        if not isinstance(item, Mapping):
            raise Unsupported("constraint is malformed")
        expression = _parse(item.get("def"), symbols) - _parse(item.get("value"), symbols)
        try:
            polynomial = sp.Poly(expression, *symbols_tuple, domain=sp.QQ)
        except (PolynomialError, CoercionFailed) as error:
            raise Unsupported("constraint is not QQ polynomial") from error
        if polynomial.total_degree() > 8:
            raise Unsupported("polynomial degree exceeds bound")
        polynomials.append(polynomial.as_expr())
    guards_raw = document.get("guards") or []
    if not isinstance(guards_raw, list) or not all(isinstance(x, str) for x in guards_raw):
        raise Unsupported("guards are malformed")
    guards = [_strict_guard(value, symbols) for value in guards_raw]
    bounds = document.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise Unsupported("two exact source bounds are required")
    exact_bounds = []
    for index, pair in enumerate(bounds):
        if not isinstance(pair, list) or len(pair) != 2:
            raise Unsupported("bound is malformed")
        lower, upper = (_parse(value, symbols) for value in pair)
        if lower.free_symbols or upper.free_symbols or not lower.is_Rational or not upper.is_Rational:
            raise Unsupported("bounds are not rational constants")
        exact_bounds.append((lower, upper))
        guards.extend((sp.StrictGreaterThan(symbols_tuple[index], lower), sp.StrictLessThan(symbols_tuple[index], upper)))
    return symbols_tuple, tuple(polynomials), tuple(guards), tuple(exact_bounds)


def _generic_corank_one(polynomials, symbols):
    jacobian = sp.Matrix(polynomials).jacobian(symbols)
    entries = [sp.expand(value) for value in jacobian]
    if not any(value != 0 for value in entries):
        raise Unsupported("zero rank")
    for first in range(jacobian.rows):
        for second in range(first + 1, jacobian.rows):
            if sp.expand(jacobian[first, 0] * jacobian[second, 1] - jacobian[first, 1] * jacobian[second, 0]) != 0:
                raise Unsupported("full rank")
    free = 0 if any(sp.diff(value, symbols[1]) != 0 for value in polynomials) else 1
    dependent = 1 - free
    if not any(sp.diff(value, symbols[dependent]) != 0 for value in polynomials):
        raise Unsupported("dependent chart absent")
    return free, dependent


def _slices(initial: float, lower: sp.Rational, upper: sp.Rational):
    values = set()
    for denominator in range(1, MAX_DENOMINATOR + 1):
        center = round(initial * denominator)
        for numerator in range(center - 1, center + 2):
            value = sp.Rational(numerator, denominator)
            if lower < value < upper:
                values.add(value)
    return sorted(values, key=lambda value: (int(value.q + abs(value.p)), abs(float(value) - initial), int(value.q), int(value.p)))


def _guard_exact(guards, substitutions) -> bool:
    try:
        return all(bool(guard.subs(substitutions)) for guard in guards)
    except TypeError:
        return False


def exact_transport(document: Mapping[str, Any], endpoint: Sequence[float]):
    try:
        symbols, polynomials, guards, bounds = _model(document)
        free, dependent = _generic_corank_one(polynomials, symbols)
        witnesses = []
        seen = set()
        for free_value in _slices(float(endpoint[free]), *bounds[free]):
            univariate = []
            for source in polynomials:
                expression = sp.expand(source.subs({symbols[free]: free_value}))
                polynomial = sp.Poly(expression, symbols[dependent], domain=sp.QQ)
                if not polynomial.is_zero:
                    univariate.append(polynomial)
            if not univariate:
                continue
            common = univariate[0]
            for polynomial in univariate[1:]:
                common = sp.gcd(common, polynomial)
            if common.degree() <= 0:
                continue
            roots = sp.real_roots(common.as_expr())
            roots.sort(key=lambda value: abs(float(sp.N(value, 50)) - float(endpoint[dependent])))
            for root in roots:
                values = [None, None]
                values[free], values[dependent] = free_value, root
                substitutions = dict(zip(symbols, values, strict=True))
                if not all(sp.expand(source.subs(substitutions)) == 0 for source in polynomials):
                    continue
                if not _guard_exact(guards, substitutions):
                    continue
                minpolys = [sp.Poly(sp.minpoly(value), domain=sp.QQ) for value in values]
                if any(poly.degree() < 1 or sp.gcd(poly, poly.diff()).degree() != 0 for poly in minpolys):
                    continue
                key = tuple(sp.srepr(value) for value in values)
                if key not in seen:
                    seen.add(key)
                    witnesses.append((tuple(values), free_value))
                break
            if len(witnesses) >= MAX_PROPOSALS:
                break
        distinct = {sp.srepr(value) for _point, value in witnesses}
        if len(distinct) < 2:
            raise Unsupported("fewer than two distinct exact slices")
        return [tuple(float(sp.N(value, 50)) for value in point) for point, _slice in witnesses], {
            "status": "EXACT_POLYNOMIAL_FIBER_WITNESSES",
            "rank": 1,
            "nullity": 1,
            "free_coordinate": free,
            "dependent_coordinate": dependent,
            "proposal_count": len(witnesses),
            "distinct_exact_slice_count": len(distinct),
            "maximum_proposals": MAX_PROPOSALS,
            "maximum_denominator": MAX_DENOMINATOR,
            "exact_polynomial_jacobian_rank": True,
            "dependent_univariate_gcd": True,
            "exact_source_and_strict_guard_substitution": True,
            "square_free_minpolys": True,
            "float_newton_used_for_branch_order_only": True,
            "routing_uses_target_answer_id_family_or_outcome": False,
        }
    except (Unsupported, PolynomialError, CoercionFailed, ValueError, TypeError, ZeroDivisionError) as error:
        return [], {"status": "EXACT_TRANSPORT_UNSUPPORTED", "reason": str(error)[:200]}
