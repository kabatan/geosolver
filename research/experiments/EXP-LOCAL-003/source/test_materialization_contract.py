"""Static C0 boundary tests for EXP-LOCAL-003.

These tests inspect preregistered contracts only. They do not generate formal
inputs, execute a candidate, or open an outcome.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
import unittest
from fractions import Fraction
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXPERIMENT_ROOT.parents[2]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
if str(PYTHON_SOURCE) not in sys.path:
    sys.path.insert(0, str(PYTHON_SOURCE))

from geotarget.canonical import canonical_bytes  # noqa: E402


CARD_PATH = EXPERIMENT_ROOT.parent / "EXP-LOCAL-003.json"
VISIBILITY_PATH = EXPERIMENT_ROOT / "visibility-contract.json"
NUMERIC_PATH = EXPERIMENT_ROOT / "numeric-json-domain.json"
CARD_SHA256 = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} is not an object")
    return value


def _bits(value: float) -> str:
    return f"0x{struct.unpack('>Q', struct.pack('>d', value))[0]:016x}"


def _from_bits(value: str) -> float:
    return struct.unpack(">d", int(value, 16).to_bytes(8, "big"))[0]


def _correctly_rounded_fma(a: float, b: float, c: float) -> float:
    exact = Fraction.from_float(a) * Fraction.from_float(b) + Fraction.from_float(c)
    return float(exact)


class MaterializationContractTests(unittest.TestCase):
    def test_contract_binds_frozen_card(self) -> None:
        self.assertEqual(hashlib.sha256(CARD_PATH.read_bytes()).hexdigest(), CARD_SHA256)
        contract = _load(VISIBILITY_PATH)
        self.assertEqual(contract["card_sha256"], CARD_SHA256)
        self.assertFalse(contract["production_connection"])

    def test_visibility_preserves_dsl_but_denies_identity_and_gold(self) -> None:
        contract = _load(VISIBILITY_PATH)
        candidate = contract["trees"]["candidate"]  # type: ignore[index]
        forbidden = " ".join(candidate["forbidden_case_material"]).lower()  # type: ignore[index]
        self.assertIn("family", forbidden)
        self.assertIn("latent-group", forbidden)
        self.assertIn("representation", forbidden)
        self.assertIn("gold", forbidden)
        self.assertIn("calibration_key", forbidden)
        self.assertIn("problemspecv1.target", candidate["semantic_target_exception"].lower())  # type: ignore[index]

        route = contract["mandatory_dsl_path"]
        self.assertEqual(route[0], "Python SDK ProblemBuilder")  # type: ignore[index]
        self.assertIn("compile_problem", route)
        self.assertIn("evaluate(compiled, C0)", route)
        self.assertIn("evaluate_canonical and validate_candidate", route)
        self.assertIn("DirectAnalyticProblem", contract["forbidden_shortcuts"])

    def test_numeric_tokens_use_semantic_domain_not_parser_subclass(self) -> None:
        fixture = _load(NUMERIC_PATH)
        payload = json.loads(fixture["canonical_payload_text"])  # type: ignore[arg-type]
        self.assertEqual(canonical_bytes(payload).decode("utf-8"), fixture["canonical_payload_text"])
        cases = fixture["cases"]
        for case in cases:  # type: ignore[assignment]
            value = case["json_value"]
            self.assertIsInstance(value, (int, float))
            self.assertNotIsInstance(value, bool)
            if case["semantic_domain"] == "finite_binary64_real":
                normalized = float(value)
                self.assertTrue(math.isfinite(normalized))
                self.assertEqual(_bits(normalized), case["binary64_bits"])

    def test_fraction_fma_matches_frozen_binary64_bits(self) -> None:
        fixture = _load(NUMERIC_PATH)
        for case in fixture["fma_fixture"]:  # type: ignore[index]
            result = _correctly_rounded_fma(
                _from_bits(case["a_bits"]),
                _from_bits(case["b_bits"]),
                _from_bits(case["c_bits"]),
            )
            self.assertEqual(_bits(result), case["result_bits"])

    def test_extended_reals_are_strings(self) -> None:
        values = _load(NUMERIC_PATH)["extended_real_tokens"]
        self.assertEqual(values["positive_infinity"], "+Inf")  # type: ignore[index]
        self.assertEqual(values["negative_infinity"], "-Inf")  # type: ignore[index]
        with self.assertRaises(ValueError):
            json.dumps(float("inf"), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
