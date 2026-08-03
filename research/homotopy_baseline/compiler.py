"""Fail-closed V15-to-polynomial compiler for the research baseline.

The compiler is intentionally independent from the product search algorithm.
It reuses the public V15 validator and the repository's symbolic geometry
formula definitions, then turns every radical and absolute value into an
auxiliary polynomial variable.  The generated equations have rational
coefficients; this makes the Julia homotopy worker and exact elimination
reproducible without floating-point coefficient reconstruction.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import operator
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import sympy as sp
from sympy.core.relational import Relational

from geotarget.lazy_symbolic_geometry import (
    LazyCircle,
    LazyGeometryState,
    LazyLine,
    LazyPoint,
    LazySegment,
    build_lazy_geometry_context,
)
from geotarget.validation import validate

from .ir import Admission, Compilation, Monomial, Polynomial, SignCondition

CORE_BLOCKED_CALLS = frozenset(
    {
        "Angle",
        "AngleBisector",
        "PointOnCircle",
        "PointOnArc",
        "Arc",
        "Rotate",
        "RegularPolygon",
        "InscribedPolygon",
        "InscribedPolygonVertices",
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "atan2",
    }
)

EXTENDED_ALWAYS_BLOCKED_CALLS = frozenset(
    {"PointOnArc", "Arc", "Rotate", "RegularPolygon", "InscribedPolygonVertices"}
)

_GEOMETRY_TYPES = (LazyPoint, LazyLine, LazyCircle, LazySegment, list, tuple)
_SCALAR_TYPES = (sp.Expr, int, float)
_COMPARISON_OPS: dict[type[ast.cmpop], Callable[[Any, Any], Any]] = {
    ast.Eq: sp.Eq,
    ast.NotEq: sp.Ne,
    ast.Lt: sp.Lt,
    ast.LtE: sp.Le,
    ast.Gt: sp.Gt,
    ast.GtE: sp.Ge,
}


class UnsupportedFormulation(ValueError):
    """The source cannot be represented by this baseline mode."""


@dataclass(frozen=True)
class PhaseReference:
    """A phase-only parameter replaced by a unit-circle coordinate pair."""

    name: str
    cosine: sp.Symbol
    sine: sp.Symbol


@dataclass(frozen=True)
class GuardRelation:
    relation: str
    left: Any
    right: Any
    source: str


@dataclass(frozen=True)
class GuardBound:
    value: Any
    lower: Any
    upper: Any
    inclusive: bool
    source: str


class SymbolicEvaluator(ast.NodeVisitor):
    """Small symbolic evaluator with no Python ``eval`` or boolean coercion."""

    def __init__(self, context: Mapping[str, Any], *, source: str = "") -> None:
        self.context = dict(context)
        self.source = source

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        value = node.value
        if isinstance(value, bool | str):
            return value
        if isinstance(value, int):
            return sp.Integer(value)
        if isinstance(value, float):
            if not math.isfinite(value):
                raise UnsupportedFormulation("non-finite numeric literal")
            return sp.Rational(str(value))
        if value is None:
            return None
        raise UnsupportedFormulation(f"unsupported literal: {value!r}")

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id not in self.context:
            raise UnsupportedFormulation(f"unknown symbolic name: {node.id}")
        return self.context[node.id]

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        value = self.visit(node.value)
        if node.attr.startswith("_"):
            raise UnsupportedFormulation("private attribute")
        try:
            return getattr(value, node.attr)
        except AttributeError as error:
            raise UnsupportedFormulation(f"unknown attribute: {node.attr}") from error

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left, right = self.visit(node.left), self.visit(node.right)
        functions: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
        }
        function = functions.get(type(node.op))
        if function is None:
            raise UnsupportedFormulation(f"unsupported binary operator: {type(node.op).__name__}")
        try:
            return function(left, right)
        except Exception as error:
            raise UnsupportedFormulation(f"symbolic operator failed: {error}") from error

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        if isinstance(node.op, ast.Not):
            return sp.Not(value)
        raise UnsupportedFormulation(f"unsupported unary operator: {type(node.op).__name__}")

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        relations = []
        for op, raw_right in zip(node.ops, node.comparators, strict=True):
            right = self.visit(raw_right)
            function = _COMPARISON_OPS.get(type(op))
            if function is None:
                raise UnsupportedFormulation(f"unsupported comparison: {type(op).__name__}")
            relations.append(function(left, right))
            left = right
        return sp.And(*relations) if len(relations) > 1 else relations[0]

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        values = [self.visit(value) for value in node.values]
        if isinstance(node.op, ast.And):
            return sp.And(*values)
        if isinstance(node.op, ast.Or):
            return sp.Or(*values)
        raise UnsupportedFormulation(f"unsupported boolean operator: {type(node.op).__name__}")

    def visit_IfExp(self, node: ast.IfExp) -> Any:
        condition = self.visit(node.test)
        body, alternate = self.visit(node.body), self.visit(node.orelse)
        if condition is True:
            return body
        if condition is False:
            return alternate
        return sp.Piecewise((body, condition), (alternate, True))

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise UnsupportedFormulation("call target must be a direct name")
        function = self.context.get(node.func.id)
        if function is None or not callable(function):
            raise UnsupportedFormulation(f"unknown call: {node.func.id}")
        args = [self.visit(value) for value in node.args]
        keywords = {
            keyword.arg: (
                int(keyword.value.value)
                if keyword.arg == "n"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, int)
                and not isinstance(keyword.value.value, bool)
                else self.visit(keyword.value)
            )
            for keyword in node.keywords
            if keyword.arg is not None
        }
        try:
            return function(*args, **keywords)
        except UnsupportedFormulation:
            raise
        except Exception as error:
            raise UnsupportedFormulation(f"call {node.func.id} failed: {error}") from error

    def visit_Tuple(self, node: ast.Tuple) -> tuple[Any, ...]:
        return tuple(self.visit(element) for element in node.elts)

    def visit_List(self, node: ast.List) -> list[Any]:
        return [self.visit(element) for element in node.elts]

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        value = self.visit(node.value)
        index = (
            int(node.slice.value)
            if isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, int)
            and not isinstance(node.slice.value, bool)
            else self.visit(node.slice)
        )
        return value[index]

    def generic_visit(self, node: ast.AST) -> Any:
        raise UnsupportedFormulation(f"unsupported syntax node: {type(node).__name__}")


def _exact_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return sp.Rational(str(value))
    return value


class AlgebraicLifter:
    """Replace radicals and absolute values with positive auxiliary variables."""

    def __init__(self, variables: list[sp.Symbol]) -> None:
        self.variables = variables
        self.equations: list[sp.Expr] = []
        self.conditions: list[tuple[sp.Expr, str, str]] = []
        self._counter = 0
        self._cache: dict[tuple[str, str], sp.Symbol] = {}

    def fresh(self, prefix: str) -> sp.Symbol:
        self._counter += 1
        symbol = sp.Symbol(f"__hc_{prefix}_{self._counter}")
        self.variables.append(symbol)
        return symbol

    def lift(self, expression: Any) -> Any:
        expression = sp.sympify(expression)
        if expression.is_Atom:
            if expression.func in (sp.zoo, sp.oo, -sp.oo, sp.nan):
                raise UnsupportedFormulation("non-finite symbolic value")
            return expression
        if expression.func is sp.Abs:
            child = self.lift(expression.args[0])
            key = ("abs", sp.srepr(child))
            symbol = self._cache.get(key)
            if symbol is None:
                symbol = self.fresh("abs")
                self._cache[key] = symbol
                self.equations.append(symbol**2 - child**2)
                self.conditions.append((symbol, ">=", "absolute value"))
            return symbol
        if expression.func is sp.Pow:
            base, exponent = expression.args
            if exponent == sp.Rational(1, 2):
                child = self.lift(base)
                key = ("sqrt", sp.srepr(child))
                symbol = self._cache.get(key)
                if symbol is None:
                    symbol = self.fresh("sqrt")
                    self._cache[key] = symbol
                    self.equations.append(symbol**2 - child)
                    self.conditions.append((symbol, ">=", "square root"))
                return symbol
            if exponent == -sp.Rational(1, 2):
                # SymPy often canonicalizes cos/sin of an Angle into an
                # inverse square root.  Lower it through the same positive
                # square-root and inverse machinery as an explicit sqrt.
                root = self.lift(sp.sqrt(base))
                key = ("inv", sp.srepr(root))
                symbol = self._cache.get(key)
                if symbol is None:
                    symbol = self.fresh("inv")
                    self._cache[key] = symbol
                    self.equations.append(symbol * root - 1)
                    self.conditions.append((root, "!=", "inverse denominator"))
                return symbol
            if exponent.is_Integer:
                exponent_int = int(exponent)
                if exponent_int < 0:
                    # Every source-level division is saturated with an
                    # explicit inverse equation.  This avoids silently
                    # clearing a denominator and accidentally admitting its
                    # zero locus as a solution.
                    lifted_base = self.lift(base)
                    key = ("inv", sp.srepr(lifted_base))
                    symbol = self._cache.get(key)
                    if symbol is None:
                        symbol = self.fresh("inv")
                        self._cache[key] = symbol
                        self.equations.append(symbol * lifted_base - 1)
                        self.conditions.append((lifted_base, "!=", "inverse denominator"))
                    return symbol ** (-exponent_int)
                return self.lift(base) ** exponent_int
            raise UnsupportedFormulation(f"unsupported non-integer power: {expression}")
        if expression.func in (sp.Add, sp.Mul):
            args = [self.lift(arg) for arg in expression.args]
            return expression.func(*args)
        if expression.func in (sp.Max, sp.Min, sp.Piecewise):
            raise UnsupportedFormulation(
                f"piecewise expression is not in algebraic core: {expression}"
            )
        if expression.has(sp.sin, sp.cos, sp.tan, sp.asin, sp.acos, sp.atan, sp.atan2):
            raise UnsupportedFormulation(f"unlowered transcendental expression: {expression}")
        args = [self.lift(arg) for arg in expression.args]
        try:
            return expression.func(*args)
        except Exception as error:
            raise UnsupportedFormulation(f"cannot lower expression: {expression}") from error

    def validation_conditions(self) -> Iterable[tuple[sp.Expr, str, str]]:
        return tuple(self.conditions)


def _polynomial(expression: sp.Expr, variables: list[sp.Symbol], *, label: str) -> Polynomial:
    expression = sp.cancel(sp.together(expression))
    numerator, denominator = sp.fraction(expression)
    if denominator != 1 and denominator.free_symbols:
        raise UnsupportedFormulation(
            f"unresolved denominator in {label}; use a nonzero inverse lift: {denominator}"
        )
    if denominator != 1:
        # Numeric rational denominators are exact coefficients, not domain
        # restrictions.  Only symbolic denominators require inverse
        # saturation above.
        numerator = sp.Rational(1, 1) * numerator / denominator
    try:
        poly = sp.Poly(sp.expand(numerator), *variables, domain=sp.QQ)
    except Exception as error:
        raise UnsupportedFormulation(f"non-rational polynomial in {label}: {numerator}") from error
    terms: list[Monomial] = []
    for exponents, coefficient in sorted(poly.terms(), key=lambda item: item[0]):
        coefficient = sp.Rational(coefficient)
        terms.append(
            Monomial(
                tuple(int(value) for value in exponents),
                int(coefficient.p),
                int(coefficient.q),
            )
        )
    return Polynomial(tuple(terms))


def _pad_polynomial(polynomial: Polynomial, width: int) -> Polynomial:
    """Pad constants/early guard polynomials to the final variable width."""

    return Polynomial(
        tuple(
            Monomial(
                tuple(term.exponents) + (0,) * max(0, width - len(term.exponents)),
                term.numerator,
                term.denominator,
            )
            for term in polynomial.terms
        )
    )


def _with_denominator_condition(
    expression: sp.Expr,
    variables: list[sp.Symbol],
    conditions: list[SignCondition],
    *,
    source: str,
) -> Polynomial:
    expression = sp.cancel(sp.together(expression))
    numerator, denominator = sp.fraction(expression)
    if denominator != 1:
        denominator_poly = _polynomial(denominator, variables, label=f"denominator:{source}")
        conditions.append(SignCondition(denominator_poly, "!=", source + ": denominator"))
    return _polynomial(numerator, variables, label=source)


def _call_names(expressions: Iterable[str]) -> tuple[str, ...]:
    names: set[str] = set()
    for expression in expressions:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            continue
        names.update(
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        )
    return tuple(sorted(names))


def _phase_analysis(problem: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Find phase-only ``PointOnCircle(..., t)`` parameters.

    A phase parameter is admitted only when every occurrence is exactly the
    second positional argument of PointOnCircle.  Bounds and direct target
    references are intentionally rejected here; a future extension can add
    certified rational arc endpoints without changing the core translator.
    """

    names = {str(value) for value in problem.get("variables", {}).get("names", [])}
    occurrences: dict[str, int] = {}
    phase_candidates: set[str] = set()
    for expression in _expressions(problem):
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id not in names:
                continue
            occurrences[node.id] = occurrences.get(node.id, 0) + 1
            parent = parents.get(node)
            allowed = False
            if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name):
                allowed = (
                    parent.func.id == "PointOnCircle"
                    and len(parent.args) >= 2
                    and parent.args[1] is node
                )
            if allowed:
                phase_candidates.add(node.id)
    phase_names = tuple(sorted(name for name in phase_candidates if occurrences.get(name, 0) > 0))
    # The parent-based test above already distinguishes the allowed uses; run
    # a direct second pass to produce stable reason codes for mixed use.
    mixed_names: set[str] = set()
    for expression in _expressions(problem):
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            continue
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id not in phase_names:
                continue
            parent = parents.get(node)
            if not (
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name)
                and parent.func.id == "PointOnCircle"
                and len(parent.args) >= 2
                and parent.args[1] is node
            ):
                mixed_names.add(node.id)
    return phase_names, tuple(sorted(mixed_names))


def _source_digest(problem: Mapping[str, Any]) -> str:
    payload = json.dumps(
        problem, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _expressions(problem: Mapping[str, Any]) -> list[str]:
    construction = problem.get("construction", [])
    constraints = problem.get("constraints", [])
    guards = problem.get("guards", [])
    values = [str(item["expr"]) for item in construction]
    values.extend(str(item["def"]) for item in constraints)
    values.extend(str(item["value"]) for item in constraints if isinstance(item.get("value"), str))
    values.extend(str(item) for item in guards)
    values.append(str(problem.get("answer", "")))
    if problem.get("post_process"):
        values.append(str(problem["post_process"]))
    return values


def _guard_context(base: Mapping[str, Any]) -> dict[str, Any]:
    context = dict(base)
    context.update(
        {
            "Assume": lambda condition, *args, **kwargs: condition,
            "AssumeEq": lambda left, right, *args, **kwargs: GuardRelation(
                "eq", left, right, "AssumeEq"
            ),
            "AssumeNe": lambda left, right, *args, **kwargs: GuardRelation(
                "ne", left, right, "AssumeNe"
            ),
            "AssumeLt": lambda left, right, *args, **kwargs: GuardRelation(
                "<", left, right, "AssumeLt"
            ),
            "AssumeLe": lambda left, right, *args, **kwargs: GuardRelation(
                "<=", left, right, "AssumeLe"
            ),
            "AssumeGt": lambda left, right, *args, **kwargs: GuardRelation(
                ">", left, right, "AssumeGt"
            ),
            "AssumeGe": lambda left, right, *args, **kwargs: GuardRelation(
                ">=", left, right, "AssumeGe"
            ),
            "Bound": lambda value, bounds, message=None, inclusive=True, **kwargs: GuardBound(
                value, bounds[0], bounds[1], bool(inclusive), "Bound"
            ),
            "AssumeAcute": lambda a, b, c, *args, **kwargs: sp.Gt((a - b).dot(c - b), 0),
            "AssumeRight": lambda a, b, c, *args, **kwargs: sp.Eq((a - b).dot(c - b), 0),
            "AssumeObtuse": lambda a, b, c, *args, **kwargs: sp.Lt((a - b).dot(c - b), 0),
            "AssumeOrder": lambda a, b, c, *args, **kwargs: sp.And(
                sp.Eq((a - b).cross(c - b), 0),
                sp.Le((a - b).dot(c - b), 0),
            ),
        }
    )
    return context


def _guard_atoms(value: Any, *, source: str) -> list[tuple[str, Any, Any, str]]:
    if isinstance(value, GuardRelation):
        return [(value.relation, value.left, value.right, source or value.source)]
    if isinstance(value, GuardBound):
        relation = ">=" if value.inclusive else ">"
        upper = "<=" if value.inclusive else "<"
        return [
            (relation, value.value, value.lower, source or value.source),
            (upper, value.value, value.upper, source or value.source),
        ]
    if value is True:
        return []
    if value is False:
        return [("false", sp.Integer(0), sp.Integer(1), source)]
    if isinstance(value, sp.And):
        atoms: list[tuple[str, Any, Any, str]] = []
        for item in value.args:
            atoms.extend(_guard_atoms(item, source=source))
        return atoms
    if isinstance(value, sp.Or | sp.Not):
        raise UnsupportedFormulation("disjunctive/negated guards require branch expansion")
    if isinstance(value, Relational):
        relation = {
            "Equality": "eq",
            "Unequality": "ne",
            "StrictLessThan": "<",
            "LessThan": "<=",
            "StrictGreaterThan": ">",
            "GreaterThan": ">=",
        }.get(type(value).__name__)
        if relation is None:
            raise UnsupportedFormulation(f"unsupported guard relation: {value}")
        return [(relation, value.lhs, value.rhs, source)]
    if isinstance(value, sp.Expr | int | float):
        return [("eq", value, 0, source)]
    raise UnsupportedFormulation(f"unsupported guard value: {value!r}")


def _relation_expression(relation: str, left: Any, right: Any) -> tuple[sp.Expr, str]:
    if relation in {"eq", "ne"}:
        return sp.sympify(left) - sp.sympify(right), relation
    return sp.sympify(left) - sp.sympify(right), relation


def _base_context(state: LazyGeometryState) -> dict[str, Any]:
    geometry, _ = build_lazy_geometry_context(state)
    return {
        **geometry,
        "abs": sp.Abs,
        "sqrt": sp.sqrt,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "asin": sp.asin,
        "acos": sp.acos,
        "atan": sp.atan,
        "atan2": sp.atan2,
        "min": sp.Min,
        "max": sp.Max,
        "pi": sp.pi,
        "float": lambda value=0: sp.sympify(value),
        "int": lambda value=0: int(value) if sp.sympify(value).is_Integer else sp.sympify(value),
        "And": sp.And,
        "Or": sp.Or,
        "Not": sp.Not,
    }


def _algebraic_intersect_context(state: LazyGeometryState) -> Callable[..., Any]:
    """Intersection formulas without the lazy runtime's Max/Piecewise nodes.

    The exact baseline admits a finite branch only when the source explicitly
    selects ``n=1`` or ``n=2``.  An unselected two-point result remains a
    finite list for a subsequent literal subscript; near/far and symbolic
    selector ordering are rejected rather than guessed.
    """

    def line_circle_candidates(line: LazyLine, circle: LazyCircle) -> list[LazyPoint]:
        a, b, c = line.a, line.b, line.c
        xc, yc, radius = circle.center.x, circle.center.y, circle.radius
        shifted = a * xc + b * yc + c
        divisor = a**2 + b**2
        state.require("nonzero", divisor, "Intersect.LineCircle.divisor")
        delta = radius**2 * divisor - shifted**2
        state.require("nonnegative", delta, "Intersect.LineCircle.discriminant")
        multiplier = sp.sqrt(delta) / divisor
        x0 = -a * shifted / divisor
        y0 = -b * shifted / divisor
        return [
            LazyPoint(xc + x0 + b * multiplier, yc + y0 - a * multiplier),
            LazyPoint(xc + x0 - b * multiplier, yc + y0 + a * multiplier),
        ]

    def circle_circle_candidates(first: LazyCircle, second: LazyCircle) -> list[LazyPoint]:
        x1, y1, radius1 = first.center.x, first.center.y, first.radius
        x2, y2, radius2 = second.center.x, second.center.y, second.radius
        distance_squared = (x1 - x2) ** 2 + (y1 - y2) ** 2
        state.require("nonzero", distance_squared, "Intersect.CircleCircle.center_distance")
        distance = sp.sqrt(distance_squared)
        along = (radius1**2 - radius2**2 + distance_squared) / (2 * distance)
        height_squared = radius1**2 - along**2
        state.require("nonnegative", height_squared, "Intersect.CircleCircle.discriminant")
        height = sp.sqrt(height_squared)
        x0 = x1 + along * (x2 - x1) / distance
        y0 = y1 + along * (y2 - y1) / distance
        offset_x = -(y2 - y1) * (height / distance)
        offset_y = (x2 - x1) * (height / distance)
        return [
            LazyPoint(x0 + offset_x, y0 + offset_y),
            LazyPoint(x0 - offset_x, y0 - offset_y),
        ]

    def intersect(first: Any, second: Any, **selectors: Any) -> Any:
        if isinstance(first, LazyLine) and isinstance(second, LazyLine):
            determinant = first.a * second.b - second.a * first.b
            state.require("nonzero", determinant, "Intersect.LineLine.determinant")
            candidates = [
                LazyPoint(
                    (first.b * second.c - second.b * first.c) / determinant,
                    (first.c * second.a - second.c * first.a) / determinant,
                )
            ]
        elif isinstance(first, LazyLine) and isinstance(second, LazyCircle):
            candidates = line_circle_candidates(first, second)
        elif isinstance(first, LazyCircle) and isinstance(second, LazyLine):
            candidates = line_circle_candidates(second, first)
        elif isinstance(first, LazyCircle) and isinstance(second, LazyCircle):
            candidates = circle_circle_candidates(first, second)
        else:
            raise UnsupportedFormulation("unsupported_intersection_operands")
        if selectors.get("near") is not None or selectors.get("far") is not None:
            raise UnsupportedFormulation("unsupported_intersection_distance_selector")
        if selectors.get("exclude") is not None:
            raise UnsupportedFormulation("unsupported_intersection_exclude_selector")
        ordinal = selectors.get("n")
        if ordinal is not None:
            if not isinstance(ordinal, int) or isinstance(ordinal, bool):
                raise UnsupportedFormulation("intersection ordinal must be a literal integer")
            if ordinal < 1 or ordinal > len(candidates):
                raise UnsupportedFormulation("intersection ordinal is outside candidate range")
            state.record_selector("n", len(candidates), ordinal - 1)
            return candidates[ordinal - 1]
        if len(candidates) == 1:
            state.record_selector("single", 1, 0)
            return candidates[0]
        state.record_selector("branch", len(candidates), None)
        return candidates

    return intersect


def _semantic_preflight(problem: Mapping[str, Any], mode: str) -> tuple[str, ...]:
    expressions = _expressions(problem)
    calls = set(_call_names(expressions))
    reasons: list[str] = []
    if mode not in {"core", "extended"}:
        reasons.append("unknown_mode")
    blocked = CORE_BLOCKED_CALLS if mode == "core" else EXTENDED_ALWAYS_BLOCKED_CALLS
    for call in sorted(calls & blocked):
        reasons.append(f"unsupported_call:{call}")
    for expression in expressions:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            reasons.append("syntax_error")
            continue
        if mode == "core" and any(
            isinstance(node, ast.Name) and node.id == "pi" for node in ast.walk(tree)
        ):
            reasons.append("unsupported_constant:pi")
        if mode == "extended":
            dynamic_trig = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"sin", "cos", "tan"}
                and any(
                    isinstance(child, ast.Name) and child.id != "pi"
                    for child in ast.walk(node.args[0])
                )
                for node in ast.walk(tree)
            )
            if dynamic_trig:
                admissible_angle = any(
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "Angle"
                    for node in ast.walk(tree)
                )
                if not admissible_angle:
                    reasons.append("unsupported_dynamic_trigonometry")
    if mode == "extended":
        phase_names, mixed_names = _phase_analysis(problem)
        for name in mixed_names:
            reasons.append(f"unsupported_phase_mixed:{name}")
        # Bounds on phase parameters require an exact arc endpoint lowering;
        # full-circle phase variables (no Bound/target occurrence) are handled
        # by the unit-circle branch in compile_problem.
        for expression in expressions:
            try:
                tree = ast.parse(expression, mode="eval")
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "Bound"
                    and node.args
                    and isinstance(node.args[0], ast.Name)
                    and node.args[0].id in phase_names
                ):
                    reasons.append(f"unsupported_phase_bound:{node.args[0].id}")
    return tuple(dict.fromkeys(reasons))


def _validate_problem(problem: Mapping[str, Any]) -> dict[str, Any]:
    report = validate(dict(problem))
    if not report.valid or report.normalized_problem is None:
        messages = "; ".join(issue.message for issue in report.issues)
        raise UnsupportedFormulation(f"invalid V15 input: {messages}")
    return report.normalized_problem


def compile_problem(problem: Mapping[str, Any], *, mode: str = "core") -> Compilation:
    """Compile one V15 document into a saturated square polynomial system.

    Evaluation is separated from lowering.  All radicals, inverse
    denominators, and guard expressions are lifted before the source ideal is
    constructed, so a later auxiliary cannot invalidate an earlier Groebner
    basis dimension.
    """

    normalized = _validate_problem(problem)
    digest = _source_digest(normalized)
    reasons = list(_semantic_preflight(normalized, mode))
    if reasons:
        admission = Admission(
            mode=mode,
            supported=False,
            stage="preflight",
            reasons=tuple(reasons),
            calls=_call_names(_expressions(normalized)),
        )
        raise UnsupportedFormulation(
            json.dumps(admission.json(), ensure_ascii=False, sort_keys=True)
        )

    original_names = tuple(str(value) for value in normalized["variables"]["names"])
    phase_names, mixed_phase_names = _phase_analysis(normalized) if mode == "extended" else ((), ())
    if mixed_phase_names:
        raise UnsupportedFormulation("unsupported_phase_mixed:" + ",".join(mixed_phase_names))
    names = tuple(name for name in original_names if name not in phase_names)
    source_constraint_count = len(normalized["constraints"])
    if source_constraint_count != len(original_names):
        raise UnsupportedFormulation(
            f"source_non_square:constraints={source_constraint_count},variables={len(original_names)}"
        )

    symbols = [sp.Symbol(name) for name in names]
    phase_references = {
        name: PhaseReference(
            name,
            sp.Symbol(f"__hc_phase_cos_{name}"),
            sp.Symbol(f"__hc_phase_sin_{name}"),
        )
        for name in phase_names
    }
    symbols.extend(
        coordinate
        for reference in phase_references.values()
        for coordinate in (reference.cosine, reference.sine)
    )
    state = LazyGeometryState()
    context = _base_context(state)
    context["Intersect"] = _algebraic_intersect_context(state)
    context.update(dict(zip(names, symbols[: len(names)], strict=True)))
    context.update(phase_references)
    if phase_references:
        original_point_on_circle = context["PointOnCircle"]

        def phase_point_on_circle(circle: Any, parameter: Any) -> Any:
            if isinstance(parameter, PhaseReference):
                return LazyPoint(
                    circle.center.x + circle.radius * parameter.cosine,
                    circle.center.y + circle.radius * parameter.sine,
                )
            return original_point_on_circle(circle, parameter)

        context["PointOnCircle"] = phase_point_on_circle
    evaluator = SymbolicEvaluator(context)
    for item in normalized["construction"]:
        name = str(item["name"])
        try:
            value = evaluator.visit(ast.parse(str(item["expr"]), mode="eval"))
        except Exception as error:
            raise UnsupportedFormulation(f"construction:{name}:{error}") from error
        if not isinstance(value, _GEOMETRY_TYPES + _SCALAR_TYPES):
            raise UnsupportedFormulation(f"construction:{name}:unsupported value type")
        context[name] = value
        evaluator.context[name] = value

    constraint_residuals: list[sp.Expr] = []
    for index, item in enumerate(normalized["constraints"]):
        left = evaluator.visit(ast.parse(str(item["def"]), mode="eval"))
        right = (
            evaluator.visit(ast.parse(str(item["value"]), mode="eval"))
            if isinstance(item.get("value"), str)
            else _exact_scalar(item.get("value"))
        )
        if isinstance(left, _GEOMETRY_TYPES) or isinstance(right, _GEOMETRY_TYPES):
            raise UnsupportedFormulation(f"constraint:{index}:not scalar")
        constraint_residuals.append(sp.sympify(left) - sp.sympify(right))

    guard_values: list[tuple[str, Any]] = []
    guard_evaluator = SymbolicEvaluator(_guard_context(context))
    for index, text in enumerate(normalized.get("guards", [])):
        try:
            value = guard_evaluator.visit(ast.parse(str(text), mode="eval"))
        except Exception as error:
            raise UnsupportedFormulation(f"guards[{index}]:{error}") from error
        guard_values.append((f"guards[{index}]", value))

    target_value = evaluator.visit(ast.parse(str(normalized["answer"]), mode="eval"))
    if isinstance(target_value, _GEOMETRY_TYPES):
        raise UnsupportedFormulation("answer is not scalar")

    lifter = AlgebraicLifter(symbols)
    for reference in phase_references.values():
        lifter.equations.append(reference.cosine**2 + reference.sine**2 - 1)
    lifted_constraints = [lifter.lift(expression) for expression in constraint_residuals]
    lifted_guards: list[tuple[str, str, sp.Expr, str]] = []
    for source, guard in guard_values:
        for relation, left, right, guard_source in _guard_atoms(guard, source=source):
            if relation == "false":
                raise UnsupportedFormulation(f"{source}:contradictory_guard")
            lifted_guards.append(
                (relation, source, lifter.lift(sp.sympify(left) - sp.sympify(right)), guard_source)
            )
    target_lifted = lifter.lift(sp.sympify(target_value))
    # Geometry constructor preconditions can contain radicals themselves.  We
    # must lift their expressions before constructing the ideal.
    for validation in state.validations:
        expression = validation.expression
        relation = validation.kind
        if relation == "nonzero_vector":
            if not isinstance(expression, tuple | list) or len(expression) != 2:
                raise UnsupportedFormulation(f"unsupported_validation_guard:{validation.source}")
            expression = sp.sympify(expression[0]) ** 2 + sp.sympify(expression[1]) ** 2
            relation = "nonzero"
        lifter.conditions.append((sp.sympify(expression), relation, validation.source))
    processed_conditions = 0
    while processed_conditions < len(lifter.conditions):
        expression, _relation, _source = lifter.conditions[processed_conditions]
        lifter.lift(expression)
        processed_conditions += 1
    validation_records = [
        (lifter.lift(expression), relation, source)
        for expression, relation, source in lifter.validation_conditions()
    ]
    variables = lifter.variables
    source_exprs = [*lifter.equations, *lifted_constraints]

    def _sympy_polynomial(polynomial: Polynomial) -> sp.Expr:
        return sum(
            sp.Rational(term.numerator, term.denominator)
            * math.prod(
                symbol**exponent for symbol, exponent in zip(variables, term.exponents, strict=True)
            )
            for term in polynomial.terms
        )

    base_polys = [
        _polynomial(expression, variables, label=f"equation:{index}")
        for index, expression in enumerate(source_exprs)
    ]
    if base_polys and variables:
        try:
            groebner = sp.groebner(
                [_sympy_polynomial(polynomial) for polynomial in base_polys],
                *variables,
                order="grevlex",
            )
        except Exception as error:
            raise UnsupportedFormulation(f"guard_ideal_failed:{error}") from error
        if not groebner.is_zero_dimensional:
            raise UnsupportedFormulation("positive_dimensional_source")
    else:
        groebner = None

    inequalities: list[SignCondition] = []
    for lifted, relation, source in validation_records:
        relation = {
            "nonzero": "!=",
            "nonnegative": ">=",
            "positive": ">",
        }.get(relation, relation)
        if relation not in {"eq", "ne", "!=", "<", "<=", ">", ">=", "nonnegative"}:
            raise UnsupportedFormulation(f"unsupported_validation_guard:{source}:{relation}")
        polynomial = _with_denominator_condition(lifted, variables, inequalities, source=source)
        inequalities.append(SignCondition(polynomial, relation, source))
    for relation, source, expression, guard_source in lifted_guards:
        polynomial = _with_denominator_condition(
            expression, variables, inequalities, source=guard_source
        )
        if relation == "eq":
            is_zero = not polynomial.terms
            implied = is_zero or (
                groebner is not None and groebner.reduce(_sympy_polynomial(polynomial))[1] == 0
            )
            if not implied:
                raise UnsupportedFormulation(f"{source}:independent_equality_guard")
        else:
            inequalities.append(SignCondition(polynomial, relation, guard_source))

    target_symbol = sp.Symbol("__hc_target")
    final_variables = [*variables, target_symbol]
    target_equation = _polynomial(target_symbol - target_lifted, final_variables, label="target")
    equations = [
        _polynomial(expression, final_variables, label=f"equation:{index}")
        for index, expression in enumerate(source_exprs)
    ]
    equations.append(target_equation)
    if len(equations) != len(final_variables):
        raise UnsupportedFormulation(
            f"non_square_system:equations={len(equations)},variables={len(final_variables)}"
        )
    final_width = len(final_variables)
    branch_count = max((selector.candidate_count for selector in state.selectors), default=1)
    admission = Admission(
        mode=mode,
        supported=True,
        stage="polynomialized",
        reasons=(),
        calls=_call_names(_expressions(normalized)),
        variable_count=final_width,
        equation_count=len(equations),
        branch_count=branch_count,
    )
    return Compilation(
        source_sha256=digest,
        mode=mode,
        variables=tuple(str(value) for value in final_variables),
        equations=[_pad_polynomial(equation, final_width) for equation in equations],
        inequalities=[
            SignCondition(
                _pad_polynomial(condition.polynomial, final_width),
                condition.relation,
                condition.source,
            )
            for condition in inequalities
        ],
        target_variable=str(target_symbol),
        target_expression=_pad_polynomial(
            _polynomial(target_lifted, final_variables, label="target_expression"), final_width
        ),
        admission=admission,
        metadata={
            "semantic_abi": "geotarget.homotopy-baseline/sympy-lift-v2",
            "construction_count": len(normalized["construction"]),
            "source_variable_count": len(original_names),
            "phase_variable_count": len(phase_names),
            "validation_count": len(state.validations),
            "selector_count": len(state.selectors),
            "source_constraint_count": source_constraint_count,
        },
    )


def admission_report(problem: Mapping[str, Any], *, mode: str = "core") -> Admission:
    try:
        compilation = compile_problem(problem, mode=mode)
    except UnsupportedFormulation as error:
        reasons: tuple[str, ...]
        try:
            payload = json.loads(str(error))
            reasons = tuple(str(value) for value in payload.get("reasons", []))
            if not reasons:
                reasons = (str(error),)
        except json.JSONDecodeError:
            reasons = (str(error),)
        return Admission(
            mode=mode,
            supported=False,
            stage="rejected",
            reasons=reasons,
            calls=_call_names(_expressions(problem)),
        )
    return compilation.admission


__all__ = [
    "Admission",
    "Compilation",
    "UnsupportedFormulation",
    "admission_report",
    "compile_problem",
]
