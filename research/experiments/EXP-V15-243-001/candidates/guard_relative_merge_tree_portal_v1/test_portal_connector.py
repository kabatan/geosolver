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
    positions = [
        -3.1, -2.0, -1.15, -0.2, 0.9, 2.05, 3.3, 4.7,
        6.2, 7.8, 9.5, 11.4, 13.5, 15.8, 18.2, 20.9,
    ]
    residuals = [
        0.12, 0.25, 0.40, 0.58, 0.01, 0.79, 1.03, 1.30,
        1.60, 1.93, 2.29, 2.68, 3.10, 3.55, 4.03, 4.54,
    ]
    # The first complete insurance block cannot activate.  Evidence arrives
    # only while evaluating the second block, so activation proves that the
    # Repair A block loop is causal rather than a static three-start split.
    second_block_extras = {
        positions[4]: positions[8:10],
        positions[5]: positions[10:12],
        positions[6]: positions[12:14],
    }

    def evaluate(point):
        value = float(np.asarray(point)[0])
        calls.append(value)
        budget.callbacks += 1
        nearest = min(range(len(positions)), key=lambda i: abs(positions[i] - value))
        invalid = bool(activate and nearest == 4 and value == positions[4])
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
            if activate and value in second_block_extras:
                for extra in second_block_extras[value]:
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
            callback_cap=32,
            callbacks_per_start=1,
            deadline_monotonic=float("inf"),
        )
        self.assertEqual(calls[:4], [float(point[0]) for point in prefix.points[:4]])
        self.assertTrue(runtime.summary["portal_activated"])
        self.assertEqual(runtime.summary["portal_detection_after_original_starts"], 8)
        self.assertEqual(runtime.summary["baseline_blocks_completed"], 2)
        self.assertEqual(runtime.summary["midpoint_callbacks"], 1)
        self.assertLessEqual(
            runtime.summary["portal_callbacks_used_including_midpoint"], 8
        )
        original_lanes = {lane for lane, _point in outcome.endpoints if lane < 16}
        self.assertEqual(original_lanes, set(range(16)))
        self.assertIn(16, {lane for lane, _point in outcome.endpoints})
        self.assertEqual(outcome.counters["guard_merge_portal_activations"], 1)
        self.assertLessEqual(budget.callbacks, 32)

    def test_unknown_continues_exact_original_prefix_without_candidate_counters(self):
        runtime, run, case, budget, prefix, calls = build_runtime(activate=False)
        outcome = run(
            "arm",
            base_case=case,
            budget=budget,
            program=None,
            literal_prefix=prefix,
            callback_cap=32,
            callbacks_per_start=1,
            deadline_monotonic=float("inf"),
        )
        self.assertEqual(calls, [float(point[0]) for point in prefix.points])
        self.assertEqual(runtime.summary["mode"], "UNKNOWN_FULL_BASELINE_FALLBACK")
        self.assertFalse(runtime.summary["portal_activated"])
        self.assertEqual(outcome.statuses, {"ok": 16})
        self.assertEqual(outcome.counters, {})
        self.assertEqual([lane for lane, _point in outcome.endpoints], list(range(16)))
        self.assertEqual(outcome.lane_callbacks, (1,) * 16)

    def test_period_four_iid_insurance_is_retained_in_baseline_prefix(self):
        blocks = portal_connector._complete_insurance_blocks(256)
        self.assertEqual(blocks[0], (0, 1, 2, 3))
        self.assertEqual(blocks[-1], (252, 253, 254, 255))
        self.assertEqual(tuple(index for block in blocks for index in block), tuple(range(256)))
        resume = portal_connector._resume_ordinals(8, 256)
        self.assertEqual(resume[:62], tuple(range(8, 256, 4)))
        self.assertEqual(set(resume), set(range(8, 256)))

    def test_signed_zero_endpoint_membership_is_geometrically_invariant(self):
        runtime, _run, _case, _budget, _prefix, _calls = build_runtime(activate=False)
        runtime.collector._rows = [{"point": [-0.0], "endpoint": False}]
        marked = runtime._mark_endpoints(((0, np.asarray([+0.0])),))
        self.assertEqual(marked, 1)
        self.assertTrue(runtime.collector._rows[0]["endpoint"])

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
