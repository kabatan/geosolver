from __future__ import annotations

import unittest

from static_census import CensusInputError, RECORD_FIELDS, SCHEMA, summarize


def record(**updates: object) -> dict[str, object]:
    result: dict[str, object] = {
        "complete_semantic_cover": True,
        "reversible_semantic_cover": True,
        "qq_coefficients": True,
        "exact_raw_target_ast": True,
        "complete_predicate_ledger": True,
        "global_upper_proof_producer_available": True,
        "global_upper_identity_provable": True,
        "all_specialized_fibres_finite": True,
        "ordered_field_sign_available": True,
        "source_variable_count": 1,
        "cover_variable_count": 1,
        "equation_count": 1,
        "max_total_degree": 2,
        "total_term_count": 4,
        "max_coefficient_bits": 8,
        "predicate_count": 1,
        "global_upper_degree": 2,
        "target_root_count": 2,
        "max_target_factor_degree": 1,
        "max_specialized_quotient_dimension": 2,
    }
    result.update(updates)
    assert set(result) == RECORD_FIELDS
    return result


class StaticCensusTest(unittest.TestCase):
    def test_aggregate_gate_and_no_records(self) -> None:
        document = {
            "schema_version": SCHEMA,
            "records": [
                record(),
                record(source_variable_count=2, cover_variable_count=4, equation_count=4),
                record(source_variable_count=2, cover_variable_count=4, equation_count=4),
                record(source_variable_count=2, cover_variable_count=4, equation_count=4),
                record(complete_predicate_ledger=False),
            ],
        }
        result = summarize(document)
        self.assertEqual(result["counts"]["eligible_count"], 4)
        self.assertEqual(result["counts"]["eligible_signature_count"], 2)
        self.assertTrue(result["gate"]["pass"])
        self.assertNotIn("records", result)
        self.assertFalse(result["authority"])
        self.assertFalse(result["release"])

    def test_identity_field_rejected(self) -> None:
        item = record()
        item["source_sha256"] = "forbidden"
        with self.assertRaises(CensusInputError):
            summarize({"schema_version": SCHEMA, "records": [item]})


if __name__ == "__main__":
    unittest.main()
