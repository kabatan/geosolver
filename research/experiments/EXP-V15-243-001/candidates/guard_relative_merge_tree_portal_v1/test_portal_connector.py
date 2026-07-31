from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import os
from types import SimpleNamespace
import unittest

import numpy as np

import candidate
import collect_connector
import portal_connector


@dataclass(frozen=True)
class Observation:
    residual: np.ndarray
    finite: bool
    semantics_valid: bool
    violation_vector: np.ndarray


@dataclass(frozen=True)
class Case:
    dimension: int
    residual_dimension: int
    scales: np.ndarray
    evaluate: object
    progressive_residual: object


@dataclass(frozen=True)
class Outcome:
    endpoints: tuple
    statuses: dict
    counters: dict
    lane_callbacks: tuple


class Budget:
    callbacks = 0


class Evaluator:
    compiled_guards = (object(),)


GLOBAL_GATE = {
    "decision": "ROOT_COLLECT_SCREEN24_SEED0_DYNAMIC_GATE_PASS",
    "global_dynamic_gate_pass": True,
    "complete_typed_pools": 11,
    "interior_ge_8_pools": 11,
    "low_residual_invalid_endpoints": 7,
    "distinct_anonymous_sources": 4,
}


def build_runtime(*, activate: bool):
    budget = Budget()
    budget.callbacks = 0
    calls = []
    positions = [-3.1, -2.0, -1.15, -0.2, 0.9, 2.05, 3.3, 4.7, 6.2, 7.8, 9.5, 11.4]
    residuals = [0.01, 0.12, 0.25, 0.40, 0.58, 0.79, 1.03, 1.30, 1.60, 1.93, 2.29, 2.68]
    pilot_extras = {
        positions[0]: positions[3:5],
        positions[1]: positions[5:7],
        positions[2]: positions[7:9],
    }

    def evaluate(point):
        value = float(np.asarray(point)[0])
        calls.append(value)
        budget.callbacks += 1
        nearest = min(range(len(positions)), key=lambda i: abs(positions[i] - value))
        invalid = bool(activate and nearest == 0 and value == positions[0])
        return Observation(
            residual=np.asarray([residuals[nearest]], dtype=float),
            finite=True,
            semantics_valid=not invalid,
            violation_vector=np.asarray([1.0 if invalid else 0.0, 0.0]),
        )

    case = Case(1, 1, np.ones(1), evaluate, lambda point: np.asarray(point))

    def build_source_case(document, *, callback_cap, deadline):
        del document, callback_cap, deadline
        return case, budget, Evaluator()

    collector = collect_connector.Collector(
        hashlib.sha256(b"generated-portal-runtime").hexdigest(), candidate
    )
    wrapped_case, _budget, _evaluator = collector.wrap_build_source_case(
        build_source_case
    )({}, callback_cap=12, deadline=1.0)
    runtime = portal_connector.PortalRuntime(
        collector=collector,
        candidate=candidate,
        point_key=collect_connector._point_key,
        global_gate=GLOBAL_GATE,
    )

    def original(
        arm,
        *,
        base_case,
        budget,
        program,
        literal_prefix,
        callback_cap,
        callbacks_per_start,
        deadline_monotonic,
    ):
        del arm, program, callbacks_per_start, deadline_monotonic
        endpoints = []
        lane_callbacks = []
        for lane, point in enumerate(literal_prefix.points):
            if budget.callbacks >= callback_cap:
                break
            before = budget.callbacks
            base_case.evaluate(point)
            value = float(np.asarray(point)[0])
            if activate and len(literal_prefix.points) == 3 and value in pilot_extras:
                for extra in pilot_extras[value]:
                    if budget.callbacks < callback_cap:
                        base_case.evaluate(np.asarray([extra], dtype=float))
            endpoints.append((lane, np.asarray(point, dtype=float).copy()))
            lane_callbacks.append(budget.callbacks - before)
        return Outcome(tuple(endpoints), {"ok": len(endpoints)}, {}, tuple(lane_callbacks))

    prefix = SimpleNamespace(
        points=tuple(np.asarray([value], dtype=float) for value in positions)
    )
    return runtime, runtime.wrap_run_local_arm(original), wrapped_case, budget, prefix, calls


class PortalRuntimeTests(unittest.TestCase):
    def test_active_pool_uses_existing_interior_portal_and_charged_midpoint(self):
        runtime, run, case, budget, prefix, calls = build_runtime(activate=True)
        outcome = run(
            "arm",
            base_case=case,
            budget=budget,
            program=None,
            literal_prefix=prefix,
            callback_cap=12,
            callbacks_per_start=1,
            deadline_monotonic=float("inf"),
        )
        self.assertEqual(calls[0], float(prefix.points[0][0]))
        self.assertEqual(calls[3], float(prefix.points[1][0]))
        self.assertEqual(calls[6], float(prefix.points[2][0]))
        self.assertTrue(runtime.summary["portal_activated"])
        self.assertEqual(runtime.summary["midpoint_callbacks"], 1)
        self.assertIn(calls[-1], calls[:9])
        self.assertNotEqual(calls[-2], calls[-1])
        self.assertEqual(outcome.counters["guard_merge_portal_activations"], 1)
        self.assertLessEqual(budget.callbacks, 12)

    def test_unknown_continues_exact_original_prefix_without_candidate_counters(self):
        runtime, run, case, budget, prefix, calls = build_runtime(activate=False)
        outcome = run(
            "arm",
            base_case=case,
            budget=budget,
            program=None,
            literal_prefix=prefix,
            callback_cap=12,
            callbacks_per_start=1,
            deadline_monotonic=float("inf"),
        )
        self.assertEqual(calls, [float(point[0]) for point in prefix.points])
        self.assertEqual(runtime.summary["mode"], "UNKNOWN_FULL_BASELINE_FALLBACK")
        self.assertFalse(runtime.summary["portal_activated"])
        self.assertEqual(outcome.statuses, {"ok": 12})
        self.assertEqual(outcome.counters, {})
        self.assertEqual([lane for lane, _point in outcome.endpoints], list(range(12)))
        self.assertEqual(outcome.lane_callbacks, (1,) * 12)

    def test_period_four_iid_insurance_is_retained_in_baseline_prefix(self):
        pilot, fallback, resume = portal_connector._phase_ordinals(256)
        self.assertEqual(pilot, (0, 1, 2))
        self.assertEqual(fallback, tuple(range(3, 256)))
        self.assertEqual(resume, tuple(range(4, 256)))
        retained = (*pilot, *resume)
        self.assertEqual(sum(index % 4 == 0 for index in retained), 64)

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
