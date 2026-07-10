from __future__ import annotations

import itertools
import json
from pathlib import Path
import tempfile
import unittest

from research.harness.matching import evaluate_run
from research.harness.miss_analyzer import (
    MissInputError,
    MissOutcome,
    analyze_miss,
    canonical_report_json,
    main,
    parse_diagnostic_bundle,
    parse_solver_trace,
)
from research.harness.models import parse_case_input, parse_run_input
from research.validate import validate_instance


ROOT = Path(__file__).resolve().parents[2]


def interval(value: str) -> dict:
    return {"lower": value, "upper": value, "certified": True}


def case_data(
    *, case_id: str = "case-neutral", target_id: str = "target-neutral"
) -> dict:
    return {
        "case_id": case_id,
        "family_id": "family-neutral",
        "strata": ["S1"],
        "domain_kind": "bounded",
        "exact_eligible": True,
        "matching": {"mode": "certified_interval"},
        "gold_targets": [{"target_id": target_id, "interval": interval("1")}],
    }


def answer_data(
    *,
    answer_id: str = "answer-neutral",
    value: str = "1",
    level: str = "validated",
    configuration_validated: bool = True,
    target_identity_certified: bool = False,
    guard_valid: bool = True,
    boundary_valid: bool = True,
    branch: str | None = None,
) -> dict:
    return {
        "answer_id": answer_id,
        "level": level,
        "interval": interval(value),
        "branch": branch,
        "configuration_validated": configuration_validated,
        "target_identity_certified": target_identity_certified,
        "guard_valid": guard_valid,
        "boundary_valid": boundary_valid,
        "configuration_id": "configuration-neutral",
    }


def run_data(answers: list[dict], *, case_id: str = "case-neutral") -> dict:
    return {
        "run_id": "run-neutral",
        "case_id": case_id,
        "seed": 7,
        "budget_seconds": 180,
        "answers": answers,
        "claims_complete": False,
        "coverage_certificate": False,
    }


def fact(
    kind: str,
    *,
    source: str,
    subject_kind: str = "run",
    subject_id: str | None = None,
    evidence_ref: str | None = None,
    causal: bool = True,
) -> dict:
    return {
        "kind": kind,
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "source": source,
        "evidence_ref": evidence_ref or f"synthetic/{kind}",
        "causal": causal,
    }


def bundle(*facts: dict):
    return parse_diagnostic_bundle(
        {"schema_version": "geotarget.miss-diagnostics/v1", "facts": list(facts)}
    )


def diagnose(
    case: dict, run: dict, *, diagnostics=None, evidence=None, checkpoint=None
):
    parsed_case = parse_case_input(case)
    parsed_run = parse_run_input(run)
    evaluation = evaluate_run(parsed_case, parsed_run)
    return analyze_miss(
        parsed_case,
        parsed_run,
        evaluation,
        diagnostics=diagnostics,
        evidence_log=evidence,
        checkpoint=checkpoint,
    )


def evidence_observation(
    diagnostic: str, *, target: float | None = 1.0, refine=False
) -> dict:
    target_document = (
        None
        if target is None
        else {"type": "TargetEnclosure{Float64}", "lower": target, "upper": target}
    )
    return {
        "schema": "geotarget.evidence-log/v1",
        "resume_identity": {},
        "events": [
            {
                "sequence": 1,
                "kind": "EVENT_OBSERVED",
                "payload": {
                    "type": "Observation",
                    "task_id": 1,
                    "configuration_id": 1,
                    "canonical_near_feasible": target is not None,
                    "canonical_valid": False,
                    "target": target_document,
                    "target_identity": None,
                    "branch_signature": [],
                    "verified": False,
                    "verified_payload": None,
                    "needs_refinement": refine,
                    "residual_score": 0.0,
                    "oracle_work": 4,
                    "endpoint": [target or 0.0],
                    "diagnostic": diagnostic,
                },
            }
        ],
    }


def checkpoint_observation(diagnostic: str) -> dict:
    observed = evidence_observation(diagnostic)["events"][0]["payload"]
    observed.pop("type")
    observed["target"] = {
        "lower": {
            "kind": "binary_float",
            "type": "Float64",
            "bits": "3ff0000000000000",
        },
        "upper": {
            "kind": "binary_float",
            "type": "Float64",
            "bits": "3ff0000000000000",
        },
    }
    observed["residual_score"] = {
        "kind": "binary_float",
        "type": "Float64",
        "bits": "0000000000000000",
    }
    observed["endpoint"] = []
    return {
        "schema_version": "geotarget.checkpoint/v1",
        "content_hash": "sha256:" + "0" * 64,
        "target_image_status": "unknown",
        "state": {
            "resume_identity": {},
            "policy_version": "1.0.0",
            "budget": {},
            "workspace": {},
            "events": [{"sequence": 1, "kind": "observed", "payload": observed}],
            "rng_state": {},
            "precision_bits": 256,
            "remaining_seconds": {},
            "cancelled": False,
        },
    }


class CounterexampleTests(unittest.TestCase):
    def test_missing_trace_is_unknown_not_no_capture(self) -> None:
        report = diagnose(case_data(), run_data([]))
        self.assertEqual(report.outcome, MissOutcome.UNKNOWN)
        self.assertIsNone(report.failure_id)
        self.assertIn("missing_solver_trace", report.unclassified_reason_codes)

    def test_unassociated_domain_event_does_not_blame_domain(self) -> None:
        trace = parse_solver_trace(
            evidence_observation(
                "local_status=LOCAL_CONVERGED;validation=CANDIDATE_DOMAIN_FAILED",
                target=None,
            ),
            origin="evidence",
        )
        report = diagnose(case_data(), run_data([]), evidence=trace)
        self.assertEqual(report.outcome, MissOutcome.UNKNOWN)
        self.assertIn(
            "unassociated_trace_diagnostics_ignored", report.unclassified_reason_codes
        )

    def test_false_output_distinguishes_configuration_from_output(self) -> None:
        configuration = diagnose(
            case_data(),
            run_data([answer_data(configuration_validated=False)]),
        )
        wrong_value = diagnose(case_data(), run_data([answer_data(value="2")]))
        self.assertEqual(configuration.failure_id, "F13")
        self.assertEqual(wrong_value.failure_id, "F15")

    def test_truth_audit_precedes_false_output(self) -> None:
        report = diagnose(
            case_data(),
            run_data([answer_data(value="2")]),
            diagnostics=bundle(
                fact("gold_truth_invalid", source="independent_truth_audit")
            ),
        )
        self.assertEqual((report.failure_id, report.checkpoint), ("F0", "truth"))


class FailureCoverageTests(unittest.TestCase):
    def test_capture_local_and_stationary_are_distinct(self) -> None:
        missing = run_data([])
        no_capture = diagnose(
            case_data(),
            missing,
            diagnostics=bundle(
                fact(
                    "capture_region_not_entered",
                    source="instrumented_capture",
                    subject_kind="target",
                    subject_id="target-neutral",
                )
            ),
        )
        local = diagnose(
            case_data(),
            missing,
            diagnostics=bundle(
                fact(
                    "capture_region_entered",
                    source="instrumented_capture",
                    subject_kind="target",
                    subject_id="target-neutral",
                ),
                fact(
                    "local_solver_failed",
                    source="instrumented_capture",
                    subject_kind="target",
                    subject_id="target-neutral",
                ),
            ),
        )
        stationary = diagnose(
            case_data(),
            missing,
            diagnostics=bundle(
                fact(
                    "nonzero_stationary_point",
                    source="counterfactual_replay",
                    subject_kind="target",
                    subject_id="target-neutral",
                )
            ),
        )
        self.assertEqual(
            (no_capture.failure_id, local.failure_id, stationary.failure_id),
            ("F4", "F5", "F6"),
        )

    def test_trace_maps_domain_guard_branch_singular_and_refinement(self) -> None:
        cases = {
            "CANDIDATE_DOMAIN_FAILED": "F2",
            "CANDIDATE_STRICT_GUARD_UNSEPARATED": "F8",
            "CANDIDATE_BRANCH_KEY_MISMATCH": "F7",
            "CANDIDATE_RELATION_TRUTH_FAILED": "F13",
        }
        for validation, expected in cases.items():
            with self.subTest(validation=validation):
                trace = parse_solver_trace(
                    evidence_observation(
                        f"local_status=LOCAL_CONVERGED;validation={validation}"
                    ),
                    origin="evidence",
                )
                self.assertEqual(
                    diagnose(case_data(), run_data([]), evidence=trace).failure_id,
                    expected,
                )

        singular = parse_solver_trace(
            evidence_observation(
                "local_status=LOCAL_CONVERGED;validation=not_run;"
                "target_image_failure=TARGET_IMAGE_SINGULAR_LINEARIZATION"
            ),
            origin="evidence",
        )
        refinement = parse_solver_trace(
            checkpoint_observation(
                "local_status=LOCAL_CONVERGED;validation=not_run;"
                "target_image_failure=TARGET_IMAGE_ORACLE_BUDGET_EXHAUSTED"
            ),
            origin="checkpoint",
        )
        self.assertEqual(
            diagnose(case_data(), run_data([]), evidence=singular).failure_id, "F9"
        )
        self.assertEqual(
            diagnose(case_data(), run_data([]), checkpoint=refinement).failure_id, "F12"
        )

    def test_archive_scheduler_output_and_overhead(self) -> None:
        for kind, source, expected in (
            ("archive_witness_lost", "archive_audit", "F10"),
            ("scheduler_starvation_or_duplicate_work", "scheduler_audit", "F11"),
            ("output_mismatch_or_false_complete", "output_audit", "F15"),
            ("same_budget_overhead_gate_failed", "performance_comparison", "F18"),
        ):
            with self.subTest(kind=kind):
                report = diagnose(
                    case_data(),
                    run_data([]),
                    diagnostics=bundle(fact(kind, source=source)),
                )
                self.assertEqual(report.failure_id, expected)

    def test_guard_branch_and_exact_shortfall_from_typed_evaluation(self) -> None:
        guarded = diagnose(
            case_data(),
            run_data([answer_data(guard_valid=False, boundary_valid=False)]),
        )
        branch_case = case_data()
        branch_case["gold_targets"][0]["allowed_branches"] = ["left"]
        branched = diagnose(branch_case, run_data([answer_data(branch="right")]))
        exact_shortfall = diagnose(case_data(), run_data([answer_data()]))
        self.assertEqual(
            (guarded.failure_id, branched.failure_id, exact_shortfall.failure_id),
            ("F8", "F7", "F14"),
        )


class StrictnessAndMetamorphicTests(unittest.TestCase):
    def test_instrumented_local_failure_requires_capture_evidence(self) -> None:
        with self.assertRaisesRegex(MissInputError, "capture_region_entered"):
            bundle(
                fact(
                    "local_solver_failed",
                    source="instrumented_capture",
                    subject_kind="target",
                    subject_id="target-neutral",
                )
            )

    def test_fact_permutation_does_not_change_report(self) -> None:
        facts = [
            fact("output_mismatch_or_false_complete", source="output_audit"),
            fact(
                "capture_region_not_entered",
                source="instrumented_capture",
                subject_kind="target",
                subject_id="target-neutral",
            ),
            fact("same_budget_overhead_gate_failed", source="performance_comparison"),
        ]
        reports = {
            canonical_report_json(
                diagnose(case_data(), run_data([]), diagnostics=bundle(*permutation))
            )
            for permutation in itertools.permutations(facts)
        }
        self.assertEqual(len(reports), 1)

    def test_identifier_renaming_cannot_route_the_classifier(self) -> None:
        first = diagnose(
            case_data(case_id="a", target_id="target-a"),
            run_data([], case_id="a"),
            diagnostics=bundle(
                fact(
                    "capture_region_not_entered",
                    source="instrumented_capture",
                    subject_kind="target",
                    subject_id="target-a",
                )
            ),
        )
        second = diagnose(
            case_data(case_id="contains-F15-magic", target_id="renamed"),
            run_data([], case_id="contains-F15-magic"),
            diagnostics=bundle(
                fact(
                    "capture_region_not_entered",
                    source="instrumented_capture",
                    subject_kind="target",
                    subject_id="renamed",
                )
            ),
        )
        self.assertEqual(
            (first.failure_id, first.checkpoint), (second.failure_id, second.checkpoint)
        )

    def test_noncausal_fact_does_not_turn_missing_logs_into_a_classification(
        self,
    ) -> None:
        report = diagnose(
            case_data(),
            run_data([]),
            diagnostics=bundle(
                fact(
                    "capture_region_not_entered",
                    source="instrumented_capture",
                    causal=False,
                )
            ),
        )
        self.assertEqual(report.outcome, MissOutcome.UNKNOWN)
        self.assertIn("noncausal_diagnostics_ignored", report.unclassified_reason_codes)


class SchemaAndCliTests(unittest.TestCase):
    def test_report_satisfies_strict_schema(self) -> None:
        report = diagnose(case_data(), run_data([answer_data(value="2")]))
        schema = json.loads(
            (ROOT / "research" / "schemas" / "miss-report.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(validate_instance(report.to_document(), schema), [])

    def test_cli_writes_canonical_deterministic_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            case_path = directory / "case.json"
            run_path = directory / "run.json"
            diagnostic_path = directory / "diagnostics.json"
            output_path = directory / "report.json"
            case_path.write_text(json.dumps(case_data()), encoding="utf-8")
            run_path.write_text(json.dumps(run_data([])), encoding="utf-8")
            diagnostic_path.write_text(
                json.dumps(
                    {
                        "schema_version": "geotarget.miss-diagnostics/v1",
                        "facts": [
                            fact(
                                "capture_region_not_entered",
                                source="instrumented_capture",
                                subject_kind="target",
                                subject_id="target-neutral",
                            )
                        ],
                    }
                ),
                encoding="utf-8",
            )
            exit_code = main(
                [
                    "--case",
                    str(case_path),
                    "--run",
                    str(run_path),
                    "--diagnostics",
                    str(diagnostic_path),
                    "--output",
                    str(output_path),
                ]
            )
            self.assertEqual(exit_code, 0)
            rendered = output_path.read_text(encoding="utf-8")
            self.assertTrue(rendered.endswith("\n"))
            document = json.loads(rendered)
            self.assertEqual(document["failure_id"], "F4")
            self.assertEqual(
                rendered.strip(),
                json.dumps(
                    document, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                ),
            )


if __name__ == "__main__":
    unittest.main()
