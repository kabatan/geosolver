from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "conformance_adapter.py"
SPEC = importlib.util.spec_from_file_location("rank_guard_conformance", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ConformanceAdapterTests(unittest.TestCase):
    def test_zero_precision_buckets_are_canonical_no_work(self) -> None:
        self.assertEqual(MODULE.normalized_ledger({"512": 0}), {})
        self.assertEqual(
            MODULE.normalized_ledger({"float64": 8, "512": 0}),
            {"float64": 8},
        )

    def test_proposal_and_route_signatures_remain_separate(self) -> None:
        common = {
            "activation_observables": {"tier_started": True},
            "assessor": {
                "matched_isolated_root_classes": [],
                "safety_control": False,
                "valid_refinement_seed": False,
            },
            "emission_kind": "none",
            "emitted_brackets": [],
            "emitted_seed_coordinates": [],
            "observed_precision_counts": {"256": 9},
            "requested_precision_counts": {"256": 9},
            "reported_weighted_work": 45,
            "reason": "rank_deficient_unisolated",
            "status": "unknown",
        }
        different_route = dict(common)
        different_route["requested_precision_counts"] = {"128": 9, "256": 9}
        different_route["reported_weighted_work"] = 72
        self.assertEqual(
            MODULE._proposal_signature(common),
            MODULE._proposal_signature(different_route),
        )
        self.assertNotEqual(
            MODULE._route_signature(common),
            MODULE._route_signature(different_route),
        )


if __name__ == "__main__":
    unittest.main()
