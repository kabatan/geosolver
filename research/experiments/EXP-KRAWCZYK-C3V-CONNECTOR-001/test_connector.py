from __future__ import annotations

import unittest

from connector import c3v, connect
from generated_cases import cases


class ConnectorTests(unittest.TestCase):
    def test_generated_expectations_and_baseline_quota(self) -> None:
        for item in cases():
            with self.subTest(item.name):
                payload = item.name.encode()
                result = connect(item.problem, total_work=8, baseline_payload=payload)
                self.assertEqual(result.authority, item.expected_authority, result.reason)
                self.assertGreaterEqual(result.baseline_work, 6)
                self.assertEqual(result.side_work, 1)
                self.assertEqual(result.baseline_payload, payload)
                if result.authority:
                    self.assertIsNotNone(result.source_certificate)
                    self.assertIsNotNone(result.target_link)
                    self.assertTrue(c3v.verify_artifact(result.target_link))
                    self.assertTrue(result.target_link["source_certificate_join_verified"])

    def test_certificate_tamper_fails_closed_at_existing_join(self) -> None:
        result = connect(cases()[0].problem)
        self.assertTrue(result.authority)
        certificate = dict(result.source_certificate)
        certificate["certified_target_interval"] = ["0", "3"]
        rejected = c3v.prove_with_verified_source_certificate(
            variables=cases()[0].problem.variables,
            source_equations=cases()[0].problem.source_equations,
            target_expression=cases()[0].problem.target_expression,
            coefficients_high_to_low=cases()[0].problem.candidate_coefficients_high_to_low,
            descriptor_selection_interval=cases()[0].problem.descriptor_selection_interval,
            source_certificate=certificate,
        )
        self.assertEqual(rejected["status"], "NOT_PROVED")
        self.assertEqual(rejected["reason"], "source-certificate-self-digest-mismatch")


if __name__ == "__main__":
    unittest.main()
