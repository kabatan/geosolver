#!/usr/bin/env python3
"""Aggregate-only generated D0 for the config-first repair skeleton."""

from __future__ import annotations

import copy
import hashlib
import json
import os

import sympy as sp

from candidate import consume_repair, repair_or_exact_outer_fallback
from test_candidate import ORIGINAL, exact_replay, gate, refinement


def attempt(raw):
    proposal = refinement(answer=raw)
    payload = repair_or_exact_outer_fallback(
        ORIGINAL,
        aggregate_gate=gate(),
        refinement_proposal=proposal,
        exact_source_replay=exact_replay(proposal, raw),
    )
    return payload, proposal


def main() -> int:
    positives = [
        sp.Rational(7, 3),
        1 + sp.sqrt(2),
        sp.real_root(2, 3),
        sp.sqrt(2) + sp.sqrt(3),
    ]
    positive_pass = sum(consume_repair(attempt(raw)[0]) for raw in positives)

    raw = sp.sqrt(2)
    valid_payload, proposal = attempt(raw)
    replay = exact_replay(proposal, raw)
    negatives = []

    wrong_target = copy.deepcopy(proposal)
    wrong_target["answer_1024bit_minimum"] = "99"
    negatives.append(("wrong_numeric_target", wrong_target, replay, gate()))

    mutated_answer = copy.deepcopy(replay)
    mutated_answer["raw_answer_exact"] = sp.sqrt(3)
    negatives.append(("mutated_exact_answer", proposal, mutated_answer, gate()))

    for name, value in (("undefined_answer", None), ("non_scalar_answer", sp.Matrix([1, 2]))):
        changed = copy.deepcopy(replay)
        changed["raw_answer_exact"] = value
        negatives.append((name, proposal, changed, gate()))

    coordinate_mutation = copy.deepcopy(proposal)
    coordinate_mutation["configuration_algebraic_proposals"][0]["coefficients_high_to_low"] = [1, -9]
    negatives.append(("coordinate_descriptor_mutation", coordinate_mutation, replay, gate()))

    missing_guard = copy.deepcopy(replay)
    missing_guard["guards_exact"] = False
    negatives.append(("guard_obligation_missing", proposal, missing_guard, gate()))
    missing_branch = copy.deepcopy(replay)
    missing_branch["branches_selectors_phases_exact"] = False
    negatives.append(("branch_phase_obligation_missing", proposal, missing_branch, gate()))
    wrong_source = copy.deepcopy(replay)
    wrong_source["replayed_source_sha256"] = hashlib.sha256(b"mutated").hexdigest()
    negatives.append(("source_mutation", proposal, wrong_source, gate()))
    negatives.append(("aggregate_gate_below_ten", proposal, replay, gate(count=9)))
    incomplete = copy.deepcopy(proposal)
    incomplete["configuration_fully_recognized"] = False
    negatives.append(("configuration_incomplete", incomplete, replay, gate()))

    fallback_pass = 0
    for _name, candidate, source_replay, activation in negatives:
        output = repair_or_exact_outer_fallback(
            ORIGINAL,
            aggregate_gate=activation,
            refinement_proposal=candidate,
            exact_source_replay=source_replay,
        )
        fallback_pass += output is ORIGINAL

    mutations = []
    valid = json.loads(valid_payload)
    wrong_root = copy.deepcopy(valid)
    wrong_root["target_descriptor"]["isolating_interval"].update({"left": "-2", "right": "-1"})
    mutations.append(("wrong_root", wrong_root))
    swapped = copy.deepcopy(valid)
    swapped["target_descriptor"]["selected_real_root_index"] = 0
    mutations.append(("swapped_ordinal", swapped))
    descriptor_mutation = copy.deepcopy(valid)
    descriptor_mutation["target_descriptor"]["minimal_polynomial_high_to_low"][0] += 1
    mutations.append(("descriptor_mutation", descriptor_mutation))
    mutation_reject = sum(not consume_repair(json.dumps(item).encode()) for _, item in mutations)

    pslq_a = refinement(answer=raw)
    pslq_b = copy.deepcopy(pslq_a)
    pslq_b["pslq_coefficients_high_to_low"] = [1, 2, 3, 4, 5]
    pslq_b["pslq_1024_lane_residual"] = None
    pslq_b["polynomial_metadata"] = None
    output_a = repair_or_exact_outer_fallback(ORIGINAL, aggregate_gate=gate(), refinement_proposal=pslq_a, exact_source_replay=exact_replay(pslq_a, raw))
    output_b = repair_or_exact_outer_fallback(ORIGINAL, aggregate_gate=gate(), refinement_proposal=pslq_b, exact_source_replay=exact_replay(pslq_b, raw))
    pslq_independent = output_a == output_b and consume_repair(output_a)

    result = {
        "candidate": "CONFIG_FIRST_SOURCE_DERIVED_TARGET_V1",
        "scope": "generated contract/repair skeleton only; dataset activation pending benchmark-owner aggregate",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "positive": {"pass": positive_pass, "total": len(positives), "anonymous_structures": ["rational", "quadratic", "cubic", "quartic"]},
        "fallback_byte_identical": {"pass": fallback_pass, "total": len(negatives), "near_miss_kinds": [name for name, *_ in negatives]},
        "consumer_mutation_rejection": {"pass": mutation_reject, "total": len(mutations), "kinds": [name for name, _ in mutations]},
        "target_pslq_fields_provably_ignored": pslq_independent,
        "truth_or_case_rows_used": False,
        "dataset_activation_gate": "PENDING_AGGREGATE_OWNER",
    }
    result["d0_skeleton_pass"] = bool(
        positive_pass == len(positives)
        and fallback_pass == len(negatives)
        and mutation_reject == len(mutations)
        and pslq_independent
        and os.sched_getaffinity(0) == {15}
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["d0_skeleton_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
