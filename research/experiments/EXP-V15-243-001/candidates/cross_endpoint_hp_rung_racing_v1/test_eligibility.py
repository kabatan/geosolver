from __future__ import annotations

import copy
import hashlib
import json
import os
import unittest

import eligibility


SOURCE_SHA = "a" * 64


def source() -> dict:
    return {
        "task": "solve",
        "variables": {"names": ["x", "y", "u", "v"]},
        "construction": [
            {"name": "A", "expr": "Point(x,y)"},
            {"name": "B", "expr": "Point(u,v)"},
            {"name": "L", "expr": "Line(A,B)"},
        ],
        "constraints": [
            {"def": "Distance(A,B)", "value": 1},
            {"def": "OnLine(A,L)", "value": 0},
        ],
        "guards": ["x < u", {"expr": "Distance(A,B) > 0"}],
        "bounds": None,
        "answer": "Distance(A,B)",
        "post_process": None,
    }


class EligibilityTests(unittest.TestCase):
    def test_generated_closed_sources_are_broadly_eligible(self):
        result = eligibility.scan(source(), SOURCE_SHA)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["activation_requires_safe_endpoint_count_at_least"], 2)
        self.assertTrue(result["all_endpoints_receive_low_rung"])
        self.assertFalse(result["authority_or_descriptor_shared_across_endpoints"])
        self.assertTrue(result["each_endpoint_requires_own_canonical_replay"])

    def test_variable_rename_constraint_reorder_and_literal_change_are_invariant(self):
        original = eligibility.scan(source(), SOURCE_SHA)
        transformed = source()
        transformed["variables"]["names"] = ["p", "q", "r", "s"]
        replacements = {"x": "p", "y": "q", "u": "r", "v": "s"}
        for item in transformed["construction"]:
            for old, new in replacements.items():
                item["expr"] = item["expr"].replace(old, new)
        transformed["guards"][0] = "p < r"
        transformed["constraints"].reverse()
        transformed["constraints"][0]["value"] = 2
        changed = eligibility.scan(transformed, SOURCE_SHA)
        self.assertTrue(changed["eligible"])
        self.assertEqual(
            original["anonymous_structural_fingerprint_sha256"],
            changed["anonymous_structural_fingerprint_sha256"],
        )

    def test_postprocess_dynamic_nested_and_malformed_sources_fail_closed(self):
        variants = []
        post = source()
        post["post_process"] = "sqrt(x)"
        variants.append(post)
        dynamic = source()
        dynamic["constraints"][0]["def"] = "factory()(A)"
        variants.append(dynamic)
        nested = source()
        nested["answer"] = "[x for x in (1,2)][0]"
        variants.append(nested)
        malformed = source()
        malformed["constraints"] = []
        variants.append(malformed)
        for document in variants:
            self.assertFalse(eligibility.scan(document, SOURCE_SHA)["eligible"])

    def test_output_is_source_only_aggregate_without_values(self):
        document = source()
        document["forbidden_truth"] = "DO_NOT_READ"
        result = eligibility.scan(document, SOURCE_SHA)
        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("DO_NOT_READ", rendered)
        self.assertNotIn("Distance(A,B)", rendered)
        self.assertNotIn("x < u", rendered)
        self.assertEqual(result["source_sha256"], SOURCE_SHA)

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
