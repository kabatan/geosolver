from __future__ import annotations

import hashlib
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import species_racing  # noqa: E402
import species_racing_repair_a as repair  # noqa: E402


ROUTES = ("ordinary", "hp", "branch")


def _block(name: str, route: str, *keys: str) -> species_racing.AuthorityBlock:
    return species_racing.AuthorityBlock(name, route, 4, tuple(keys))


def _history() -> tuple[species_racing.AuthorityBlock, ...]:
    return (
        _block("o0", "ordinary", "known", "known"),
        _block("o1", "ordinary", "known", "known"),
        _block("h0", "hp", "known", "known"),
        _block("h1", "hp", "known", "known"),
        _block("b0", "branch", "rare-a", "rare-b"),
        _block("b1", "branch", "rare-c", "rare-d"),
    )


def test_borrows_only_redundant_unstarted_independently_confirmed_handoff() -> None:
    handoff = repair.DeepHandoff("deep-0", "known", 4)
    decision = repair.choose_dominance_safe_handoff(
        _history(), handoff=handoff, routes=ROUTES
    )
    assert decision.borrow
    assert decision.route == "branch"
    assert decision.unseen_mass >= repair.HIGH_UNSEEN_MASS


def test_started_novel_or_unconfirmed_handoff_is_never_borrowed() -> None:
    variants = (
        repair.DeepHandoff("started", "known", 4, started=True),
        repair.DeepHandoff(
            "novel", "known", 4, can_generate_novel_descriptor=True
        ),
        repair.DeepHandoff("unconfirmed", "other", 4),
    )
    for handoff in variants:
        decision = repair.choose_dominance_safe_handoff(
            _history(), handoff=handoff, routes=ROUTES
        )
        assert not decision.borrow
        assert decision.route is None


def test_false_saturation_does_not_borrow() -> None:
    history = (
        _block("o0", "ordinary", "known", "known"),
        _block("o1", "ordinary", "known", "known"),
        _block("h0", "hp", "known", "known"),
        _block("h1", "hp", "known", "known"),
        _block("b0", "branch", "known", "known", "known"),
        _block("b1", "branch", "known", "known", "known"),
    )
    decision = repair.choose_dominance_safe_handoff(
        history,
        handoff=repair.DeepHandoff("deep", "known", 4),
        routes=ROUTES,
    )
    assert not decision.borrow
    assert decision.reason == "UNSEEN_MASS_NOT_HIGH"


def test_additive_union_cannot_suppress_control_descriptor() -> None:
    control = frozenset(("a", "b"))
    combined = repair.dominance_safe_union(control, ("b", "c"))
    assert combined == frozenset(("a", "b", "c"))
    assert control <= combined


def test_relabel_and_block_order_preserve_handoff_decision() -> None:
    history = _history()
    reference = repair.choose_dominance_safe_handoff(
        history,
        handoff=repair.DeepHandoff("deep", "known", 4),
        routes=ROUTES,
    )
    keys = {key for block in history for key in block.descriptors}
    mapping = {
        key: hashlib.sha256(("repair:" + key).encode()).hexdigest()
        for key in keys
    }
    transformed = tuple(
        species_racing.AuthorityBlock(
            block.block_id,
            block.route,
            block.attempts,
            tuple(mapping[key] for key in block.descriptors),
        )
        for block in reversed(history)
    )
    observed = repair.choose_dominance_safe_handoff(
        transformed,
        handoff=repair.DeepHandoff("deep", mapping["known"], 4),
        routes=ROUTES,
    )
    assert observed.borrow == reference.borrow
    assert observed.route == reference.route
    assert observed.unseen_mass == reference.unseen_mass
    assert observed.chao_unseen == reference.chao_unseen


def test_policy_surface_is_truth_blind_and_unknown_only() -> None:
    source = (HERE / "species_racing_repair_a.py").read_text(encoding="utf-8")
    for forbidden in (
        "case_id",
        "gold_targets",
        "known_target_count",
        "target_value",
        "expected_answer",
    ):
        assert forbidden not in source
    assert repair.UNKNOWN_STATUS == "UNKNOWN"
