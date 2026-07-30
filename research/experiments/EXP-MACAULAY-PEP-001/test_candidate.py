from __future__ import annotations

import math

import pytest

import candidate
import generated_cases


def canonical(block, *, reject: bool = False):
    def replay(point):
        residual = candidate.residual_inf(block, point)
        return {
            "safe": bool(not reject and residual <= 1.0e-7),
            "residual_inf": residual,
            "canonical_source_replay": True,
        }
    return replay


@pytest.mark.parametrize("case", generated_cases.cases(), ids=lambda case: case.family)
def test_generated_families(case):
    result = candidate.propose(case.block, canonical(case.block))
    assert bool(result.proposals) is case.expect_proposal
    assert result.proposal_is_authority is False
    assert result.canonical_replay_required is True
    for proposal in result.proposals:
        assert proposal.replay_payload["canonical_source_replay"] is True
        assert proposal.replay_payload["safe"] is True
        assert proposal.residual_inf <= 1.0e-7
        assert all(math.isfinite(value) for value in proposal.point)


def test_at_least_three_independent_families_per_category():
    categories = {name: set() for name in ("positive", "negative", "near_miss")}
    for case in generated_cases.cases():
        categories[case.category].add(case.family)
    assert all(len(families) >= 3 for families in categories.values())


def test_canonical_replay_can_veto_every_numerical_proposal():
    block = generated_cases.cases()[0].block
    result = candidate.propose(block, canonical(block, reject=True))
    assert result.applicable is True
    assert result.proposals == ()
    assert result.status == "NO_CANONICAL_PROPOSAL"


def test_opaque_fallback_is_empty_and_baseline_quota_is_unchanged():
    opaque = next(case for case in generated_cases.cases() if case.family == "opaque_transcendental_block")
    result = candidate.propose(opaque.block, canonical(opaque.block))
    assert result.status == "OPAQUE_OR_NONPOLYNOMIAL_BASELINE_ONLY"
    assert result.proposals == ()
    assert result.baseline_quota == 0.75
    assert candidate.portfolio_slots(16) == (12, 4)
    assert candidate.portfolio_slots(3) == (3, 0)


def test_equation_permutation_preserves_replayed_points():
    original = next(case.block for case in generated_cases.cases() if case.family == "near_colliding_distinct_roots")
    swapped_equations = candidate.PolynomialBlock(
        original.variable_count,
        tuple(reversed(original.equations)),
        original.lower,
        original.upper,
        rank_signal=original.rank_signal,
    )
    left = candidate.propose(original, canonical(original))
    right = candidate.propose(swapped_equations, canonical(swapped_equations))
    left_points = sorted(tuple(round(value, 6) for value in proposal.point) for proposal in left.proposals)
    right_points = sorted(tuple(round(value, 6) for value in proposal.point) for proposal in right.proposals)
    assert left_points == right_points


def test_variable_permutation_preserves_replayed_points():
    original = next(case.block for case in generated_cases.cases() if case.family == "near_colliding_distinct_roots")
    swapped = candidate.PolynomialBlock(
        2,
        tuple(
            {(exponent[1], exponent[0]): coefficient for exponent, coefficient in polynomial.items()}
            for polynomial in original.equations
        ),
        tuple(reversed(original.lower)),
        tuple(reversed(original.upper)),
        rank_signal=original.rank_signal,
    )
    left = candidate.propose(original, canonical(original))
    right = candidate.propose(swapped, canonical(swapped))
    left_points = sorted(tuple(round(value, 6) for value in proposal.point) for proposal in left.proposals)
    right_points = sorted(
        tuple(round(value, 6) for value in reversed(proposal.point))
        for proposal in right.proposals
    )
    assert left_points == right_points


def test_canonical_replay_exception_fails_closed():
    block = generated_cases.cases()[0].block

    def broken(_point):
        raise RuntimeError("opaque replay failure")

    result = candidate.propose(block, broken)
    assert result.applicable is True
    assert result.proposals == ()


def test_rank_completion_is_deterministic():
    block = next(case.block for case in generated_cases.cases() if case.family == "nilpotent_cusp_block")
    first = candidate.propose(block, canonical(block))
    second = candidate.propose(block, canonical(block))
    assert first == second
