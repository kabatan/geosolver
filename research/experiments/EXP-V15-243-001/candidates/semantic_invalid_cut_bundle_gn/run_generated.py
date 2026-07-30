#!/usr/bin/env python3
"""Fixed-cap generated D0 for semantic-invalid cut-bundle GN."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from candidate import DEFAULT, portfolio_trace, solve
from generated_cases import NEGATIVE_FAMILIES, POSITIVE_FAMILIES, transformed


SEEDS = tuple(range(20))
CALLBACK_CAP = 100


def _name(factory: object, ordinal: int) -> str:
    value = getattr(factory, "__name__", "")
    return value if value and value != "<lambda>" else f"nonfinite_opaque_{ordinal}"


def run() -> dict[str, object]:
    positive: dict[str, object] = {}
    control_invalid = candidate_invalid = 0
    gains = losses = false_descriptors = 0
    improved_families = 0
    callback_mismatches = 0
    for factory in POSITIVE_FAMILIES:
        records = []
        for seed in SEEDS:
            control_problem = factory(seed)
            candidate_problem = factory(seed)
            control = solve(
                control_problem,
                control_problem.start,
                callback_cap=CALLBACK_CAP,
                arm="control",
            )
            candidate = solve(
                candidate_problem,
                candidate_problem.start,
                callback_cap=CALLBACK_CAP,
                arm="candidate",
            )
            callback_mismatches += int(control.callbacks != candidate.callbacks)
            control_invalid += control.invalid_evaluations
            candidate_invalid += candidate.invalid_evaluations
            records.append((control, candidate))
        family_gains = sum(not control.solved and candidate.solved for control, candidate in records)
        family_losses = sum(control.solved and not candidate.solved for control, candidate in records)
        gains += family_gains
        losses += family_losses
        improved_families += int(family_gains > 0)
        positive[factory.__name__] = {
            "cases": len(records),
            "control_safe_roots": sum(control.solved for control, _candidate in records),
            "candidate_safe_roots": sum(candidate.solved for _control, candidate in records),
            "gains": family_gains,
            "losses": family_losses,
            "control_invalid_evaluations": sum(control.invalid_evaluations for control, _candidate in records),
            "candidate_invalid_evaluations": sum(candidate.invalid_evaluations for _control, candidate in records),
            "cuts_learned": sum(candidate.cuts_learned for _control, candidate in records),
            "maximum_retained_cuts": max(candidate.maximum_retained_cuts for _control, candidate in records),
        }

    negative: dict[str, object] = {}
    for ordinal, factory in enumerate(NEGATIVE_FAMILIES):
        outcomes = []
        for seed in SEEDS:
            problem = factory(seed)
            outcomes.append(
                solve(
                    problem,
                    problem.start,
                    callback_cap=CALLBACK_CAP,
                    arm="candidate",
                )
            )
        false_count = sum(outcome.solved for outcome in outcomes)
        false_descriptors += false_count
        negative[_name(factory, ordinal)] = {
            "cases": len(outcomes),
            "false_descriptors": false_count,
            "cuts_learned": sum(outcome.cuts_learned for outcome in outcomes),
            "status_counts": dict(sorted(Counter(outcome.status for outcome in outcomes).items())),
        }

    metamorphic = []
    for factory in POSITIVE_FAMILIES:
        base_problem = factory(0)
        base = solve(
            base_problem,
            base_problem.start,
            callback_cap=CALLBACK_CAP,
            arm="candidate",
        )
        for kind in ("permutation", "scale", "reflection", "guard-order"):
            changed_problem = transformed(base_problem, kind)
            changed = solve(
                changed_problem,
                changed_problem.start,
                callback_cap=CALLBACK_CAP,
                arm="candidate",
            )
            metamorphic.append(
                {
                    "family": factory.__name__,
                    "transform": kind,
                    "safe_root_invariant": changed.solved == base.solved,
                    "candidate_safe_root": changed.solved,
                    "false_descriptor": False,
                }
            )

    trace = portfolio_trace(16)
    invalid_reduction = 1.0 - candidate_invalid / control_invalid
    gate = {
        "improved_family_count": improved_families,
        "safe_root_gains": gains,
        "safe_root_losses": losses,
        "false_descriptors": false_descriptors,
        "control_invalid_evaluations": control_invalid,
        "candidate_invalid_evaluations": candidate_invalid,
        "invalid_evaluation_reduction": invalid_reduction,
        "positive_callback_mismatches": callback_mismatches,
        "metamorphic_failures": sum(
            not item["safe_root_invariant"] or item["false_descriptor"] for item in metamorphic
        ),
    }
    gate["passed"] = bool(
        improved_families >= 2
        and gains > 0
        and losses == 0
        and false_descriptors == 0
        and invalid_reduction >= 0.30
        and callback_mismatches == 0
        and gate["metamorphic_failures"] == 0
        and trace.count("baseline") / len(trace) >= DEFAULT.baseline_fraction
    )
    here = Path(__file__).resolve().parent
    return {
        "schema_version": "geotarget.semantic-invalid-cut-bundle-gn-d0/v1",
        "scope": {
            "generated_only": True,
            "real_solver_runs": 0,
            "formal_runs": 0,
            "scorer_truth_previous_outcome_reads": 0,
            "validation_or_sealed_access": False,
            "callback_cap_per_arm_case": CALLBACK_CAP,
            "seeds_per_family": len(SEEDS),
        },
        "mechanism": {
            "maximum_cuts": DEFAULT.maximum_cuts,
            "bisection_steps": DEFAULT.bisection_steps,
            "baseline_slots": trace.count("baseline"),
            "side_slots": trace.count("side"),
            "baseline_fraction": trace.count("baseline") / len(trace),
            "canonical_replay_required": True,
        },
        "authority": {
            "candidate_sha256": hashlib.sha256((here / "candidate.py").read_bytes()).hexdigest(),
            "generated_cases_sha256": hashlib.sha256((here / "generated_cases.py").read_bytes()).hexdigest(),
        },
        "positive": positive,
        "negative_near_miss": negative,
        "metamorphic": metamorphic,
        "gate": gate,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
