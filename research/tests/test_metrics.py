from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from research.harness.bootstrap import (
    ClusteredValue,
    PairedValue,
    family_clustered_lower_bound,
    family_clustered_paired_bootstrap,
    load_bootstrap_plan,
    make_bootstrap_plan,
    save_bootstrap_plan,
)
from research.harness.matching import RunEvaluation, evaluate_run
from research.harness.metrics import (
    aggregate_metrics,
    assess_zero_answer_safety_controls,
    exact_prefix_monotonicity,
    exact_stability_27_of_30,
    prefix_monotonicity,
    stability_27_of_30,
)
from research.harness.models import InputError, parse_case_input, parse_run_input
from research.harness.partitions import (
    AccessMode,
    Partition,
    PartitionAccessError,
    PartitionRecord,
    PartitionRegistry,
    PartitionStatus,
)


def interval(lower: str, upper: str | None = None, *, certified: bool = True) -> dict:
    return {"lower": lower, "upper": upper or lower, "certified": certified}


def case_data(
    *,
    case_id: str = "case-1",
    family_id: str = "family-1",
    strata: list[str] | None = None,
    domain_kind: str = "bounded",
    exact_eligible: bool = True,
    matching: dict | None = None,
    targets: list[dict] | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "family_id": family_id,
        "strata": strata or ["S1"],
        "domain_kind": domain_kind,
        "exact_eligible": exact_eligible,
        "matching": matching or {"mode": "certified_interval"},
        "gold_targets": targets
        or [{"target_id": "target-1", "interval": interval("1")}],
    }


def answer_data(
    *,
    answer_id: str = "answer-1",
    level: str = "validated",
    value_interval: dict | None = None,
    branch: str | None = None,
    configuration_validated: bool = True,
    target_identity_certified: bool = False,
    guard_valid: bool = True,
    boundary_valid: bool = True,
    configuration_id: str | None = "config-1",
) -> dict:
    return {
        "answer_id": answer_id,
        "level": level,
        "interval": value_interval or interval("1"),
        "branch": branch,
        "configuration_validated": configuration_validated,
        "target_identity_certified": target_identity_certified,
        "guard_valid": guard_valid,
        "boundary_valid": boundary_valid,
        "configuration_id": configuration_id,
    }


def run_data(
    answers: list[dict],
    *,
    run_id: str = "run-1",
    case_id: str = "case-1",
    seed: int = 0,
    budget: int = 180,
    claims_complete: bool = False,
    coverage_certificate: bool = False,
) -> dict:
    return {
        "run_id": run_id,
        "case_id": case_id,
        "seed": seed,
        "budget_seconds": budget,
        "answers": answers,
        "claims_complete": claims_complete,
        "coverage_certificate": coverage_certificate,
    }


def evaluated(
    case: dict | None = None,
    answers: list[dict] | None = None,
    **run_kwargs,
) -> RunEvaluation:
    parsed_case = parse_case_input(case or case_data())
    parsed_run = parse_run_input(run_data(answers or [], case_id=parsed_case.case_id, **run_kwargs))
    return evaluate_run(parsed_case, parsed_run)


class InputAndMatchingTests(unittest.TestCase):
    def test_binary_float_and_overlapping_certified_gold_are_rejected(self) -> None:
        bad_float = case_data(
            targets=[
                {
                    "target_id": "target-1",
                    "interval": {"lower": 1.0, "upper": "1", "certified": True},
                }
            ]
        )
        with self.assertRaisesRegex(InputError, "binary floats"):
            parse_case_input(bad_float)

        overlap = case_data(
            targets=[
                {"target_id": "a", "interval": interval("0", "1")},
                {"target_id": "b", "interval": interval("1", "2")},
            ]
        )
        with self.assertRaisesRegex(InputError, "must be disjoint"):
            parse_case_input(overlap)

    def test_same_target_multiple_configurations_is_one_answer_value(self) -> None:
        answers = [
            answer_data(
                answer_id="a",
                level="exact",
                target_identity_certified=True,
                configuration_id="left-configuration",
            ),
            answer_data(
                answer_id="b",
                level="exact",
                target_identity_certified=True,
                configuration_id="right-configuration",
            ),
        ]
        result = evaluated(answers=answers)
        self.assertTrue(result.full_validated)
        self.assertTrue(result.full_exact)
        self.assertEqual(result.covered_exact_targets, {"target-1"})
        self.assertEqual(result.duplicate_validated_witnesses, 1)
        self.assertEqual(result.duplicate_exact_witnesses, 1)
        self.assertEqual(result.false_answer_count, 0)

    def test_false_output_categories_and_complete_claim_are_release_blocking(self) -> None:
        case = case_data(
            targets=[
                {
                    "target_id": "target-1",
                    "interval": interval("1"),
                    "allowed_branches": ["left"],
                }
            ]
        )
        wrong = evaluated(
            case,
            [
                answer_data(
                    branch="right",
                    boundary_valid=False,
                    guard_valid=False,
                )
            ],
            claims_complete=True,
        )
        self.assertEqual(wrong.false_validated_count, 1)
        self.assertEqual(wrong.false_branch_count, 1)
        self.assertEqual(wrong.false_boundary_count, 1)
        self.assertEqual(wrong.false_guard_count, 1)
        self.assertEqual(wrong.false_complete_count, 1)

        false_exact = evaluated(
            answers=[answer_data(level="exact", target_identity_certified=False)]
        )
        self.assertEqual(false_exact.false_exact_count, 1)
        self.assertFalse(false_exact.full_exact)

    def test_full_targets_do_not_launder_an_unproved_complete_claim(self) -> None:
        result = evaluated(
            answers=[answer_data()], claims_complete=True, coverage_certificate=False
        )
        self.assertTrue(result.full_validated)
        self.assertEqual(result.false_complete_count, 1)
        self.assertEqual(result.safety_violation_count, 1)

    def test_declared_tolerance_is_explicit_and_rejects_broad_intervals(self) -> None:
        case = case_data(
            matching={"mode": "declared_tolerance", "tolerance": "0.1"},
            targets=[
                {
                    "target_id": "target-1",
                    "interval": interval("1", certified=False),
                }
            ],
        )
        nearby = evaluated(
            case,
            [answer_data(value_interval=interval("1.05", certified=False))],
        )
        self.assertTrue(nearby.full_validated)
        broad = evaluated(
            case,
            [answer_data(value_interval=interval("0", "2", certified=False))],
        )
        self.assertEqual(broad.false_validated_count, 1)


class MetricTests(unittest.TestCase):
    def test_aggregate_reports_strata_domains_exact_denominator_and_false_counts(self) -> None:
        full = evaluated(answers=[answer_data(level="exact", target_identity_certified=True)])
        unbounded_case = case_data(
            case_id="case-2",
            family_id="family-2",
            strata=["S2", "S8"],
            domain_kind="adaptive_unbounded",
            exact_eligible=False,
        )
        false = evaluated(
            unbounded_case,
            [answer_data(value_interval=interval("9"))],
            run_id="run-2",
        )
        report = aggregate_metrics(
            [full, false], budget_seconds=180, bootstrap_resamples=100, bootstrap_seed=7
        )
        self.assertEqual(report.overall.p_full_validated, 0.5)
        self.assertEqual(report.overall.p_full_exact, 1.0)
        self.assertEqual(report.overall.exact_eligible_run_count, 1)
        self.assertEqual(report.overall.false_validated_count, 1)
        self.assertEqual(len(report.by_stratum), 8)
        self.assertEqual(report.by_stratum[0].p_full_validated, 1.0)
        self.assertEqual(report.by_stratum[1].p_full_validated, 0.0)
        self.assertIsNone(report.by_stratum[2].p_full_validated)
        domains = {item.label: item for item in report.by_domain_kind}
        self.assertEqual(domains["bounded"].p_full_validated, 1.0)
        self.assertEqual(domains["adaptive_unbounded"].p_full_validated, 0.0)

    def test_stability_requires_the_complete_seed_grid(self) -> None:
        base = evaluated(answers=[answer_data()])
        runs = [replace(base, run_id=f"run-{seed}", seed=seed) for seed in range(30)]
        for index in range(3):
            runs[index] = replace(
                runs[index],
                covered_validated_targets=frozenset(),
                full_validated=False,
            )
        report = stability_27_of_30(runs)
        self.assertTrue(report.cases[0].stable_27_of_30)
        self.assertTrue(report.release_pass)

        incomplete = stability_27_of_30(runs[:-1])
        self.assertEqual(incomplete.cases[0].missing_seeds, (29,))
        self.assertFalse(incomplete.cases[0].stable_27_of_30)
        self.assertFalse(incomplete.release_pass)

        entirely_missing = stability_27_of_30(
            runs,
            expected_case_families={
                "case-1": "family-1",
                "case-never-ran": "family-missing",
            },
        )
        missing_case = next(
            item for item in entirely_missing.cases if item.case_id == "case-never-ran"
        )
        self.assertEqual(missing_case.missing_seeds, tuple(range(30)))
        self.assertFalse(entirely_missing.release_pass)

    def test_exact_stability_uses_full_exact_and_requires_exact_eligibility(
        self,
    ) -> None:
        base = evaluated(
            answers=[answer_data(level="exact", target_identity_certified=True)]
        )
        runs = [replace(base, run_id=f"run-{seed}", seed=seed) for seed in range(30)]
        for index in range(3):
            runs[index] = replace(
                runs[index],
                covered_exact_targets=frozenset(),
                full_exact=False,
            )

        report = exact_stability_27_of_30(runs)
        self.assertEqual(report.cases[0].success_count, 27)
        self.assertTrue(report.cases[0].stable_27_of_30)
        self.assertTrue(report.release_pass)

        four_misses = list(runs)
        four_misses[3] = replace(
            four_misses[3],
            covered_exact_targets=frozenset(),
            full_exact=False,
        )
        self.assertFalse(exact_stability_27_of_30(four_misses).release_pass)

        nonexact = replace(base, exact_eligible=False, full_exact=False)
        with self.assertRaisesRegex(ValueError, "exact-eligible"):
            exact_stability_27_of_30([nonexact])

    def test_prefix_reports_losses_and_recovers_short_budget_misses(self) -> None:
        full_short = evaluated(answers=[answer_data()], run_id="short-a")
        lost_long = replace(
            full_short,
            run_id="long-a",
            budget_seconds=420,
            covered_validated_targets=frozenset(),
            full_validated=False,
        )
        miss_short = evaluated(
            case_data(case_id="case-2", family_id="family-2"),
            [],
            run_id="short-b",
        )
        recovered_long = replace(
            miss_short,
            run_id="long-b",
            budget_seconds=420,
            covered_validated_targets=miss_short.gold_target_ids,
            full_validated=True,
        )
        report = prefix_monotonicity(
            [full_short, lost_long, miss_short, recovered_long]
        )
        self.assertEqual(report.remaining_short_misses, 1)
        self.assertEqual(report.recovered_fraction, 1.0)
        self.assertEqual(report.validated_losses[0].lost_target_ids, ("target-1",))
        self.assertFalse(report.release_pass)

        clean = prefix_monotonicity([miss_short, recovered_long])
        self.assertTrue(clean.release_pass)

    def test_exact_prefix_uses_exact_sets_and_full_exact_recovery(self) -> None:
        full_short = evaluated(
            answers=[answer_data(level="exact", target_identity_certified=True)],
            run_id="short-a",
        )
        lost_long = replace(
            full_short,
            run_id="long-a",
            budget_seconds=420,
            covered_exact_targets=frozenset(),
            full_exact=False,
        )
        miss_short = replace(
            full_short,
            run_id="short-b",
            case_id="case-2",
            family_id="family-2",
            covered_exact_targets=frozenset(),
            full_exact=False,
        )
        recovered_long = replace(
            miss_short,
            run_id="long-b",
            budget_seconds=420,
            covered_exact_targets=miss_short.gold_target_ids,
            full_exact=True,
        )

        report = exact_prefix_monotonicity(
            [full_short, lost_long, miss_short, recovered_long]
        )
        self.assertEqual(report.remaining_short_exact_misses, 1)
        self.assertEqual(report.recovered_short_exact_misses, 1)
        self.assertEqual(report.recovered_fraction, 1.0)
        self.assertEqual(report.exact_losses[0].lost_target_ids, ("target-1",))
        self.assertFalse(report.release_pass)

        clean = exact_prefix_monotonicity([miss_short, recovered_long])
        self.assertTrue(clean.no_exact_answer_loss)
        self.assertTrue(clean.release_pass)

    def test_zero_answer_controls_are_safety_only_and_require_no_output(self) -> None:
        safe = evaluated(answers=[], run_id="safe", seed=0)
        safe_report = assess_zero_answer_safety_controls([safe], budget_seconds=180)
        self.assertEqual(safe_report.control_run_count, 1)
        self.assertEqual(safe_report.completion_denominator_count, 0)
        self.assertEqual(safe_report.reported_answer_count, 0)
        self.assertTrue(safe_report.release_pass)

        false_exact = evaluated(
            answers=[
                answer_data(
                    level="exact",
                    target_identity_certified=True,
                    value_interval=interval("9"),
                )
            ],
            run_id="false-exact",
            seed=1,
        )
        branch_case = case_data(
            targets=[
                {
                    "target_id": "target-1",
                    "interval": interval("1"),
                    "allowed_branches": ["left"],
                }
            ]
        )
        false_validated = evaluated(
            branch_case,
            [answer_data(branch="right", boundary_valid=False)],
            run_id="false-validated",
            seed=2,
        )
        false_complete = evaluated(
            answers=[], run_id="false-complete", seed=3, claims_complete=True
        )
        unsafe = assess_zero_answer_safety_controls(
            [false_exact, false_validated, false_complete],
            budget_seconds=180,
        )
        self.assertEqual(unsafe.reported_answer_count, 2)
        self.assertEqual(unsafe.false_exact_count, 1)
        self.assertEqual(unsafe.false_validated_count, 1)
        self.assertEqual(unsafe.false_branch_count, 1)
        self.assertEqual(unsafe.false_boundary_count, 1)
        self.assertEqual(unsafe.false_complete_count, 1)
        self.assertFalse(unsafe.release_pass)

        accepted = evaluated(
            answers=[answer_data(level="exact", target_identity_certified=True)],
            run_id="accepted",
            seed=4,
        )
        accepted_report = assess_zero_answer_safety_controls(
            [accepted], budget_seconds=180
        )
        self.assertEqual(accepted_report.false_exact_count, 0)
        self.assertEqual(accepted_report.reported_answer_count, 1)
        self.assertFalse(accepted_report.release_pass)

        self.assertFalse(
            assess_zero_answer_safety_controls([], budget_seconds=180).release_pass
        )


class BootstrapTests(unittest.TestCase):
    def test_equal_family_weighting_and_paired_difference(self) -> None:
        values = [
            ClusteredValue("large-family", "a", 1.0),
            ClusteredValue("large-family", "b", 1.0),
            ClusteredValue("small-family", "c", 0.0),
        ]
        result = family_clustered_lower_bound(values, resamples=200, seed=11)
        self.assertEqual(result.estimate, 0.5)

        paired = family_clustered_paired_bootstrap(
            [
                PairedValue("large-family", "a", 1.0, 0.0),
                PairedValue("large-family", "b", 1.0, 0.0),
                PairedValue("small-family", "c", 0.0, 1.0),
            ],
            resamples=200,
            seed=11,
        )
        self.assertEqual(paired.estimate, 0.0)

    def test_saved_indices_and_checksum_are_replay_truth(self) -> None:
        plan = make_bootstrap_plan(["b", "a"], resamples=25, seed=19)
        same = make_bootstrap_plan(["a", "b"], resamples=25, seed=19)
        self.assertEqual(plan, same)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            save_bootstrap_plan(plan, path)
            self.assertEqual(load_bootstrap_plan(path), plan)
            tampered = json.loads(path.read_text(encoding="utf-8"))
            tampered["resample_indices"][0][0] = 1 - tampered["resample_indices"][0][0]
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                load_bootstrap_plan(path)


class PartitionTests(unittest.TestCase):
    def make_registry(self) -> PartitionRegistry:
        return PartitionRegistry(
            [
                PartitionRecord(
                    "dev-v1",
                    Partition.D1,
                    PartitionStatus.DEVELOPMENT,
                    frozenset({"family-dev"}),
                ),
                PartitionRecord(
                    "locked-v1",
                    Partition.V1,
                    PartitionStatus.LOCKED,
                    frozenset({"family-locked"}),
                ),
                PartitionRecord(
                    "blind-v1",
                    Partition.F1,
                    PartitionStatus.BLIND,
                    frozenset({"family-blind"}),
                ),
            ]
        )

    def test_development_rejects_locked_and_blind_truth(self) -> None:
        registry = self.make_registry()
        self.assertEqual(
            registry.access("dev-v1", AccessMode.DEVELOPMENT).record_id, "dev-v1"
        )
        with self.assertRaises(PartitionAccessError):
            registry.access("locked-v1", AccessMode.DEVELOPMENT)
        with self.assertRaises(PartitionAccessError):
            registry.access("blind-v1", AccessMode.DEVELOPMENT)
        self.assertEqual(
            registry.access("locked-v1", AccessMode.VALIDATION_EVALUATION).record_id,
            "locked-v1",
        )
        self.assertEqual(
            registry.access("blind-v1", AccessMode.BLIND_EVALUATION).record_id,
            "blind-v1",
        )

    def test_burn_requires_disjoint_replacement_and_is_atomic(self) -> None:
        registry = self.make_registry()
        collision = PartitionRecord(
            "blind-v2",
            Partition.F1,
            PartitionStatus.BLIND,
            frozenset({"family-dev"}),
            replacement_for="blind-v1",
        )
        with self.assertRaisesRegex(ValueError, "partition-disjoint"):
            registry.burn_and_replace("blind-v1", collision, reason="opened failure")
        # A rejected replacement must leave the original blind and inaccessible to dev.
        self.assertEqual(
            registry.access("blind-v1", AccessMode.BLIND_EVALUATION).status,
            PartitionStatus.BLIND,
        )

        replacement = PartitionRecord(
            "locked-v2",
            Partition.V1,
            PartitionStatus.LOCKED,
            frozenset({"family-fresh"}),
            replacement_for="locked-v1",
        )
        burn = registry.burn_and_replace(
            "locked-v1", replacement, reason="diagnose observed miss"
        )
        self.assertEqual(burn.replacement_record_id, "locked-v2")
        self.assertEqual(
            registry.access("locked-v1", AccessMode.DEVELOPMENT).status,
            PartitionStatus.BURNED,
        )
        with self.assertRaises(PartitionAccessError):
            registry.access("locked-v2", AccessMode.DEVELOPMENT)
        self.assertEqual(
            registry.access("locked-v2", AccessMode.VALIDATION_EVALUATION).status,
            PartitionStatus.LOCKED,
        )


if __name__ == "__main__":
    unittest.main()
