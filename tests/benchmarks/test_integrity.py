"""Benchmarks/test integrity contracts and numerical regressions."""

import json

from tests.paths import REPO_ROOT


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_active_corpus_has_neither_duplicate_identity_nor_duplicate_dsl():
    path = REPO_ROOT / "benchmarks/cases.jsonl"
    rows = list(map(json.loads, path.read_text(encoding="utf-8").splitlines()))
    identities = {row.get("dedupe_key", row["id"]) for row in rows}
    problems = set()
    for row in rows:
        dsl = {key: value for key, value in row["dsl"].items() if key != "id"}
        # Only ID and conjunct order are irrelevant to mathematical identity.
        dsl["conditions"] = sorted(dsl["conditions"], key=_encoded)
        problems.add(_encoded(dsl))
    assert len(rows) == len({row["id"] for row in rows}) == 323
    assert len(identities) == len(problems) == len(rows)
