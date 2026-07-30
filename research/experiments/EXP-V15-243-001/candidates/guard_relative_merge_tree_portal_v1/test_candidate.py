from __future__ import annotations

import copy
import hashlib
import os
import unittest

import candidate


def make_pool(label: str, dimension: int) -> dict:
    positions = [-3.1, -2.0, -1.15, -0.2, 0.9, 2.05, 3.3, 4.7, 6.2, 7.8, 9.5]
    residuals = [0.01, 0.12, 0.25, 0.40, 0.58, 0.79, 1.03, 1.30, 1.60, 1.93, 2.29]
    observations = []
    for index, (position, residual) in enumerate(zip(positions, residuals, strict=True)):
        coordinates = [position]
        if dimension >= 2:
            coordinates.append(0.071 * position * position + 0.013 * index)
        if dimension >= 3:
            coordinates.append(0.0041 * position**3 + 0.017 * index)
        observations.append(
            {
                "point": coordinates,
                "residual": residual,
                "guard_state": "INVALID" if index < 3 else "INTERIOR",
                "endpoint": index < 3,
                "charged": True,
            }
        )
    return {
        "anonymous_source_hash": hashlib.sha256(label.encode()).hexdigest(),
        "dimension": dimension,
        "scale": [1.0] * dimension,
        "typed_guard_complete": True,
        "guard_count": 2,
        "typed_guard_count": 2,
        "observations": observations,
    }


def three_families() -> list[dict]:
    return [make_pool("curved-one", 1), make_pool("curved-two", 2), make_pool("curved-three", 3)]


class GateTests(unittest.TestCase):
    def test_three_family_dynamic_gate_passes_without_threshold(self):
        result = candidate.dynamic_gate(three_families())
        self.assertTrue(result["gate_pass"])
        self.assertEqual(result["low_residual_invalid_endpoint_count"], 3)
        self.assertEqual(result["anonymous_hash_count_with_low_invalid_endpoint"], 3)
        self.assertFalse(result["threshold_or_persistence_parameter_used"])
        self.assertFalse(result["individual_observations_emitted"])

    def test_gate_fails_incomplete_guards_recurrence_and_interior_count(self):
        incomplete = three_families()
        incomplete[0]["typed_guard_complete"] = False
        self.assertFalse(candidate.dynamic_gate(incomplete)["gate_pass"])
        two = three_families()[:2]
        self.assertFalse(candidate.dynamic_gate(two)["gate_pass"])
        one_hash = three_families()
        for pool in one_hash:
            pool["anonymous_source_hash"] = "a" * 64
        self.assertFalse(candidate.dynamic_gate(one_hash)["gate_pass"])
        sparse = three_families()
        sparse[0]["observations"] = sparse[0]["observations"][:10]
        self.assertFalse(candidate.dynamic_gate(sparse)["gate_pass"])

    def test_uncharged_nonfinite_and_knn_tie_fail_closed(self):
        for mutation in ("uncharged", "nonfinite", "duplicate"):
            pools = three_families()
            if mutation == "uncharged":
                pools[0]["observations"][0]["charged"] = False
            elif mutation == "nonfinite":
                pools[0]["observations"][0]["residual"] = float("inf")
            else:
                pools[0]["observations"][1]["point"] = list(pools[0]["observations"][0]["point"])
            result = candidate.dynamic_gate(pools)
            self.assertFalse(result["gate_pass"])
            self.assertEqual(result["decision"], "UNKNOWN_FULL_BASELINE_FALLBACK")


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.pools = three_families()
        self.gate = candidate.dynamic_gate(self.pools)

    def test_portal_is_existing_interior_vertex_and_midpoint_is_probe_only(self):
        for raw in self.pools:
            proposal = candidate.select_portal(raw, self.gate)
            self.assertIsNotNone(proposal)
            interior_points = {
                tuple(item["point"])
                for item in raw["observations"]
                if item["guard_state"] == "INTERIOR"
            }
            self.assertIn(proposal.point, interior_points)
            self.assertFalse(proposal.authority_pass)
            self.assertTrue(proposal.canonical_replay_required)
            self.assertNotEqual(proposal.midpoint_probe, proposal.point)
            self.assertEqual(candidate.proposal_disposition(proposal), "SEND_TO_CANONICAL_LOCAL_AND_REPLAY")

    def test_observation_order_residual_scale_and_coordinate_scale_are_invariant(self):
        raw = self.pools[1]
        baseline = candidate.select_portal(raw, self.gate)
        reordered = copy.deepcopy(raw)
        reordered["observations"] = list(reversed(reordered["observations"]))
        reordered_proposal = candidate.select_portal(reordered, self.gate)
        self.assertEqual(reordered_proposal.point, baseline.point)
        self.assertEqual(reordered_proposal.midpoint_probe, baseline.midpoint_probe)
        residual_scaled = copy.deepcopy(raw)
        for item in residual_scaled["observations"]:
            item["residual"] *= 17.0
        self.assertEqual(candidate.select_portal(residual_scaled, self.gate).point, baseline.point)
        coordinate_scaled = copy.deepcopy(raw)
        coordinate_scaled["scale"] = [3.0, 0.25]
        for item in coordinate_scaled["observations"]:
            item["point"] = [item["point"][0] * 3.0, item["point"][1] * 0.25]
        transformed = candidate.select_portal(coordinate_scaled, self.gate)
        self.assertAlmostEqual(transformed.point[0] / 3.0, baseline.point[0])
        self.assertAlmostEqual(transformed.point[1] / 0.25, baseline.point[1])

    def test_gate_hold_returns_no_portal(self):
        self.assertIsNone(candidate.select_portal(self.pools[0], {"gate_pass": False}))

    def test_baseline_and_midpoint_charges_never_exceed_quota(self):
        for starts in range(33):
            baseline, side = candidate.partition_start_ordinals(starts, self.gate)
            self.assertGreaterEqual(4 * len(baseline), 3 * starts)
            self.assertLessEqual(4 * len(side), starts)
            self.assertEqual(sorted((*baseline, *side)), list(range(starts)))
        for callbacks in range(80):
            allocation = candidate.callback_allocation(callbacks, portal_available=True)
            self.assertGreaterEqual(4 * allocation["baseline_callbacks"], 3 * callbacks)
            self.assertLessEqual(4 * allocation["side_callbacks"], callbacks)
            self.assertEqual(sum((allocation["baseline_callbacks"], allocation["side_callbacks"])), callbacks)
            self.assertLessEqual(allocation["midpoint_evaluation_callbacks"], allocation["side_callbacks"])

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
