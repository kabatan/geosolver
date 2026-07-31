"""Truth-blind signed source-ideal automorphisms as local-search starts.

The route is deliberately conservative.  It recognizes only exact rational
polynomial covers whose equality *row space*, ordered predicates, and source
bounds are invariant under a signed coordinate permutation.  The image of an
already accepted endpoint is merely a proposal and must pass the caller's
untouched canonical source replay.  No target value is computed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import itertools
import json
import math
from typing import Callable, Iterable, Mapping, Sequence

import sympy as sp


POLICY_ID = "source_ideal_signed_automorphism_orbit_start_v1"
UNKNOWN_STATUS = "UNKNOWN"
PROPOSAL_STATUS = "PROPOSALS_ONLY"
MAX_VARIABLES = 12
MAX_EQUATIONS = 24
MAX_PREDICATES = 64
MAX_TOTAL_MONOMIALS = 400
MAX_TRANSFORM_TRIALS = 512
MAX_GENERATORS = 32
MAX_GROUP_ELEMENTS = 64


@dataclass(frozen=True)
class Predicate:
    relation: str
    expression: str


@dataclass(frozen=True)
class ExactSource:
    variables: tuple[str, ...]
    equations: tuple[str, ...]
    predicates: tuple[Predicate, ...] = ()
    bounds: tuple[tuple[Fraction | None, Fraction | None], ...] = ()
    opaque: bool = False


@dataclass(frozen=True)
class SignedPermutation:
    """``output[i] = signs[i] * input[permutation[i]]``."""

    permutation: tuple[int, ...]
    signs: tuple[int, ...]


@dataclass(frozen=True)
class OrbitResult:
    baseline_payload: bytes
    proposals: tuple[tuple[float, ...], ...]
    status: str
    reason: str
    eligible: bool
    transforms_tested: int
    generators_found: int
    orbit_elements: int
    source_invalid: int
    anonymous_signature: str | None


class UnsupportedSource(ValueError):
    pass


def _parse_polynomial(text: str, symbols: Sequence[sp.Symbol]) -> sp.Poly:
    if not isinstance(text, str) or not text.strip():
        raise UnsupportedSource("MALFORMED_POLYNOMIAL")
    locals_map = {symbol.name: symbol for symbol in symbols}
    try:
        expression = sp.sympify(text.replace("^", "**"), locals=locals_map)
        polynomial = sp.Poly(expression, *symbols, domain=sp.QQ)
    except (sp.PolynomialError, sp.CoercionFailed, TypeError, ValueError) as error:
        raise UnsupportedSource("NON_QQ_POLYNOMIAL") from error
    return polynomial


def _fraction_key(value: sp.Rational) -> tuple[int, int]:
    rational = sp.Rational(value)
    return int(rational.p), int(rational.q)


def _polynomial_vector(
    polynomial: sp.Poly, monomials: Sequence[tuple[int, ...]]
) -> list[sp.Rational]:
    terms = dict(polynomial.terms())
    return [sp.Rational(terms.get(monomial, 0)) for monomial in monomials]


def _rowspace_key(polynomials: Sequence[sp.Poly]) -> tuple[
    tuple[tuple[int, ...], ...], tuple[tuple[tuple[int, int], ...], ...]
]:
    nonzero = [polynomial for polynomial in polynomials if not polynomial.is_zero]
    if not nonzero:
        return (), ()
    monomials = sorted(
        {monomial for polynomial in nonzero for monomial, _ in polynomial.terms()},
        reverse=True,
    )
    matrix = sp.Matrix(
        [_polynomial_vector(polynomial, monomials) for polynomial in nonzero]
    )
    reduced, _pivots = matrix.rref()
    rows = []
    for row in range(reduced.rows):
        values = tuple(_fraction_key(reduced[row, column]) for column in range(reduced.cols))
        if any(numerator != 0 for numerator, _denominator in values):
            rows.append(values)
    # The monomial basis is part of the key.  Numeric RREF rows alone would
    # incorrectly identify, for example, span{x-1} with span{y-1}.
    return tuple(monomials), tuple(rows)


def _primitive_polynomial_key(
    polynomial: sp.Poly, *, sign_is_semantic: bool
) -> tuple[tuple[tuple[int, ...], int], ...]:
    if polynomial.is_zero:
        return ()
    _denominator, integral = polynomial.clear_denoms(convert=True)
    _content, primitive = integral.primitive()
    if not sign_is_semantic and primitive.LC() < 0:
        primitive = -primitive
    return tuple((tuple(monomial), int(coefficient)) for monomial, coefficient in primitive.terms())


def _predicate_key(
    predicates: Sequence[tuple[str, sp.Poly]],
) -> tuple[tuple[str, tuple[tuple[tuple[int, ...], int], ...]], ...]:
    keys = []
    for relation, polynomial in predicates:
        if relation not in {"gt", "ge", "ne"}:
            raise UnsupportedSource("UNSUPPORTED_PREDICATE_RELATION")
        keys.append(
            (
                relation,
                _primitive_polynomial_key(
                    polynomial, sign_is_semantic=relation in {"gt", "ge"}
                ),
            )
        )
    return tuple(sorted(keys))


def _source_bounds(source: ExactSource) -> tuple[tuple[Fraction | None, Fraction | None], ...]:
    if not source.bounds:
        return tuple((None, None) for _ in source.variables)
    if len(source.bounds) != len(source.variables):
        raise UnsupportedSource("BOUND_DIMENSION_MISMATCH")
    result = []
    for lower, upper in source.bounds:
        if lower is not None and not isinstance(lower, Fraction):
            raise UnsupportedSource("NONRATIONAL_BOUND")
        if upper is not None and not isinstance(upper, Fraction):
            raise UnsupportedSource("NONRATIONAL_BOUND")
        if lower is not None and upper is not None and lower >= upper:
            raise UnsupportedSource("EMPTY_BOUND")
        result.append((lower, upper))
    return tuple(result)


@dataclass(frozen=True)
class _CompiledSource:
    symbols: tuple[sp.Symbol, ...]
    equations: tuple[sp.Poly, ...]
    predicates: tuple[tuple[str, sp.Poly], ...]
    bounds: tuple[tuple[Fraction | None, Fraction | None], ...]
    equality_key: tuple[
        tuple[tuple[int, ...], ...], tuple[tuple[tuple[int, int], ...], ...]
    ]
    predicate_key: tuple[tuple[str, tuple[tuple[tuple[int, ...], int], ...]], ...]


def _compile(source: ExactSource) -> _CompiledSource:
    if source.opaque:
        raise UnsupportedSource("OPAQUE_SOURCE")
    dimension = len(source.variables)
    if (
        dimension == 0
        or dimension > MAX_VARIABLES
        or len(set(source.variables)) != dimension
        or not all(isinstance(name, str) and name for name in source.variables)
    ):
        raise UnsupportedSource("VARIABLE_CAP_OR_IDENTITY")
    if not source.equations or len(source.equations) > MAX_EQUATIONS:
        raise UnsupportedSource("EQUATION_CAP")
    if len(source.predicates) > MAX_PREDICATES:
        raise UnsupportedSource("PREDICATE_CAP")
    symbols = tuple(sp.Symbol(name) for name in source.variables)
    equations = tuple(_parse_polynomial(text, symbols) for text in source.equations)
    if any(polynomial.total_degree() == 0 and not polynomial.is_zero for polynomial in equations):
        raise UnsupportedSource("CONSTANT_INCONSISTENT_EQUATION")
    predicates = tuple(
        (predicate.relation, _parse_polynomial(predicate.expression, symbols))
        for predicate in source.predicates
    )
    monomial_count = sum(len(polynomial.terms()) for polynomial in equations)
    monomial_count += sum(len(polynomial.terms()) for _relation, polynomial in predicates)
    if monomial_count > MAX_TOTAL_MONOMIALS:
        raise UnsupportedSource("MONOMIAL_CAP")
    bounds = _source_bounds(source)
    return _CompiledSource(
        symbols=symbols,
        equations=equations,
        predicates=predicates,
        bounds=bounds,
        equality_key=_rowspace_key(equations),
        predicate_key=_predicate_key(predicates),
    )


def _candidate_transforms(dimension: int) -> Iterable[SignedPermutation]:
    identity = tuple(range(dimension))
    seen: set[SignedPermutation] = set()

    def emit(permutation: tuple[int, ...], signs: tuple[int, ...]):
        candidate = SignedPermutation(permutation, signs)
        if candidate not in seen:
            seen.add(candidate)
            return candidate
        return None

    # Exact sign symmetries are cheap and cover the common even/global-sign cases.
    sign_masks = [1 << index for index in range(dimension)]
    sign_masks.extend((1 << left) | (1 << right) for left in range(dimension) for right in range(left + 1, dimension))
    sign_masks.append((1 << dimension) - 1)
    for mask in sign_masks:
        candidate = emit(
            identity,
            tuple(-1 if mask & (1 << index) else 1 for index in range(dimension)),
        )
        if candidate is not None:
            yield candidate

    # Transpositions plus signed variants generate a bounded, representation-
    # equivariant subset of the hyperoctahedral group.
    for left in range(dimension):
        for right in range(left + 1, dimension):
            permutation = list(identity)
            permutation[left], permutation[right] = permutation[right], permutation[left]
            for left_sign, right_sign in itertools.product((1, -1), repeat=2):
                signs = [1] * dimension
                signs[left], signs[right] = left_sign, right_sign
                candidate = emit(tuple(permutation), tuple(signs))
                if candidate is not None:
                    yield candidate


def _substitution(
    compiled: _CompiledSource, transform: SignedPermutation
) -> Mapping[sp.Symbol, sp.Expr]:
    return {
        symbol: transform.signs[index] * compiled.symbols[transform.permutation[index]]
        for index, symbol in enumerate(compiled.symbols)
    }


def _bounds_invariant(
    bounds: Sequence[tuple[Fraction | None, Fraction | None]],
    transform: SignedPermutation,
) -> bool:
    for output_index, (expected_lower, expected_upper) in enumerate(bounds):
        input_lower, input_upper = bounds[transform.permutation[output_index]]
        if transform.signs[output_index] == 1:
            observed = input_lower, input_upper
        else:
            observed = (
                None if input_upper is None else -input_upper,
                None if input_lower is None else -input_lower,
            )
        if observed != (expected_lower, expected_upper):
            return False
    return True


def _is_automorphism(compiled: _CompiledSource, transform: SignedPermutation) -> bool:
    if not _bounds_invariant(compiled.bounds, transform):
        return False
    substitution = _substitution(compiled, transform)
    transformed_equations = tuple(
        sp.Poly(
            polynomial.as_expr().subs(substitution, simultaneous=True),
            *compiled.symbols,
            domain=sp.QQ,
        )
        for polynomial in compiled.equations
    )
    if _rowspace_key(transformed_equations) != compiled.equality_key:
        return False
    transformed_predicates = tuple(
        (
            relation,
            sp.Poly(
                polynomial.as_expr().subs(substitution, simultaneous=True),
                *compiled.symbols,
                domain=sp.QQ,
            ),
        )
        for relation, polynomial in compiled.predicates
    )
    return _predicate_key(transformed_predicates) == compiled.predicate_key


def _compose(outer: SignedPermutation, inner: SignedPermutation) -> SignedPermutation:
    """Return ``outer(inner(point))``."""

    return SignedPermutation(
        tuple(inner.permutation[outer.permutation[index]] for index in range(len(outer.permutation))),
        tuple(
            outer.signs[index] * inner.signs[outer.permutation[index]]
            for index in range(len(outer.permutation))
        ),
    )


def _group_closure(
    dimension: int, generators: Sequence[SignedPermutation]
) -> tuple[SignedPermutation, ...]:
    identity = SignedPermutation(tuple(range(dimension)), (1,) * dimension)
    elements = [identity]
    seen = {identity}
    cursor = 0
    bounded_generators = tuple(generators[:MAX_GENERATORS])
    while cursor < len(elements) and len(elements) < MAX_GROUP_ELEMENTS:
        current = elements[cursor]
        cursor += 1
        for generator in bounded_generators:
            combined = _compose(generator, current)
            if combined in seen:
                continue
            seen.add(combined)
            elements.append(combined)
            if len(elements) >= MAX_GROUP_ELEMENTS:
                break
    return tuple(elements)


def _apply(transform: SignedPermutation, point: Sequence[float]) -> tuple[float, ...]:
    return tuple(
        float(transform.signs[index]) * float(point[transform.permutation[index]])
        for index in range(len(transform.permutation))
    )


def _cycle_signature(transform: SignedPermutation) -> tuple[tuple[int, int], ...]:
    visited: set[int] = set()
    cycles = []
    for start in range(len(transform.permutation)):
        if start in visited:
            continue
        cursor = start
        sign_product = 1
        length = 0
        while cursor not in visited:
            visited.add(cursor)
            sign_product *= transform.signs[cursor]
            length += 1
            cursor = transform.permutation[cursor]
        cycles.append((length, sign_product))
    return tuple(sorted(cycles))


def _polynomial_shape(polynomial: sp.Poly) -> tuple[int, tuple[tuple[int, ...], ...]]:
    monomials = tuple(
        sorted(tuple(sorted(monomial, reverse=True)) for monomial, _ in polynomial.terms())
    )
    return int(polynomial.total_degree()), monomials


def _anonymous_signature(
    compiled: _CompiledSource,
    generators: Sequence[SignedPermutation],
    orbit_size: int,
) -> str:
    statement = {
        "dimension": len(compiled.symbols),
        "equation_shapes": sorted(_polynomial_shape(polynomial) for polynomial in compiled.equations),
        "predicate_shapes": sorted(
            (relation, _polynomial_shape(polynomial))
            for relation, polynomial in compiled.predicates
        ),
        "generator_signed_cycle_types": sorted(
            _cycle_signature(generator) for generator in generators
        ),
        "orbit_cardinality": orbit_size,
    }
    payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _unknown(
    payload: bytes,
    reason: str,
    *,
    eligible: bool = False,
    tested: int = 0,
    generators: int = 0,
    orbit_elements: int = 0,
    source_invalid: int = 0,
) -> OrbitResult:
    return OrbitResult(
        baseline_payload=payload,
        proposals=(),
        status=UNKNOWN_STATUS,
        reason=reason,
        eligible=eligible,
        transforms_tested=tested,
        generators_found=generators,
        orbit_elements=orbit_elements,
        source_invalid=source_invalid,
        anonymous_signature=None,
    )


def augment_baseline(
    source: ExactSource,
    *,
    accepted_endpoint: Sequence[float],
    baseline_payload: bytes,
    replay: Callable[[tuple[float, ...]], bool],
) -> OrbitResult:
    """Return replay-safe starts while preserving baseline bytes on every path."""

    if not isinstance(baseline_payload, bytes):
        raise TypeError("baseline_payload must be bytes")
    try:
        endpoint = tuple(float(value) for value in accepted_endpoint)
    except (TypeError, ValueError, OverflowError):
        return _unknown(baseline_payload, "MALFORMED_ENDPOINT")
    if (
        len(endpoint) != len(source.variables)
        or not endpoint
        or any(not math.isfinite(value) for value in endpoint)
    ):
        return _unknown(baseline_payload, "MALFORMED_ENDPOINT")
    try:
        if replay(endpoint) is not True:
            return _unknown(baseline_payload, "ACCEPTED_ENDPOINT_REPLAY_FAILED")
        compiled = _compile(source)
    except UnsupportedSource as error:
        return _unknown(baseline_payload, str(error))
    except Exception:
        return _unknown(baseline_payload, "SOURCE_COMPILE_FAILED")

    generators = []
    tested = 0
    try:
        for transform in itertools.islice(_candidate_transforms(len(endpoint)), MAX_TRANSFORM_TRIALS):
            tested += 1
            if _is_automorphism(compiled, transform):
                generators.append(transform)
    except Exception:
        return _unknown(baseline_payload, "AUTOMORPHISM_CHECK_FAILED", eligible=True, tested=tested)
    if not generators:
        return _unknown(baseline_payload, "NO_NONTRIVIAL_AUTOMORPHISM", eligible=True, tested=tested)

    group = _group_closure(len(endpoint), generators)
    proposals = []
    seen_points = {endpoint}
    for transform in group:
        mapped = _apply(transform, endpoint)
        if mapped in seen_points:
            continue
        seen_points.add(mapped)
        try:
            valid = replay(mapped) is True
        except Exception:
            valid = False
        if not valid:
            # A source compiler/replay disagreement invalidates the entire side
            # route; partial orbit emission would hide the mismatch.
            return _unknown(
                baseline_payload,
                "MAPPED_SOURCE_REPLAY_FAILED",
                eligible=True,
                tested=tested,
                generators=len(generators),
                orbit_elements=len(group),
                source_invalid=1,
            )
        proposals.append(mapped)
    if not proposals:
        return _unknown(
            baseline_payload,
            "FIXED_POINT_ORBIT",
            eligible=True,
            tested=tested,
            generators=len(generators),
            orbit_elements=len(group),
        )
    signature = _anonymous_signature(compiled, generators, len(seen_points))
    return OrbitResult(
        baseline_payload=baseline_payload,
        proposals=tuple(proposals),
        status=PROPOSAL_STATUS,
        reason="SOURCE_REPLAYED_ORBIT_STARTS",
        eligible=True,
        transforms_tested=tested,
        generators_found=len(generators),
        orbit_elements=len(group),
        source_invalid=0,
        anonymous_signature=signature,
    )


__all__ = [
    "ExactSource",
    "OrbitResult",
    "POLICY_ID",
    "PROPOSAL_STATUS",
    "Predicate",
    "UNKNOWN_STATUS",
    "augment_baseline",
]
