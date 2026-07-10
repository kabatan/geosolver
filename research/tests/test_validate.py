from __future__ import annotations

import copy
import importlib.util
import json
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


class ExperimentTerminalStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        card_path = VALIDATE.CARD_DIR / "EXP-JAC-003.json"
        cls.base_card = json.loads(card_path.read_text(encoding="utf-8"))
        cls.literature_text = VALIDATE.LITERATURE.read_text(encoding="utf-8")
        cls.failure_ids = VALIDATE.failure_ids_from_markdown(
            VALIDATE.FAILURES.read_text(encoding="utf-8")
        )
        cls.schema = VALIDATE.load_json(
            VALIDATE.SCHEMA_DIR / "experiment-card.schema.json"
        )

    def terminal_card(self) -> dict[str, object]:
        card = copy.deepcopy(self.base_card)
        card["status"] = "terminated"
        card["decision"] = {
            "state": "inconclusive",
            "selected_variant": None,
            "rationale": "The frozen experiment ended before producing decision evidence.",
            "decision_commit": "0123456789abcdef",
        }
        return card

    def semantic_errors(self, card: dict[str, object]) -> list[str]:
        return VALIDATE.validate_card_semantics(
            card, self.literature_text, self.failure_ids
        )

    def test_terminated_inconclusive_is_schema_and_semantically_valid(self) -> None:
        card = self.terminal_card()
        self.assertEqual(
            VALIDATE.validate_instance(card, self.schema, root_schema=self.schema), []
        )
        self.assertEqual(self.semantic_errors(card), [])

    def test_terminated_allows_only_inconclusive_decision(self) -> None:
        card = self.terminal_card()
        card["decision"]["state"] = "rejected"
        errors = self.semantic_errors(card)
        self.assertTrue(
            any(
                "status terminated is inconsistent with decision rejected" in error
                for error in errors
            )
        )

    def test_inconclusive_is_allowed_only_for_terminated_status(self) -> None:
        card = self.terminal_card()
        card["status"] = "completed"
        errors = self.semantic_errors(card)
        self.assertTrue(
            any(
                "status completed is inconsistent with decision inconclusive" in error
                for error in errors
            )
        )

    def test_inconclusive_cannot_select_a_variant(self) -> None:
        card = self.terminal_card()
        card["decision"]["selected_variant"] = "JAC-CACHED"
        errors = self.semantic_errors(card)
        self.assertIn(
            "EXP-JAC-003: inconclusive decision cannot select a variant", errors
        )

    def test_inconclusive_requires_rationale_and_decision_commit(self) -> None:
        for missing_field in ("rationale", "decision_commit"):
            with self.subTest(missing_field=missing_field):
                card = self.terminal_card()
                card["decision"][missing_field] = None
                errors = self.semantic_errors(card)
                self.assertIn(
                    "EXP-JAC-003: final decision requires rationale and decision_commit",
                    errors,
                )


if __name__ == "__main__":
    unittest.main()
