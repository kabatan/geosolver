"""Truth-blind side-budget racing from canonical descriptor incidences.

This candidate-private policy never accepts, rejects, or removes a descriptor.
It only chooses which proposal route receives the next side-work block after a
fixed ordinary-search prefix has consumed at least 75% of total work.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence


POLICY_ID = "exact_descriptor_species_racing_d0"
BASELINE_FLOOR = 0.75
MIN_INDEPENDENT_BLOCKS = 2
UNKNOWN_STATUS = "UNKNOWN"


@dataclass(frozen=True)
class AuthorityBlock:
    """Canonical-authority observations from one independent start block."""

    block_id: str
    route: str
    attempts: int
    descriptors: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.block_id:
            raise ValueError("block_id must be nonempty")
        if not self.route:
            raise ValueError("route must be nonempty")
        if self.attempts <= 0:
            raise ValueError("attempts must be positive")
        if len(self.descriptors) > self.attempts:
            raise ValueError("authority events cannot exceed attempts")
        if any(not descriptor for descriptor in self.descriptors):
            raise ValueError("descriptor keys must be nonempty")


@dataclass(frozen=True)
class SpeciesEstimate:
    blocks: int
    attempts: int
    authority_events: int
    observed_species: int
    singleton_blocks: int
    doubleton_blocks: int
    incidence_total: int
    good_turing_unseen_mass: float
    chao2_unseen_species: float
    score: float


@dataclass(frozen=True)
class RacingDecision:
    route: str
    scores: tuple[tuple[str, float], ...]
    estimates: tuple[tuple[str, SpeciesEstimate], ...]
    status: str = UNKNOWN_STATUS


def split_budget(total_work: int) -> tuple[int, int]:
    """Return a protected ordinary prefix and a candidate-controlled side."""

    if total_work <= 0:
        raise ValueError("total_work must be positive")
    baseline = math.ceil(BASELINE_FLOOR * total_work)
    return baseline, total_work - baseline


def estimate_unseen(blocks: Iterable[AuthorityBlock]) -> SpeciesEstimate:
    """Estimate unseen incidence mass using block-level Good--Turing/Chao2.

    A descriptor repeated many times by correlated starts inside one block is
    counted once for incidence estimation. This prevents a single correlated
    basin from looking like independent evidence of saturation.
    """

    materialized = tuple(blocks)
    block_ids = [block.block_id for block in materialized]
    if len(block_ids) != len(set(block_ids)):
        raise ValueError("independent block identifiers must be unique")
    if not materialized:
        return SpeciesEstimate(0, 0, 0, 0, 0, 0, 0, 1.0, 1.0, 1.0)

    incidence: Counter[str] = Counter()
    attempts = 0
    events = 0
    for block in materialized:
        attempts += block.attempts
        events += len(block.descriptors)
        incidence.update(set(block.descriptors))

    observed = len(incidence)
    q1 = sum(count == 1 for count in incidence.values())
    q2 = sum(count == 2 for count in incidence.values())
    incidence_total = sum(incidence.values())
    if incidence_total:
        unseen_mass = min(1.0, q1 / incidence_total)
    else:
        unseen_mass = 1.0

    block_count = len(materialized)
    finite_sample = (block_count - 1) / block_count if block_count > 1 else 0.0
    if q2:
        chao = finite_sample * q1 * q1 / (2.0 * q2)
    else:
        chao = finite_sample * q1 * max(0, q1 - 1) / 2.0
    if not incidence:
        chao = 1.0

    unseen_fraction = chao / (observed + chao + 1.0)
    authority_rate = events / attempts
    score = 0.55 * unseen_mass + 0.35 * unseen_fraction + 0.10 * authority_rate
    return SpeciesEstimate(
        blocks=block_count,
        attempts=attempts,
        authority_events=events,
        observed_species=observed,
        singleton_blocks=q1,
        doubleton_blocks=q2,
        incidence_total=incidence_total,
        good_turing_unseen_mass=unseen_mass,
        chao2_unseen_species=chao,
        score=score,
    )


def choose_side_route(
    history: Sequence[AuthorityBlock],
    *,
    routes: Sequence[str],
    route_costs: Mapping[str, float] | None = None,
) -> RacingDecision:
    """Choose one side route without consulting descriptor identities.

    Before every route has two independent blocks, the least-observed route is
    selected. Afterwards the block-incidence score is divided by measured
    route cost. Stable declaration order is used only for exact ties.
    """

    if not routes or len(routes) != len(set(routes)):
        raise ValueError("routes must be a nonempty unique sequence")
    if any(block.route not in routes for block in history):
        raise ValueError("history contains an undeclared route")
    costs = dict(route_costs or {})
    if any(costs.get(route, 1.0) <= 0.0 for route in routes):
        raise ValueError("route costs must be positive")

    grouped = {
        route: tuple(block for block in history if block.route == route)
        for route in routes
    }
    estimates = {route: estimate_unseen(grouped[route]) for route in routes}
    under_sampled = [
        route
        for route in routes
        if estimates[route].blocks < MIN_INDEPENDENT_BLOCKS
    ]
    if under_sampled:
        selected = min(
            under_sampled,
            key=lambda route: (estimates[route].blocks, routes.index(route)),
        )
    else:
        selected = max(
            routes,
            key=lambda route: (
                estimates[route].score / costs.get(route, 1.0),
                -routes.index(route),
            ),
        )
    scores = tuple(
        (route, estimates[route].score / costs.get(route, 1.0))
        for route in routes
    )
    return RacingDecision(
        route=selected,
        scores=scores,
        estimates=tuple((route, estimates[route]) for route in routes),
    )
