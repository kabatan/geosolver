#!/usr/bin/env python3
"""Proposal-only cross-endpoint Vieta reconstruction.

This disposable core deliberately has no source eliminant and no geometry
primitive knowledge.  It combines independent HP evaluations of the scalar
answer at several endpoints from one immutable source.  A result is only a
proposal: the caller's untouched full-tuple replay remains the sole authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import reduce
import hashlib
import math
from typing import Any, Callable, Sequence


SCHEMA_VERSION = "geotarget.cross-endpoint-vieta/v1"
MECHANISM = "CROSS_ENDPOINT_ELEMENTARY_SYMMETRIC_RATIONAL_RECONSTRUCTION"
MIN_DEGREE = 2
MAX_DEGREE = 6


@dataclass(frozen=True)
class HPRung:
    precision_bits: int
    provenance_sha256: str
    target_decimal: str
    full_tuple_decimal: tuple[str, ...]


@dataclass(frozen=True)
class EndpointObservation:
    source_sha256: str
    low: HPRung
    high: HPRung
    opaque_tag: str = ""


@dataclass(frozen=True)
class PolynomialProposal:
    # Primitive integer coefficients, highest degree first.
    coefficients: tuple[int, ...]
    degree: int
    endpoint_root_ordinals: tuple[int, ...]
    source_sha256: str
    mechanism: str = MECHANISM
    completeness_claimed: bool = False
    minimal_descriptor_claimed: bool = False
    descriptor_emission_permitted: bool = False


@dataclass(frozen=True)
class Outcome:
    status: str
    reason: str
    proposal: PolynomialProposal | None
    fallback_result: Any
    replay_calls: int


Replay = Callable[[EndpointObservation, PolynomialProposal, int], bool]


@dataclass(frozen=True)
class EndpointReplayDecision:
    accepted: bool
    descriptor_identity_sha256: str


@dataclass(frozen=True)
class IndependentOutcome:
    status: str
    reason: str
    structural_proposal: PolynomialProposal | None
    fallback_result: Any
    replay_calls: int
    accepted_endpoint_indices: tuple[int, ...]
    accepted_descriptor_identities: tuple[str, ...]
    rejected_endpoint_count: int
    exception_endpoint_count: int
    duplicate_descriptor_count: int
    completeness_claimed: bool = False


IndependentReplay = Callable[
    [EndpointObservation, PolynomialProposal, int], EndpointReplayDecision
]


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _decimal_fraction(text: str) -> Fraction:
    value = Decimal(text)
    if not value.is_finite():
        raise ValueError("non-finite HP value")
    return Fraction(value)


def _elementary_symmetric(values: Sequence[Decimal]) -> tuple[Decimal, ...]:
    result = [Decimal(0)] * (len(values) + 1)
    result[0] = Decimal(1)
    for used, value in enumerate(values, start=1):
        for index in range(used, 0, -1):
            result[index] += value * result[index - 1]
    return tuple(result)


def _rational_reconstruct(
    value: Decimal,
    *,
    max_denominator: int,
    max_numerator: int,
    tolerance: Fraction,
) -> Fraction | None:
    exact_decimal = Fraction(value)
    candidate = exact_decimal.limit_denominator(max_denominator)
    if abs(candidate.numerator) > max_numerator:
        return None
    if abs(exact_decimal - candidate) > tolerance:
        return None
    # This is the standard separation bound for two reduced rationals whose
    # denominators are at most Q.  It makes the bounded reconstruction unique.
    if 2 * tolerance * max_denominator * max_denominator >= 1:
        return None
    return candidate


def _reconstruct_monic_coefficients(
    values: Sequence[str],
    *,
    decimal_precision: int,
    max_denominator: int,
    max_numerator: int,
    tolerance: Fraction,
) -> tuple[Fraction, ...] | None:
    with localcontext() as context:
        context.prec = decimal_precision
        decimals = [Decimal(value) for value in values]
        if any(not value.is_finite() for value in decimals):
            return None
        elementary = _elementary_symmetric(decimals)
    coefficients: list[Fraction] = [Fraction(1)]
    for index in range(1, len(elementary)):
        reconstructed = _rational_reconstruct(
            elementary[index],
            max_denominator=max_denominator,
            max_numerator=max_numerator,
            tolerance=tolerance,
        )
        if reconstructed is None:
            return None
        coefficients.append(reconstructed if index % 2 == 0 else -reconstructed)
    return tuple(coefficients)


def _lcm(left: int, right: int) -> int:
    return abs(left * right) // math.gcd(left, right)


def _primitive_integer_coefficients(coefficients: Sequence[Fraction]) -> tuple[int, ...]:
    denominator = reduce(_lcm, (value.denominator for value in coefficients), 1)
    integers = [value.numerator * (denominator // value.denominator) for value in coefficients]
    divisor = reduce(math.gcd, (abs(value) for value in integers if value), 0) or 1
    integers = [value // divisor for value in integers]
    if integers[0] < 0:
        integers = [-value for value in integers]
    return tuple(integers)


def _evaluate(coefficients: Sequence[int], value: Decimal) -> Decimal:
    result = Decimal(0)
    for coefficient in coefficients:
        result = result * value + Decimal(coefficient)
    return result


def _root_ordinals(values: Sequence[str]) -> tuple[int, ...] | None:
    parsed = [Decimal(value) for value in values]
    if any(not value.is_finite() for value in parsed) or len(set(parsed)) != len(parsed):
        return None
    order = sorted(range(len(parsed)), key=lambda index: parsed[index])
    ordinals = [0] * len(parsed)
    for ordinal, index in enumerate(order):
        ordinals[index] = ordinal
    return tuple(ordinals)


def _closed(
    reason: str,
    fallback_result: Any,
    *,
    replay_calls: int = 0,
) -> Outcome:
    return Outcome("FALLBACK", reason, None, fallback_result, replay_calls)


def propose_cross_endpoint_vieta(
    *,
    source_bytes: bytes,
    source_sha256: str,
    endpoints: Sequence[EndpointObservation],
    replay_full_tuple: Replay,
    fallback_result: Any,
    low_decimal_precision: int = 70,
    high_decimal_precision: int = 110,
    max_denominator: int = 10**6,
    max_numerator: int = 10**9,
    low_tolerance: Fraction = Fraction(1, 10**40),
    high_tolerance: Fraction = Fraction(1, 10**70),
) -> Outcome:
    """Build a bounded rational Vieta proposal and replay every full tuple.

    No positive result asserts that the observed endpoint set is complete.
    The callback must be the existing canonical source/guard/branch/raw-answer
    verifier.  A single false return or exception discards the whole proposal.
    """

    observed_source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if not _valid_sha256(source_sha256) or observed_source_sha256 != source_sha256:
        return _closed("SOURCE_SHA_MISMATCH", fallback_result)
    degree = len(endpoints)
    if degree < MIN_DEGREE or degree > MAX_DEGREE:
        return _closed("DEGREE_OUTSIDE_2_TO_6", fallback_result)
    if not callable(replay_full_tuple):
        return _closed("REPLAY_NOT_CALLABLE", fallback_result)
    if low_decimal_precision < 32 or high_decimal_precision <= low_decimal_precision:
        return _closed("INVALID_PRECISION_LADDER", fallback_result)
    if max_denominator < 1 or max_numerator < 1:
        return _closed("INVALID_HEIGHT_BOUND", fallback_result)

    tuple_dimensions: set[int] = set()
    low_targets: list[str] = []
    high_targets: list[str] = []
    endpoint_tuple_fingerprints: set[tuple[str, ...]] = set()
    for endpoint in endpoints:
        if endpoint.source_sha256 != source_sha256:
            return _closed("MIXED_SOURCE_ENDPOINT_SET", fallback_result)
        if (
            not _valid_sha256(endpoint.low.provenance_sha256)
            or not _valid_sha256(endpoint.high.provenance_sha256)
            or endpoint.low.provenance_sha256 == endpoint.high.provenance_sha256
            or endpoint.high.precision_bits <= endpoint.low.precision_bits
        ):
            return _closed("RUNGS_NOT_INDEPENDENT_OR_ORDERED", fallback_result)
        if not endpoint.low.full_tuple_decimal or not endpoint.high.full_tuple_decimal:
            return _closed("EMPTY_FULL_TUPLE", fallback_result)
        if len(endpoint.low.full_tuple_decimal) != len(endpoint.high.full_tuple_decimal):
            return _closed("RUNG_TUPLE_DIMENSION_MISMATCH", fallback_result)
        tuple_dimensions.add(len(endpoint.high.full_tuple_decimal))
        try:
            _decimal_fraction(endpoint.low.target_decimal)
            _decimal_fraction(endpoint.high.target_decimal)
            for coordinate in (*endpoint.low.full_tuple_decimal, *endpoint.high.full_tuple_decimal):
                _decimal_fraction(coordinate)
        except (ValueError, ArithmeticError):
            return _closed("MALFORMED_HP_VALUE", fallback_result)
        low_targets.append(endpoint.low.target_decimal)
        high_targets.append(endpoint.high.target_decimal)
        fingerprint = tuple(endpoint.high.full_tuple_decimal)
        if fingerprint in endpoint_tuple_fingerprints:
            return _closed("DUPLICATE_ENDPOINT_TUPLE", fallback_result)
        endpoint_tuple_fingerprints.add(fingerprint)
    if len(tuple_dimensions) != 1:
        return _closed("MIXED_TUPLE_DIMENSIONS", fallback_result)

    low_coefficients = _reconstruct_monic_coefficients(
        low_targets,
        decimal_precision=low_decimal_precision,
        max_denominator=max_denominator,
        max_numerator=max_numerator,
        tolerance=low_tolerance,
    )
    high_coefficients = _reconstruct_monic_coefficients(
        high_targets,
        decimal_precision=high_decimal_precision,
        max_denominator=max_denominator,
        max_numerator=max_numerator,
        tolerance=high_tolerance,
    )
    if low_coefficients is None or high_coefficients is None:
        return _closed("BOUNDED_RATIONAL_RECONSTRUCTION_FAILED", fallback_result)
    if low_coefficients != high_coefficients:
        return _closed("INDEPENDENT_RUNG_DISAGREEMENT", fallback_result)

    integer_coefficients = _primitive_integer_coefficients(high_coefficients)
    ordinals = _root_ordinals(high_targets)
    if ordinals is None:
        return _closed("TARGETS_NOT_DISTINCT_REAL_VALUES", fallback_result)

    # A cheap numeric consistency gate catches unstable/mixed sets before the
    # expensive canonical replay.  It is never authority.
    with localcontext() as context:
        context.prec = high_decimal_precision
        gate = Decimal(10) ** (-(high_decimal_precision // 2))
        if any(abs(_evaluate(integer_coefficients, Decimal(value))) > gate for value in high_targets):
            return _closed("RECONSTRUCTED_POLYNOMIAL_NUMERIC_MISMATCH", fallback_result)

    proposal = PolynomialProposal(
        coefficients=integer_coefficients,
        degree=degree,
        endpoint_root_ordinals=ordinals,
        source_sha256=source_sha256,
    )
    replay_calls = 0
    try:
        for endpoint, root_ordinal in zip(endpoints, ordinals):
            replay_calls += 1
            if replay_full_tuple(endpoint, proposal, root_ordinal) is not True:
                return _closed("FULL_TUPLE_REPLAY_REJECTED", fallback_result, replay_calls=replay_calls)
    except Exception:
        return _closed("FULL_TUPLE_REPLAY_EXCEPTION", fallback_result, replay_calls=replay_calls)
    return Outcome("PROPOSAL", "ALL_ENDPOINT_FULL_TUPLE_REPLAYS_ACCEPTED", proposal, fallback_result, replay_calls)


def propose_cross_endpoint_vieta_independent(
    *,
    source_bytes: bytes,
    source_sha256: str,
    endpoints: Sequence[EndpointObservation],
    replay_endpoint: IndependentReplay,
    fallback_result: Any,
    **reconstruction_options: Any,
) -> IndependentOutcome:
    """Repair A: retain independently accepted factor descriptors only.

    The whole Vieta polynomial is structural evidence and is explicitly not a
    minimal-polynomial descriptor.  A caller must factor it first and return a
    canonical factor/root descriptor identity per endpoint.  False/exception
    results reject only that endpoint; accepted identities are deduplicated.
    No unobserved root is materialized and the baseline fallback object is
    carried through unchanged.
    """

    captured: list[tuple[EndpointObservation, PolynomialProposal, int]] = []

    def capture(
        endpoint: EndpointObservation,
        proposal: PolynomialProposal,
        root_ordinal: int,
    ) -> bool:
        captured.append((endpoint, proposal, root_ordinal))
        return True

    structural = propose_cross_endpoint_vieta(
        source_bytes=source_bytes,
        source_sha256=source_sha256,
        endpoints=endpoints,
        replay_full_tuple=capture,
        fallback_result=fallback_result,
        **reconstruction_options,
    )
    if structural.status != "PROPOSAL" or structural.proposal is None:
        return IndependentOutcome(
            "FALLBACK",
            structural.reason,
            None,
            fallback_result,
            0,
            (),
            (),
            0,
            0,
            0,
        )
    proposal = structural.proposal
    if (
        proposal.minimal_descriptor_claimed is not False
        or proposal.descriptor_emission_permitted is not False
        or len(captured) != len(endpoints)
        or any(item[1] != proposal for item in captured)
    ):
        return IndependentOutcome(
            "FALLBACK",
            "STRUCTURAL_PROPOSAL_CONTRACT_CHANGED",
            None,
            fallback_result,
            0,
            (),
            (),
            0,
            len(endpoints),
            0,
        )

    accepted_indices: list[int] = []
    accepted_identities: list[str] = []
    seen_identities: set[str] = set()
    rejected = 0
    exceptions = 0
    duplicates = 0
    replay_calls = 0
    for index, (endpoint, _proposal, root_ordinal) in enumerate(captured):
        replay_calls += 1
        try:
            decision = replay_endpoint(endpoint, proposal, root_ordinal)
        except Exception:
            exceptions += 1
            continue
        identity = (
            decision.descriptor_identity_sha256
            if isinstance(decision, EndpointReplayDecision)
            else None
        )
        if (
            not isinstance(decision, EndpointReplayDecision)
            or decision.accepted is not True
            or not isinstance(identity, str)
            or len(identity) != 64
            or any(character not in "0123456789abcdef" for character in identity)
        ):
            rejected += 1
            continue
        if identity in seen_identities:
            duplicates += 1
            continue
        seen_identities.add(identity)
        accepted_indices.append(index)
        accepted_identities.append(identity)
    accepted = len(accepted_indices)
    return IndependentOutcome(
        "PORTFOLIO" if accepted else "FALLBACK",
        (
            "INDEPENDENT_CANONICAL_ENDPOINTS_ACCEPTED"
            if accepted
            else "NO_CANONICAL_ENDPOINT_ACCEPTED"
        ),
        proposal,
        fallback_result,
        replay_calls,
        tuple(accepted_indices),
        tuple(accepted_identities),
        rejected,
        exceptions,
        duplicates,
    )
