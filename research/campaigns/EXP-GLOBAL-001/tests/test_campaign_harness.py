from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


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
        screen60_extra = RUN.select_partition(
            ordered, "screen60-extra", self.screen_manifest
        )
        development_extra = RUN.select_partition(
            ordered, "development-extra", self.screen_manifest
        )
        self.assertEqual(len(screen24), 24)
        self.assertEqual(len(screen60), 60)
        self.assertEqual(len(screen60_extra), 36)
        self.assertEqual(len(development_extra), 85)
        ids24 = {row["problem_id"] for row in screen24}
        ids60 = {row["problem_id"] for row in screen60}
        ids60_extra = {row["problem_id"] for row in screen60_extra}
        ids_development_extra = {row["problem_id"] for row in development_extra}
        self.assertLessEqual(ids24, ids60)
        self.assertFalse(ids24 & ids60_extra)
        self.assertEqual(ids60, ids24 | ids60_extra)
        self.assertFalse(ids60 & ids_development_extra)
        self.assertEqual(
            {row["problem_id"] for row in ordered}, ids60 | ids_development_extra
        )

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

    def test_serial_child_metrics_cover_success_and_timeout(self) -> None:
        original_calls = []

        def guarded(*_args, **kwargs):
            phase = Path(kwargs["status_path"]).stem
            original_calls.append(phase)
            return types.SimpleNamespace(
                classification="SUCCESS" if phase == "dry" else "TIMEOUT",
                peak_process_group_rss_bytes=100 if phase == "dry" else 250,
            )

        runner = types.SimpleNamespace(run_guarded=guarded)
        usages = [
            types.SimpleNamespace(ru_utime=1.0, ru_stime=0.5),
            types.SimpleNamespace(ru_utime=1.4, ru_stime=0.7),
            types.SimpleNamespace(ru_utime=1.4, ru_stime=0.7),
            types.SimpleNamespace(ru_utime=2.1, ru_stime=0.9),
        ]
        with mock.patch.object(RUN.resource, "getrusage", side_effect=usages):
            with RUN.capture_runner_metrics(runner, 1) as metrics:
                runner.run_guarded(
                    status_path=Path("process-status/001-generated/dry.json")
                )
                runner.run_guarded(
                    status_path=Path("process-status/001-generated/execute.json")
                )

        self.assertEqual(original_calls, ["dry", "execute"])
        self.assertIs(runner.run_guarded, guarded)
        row = metrics["001-generated"]
        self.assertAlmostEqual(row["outer_cpu_seconds"], 1.5)
        self.assertEqual(
            row["outer_cpu_measurement_status"],
            "available_serial_rusage_children",
        )
        self.assertEqual(row["peak_rss_bytes"], 250)
        self.assertEqual(row["guarded_process_count"], 2)

    def test_outer_metrics_survive_missing_and_malformed_worker_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "RESULT.json").write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "index": 1,
                                "slug": "001-missing",
                                "accepted": False,
                                "outer_elapsed_seconds": 4.0,
                                "elapsed_wall_seconds": None,
                                "exact_target_count": 0,
                            },
                            {
                                "index": 2,
                                "slug": "002-malformed",
                                "accepted": False,
                                "outer_elapsed_seconds": 5.0,
                                "elapsed_wall_seconds": None,
                                "exact_target_count": 0,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (output / "INPUT_MANIFEST.json").write_text(
                json.dumps(
                    {
                        "rows": [
                            {"slug": "001-missing", "source_sha256": "a" * 64},
                            {"slug": "002-malformed", "source_sha256": "b" * 64},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            malformed = output / "artifacts/002-malformed"
            malformed.mkdir(parents=True)
            (malformed / "RESULT.json").write_text("{not-json", encoding="utf-8")
            RUN.write_truth_free_telemetry(
                output,
                {
                    "001-missing": {
                        "outer_cpu_seconds": 1.25,
                        "outer_cpu_measurement_status": (
                            "available_serial_rusage_children"
                        ),
                        "peak_rss_bytes": 1024,
                    },
                    "002-malformed": {
                        "outer_cpu_seconds": 2.5,
                        "outer_cpu_measurement_status": (
                            "available_serial_rusage_children"
                        ),
                        "peak_rss_bytes": 2048,
                    },
                },
                jobs=1,
            )
            telemetry = json.loads((output / "TELEMETRY.json").read_text())

        self.assertEqual(telemetry["schema_version"], "geotarget.exp-global-001-telemetry/v2")
        self.assertEqual(telemetry["outer_cpu_measurement"]["unit"], "seconds")
        self.assertEqual(telemetry["peak_rss_measurement"]["unit"], "bytes")
        self.assertEqual(telemetry["rows"][0]["outer_cpu_seconds"], 1.25)
        self.assertEqual(telemetry["rows"][0]["peak_rss_bytes"], 1024)
        self.assertEqual(telemetry["rows"][0]["worker"], {})
        self.assertEqual(telemetry["rows"][1]["outer_cpu_seconds"], 2.5)
        self.assertEqual(telemetry["rows"][1]["peak_rss_bytes"], 2048)
        self.assertEqual(telemetry["rows"][1]["worker"], {})

    def test_concurrent_jobs_report_cpu_unavailable_without_wrong_deltas(self) -> None:
        def guarded(*_args, **kwargs):
            slug = Path(kwargs["status_path"]).parent.name
            return types.SimpleNamespace(
                classification="SUCCESS",
                peak_process_group_rss_bytes=1000 + int(slug[:3]),
            )

        runner = types.SimpleNamespace(run_guarded=guarded)
        paths = [
            Path("process-status/001-left/execute.json"),
            Path("process-status/002-right/execute.json"),
        ]
        with mock.patch.object(
            RUN.resource,
            "getrusage",
            side_effect=AssertionError("must not read process-global rusage"),
        ):
            with RUN.capture_runner_metrics(runner, 2) as metrics:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    list(
                        executor.map(
                            lambda path: runner.run_guarded(status_path=path),
                            paths,
                        )
                    )

        self.assertEqual(set(metrics), {"001-left", "002-right"})
        for slug, row in metrics.items():
            self.assertIsNone(row["outer_cpu_seconds"])
            self.assertEqual(
                row["outer_cpu_measurement_status"],
                "unavailable_concurrent_jobs",
            )
            self.assertEqual(row["peak_rss_bytes"], 1000 + int(slug[:3]))

    def test_exact_mcnemar_and_clustered_bootstrap(self) -> None:
        result = COMPARE.exact_mcnemar(4, 0)
        self.assertEqual(result["candidate_one_sided_p"], 0.0625)
        self.assertEqual(result["two_sided_p"], 0.125)
        bootstrap = COMPARE.clustered_bootstrap(
            {"a": [1.0, 0.0], "b": [0.0]}, resamples=100, seed=7
        )
        self.assertGreaterEqual(bootstrap["lower_95"], 0.0)
        self.assertGreater(bootstrap["point_estimate"], 0.0)

    def test_rejected_case_uses_outer_censored_time(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "OFFLINE_SCORE.json").write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "index": 1,
                                "problem_id": "generated(A)",
                                "worker_elapsed_wall_seconds": None,
                                "status": "WORKER_NOT_ACCEPTED",
                                "exact_set_equal": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (root / "TELEMETRY.json").write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "ordinal": 1,
                                "outer_elapsed_seconds": 3.25,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            loaded = COMPARE.load_run(root)["generated(A)"]
            self.assertEqual(loaded["_comparison_elapsed_seconds"], 3.25)
            self.assertEqual(loaded["_comparison_time_source"], "outer_censored")


if __name__ == "__main__":
    unittest.main()
