from __future__ import annotations

import copy
import unittest

from candidate import CertificationFailure, certify
from generated_cases import NEGATIVE_CASES, POSITIVE_CASES, affine_target, permuted
from verifier import VerificationFailure, verify


class CandidateTests(unittest.TestCase):
    def test_positive_families_certify_and_verify(self) -> None:
        for name, problem in POSITIVE_CASES.items():
            with self.subTest(name=name):
                certificate = certify(problem)
                result = verify(problem, certificate)
                self.assertTrue(result["verified"])
                self.assertFalse(result["coordinate_exactification"])
                self.assertGreater(result["strictly_feasible_real_root_count"], 0)

    def test_nonradical_family_retains_singular_trace_form(self) -> None:
        certificate = certify(POSITIVE_CASES["nonradical-singular-degree1"])
        self.assertEqual(certificate["quotient"]["dimension"], 2)
        self.assertTrue(any(query["inertia"]["zero"] > 0 for query in certificate["tarski_queries"]))

    def test_negative_and_near_miss_cases_fail_closed(self) -> None:
        for name, (problem, expected_reason) in NEGATIVE_CASES.items():
            with self.subTest(name=name):
                with self.assertRaises(CertificationFailure) as caught:
                    certify(problem)
                self.assertEqual(caught.exception.reason, expected_reason)

    def test_variable_equation_guard_permutation(self) -> None:
        for name, problem in POSITIVE_CASES.items():
            with self.subTest(name=name):
                original = verify(problem, certify(problem))
                transformed_problem = permuted(problem)
                transformed = verify(transformed_problem, certify(transformed_problem))
                self.assertEqual(
                    original["strictly_feasible_real_root_count"],
                    transformed["strictly_feasible_real_root_count"],
                )

    def test_affine_target_metamorphic(self) -> None:
        for name, problem in POSITIVE_CASES.items():
            with self.subTest(name=name):
                original = verify(problem, certify(problem))
                transformed_problem = affine_target(problem)
                transformed = verify(transformed_problem, certify(transformed_problem))
                self.assertEqual(
                    original["strictly_feasible_real_root_count"],
                    transformed["strictly_feasible_real_root_count"],
                )

    def test_independent_verifier_rejects_certificate_mutations(self) -> None:
        problem = POSITIVE_CASES["regular-zero-dimensional-degree2"]
        certificate = certify(problem)

        bad_digest = copy.deepcopy(certificate)
        bad_digest["problem_sha256"] = "0" * 64
        with self.assertRaises(VerificationFailure):
            verify(problem, bad_digest)

        bad_matrix = copy.deepcopy(certificate)
        bad_matrix["quotient"]["multiplication_matrices"]["x"][0][0] = "1"
        with self.assertRaises(VerificationFailure):
            verify(problem, bad_matrix)

        bad_hermite = copy.deepcopy(certificate)
        bad_hermite["tarski_queries"][0]["hermite"][0][0] = "999"
        with self.assertRaises(VerificationFailure):
            verify(problem, bad_hermite)

    def test_inexact_input_is_rejected(self) -> None:
        problem = copy.deepcopy(POSITIVE_CASES["regular-zero-dimensional-degree2"])
        problem["equations"] = ["x**2 - 2.0"]
        with self.assertRaises(CertificationFailure) as caught:
            certify(problem)
        self.assertEqual(caught.exception.reason, "inexact-equation-0")

    def test_boolean_or_outside_polynomial_subset_fails_closed(self) -> None:
        problem = copy.deepcopy(POSITIVE_CASES["regular-zero-dimensional-degree2"])
        problem["guards"] = ["Or(x > 0, x < -1)"]
        with self.assertRaises(CertificationFailure) as caught:
            certify(problem)
        self.assertEqual(caught.exception.reason, "non-qq-polynomial-guard-0")


if __name__ == "__main__":
    unittest.main()
