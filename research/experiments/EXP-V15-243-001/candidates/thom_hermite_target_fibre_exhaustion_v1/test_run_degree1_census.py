from __future__ import annotations

import unittest

from run_degree1_census import (
    DegreeOneCensusError,
    _degree_one_relation,
    _empty_feature,
    _endpoint,
    _validated_request,
)
from static_census import RECORD_FIELDS


class DegreeOneCensusContractTest(unittest.TestCase):
    def test_request_contract_is_exact(self) -> None:
        request = {
            "source_path": "/tmp/anonymous.json",
            "endpoint": [0.0],
            "candidate_relation_high_to_low": [1, -2],
        }
        self.assertEqual(_validated_request(request), request)
        request["outcome"] = "forbidden"
        with self.assertRaises(DegreeOneCensusError):
            _validated_request(request)

    def test_process_local_numeric_fields_are_strict(self) -> None:
        self.assertEqual(_endpoint([1, -0.5]), (1.0, -0.5))
        self.assertEqual(_degree_one_relation([3, -2]), (3, -2))
        with self.assertRaises(DegreeOneCensusError):
            _endpoint([float("nan")])
        with self.assertRaises(DegreeOneCensusError):
            _degree_one_relation([-1, 0])
        with self.assertRaises(DegreeOneCensusError):
            _degree_one_relation([2, 2])

    def test_failed_record_has_only_sanitized_feature_fields(self) -> None:
        feature = _empty_feature()
        self.assertEqual(set(feature), RECORD_FIELDS)
        self.assertFalse(any(feature.values()))


if __name__ == "__main__":
    unittest.main()
