from __future__ import annotations

import unittest

from prototype import fixtures, run_all, solve


class PrototypeTest(unittest.TestCase):
    def test_frozen_gate(self) -> None:
        result = run_all()
        self.assertTrue(result["aggregate"]["gate_pass"])
        self.assertEqual(result["aggregate"]["positive_authority_pass"], 3)
        self.assertEqual(result["aggregate"]["false_authority_count"], 0)
        self.assertTrue(result["aggregate"]["even_multiplicity_authority"])

    def test_each_expected_disposition(self) -> None:
        for problem in fixtures():
            with self.subTest(problem=problem.name):
                record = solve(problem)
                self.assertEqual(record["authority"], problem.expected_authority)


if __name__ == "__main__":
    unittest.main()
