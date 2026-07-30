"""Strict, truth-free polynomial side-route prototype for V15 formulations."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import math
import multiprocessing
import queue
import time
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class PolynomialLimits:
    maximum_variables: int = 3
    maximum_total_degree: int = 4
    maximum_terms_per_equation: int = 16
    maximum_total_terms: int = 32
    maximum_coefficient_bits: int = 64
    maximum_solutions: int = 32


@dataclass(frozen=True)
class PolynomialPlan:
    applicable: bool
    reason: str
    variable_names: tuple[str, ...]
    equation_count: int
    maximum_total_degree: int
    total_terms: int


@dataclass(frozen=True)
class SymbolicAllocation:
    total_starts: int
    baseline_starts: int
    symbolic_slots: int


@dataclass(frozen=True)
class SymbolicRouteResult:
    plan: PolynomialPlan
    allocation: SymbolicAllocation
    status: str
    proposals: tuple[tuple[float, ...], ...]
    verified: tuple[tuple[float, ...], ...]
    verifier_calls: int
    symbolic_elapsed_seconds: float


class _UnsupportedPolynomial(ValueError):
    pass


def _sympy():
    try:
        import sympy
    except ImportError as error:
        raise _UnsupportedPolynomial("sympy_unavailable") from error
    return sympy


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _UnsupportedPolynomial("noninteger_literal")
    return value


def _ast_expression(node: ast.AST, environment: Mapping[str, object], sympy):
    if isinstance(node, ast.Expression):
        return _ast_expression(node.body, environment, sympy)
    if isinstance(node, ast.Constant):
        return sympy.Integer(_integer(node.value))
    if isinstance(node, ast.Name):
        if node.id not in environment:
            raise _UnsupportedPolynomial("unknown_symbol")
        return environment[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _ast_expression(node.operand, environment, sympy)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _ast_expression(node.left, environment, sympy)
        right = _ast_expression(node.right, environment, sympy)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Pow):
            exponent = _integer(node.right.value) if isinstance(node.right, ast.Constant) else None
            if exponent is None or exponent < 0:
                raise _UnsupportedPolynomial("nonpolynomial_power")
            return left**exponent
        if isinstance(node.op, ast.Div):
            if not isinstance(node.right, ast.Constant):
                raise _UnsupportedPolynomial("symbolic_division")
            denominator = _integer(node.right.value)
            if denominator == 0:
                raise _UnsupportedPolynomial("division_by_zero")
            return left / sympy.Integer(denominator)
    if isinstance(node, (ast.Call, ast.Attribute, ast.Compare, ast.BoolOp, ast.IfExp)):
        raise _UnsupportedPolynomial("nonpolynomial_or_branch_ast")
    raise _UnsupportedPolynomial("unsupported_ast")


def _parse_expression(text: str, environment: Mapping[str, object], sympy):
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as error:
        raise _UnsupportedPolynomial("syntax_error") from error
    return _ast_expression(tree, environment, sympy)


def _coefficient_bits(coefficient) -> int:
    numerator, denominator = coefficient.as_numer_denom()
    return max(abs(int(numerator)).bit_length(), abs(int(denominator)).bit_length())


def _build_polynomials(
    formulation: Mapping[str, object], limits: PolynomialLimits
):
    sympy = _sympy()
    variables = formulation.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(names, list) or not names or not all(isinstance(name, str) for name in names):
        raise _UnsupportedPolynomial("malformed_variables")
    variable_names = tuple(names)
    if len(set(variable_names)) != len(variable_names):
        raise _UnsupportedPolynomial("duplicate_variables")
    if len(variable_names) > limits.maximum_variables:
        raise _UnsupportedPolynomial("dimension_cap")
    symbols = tuple(sympy.Symbol(name, real=True) for name in variable_names)
    environment: dict[str, object] = dict(zip(variable_names, symbols, strict=True))

    construction = formulation.get("construction", [])
    if not isinstance(construction, list):
        raise _UnsupportedPolynomial("malformed_construction")
    for binding in construction:
        if not isinstance(binding, Mapping):
            raise _UnsupportedPolynomial("opaque_construction")
        name = binding.get("name")
        expression = binding.get("expr")
        if not isinstance(name, str) or not isinstance(expression, str) or name in environment:
            raise _UnsupportedPolynomial("malformed_construction")
        environment[name] = _parse_expression(expression, environment, sympy)

    constraints = formulation.get("constraints")
    if not isinstance(constraints, list) or len(constraints) != len(symbols):
        raise _UnsupportedPolynomial("non_square")
    polynomials = []
    maximum_degree = 0
    total_terms = 0
    for constraint in constraints:
        if not isinstance(constraint, Mapping) or not isinstance(constraint.get("def"), str):
            raise _UnsupportedPolynomial("malformed_constraint")
        left = _parse_expression(str(constraint["def"]), environment, sympy)
        raw_right = constraint.get("value")
        if isinstance(raw_right, str):
            right = _parse_expression(raw_right, environment, sympy)
        else:
            right = sympy.Integer(_integer(raw_right))
        try:
            polynomial = sympy.Poly(left - right, *symbols, domain=sympy.QQ)
        except (TypeError, ValueError, sympy.PolynomialError) as error:
            raise _UnsupportedPolynomial("not_polynomial_over_Q") from error
        if polynomial.is_zero:
            raise _UnsupportedPolynomial("identically_zero_equation")
        degree = int(polynomial.total_degree())
        terms = len(polynomial.terms())
        if degree > limits.maximum_total_degree:
            raise _UnsupportedPolynomial("degree_cap")
        if terms > limits.maximum_terms_per_equation:
            raise _UnsupportedPolynomial("terms_per_equation_cap")
        if any(
            _coefficient_bits(coefficient) > limits.maximum_coefficient_bits
            for coefficient in polynomial.coeffs()
        ):
            raise _UnsupportedPolynomial("coefficient_bits_cap")
        maximum_degree = max(maximum_degree, degree)
        total_terms += terms
        polynomials.append(polynomial)
    if total_terms > limits.maximum_total_terms:
        raise _UnsupportedPolynomial("total_terms_cap")
    return variable_names, symbols, tuple(polynomials), maximum_degree, total_terms


def detect_polynomial_plan(
    formulation: Mapping[str, object], limits: PolynomialLimits = PolynomialLimits()
) -> PolynomialPlan:
    try:
        names, _symbols, polynomials, degree, terms = _build_polynomials(formulation, limits)
    except _UnsupportedPolynomial as error:
        variables = formulation.get("variables") if isinstance(formulation, Mapping) else None
        names = variables.get("names") if isinstance(variables, Mapping) else ()
        safe_names = tuple(name for name in names if isinstance(name, str)) if isinstance(names, list) else ()
        constraints = formulation.get("constraints") if isinstance(formulation, Mapping) else None
        count = len(constraints) if isinstance(constraints, list) else 0
        return PolynomialPlan(False, str(error), safe_names, count, 0, 0)
    return PolynomialPlan(True, "strict_polynomial_over_Q", names, len(polynomials), degree, terms)


def allocate_symbolic_portfolio(
    total_starts: int, baseline_quota: float = 0.75
) -> SymbolicAllocation:
    if isinstance(total_starts, bool) or total_starts <= 0:
        raise ValueError("total_starts must be positive")
    if not math.isfinite(baseline_quota) or not 0.5 <= baseline_quota <= 1.0:
        raise ValueError("baseline_quota must be in [0.5, 1]")
    baseline = max(1, math.ceil(total_starts * baseline_quota))
    return SymbolicAllocation(total_starts, baseline, total_starts - baseline)


def _solve_child(formulation, limits: PolynomialLimits, channel) -> None:
    started = time.monotonic()
    try:
        _names, symbols, polynomials, _degree, _terms = _build_polynomials(formulation, limits)
        sympy = _sympy()
        expressions = tuple(polynomial.as_expr() for polynomial in polynomials)
        basis = sympy.groebner(expressions, *symbols, order="grevlex")
        if not basis.is_zero_dimensional:
            channel.put({"status": "positive_dimensional", "points": [], "elapsed": time.monotonic() - started})
            return
        roots = sympy.solve_poly_system(expressions, *symbols)
        if roots is None:
            roots = []
        if len(roots) > limits.maximum_solutions:
            channel.put({"status": "solution_cap", "points": [], "elapsed": time.monotonic() - started})
            return
        points: list[tuple[float, ...]] = []
        for root in roots:
            if len(root) != len(symbols) or any(value.is_real is not True for value in root):
                continue
            substitution = dict(zip(symbols, root, strict=True))
            if any(sympy.simplify(expression.subs(substitution)) != 0 for expression in expressions):
                continue
            numeric = tuple(float(sympy.N(value, 30)) for value in root)
            if all(math.isfinite(value) for value in numeric):
                points.append(numeric)
        channel.put({"status": "complete", "points": sorted(set(points)), "elapsed": time.monotonic() - started})
    except Exception as error:
        channel.put({"status": f"solver_failure:{type(error).__name__}", "points": [], "elapsed": time.monotonic() - started})


def _bounded_candidates(
    formulation: Mapping[str, object], limits: PolynomialLimits, timeout_seconds: float
) -> tuple[str, tuple[tuple[float, ...], ...], float]:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.0 or timeout_seconds > 2.0:
        raise ValueError("timeout_seconds must be in (0, 2]")
    context = multiprocessing.get_context("spawn")
    channel = context.Queue(maxsize=1)
    process = context.Process(target=_solve_child, args=(dict(formulation), limits, channel))
    started = time.monotonic()
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(0.25)
        return "symbolic_timeout", (), time.monotonic() - started
    try:
        document = channel.get(timeout=0.25)
    except queue.Empty:
        return "symbolic_worker_no_result", (), time.monotonic() - started
    points = tuple(tuple(float(value) for value in point) for point in document.get("points", ()))
    return str(document.get("status", "malformed")), points, time.monotonic() - started


def run_symbolic_side_route(
    formulation: Mapping[str, object],
    canonical_verifier: Callable[[Sequence[float]], bool],
    *,
    total_starts: int = 256,
    baseline_quota: float = 0.75,
    timeout_seconds: float = 0.5,
    limits: PolynomialLimits = PolynomialLimits(),
) -> SymbolicRouteResult:
    allocation = allocate_symbolic_portfolio(total_starts, baseline_quota)
    plan = detect_polynomial_plan(formulation, limits)
    if not plan.applicable or allocation.symbolic_slots == 0:
        return SymbolicRouteResult(plan, allocation, "baseline_only", (), (), 0, 0.0)
    status, proposals, elapsed = _bounded_candidates(formulation, limits, timeout_seconds)
    verified: list[tuple[float, ...]] = []
    verifier_calls = 0
    for proposal in proposals:
        verifier_calls += 1
        try:
            accepted = canonical_verifier(proposal)
        except Exception:
            accepted = False
        if accepted:
            verified.append(proposal)
    return SymbolicRouteResult(
        plan,
        allocation,
        status,
        proposals,
        tuple(verified),
        verifier_calls,
        elapsed,
    )
