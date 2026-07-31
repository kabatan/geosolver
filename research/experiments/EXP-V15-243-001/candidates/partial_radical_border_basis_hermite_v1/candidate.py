"""Disposable partial-radical border-basis/Hermite existence witness.

Approximate points propose rational moments.  Authority comes only from exact
border-basis, generator, trace, descriptor, and Hermite/Tarski checks.
"""

from __future__ import annotations

from fractions import Fraction
import hashlib
import itertools
import json
import math
from typing import Any, Iterable, Mapping, Sequence

import mpmath as mp
import sympy as sp


SCHEMA = "geotarget.partial-radical-border-basis-hermite-problem/v1"
CERT_SCHEMA = "geotarget.partial-radical-border-basis-hermite-certificate/v1"
MAX_VARIABLES = 8
MAX_K = 8
MAX_EQUATIONS = 16
MAX_PREDICATES = 12
MAX_DEGREE = 6
MAX_TERMS = 160
MAX_TARGET_DEGREE = 4
MAX_COORDINATE = mp.mpf(128)
MIN_PRECISION_BITS = 53
MAX_PRECISION_BITS = 256
MAX_DENOMINATOR = 4096
RECONSTRUCTION_TOLERANCE = mp.mpf(2) ** -30
CLUSTER_SEPARATION = mp.mpf(2) ** -24
MAX_QUERY_TERMS = 4096
SEPARATOR_PANELS = (
    (1, 2, 4, 8, 16, 32, 64, 128),
    (1, 3, 9, 27, 81, 243, 729, 2187),
    (1, 5, 11, 23, 47, 95, 191, 383),
)


class NotCertified(ValueError):
    pass


def _reject(reason: str) -> None:
    raise NotCertified(reason)


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _rational(value: object) -> sp.Rational:
    try:
        result = sp.Rational(str(value))
    except (TypeError, ValueError, ZeroDivisionError):
        _reject("malformed-rational")
    return result


def _parse_complex(value: object) -> mp.mpc:
    if not isinstance(value, list) or len(value) != 2:
        _reject("malformed-cluster-coordinate")
    try:
        result = mp.mpc(str(value[0]), str(value[1]))
    except (TypeError, ValueError):
        _reject("malformed-cluster-coordinate")
    if not mp.isfinite(result.real) or not mp.isfinite(result.imag):
        _reject("nonfinite-cluster-coordinate")
    if abs(result) > MAX_COORDINATE:
        _reject("cluster-coordinate-cap")
    return result


def _poly(
    text: object,
    symbols: Sequence[sp.Symbol],
    *,
    allow_zero: bool = True,
) -> sp.Poly:
    if not isinstance(text, str):
        _reject("polynomial-is-not-text")
    local = {symbol.name: symbol for symbol in symbols}
    try:
        expression = sp.sympify(text, locals=local)
        polynomial = sp.Poly(expression, *symbols, domain=sp.QQ)
    except (sp.PolynomialError, sp.CoercionFailed, TypeError, ValueError):
        _reject("non-QQ-polynomial")
    if polynomial.total_degree() > MAX_DEGREE or len(polynomial.terms()) > MAX_TERMS:
        _reject("polynomial-cap")
    if not allow_zero and polynomial.is_zero:
        _reject("zero-polynomial")
    return polynomial


def _primitive_descriptor(value: object) -> tuple[sp.Poly, int, sp.Rational, sp.Rational]:
    if not isinstance(value, Mapping):
        _reject("descriptor-missing")
    coefficients = value.get("minimal_polynomial_high_to_low")
    ordinal = value.get("selected_real_root_index")
    if (
        not isinstance(coefficients, list)
        or not 2 <= len(coefficients) <= MAX_TARGET_DEGREE + 1
        or any(not isinstance(item, int) or isinstance(item, bool) for item in coefficients)
        or not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or ordinal < 0
    ):
        _reject("descriptor-shape")
    target_symbol = sp.Symbol("__target_descriptor")
    polynomial = sp.Poly.from_list(coefficients, gens=target_symbol, domain=sp.ZZ)
    content, primitive = polynomial.primitive()
    if content not in {1, -1} or primitive.LC() <= 0 or primitive != polynomial:
        _reject("descriptor-not-primitive-leading-positive")
    if sp.gcd(polynomial, polynomial.diff()).degree() != 0:
        _reject("descriptor-not-square-free")
    if not polynomial.is_irreducible:
        _reject("descriptor-not-irreducible")
    interval = value.get("isolating_interval")
    if not isinstance(interval, Mapping):
        _reject("descriptor-isolator-missing")
    left = _rational(interval.get("left"))
    right = _rational(interval.get("right"))
    if not left < right or polynomial.count_roots(left, right) != 1:
        _reject("descriptor-isolator-not-unique")
    try:
        below = int(polynomial.count_roots(-sp.oo, left))
    except Exception:
        intervals = polynomial.intervals(eps=sp.Rational(1, 10**12))
        below = sum(int(multiplicity) for (lo, hi), multiplicity in intervals if hi <= left)
    if below != ordinal:
        _reject("descriptor-factor-local-ordinal")
    return polynomial, ordinal, left, right


def _parse_problem(problem: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(problem, Mapping) or problem.get("schema_version") != SCHEMA:
        _reject("problem-schema")
    precision = problem.get("precision_bits")
    variables = problem.get("variables")
    equations = problem.get("equations")
    predicates = problem.get("predicates")
    cluster = problem.get("approximate_cluster")
    box = problem.get("proposal_box")
    if (
        not isinstance(precision, int)
        or isinstance(precision, bool)
        or not MIN_PRECISION_BITS <= precision <= MAX_PRECISION_BITS
    ):
        _reject("precision-cap")
    if (
        not isinstance(variables, list)
        or not 1 <= len(variables) <= MAX_VARIABLES
        or not all(isinstance(item, str) and item.isidentifier() for item in variables)
        or len(set(variables)) != len(variables)
    ):
        _reject("variable-ledger")
    if (
        not isinstance(equations, list)
        or not 1 <= len(equations) <= MAX_EQUATIONS
        or problem.get("complete_equality_ledger") is not True
        or problem.get("source_fibre_equality_count") != len(equations)
    ):
        _reject("incomplete-equality-ledger")
    if (
        not isinstance(predicates, list)
        or len(predicates) > MAX_PREDICATES
        or problem.get("complete_predicate_ledger") is not True
        or problem.get("predicate_ledger_count") != len(predicates)
    ):
        _reject("incomplete-predicate-ledger")
    kind_counts = {"guard": 0, "definedness": 0, "branch": 0}
    for item in predicates:
        if not isinstance(item, Mapping) or item.get("kind") not in kind_counts:
            _reject("predicate-kind-ledger")
        if item.get("relation") not in {"gt", "ge", "lt", "le", "ne", "eq"}:
            _reject("predicate-relation")
        kind_counts[str(item["kind"])] += 1
    for kind, count in kind_counts.items():
        if problem.get(f"{kind}_predicate_count") != count:
            _reject("predicate-accounting-mismatch")
    if (
        not isinstance(cluster, list)
        or not 1 <= len(cluster) <= MAX_K
        or problem.get("cluster_declared_count") != len(cluster)
        or problem.get("cluster_padded") is not False
    ):
        _reject("cluster-count-or-padding")
    if not isinstance(box, list) or len(box) != len(variables):
        _reject("proposal-box-shape")
    symbols = tuple(sp.Symbol(name, real=True) for name in variables)
    parsed_equations = tuple(_poly(item, symbols, allow_zero=False) for item in equations)
    parsed_predicates = []
    for item in predicates:
        parsed_predicates.append(
            {
                "polynomial": _poly(item.get("expression"), symbols),
                "relation": str(item["relation"]),
                "kind": str(item["kind"]),
                "source": str(item.get("source", "")),
            }
        )
    target = _poly(problem.get("raw_target"), symbols)
    descriptor = _primitive_descriptor(problem.get("descriptor"))
    parsed_box = []
    for item in box:
        if not isinstance(item, list) or len(item) != 2:
            _reject("proposal-box-shape")
        lower, upper = _rational(item[0]), _rational(item[1])
        if not lower < upper:
            _reject("proposal-box-empty")
        parsed_box.append((lower, upper))
    mp.mp.prec = precision
    parsed_cluster = []
    for point in cluster:
        if not isinstance(point, list) or len(point) != len(symbols):
            _reject("cluster-point-dimension")
        parsed_cluster.append(tuple(_parse_complex(item) for item in point))
    for first, second in itertools.combinations(parsed_cluster, 2):
        if max(abs(a - b) for a, b in zip(first, second, strict=True)) <= CLUSTER_SEPARATION:
            _reject("duplicated-or-padded-cluster")
    return {
        "problem": dict(problem),
        "problem_sha256": _canonical_sha(problem),
        "precision": precision,
        "variables": tuple(variables),
        "symbols": symbols,
        "equations": parsed_equations,
        "predicates": tuple(parsed_predicates),
        "target": target,
        "descriptor": descriptor,
        "cluster": tuple(parsed_cluster),
        "box": tuple(parsed_box),
    }


def _monomial_value(exponents: tuple[int, ...], point: Sequence[mp.mpc]) -> mp.mpc:
    value = mp.mpc(1)
    for coordinate, exponent in zip(point, exponents, strict=True):
        if exponent:
            value *= coordinate**exponent
    return value


def _reconstruct(value: mp.mpc) -> sp.Rational:
    if abs(value.imag) >= RECONSTRUCTION_TOLERANCE:
        _reject("moment-not-rational-imaginary-part")
    candidate = Fraction(str(value.real)).limit_denominator(MAX_DENOMINATOR)
    reconstructed = mp.mpf(candidate.numerator) / candidate.denominator
    if abs(value.real - reconstructed) >= RECONSTRUCTION_TOLERANCE:
        _reject("moment-rational-reconstruction-failed")
    return sp.Rational(candidate.numerator, candidate.denominator)


def _basis(k: int, variable_count: int, separator: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(power if index == separator else 0 for index in range(variable_count))
        for power in range(k)
    )


def _extension(
    basis: Sequence[tuple[int, ...]], variable_count: int
) -> tuple[tuple[int, ...], ...]:
    result = set(basis)
    for monomial in basis:
        for index in range(variable_count):
            lifted = list(monomial)
            lifted[index] += 1
            result.add(tuple(lifted))
    return tuple(sorted(result, key=lambda item: (sum(item), item)))


def _matrix_encode(matrix: sp.Matrix) -> list[list[str]]:
    return [[str(sp.Rational(matrix[row, col])) for col in range(matrix.cols)] for row in range(matrix.rows)]


def _matrix_decode(value: object, rows: int, columns: int) -> sp.Matrix:
    if not isinstance(value, list) or len(value) != rows:
        _reject("matrix-shape")
    parsed = []
    for row in value:
        if not isinstance(row, list) or len(row) != columns:
            _reject("matrix-shape")
        parsed.append([_rational(item) for item in row])
    return sp.Matrix(parsed)


def _evaluate_polynomial(polynomial: sp.Poly, matrices: Sequence[sp.Matrix]) -> sp.Matrix:
    dimension = matrices[0].rows
    result = sp.zeros(dimension)
    for powers, coefficient in polynomial.terms():
        term = sp.eye(dimension) * coefficient
        for matrix, exponent in zip(matrices, powers, strict=True):
            if exponent:
                term *= matrix**exponent
        result += term
    return result


def _monomial_matrix(exponents: Sequence[int], matrices: Sequence[sp.Matrix]) -> sp.Matrix:
    result = sp.eye(matrices[0].rows)
    for matrix, exponent in zip(matrices, exponents, strict=True):
        if exponent:
            result *= matrix**exponent
    return result


def _exact_inertia(matrix: sp.Matrix) -> tuple[int, int, int]:
    if matrix.rows != matrix.cols or matrix != matrix.T:
        _reject("nonsymmetric-hermite-matrix")
    active = sp.Matrix(matrix)
    positive = negative = zero = 0
    while active.rows:
        size = active.rows
        diagonal = next((index for index in range(size) if active[index, index] != 0), None)
        if diagonal is not None:
            order = [diagonal] + [index for index in range(size) if index != diagonal]
            active = active.extract(order, order)
            pivot = active[0, 0]
            if pivot > 0:
                positive += 1
            else:
                negative += 1
            if size == 1:
                active = sp.zeros(0)
            else:
                column = active[1:, 0]
                active = active[1:, 1:] - column * column.T / pivot
            continue
        pair = next(
            (
                (row, column)
                for row in range(size)
                for column in range(row + 1, size)
                if active[row, column] != 0
            ),
            None,
        )
        if pair is None:
            zero += size
            break
        first, second = pair
        order = [first, second] + [index for index in range(size) if index not in pair]
        active = active.extract(order, order)
        positive += 1
        negative += 1
        if size == 2:
            active = sp.zeros(0)
        else:
            pivot = active[:2, :2]
            coupling = active[:2, 2:]
            active = active[2:, 2:] - coupling.T * pivot.inv() * coupling
    return positive, negative, zero


def _indicator_terms(relations: Sequence[str]) -> dict[tuple[int, ...], sp.Rational]:
    terms: dict[tuple[int, ...], sp.Rational] = {(): sp.Integer(1)}
    factors = {
        "gt": {1: sp.Rational(1, 2), 2: sp.Rational(1, 2)},
        "ge": {0: sp.Integer(1), 1: sp.Rational(1, 2), 2: sp.Rational(-1, 2)},
        "ne": {2: sp.Integer(1)},
        "eq": {0: sp.Integer(1), 2: sp.Integer(-1)},
    }
    for relation in relations:
        updated: dict[tuple[int, ...], sp.Rational] = {}
        for prefix, coefficient in terms.items():
            for power, factor in factors[relation].items():
                key = (*prefix, power)
                updated[key] = updated.get(key, sp.Integer(0)) + coefficient * factor
        terms = {key: value for key, value in updated.items() if value}
        if len(terms) > MAX_QUERY_TERMS:
            _reject("tarski-query-term-cap")
    return terms


def _normalized_predicates(parsed: Mapping[str, Any]) -> tuple[tuple[sp.Poly, str], ...]:
    result = []
    for item in parsed["predicates"]:
        polynomial, relation = item["polynomial"], item["relation"]
        if relation == "lt":
            polynomial, relation = -polynomial, "gt"
        elif relation == "le":
            polynomial, relation = -polynomial, "ge"
        result.append((polynomial, relation))
    symbols = parsed["symbols"]
    center = [(lower + upper) / 2 for lower, upper in parsed["box"]]
    radius = min((upper - lower) / 2 for lower, upper in parsed["box"])
    ball = radius**2 - sum((symbol - value) ** 2 for symbol, value in zip(symbols, center, strict=True))
    result.append((sp.Poly(ball, *symbols, domain=sp.QQ), "gt"))
    _target_poly, _ordinal, left, right = parsed["descriptor"]
    target_expression = parsed["target"].as_expr()
    result.append((sp.Poly(target_expression - left, *symbols, domain=sp.QQ), "gt"))
    result.append((sp.Poly(right - target_expression, *symbols, domain=sp.QQ), "gt"))
    return tuple(result)


def _tarski_count(
    parsed: Mapping[str, Any],
    basis: Sequence[tuple[int, ...]],
    matrices: Sequence[sp.Matrix],
) -> tuple[int, int]:
    predicates = _normalized_predicates(parsed)
    relations = [relation for _polynomial, relation in predicates]
    terms = _indicator_terms(relations)
    evaluated = [_evaluate_polynomial(polynomial, matrices) for polynomial, _relation in predicates]
    basis_matrices = [_monomial_matrix(monomial, matrices) for monomial in basis]
    count = sp.Integer(0)
    for powers, coefficient in terms.items():
        multiplier = sp.eye(len(basis))
        for matrix, power in zip(evaluated, powers, strict=True):
            if power:
                multiplier *= matrix**power
        hermite = sp.zeros(len(basis))
        for row in range(len(basis)):
            for column in range(row, len(basis)):
                value = sp.trace(multiplier * basis_matrices[row] * basis_matrices[column])
                hermite[row, column] = value
                hermite[column, row] = value
        positive, negative, _zero = _exact_inertia(hermite)
        count += coefficient * (positive - negative)
    if count.q != 1:
        _reject("nonintegral-tarski-count")
    return int(count), len(terms)


def _build_for_separator(parsed: Mapping[str, Any], separator: int) -> dict[str, Any]:
    cluster = parsed["cluster"]
    k = len(cluster)
    basis = _basis(k, len(parsed["symbols"]), separator)
    extension = _extension(basis, len(parsed["symbols"]))
    moment_cache: dict[tuple[int, ...], sp.Rational] = {}

    def moment(exponents: tuple[int, ...]) -> sp.Rational:
        if exponents not in moment_cache:
            approximate = sum((_monomial_value(exponents, point) for point in cluster), mp.mpc(0))
            moment_cache[exponents] = _reconstruct(approximate)
        return moment_cache[exponents]

    hplus = sp.Matrix(
        [
            [moment(tuple(a + b for a, b in zip(left, right, strict=True))) for right in extension]
            for left in extension
        ]
    )
    index = {monomial: position for position, monomial in enumerate(extension)}
    positions = [index[item] for item in basis]
    hbase = hplus.extract(positions, positions)
    if hbase.rank() != k or hplus.rank() != k:
        _reject("moment-flat-rank-failed")
    matrices = []
    for variable in range(len(parsed["symbols"])):
        columns = []
        for monomial in basis:
            lifted = list(monomial)
            lifted[variable] += 1
            columns.append(index[tuple(lifted)])
        hx = hplus.extract(positions, columns)
        matrices.append(sp.simplify(hbase.inv() * hx))
    for power in range(k - 1):
        expected = sp.zeros(k, 1)
        expected[power + 1, 0] = 1
        if matrices[separator][:, power] != expected:
            _reject("connected-to-one-border-identity")
    for first, second in itertools.combinations(matrices, 2):
        if first * second != second * first:
            _reject("multiplication-matrices-do-not-commute")
    separator_coefficients = None
    separator_polynomial = None
    lam = sp.Symbol("__lambda")
    for panel in SEPARATOR_PANELS:
        combined = sp.zeros(k)
        for coefficient, matrix in zip(panel, matrices, strict=False):
            combined += coefficient * matrix
        characteristic = sp.Poly(combined.charpoly(lam).as_expr(), lam, domain=sp.QQ)
        if sp.gcd(characteristic, characteristic.diff()).degree() == 0:
            separator_coefficients = panel[: len(matrices)]
            separator_polynomial = characteristic
            break
    if separator_coefficients is None:
        _reject("singular-or-nonradical-quotient")
    for equation in parsed["equations"]:
        if _evaluate_polynomial(equation, matrices) != sp.zeros(k):
            _reject("source-fibre-generator-does-not-vanish")
    target_matrix = _evaluate_polynomial(parsed["target"], matrices)
    target_descriptor, _ordinal, _left, _right = parsed["descriptor"]
    target_on_matrices = sp.zeros(k)
    for (power,), coefficient in target_descriptor.terms():
        target_on_matrices += coefficient * target_matrix**power
    if target_on_matrices != sp.zeros(k):
        _reject("proposed-target-fibre-does-not-vanish")
    for row, left in enumerate(extension):
        left_matrix = _monomial_matrix(left, matrices)
        for column, right in enumerate(extension):
            exact = sp.trace(left_matrix * _monomial_matrix(right, matrices))
            if exact != hplus[row, column]:
                _reject("trace-moment-inconsistency")
    count, query_terms = _tarski_count(parsed, basis, matrices)
    if count <= 0:
        _reject("no-real-subideal-root-in-box-and-fibre")
    return {
        "schema_version": CERT_SCHEMA,
        "status": "CERTIFIED_PARTIAL_RADICAL_EXISTENCE",
        "problem_sha256": parsed["problem_sha256"],
        "basis": [list(item) for item in basis],
        "extension": [list(item) for item in extension],
        "separator_variable_index": separator,
        "hplus": _matrix_encode(hplus),
        "multiplication_matrices": [_matrix_encode(item) for item in matrices],
        "separating_coefficients": list(separator_coefficients),
        "separating_characteristic_high_to_low": [str(item) for item in separator_polynomial.all_coeffs()],
        "positive_tarski_count": count,
        "tarski_query_term_count": query_terms,
        "ideal_inclusion": "I_SUBSET_J",
        "variety_inclusion": "V_J_SUBSET_V_I",
        "coordinate_exactification": False,
        "complete_source_quotient_claim": False,
        "target_set_completeness_claim": False,
        "truth_used": False,
        "authority": True,
    }


def verify_certificate(problem: Mapping[str, Any], certificate: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _parse_problem(problem)
    if not isinstance(certificate, Mapping) or certificate.get("schema_version") != CERT_SCHEMA:
        _reject("certificate-schema")
    separator = certificate.get("separator_variable_index")
    if not isinstance(separator, int) or not 0 <= separator < len(parsed["symbols"]):
        _reject("certificate-separator")
    rebuilt = _build_for_separator(parsed, separator)
    if dict(certificate) != rebuilt:
        _reject("certificate-exact-rebuild-mismatch")
    return rebuilt


def certify(problem: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _parse_problem(problem)
    failures = []
    for separator in range(len(parsed["symbols"])):
        try:
            artifact = _build_for_separator(parsed, separator)
            return verify_certificate(problem, artifact)
        except NotCertified as error:
            failures.append(str(error))
    _reject("all-connected-basis-attempts-failed:" + "|".join(failures))


def disposition(problem: Mapping[str, Any]) -> dict[str, Any]:
    try:
        result = certify(problem)
        return {
            "activated": True,
            "authority": result["authority"],
            "positive_tarski_count": result["positive_tarski_count"],
            "signature": {
                "variable_count": len(problem.get("variables", ())),
                "cluster_count": len(problem.get("approximate_cluster", ())),
                "equation_count": len(problem.get("equations", ())),
                "predicate_count": len(problem.get("predicates", ())),
            },
            "reason": None,
        }
    except Exception as error:
        return {
            "activated": False,
            "authority": False,
            "positive_tarski_count": 0,
            "signature": None,
            "reason": f"{type(error).__name__}:{error}",
        }
