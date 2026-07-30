from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
SPEC = importlib.util.spec_from_file_location(
    "exp_global_001_run_arm", CAMPAIGN / "run_arm.py"
)
assert SPEC is not None and SPEC.loader is not None
RUN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUN
SPEC.loader.exec_module(RUN)

COMPARE_SPEC = importlib.util.spec_from_file_location(
    "exp_global_001_compare_runs", CAMPAIGN / "compare_runs.py"
)
assert COMPARE_SPEC is not None and COMPARE_SPEC.loader is not None
COMPARE = importlib.util.module_from_spec(COMPARE_SPEC)
sys.modules[COMPARE_SPEC.name] = COMPARE
COMPARE_SPEC.loader.exec_module(COMPARE)


class CampaignHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frozen = RUN.DEFAULT_FROZEN_ROOT
        self.arm_path = CAMPAIGN / "arms/frozen-champion/arm.json"
        self.input_manifest = self.frozen / (
            "research/experiments/EXP-V15-243-001/results/"
            "repro-20260722-champion-v2-poc-preloaded-development145-180s-jobs7-v1/"
            "INPUT_MANIFEST.json"
        )
        self.screen_manifest = self.frozen / (
            "research/experiments/EXP-V15-243-001/benchmark/SCREEN_MANIFEST.json"
        )

    def test_frozen_arm_is_hash_bound(self) -> None:
        arm, entrypoint = RUN.load_arm(self.arm_path, self.frozen)
        self.assertEqual(arm["mechanism_hash"], RUN.sha256_file(entrypoint))
        self.assertIn("champion_v2_poc_preloaded.py", str(entrypoint))

    def test_optimized_core_arm_is_hash_bound(self) -> None:
        path = CAMPAIGN / "arms/optimized-0967/arm.json"
        arm, entrypoint = RUN.load_arm(path, self.frozen)
        self.assertEqual(
            arm["base_commit"], "0967ff1cde5c2435fe0207da65e8779ff24a6da6"
        )
        self.assertEqual(arm["mechanism_hash"], RUN.sha256_file(entrypoint))

    def test_development_formulations_match_archive(self) -> None:
        rows = RUN.load_rows(RUN.DEFAULT_DATASET)
        ordered, expected = RUN.validate_development_rows(rows, self.input_manifest)
        self.assertEqual(len(ordered), 145)
        self.assertEqual(len(expected), 145)

    def test_formulation_mutation_fails_closed(self) -> None:
        rows = deepcopy(RUN.load_rows(RUN.DEFAULT_DATASET))
        rows[0]["formulation"]["id"] = "MUTATED"
        with self.assertRaisesRegex(ValueError, "canonical formulation mismatch"):
            RUN.validate_development_rows(rows, self.input_manifest)

    def test_screen_counts_and_nesting(self) -> None:
        rows = RUN.load_rows(RUN.DEFAULT_DATASET)
        ordered, _ = RUN.validate_development_rows(rows, self.input_manifest)
        screen24 = RUN.select_partition(ordered, "screen24", self.screen_manifest)
        screen60 = RUN.select_partition(ordered, "screen60", self.screen_manifest)
        self.assertEqual(len(screen24), 24)
        self.assertEqual(len(screen60), 60)
        ids24 = {row["problem_id"] for row in screen24}
        ids60 = {row["problem_id"] for row in screen60}
        self.assertLessEqual(ids24, ids60)

    def test_telemetry_drops_exact_values(self) -> None:
        extracted = RUN.scalar_telemetry(
            {
                "elapsed_wall_seconds": 1.25,
                "completed_start_count": 4,
                "selected_real_root_index": 2,
                "minimal_polynomial": [1, 0, -2],
                "nested": {"reservoir_candidates": [1, 2, 3]},
            }
        )
        self.assertEqual(extracted["elapsed_wall_seconds"], 1.25)
        self.assertEqual(extracted["completed_start_count"], 4)
        self.assertEqual(extracted["nested.reservoir_candidates.length"], 3)
        self.assertFalse(any("root" in key or "polynomial" in key for key in extracted))

    def test_exact_mcnemar_and_clustered_bootstrap(self) -> None:
        result = COMPARE.exact_mcnemar(4, 0)
        self.assertEqual(result["candidate_one_sided_p"], 0.0625)
        self.assertEqual(result["two_sided_p"], 0.125)
        bootstrap = COMPARE.clustered_bootstrap(
            {"a": [1.0, 0.0], "b": [0.0]}, resamples=100, seed=7
        )
        self.assertGreaterEqual(bootstrap["lower_95"], 0.0)
        self.assertGreater(bootstrap["point_estimate"], 0.0)


if __name__ == "__main__":
    unittest.main()
