from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import pytest


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import species_racing as candidate  # noqa: E402


def _block(name: str, route: str, *descriptors: str) -> candidate.AuthorityBlock:
    return candidate.AuthorityBlock(name, route, 4, tuple(descriptors))


def test_budget_floor_is_never_below_seventy_five_percent() -> None:
    for total in range(1, 513):
        baseline, side = candidate.split_budget(total)
        assert baseline + side == total
        assert baseline / total >= 0.75


def test_block_incidence_does_not_overcount_correlated_repeats() -> None:
    estimate = candidate.estimate_unseen(
        (
            _block("b0", "ordinary", "a", "a", "a", "a"),
            _block("b1", "ordinary", "a", "a", "a", "a"),
            _block("b2", "ordinary", "b", "b", "b", "b"),
        )
    )
    assert estimate.authority_events == 12
    assert estimate.incidence_total == 3
    assert estimate.singleton_blocks == 1
    assert estimate.doubleton_blocks == 1
    assert estimate.good_turing_unseen_mass == pytest.approx(1 / 3)


def test_species_racing_activates_on_unseen_incidence() -> None:
    history = (
        _block("o0", "ordinary", "common", "common"),
        _block("o1", "ordinary", "common", "common"),
        _block("h0", "hp", "common", "common"),
        _block("h1", "hp", "common", "common"),
        _block("b0", "branch", "rare-1", "rare-2"),
        _block("b1", "branch", "rare-3", "rare-4"),
    )
    decision = candidate.choose_side_route(
        history, routes=("ordinary", "hp", "branch")
    )
    assert decision.route == "branch"
    assert decision.status == "UNKNOWN"


def test_descriptor_relabel_and_block_order_are_metamorphic() -> None:
    history = (
        _block("o0", "ordinary", "a", "a"),
        _block("o1", "ordinary", "a", "a"),
        _block("h0", "hp", "a", "b"),
        _block("h1", "hp", "c", "d"),
        _block("b0", "branch", "a", "a"),
        _block("b1", "branch", "a", "a"),
    )
    relabel = {
        key: hashlib.sha256(key.encode()).hexdigest()
        for key in {descriptor for block in history for descriptor in block.descriptors}
    }
    transformed = tuple(
        candidate.AuthorityBlock(
            block.block_id,
            block.route,
            block.attempts,
            tuple(relabel[value] for value in block.descriptors),
        )
        for block in reversed(history)
    )
    reference = candidate.choose_side_route(
        history, routes=("ordinary", "hp", "branch")
    )
    observed = candidate.choose_side_route(
        transformed, routes=("ordinary", "hp", "branch")
    )
    assert observed.route == reference.route
    assert dict(observed.scores) == pytest.approx(dict(reference.scores))


def test_duplicate_block_identifier_fails_closed() -> None:
    with pytest.raises(ValueError, match="unique"):
        candidate.estimate_unseen(
            (_block("same", "ordinary", "a"), _block("same", "ordinary", "b"))
        )


def test_policy_surface_is_truth_blind_and_not_output_authority() -> None:
    source = (HERE / "species_racing.py").read_text(encoding="utf-8")
    for forbidden in (
        "case_id",
        "gold_targets",
        "known_target_count",
        "target_value",
        "expected_answer",
    ):
        assert forbidden not in source
    assert "UNKNOWN_STATUS" in source
