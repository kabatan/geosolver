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

    def test_post_m0_cards_do_not_remove_frozen_preregistrations(self) -> None:
        card_stems = {path.stem for path in (VALIDATE.CARD_DIR).glob("EXP-*.json")}
        self.assertTrue(
            {"EXP-COMP-001", "EXP-LOCAL-001", "EXP-DISC-001"}.issubset(card_stems)
        )
        self.assertIn("EXP-LOCAL-002", card_stems)

    def test_evidence_links_are_unique_and_state_aware(self) -> None:
        evidence = """\
| EVID-01 | prior | implication |

## Reproduced current evidence

| EVID-12 | reproduced | decision |
"""
        valid = {
            "entries": [
                {
                    "id": "NEG-001",
                    "evidence_state": "prior_unreproduced",
                    "source_evidence_ids": ["EVID-01"],
                },
                {
                    "id": "NEG-002",
                    "evidence_state": "reproduced",
                    "source_evidence_ids": ["EVID-12"],
                },
            ]
        }
        self.assertEqual(VALIDATE.validate_evidence_links(valid, evidence), [])

        duplicate = evidence + "\n| EVID-12 | duplicate | invalid |\n"
        errors = VALIDATE.validate_evidence_links(valid, duplicate)
        self.assertTrue(any("occurs 2 times" in error for error in errors))

        invalid = {
            "entries": [
                {
                    "id": "NEG-003",
                    "evidence_state": "reproduced",
                    "source_evidence_ids": ["EVID-01", "EVID-99"],
                }
            ]
        }
        errors = VALIDATE.validate_evidence_links(invalid, evidence)
        self.assertTrue(any("non-reproduced EVID-01" in error for error in errors))
        self.assertTrue(any("EVID-99 is absent" in error for error in errors))

        duplicated_negative = {"entries": [valid["entries"][0], valid["entries"][0]]}
        errors = VALIDATE.validate_evidence_links(duplicated_negative, evidence)
        self.assertTrue(any("NEG-001 occurs 2 times" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
