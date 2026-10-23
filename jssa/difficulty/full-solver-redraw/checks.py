"""Small protocol checks; all temporary files stay under this output folder."""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "hook")]

import json
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

import numpy as np

from aggregate import aggregate, correct_and_cost, write_csv
from redraw_patch import redraw_point
from run import loadavg, portable_pin, research


class ProtocolChecks(unittest.TestCase):
    def test_original_feasible_and_uniform_stream(self):
        point = np.array([0.0, 0.0])
        low, high = np.array([-2., -3.]), np.array([2., 3.])
        result, retries, ok = redraw_point(point, low, high, 101, 7, lambda x: True)
        self.assertIs(result, point)
        self.assertEqual((retries, ok), (0, True))
        seen = []

        def feasible(x):
            seen.append(x.copy())
            return len(seen) == 4

        result, retries, ok = redraw_point(point, low, high, 101, 7, feasible)
        expected = np.random.default_rng([101, 99, 7]).uniform(low, high, size=(3, 2))
        np.testing.assert_array_equal(seen[1:], expected)
        np.testing.assert_array_equal(result, expected[-1])
        self.assertEqual((retries, ok), (3, True))

    def test_2001_including_original_and_last_point(self):
        seen = []
        low, high = np.array([-2.]), np.array([5.])
        result, retries, ok = redraw_point(np.array([0.]), low, high, 103, 11,
                                           lambda x: seen.append(x.copy()) or False)
        self.assertEqual((len(seen), retries, ok), (2001, 2000, False))
        np.testing.assert_array_equal(result, np.random.default_rng([103, 99, 11]).uniform(low, high, size=(2000, 1))[-1])
        self.assertTrue(all(np.all((x >= low) & (x <= high)) for x in seen))

    def test_timeout_propagates(self):
        def expired(x):
            raise TimeoutError("deadline")
        with self.assertRaises(TimeoutError):
            redraw_point([0], [0], [1], 101, 0, expired)

    def test_portable_missing_load_and_affinity(self):
        with patch.object(os, "getloadavg", side_effect=OSError, create=True):
            self.assertIsNone(loadavg())
        with patch.object(research, "_redraw_original_pin", side_effect=research.CampaignError("unsupported"), create=True):
            self.assertIsNone(portable_pin(None))

    def test_exact_set_equality_and_error_cost(self):
        from geosolver.exact import describe_exact
        answer = describe_exact("2").model_dump(mode="json")
        raw = {"solver_result": {"status": "solved", "answers": [answer], "elapsed_seconds": 2.5},
               "process": {"returncode": 0, "elapsed_seconds": 3.0}}
        self.assertEqual(correct_and_cost(raw, ["2"])[1:], (True, True, 2.5))
        self.assertEqual(correct_and_cost(raw, ["2, 3"])[1:], (False, False, 180.0))
        raw["process"]["timed_out"] = True
        self.assertEqual(correct_and_cost(raw, ["2"])[1:], (False, False, 180.0))
        del raw["process"]["timed_out"]
        raw["solver_result"]["elapsed_seconds"] = 180.01
        self.assertEqual(correct_and_cost(raw, ["2"])[1:], (True, False, 180.0))
        raw["solver_result"]["elapsed_seconds"] = 2.5
        raw["process"]["returncode"] = 91
        self.assertEqual(correct_and_cost(raw, ["2"])[1:], (True, False, 180.0))

    def test_builder_identity_and_optimizer_delivery(self):
        from geosolver.engine.standard.search import scipy_multistart_backend as smb
        from redraw_patch import install, point_hash
        from run import summarize_audit
        from types import SimpleNamespace
        kwargs = dict(lower=np.array([-2., -3.]), upper=np.array([2., 3.]),
                      n_starts_halton=3, burn_in=0, seed=701, extra_prefix_points=())
        original_builder = smb._build_local_start_sequence_with_kinds
        original_starts, original_kinds, prefix = original_builder(**kwargs)

        def search(self, **search_kwargs):
            starts, kinds, actual_prefix = smb._build_local_start_sequence_with_kinds(**kwargs)
            self.assertions.assertEqual(kinds, original_kinds)
            self.assertions.assertEqual(actual_prefix, prefix)
            for index, point in enumerate(starts):
                smb._collect_local_start_record(seed=701, start_index=index, start=point)
            return starts

        def collect(**collect_kwargs):
            return smb.least_squares(lambda x: x, collect_kwargs["start"])

        evaluator = SimpleNamespace(evaluate_float_hard_feasibility=lambda x, **kw:
                                    SimpleNamespace(hard_feasible=x[0] > 0))
        with tempfile.TemporaryDirectory(dir=HERE, prefix="check-hook-") as folder:
            for condition in ("normal", "redraw"):
                audit = Path(folder) / f"{condition}.jsonl"
                with ExitStack() as stack:
                    stack.enter_context(patch.dict(os.environ, REDRAW_CONDITION=condition,
                        REDRAW_SEED="101", REDRAW_AUDIT_PATH=str(audit)))
                    stack.enter_context(patch.object(smb, "_build_local_start_sequence_with_kinds", original_builder))
                    stack.enter_context(patch.object(smb.ScipyMultistartBackend, "run_search", search))
                    stack.enter_context(patch.object(smb, "_collect_local_start_record", collect))
                    stack.enter_context(patch.object(smb, "least_squares", lambda fun, x: x))
                    stack.enter_context(patch.object(smb, "minimize", lambda fun, x: x))
                    stack.callback(install())
                    self.assertEqual(smb._build_local_start_sequence_with_kinds is original_builder,
                                     condition == "normal")
                    starts = smb.ScipyMultistartBackend.run_search(
                        SimpleNamespace(assertions=self), evaluator=evaluator)
                    summary = summarize_audit(audit, condition)
                    self.assertTrue(summary["audit_verified"])
                    self.assertEqual(summary["starts_consumed"], len(original_starts))
                    if condition == "normal":
                        self.assertEqual(summary["starts_generated"], 0)
                        self.assertEqual([point_hash(p) for p in starts],
                                         [point_hash(p) for p in original_starts])
                    else:
                        self.assertGreater(summary["redraws_consumed"], 0)
                        self.assertEqual(summary["consumed_hard_fraction"], 1.)
                        self.assertEqual(summary["consumed_matching_generated"], len(starts))

    def test_single_runner_lock(self):
        from run import campaign_lock
        with tempfile.TemporaryDirectory(dir=HERE, prefix="check-lock-") as folder:
            with campaign_lock(Path(folder)):
                with self.assertRaises(RuntimeError):
                    with campaign_lock(Path(folder)):
                        self.fail("second runner entered")
            with campaign_lock(Path(folder)):
                pass

    def test_three_seed_paired_aggregation_including_errors(self):
        from run import prediction_rows
        ids = [r["id"] for r in prediction_rows()[:2]]
        with tempfile.TemporaryDirectory(dir=HERE, prefix="check-") as folder:
            folder = Path(folder)
            (folder / "manifest.json").write_text(json.dumps({"fixed": {
                "ids": ids, "seeds": [101, 102, 103], "mode": "smoke", "bootstrap_seed": 102304}}))
            rows = []
            for identifier in ids:
                for seed in [101, 102, 103]:
                    for condition in ["normal", "redraw"]:
                        cost = 180 if condition == "normal" else seed - 100
                        rows.append(dict(id=identifier, seed=seed, condition=condition,
                                         correct=int(condition == "redraw"), cost=cost,
                                         error=int(condition == "normal"), external_timeout=int(condition == "normal"),
                                         audit_verified=1, status="external_timeout" if condition == "normal" else "solved"))
            write_csv(folder / "per-run.csv", rows)
            aggregate(folder)
            import csv
            with (folder / "per-problem.csv").open() as stream:
                result = list(csv.DictReader(stream))
            self.assertEqual([float(r["delta_cost_redraw_minus_normal"]) for r in result], [-178., -178.])
            score = (folder / "score.md").read_text()
            self.assertIn("12/12", score)
            self.assertIn("判定しない", score)
            self.assertIn("| normal | 6 | 0 | 6 | 6 | 0 |", score)


if __name__ == "__main__":
    unittest.main()
