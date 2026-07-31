"""Throwaway D0 for exact target-fibre exhaustion with Hermite forms.

This intentionally supports only tiny QQ fixtures.  It proves a global target
upper polynomial, constructs and independently checks a Buchberger basis for
every specialized fibre, and uses Hermite-form signatures/Tarski queries to
count complete predicate sign patterns without enumerating coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Iterable, Sequence

import sympy as sp


class CapabilityError(RuntimeError):
    """The deliberately tiny D0 capability is not applicable."""


def _poly(expr: sp.Expr | sp.Poly, variables: Sequence[sp.Symbol]) -> sp.Poly:
    if isinstance(expr, sp.Poly):
        expr = expr.as_expr()
    return sp.Poly(sp.expand(expr), *variables, domain=sp.QQ)


def _zero(variables: Sequence[sp.Symbol]) -> sp.Poly:
    return _poly(0, variables)


def _lt(poly: sp.Poly) -> tuple[tuple[int, ...], sp.Rational]:
    (monomial, coefficient), *_ = poly.terms(order="lex")
    return monomial, sp.Rational(coefficient)


def _divides(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    return all(a <= b for a, b in zip(left, right, strict=True))


def _monomial(
    variables: Sequence[sp.Symbol], powers: tuple[int, ...], coefficient: sp.Expr = 1
) -> sp.Poly:
    expr = sp.Rational(coefficient)
    for variable, exponent in zip(variables, powers, strict=True):
        expr *= variable**exponent
    return _poly(expr, variables)


def _divide(
    dividend: sp.Poly, basis: Sequence[sp.Poly]
) -> tuple[list[sp.Poly], sp.Poly]:
    variables = dividend.gens
    quotients = [_zero(variables) for _ in basis]
    remainder = _zero(variables)
    pending = _poly(dividend, variables)
    operations = 0
    while not pending.is_zero:
        operations += 1
        if operations > 20_000:
            raise CapabilityError("polynomial division operation cap")
        pending_monomial, pending_coefficient = _lt(pending)
        reduced = False
        for index, divisor in enumerate(basis):
            divisor_monomial, divisor_coefficient = _lt(divisor)
            if not _divides(divisor_monomial, pending_monomial):
                continue
            powers = tuple(
                a - b
                for a, b in zip(
                    pending_monomial, divisor_monomial, strict=True
                )
            )
            factor = _monomial(
                variables, powers, pending_coefficient / divisor_coefficient
            )
            quotients[index] = _poly(
                quotients[index].as_expr() + factor.as_expr(), variables
            )
            pending = _poly(
                pending.as_expr() - factor.as_expr() * divisor.as_expr(), variables
            )
            reduced = True
            break
        if reduced:
            continue
        term = _monomial(variables, pending_monomial, pending_coefficient)
        remainder = _poly(remainder.as_expr() + term.as_expr(), variables)
        pending = _poly(pending.as_expr() - term.as_expr(), variables)
    return quotients, remainder


def _s_polynomial(first: sp.Poly, second: sp.Poly) -> tuple[sp.Poly, sp.Poly, sp.Poly]:
    variables = first.gens
    first_monomial, first_coefficient = _lt(first)
    second_monomial, second_coefficient = _lt(second)
    common = tuple(
        max(a, b) for a, b in zip(first_monomial, second_monomial, strict=True)
    )
    first_factor = _monomial(
        variables,
        tuple(a - b for a, b in zip(common, first_monomial, strict=True)),
        1 / first_coefficient,
    )
    second_factor = _monomial(
        variables,
        tuple(a - b for a, b in zip(common, second_monomial, strict=True)),
        1 / second_coefficient,
    )
    value = _poly(
        first_factor.as_expr() * first.as_expr()
        - second_factor.as_expr() * second.as_expr(),
        variables,
    )
    return value, first_factor, second_factor


@dataclass
class GroebnerCertificate:
    inputs: list[sp.Poly]
    basis: list[sp.Poly]
    representations: list[list[sp.Poly]]

    def verify(self) -> bool:
        if len(self.basis) != len(self.representations):
            return False
        for basis_poly, representation in zip(
            self.basis, self.representations, strict=True
        ):
            if len(representation) != len(self.inputs):
                return False
            reconstructed = sum(
                (
                    multiplier.as_expr() * generator.as_expr()
                    for multiplier, generator in zip(
                        representation, self.inputs, strict=True
                    )
                ),
                sp.Integer(0),
            )
            if sp.expand(basis_poly.as_expr() - reconstructed) != 0:
                return False
        for generator in self.inputs:
            _quotients, remainder = _divide(generator, self.basis)
            if not remainder.is_zero:
                return False
        for first, second in combinations(self.basis, 2):
            s_value, _first_factor, _second_factor = _s_polynomial(first, second)
            _quotients, remainder = _divide(s_value, self.basis)
            if not remainder.is_zero:
                return False
        return True


def buchberger(
    expressions: Iterable[sp.Expr], variables: Sequence[sp.Symbol]
) -> GroebnerCertificate:
    inputs = [_poly(expression, variables) for expression in expressions]
    inputs = [item for item in inputs if not item.is_zero]
    if not inputs:
        raise CapabilityError("empty equality ideal")
    basis: list[sp.Poly] = []
    representations: list[list[sp.Poly]] = []
    for input_index, generator in enumerate(inputs):
        _monomial_value, coefficient = _lt(generator)
        normalized = _poly(generator.as_expr() / coefficient, variables)
        representation = [_zero(variables) for _ in inputs]
        representation[input_index] = _poly(1 / coefficient, variables)
        _quotients, remainder = _divide(normalized, basis)
        if remainder.is_zero:
            continue
        _remainder_monomial, remainder_coefficient = _lt(remainder)
        remainder = _poly(remainder.as_expr() / remainder_coefficient, variables)
        # The initial generator was divided by the existing basis.  Track that
        # reduction so the new row still has a checkable input representation.
        quotients, raw_remainder = _divide(normalized, basis)
        if raw_remainder.is_zero:
            continue
        representation = [
            _poly(
                representation[column].as_expr()
                - sum(
                    (
                        quotients[row].as_expr()
                        * representations[row][column].as_expr()
                        for row in range(len(basis))
                    ),
                    sp.Integer(0),
                ),
                variables,
            )
            for column in range(len(inputs))
        ]
        representation = [
            _poly(item.as_expr() / remainder_coefficient, variables)
            for item in representation
        ]
        basis.append(remainder)
        representations.append(representation)

    pairs = list(combinations(range(len(basis)), 2))
    cursor = 0
    while cursor < len(pairs):
        if cursor > 512 or len(basis) > 48:
            raise CapabilityError("Buchberger cap")
        first_index, second_index = pairs[cursor]
        cursor += 1
        s_value, first_factor, second_factor = _s_polynomial(
            basis[first_index], basis[second_index]
        )
        s_representation = [
            _poly(
                first_factor.as_expr()
                * representations[first_index][column].as_expr()
                - second_factor.as_expr()
                * representations[second_index][column].as_expr(),
                variables,
            )
            for column in range(len(inputs))
        ]
        quotients, remainder = _divide(s_value, basis)
        if remainder.is_zero:
            continue
        remainder_representation = [
            _poly(
                s_representation[column].as_expr()
                - sum(
                    (
                        quotients[row].as_expr()
                        * representations[row][column].as_expr()
                        for row in range(len(basis))
                    ),
                    sp.Integer(0),
                ),
                variables,
            )
            for column in range(len(inputs))
        ]
        _leading_monomial, leading_coefficient = _lt(remainder)
        remainder = _poly(remainder.as_expr() / leading_coefficient, variables)
        remainder_representation = [
            _poly(item.as_expr() / leading_coefficient, variables)
            for item in remainder_representation
        ]
        new_index = len(basis)
        basis.append(remainder)
        representations.append(remainder_representation)
        pairs.extend((old_index, new_index) for old_index in range(new_index))

    certificate = GroebnerCertificate(inputs, basis, representations)
    if not certificate.verify():
        raise CapabilityError("internal Buchberger certificate verification failed")
    return certificate


def standard_monomials(
    basis: Sequence[sp.Poly], variables: Sequence[sp.Symbol], cap: int = 48
) -> list[tuple[int, ...]]:
    leading = [_lt(item)[0] for item in basis]

    def admitted(monomial: tuple[int, ...]) -> bool:
        return not any(_divides(generator, monomial) for generator in leading)

    origin = tuple(0 for _ in variables)
    if not admitted(origin):
        return []
    seen = {origin}
    queue = [origin]
    while queue:
        current = queue.pop(0)
        for axis in range(len(variables)):
            candidate = list(current)
            candidate[axis] += 1
            candidate_tuple = tuple(candidate)
            if candidate_tuple in seen or not admitted(candidate_tuple):
                continue
            seen.add(candidate_tuple)
            queue.append(candidate_tuple)
            if len(seen) > cap:
                raise CapabilityError("positive-dimensional or quotient cap exceeded")
    return sorted(seen, key=lambda item: (sum(item), item))


def _normal_form(expression: sp.Expr, certificate: GroebnerCertificate) -> sp.Poly:
    polynomial = _poly(expression, certificate.inputs[0].gens)
    _quotients, remainder = _divide(polynomial, certificate.basis)
    return remainder


def multiplication_matrix(
    expression: sp.Expr,
    certificate: GroebnerCertificate,
    monomials: Sequence[tuple[int, ...]],
) -> sp.Matrix:
    variables = certificate.inputs[0].gens
    dimension = len(monomials)
    if dimension == 0:
        return sp.zeros(0, 0)
    index = {monomial: row for row, monomial in enumerate(monomials)}
    matrix = sp.zeros(dimension, dimension)
    for column, monomial in enumerate(monomials):
        basis_expr = _monomial(variables, monomial).as_expr()
        remainder = _normal_form(expression * basis_expr, certificate)
        for powers, coefficient in remainder.terms():
            if powers not in index:
                raise CapabilityError("normal form escaped standard monomial basis")
            matrix[index[powers], column] = sp.Rational(coefficient)
    return matrix


def hermite_matrix(
    expression: sp.Expr,
    certificate: GroebnerCertificate,
    monomials: Sequence[tuple[int, ...]],
) -> sp.Matrix:
    variables = certificate.inputs[0].gens
    dimension = len(monomials)
    matrix = sp.zeros(dimension, dimension)
    for row, first in enumerate(monomials):
        first_expr = _monomial(variables, first).as_expr()
        for column in range(row, dimension):
            second_expr = _monomial(variables, monomials[column]).as_expr()
            multiplier = multiplication_matrix(
                expression * first_expr * second_expr, certificate, monomials
            )
            value = sp.trace(multiplier)
            matrix[row, column] = value
            matrix[column, row] = value
    return matrix


def rational_inertia(matrix: sp.Matrix) -> tuple[int, int, int]:
    """Exact inertia by symmetric congruence over QQ."""
    if matrix.rows != matrix.cols or matrix != matrix.T:
        raise CapabilityError("Hermite matrix is not symmetric")
    current = sp.Matrix(matrix)
    positive = 0
    negative = 0
    while current.rows:
        size = current.rows
        diagonal_index = next(
            (index for index in range(size) if current[index, index] != 0), None
        )
        if diagonal_index is not None:
            if diagonal_index != 0:
                current.row_swap(0, diagonal_index)
                current.col_swap(0, diagonal_index)
            pivot = sp.Rational(current[0, 0])
            if pivot > 0:
                positive += 1
            else:
                negative += 1
            if size == 1:
                current = sp.zeros(0, 0)
                continue
            tail = current[1:, 1:]
            coupling = current[1:, 0]
            current = sp.simplify(tail - coupling * coupling.T / pivot)
            continue
        off_diagonal = next(
            (
                (row, column)
                for row in range(size)
                for column in range(row + 1, size)
                if current[row, column] != 0
            ),
            None,
        )
        if off_diagonal is None:
            break
        first, second = off_diagonal
        for destination, source in ((0, first), (1, second)):
            if source != destination:
                current.row_swap(destination, source)
                current.col_swap(destination, source)
                if first == destination:
                    first = source
                if second == destination:
                    second = source
        block = current[:2, :2]
        positive += 1
        negative += 1
        if size == 2:
            current = sp.zeros(0, 0)
            continue
        coupling = current[:2, 2:]
        tail = current[2:, 2:]
        current = sp.simplify(tail - coupling.T * block.inv() * coupling)
    zero = matrix.rows - positive - negative
    return positive, negative, zero


def _tarski_query(
    expression: sp.Expr,
    certificate: GroebnerCertificate,
    monomials: Sequence[tuple[int, ...]],
) -> int:
    positive, negative, _zero_count = rational_inertia(
        hermite_matrix(expression, certificate, monomials)
    )
    return positive - negative


def sign_pattern_counts(
    predicates: Sequence[sp.Expr],
    certificate: GroebnerCertificate,
    monomials: Sequence[tuple[int, ...]],
) -> dict[tuple[int, ...], int]:
    exponents = list(product(range(3), repeat=len(predicates)))
    patterns = list(product((-1, 0, 1), repeat=len(predicates)))
    transform = sp.Matrix(
        [
            [
                sp.prod(1 if exponent == 0 else sign**exponent for sign, exponent in zip(pattern, powers, strict=True))
                for pattern in patterns
            ]
            for powers in exponents
        ]
    )
    queries = []
    for powers in exponents:
        expression = sp.Integer(1)
        for predicate, exponent in zip(predicates, powers, strict=True):
            expression *= predicate**exponent
        queries.append(_tarski_query(expression, certificate, monomials))
    solution = transform.inv() * sp.Matrix(queries)
    counts: dict[tuple[int, ...], int] = {}
    for pattern, value in zip(patterns, solution, strict=True):
        value = sp.Rational(value)
        if value.q != 1 or value < 0:
            raise CapabilityError("invalid sign-determination count")
        counts[pattern] = int(value)
    return counts


@dataclass(frozen=True)
class Predicate:
    relation: str
    expression: sp.Expr

    def accepts(self, sign: int) -> bool:
        return {
            "eq": sign == 0,
            "ne": sign != 0,
            "lt": sign < 0,
            "le": sign <= 0,
            "gt": sign > 0,
            "ge": sign >= 0,
        }[self.relation]


@dataclass(frozen=True)
class Problem:
    name: str
    variables: tuple[sp.Symbol, ...]
    equations: tuple[sp.Expr, ...]
    target: sp.Expr
    target_symbol: sp.Symbol
    upper_polynomial: sp.Expr
    predicates: tuple[Predicate, ...]
    expected_predicate_count: int
    expected_targets: tuple[sp.Rational, ...] | None
    expected_authority: bool
    tamper_gb_certificate: bool = False


def _rational_target_roots(problem: Problem) -> list[sp.Rational]:
    polynomial = sp.Poly(
        problem.upper_polynomial, problem.target_symbol, domain=sp.QQ
    ).sqf_part()
    roots = sp.roots(polynomial.as_expr(), problem.target_symbol)
    if sum(roots.values()) != polynomial.degree() or not all(
        root.is_Rational for root in roots
    ):
        raise CapabilityError("D0 supports only fully rational target roots")
    return sorted(sp.Rational(root) for root in roots)


def _thom_encoding(polynomial: sp.Poly, root: sp.Rational) -> list[int]:
    signs = []
    derivative = polynomial
    for _order in range(polynomial.degree() + 1):
        value = derivative.eval(root)
        signs.append(int(sp.sign(value)))
        derivative = derivative.diff()
    return signs


def solve(problem: Problem) -> dict[str, object]:
    flags = {
        "global_upper_proof": False,
        "gb_equality_buchberger": False,
        "ordered_field_sign": False,
        "full_predicate_count": len(problem.predicates)
        == problem.expected_predicate_count,
    }
    result: dict[str, object] = {
        "name": problem.name,
        "authority": False,
        "authority_flags": flags,
        "targets": [],
        "fibres": [],
        "status": "NOT_PROVED",
    }
    try:
        source_certificate = buchberger(problem.equations, problem.variables)
        if problem.tamper_gb_certificate:
            source_certificate.representations[0][0] = _poly(
                source_certificate.representations[0][0].as_expr() + 1,
                problem.variables,
            )
        source_gb_valid = source_certificate.verify()
        flags["gb_equality_buchberger"] = source_gb_valid
        if not source_gb_valid:
            result["status"] = "GB_CERTIFICATE_REJECTED"
            return result
        upper_at_target = sp.expand(
            problem.upper_polynomial.subs(problem.target_symbol, problem.target)
        )
        flags["global_upper_proof"] = _normal_form(
            upper_at_target, source_certificate
        ).is_zero
        if not flags["global_upper_proof"]:
            result["status"] = "GLOBAL_UPPER_NOT_PROVED"
            return result
        roots = _rational_target_roots(problem)
        square_free_upper = sp.Poly(
            problem.upper_polynomial, problem.target_symbol, domain=sp.QQ
        ).sqf_part()
        retained: list[sp.Rational] = []
        all_fibres_classified = True
        for root in roots:
            fibre_equations = [
                *problem.equations,
                sp.expand(problem.target - root),
            ]
            fibre_certificate = buchberger(fibre_equations, problem.variables)
            fibre_gb_valid = fibre_certificate.verify()
            flags["gb_equality_buchberger"] = (
                flags["gb_equality_buchberger"] and fibre_gb_valid
            )
            if not fibre_gb_valid:
                all_fibres_classified = False
                break
            monomials = standard_monomials(
                fibre_certificate.basis, problem.variables
            )
            counts = sign_pattern_counts(
                [predicate.expression for predicate in problem.predicates],
                fibre_certificate,
                monomials,
            )
            valid_count = sum(
                count
                for pattern, count in counts.items()
                if all(
                    predicate.accepts(sign)
                    for predicate, sign in zip(
                        problem.predicates, pattern, strict=True
                    )
                )
            )
            if valid_count > 0:
                retained.append(root)
            result["fibres"].append(
                {
                    "target": str(root),
                    "quotient_dimension": len(monomials),
                    "valid_real_point_count": valid_count,
                    "sign_pattern_counts": {
                        ",".join(map(str, pattern)): count
                        for pattern, count in counts.items()
                        if count
                    },
                    "thom_signs": _thom_encoding(square_free_upper, root),
                }
            )
        flags["ordered_field_sign"] = all_fibres_classified
        authority = all(flags.values()) and all_fibres_classified
        result["authority"] = authority
        result["targets"] = [str(value) for value in retained]
        result["status"] = "COMPLETE_SYNTHETIC_AUTHORITY" if authority else "NOT_PROVED"
        return result
    except (CapabilityError, KeyError, ValueError, ZeroDivisionError) as error:
        result["status"] = f"FAIL_CLOSED:{type(error).__name__}:{error}"
        return result


def fixtures() -> list[Problem]:
    x, y, t = sp.symbols("x y t")
    return [
        Problem(
            name="positive_two_targets",
            variables=(x,),
            equations=(x**2 - 1,),
            target=x,
            target_symbol=t,
            upper_polynomial=t**2 - 1,
            predicates=(),
            expected_predicate_count=0,
            expected_targets=(sp.Rational(-1), sp.Rational(1)),
            expected_authority=True,
        ),
        Problem(
            name="positive_even_multiplicity_singular",
            variables=(x,),
            equations=((x**2 - 2) ** 2,),
            target=x**2,
            target_symbol=t,
            upper_polynomial=(t - 2) ** 2,
            predicates=(),
            expected_predicate_count=0,
            expected_targets=(sp.Rational(2),),
            expected_authority=True,
        ),
        Problem(
            name="positive_guarded_multitarget",
            variables=(x, y),
            equations=(x**2 - 1, y**2 - 1),
            target=x + y,
            target_symbol=t,
            upper_polynomial=(t + 2) * t * (t - 2),
            predicates=(Predicate("gt", x),),
            expected_predicate_count=1,
            expected_targets=(sp.Rational(0), sp.Rational(2)),
            expected_authority=True,
        ),
        Problem(
            name="negative_wrong_global_upper",
            variables=(x,),
            equations=(x**2 - 1,),
            target=x,
            target_symbol=t,
            upper_polynomial=t - 1,
            predicates=(),
            expected_predicate_count=0,
            expected_targets=None,
            expected_authority=False,
        ),
        Problem(
            name="negative_positive_dimensional_fibre",
            variables=(x, y),
            equations=(x * y,),
            target=x * y,
            target_symbol=t,
            upper_polynomial=t,
            predicates=(),
            expected_predicate_count=0,
            expected_targets=None,
            expected_authority=False,
        ),
        Problem(
            name="negative_incomplete_predicate_ledger",
            variables=(x,),
            equations=(x**2 - 1,),
            target=x,
            target_symbol=t,
            upper_polynomial=t**2 - 1,
            predicates=(Predicate("gt", x),),
            expected_predicate_count=2,
            expected_targets=None,
            expected_authority=False,
        ),
        Problem(
            name="negative_tampered_gb_certificate",
            variables=(x,),
            equations=(x**2 - 1,),
            target=x,
            target_symbol=t,
            upper_polynomial=t**2 - 1,
            predicates=(),
            expected_predicate_count=0,
            expected_targets=None,
            expected_authority=False,
            tamper_gb_certificate=True,
        ),
        Problem(
            name="near_miss_strict_boundary_empty",
            variables=(x,),
            equations=(x**2,),
            target=x,
            target_symbol=t,
            upper_polynomial=t**2,
            predicates=(Predicate("gt", x),),
            expected_predicate_count=1,
            expected_targets=(),
            expected_authority=True,
        ),
        Problem(
            name="metamorphic_row_scale_and_generator_mix",
            variables=(x, y),
            equations=(-3 * (y**2 - 1), 5 * ((x**2 - 1) + 2 * (y**2 - 1))),
            target=x + y,
            target_symbol=t,
            upper_polynomial=(t + 2) * t * (t - 2),
            predicates=(Predicate("gt", x),),
            expected_predicate_count=1,
            expected_targets=(sp.Rational(0), sp.Rational(2)),
            expected_authority=True,
        ),
        Problem(
            name="metamorphic_variable_and_equation_permutation",
            variables=(y, x),
            equations=(y**2 - 1, x**2 - 1),
            target=y + x,
            target_symbol=t,
            upper_polynomial=(t + 2) * t * (t - 2),
            predicates=(Predicate("gt", x),),
            expected_predicate_count=1,
            expected_targets=(sp.Rational(0), sp.Rational(2)),
            expected_authority=True,
        ),
        Problem(
            name="metamorphic_affine_target",
            variables=(x, y),
            equations=(x**2 - 1, y**2 - 1),
            target=2 * (x + y) + 3,
            target_symbol=t,
            upper_polynomial=(t + 1) * (t - 3) * (t - 7),
            predicates=(Predicate("gt", x),),
            expected_predicate_count=1,
            expected_targets=(sp.Rational(3), sp.Rational(7)),
            expected_authority=True,
        ),
        Problem(
            name="negative_spurious_upper_root_exactly_excluded",
            variables=(x,),
            equations=(x**2 - 1,),
            target=x,
            target_symbol=t,
            upper_polynomial=(t**2 - 1) * (t - 3),
            predicates=(),
            expected_predicate_count=0,
            expected_targets=(sp.Rational(-1), sp.Rational(1)),
            expected_authority=True,
        ),
    ]


def run_all() -> dict[str, object]:
    records = []
    failures = []
    for problem in fixtures():
        record = solve(problem)
        records.append(record)
        targets = tuple(sp.Rational(value) for value in record["targets"])
        if record["authority"] != problem.expected_authority:
            failures.append(f"{problem.name}: authority")
        if problem.expected_targets is not None and targets != problem.expected_targets:
            failures.append(f"{problem.name}: targets {targets}")
    positive_names = {
        "positive_two_targets",
        "positive_even_multiplicity_singular",
        "positive_guarded_multitarget",
    }
    positive_pass = sum(
        1
        for record in records
        if record["name"] in positive_names and record["authority"]
    )
    false_authority = sum(
        1
        for problem, record in zip(fixtures(), records, strict=True)
        if not problem.expected_authority and record["authority"]
    )
    aggregate = {
        "schema_version": "geotarget.thom-hermite-target-fibre-d0/v1",
        "candidate": "THOM_HERMITE_TARGET_FIBRE_EXHAUSTION_V1",
        "scope": "SYNTHETIC_ONLY",
        "truth_used": False,
        "source_or_target_identity_routing": False,
        "records": records,
        "aggregate": {
            "fixture_count": len(records),
            "positive_authority_pass": positive_pass,
            "positive_authority_total": len(positive_names),
            "false_authority_count": false_authority,
            "even_multiplicity_authority": next(
                record["authority"]
                for record in records
                if record["name"] == "positive_even_multiplicity_singular"
            ),
            "metamorphic_pass_count": sum(
                bool(record["authority"])
                for record in records
                if str(record["name"]).startswith("metamorphic_")
            ),
            "spurious_upper_root_excluded": next(
                record["targets"] == ["-1", "1"]
                for record in records
                if record["name"] == "negative_spurious_upper_root_exactly_excluded"
            ),
            "gate_pass": not failures,
            "failures": failures,
        },
    }
    return aggregate
