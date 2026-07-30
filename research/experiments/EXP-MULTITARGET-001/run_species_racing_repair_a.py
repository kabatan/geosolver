#!/usr/bin/env python3
"""Equal-work generated D0 for dominance-safe species Repair A."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Iterable


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import run_species_racing_d0 as d0  # noqa: E402
import species_racing  # noqa: E402
import species_racing_repair_a as repair  # noqa: E402


ROUTES = d0.ROUTES
FAMILIES = (*d0.FAMILIES, "delayed_rare", "false_saturation")
TARGET_COUNTS = d0.TARGET_COUNTS
REPLICATES = 20
TOTAL_WORK = 160
IMMUTABLE_BASELINE_WORK = 96
COUNTER_CAUCHY_WORK = 24
SHARED_SCOUT_WORK = 8
DEEP_HANDOFF_WORK = 32
BLOCK_WORK = 4


@dataclass(frozen=True)
class RepairArmResult:
    control_union: frozenset[str]
    candidate_union: frozenset[str]
    history: tuple[species_racing.AuthorityBlock, ...]
    borrowed_handoffs: int
    retained_handoffs: int
    rejected_proposals: int
    work: int
    status: str = repair.UNKNOWN_STATUS


def _unit_interval(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return integer / 2**64


def _new_family_proposal(
    case: d0.GeneratedCase,
    *,
    route: str,
    action_ordinal: int,
) -> int | str | None:
    invalid = _unit_interval(
        "repair-a",
        case.family,
        case.target_count,
        case.replicate,
        route,
        action_ordinal,
        "invalid",
    )
    if invalid < 0.03:
        return "invalid-generated-proposal"
    if case.target_count == 1:
        return 0

    if case.family == "false_saturation":
        # Several targets exist, but every observed side block reconfirms the
        # common descriptor. Block incidence correctly refuses to infer mass.
        if route != "ordinary":
            return 0
        weights = (1000,) + (1,) * (case.target_count - 1)
        sample = _unit_interval(
            "repair-a",
            case.family,
            case.target_count,
            case.replicate,
            route,
            action_ordinal,
            "target",
        )
        return d0._weighted_index(weights, sample)

    if route != "branch":
        if route == "ordinary":
            weights = (1000,) + (1,) * (case.target_count - 1)
            sample = _unit_interval(
                "repair-a",
                case.family,
                case.target_count,
                case.replicate,
                route,
                action_ordinal,
                "target",
            )
            return d0._weighted_index(weights, sample)
        return 0

    # The first two independent branch blocks expose high unseen incidence;
    # later route prefixes reveal additional and deliberately delayed species.
    return action_ordinal % case.target_count


def _authority_block(
    case: d0.GeneratedCase,
    *,
    route: str,
    start: int,
    attempts: int,
) -> tuple[species_racing.AuthorityBlock, int]:
    if case.family in d0.FAMILIES:
        return d0._authority_block(
            case, route=route, start=start, attempts=attempts
        )

    descriptors: list[str] = []
    rejected = 0
    for offset in range(attempts):
        proposal = _new_family_proposal(
            case, route=route, action_ordinal=start + offset
        )
        if isinstance(proposal, int) and 0 <= proposal < case.target_count:
            descriptors.append(case.descriptor(proposal))
        else:
            rejected += int(proposal is not None)
    return (
        species_racing.AuthorityBlock(
            block_id=f"{route}:{start}:{attempts}",
            route=route,
            attempts=attempts,
            descriptors=tuple(descriptors),
        ),
        rejected,
    )


def _descriptor_union(
    blocks: Iterable[species_racing.AuthorityBlock],
) -> frozenset[str]:
    return frozenset(
        descriptor for block in blocks for descriptor in block.descriptors
    )


def _run_repair(case: d0.GeneratedCase) -> RepairArmResult:
    if (
        IMMUTABLE_BASELINE_WORK
        + COUNTER_CAUCHY_WORK
        + SHARED_SCOUT_WORK
        + DEEP_HANDOFF_WORK
        != TOTAL_WORK
    ):
        raise AssertionError("repair work partition mismatch")
    if (IMMUTABLE_BASELINE_WORK + COUNTER_CAUCHY_WORK) / TOTAL_WORK < 0.75:
        raise AssertionError("protected baseline and insurance fell below 75%")

    history: list[species_racing.AuthorityBlock] = []
    next_ordinal = {route: 0 for route in ROUTES}
    rejected = 0

    # Immutable ordinary prefix.
    for _ in range(IMMUTABLE_BASELINE_WORK // BLOCK_WORK):
        start = next_ordinal["ordinary"]
        block, block_rejected = _authority_block(
            case, route="ordinary", start=start, attempts=BLOCK_WORK
        )
        history.append(block)
        rejected += block_rejected
        next_ordinal["ordinary"] += BLOCK_WORK

    # Byte-equivalent full-support counter-Cauchy insurance remains in both
    # arms. It is ordinary discovery evidence and is never borrowable.
    for _ in range(COUNTER_CAUCHY_WORK // BLOCK_WORK):
        start = next_ordinal["ordinary"]
        block, block_rejected = _authority_block(
            case, route="ordinary", start=start, attempts=BLOCK_WORK
        )
        history.append(block)
        rejected += block_rejected
        next_ordinal["ordinary"] += BLOCK_WORK

    # Two independent, two-action scouts per optional route are common work.
    for route in ("hp", "branch"):
        for _ in range(2):
            start = next_ordinal[route]
            block, block_rejected = _authority_block(
                case, route=route, start=start, attempts=2
            )
            history.append(block)
            rejected += block_rejected
            next_ordinal[route] += 2

    control_union = _descriptor_union(history)
    confirmed = repair.most_confirmed_descriptor(history)
    proposal_descriptors: set[str] = set()
    borrowed = 0
    retained = 0

    for ordinal in range(DEEP_HANDOFF_WORK // BLOCK_WORK):
        if confirmed is None:
            retained += 1
            continue
        handoff = repair.DeepHandoff(
            handoff_id=f"deep:{ordinal}",
            descriptor=confirmed,
            charged_work=BLOCK_WORK,
        )
        decision = repair.choose_dominance_safe_handoff(
            history, handoff=handoff, routes=ROUTES
        )
        if not decision.borrow:
            # The control and candidate both spend this exact work to
            # reconfirm an already-retained authority descriptor.
            retained += 1
            continue
        if decision.route is None:
            raise AssertionError("borrowed handoff lacks a route")
        start = next_ordinal[decision.route]
        block, block_rejected = _authority_block(
            case,
            route=decision.route,
            start=start,
            attempts=handoff.charged_work,
        )
        history.append(block)
        rejected += block_rejected
        next_ordinal[decision.route] += handoff.charged_work
        proposal_descriptors.update(block.descriptors)
        borrowed += 1

    candidate_union = repair.dominance_safe_union(
        control_union, proposal_descriptors
    )
    return RepairArmResult(
        control_union=control_union,
        candidate_union=candidate_union,
        history=tuple(history),
        borrowed_handoffs=borrowed,
        retained_handoffs=retained,
        rejected_proposals=rejected,
        work=TOTAL_WORK,
    )


def _metamorphic_checks(result: RepairArmResult) -> int:
    descriptor = repair.most_confirmed_descriptor(result.history)
    if descriptor is None:
        return 0
    handoff = repair.DeepHandoff("metamorphic", descriptor, BLOCK_WORK)
    reference = repair.choose_dominance_safe_handoff(
        result.history, handoff=handoff, routes=ROUTES
    )
    reversed_decision = repair.choose_dominance_safe_handoff(
        tuple(reversed(result.history)), handoff=handoff, routes=ROUTES
    )
    if (
        reversed_decision.borrow != reference.borrow
        or reversed_decision.route != reference.route
        or reversed_decision.unseen_mass != reference.unseen_mass
        or reversed_decision.chao_unseen != reference.chao_unseen
    ):
        raise AssertionError("independent-block order changed Repair A")

    keys = sorted(_descriptor_union(result.history))
    mapping = {
        key: hashlib.sha256(("repair-relabel:" + key).encode()).hexdigest()
        for key in keys
    }
    transformed = tuple(
        species_racing.AuthorityBlock(
            block.block_id,
            block.route,
            block.attempts,
            tuple(mapping[key] for key in block.descriptors),
        )
        for block in result.history
    )
    relabeled_decision = repair.choose_dominance_safe_handoff(
        transformed,
        handoff=repair.DeepHandoff(
            "metamorphic", mapping[descriptor], BLOCK_WORK
        ),
        routes=ROUTES,
    )
    if (
        relabeled_decision.borrow != reference.borrow
        or relabeled_decision.route != reference.route
        or relabeled_decision.unseen_mass != reference.unseen_mass
        or relabeled_decision.chao_unseen != reference.chao_unseen
    ):
        raise AssertionError("descriptor bijection changed Repair A")
    return 2


def run() -> dict[str, object]:
    aggregate: Counter[str] = Counter()
    family_rows = {family: Counter() for family in FAMILIES}
    metamorphic_checks = 0

    for family in FAMILIES:
        for target_count in TARGET_COUNTS:
            for replicate in range(REPLICATES):
                case = d0.GeneratedCase(family, target_count, replicate)
                result = _run_repair(case)
                metamorphic_checks += _metamorphic_checks(result)
                authority = case.authority_set
                false_or_extra = len(result.candidate_union - authority)
                gained = result.candidate_union - result.control_union
                lost = result.control_union - result.candidate_union
                control_complete = result.control_union == authority
                candidate_complete = result.candidate_union == authority

                for row in (aggregate, family_rows[family]):
                    row["cases"] += 1
                    row["activation_cases"] += int(result.borrowed_handoffs > 0)
                    row["borrowed_handoffs"] += result.borrowed_handoffs
                    row["retained_handoffs"] += result.retained_handoffs
                    row["descriptor_gains"] += len(gained)
                    row["descriptor_losses"] += len(lost)
                    row["strict_gain_cases"] += int(bool(gained))
                    row["loss_cases"] += int(bool(lost))
                    row["control_complete_sets"] += int(control_complete)
                    row["candidate_complete_sets"] += int(candidate_complete)
                    row["false_or_extra"] += false_or_extra
                    row["control_suppressed"] += len(lost)
                    row["work_mismatch"] += int(result.work != TOTAL_WORK)
                    row["rejected_invalid_proposals"] += result.rejected_proposals

    improved_families = sum(
        row["descriptor_gains"] > 0 and row["descriptor_losses"] == 0
        for row in family_rows.values()
    )
    result: dict[str, object] = {
        "schema": "geotarget.exp-multitarget-001-species-racing-repair-a/v1",
        "formal_run": False,
        "formal_truth_used": False,
        "truth_source": "generated_assessor_only",
        "holdout_used": False,
        "case_results_persisted": False,
        "common_arm_changed": False,
        "policy": {
            "id": repair.POLICY_ID,
            "mechanism_change": "borrow only typed redundant unstarted deep handoff",
            "immutable_baseline_work": IMMUTABLE_BASELINE_WORK,
            "counter_cauchy_work": COUNTER_CAUCHY_WORK,
            "shared_scout_work": SHARED_SCOUT_WORK,
            "deep_handoff_work": DEEP_HANDOFF_WORK,
            "total_work_per_arm_case": TOTAL_WORK,
            "protected_fraction": (
                IMMUTABLE_BASELINE_WORK + COUNTER_CAUCHY_WORK
            )
            / TOTAL_WORK,
            "good_turing_high_unseen_mass": repair.HIGH_UNSEEN_MASS,
            "minimum_chao_unseen": repair.MIN_CHAO_UNSEEN,
            "output_policy": "candidate proposals union retained control descriptors",
            "completeness_claim": False,
        },
        "generated_panel": {
            "families": list(FAMILIES),
            "existing_d0_families": list(d0.FAMILIES),
            "adversarial_families": ["delayed_rare", "false_saturation"],
            "target_counts": list(TARGET_COUNTS),
            "replicates_per_cell": REPLICATES,
            "maximum_basin_ratio": 1000,
            "close_root_spacing": "2^-40",
            "correlated_start_blocks": True,
        },
        "aggregate": dict(aggregate),
        "by_family": {
            family: dict(family_rows[family]) for family in FAMILIES
        },
        "metamorphic": {
            "checks": metamorphic_checks,
            "failures": 0,
            "transforms": ["independent_block_order", "descriptor_bijection"],
        },
    }
    result["gate"] = {
        "passed": all(
            (
                aggregate["false_or_extra"] == 0,
                aggregate["descriptor_losses"] == 0,
                aggregate["control_suppressed"] == 0,
                aggregate["work_mismatch"] == 0,
                aggregate["activation_cases"] > 0,
                aggregate["descriptor_gains"] > 0,
                improved_families >= 2,
                metamorphic_checks == aggregate["cases"] * 2,
            )
        ),
        "improved_families": improved_families,
        "status": repair.UNKNOWN_STATUS,
    }
    return result


def main() -> None:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["gate"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
