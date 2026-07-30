from __future__ import annotations

import math

import pytest

import candidate
import generated_cases


def canonical(case: generated_cases.GeneratedCase):
    block = case.block
    phase = block.sine_phase

    def replay(source: candidate.SourceCandidate):
        assert phase is not None
        if phase.unit == "radians":
            angle = float(phase.multiplier) * source.value + math.pi * float(phase.offset)
        else:
            angle = 2.0 * math.pi * (
                float(phase.multiplier) * source.value + float(phase.offset)
            )
        cosine, sine = math.cos(angle), math.sin(angle)
        residual = candidate.lifted_residual_inf(block, cosine, sine)
        lower_ok = source.value >= block.lower if block.lower_closed else source.value > block.lower
        upper_ok = source.value <= block.upper if block.upper_closed else source.value < block.upper
        strict_valid = lower_ok and upper_ok
        branch_valid = case.replay_mode != "reject_branch"
        ordinal_valid = case.replay_mode != "reject_ordinal"
        if case.replay_mode == "reject_residual":
            residual = 1.0e-3
        return {
            "safe": bool(
                strict_valid
                and branch_valid
                and ordinal_valid
                and residual <= candidate.REPLAY_RESIDUAL_TOLERANCE
            ),
            "canonical_source_replay": True,
            "strict_guards_valid": strict_valid,
            "branch_valid": branch_valid,
            "ordinal_valid": ordinal_valid,
            "residual_inf": residual,
        }

    return replay


@pytest.mark.parametrize("case", generated_cases.cases(), ids=lambda case: case.family)
def test_generated_families(case):
    result = candidate.propose(case.block, canonical(case))
    assert bool(result.proposals) is case.expect_proposal
    assert result.applicable is case.expect_applicable
    assert result.proposal_is_authority is False
    assert result.canonical_replay_required is True
    for proposal in result.proposals:
        assert proposal.replay_payload["canonical_source_replay"] is True
        assert proposal.replay_payload["strict_guards_valid"] is True
        assert proposal.replay_payload["branch_valid"] is True
        assert proposal.replay_payload["ordinal_valid"] is True
        assert proposal.replay_payload["safe"] is True
        assert proposal.lifted_residual_inf <= candidate.LIFTED_RESIDUAL_TOLERANCE


def test_at_least_three_independent_families_per_category():
    categories = {name: set() for name in ("positive", "negative", "near_miss")}
    for case in generated_cases.cases():
        categories[case.category].add(case.family)
    assert all(len(families) >= 3 for families in categories.values())


def test_antipodal_stereographic_pole_is_not_lost():
    case = next(
        item for item in generated_cases.cases()
        if item.family == "point_on_circle_antipodal_pole"
    )
    result = candidate.propose(case.block, canonical(case))
    assert len(result.proposals) == 1
    assert result.proposals[0].source_value == pytest.approx(0.5)
    assert result.proposals[0].cosine == -1.0
    assert result.pole_checked is True


def test_every_replay_obligation_is_mandatory():
    case = generated_cases.cases()[0]

    def incomplete_replay(_source):
        return {"safe": True, "residual_inf": 0.0, "canonical_source_replay": True}

    result = candidate.propose(case.block, incomplete_replay)
    assert result.applicable is True
    assert result.proposals == ()
    assert result.status == "NO_CANONICAL_PROPOSAL"


def test_canonical_replay_exception_fails_closed():
    case = generated_cases.cases()[0]

    def broken(_source):
        raise RuntimeError("source evaluator unavailable")

    result = candidate.propose(case.block, broken)
    assert result.applicable is True
    assert result.proposals == ()


def test_equation_permutation_preserves_replayed_source_values():
    phase = candidate.PhaseSpec("theta", "radians", candidate.Fraction(1))
    left = candidate.TrigBlock(
        "theta",
        phase,
        phase,
        ({(1, 0): 1.0}, {(2, 0): 1.0}),
        -math.pi,
        math.pi,
    )
    right = candidate.TrigBlock(
        "theta",
        phase,
        phase,
        tuple(reversed(left.equations)),
        left.lower,
        left.upper,
    )
    left_case = generated_cases.GeneratedCase("left", "positive", left, True, True)
    right_case = generated_cases.GeneratedCase("right", "positive", right, True, True)
    left_result = candidate.propose(left, canonical(left_case))
    right_result = candidate.propose(right, canonical(right_case))
    assert [round(item.source_value, 8) for item in left_result.proposals] == [
        round(item.source_value, 8) for item in right_result.proposals
    ]


def test_distance_square_requires_proved_nonnegativity():
    squared = {(0, 0): 2.0, (1, 0): -2.0}
    with pytest.raises(candidate.UnsafeLowering):
        candidate.sound_distance_equality_square(
            candidate.DistanceOperand(squared, nonnegative_proved=False), 1.0
        )
    with pytest.raises(candidate.UnsafeLowering):
        candidate.sound_distance_equality_square(candidate.DistanceOperand(squared), -1.0)
    with pytest.raises(candidate.UnsafeLowering):
        candidate.sound_distance_equality_square(
            candidate.DistanceOperand(squared),
            candidate.DistanceOperand(squared, source_operator="sqrt"),
        )


def test_distance_to_distance_square_is_exactly_a_difference_of_squares():
    left = candidate.DistanceOperand({(0, 0): 2.0, (1, 0): -2.0})
    right = candidate.DistanceOperand({(0, 0): 2.0, (1, 0): 2.0})
    assert candidate.sound_distance_equality_square(left, right) == {(1, 0): -4.0}


def test_baseline_has_at_least_three_quarters_of_slots():
    assert candidate.portfolio_slots(16) == (12, 4)
    assert candidate.portfolio_slots(3) == (3, 0)
    assert candidate.portfolio_slots(1) == (1, 0)


def test_no_forbidden_benchmark_or_truth_fields_in_public_input():
    assert set(candidate.TrigBlock.__dataclass_fields__) == {
        "variable",
        "sine_phase",
        "cosine_phase",
        "equations",
        "lower",
        "upper",
        "lower_closed",
        "upper_closed",
        "semantic_kind",
        "raw_angle_escape",
        "required_branch",
        "required_ordinal",
    }
