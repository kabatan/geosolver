from __future__ import annotations

from copy import deepcopy
import unittest

from candidate import certify, disposition, verify_certificate
from generated_cases import metamorphics, negatives, positives


class CandidateTests(unittest.TestCase):
    def test_positive_families(self):
        for name, problem in positives().items():
            with self.subTest(name=name):
                result = certify(problem)
                self.assertTrue(result["authority"])
                self.assertEqual(result["ideal_inclusion"], "I_SUBSET_J")
                self.assertEqual(result["variety_inclusion"], "V_J_SUBSET_V_I")
                self.assertFalse(result["target_set_completeness_claim"])

    def test_negatives_fail_closed(self):
        for name, problem in negatives().items():
            with self.subTest(name=name):
                self.assertFalse(disposition(problem)["authority"])

    def test_metamorphics(self):
        for name, problem in metamorphics().items():
            with self.subTest(name=name):
                self.assertTrue(certify(problem)["authority"])

    def test_forged_moment_and_matrix(self):
        problem = positives()["quadratic-conjugates"]
        certificate = certify(problem)
        for path in ("moment", "matrix"):
            bad = deepcopy(certificate)
            if path == "moment":
                bad["hplus"][0][0] = "9"
            else:
                bad["multiplication_matrices"][0][0][0] = "9"
            with self.subTest(path=path):
                with self.assertRaises(Exception):
                    verify_certificate(problem, bad)


if __name__ == "__main__":
    unittest.main()
