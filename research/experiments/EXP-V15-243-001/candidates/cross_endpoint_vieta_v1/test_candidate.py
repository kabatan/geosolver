from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, localcontext
from fractions import Fraction
from hashlib import sha256

from candidate import propose_cross_endpoint_vieta
from generated_cases import FAMILIES, GeneratedReplay, SOURCE_BYTES, SOURCE_SHA256, endpoint_set


FALLBACK = object()


def run_family(family, endpoints=None, replay=None):
    selected = endpoint_set(family) if endpoints is None else endpoints
    verifier = replay or GeneratedReplay(
        expected_coefficients=family.expected_coefficients,
        expected_endpoint_ids=map(id, selected),
    )
    return propose_cross_endpoint_vieta(
        source_bytes=SOURCE_BYTES,
        source_sha256=SOURCE_SHA256,
        endpoints=selected,
        replay_full_tuple=verifier,
        fallback_result=FALLBACK,
    ), verifier


def test_degree_two_through_six_activate_with_full_replay():
    for family in FAMILIES:
        endpoints = endpoint_set(family)
        outcome, replay = run_family(family, endpoints)
        assert outcome.status == "PROPOSAL", (family.degree, outcome)
        assert outcome.proposal is not None
        assert outcome.proposal.coefficients == family.expected_coefficients
        assert outcome.proposal.degree == family.degree
        assert outcome.proposal.completeness_claimed is False
        assert outcome.replay_calls == family.degree
        assert replay.seen_ids == list(map(id, endpoints))
        assert outcome.fallback_result is FALLBACK


def test_endpoint_permutation_preserves_polynomial_and_original_tuple_custody():
    family = FAMILIES[-1]
    forward = endpoint_set(family)
    reverse = tuple(reversed(forward))
    first, first_replay = run_family(family, forward)
    second, second_replay = run_family(family, reverse)
    assert first.proposal is not None and second.proposal is not None
    assert first.proposal.coefficients == second.proposal.coefficients
    assert first.proposal.endpoint_root_ordinals == tuple(range(family.degree))
    assert second.proposal.endpoint_root_ordinals == tuple(reversed(range(family.degree)))
    assert first_replay.seen_ids == list(map(id, forward))
    assert second_replay.seen_ids == list(map(id, reverse))


def test_reversible_affine_target_transform_has_equivariant_polynomial():
    # t = 2*z + 1 transforms z^4 - 5*z^2 + 6 into
    # t^4 - 4*t^3 - 14*t^2 + 36*t + 77 after primitive normalization.
    family = FAMILIES[2]
    transformed_source = (
        b'{"task":"solve","variables":{"names":["x","y"]},'
        b'"answer":"2*x+1"}'
    )
    transformed_sha = sha256(transformed_source).hexdigest()
    endpoints = []
    for endpoint in endpoint_set(family):
        with localcontext() as context:
            context.prec = 125
            low_target = 2 * Decimal(endpoint.low.target_decimal) + 1
            high_target = 2 * Decimal(endpoint.high.target_decimal) + 1
        endpoints.append(replace(
            endpoint,
            source_sha256=transformed_sha,
            low=replace(endpoint.low, target_decimal=format(low_target, "f")),
            high=replace(endpoint.high, target_decimal=format(high_target, "f")),
        ))
    selected = tuple(endpoints)
    expected = (1, -4, -14, 36, 77)
    replay = GeneratedReplay(
        expected_coefficients=expected,
        expected_endpoint_ids=map(id, selected),
        expected_source_sha256=transformed_sha,
    )
    outcome = propose_cross_endpoint_vieta(
        source_bytes=transformed_source,
        source_sha256=transformed_sha,
        endpoints=selected,
        replay_full_tuple=replay,
        fallback_result=FALLBACK,
    )
    assert outcome.status == "PROPOSAL"
    assert outcome.proposal is not None
    assert outcome.proposal.coefficients == expected
    assert replay.seen_ids == list(map(id, selected))


def test_partial_endpoint_set_is_rejected_by_untouched_full_tuple_replay():
    family = FAMILIES[-1]
    complete = endpoint_set(family)
    partial = complete[:-1]
    replay = GeneratedReplay(
        expected_coefficients=family.expected_coefficients,
        expected_endpoint_ids=map(id, complete),
    )
    outcome, _ = run_family(family, partial, replay)
    assert outcome.status == "FALLBACK"
    assert outcome.reason in {"FULL_TUPLE_REPLAY_REJECTED", "BOUNDED_RATIONAL_RECONSTRUCTION_FAILED"}
    assert outcome.proposal is None
    assert outcome.fallback_result is FALLBACK


def test_mixed_source_duplicate_and_non_independent_rungs_fail_closed():
    family = FAMILIES[1]
    endpoints = list(endpoint_set(family))
    endpoints[1] = replace(endpoints[1], source_sha256="0" * 64)
    mixed, _ = run_family(family, tuple(endpoints))
    assert mixed.reason == "MIXED_SOURCE_ENDPOINT_SET"

    endpoints = list(endpoint_set(family))
    endpoints[1] = replace(endpoints[1], low=endpoints[0].low, high=endpoints[0].high)
    duplicate, _ = run_family(family, tuple(endpoints))
    assert duplicate.reason == "DUPLICATE_ENDPOINT_TUPLE"

    endpoints = list(endpoint_set(family))
    endpoints[0] = replace(endpoints[0], high=replace(
        endpoints[0].high,
        provenance_sha256=endpoints[0].low.provenance_sha256,
    ))
    same_rung, _ = run_family(family, tuple(endpoints))
    assert same_rung.reason == "RUNGS_NOT_INDEPENDENT_OR_ORDERED"


def test_any_replay_rejection_or_exception_discards_whole_proposal():
    family = FAMILIES[2]
    endpoints = endpoint_set(family)
    replay = GeneratedReplay(
        expected_coefficients=family.expected_coefficients,
        expected_endpoint_ids=map(id, endpoints),
        reject_tag=endpoints[-1].opaque_tag,
    )
    rejected, _ = run_family(family, endpoints, replay)
    assert rejected.reason == "FULL_TUPLE_REPLAY_REJECTED"
    assert rejected.proposal is None
    assert rejected.replay_calls == family.degree

    def exploding_replay(endpoint, proposal, root_ordinal):
        raise RuntimeError("synthetic replay failure")

    exploded, _ = run_family(family, endpoints, exploding_replay)
    assert exploded.reason == "FULL_TUPLE_REPLAY_EXCEPTION"
    assert exploded.proposal is None
    assert exploded.replay_calls == 1


def test_cross_orbit_mixture_and_corrupted_high_rung_do_not_emit():
    pair_two = endpoint_set(FAMILIES[0])
    pair_three = endpoint_set(FAMILIES[2])
    # +sqrt(2), +sqrt(3) are individually source-shaped values but their
    # degree-two symmetric sums are not rational under the fixed height cap.
    mixed = (pair_two[-1], pair_three[-1])
    replay_calls = []
    rejected = propose_cross_endpoint_vieta(
        source_bytes=SOURCE_BYTES,
        source_sha256=SOURCE_SHA256,
        endpoints=mixed,
        replay_full_tuple=lambda *arguments: replay_calls.append(arguments) or True,
        fallback_result=FALLBACK,
    )
    assert rejected.reason == "BOUNDED_RATIONAL_RECONSTRUCTION_FAILED"
    assert rejected.proposal is None
    assert replay_calls == []

    endpoints = list(pair_two)
    endpoints[-1] = replace(
        endpoints[-1],
        high=replace(endpoints[-1].high, target_decimal="1.5"),
    )
    corrupted = propose_cross_endpoint_vieta(
        source_bytes=SOURCE_BYTES,
        source_sha256=SOURCE_SHA256,
        endpoints=tuple(endpoints),
        replay_full_tuple=lambda *_: True,
        fallback_result=FALLBACK,
    )
    assert corrupted.reason in {
        "INDEPENDENT_RUNG_DISAGREEMENT",
        "BOUNDED_RATIONAL_RECONSTRUCTION_FAILED",
    }
    assert corrupted.proposal is None


def test_individual_irrational_roots_are_not_rational_reconstruction_inputs():
    family = FAMILIES[0]
    endpoints = endpoint_set(family)
    for endpoint in endpoints:
        value = Fraction(endpoint.high.target_decimal)
        assert abs(value - value.limit_denominator(10**6)) > Fraction(1, 10**70)
    outcome, _ = run_family(family, endpoints)
    assert outcome.status == "PROPOSAL"
    assert outcome.proposal.coefficients == (1, 0, -2)


def test_source_hash_and_degree_bounds_fail_closed_with_identity_fallback():
    family = FAMILIES[0]
    endpoints = endpoint_set(family)
    bad_hash = propose_cross_endpoint_vieta(
        source_bytes=SOURCE_BYTES + b" ",
        source_sha256=SOURCE_SHA256,
        endpoints=endpoints,
        replay_full_tuple=lambda *_: True,
        fallback_result=FALLBACK,
    )
    assert bad_hash.reason == "SOURCE_SHA_MISMATCH"
    assert bad_hash.fallback_result is FALLBACK
    one = propose_cross_endpoint_vieta(
        source_bytes=SOURCE_BYTES,
        source_sha256=SOURCE_SHA256,
        endpoints=endpoints[:1],
        replay_full_tuple=lambda *_: True,
        fallback_result=FALLBACK,
    )
    assert one.reason == "DEGREE_OUTSIDE_2_TO_6"
    assert one.fallback_result is FALLBACK
