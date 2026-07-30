"""Dominance-safe Repair A for exact-descriptor species racing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence

import species_racing


POLICY_ID = "exact_descriptor_species_racing_repair_a"
HIGH_UNSEEN_MASS = 0.5
MIN_CHAO_UNSEEN = 1.0
UNKNOWN_STATUS = species_racing.UNKNOWN_STATUS


@dataclass(frozen=True)
class DeepHandoff:
    """Unstarted work that can only reconfirm one existing descriptor."""

    handoff_id: str
    descriptor: str
    charged_work: int
    started: bool = False
    can_generate_novel_descriptor: bool = False

    def __post_init__(self) -> None:
        if not self.handoff_id or not self.descriptor:
            raise ValueError("handoff identity and descriptor must be nonempty")
        if self.charged_work <= 0:
            raise ValueError("charged_work must be positive")


@dataclass(frozen=True)
class HandoffDecision:
    borrow: bool
    route: str | None
    reason: str
    unseen_mass: float
    chao_unseen: float
    status: str = UNKNOWN_STATUS


def independent_confirmation_count(
    history: Iterable[species_racing.AuthorityBlock], descriptor: str
) -> int:
    """Count independent blocks containing an exact descriptor at least once."""

    return sum(descriptor in set(block.descriptors) for block in history)


def choose_dominance_safe_handoff(
    history: Sequence[species_racing.AuthorityBlock],
    *,
    handoff: DeepHandoff,
    routes: Sequence[str],
) -> HandoffDecision:
    """Borrow only a typed redundant handoff under strong unseen evidence."""

    if handoff.started:
        return HandoffDecision(False, None, "HANDOFF_ALREADY_STARTED", 0.0, 0.0)
    if handoff.can_generate_novel_descriptor:
        return HandoffDecision(False, None, "HANDOFF_NOT_REDUNDANT", 0.0, 0.0)
    if independent_confirmation_count(history, handoff.descriptor) < 2:
        return HandoffDecision(
            False, None, "DESCRIPTOR_NOT_INDEPENDENTLY_CONFIRMED", 0.0, 0.0
        )

    racing = species_racing.choose_side_route(history, routes=routes)
    estimates = dict(racing.estimates)
    estimate = estimates[racing.route]
    if (
        estimate.good_turing_unseen_mass < HIGH_UNSEEN_MASS
        or estimate.chao2_unseen_species < MIN_CHAO_UNSEEN
    ):
        return HandoffDecision(
            False,
            None,
            "UNSEEN_MASS_NOT_HIGH",
            estimate.good_turing_unseen_mass,
            estimate.chao2_unseen_species,
        )
    return HandoffDecision(
        True,
        racing.route,
        "BORROW_REDUNDANT_DEEP_HANDOFF",
        estimate.good_turing_unseen_mass,
        estimate.chao2_unseen_species,
    )


def dominance_safe_union(
    control_union: Iterable[str], proposal_descriptors: Iterable[str]
) -> frozenset[str]:
    """Publish proposals only as an additive union with retained control output."""

    retained = frozenset(control_union)
    combined = retained.union(proposal_descriptors)
    if not retained.issubset(combined):
        raise AssertionError("control descriptor suppression is forbidden")
    return combined


def most_confirmed_descriptor(
    history: Sequence[species_racing.AuthorityBlock],
) -> str | None:
    """Select an already-authoritative descriptor without inspecting its value."""

    incidence: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    for block in history:
        for descriptor in dict.fromkeys(block.descriptors):
            if descriptor not in first_seen:
                first_seen[descriptor] = len(first_seen)
            incidence[descriptor] += 1
    eligible = [item for item in incidence.items() if item[1] >= 2]
    if not eligible:
        return None
    return min(eligible, key=lambda item: (-item[1], first_seen[item[0]]))[0]
