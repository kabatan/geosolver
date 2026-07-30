"""Independent exact verifier for target-constrained Hermite certificates.

The verifier intentionally does not import the candidate or recompute a
Groebner basis.  It verifies that the supplied multiplication matrices form a
faithful finite-dimensional regular representation annihilated by J, then
recomputes every Hermite/Tarski query exactly.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from typing import Any, Mapping, Sequence

import sympy as sp


class VerificationFailure(ValueError):
    pass


def _reject(reason: str) -> None:
    raise VerificationFailure(reason)


def _parse_expr(value: Any, symbols: Sequence[sp.Symbol], locals_: Mapping[str, sp.Symbol], label: str) -> sp.Expr:
    if not isinstance(value, (str, int, sp.Integer, sp.Rational)):
        _reject(f"invalid-{label}-encoding")
    try:
        expr = sp.sympify(value, locals=dict(locals_))
    except (sp.SympifyError, TypeError, ValueError):
        _reject(f"invalid-{label}-syntax")
    if expr.atoms(sp.Float) or not expr.free_symbols.issubset(set(symbols)):
        _reject(f"nonexact-{label}")
    try:
        return sp.Poly(sp.expand(expr), *symbols, domain=sp.QQ).as_expr()
    except (sp.PolynomialError, sp.CoercionFailed):
        _reject(f"non-qq-polynomial-{label}")


def _poly_encoding(expr: sp.Expr, symbols: Sequence[sp.Symbol]) -> list[list[Any]]:
    return [[list(monomial), str(coefficient)] for monomial, coefficient in sp.Poly(expr, *symbols, domain=sp.QQ).terms()]


def _parse_problem(problem: Mapping[str, Any]) -> dict[str, Any]:
    required = {"variables", "target_variable", "equations", "target", "polynomial", "interval", "guards"}
    if set(problem) != required:
        _reject("invalid-problem-fields")
    names = problem["variables"]
    if not isinstance(names, list) or not names or len(set(names)) != len(names):
        _reject("invalid-variables")
    if any(not isinstance(name, str) or not name.isidentifier() for name in names):
        _reject("invalid-variable-name")
    symbols = tuple(sp.Symbol(name) for name in names)
    locals_ = dict(zip(names, symbols, strict=True))
    if problem["target_variable"] not in locals_:
        _reject("unknown-target-variable")
    target_index = names.index(problem["target_variable"])
    if not isinstance(problem["equations"], list) or not isinstance(problem["guards"], list):
        _reject("invalid-equation-or-guard-list")
    equations = tuple(
        _parse_expr(value, symbols, locals_, f"equation-{index}")
        for index, value in enumerate(problem["equations"])
    )
    target = _parse_expr(problem["target"], symbols, locals_, "target")
    if symbols[target_index] in target.free_symbols:
        _reject("recursive-target-expression")
    polynomial_expr = _parse_expr(problem["polynomial"], symbols, locals_, "target-polynomial")
    if polynomial_expr.free_symbols - {symbols[target_index]}:
        _reject("multivariate-target-polynomial")
    polynomial = sp.Poly(polynomial_expr, symbols[target_index], domain=sp.QQ)
    guards = tuple(
        _parse_expr(value, symbols, locals_, f"guard-{index}")
        for index, value in enumerate(problem["guards"])
    )
    if not isinstance(problem["interval"], list) or len(problem["interval"]) != 2:
        _reject("invalid-interval")
    if any(isinstance(value, float) for value in problem["interval"]):
        _reject("inexact-interval")
    try:
        left, right = (sp.Rational(value) for value in problem["interval"])
    except (TypeError, ValueError, ZeroDivisionError):
        _reject("invalid-interval")
    if not left < right:
        _reject("unordered-interval")
    canonical = {
        "variables": names,
        "target_variable": problem["target_variable"],
        "equations": [_poly_encoding(expr, symbols) for expr in equations],
        "target": _poly_encoding(target, symbols),
        "polynomial": _poly_encoding(polynomial.as_expr(), symbols),
        "interval": [str(left), str(right)],
        "guards": [_poly_encoding(expr, symbols) for expr in guards],
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return {
        "names": tuple(names),
        "symbols": symbols,
        "target_index": target_index,
        "equations": equations,
        "target": target,
        "polynomial": polynomial,
        "interval": (left, right),
        "guards": guards,
        "digest": digest,
    }


def _matrix(value: Any, dimension: int, label: str) -> sp.Matrix:
    if not isinstance(value, list) or len(value) != dimension:
        _reject(f"invalid-{label}-rows")
    parsed: list[list[sp.Rational]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != dimension:
            _reject(f"invalid-{label}-columns")
        try:
            parsed.append([sp.Rational(cell) for cell in row])
        except (TypeError, ValueError, ZeroDivisionError):
            _reject(f"nonrational-{label}")
    return sp.Matrix(parsed)


def _eval_matrix(expr: sp.Expr, symbols: Sequence[sp.Symbol], matrices: Mapping[str, sp.Matrix]) -> sp.Matrix:
    dimension = next(iter(matrices.values())).rows
    out = sp.zeros(dimension)
    for monomial, coefficient in sp.Poly(expr, *symbols, domain=sp.QQ).terms():
        term = sp.eye(dimension) * coefficient
        for symbol, exponent in zip(symbols, monomial, strict=True):
            if exponent:
                term *= matrices[str(symbol)] ** exponent
        out += term
    return out


def _inertia(matrix: sp.Matrix) -> tuple[int, int, int]:
    if matrix.rows != matrix.cols or matrix != matrix.T:
        _reject("nonsymmetric-hermite")
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
            active = sp.zeros(0) if n == 1 else active[1:, 1:] - active[1:, 0] * active[1:, 0].T / pivot
            continue
        pair = next(
            ((row, column) for row in range(n) for column in range(row + 1, n) if active[row, column] != 0),
            None,
        )
        if pair is None:
            zero += n
            break
        order = [*pair, *(index for index in range(n) if index not in pair)]
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


def verify(problem: Mapping[str, Any], certificate: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _parse_problem(problem)
    if certificate.get("schema") != "target-constrained-hermite-certificate-v1":
        _reject("unknown-schema")
    if certificate.get("status") != "CERTIFIED_EXISTENCE":
        _reject("non-certificate-status")
    if certificate.get("method") != "exact-quotient-hermite-tarski-strict-conjunction":
        _reject("unexpected-method")
    if certificate.get("problem_sha256") != parsed["digest"]:
        _reject("problem-digest-mismatch")
    if certificate.get("coordinate_exactification") is not False:
        _reject("coordinate-exactification-contract-mismatch")

    p: sp.Poly = parsed["polynomial"]
    left, right = parsed["interval"]
    if p.degree() < 1 or sp.gcd(p, p.diff()).degree() != 0:
        _reject("target-polynomial-not-square-free")
    if p.eval(left) == 0 or p.eval(right) == 0 or int(p.count_roots(left, right)) != 1:
        _reject("invalid-target-isolator")
    if certificate.get("target") != {
        "variable": parsed["names"][parsed["target_index"]],
        "polynomial_degree": p.degree(),
        "isolating_interval": [str(left), str(right)],
        "isolated_real_root_count": 1,
    }:
        _reject("target-metadata-mismatch")

    quotient = certificate.get("quotient")
    if not isinstance(quotient, dict):
        _reject("missing-quotient")
    dimension = quotient.get("dimension")
    if not isinstance(dimension, int) or not (1 <= dimension <= 32):
        _reject("invalid-quotient-dimension")
    basis_raw = quotient.get("basis_monomials")
    variable_count = len(parsed["symbols"])
    if not isinstance(basis_raw, list) or len(basis_raw) != dimension:
        _reject("invalid-basis-size")
    basis: list[tuple[int, ...]] = []
    for monomial in basis_raw:
        if (
            not isinstance(monomial, list)
            or len(monomial) != variable_count
            or any(not isinstance(power, int) or power < 0 for power in monomial)
        ):
            _reject("invalid-basis-monomial")
        basis.append(tuple(monomial))
    if len(set(basis)) != dimension or basis[0] != (0,) * variable_count:
        _reject("invalid-basis-identity")

    matrices_raw = quotient.get("multiplication_matrices")
    if not isinstance(matrices_raw, dict) or set(matrices_raw) != set(parsed["names"]):
        _reject("invalid-multiplication-matrix-set")
    matrices = {
        name: _matrix(matrices_raw[name], dimension, f"multiplication-{name}") for name in parsed["names"]
    }
    for left_name, right_name in itertools.combinations(parsed["names"], 2):
        if matrices[left_name] * matrices[right_name] != matrices[right_name] * matrices[left_name]:
            _reject("noncommuting-multiplication-matrices")

    basis_matrices: list[sp.Matrix] = []
    for monomial in basis:
        value = sp.eye(dimension)
        for symbol, exponent in zip(parsed["symbols"], monomial, strict=True):
            if exponent:
                value *= matrices[str(symbol)] ** exponent
        basis_matrices.append(value)
    flattened = sp.Matrix.hstack(*(matrix.reshape(dimension * dimension, 1) for matrix in basis_matrices))
    if flattened.rank() != dimension:
        _reject("nonfaithful-basis-representation")

    # The advertised matrices must be the regular action on the advertised
    # basis, not merely an arbitrary representation satisfying J.
    for name in parsed["names"]:
        coordinate_matrix = matrices[name]
        for column, basis_matrix in enumerate(basis_matrices):
            expected = sp.zeros(dimension)
            for row in range(dimension):
                expected += coordinate_matrix[row, column] * basis_matrices[row]
            if coordinate_matrix * basis_matrix != expected:
                _reject("invalid-regular-representation-closure")

    target_symbol = parsed["symbols"][parsed["target_index"]]
    generators = (
        *parsed["equations"],
        target_symbol - parsed["target"],
        parsed["polynomial"].as_expr(),
    )
    for generator in generators:
        if _eval_matrix(generator, parsed["symbols"], matrices) != sp.zeros(dimension):
            _reject("generator-does-not-annihilate-representation")

    guards = (*parsed["guards"], target_symbol - left, right - target_symbol)
    if certificate.get("strict_guard_count") != len(guards):
        _reject("strict-guard-count-mismatch")
    queries = certificate.get("tarski_queries")
    expected_powers = set(itertools.product((1, 2), repeat=len(guards)))
    if not isinstance(queries, list) or len(queries) != len(expected_powers):
        _reject("invalid-query-count")
    seen: set[tuple[int, ...]] = set()
    signature_sum = 0
    for query in queries:
        if not isinstance(query, dict):
            _reject("invalid-query-record")
        powers_raw = query.get("powers")
        if not isinstance(powers_raw, list):
            _reject("invalid-query-powers")
        powers = tuple(powers_raw)
        if powers not in expected_powers or powers in seen:
            _reject("unexpected-or-duplicate-query")
        seen.add(powers)
        multiplier = sp.eye(dimension)
        for guard, power in zip(guards, powers, strict=True):
            multiplier *= _eval_matrix(guard, parsed["symbols"], matrices) ** power
        hermite = sp.zeros(dimension)
        for row in range(dimension):
            for column in range(row, dimension):
                value = sp.trace(multiplier * basis_matrices[row] * basis_matrices[column])
                hermite[row, column] = value
                hermite[column, row] = value
        supplied = _matrix(query.get("hermite"), dimension, "hermite")
        if supplied != hermite:
            _reject("hermite-matrix-mismatch")
        positive, negative, zero = _inertia(hermite)
        inertia = query.get("inertia")
        if inertia != {"positive": positive, "negative": negative, "zero": zero}:
            _reject("inertia-mismatch")
        signature = positive - negative
        if query.get("signature") != signature:
            _reject("signature-mismatch")
        signature_sum += signature
    if seen != expected_powers:
        _reject("incomplete-query-set")
    denominator = 1 << len(guards)
    if signature_sum % denominator:
        _reject("nonintegral-strict-count")
    positive_count = signature_sum // denominator
    if (
        positive_count <= 0
        or positive_count > dimension
        or certificate.get("strictly_feasible_real_root_count") != positive_count
    ):
        _reject("no-certified-strictly-feasible-root")

    return {
        "verified": True,
        "problem_sha256": parsed["digest"],
        "quotient_dimension": dimension,
        "strictly_feasible_real_root_count": positive_count,
        "coordinate_exactification": False,
    }


__all__ = ["VerificationFailure", "verify"]
