from __future__ import annotations

from fractions import Fraction

import sympy as sp

from applicability import assess_document, assess_source_document, dry_or_authority
from candidate import TargetProposal


def proposal(coefficients, ordinal, lower, upper):
    return TargetProposal(tuple(coefficients), ordinal, Fraction(lower), Fraction(upper))


def regular_document():
    return {
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x*x", "value": "2"}],
        "guards": ["AssumeGt(x,0)"],
        "answer": "x",
        "post_process": "",
    }


def test_source_only_stops_at_descriptor_seam_with_cost_and_replay() -> None:
    result = assess_document(regular_document())
    assert result["status"] == "HOLD_DESCRIPTOR_SEAM"
    assert result["statically_admissible_if_descriptor_compatible"] is True
    assert result["source_quotient"]["quotient_dimension"] == 2
    assert all(result["replay_target_seams"].values())


def test_real_descriptor_makes_backend_subset_eligibility_decidable() -> None:
    result = assess_document(regular_document(), proposal((1, 0, -2), 1, 1, 2))
    assert result["status"] == "ELIGIBLE_COMPLETE_SUBSET"
    # The quotient counts both algebraic roots; the exact guard/isolator cell
    # filters this finite list to the positive witness during replay.
    assert result["descriptor_conditioned_quotient"]["quotient_dimension"] == 2


def test_positive_dimensional_relevant_fiber_is_ineligible() -> None:
    document = {
        "variables": {"names": ["x", "y"]},
        "construction": [],
        "constraints": [{"def": "x*x", "value": "2"}],
        "guards": ["AssumeGt(y,0)"],
        "answer": "x",
        "post_process": "",
    }
    result = assess_document(document, proposal((1, 0, -2), 1, 1, 2))
    assert result["status"] == "INELIGIBLE_POSITIVE_DIMENSIONAL_RELEVANT_FIBER"


def test_dry_or_route_requires_replay_and_preserves_baseline() -> None:
    failed = {"status": "NOT_PROVED", "authority_pass": False, "sentinel": 7}
    emitted = dry_or_authority(
        failed, regular_document(), proposal((1, 0, -2), 1, 1, 2)
    )
    assert emitted["authority_pass"] is True
    assert emitted["all_emissions_require_independent_replay"] is True
    replay = emitted["target_constrained_exact_witness"]["independent_replay"]
    assert replay["untouched_source_dsl_replay"] is True
    assert replay["raw_target_link"] is True

    existing = {"status": "TARGET_AUTHORITY_READY", "authority_pass": True, "sentinel": 9}
    assert dry_or_authority(
        existing, regular_document(), proposal((1, 0, -2), 1, 1, 2)
    ) == existing


def test_existing_zero_dimensional_route_is_immutable() -> None:
    baseline = {
        "status": "NOT_PROVED",
        "authority_pass": False,
        "archive_reopen_execution_route": "existing_source_exact_zero_dimensional_authority",
    }
    assert dry_or_authority(
        baseline, regular_document(), proposal((1, 0, -2), 1, 1, 2)
    ) == baseline


def test_wrong_descriptor_cannot_emit_or_authority() -> None:
    baseline = {"status": "NOT_PROVED", "authority_pass": False, "sentinel": 11}
    assert dry_or_authority(
        baseline, regular_document(), proposal((1, 0, -3), 1, 1, 2)
    ) == baseline


def test_existing_primitive_cover_is_thinly_reused_for_static_target_link() -> None:
    document = {
        "variables": {"names": ["x"]},
        "construction": [
            {"name": "A", "expr": "Point(0,0)"},
            {"name": "B", "expr": "Point(x,0)"},
            {"name": "M", "expr": "Midpoint(A,B)"},
        ],
        "constraints": [{"def": "x*x", "value": "2"}],
        "guards": ["AssumeGt(x,0)"],
        "answer": "Distance(A,M)",
        "post_process": "",
    }
    result = assess_source_document(document)
    assert result["semantic_frontend_route"] == "digest-pinned-existing-primitive-cover"
    assert result["status"] == "HOLD_DESCRIPTOR_SEAM"
    assert result["statically_admissible_if_descriptor_compatible"] is True
    assert result["candidate_private_exact_target_link_present"] is True
    assert result["source_replay_authority_bridge_wired"] is False
