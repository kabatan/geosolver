"""Exact target-constrained Hermite/Tarski existence certificates.

This D0 candidate deliberately starts *after* semantic lifting.  Its input is a
small exact QQ polynomial problem and a proposed target polynomial/isolator.
It never reconstructs, rounds, or exactifies individual coordinates.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import sympy as sp


MAX_VARIABLES = 6
MAX_EQUATIONS = 10
MAX_RAW_GUARDS = 4
MAX_INPUT_DEGREE = 10
MAX_QUOTIENT_DIMENSION = 32


class CertificationFailure(ValueError):
    """A truth-blind, fail-closed inapplicability/certification result."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ParsedProblem:
    variable_names: tuple[str, ...]
    symbols: tuple[sp.Symbol, ...]
    target_index: int
    equations: tuple[sp.Expr, ...]
    target: sp.Expr
    polynomial: sp.Poly
    interval: tuple[sp.Rational, sp.Rational]
    guards: tuple[sp.Expr, ...]
    canonical_bytes: bytes

    @property
    def target_symbol(self) -> sp.Symbol:
        return self.symbols[self.target_index]

    @property
    def problem_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


def _fail(reason: str) -> None:
    raise CertificationFailure(reason)


def _rational(value: Any, label: str) -> sp.Rational:
    if isinstance(value, float):
        _fail(f"inexact-{label}")
    try:
        out = sp.Rational(value)
    except (TypeError, ValueError, ZeroDivisionError):
        _fail(f"invalid-{label}")
    return out


def _polynomial_expr(
    value: Any,
    symbols: Sequence[sp.Symbol],
    local_dict: Mapping[str, sp.Symbol],
    label: str,
) -> sp.Expr:
    if not isinstance(value, (str, int, sp.Integer, sp.Rational)):
        _fail(f"invalid-{label}-encoding")
    try:
        expr = sp.sympify(value, locals=dict(local_dict))
    except (sp.SympifyError, TypeError, ValueError):
        _fail(f"invalid-{label}-syntax")
    if expr.atoms(sp.Float):
        _fail(f"inexact-{label}")
    if not expr.free_symbols.issubset(set(symbols)):
        _fail(f"undeclared-symbol-in-{label}")
    try:
        poly = sp.Poly(sp.expand(expr), *symbols, domain=sp.QQ)
    except (sp.PolynomialError, sp.CoercionFailed, AttributeError, TypeError, ValueError):
        _fail(f"non-qq-polynomial-{label}")
    if poly.total_degree() > MAX_INPUT_DEGREE:
        _fail(f"degree-cap-{label}")
    return poly.as_expr()


def _poly_encoding(expr: sp.Expr, symbols: Sequence[sp.Symbol]) -> list[list[Any]]:
    poly = sp.Poly(expr, *symbols, domain=sp.QQ)
    return [[list(monomial), str(coefficient)] for monomial, coefficient in poly.terms()]


def parse_problem(problem: Mapping[str, Any]) -> ParsedProblem:
    required = {"variables", "target_variable", "equations", "target", "polynomial", "interval", "guards"}
    if set(problem) != required:
        _fail("invalid-problem-fields")

    names_raw = problem["variables"]
    if not isinstance(names_raw, list) or not (1 <= len(names_raw) <= MAX_VARIABLES):
        _fail("invalid-variable-count")
    if any(not isinstance(name, str) or not name.isidentifier() for name in names_raw):
        _fail("invalid-variable-name")
    if len(set(names_raw)) != len(names_raw):
        _fail("duplicate-variable")
    names = tuple(names_raw)
    symbols = tuple(sp.Symbol(name) for name in names)
    local_dict = dict(zip(names, symbols, strict=True))

    target_name = problem["target_variable"]
    if target_name not in local_dict:
        _fail("unknown-target-variable")
    target_index = names.index(target_name)

    equations_raw = problem["equations"]
    guards_raw = problem["guards"]
    if not isinstance(equations_raw, list) or len(equations_raw) > MAX_EQUATIONS:
        _fail("invalid-equation-count")
    if not isinstance(guards_raw, list) or len(guards_raw) > MAX_RAW_GUARDS:
        _fail("invalid-guard-count")

    equations = tuple(
        _polynomial_expr(value, symbols, local_dict, f"equation-{index}")
        for index, value in enumerate(equations_raw)
    )
    target = _polynomial_expr(problem["target"], symbols, local_dict, "target")
    if symbols[target_index] in target.free_symbols:
        _fail("recursive-target-expression")
    guards = tuple(
        _polynomial_expr(value, symbols, local_dict, f"guard-{index}")
        for index, value in enumerate(guards_raw)
    )

    polynomial_expr = _polynomial_expr(problem["polynomial"], symbols, local_dict, "target-polynomial")
    if polynomial_expr.free_symbols - {symbols[target_index]}:
        _fail("multivariate-target-polynomial")
    try:
        polynomial = sp.Poly(polynomial_expr, symbols[target_index], domain=sp.QQ)
    except (sp.PolynomialError, sp.CoercionFailed):
        _fail("invalid-target-polynomial")
    if polynomial.degree() < 1:
        _fail("constant-target-polynomial")

    interval_raw = problem["interval"]
    if not isinstance(interval_raw, list) or len(interval_raw) != 2:
        _fail("invalid-isolating-interval")
    left = _rational(interval_raw[0], "interval-left")
    right = _rational(interval_raw[1], "interval-right")
    if not left < right:
        _fail("unordered-isolating-interval")

    canonical = {
        "variables": list(names),
        "target_variable": target_name,
        "equations": [_poly_encoding(expr, symbols) for expr in equations],
        "target": _poly_encoding(target, symbols),
        "polynomial": _poly_encoding(polynomial.as_expr(), symbols),
        "interval": [str(left), str(right)],
        "guards": [_poly_encoding(expr, symbols) for expr in guards],
    }
    canonical_bytes = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("ascii")
    return ParsedProblem(
        variable_names=names,
        symbols=symbols,
        target_index=target_index,
        equations=equations,
        target=target,
        polynomial=polynomial,
        interval=(left, right),
        guards=guards,
        canonical_bytes=canonical_bytes,
    )


def _check_target_proposal(parsed: ParsedProblem) -> int:
    p = parsed.polynomial
    if sp.gcd(p, p.diff()).degree() != 0:
        _fail("target-polynomial-not-square-free")
    left, right = parsed.interval
    if p.eval(left) == 0 or p.eval(right) == 0:
        _fail("isolating-interval-endpoint-is-root")
    try:
        count = int(p.count_roots(left, right))
    except (NotImplementedError, ValueError):
        _fail("target-root-count-failed")
    if count != 1:
        _fail("isolating-interval-not-single-real-root")
    return count


def _is_unit_ideal(groebner: sp.GroebnerBasis) -> bool:
    return len(groebner.polys) == 1 and groebner.polys[0].as_expr() == 1


def _standard_monomials(
    leading_monomials: Sequence[tuple[int, ...]],
    variable_count: int,
) -> list[tuple[int, ...]]:
    pure_bounds: list[int] = []
    for variable in range(variable_count):
        candidates = [
            lm[variable]
            for lm in leading_monomials
            if lm[variable] > 0 and all(power == 0 for index, power in enumerate(lm) if index != variable)
        ]
        if not candidates:
            _fail("missing-zero-dimensional-pure-power")
        pure_bounds.append(min(candidates))
    rectangular_size = 1
    for bound in pure_bounds:
        rectangular_size *= bound
    if rectangular_size > 8 * MAX_QUOTIENT_DIMENSION:
        _fail("standard-monomial-enumeration-cap")

    basis = [
        exponents
        for exponents in itertools.product(*(range(bound) for bound in pure_bounds))
        if not any(all(a >= b for a, b in zip(exponents, lm, strict=True)) for lm in leading_monomials)
    ]
    basis.sort(key=lambda exponents: (sum(exponents), exponents))
    if not basis or len(basis) > MAX_QUOTIENT_DIMENSION:
        _fail("quotient-dimension-cap")
    return basis


def _monomial_expr(symbols: Sequence[sp.Symbol], exponents: Sequence[int]) -> sp.Expr:
    out: sp.Expr = sp.Integer(1)
    for symbol, exponent in zip(symbols, exponents, strict=True):
        out *= symbol**exponent
    return out


def _remainder_coordinates(
    groebner: sp.GroebnerBasis,
    expr: sp.Expr,
    symbols: Sequence[sp.Symbol],
    basis_index: Mapping[tuple[int, ...], int],
) -> list[sp.Rational]:
    try:
        remainder = groebner.reduce(expr)[1]
        terms = sp.Poly(remainder, *symbols, domain=sp.QQ).terms()
    except (sp.PolynomialError, sp.CoercionFailed):
        _fail("groebner-remainder-failed")
    coordinates = [sp.Rational(0)] * len(basis_index)
    for monomial, coefficient in terms:
        if monomial not in basis_index:
            _fail("remainder-outside-standard-basis")
        coordinates[basis_index[monomial]] = sp.Rational(coefficient)
    return coordinates


def _multiplication_matrices(
    groebner: sp.GroebnerBasis,
    symbols: Sequence[sp.Symbol],
    basis: Sequence[tuple[int, ...]],
) -> dict[str, sp.Matrix]:
    dimension = len(basis)
    basis_index = {monomial: index for index, monomial in enumerate(basis)}
    basis_exprs = [_monomial_expr(symbols, monomial) for monomial in basis]
    matrices: dict[str, sp.Matrix] = {}
    for symbol in symbols:
        matrix = sp.zeros(dimension)
        for column, basis_expr in enumerate(basis_exprs):
            coordinates = _remainder_coordinates(groebner, symbol * basis_expr, symbols, basis_index)
            for row, coefficient in enumerate(coordinates):
                matrix[row, column] = coefficient
        matrices[str(symbol)] = matrix
    return matrices


def _evaluate_at_matrices(
    expr: sp.Expr,
    symbols: Sequence[sp.Symbol],
    multiplication: Mapping[str, sp.Matrix],
) -> sp.Matrix:
    dimension = next(iter(multiplication.values())).rows
    out = sp.zeros(dimension)
    poly = sp.Poly(expr, *symbols, domain=sp.QQ)
    for monomial, coefficient in poly.terms():
        term = sp.eye(dimension) * coefficient
        for symbol, exponent in zip(symbols, monomial, strict=True):
            if exponent:
                term *= multiplication[str(symbol)] ** exponent
        out += term
    return out


def _basis_matrices(
    basis: Sequence[tuple[int, ...]],
    symbols: Sequence[sp.Symbol],
    multiplication: Mapping[str, sp.Matrix],
) -> list[sp.Matrix]:
    dimension = len(basis)
    out: list[sp.Matrix] = []
    for monomial in basis:
        matrix = sp.eye(dimension)
        for symbol, exponent in zip(symbols, monomial, strict=True):
            if exponent:
                matrix *= multiplication[str(symbol)] ** exponent
        out.append(matrix)
    return out


def _exact_inertia(matrix: sp.Matrix) -> tuple[int, int, int]:
    """Exact symmetric LDL congruence, including zero-diagonal 2x2 pivots."""

    if matrix.rows != matrix.cols or matrix != matrix.T:
        _fail("nonsymmetric-hermite-matrix")
    active = sp.Matrix(matrix)
    positive = negative = zero = 0
    while active.rows:
        n = active.rows
        diagonal = next((index for index in range(n) if active[index, index] != 0), None)
        if diagonal is not None:
            order = [diagonal] + [index for index in range(n) if index != diagonal]
            active = active.extract(order, order)
            pivot = active[0, 0]
            if pivot > 0:
                positive += 1
            else:
                negative += 1
            if n == 1:
                active = sp.zeros(0)
            else:
                column = active[1:, 0]
                active = active[1:, 1:] - column * column.T / pivot
            continue

        off_diagonal: tuple[int, int] | None = None
        for row in range(n):
            for column in range(row + 1, n):
                if active[row, column] != 0:
                    off_diagonal = (row, column)
                    break
            if off_diagonal is not None:
                break
        if off_diagonal is None:
            zero += n
            break

        first, second = off_diagonal
        order = [first, second] + [index for index in range(n) if index not in (first, second)]
        active = active.extract(order, order)
        positive += 1
        negative += 1
        if n == 2:
            active = sp.zeros(0)
        else:
            pivot = active[:2, :2]
            coupling = active[:2, 2:]
            active = active[2:, 2:] - coupling.T * pivot.inv() * coupling
    return positive, negative, zero


def _matrix_encoding(matrix: sp.Matrix) -> list[list[str]]:
    return [[str(sp.Rational(matrix[row, column])) for column in range(matrix.cols)] for row in range(matrix.rows)]


def certify(problem: Mapping[str, Any]) -> dict[str, Any]:
    """Return an independently checkable exact certificate or fail closed."""

    parsed = parse_problem(problem)
    isolated_root_count = _check_target_proposal(parsed)
    target_equation = parsed.target_symbol - parsed.target
    generators = (*parsed.equations, target_equation, parsed.polynomial.as_expr())
    try:
        groebner = sp.groebner(generators, *parsed.symbols, order="grevlex", domain=sp.QQ)
    except (sp.PolynomialError, sp.CoercionFailed, NotImplementedError):
        _fail("groebner-construction-failed")
    if _is_unit_ideal(groebner):
        _fail("inconsistent-target-fibre")
    if not groebner.is_zero_dimensional:
        _fail("target-fibre-not-zero-dimensional")

    leading = [tuple(poly.LM(order=groebner.order).exponents) for poly in groebner.polys]
    basis = _standard_monomials(leading, len(parsed.symbols))
    multiplication = _multiplication_matrices(groebner, parsed.symbols, basis)
    basis_matrices = _basis_matrices(basis, parsed.symbols, multiplication)
    dimension = len(basis)

    left, right = parsed.interval
    interval_guards = (parsed.target_symbol - left, right - parsed.target_symbol)
    all_guards = (*parsed.guards, *interval_guards)
    query_records: list[dict[str, Any]] = []
    signature_sum = 0
    for powers in itertools.product((1, 2), repeat=len(all_guards)):
        multiplier = sp.eye(dimension)
        for guard, power in zip(all_guards, powers, strict=True):
            multiplier *= _evaluate_at_matrices(guard, parsed.symbols, multiplication) ** power
        hermite = sp.zeros(dimension)
        for row in range(dimension):
            for column in range(row, dimension):
                value = sp.trace(multiplier * basis_matrices[row] * basis_matrices[column])
                hermite[row, column] = value
                hermite[column, row] = value
        positive, negative, zero = _exact_inertia(hermite)
        signature = positive - negative
        signature_sum += signature
        query_records.append(
            {
                "powers": list(powers),
                "hermite": _matrix_encoding(hermite),
                "inertia": {"positive": positive, "negative": negative, "zero": zero},
                "signature": signature,
            }
        )

    denominator = 1 << len(all_guards)
    if signature_sum % denominator:
        _fail("nonintegral-strict-sign-count")
    positive_root_count = signature_sum // denominator
    if positive_root_count <= 0:
        _fail("no-root-satisfies-strict-guards")

    return {
        "schema": "target-constrained-hermite-certificate-v1",
        "status": "CERTIFIED_EXISTENCE",
        "problem_sha256": parsed.problem_sha256,
        "method": "exact-quotient-hermite-tarski-strict-conjunction",
        "target": {
            "variable": parsed.variable_names[parsed.target_index],
            "polynomial_degree": parsed.polynomial.degree(),
            "isolating_interval": [str(left), str(right)],
            "isolated_real_root_count": isolated_root_count,
        },
        "quotient": {
            "dimension": dimension,
            "basis_monomials": [list(monomial) for monomial in basis],
            "multiplication_matrices": {
                name: _matrix_encoding(matrix) for name, matrix in multiplication.items()
            },
            "groebner_diagnostic": {
                "order": "grevlex",
                "basis": [sp.sstr(poly.as_expr()) for poly in groebner.polys],
                "leading_monomials": [list(monomial) for monomial in leading],
            },
        },
        "strict_guard_count": len(all_guards),
        "tarski_queries": query_records,
        "strictly_feasible_real_root_count": positive_root_count,
        "coordinate_exactification": False,
    }


__all__ = ["CertificationFailure", "certify", "parse_problem"]
