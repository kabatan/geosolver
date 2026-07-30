from __future__ import annotations

import json
import unittest
from unittest import mock

import audit_development_formulations as audit


class FormulationBoundaryTests(unittest.TestCase):
    def test_only_formulation_value_is_materialized(self):
        row = (
            b'{"problem_id":"must-not-be-retained",'
            b'"expected":{"nested":"must-not-be-decoded"},'
            b'"formulation":{"task":"solve","variables":{"names":["x"]}}}'
        )
        real_loads = json.loads
        decoded = []

        def observing_loads(value, *args, **kwargs):
            decoded.append(bytes(value) if isinstance(value, (bytes, bytearray)) else value)
            return real_loads(value, *args, **kwargs)

        with mock.patch.object(audit.json, "loads", side_effect=observing_loads):
            source = audit.formulation_bytes(row)

        self.assertEqual(
            source, b'{"task":"solve","variables":{"names":["x"]}}'
        )
        self.assertNotIn(b'{"nested":"must-not-be-decoded"}', decoded)
        self.assertNotIn('"must-not-be-retained"', decoded)

    def test_nested_formulation_label_in_sibling_does_not_confuse_boundary(self):
        row = (
            b'{"result":{"formulation":{"wrong":true}},'
            b'"formulation":{"task":"solve"}}'
        )
        self.assertEqual(
            audit.formulation_bytes(row), b'{"task":"solve"}'
        )

    def test_duplicate_formulation_fails_closed(self):
        with self.assertRaises(audit.SourceBoundaryError):
            audit.formulation_bytes(b'{"formulation":{},"formulation":{}}')

    def test_malformed_boundaries_fail_closed(self):
        for row in (
            b'[]',
            b'{"other":1}',
            b'{"formulation":{"x":1]',
            b'{"formulation":{}} trailing',
        ):
            with self.subTest(row=row), self.assertRaises(audit.SourceBoundaryError):
                audit.formulation_bytes(row)


if __name__ == "__main__":
    unittest.main()
