#!/usr/bin/env python3
"""Run generated equal-budget D0 and write aggregate-only evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import candidate
import generated_cases


HERE = Path(__file__).resolve().parent
SEEDS_PER_FAMILY = 128


def _trace(result: candidate.RacingResult):
    return tuple(
        (attempt.endpoint_key, attempt.rung, attempt.status, attempt.censored)
        for attempt in result.attempts
    )


def run() -> dict[str, object]:
    totals = {
        "paired_cases": 0,
        "gain": 0,
        "loss": 0,
        "false": 0,
        "extra": 0,
        "work_mismatch": 0,
        "insurance_failure": 0,
        "permutation_failure": 0,
        "censor_prefix_failure": 0,
        "candidate_invalid_outcomes": 0,
    }
    by_family: dict[str, dict[str, int]] = {}
    configuration = candidate.Configuration()
    for family in generated_cases.FAMILIES:
        family_rows = {"cases": 0, "gain": 0, "loss": 0, "false": 0, "extra": 0}
        for seed in range(SEEDS_PER_FAMILY):
            case = generated_cases.make_case(family, seed)
            control = candidate.run_racing(
                case.endpoints,
                generated_cases.Backend(case),
                candidate.Arm.CONTROL,
                configuration,
            )
            racing = candidate.run_racing(
                case.endpoints,
                generated_cases.Backend(case),
                candidate.Arm.CANDIDATE,
                configuration,
            )
            control_set = set(control.descriptors)
            candidate_set = set(racing.descriptors)
            expected = set(case.expected_descriptors)
            gain = bool(candidate_set > control_set)
            loss = not control_set.issubset(candidate_set)
            false = not candidate_set.issubset(expected)
            extra = len(candidate_set - expected)
            totals["paired_cases"] += 1
            totals["gain"] += int(gain)
            totals["loss"] += int(loss)
            totals["false"] += int(false)
            totals["extra"] += extra
            totals["candidate_invalid_outcomes"] += racing.invalid_outcomes
            totals["work_mismatch"] += int(
                control.charged_callbacks != racing.charged_callbacks
                or control.charged_wall_seconds != racing.charged_wall_seconds
            )
            totals["insurance_failure"] += int(not racing.first_probe_insurance_holds)
            family_rows["cases"] += 1
            family_rows["gain"] += int(gain)
            family_rows["loss"] += int(loss)
            family_rows["false"] += int(false)
            family_rows["extra"] += extra

            for salt in range(3):
                transformed = generated_cases.permuted(case, salt)
                permuted = candidate.run_racing(
                    transformed.endpoints,
                    generated_cases.Backend(transformed),
                    candidate.Arm.CANDIDATE,
                    configuration,
                )
                totals["permutation_failure"] += int(
                    permuted.descriptors != racing.descriptors
                    or _trace(permuted) != _trace(racing)
                )
            for cap in (1, 3, 4, 7, 8, 11, 12, 15):
                censored = candidate.run_racing(
                    case.endpoints,
                    generated_cases.Backend(case),
                    candidate.Arm.CANDIDATE,
                    configuration,
                    maximum_dispatches=cap,
                )
                totals["censor_prefix_failure"] += int(
                    _trace(censored) != _trace(racing)[:cap]
                    or not set(censored.descriptors).issubset(candidate_set)
                )
        by_family[family] = family_rows

    gates = {
        "at_least_three_families": len(by_family) >= 3,
        "gain_in_at_least_two_families": sum(row["gain"] > 0 for row in by_family.values()) >= 2,
        "loss_zero": totals["loss"] == 0,
        "false_zero": totals["false"] == 0,
        "extra_zero": totals["extra"] == 0,
        "equal_callback_and_wall_budget": totals["work_mismatch"] == 0,
        "untried_insurance_75pct": totals["insurance_failure"] == 0,
        "endpoint_permutation_invariant": totals["permutation_failure"] == 0,
        "censor_prefix_invariant": totals["censor_prefix_failure"] == 0,
        "ordinary_opaque_fail_closed": totals["candidate_invalid_outcomes"] == 0,
    }
    document: dict[str, object] = {
        "schema_version": "geotarget.exp-v15-243.cross-endpoint-hp-voi-d0/v1",
        "decision": "GO_PROSPECTIVE_SEAM" if all(gates.values()) else "STOP_D0_GATE",
        "generated_only": True,
        "formal_screen_executed": False,
        "scorer_used": False,
        "benchmark_truth_used": False,
        "individual_case_results_emitted": False,
        "configuration": candidate.configuration_manifest(),
        "totals": totals,
        "by_family": by_family,
        "gates": gates,
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    document["content_sha256_before_self_field"] = hashlib.sha256(encoded).hexdigest()
    return document


def main() -> None:
    output = HERE / "AGGREGATE.json"
    output.write_text(json.dumps(run(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
