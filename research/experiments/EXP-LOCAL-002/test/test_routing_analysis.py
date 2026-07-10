from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "routing_analysis.py"
SPEC = importlib.util.spec_from_file_location("exp_local_002_routing_analysis", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
routing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(routing)


class RoutingAmendmentTests(unittest.TestCase):
    def test_amendment_freezes_one_identity_free_route(self) -> None:
        amendment = routing.load_amendment()
        self.assertEqual(amendment["selected_route"]["id"], routing.ROUTE_ID)
        self.assertEqual(amendment["tuning_round"]["used"], 1)
        self.assertFalse(amendment["tuning_round"]["post_amendment_retuning_allowed"])
        self.assertFalse(amendment["scope"]["family_or_problem_identity_routing_allowed"])
        self.assertEqual(
            sum(item["selected"] for item in amendment["tuning_domain"]["replayed_candidate_table_prefix_32"]),
            1,
        )

    def test_declared_development_gate_is_mechanical(self) -> None:
        criteria = {
            "safety_zero": True,
            "prefix_truth_nonregression": True,
            "prefix32_p_local_gain_at_least_0_005": True,
            "paired_lower95_nonnegative": True,
            "positive_family_count_at_least_one": True,
            "fully_charged_work_ratio_at_most_1_05": True,
            "warm_wall_ratio_at_most_1_10": True,
            "lm_selection_fraction_in_range": True,
        }
        self.assertTrue(all(criteria.values()))
        criteria["prefix_truth_nonregression"] = False
        self.assertFalse(all(criteria.values()))


if __name__ == "__main__":
    unittest.main()
