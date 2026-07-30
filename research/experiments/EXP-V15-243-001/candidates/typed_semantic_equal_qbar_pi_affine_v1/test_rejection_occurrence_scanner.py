from __future__ import annotations

import os
import unittest

import rejection_occurrence_scanner as occurrence


def base_source() -> dict:
    return {
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "A", "expr": "Point(0,0)"},
            {"name": "B", "expr": "Point(1,0)"},
            {"name": "C", "expr": "Point(0,1)"},
            {"name": "theta", "expr": "Angle(A,B,C)"},
        ],
        "constraints": [
            {"def": "theta", "value": "theta"},
            {"def": "theta", "value": "x"},
        ],
        "guards": [],
        "bounds": None,
        "answer": "x",
    }


class OccurrenceTests(unittest.TestCase):
    def test_selected_angle_equality_is_not_the_rejecting_root(self):
        result = occurrence.scan(base_source())
        self.assertEqual(result["repair_a_selected_relation_root_count"], 1)
        self.assertEqual(result["repair_a_selected_actual_rejecting_root_count"], 0)
        self.assertEqual(result["actual_rejecting_occurrence_count"], 1)
        key = next(iter(result["anonymous_rejecting_occurrence_counts"]))
        self.assertIn("constraint_synthetic_root", key)
        self.assertIn("UNSELECTED", key)
        self.assertIn("NO_EXACT_QQBAR_TO_ANGLE_COERCION", key)

    def test_construction_and_raw_answer_are_separate_unreachable_sites(self):
        document = base_source()
        document["construction"].append({"name": "bad", "expr": "theta-x"})
        document["answer"] = "theta-y"
        result = occurrence.scan(document)
        keys = result["anonymous_rejecting_occurrence_counts"]
        self.assertTrue(any(key.startswith("construction|") for key in keys))
        self.assertTrue(any(key.startswith("raw_answer|") for key in keys))
        self.assertEqual(result["angle_scalar_occurrences_without_exact_qbar_coercion"], 3)

    def test_pi_affine_site_is_separated_as_already_covered(self):
        document = base_source()
        document["construction"].append({"name": "affine", "expr": "pi+x"})
        result = occurrence.scan(document)
        self.assertEqual(result["pi_affine_occurrences_already_covered_by_repair_a_worker"], 1)

    def test_scaled_angle_and_comparison_reach_extended_as_angle_sites(self):
        document = base_source()
        document["construction"].append({"name": "twice", "expr": "2*theta"})
        document["guards"] = ["twice < x"]
        result = occurrence.scan(document)
        keys = result["anonymous_rejecting_occurrence_counts"]
        self.assertTrue(any("guard|COMPARISON|ANGLE_WITH_NONANGLE_SCALAR" in key for key in keys))

    def test_minmax_mixed_angle_scalar_is_localized(self):
        document = base_source()
        document["answer"] = "min(theta,x)"
        result = occurrence.scan(document)
        self.assertTrue(any("raw_answer|MINMAX|ANGLE_WITH_NONANGLE_SCALAR" in key for key in result["anonymous_rejecting_occurrence_counts"]))

    def test_exact_zero_never_emits_as_angle_rejection(self):
        document = base_source()
        document["constraints"] = [{"def": "theta", "value": 0}]
        result = occurrence.scan(document)
        self.assertEqual(result["actual_rejecting_occurrence_count"], 0)

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
