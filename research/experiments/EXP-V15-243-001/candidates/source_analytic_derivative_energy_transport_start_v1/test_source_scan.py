from __future__ import annotations

import unittest

import sympy as sp

from run_source_scan import ScanError, _bounds, _request, _signature


class SourceScanContractTest(unittest.TestCase):
    def test_source_only_request_whitelist(self) -> None:
        self.assertEqual(_request({"source_path": "/tmp/source.json"}), {"source_path": "/tmp/source.json"})
        with self.assertRaises(ScanError):
            _request({"source_path": "/tmp/source.json", "target": 2})
        with self.assertRaises(ScanError):
            _request({"source_path": "/tmp/source.json", "outcome": "pass"})

    def test_exact_finite_bounds(self) -> None:
        self.assertEqual(
            _bounds({"bounds": [[-1, 1], ["1/3", "2/3"]]}, 2),
            ((sp.Rational(-1), sp.Rational(1)), (sp.Rational(1, 3), sp.Rational(2, 3))),
        )
        with self.assertRaises(ScanError):
            _bounds({"bounds": [[1, 1]]}, 1)

    def test_signature_is_aggregate_structure_only(self) -> None:
        x, y = sp.symbols("x y")
        residuals = (sp.Poly(x + y, x, y, domain=sp.QQ),)
        signature = _signature(2, residuals, sp.Matrix([[1, 1], [1, 1]]))
        self.assertEqual(signature[:3], (2, -1, 1))
        self.assertNotIn("source_path", signature)


if __name__ == "__main__":
    unittest.main()
