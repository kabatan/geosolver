#!/usr/bin/env python3
"""Validate GeoTarget research artifacts with Python's standard library."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "research" / "schemas"
CARD_DIR = ROOT / "research" / "experiments"
LEDGER = ROOT / "research" / "negative-results" / "ledger.json"
ENVELOPE = ROOT / "benchmarks" / "manifests" / "m0-m4-tested-envelope.json"
EXAMPLE_DIR = ROOT / "research" / "examples"
LITERATURE = ROOT / "docs" / "research" / "LITERATURE_MATRIX.md"
FAILURES = ROOT / "docs" / "research" / "FAILURES.md"
EVIDENCE = ROOT / "docs" / "research" / "EVIDENCE.md"


class ValidationError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: cannot load JSON: {exc}") from exc


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    raise ValidationError(f"validator: unsupported schema type {expected!r}")


def _resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValidationError(f"validator: only local schema refs are supported: {ref}")
    current: Any = root_schema
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[token]
    if not isinstance(current, dict):
        raise ValidationError(f"validator: ref does not resolve to a schema: {ref}")
    return current


def validate_instance(
    value: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> list[str]:
    """Validate the JSON-Schema subset used by this repository."""

    root_schema = root_schema or schema
    if "$ref" in schema:
        schema = _resolve_ref(root_schema, schema["$ref"])

    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        expected_types = expected if isinstance(expected, list) else [expected]
        if not any(_matches_type(value, kind) for kind in expected_types):
            return [f"{path}: expected {expected_types}, got {type(value).__name__}"]

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']!r}")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string shorter than minLength")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            errors.append(f"{path}: {value!r} does not match {pattern!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above maximum {schema['maximum']}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: array shorter than minItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    validate_instance(
                        item,
                        item_schema,
                        root_schema=root_schema,
                        path=f"{path}[{index}]",
                    )
                )

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: object has fewer than minProperties")

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                errors.extend(
                    validate_instance(
                        item,
                        properties[key],
                        root_schema=root_schema,
                        path=f"{path}.{key}",
                    )
                )
            elif additional is False:
                errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                errors.extend(
                    validate_instance(
                        item,
                        additional,
                        root_schema=root_schema,
                        path=f"{path}.{key}",
                    )
                )
    return errors


def validate_card_semantics(
    card: dict[str, Any], literature_text: str, failure_ids: set[str]
) -> list[str]:
    errors: list[str] = []
    card_id = card["id"]
    if card["baseline_id"] != "RB0-IID-LMQR-1":
        errors.append(f"{card_id}: unexpected M0-M4 baseline")
    allowed_decisions = {
        "preregistered": {"pending"},
        "running": {"pending"},
        "completed": {"promoted", "specialized", "rejected"},
        "promoted": {"promoted", "specialized"},
        "rejected": {"rejected"},
        "terminated": {"inconclusive"},
    }
    decision = card["decision"]
    if decision["state"] not in allowed_decisions[card["status"]]:
        errors.append(
            f"{card_id}: status {card['status']} is inconsistent with "
            f"decision {decision['state']}"
        )
    if decision["state"] == "pending":
        if any(
            decision[field] is not None
            for field in ("selected_variant", "rationale", "decision_commit")
        ):
            errors.append(
                f"{card_id}: pending decision must not contain a frozen outcome"
            )
    elif decision["rationale"] is None or decision["decision_commit"] is None:
        errors.append(
            f"{card_id}: final decision requires rationale and decision_commit"
        )
    if decision["state"] == "inconclusive" and decision["selected_variant"] is not None:
        errors.append(f"{card_id}: inconclusive decision cannot select a variant")
    if "RES-01" not in card["requirements"] or "RES-02" not in card["requirements"]:
        errors.append(f"{card_id}: RES-01 and RES-02 are mandatory")

    variant_ids = [entry["id"] for entry in card["controls"] + card["candidates"]]
    if len(variant_ids) != len(set(variant_ids)):
        errors.append(f"{card_id}: duplicate variant IDs")

    for failure_id in card["failure_ids"]:
        if failure_id not in failure_ids:
            errors.append(f"{card_id}: unknown failure ID {failure_id}")
    for citation in card["literature"]:
        if citation["id"] not in literature_text:
            errors.append(
                f"{card_id}: literature ID {citation['id']} missing from matrix"
            )
        if citation["url"] not in literature_text:
            errors.append(
                f"{card_id}: literature URL {citation['url']} missing from matrix"
            )
    for name, parameter in card["hyperparameters"].items():
        if parameter["status"] != "hypothesis":
            errors.append(f"{card_id}: hyperparameter {name} is not marked hypothesis")

    joined = json.dumps(card, sort_keys=True).lower()
    forbidden = ["known answer table", "route by case", "legacy import"]
    for phrase in forbidden:
        if phrase in joined:
            errors.append(
                f"{card_id}: forbidden case-specific/retired coupling phrase {phrase!r}"
            )

    if card_id == "EXP-DISC-001":
        invariants = " ".join(card["safety_invariants"]).lower()
        if "n_independent(t)" not in invariants:
            errors.append(f"{card_id}: missing non-starving independent-lane invariant")
        if not any(variant["id"] == "D0-IID-ALL" for variant in card["controls"]):
            errors.append(f"{card_id}: missing permanent IID all-launch control")
    return errors


def validate_envelope(envelope: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if envelope.get("schema_version") != "1.0.0":
        errors.append("envelope: unsupported schema_version")
    if envelope.get("status") != "research_staging_not_product_scope":
        errors.append("envelope: must not claim to be the final product scope")
    strata = {entry.get("id") for entry in envelope.get("critical_strata", [])}
    if strata != {f"S{i}" for i in range(1, 9)}:
        errors.append("envelope: critical strata must be exactly S1-S8")
    unknown = {entry.get("id") for entry in envelope.get("unknown_levels", [])}
    if unknown != {f"U{i}" for i in range(1, 6)}:
        errors.append("envelope: unknown levels must be exactly U1-U5")
    truth = {
        entry.get("id"): entry.get("eligible_for_p_full")
        for entry in envelope.get("truth_levels", [])
    }
    if truth.get("reference_only") is not False:
        errors.append("envelope: reference_only truth must be excluded from P_full")
    if not envelope.get("metamorphic_transforms"):
        errors.append("envelope: metamorphic transforms are required")
    return errors


def failure_ids_from_markdown(text: str) -> set[str]:
    return set(re.findall(r"\| (F(?:[0-9]|1[0-8])) \|", text))


def validate_evidence_links(ledger: dict[str, Any], evidence_text: str) -> list[str]:
    """Keep the append-only evidence and negative-result registers referentially sound."""

    errors: list[str] = []
    evidence_ids = re.findall(r"\| (EVID-[0-9]{2,}) \|", evidence_text)
    for evidence_id, count in Counter(evidence_ids).items():
        if count != 1:
            errors.append(f"evidence register: {evidence_id} occurs {count} times")
    known = set(evidence_ids)
    marker = "## Reproduced current evidence"
    if marker not in evidence_text:
        errors.append("evidence register: reproduced evidence section is missing")
        reproduced: set[str] = set()
    else:
        reproduced = set(
            re.findall(r"\| (EVID-[0-9]{2,}) \|", evidence_text.split(marker, 1)[1])
        )

    negative_ids = [entry["id"] for entry in ledger["entries"]]
    for negative_id, count in Counter(negative_ids).items():
        if count != 1:
            errors.append(f"negative-result ledger: {negative_id} occurs {count} times")
    for entry in ledger["entries"]:
        for evidence_id in entry["source_evidence_ids"]:
            if evidence_id not in known:
                errors.append(
                    f"{entry['id']}: source evidence {evidence_id} is absent from the register"
                )
            if (
                entry["evidence_state"] == "reproduced"
                and evidence_id not in reproduced
            ):
                errors.append(
                    f"{entry['id']}: reproduced result cites non-reproduced {evidence_id}"
                )
    return errors


def main() -> int:
    errors: list[str] = []
    schema_paths = sorted(SCHEMA_DIR.glob("*.schema.json"))
    if not schema_paths:
        errors.append("no schemas found")
    schemas = {path.name: load_json(path) for path in schema_paths}
    for name, schema in schemas.items():
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name}: expected JSON Schema 2020-12")
        if schema.get("type") != "object":
            errors.append(f"{name}: top-level type must be object")

    card_schema = schemas["experiment-card.schema.json"]
    literature_text = LITERATURE.read_text(encoding="utf-8")
    failure_text = FAILURES.read_text(encoding="utf-8")
    known_failures = failure_ids_from_markdown(failure_text)
    card_paths = sorted(CARD_DIR.glob("EXP-*.json"))
    required_m0_cards = {"EXP-COMP-001", "EXP-LOCAL-001", "EXP-DISC-001"}
    missing_m0_cards = required_m0_cards - {path.stem for path in card_paths}
    if missing_m0_cards:
        errors.append(
            "required M0 preregistrations are missing: "
            + ", ".join(sorted(missing_m0_cards))
        )
    for path in card_paths:
        card = load_json(path)
        errors.extend(
            f"{path}: {error}" for error in validate_instance(card, card_schema)
        )
        errors.extend(validate_card_semantics(card, literature_text, known_failures))

    ledger = load_json(LEDGER)
    ledger_schema = schemas["negative-result-ledger.schema.json"]
    errors.extend(
        f"{LEDGER}: {error}" for error in validate_instance(ledger, ledger_schema)
    )
    evidence_text = EVIDENCE.read_text(encoding="utf-8")
    errors.extend(validate_evidence_links(ledger, evidence_text))
    envelope = load_json(ENVELOPE)
    errors.extend(validate_envelope(envelope))

    example_pairs = [
        (
            EXAMPLE_DIR / "run-manifest.example.json",
            schemas["run-manifest.schema.json"],
        ),
        (
            EXAMPLE_DIR / "benchmark-manifest.example.json",
            schemas["benchmark-manifest.schema.json"],
        ),
    ]
    for path, schema in example_pairs:
        instance = load_json(path)
        errors.extend(
            f"{path}: {error}" for error in validate_instance(instance, schema)
        )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"validated {len(schema_paths)} schemas, {len(card_paths)} experiment cards, "
        f"{len(ledger['entries'])} negative results, {len(example_pairs)} examples and "
        f"envelope {envelope['envelope_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
