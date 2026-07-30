from __future__ import annotations

import os
from pathlib import Path
import unittest


os.environ.setdefault(
    "GEOTARGET_AMS_EXPERIMENTS_ROOT",
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments",
)

import candidate
from generated_cases import PANEL
from run_generated import run_arm_pair, summarize


class CheckpointGenealogicalAMSTest(unittest.TestCase):
    def test_budget_floor_and_ceiling(self) -> None:
        for total in (4, 7, 16, 191, 384):
            baseline, side = candidate.split_budget(total)
            self.assertEqual(total, baseline + side)
            self.assertGreaterEqual(baseline / total, 0.75)
            self.assertLessEqual(side / total, 0.25)

    def test_semantic_validity_is_primary_score_key(self) -> None:
        invalid_but_tiny = candidate.PassageScore(0, 299.0)
        valid_but_rough = candidate.PassageScore(1, -12.0)
        self.assertGreater(valid_but_rough, invalid_but_tiny)

    def test_generated_d0_equal_work_safety_gain_and_metamorphic(self) -> None:
        runs = []
        for spec in PANEL:
            runs.append(run_arm_pair(spec, 0, total_callbacks=384))
            if spec.category == "positive":
                runs.append(
                    run_arm_pair(
                        spec,
                        0,
                        total_callbacks=384,
                        coordinate_signed_permutation=True,
                        residual_swap_sign=True,
                    )
                )
        summary = summarize(runs)
        self.assertTrue(summary["d0_pass"], summary)
        self.assertEqual(summary["total_safe_root_losses"], 0)
        self.assertEqual(summary["false_safe_roots"], 0)
        self.assertGreater(summary["genealogy_events"], 0)

    def test_genealogy_records_first_passage_rng_and_tangent_mutation(self) -> None:
        positive = next(item for item in PANEL if item.category == "positive")
        result = run_arm_pair(positive, 1, total_callbacks=384)
        self.assertTrue(result["genealogy"])
        digests = set()
        for event in result["genealogy"]:
            self.assertGreater(event["parent_passage_callback"], 0)
            self.assertGreater(event["perturbation_norm_z"], 0.0)
            self.assertNotEqual(
                event["killed_trajectory_id"], event["parent_trajectory_id"]
            )
            self.assertEqual(len(event["rng_key_sha256"]), 64)
            digests.add(event["rng_key_sha256"])
        self.assertEqual(len(digests), len(result["genealogy"]))

    def test_opaque_evaluator_fails_closed_at_exact_budget(self) -> None:
        opaque = next(item for item in PANEL if item.name == "opaque-evaluator")
        result = run_arm_pair(opaque, 0, total_callbacks=96)
        self.assertEqual(result["callbacks"], {"control": 96, "candidate": 96, "candidate_ams": 24})
        self.assertEqual(result["candidate_safe_roots"], [])
        self.assertEqual(result["genealogy_events"], 0)

    def test_no_common_framework_or_truth_routing_declared(self) -> None:
        manifest = candidate.configuration_manifest()
        self.assertFalse(manifest["checkpoint_serialization"])
        self.assertFalse(manifest["common_checkpoint_or_scheduler_framework"])
        self.assertFalse(manifest["problem_family_truth_target_count_routing"])
        text = Path(candidate.__file__).read_text()
        for forbidden in ("expected_root", "truth_manifest", "problem_id"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
