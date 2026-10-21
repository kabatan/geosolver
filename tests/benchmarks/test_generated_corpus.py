"""Check imported evaluation inputs without consuming their first solver run."""

import hashlib
import json
from collections import Counter

from benchmarks import research_runner
from tests.paths import REPO_ROOT

DATASET = REPO_ROOT / "benchmarks/generated-88"


def test_generated_corpus_is_valid_and_not_counted_as_natural():
    report = research_runner.validate_corpus(DATASET / "cases.jsonl")
    assert report["valid"], report["issues"]
    assert report["inventory_count"] == report["runnable_count"] == 88
    assert report["truth_verified_count"] == report["dsl_file_count"] == 88
    assert report["unique_natural_problem_count"] == 0
    assert report["generated_input_count"] == 88


def test_import_preserves_frozen_inputs_answers_and_family_structure():
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((DATASET / relative).read_bytes()).hexdigest() == expected, relative

    rows = [
        json.loads(line)
        for line in (DATASET / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    for row in rows:
        assert row.pop("problem_kind") == "generated"
    original = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    freeze = json.loads((DATASET / "freeze.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(original.encode()).hexdigest() == freeze["cases_sha256"]
    assert manifest["original_cases_sha256"] == freeze["cases_sha256"]

    proofs = json.loads((DATASET / "derivations.json").read_text(encoding="utf-8"))
    assert {row["id"] for row in rows} == {proof["id"] for proof in proofs}
    families = Counter(proof["family"] for proof in proofs)
    assert len(families) == 11 and set(families.values()) == {8}
    for family in families:
        assert {
            (p["parameter_index"], p["equivalent_form"]) for p in proofs if p["family"] == family
        } == {(index, form) for index in range(4) for form in range(2)}

    existing = [
        json.loads(line)
        for line in research_runner.DEFAULT_CASES.read_text(encoding="utf-8").splitlines()
    ]
    assert not {row["id"] for row in rows} & {row["id"] for row in existing}
