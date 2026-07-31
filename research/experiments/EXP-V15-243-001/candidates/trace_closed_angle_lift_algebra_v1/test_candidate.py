from fractions import Fraction
import itertools

import candidate
import canonical_replay
import generated_cases


def _rejects(reason, function, *args):
    try:
        function(*args)
    except candidate.LiftFailure as error:
        assert str(error).startswith(reason)
    else:
        raise AssertionError("expected fail-closed rejection")


def test_triangle_sum_product_and_original_angle_replay():
    relation, assignment = generated_cases.triangle_sum()
    proposal = candidate.compile_relation(relation)
    assert proposal.cover.exponents == (1, 1, 1)
    assert proposal.cover.target_integer == 1
    assert proposal.winding_ledger.admissible_windings == (0,)
    assert candidate.check_exact_proposal(proposal, assignment).passed
    assert canonical_replay.replay_original_relation(relation, assignment).generated_replay_pass
    assert proposal.authority_pass is False
    assert proposal.target_release is False


def test_rational_sum_difference_denominator_clearing_and_near_miss():
    relation, assignment, near_miss = generated_cases.rational_sum_difference()
    proposal = candidate.compile_relation(relation)
    assert proposal.cover.exponents == (3, 6, -5)
    assert proposal.cover.target_integer == 0
    assert candidate.check_exact_proposal(proposal, assignment).passed
    assert canonical_replay.replay_original_relation(relation, assignment).generated_replay_pass
    assert not candidate.check_exact_proposal(proposal, near_miss).passed
    assert not canonical_replay.replay_original_relation(relation, near_miss).generated_replay_pass


def test_reflection_flips_orientation_but_preserves_algebraic_cover():
    source, assignment = generated_cases.triangle_sum()
    reflected, reflected_assignment = generated_cases.triangle_sum(reflected=True)
    first, second = candidate.compile_relation(source), candidate.compile_relation(reflected)
    assert first.cover.algebraic_cover_sha256 == second.cover.algebraic_cover_sha256
    assert all(entry.required_sign == 1 for entry in second.orientation_ledger)
    assert candidate.check_exact_proposal(second, reflected_assignment).passed
    assert canonical_replay.replay_original_relation(reflected, reflected_assignment).generated_replay_pass


def test_undefined_collinear_fails_orientation_and_replay():
    relation, assignment = generated_cases.undefined_collinear()
    proposal = candidate.compile_relation(relation)
    assert not candidate.check_exact_proposal(proposal, assignment).passed
    assert not canonical_replay.replay_original_relation(relation, assignment).generated_replay_pass


def test_two_pi_alias_and_ambiguous_winding_fail_before_authority():
    alias, _ = generated_cases.two_pi_alias()
    cover = candidate.build_phase_cover(alias)
    assert candidate._zero(cover.imaginary_polynomial)
    assert candidate._sign(cover.sign_polynomial) > 0
    _rejects("NONZERO_OR_AMBIGUOUS_WINDING", candidate.compile_relation, alias)
    ambiguous, _ = generated_cases.winding_ambiguity()
    _rejects("NONZERO_OR_AMBIGUOUS_WINDING", candidate.compile_relation, ambiguous)


def test_term_permutation_is_digest_and_replay_invariant():
    relation, assignment = generated_cases.triangle_sum()
    digests = set()
    for terms in itertools.permutations(relation.terms):
        permuted = candidate.AngleRelation(terms, relation.pi_coefficient)
        proposal = candidate.compile_relation(permuted)
        digests.add(proposal.cover.source_relation_sha256)
        assert candidate.check_exact_proposal(proposal, assignment).passed
        assert canonical_replay.replay_original_relation(permuted, assignment).generated_replay_pass
    assert len(digests) == 1


def test_legacy_sector3_shape_is_explicitly_excluded_and_fallback_is_identity():
    legacy = generated_cases.legacy_sector3_shape()
    assert candidate.is_legacy_sector3_shape(legacy)
    _rejects("LEGACY_SECTOR3_SHAPE_EXCLUDED", candidate.compile_relation, legacy)
    baseline = {"opaque": object()}
    relation, assignment = generated_cases.triangle_sum()
    assert candidate.prejoin_or_baseline(relation, assignment, baseline) is baseline


def test_caps_and_duplicate_key_collision_fail_closed():
    atom = candidate.AngleAtom("cap", (1, 0), (1, 1), 1)
    relation = candidate.AngleRelation(
        (candidate.AngleTerm(atom, Fraction(13)),), Fraction(0)
    )
    _rejects("ABS_EXPONENT_CAP", candidate.compile_relation, relation)
    collision = candidate.AngleAtom("cap", (1, 0), (0, 1), 1)
    malformed = candidate.AngleRelation(
        (
            candidate.AngleTerm(atom, Fraction(1)),
            candidate.AngleTerm(collision, Fraction(1)),
        ),
        Fraction(1),
    )
    _rejects("ANGLE_DAG_KEY_COLLISION", candidate.compile_relation, malformed)

    _rejects(
        "COEFFICIENT_NUMERATOR_BIT_CAP",
        candidate.AngleRelation,
        (candidate.AngleTerm(atom, Fraction(1)),),
        Fraction(1 << 80),
    )
    _rejects(
        "COEFFICIENT_TYPE_FORBIDDEN",
        candidate.AngleTerm,
        atom,
        0.5,
    )


def test_proposal_check_replays_each_principal_range_ledger():
    first = candidate.AngleAtom(
        "range:first",
        (1, 0),
        (1, 1),
        1,
        Fraction(1, 10),
        Fraction(1, 5),
    )
    second = candidate.AngleAtom(
        "range:second",
        (1, 0),
        (-1, 1),
        1,
        Fraction(4, 5),
        Fraction(9, 10),
    )
    relation = candidate.AngleRelation(
        (
            candidate.AngleTerm(first, Fraction(1)),
            candidate.AngleTerm(second, Fraction(1)),
        ),
        Fraction(1),
    )
    proposal = candidate.compile_relation(relation)
    assert candidate._zero(proposal.cover.imaginary_polynomial)
    assert candidate._sign(proposal.cover.sign_polynomial) > 0
    check = candidate.check_exact_proposal(proposal, {})
    assert not check.passed
    assert check.reason == "PRINCIPAL_RANGE_LEDGER_FAILED"
