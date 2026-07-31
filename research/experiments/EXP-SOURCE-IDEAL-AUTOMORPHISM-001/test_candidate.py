from fractions import Fraction

from candidate import ExactSource, Predicate, PROPOSAL_STATUS, augment_baseline


BASELINE = b"opaque baseline bytes\x00\xff"


def test_sign_orbit_is_replayed_and_baseline_is_untouched():
    source = ExactSource(
        ("x",),
        ("x^2-1",),
        bounds=((Fraction(-2), Fraction(2)),),
    )
    result = augment_baseline(
        source,
        accepted_endpoint=(1.0,),
        baseline_payload=BASELINE,
        replay=lambda point: point in {(1.0,), (-1.0,)},
    )
    assert result.status == PROPOSAL_STATUS
    assert result.proposals == ((-1.0,),)
    assert result.baseline_payload is BASELINE
    assert result.anonymous_signature is not None


def test_guard_breaks_algebraic_sign_symmetry():
    source = ExactSource(
        ("x",),
        ("x^2-1",),
        (Predicate("gt", "x"),),
        ((Fraction(-2), Fraction(2)),),
    )
    result = augment_baseline(
        source,
        accepted_endpoint=(1.0,),
        baseline_payload=BASELINE,
        replay=lambda point: point == (1.0,),
    )
    assert result.proposals == ()
    assert result.source_invalid == 0
    assert result.baseline_payload is BASELINE


def test_replay_disagreement_discards_complete_orbit():
    source = ExactSource(
        ("x",),
        ("x^2-1",),
        bounds=((Fraction(-2), Fraction(2)),),
    )
    result = augment_baseline(
        source,
        accepted_endpoint=(1.0,),
        baseline_payload=BASELINE,
        replay=lambda point: point == (1.0,),
    )
    assert result.proposals == ()
    assert result.source_invalid == 1
    assert result.baseline_payload is BASELINE


def test_equation_row_scaling_and_swap_are_representation_invariant():
    source = ExactSource(
        ("x", "y"),
        ("-3*(x*y-2)", "2*(x+y-3)"),
        bounds=((Fraction(0), Fraction(3)), (Fraction(0), Fraction(3))),
    )
    result = augment_baseline(
        source,
        accepted_endpoint=(1.0, 2.0),
        baseline_payload=BASELINE,
        replay=lambda point: point in {(1.0, 2.0), (2.0, 1.0)},
    )
    assert result.status == PROPOSAL_STATUS
    assert result.proposals == ((2.0, 1.0),)


def test_opaque_unknown_is_byte_identical():
    result = augment_baseline(
        ExactSource(("x",), ("x",), opaque=True),
        accepted_endpoint=(0.0,),
        baseline_payload=BASELINE,
        replay=lambda _point: True,
    )
    assert result.proposals == ()
    assert result.baseline_payload is BASELINE
    assert result.reason == "OPAQUE_SOURCE"


def test_malformed_endpoint_is_byte_identical_unknown():
    result = augment_baseline(
        ExactSource(("x",), ("x",)),
        accepted_endpoint=(object(),),
        baseline_payload=BASELINE,
        replay=lambda _point: True,
    )
    assert result.proposals == ()
    assert result.baseline_payload is BASELINE
    assert result.reason == "MALFORMED_ENDPOINT"
