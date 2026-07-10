from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from geotarget import (
    ProtocolValidationError,
    canonical_hash,
    canonical_json,
    load_and_validate,
    parse_json,
    validate_document,
)

FIXTURES = Path(__file__).resolve().parents[2] / "schemas" / "fixtures"


def _load(path: Path) -> object:
    return parse_json(path.read_text(encoding="utf-8"))


def _replace_pointer(document: object, pointer: str, value: object) -> None:
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer.split("/")[1:]]
    if not tokens:
        raise AssertionError("fixture patches cannot replace the document root")
    current = document
    for token in tokens[:-1]:
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = cast(dict[str, object], current)[token]
        else:
            raise AssertionError(f"JSON pointer traversed scalar at {token!r}")
    final = tokens[-1]
    if isinstance(current, list):
        current[int(final)] = value
    elif isinstance(current, dict):
        cast(dict[str, object], current)[final] = value
    else:
        raise AssertionError("JSON pointer parent is scalar")


@pytest.mark.parametrize(
    "filename",
    [
        "checkpoint-paused-v1.json",
        "plugin-manifest-full-v1.json",
        "problem-open-world-v1.json",
        "solve-options-checkpoint-v1.json",
        "solve-result-combined-v1.json",
    ],
)
def test_valid_cross_language_fixture(filename: str) -> None:
    document, version = load_and_validate(FIXTURES / "valid" / filename)
    assert version.startswith("geotarget.")
    canonical = canonical_json(document)
    assert canonical_json(parse_json(canonical)) == canonical
    assert canonical_hash(document).startswith("sha256:")


def test_invalid_cross_language_fixture_mutations() -> None:
    manifest = _load(FIXTURES / "invalid" / "cases-v1.json")
    assert isinstance(manifest, dict)
    cases = manifest["cases"]
    assert isinstance(cases, list)
    for raw in cases:
        assert isinstance(raw, dict)
        document = deepcopy(_load(FIXTURES / cast(str, raw["base"])))
        patch = raw["patch"]
        assert isinstance(patch, list)
        for operation in patch:
            assert isinstance(operation, dict)
            assert operation["op"] == "replace"
            _replace_pointer(document, cast(str, operation["path"]), operation["value"])
        with pytest.raises(ProtocolValidationError, match=cast(str, raw["expected"])):
            validate_document(document)


def test_cross_language_fixture_hashes_are_frozen() -> None:
    manifest = _load(FIXTURES / "canonical-hashes-v1.json")
    assert isinstance(manifest, dict)
    assert manifest["canonicalization"] == "RFC 8785"
    fixtures = manifest["fixtures"]
    assert isinstance(fixtures, dict)
    for relative, expected in fixtures.items():
        document = _load(FIXTURES / relative)
        assert canonical_hash(document) == expected
