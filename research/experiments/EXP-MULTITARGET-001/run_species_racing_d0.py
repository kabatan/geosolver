#!/usr/bin/env python3
"""Generated D0 for exact-descriptor species side-budget racing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
from typing import Iterable


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import species_racing as candidate  # noqa: E402


ROUTES = ("ordinary", "hp", "branch")
FAMILIES = ("skewed_basin", "close_root", "correlated_start")
TARGET_COUNTS = (1, 2, 5, 10)
REPLICATES = 20
TOTAL_WORK = 128
BLOCK_WORK = 4
SCOUT_WORK_PER_ROUTE = 4


@dataclass(frozen=True)
class GeneratedCase:
    family: str
    target_count: int
    replicate: int

    def descriptor(self, index: int) -> str:
        payload = (
            "generated-authority:"
            f"{self.family}:{self.target_count}:{self.replicate}:{index}"
        )
        return "exact:" + hashlib.sha256(payload.encode()).hexdigest()

    @property
    def authority_set(self) -> frozenset[str]:
        return frozenset(self.descriptor(index) for index in range(self.target_count))

    @property
    def exact_target_values(self) -> tuple[str, ...]:
        if self.family == "close_root":
            return tuple(
                str(Fraction(1, 1) + Fraction(index, 1 << 40))
                for index in range(self.target_count)
            )
        return tuple(str(Fraction(index, 1)) for index in range(self.target_count))


@dataclass(frozen=True)
class ArmResult:
    descriptors: frozenset[str]
    baseline_descriptors: frozenset[str]
    history: tuple[candidate.AuthorityBlock, ...]
    side_plan: tuple[str, ...]
    side_work_by_route: tuple[tuple[str, int], ...]
    rejected_proposals: int
    status: str = candidate.UNKNOWN_STATUS


def _unit_interval(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return integer / 2**64


def _weighted_index(weights: tuple[int, ...], sample: float) -> int:
    total = sum(weights)
    threshold = sample * total
    cumulative = 0
    for index, weight in enumerate(weights):
        cumulative += weight
        if threshold < cumulative:
            return index
    return len(weights) - 1


def _productive_route(case: GeneratedCase) -> str:
    return "hp" if case.family == "close_root" else "branch"


def _proposal(
    case: GeneratedCase,
    *,
    route: str,
    action_ordinal: int,
    block_start: int,
) -> int | str | None:
    invalid = _unit_interval(
        case.family,
        case.target_count,
        case.replicate,
        route,
        action_ordinal,
        "invalid",
    )
    if invalid < 0.03:
        return "outside-generated-authority"
    missing = _unit_interval(
        case.family,
        case.target_count,
        case.replicate,
        route,
        action_ordinal,
        "missing",
    )
    if missing < (0.08 if route == _productive_route(case) else 0.04):
        return None

    if case.target_count == 1:
        return 0
    productive = route == _productive_route(case)
    if productive:
        weights = (1,) * case.target_count
    elif route == "ordinary":
        weights = (1000,) + (1,) * (case.target_count - 1)
    else:
        weights = (1,) + (0,) * (case.target_count - 1)

    # The correlated family deliberately gives every ordinary launch inside a
    # block the same basin draw. The estimator sees one incidence, not four.
    selector_ordinal = (
        block_start
        if case.family == "correlated_start" and route == "ordinary"
        else action_ordinal
    )
    sample = _unit_interval(
        case.family,
        case.target_count,
        case.replicate,
        route,
        selector_ordinal,
        "target",
    )
    return _weighted_index(weights, sample)


def _authority_block(
    case: GeneratedCase,
    *,
    route: str,
    start: int,
    attempts: int,
) -> tuple[candidate.AuthorityBlock, int]:
    descriptors: list[str] = []
    rejected = 0
    for offset in range(attempts):
        proposal = _proposal(
            case,
            route=route,
            action_ordinal=start + offset,
            block_start=start,
        )
        # This is the generated assessor's canonical authority boundary. The
        # policy receives only the accepted opaque descriptor key below.
        if isinstance(proposal, int) and 0 <= proposal < case.target_count:
            descriptors.append(case.descriptor(proposal))
        else:
            rejected += int(proposal is not None)
    block = candidate.AuthorityBlock(
        block_id=f"{route}:{start}:{attempts}",
        route=route,
        attempts=attempts,
        descriptors=tuple(descriptors),
    )
    return block, rejected


def _descriptor_union(blocks: Iterable[candidate.AuthorityBlock]) -> frozenset[str]:
    return frozenset(
        descriptor for block in blocks for descriptor in block.descriptors
    )


def _run_arm(case: GeneratedCase, *, adaptive: bool) -> ArmResult:
    baseline_work, side_work = candidate.split_budget(TOTAL_WORK)
    assert baseline_work == 96 and side_work == 32
    history: list[candidate.AuthorityBlock] = []
    rejected = 0
    next_ordinal = {route: 0 for route in ROUTES}

    for _ in range(baseline_work // BLOCK_WORK):
        start = next_ordinal["ordinary"]
        block, block_rejected = _authority_block(
            case, route="ordinary", start=start, attempts=BLOCK_WORK
        )
        history.append(block)
        rejected += block_rejected
        next_ordinal["ordinary"] += BLOCK_WORK
    baseline_descriptors = _descriptor_union(history)

    side_plan: list[str] = []
    side_work_by_route: Counter[str] = Counter()
    for route in ROUTES:
        for _ in range(SCOUT_WORK_PER_ROUTE // 2):
            start = next_ordinal[route]
            block, block_rejected = _authority_block(
                case, route=route, start=start, attempts=2
            )
            history.append(block)
            rejected += block_rejected
            next_ordinal[route] += 2
            side_work_by_route[route] += 2
            side_plan.append(route)

    remaining = side_work - SCOUT_WORK_PER_ROUTE * len(ROUTES)
    for side_block in range(remaining // BLOCK_WORK):
        if adaptive:
            route = candidate.choose_side_route(history, routes=ROUTES).route
        else:
            route = ROUTES[side_block % len(ROUTES)]
        start = next_ordinal[route]
        block, block_rejected = _authority_block(
            case, route=route, start=start, attempts=BLOCK_WORK
        )
        history.append(block)
        rejected += block_rejected
        next_ordinal[route] += BLOCK_WORK
        side_work_by_route[route] += BLOCK_WORK
        side_plan.append(route)

    descriptors = _descriptor_union(history)
    if not baseline_descriptors.issubset(descriptors):
        raise AssertionError("side-budget policy suppressed baseline authority")
    if sum(side_work_by_route.values()) != side_work:
        raise AssertionError("side work accounting mismatch")
    return ArmResult(
        descriptors=descriptors,
        baseline_descriptors=baseline_descriptors,
        history=tuple(history),
        side_plan=tuple(side_plan),
        side_work_by_route=tuple(
            (route, side_work_by_route[route]) for route in ROUTES
        ),
        rejected_proposals=rejected,
    )


def _metamorphic_checks(result: ArmResult) -> int:
    reference = candidate.choose_side_route(result.history, routes=ROUTES)
    reversed_decision = candidate.choose_side_route(
        tuple(reversed(result.history)), routes=ROUTES
    )
    if reversed_decision.route != reference.route:
        raise AssertionError("independent-block order changed routing")
    if dict(reversed_decision.scores) != dict(reference.scores):
        raise AssertionError("independent-block order changed scores")

    keys = sorted(result.descriptors)
    relabel = {
        key: hashlib.sha256(("relabel:" + key).encode()).hexdigest()
        for key in keys
    }
    transformed = tuple(
        candidate.AuthorityBlock(
            block_id=block.block_id,
            route=block.route,
            attempts=block.attempts,
            descriptors=tuple(relabel[key] for key in block.descriptors),
        )
        for block in result.history
    )
    relabeled_decision = candidate.choose_side_route(transformed, routes=ROUTES)
    if relabeled_decision.route != reference.route:
        raise AssertionError("descriptor relabel changed routing")
    if dict(relabeled_decision.scores) != dict(reference.scores):
        raise AssertionError("descriptor relabel changed scores")
    return 2


def run() -> dict[str, object]:
    family_rows: dict[str, Counter[str]] = {
        family: Counter() for family in FAMILIES
    }
    candidate_route_work: Counter[str] = Counter()
    control_route_work: Counter[str] = Counter()
    total = Counter()
    metamorphic_checks = 0

    for family in FAMILIES:
        for target_count in TARGET_COUNTS:
            for replicate in range(REPLICATES):
                case = GeneratedCase(family, target_count, replicate)
                # Materialize values in the assessor to exercise the close-root
                # family without exposing values to the candidate policy.
                assert len(case.exact_target_values) == target_count
                control = _run_arm(case, adaptive=False)
                observed = _run_arm(case, adaptive=True)
                metamorphic_checks += _metamorphic_checks(observed)

                authority = case.authority_set
                control_extra = control.descriptors - authority
                candidate_extra = observed.descriptors - authority
                gained = observed.descriptors - control.descriptors
                lost = control.descriptors - observed.descriptors
                activated = observed.side_plan != control.side_plan
                complete_control = control.descriptors == authority
                complete_candidate = observed.descriptors == authority
                baseline_suppressed = observed.baseline_descriptors - observed.descriptors

                row = family_rows[family]
                for counter in (row, total):
                    counter["cases"] += 1
                    counter["activation_cases"] += int(activated)
                    counter["descriptor_gains"] += len(gained)
                    counter["descriptor_losses"] += len(lost)
                    counter["case_gains"] += int(bool(gained) and not lost)
                    counter["case_losses"] += int(bool(lost))
                    counter["control_complete_sets"] += int(complete_control)
                    counter["candidate_complete_sets"] += int(complete_candidate)
                    counter["false_or_extra"] += len(control_extra) + len(candidate_extra)
                    counter["baseline_suppressed"] += len(baseline_suppressed)
                    counter["rejected_invalid_proposals"] += (
                        control.rejected_proposals + observed.rejected_proposals
                    )
                for route, work in observed.side_work_by_route:
                    candidate_route_work[route] += work
                for route, work in control.side_work_by_route:
                    control_route_work[route] += work

    improved_families = sum(
        row["descriptor_gains"] > row["descriptor_losses"]
        for row in family_rows.values()
    )
    result: dict[str, object] = {
        "schema": "geotarget.exp-multitarget-001-species-racing-d0/v1",
        "formal_run": False,
        "truth_source": "generated_assessor_only",
        "formal_truth_used": False,
        "holdout_used": False,
        "case_results_persisted": False,
        "common_arm_changed": False,
        "policy": {
            "id": candidate.POLICY_ID,
            "baseline_floor": candidate.BASELINE_FLOOR,
            "total_work_per_arm_case": TOTAL_WORK,
            "baseline_work": candidate.split_budget(TOTAL_WORK)[0],
            "side_work": candidate.split_budget(TOTAL_WORK)[1],
            "routes": list(ROUTES),
            "estimator": "block-incidence Good-Turing unseen mass + bias-corrected Chao2",
            "output_authority": False,
            "completeness_claim": False,
        },
        "generated_panel": {
            "families": list(FAMILIES),
            "target_counts": list(TARGET_COUNTS),
            "replicates_per_cell": REPLICATES,
            "maximum_basin_ratio": 1000,
            "close_root_spacing": "2^-40",
            "correlated_start_blocks": True,
        },
        "aggregate": dict(total),
        "by_family": {
            family: dict(family_rows[family]) for family in FAMILIES
        },
        "side_work_by_route": {
            "control": dict(control_route_work),
            "candidate": dict(candidate_route_work),
        },
        "metamorphic": {
            "checks": metamorphic_checks,
            "failures": 0,
            "transforms": ["independent_block_order", "descriptor_bijection"],
        },
        "reopen_signal": {
            "prior_v4_generated_novel_union": 0,
            "species_policy_activation_cases": total["activation_cases"],
            "species_policy_descriptor_gains": total["descriptor_gains"],
        },
    }
    result["gate"] = {
        "passed": all(
            (
                total["false_or_extra"] == 0,
                total["baseline_suppressed"] == 0,
                total["activation_cases"] > 0,
                total["descriptor_gains"] > total["descriptor_losses"],
                improved_families >= 3,
                metamorphic_checks == total["cases"] * 2,
            )
        ),
        "improved_families": improved_families,
        "status": candidate.UNKNOWN_STATUS,
    }
    return result


def main() -> None:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["gate"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
