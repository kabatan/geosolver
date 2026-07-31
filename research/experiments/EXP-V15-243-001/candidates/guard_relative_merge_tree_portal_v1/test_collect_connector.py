from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

import candidate
import collect_connector


@dataclass(frozen=True)
class FakeObservation:
    residual: np.ndarray
    finite: bool
    semantics_valid: bool
    violation_vector: np.ndarray


@dataclass(frozen=True)
class FakeCase:
    dimension: int
    residual_dimension: int
    scales: np.ndarray
    evaluate: object
    progressive_residual: object


class FakeBudget:
    def __init__(self) -> None:
        self.callbacks = 0


class FakeEvaluator:
    compiled_guards = (object(), object())


def source_hash(label: str = "generated-collect-only") -> str:
    return hashlib.sha256(label.encode()).hexdigest()


class CollectOnlyTests(unittest.TestCase):
    def setUp(self):
        self.positions = [-3.1, -2.0, -1.15, -0.2, 0.9, 2.05, 3.3, 4.7, 6.2, 7.8, 9.5]
        self.residuals = [0.01, 0.12, 0.25, 0.40, 0.58, 0.79, 1.03, 1.30, 1.60, 1.93, 2.29]
        self.budget = FakeBudget()
        self.returned = []

        def evaluate(point):
            self.budget.callbacks += 1
            index = self.positions.index(float(np.asarray(point)[0]))
            invalid = index < 3
            observation = FakeObservation(
                residual=np.asarray([self.residuals[index]], dtype=float),
                finite=True,
                semantics_valid=not invalid,
                violation_vector=np.asarray([1.0 if invalid else 0.0, 0.0, 0.0]),
            )
            self.returned.append(observation)
            return observation

        self.original_progressive = lambda point: np.asarray(point, dtype=float)
        self.case = FakeCase(
            dimension=1,
            residual_dimension=1,
            scales=np.ones(1),
            evaluate=evaluate,
            progressive_residual=self.original_progressive,
        )

        def build_source_case(document, *, callback_cap, deadline):
            del document, callback_cap, deadline
            return self.case, self.budget, FakeEvaluator()

        self.collector = collect_connector.Collector(source_hash(), candidate)
        wrapped_build = self.collector.wrap_build_source_case(build_source_case)
        self.wrapped_case, returned_budget, _evaluator = wrapped_build(
            {}, callback_cap=1200, deadline=1.0
        )
        self.assertIs(returned_budget, self.budget)

    def test_callback_result_and_progressive_path_are_unchanged(self):
        for position in self.positions:
            returned = self.wrapped_case.evaluate(np.asarray([position]))
            self.assertIs(returned, self.returned[-1])
        self.assertIs(self.wrapped_case.progressive_residual, self.original_progressive)
        self.assertEqual(self.budget.callbacks, len(self.positions))
        self.assertEqual(self.collector.charged_evaluate_calls, len(self.positions))
        self.assertFalse(self.collector.accounting_mismatch)

    def test_process_gate_aggregate_has_no_individual_rows(self):
        for position in self.positions:
            self.wrapped_case.evaluate(np.asarray([position]))
        result = {
            "completed": True,
            "endpoints": [
                {"lane": index, "point": [position]}
                for index, position in enumerate(self.positions[:3])
            ],
        }
        aggregate = self.collector.aggregate(result)
        gate = aggregate["dynamic_gate"]
        self.assertEqual(gate["decision"], "HOLD_DYNAMIC_RECURRENCE")
        self.assertEqual(gate["low_residual_invalid_endpoint_count"], 1)
        self.assertEqual(gate["anonymous_hash_count_with_low_invalid_endpoint"], 1)
        self.assertFalse(aggregate["portal_proposal_enabled"])
        self.assertFalse(aggregate["side_callback_quota_enabled"])
        serialized = json.dumps(aggregate, sort_keys=True)
        for forbidden in ('"point"', '"residual"', '"observations"'):
            self.assertNotIn(forbidden, serialized)

    def test_sidecar_does_not_change_baseline_result(self):
        for position in self.positions:
            self.wrapped_case.evaluate(np.asarray([position]))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "search.json"
            output.write_text(
                json.dumps(
                    {
                        "completed": True,
                        "endpoints": [{"lane": 0, "point": [self.positions[0]]}],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            before = output.read_bytes()

            def atomic_write_json(path, payload):
                path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

            sidecar = collect_connector.write_aggregate_sidecar(
                collector=self.collector,
                output=output,
                atomic_write_json=atomic_write_json,
            )
            self.assertEqual(output.read_bytes(), before)
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(payload["baseline_result_sha256"], hashlib.sha256(before).hexdigest())
            self.assertFalse(payload["individual_observations_emitted"])

    def test_duplicate_hard_only_and_cap_fail_conservatively(self):
        first = self.wrapped_case.evaluate(np.asarray([self.positions[0]]))
        self.assertIs(first, self.returned[-1])
        self.wrapped_case.evaluate(np.asarray([self.positions[0]]))
        self.assertEqual(self.collector.duplicate_points_skipped, 1)

        hard_only = FakeObservation(
            residual=np.asarray([0.2]),
            finite=True,
            semantics_valid=False,
            violation_vector=np.zeros(3),
        )
        self.collector._observe(np.asarray([100.0]), hard_only)
        self.assertEqual(self.collector.hard_only_invalid_skipped, 1)

        self.collector._rows = [dict(self.collector._rows[0])] * collect_connector.OBSERVATION_CAP
        self.collector._observe(np.asarray([101.0]), hard_only)
        self.assertEqual(self.collector.cap_dropped, 1)

    def test_nonfinite_callback_is_skipped_without_poisoning_typed_finite_pool(self):
        failed = FakeObservation(
            residual=np.asarray([float("inf")]),
            finite=False,
            semantics_valid=False,
            # The authority returns a one-entry fallback vector when the
            # evaluator itself fails; it is not an included finite row.
            violation_vector=np.ones(1),
        )
        self.collector._observe(np.asarray([0.125]), failed)
        self.assertEqual(self.collector.nonfinite_or_untyped_skipped, 1)
        self.assertTrue(self.collector.typed_guard_complete)

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
