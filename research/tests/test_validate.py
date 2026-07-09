from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "validate.py"
SPEC = importlib.util.spec_from_file_location("research_validate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE)


class SchemaSubsetTests(unittest.TestCase):
    def test_required_and_additional_properties(self) -> None:
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
        self.assertEqual(VALIDATE.validate_instance({"name": "ok"}, schema), [])
        self.assertTrue(VALIDATE.validate_instance({}, schema))
        self.assertTrue(VALIDATE.validate_instance({"name": "ok", "extra": 1}, schema))

    def test_local_ref_and_const(self) -> None:
        schema = {
            "type": "object",
            "properties": {"version": {"$ref": "#/$defs/version"}},
            "required": ["version"],
            "$defs": {"version": {"const": "1.0.0"}},
        }
        self.assertEqual(VALIDATE.validate_instance({"version": "1.0.0"}, schema), [])
        self.assertTrue(VALIDATE.validate_instance({"version": "2.0.0"}, schema))

    def test_repository_artifacts_validate(self) -> None:
        self.assertEqual(VALIDATE.main(), 0)


if __name__ == "__main__":
    unittest.main()
