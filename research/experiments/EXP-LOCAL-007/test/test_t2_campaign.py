"""Focused tests for the lightweight T2 campaign aggregator."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "run_t2_campaign.py"
SPEC = importlib.util.spec_from_file_location("exp_local_007_t2_campaign", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load T2 campaign module")
CAMPAIGN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)


def gate_fixture(*, ratio=0.79, critical_delta=0.0, audit="pass"):
    control_safe = {family: 0.5 for family in CAMPAIGN.APPLICABLE_FAMILIES}
    candidate_safe = dict(control_safe)
    family_safe = {
        CAMPAIGN.CONTROL: control_safe,
        CAMPAIGN.CANDIDATE: candidate_safe,
    }
    family_work = {
        CAMPAIGN.CONTROL: {
            family: 100 for family in CAMPAIGN.APPLICABLE_FAMILIES
        },
        CAMPAIGN.CANDIDATE: {
            family: int(100 * ratio) for family in CAMPAIGN.APPLICABLE_FAMILIES
        },
    }
    critical_safe = {
        CAMPAIGN.CONTROL: {name: 0.5 for name in CAMPAIGN.CRITICAL},
        CAMPAIGN.CANDIDATE: {name: 0.5 for name in CAMPAIGN.CRITICAL},
    }
    critical_safe[CAMPAIGN.CANDIDATE][next(iter(CAMPAIGN.CRITICAL))] += critical_delta
    return CAMPAIGN.evaluate_gate(
        family_safe,
        family_work,
        critical_safe,
        0,
        0,
        audit,
    )


class CampaignTests(unittest.TestCase):
    def test_path_b_passes_only_after_source_audit(self):
        passed = gate_fixture()
        self.assertTrue(passed["performance_path_b"])
        self.assertEqual(len(passed["path_b_supporting_families"]), 7)
        self.assertTrue(passed["passed"])
        pending = gate_fixture(audit="pending")
        self.assertFalse(pending["truth_leak_gate"])
        self.assertFalse(pending["passed"])

    def test_critical_regression_kills_candidate(self):
        result = gate_fixture(critical_delta=-0.03)
        self.assertFalse(result["critical_gate"])
        self.assertFalse(result["passed"])

    def test_attempt_safety_and_nonsquare_checks(self):
        attempt = {
            "reported_accepted": True,
            "canonical_valid": False,
            "gold_matched": False,
            "numeric_target_matched": True,
            "configuration_matched": False,
            "target_ambiguous": True,
            "assessor_qualified": True,
            "assessor_gold_matched": False,
            "assessor_target_ambiguous": False,
            "evaluation_count_mismatch": True,
            "evaluations": 601,
            "variant": CAMPAIGN.CANDIDATE,
            "budget_exhausted": False,
            "exception": "fixture",
        }
        violations = CAMPAIGN._attempt_violations(attempt)
        self.assertIn("reported-accepted-canonical-invalid", violations)
        self.assertIn("evaluation-count-mismatch", violations)
        self.assertIn("runner-cap-violation", violations)
        self.assertIn("unhandled-exception", violations)

        nonsquare = {
            "status": "INAPPLICABLE_NONSQUARE",
            "evaluations": 0,
            "reported_evaluations": 0,
            "endpoint": None,
            "reported_accepted": False,
            "reported_converged": False,
            "budget_exhausted": False,
            "exception": None,
        }
        self.assertEqual(CAMPAIGN._nonsquare_violations(nonsquare), [])

    def test_driver_contract_is_48_shards_and_16_physical_cores(self):
        self.assertEqual(CAMPAIGN.SHARD_COUNT, 48)
        self.assertEqual(CAMPAIGN.MAX_JOBS, 16)
        command = CAMPAIGN.shard_command("julia", Path("out.json"), 47, 15)
        self.assertIn("--shard-index=47", command)
        self.assertIn("--shard-count=48", command)
        if command[0].endswith("taskset"):
            self.assertEqual(command[1:3], ["-c", "15"])

    def test_family_work_uses_suffix_stable_right_censor_not_total_evaluations(self):
        summaries = [
            {
                "variant": CAMPAIGN.CONTROL,
                "family_id": "SCALE-LADDER",
                "evaluations": 19_999,
                "right_censored_assessor_safe_full_work": 37,
            },
            {
                "variant": CAMPAIGN.CONTROL,
                "family_id": "SCALE-LADDER",
                "evaluations": 18_888,
                "right_censored_assessor_safe_full_work": 4800,
            },
        ]
        self.assertEqual(
            CAMPAIGN._family_callback_work(
                summaries, CAMPAIGN.CONTROL, "SCALE-LADDER"
            ),
            4837,
        )
        self.assertNotEqual(
            CAMPAIGN._family_callback_work(
                summaries, CAMPAIGN.CONTROL, "SCALE-LADDER"
            ),
            sum(summary["evaluations"] for summary in summaries),
        )

    def test_raw_suffix_work_uses_common_assessor_and_later_safety(self):
        sequence = []
        for start_index in range(1, 33):
            sequence.append(
                {
                    "start_index": start_index,
                    "evaluations": 10 if start_index == 1 else 1,
                    "assessor_qualified": start_index == 1,
                    "assessor_gold_matched": start_index == 1,
                    "assessor_target_ambiguous": False,
                    "assessor_matched_target_id": "target-1"
                    if start_index == 1
                    else None,
                }
            )
        self.assertEqual(CAMPAIGN._suffix_stable_assessor_work(sequence, 1), 10)
        snapshot = CAMPAIGN._assessor_snapshot(sequence, 1, 8)
        self.assertTrue(snapshot["assessor_safe_all_targets"])
        self.assertEqual(snapshot["assessor_qualified_targets_found"], 1)
        self.assertEqual(snapshot["evaluations"], 17)

        sequence[8].update(
            assessor_qualified=True,
            assessor_gold_matched=True,
            assessor_target_ambiguous=True,
            assessor_matched_target_id="target-1",
        )
        self.assertIsNone(CAMPAIGN._suffix_stable_assessor_work(sequence, 1))

    def test_raw_case_reaggregation_uses_solver_manifest_targets_key(self):
        attempts = []
        for variant in CAMPAIGN.VARIANTS:
            for start_index in range(1, 33):
                attempts.append(
                    {
                        "variant": variant,
                        "start_index": start_index,
                        "evaluations": 1,
                        "assessor_qualified": start_index == 1,
                        "assessor_gold_matched": start_index == 1,
                        "assessor_target_ambiguous": False,
                        "assessor_matched_target_id": "target-1"
                        if start_index == 1
                        else None,
                    }
                )
        document = {
            "problem_manifest": [
                {
                    "instance_id": "fixture",
                    "family_id": "SCALE-LADDER",
                    "targets": 1,
                }
            ],
            "attempts": attempts,
        }
        records = CAMPAIGN._raw_case_summaries(document)
        self.assertEqual(len(records), 9)
        self.assertTrue(all(record["target_count"] == 1 for record in records))


if __name__ == "__main__":
    unittest.main()
