from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from candidate import canonical_dnf
from run_d0 import FROZEN_TAPE_SHA256, TAPE_PATH, _execute, build_report, load_tape


class ProofObligationSchedulerD0Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tape = load_tape()
        cls.cases = {case["name"]: case for case in cls.tape["cases"]}

    def test_hidden_tape_is_precommitted(self) -> None:
        self.assertEqual(hashlib.sha256(TAPE_PATH.read_bytes()).hexdigest(), FROZEN_TAPE_SHA256)
        self.assertEqual(
            self.tape["parameters_frozen_before_run"],
            {
                "and_leaf_order": "c/(1-p)",
                "or_term_order": "e/q",
                "aging_per_turn": 0.1,
                "first_service_bonus": 0.2,
            },
        )

    def test_equivalent_factoring_has_same_canonical_dnf(self) -> None:
        raw = self.cases["P3_shared_prefix"]
        original = raw["descriptors"][raw["factor_descriptor"]]
        self.assertEqual(canonical_dnf(original), canonical_dnf(raw["factored_node"]))

    def test_baseline_75_percent_is_byte_identical(self) -> None:
        for raw in self.cases.values():
            control, _truth = _execute(raw, "fifo")
            candidate, _truth = _execute(raw, "sbfe")
            self.assertEqual(control.baseline_bytes, candidate.baseline_bytes)
            self.assertEqual(candidate.baseline_reserved, 75.0)
            self.assertEqual(candidate.baseline_spent, 75.0)
            self.assertLessEqual(candidate.graph_spent, 25.0)

    def test_capability_rejection_is_selected_before_expensive_test(self) -> None:
        candidate, _truth = _execute(self.cases["P4_capability_reject"], "sbfe")
        self.assertEqual(candidate.selections[0], "capability_bit")
        self.assertNotIn("expensive", candidate.selections)
        self.assertEqual(len(candidate.certificates), 2)

    def test_shared_leaf_is_resolved_once_and_reused(self) -> None:
        candidate, _truth = _execute(self.cases["P3_shared_prefix"], "sbfe")
        self.assertEqual(candidate.selections.count("s"), 1)
        self.assertGreaterEqual(candidate.shared_resolution_hits, 2)
        self.assertEqual(len(candidate.certificates), 3)

    def test_partial_and_deadline_late_never_emit_certificate(self) -> None:
        partial, _truth = _execute(self.cases["M1_partial_no_certificate"], "sbfe")
        late, _truth = _execute(self.cases["M2_deadline_late"], "sbfe")
        self.assertEqual(partial.certificates, ())
        self.assertEqual(late.certificates, ())
        self.assertEqual(late.deadline_late, ("a",))
        self.assertNotIn("a", late.revealed)

    def test_full_generated_gate_is_go(self) -> None:
        report = build_report()
        self.assertEqual(report["decision"], "GO")
        self.assertEqual(report["aggregate"]["positive_families_improved"], 4)
        self.assertEqual(report["aggregate"]["loss_count"], 0)
        self.assertEqual(report["aggregate"]["false_authority"], 0)
        self.assertEqual(report["metamorphic"]["passed"], 40)
        self.assertTrue(all(report["gates"].values()))

    def test_candidate_module_has_no_forbidden_corpus_tokens(self) -> None:
        source = (Path(__file__).parent / "candidate.py").read_text()
        for forbidden in ("case_id", "answer_value", "formal", "sealed", "scorer"):
            self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    unittest.main()
