"""Source-based deduplication, with no solver outcomes used in representative selection."""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from benchmarks.repairs.corpus97.records import CASES, digest, encoded, removed_rows, repaired_rows

ARCHIVE = CASES.parent / "repairs/dedup-20260830"


def _rows(path):
    return {row["id"]: row for row in map(json.loads, path.read_text().splitlines())}


def _mathematical_dsl(dsl):
    """Ignore only the case ID and the order of conjunctive conditions."""
    normalized = {key: value for key, value in dsl.items() if key != "id"}
    normalized["conditions"] = sorted(normalized["conditions"], key=encoded)
    return normalized


def test_six_duplicates_are_archived_with_unchanged_official_representatives():
    current = _rows(CASES)
    archived = _rows(ARCHIVE / "removed-cases.jsonl")
    ledger = json.loads((ARCHIVE / "ledger.json").read_text())
    assert len(archived) == len(ledger["pairs"]) == 6
    assert {pair["removed_id"] for pair in ledger["pairs"]} == set(archived)
    assert len({pair["retained_id"] for pair in ledger["pairs"]}) == 6
    assert len(current) == ledger["inventory_after"] == 323
    assert ledger["inventory_before"] == 329
    assert Counter(pair["dsl_comparison"] for pair in ledger["pairs"]) == {
        "identical_except_id": 4,
        "identical_except_id_and_condition_order": 2,
    }
    for pair in ledger["pairs"]:
        old, kept = archived[pair["removed_id"]], current[pair["retained_id"]]
        assert old["id"] not in current
        assert not (CASES.parent / old["dsl_path"]).exists()
        assert pair["dedupe_key"] == old["dedupe_key"] == kept["dedupe_key"]
        assert digest(old) == pair["removed_row_sha256"]
        assert digest(kept) == pair["retained_row_sha256"]
        assert (
            hashlib.sha256((CASES.parent / kept["dsl_path"]).read_bytes()).hexdigest()
            == (pair["retained_dsl_file_sha256"])
        )
        assert old["answer"] == kept["answer"]
        assert old["truth_status"] == kept["truth_status"] == "verified"
        assert _mathematical_dsl(old["dsl"]) == _mathematical_dsl(kept["dsl"])
        assert kept["id"].startswith(("HMMT-2011-FEB-ALGGEO-", "JMO-2019-PRE-", "JMO-2022-PRE-"))
        assert kept["source"].startswith(("https://hmmt-archive.", "https://www.imojp.org/"))


def test_active_corpus_has_neither_duplicate_identity_nor_duplicate_dsl():
    rows = _rows(CASES)
    identities = {row.get("dedupe_key", row["id"]) for row in rows.values()}
    problems = {encoded(_mathematical_dsl(row["dsl"])) for row in rows.values()}
    assert len(rows) == len(identities) == len(problems) == 323


def test_historical_witness_loader_reads_archived_alias():
    identifier = "HMMT-2011-collinear-circumcircle"
    historical = repaired_rows(include_removed=True)
    assert historical[identifier] == removed_rows()[identifier]
    assert identifier not in repaired_rows()
    assert not (CASES.parent / f"dsl/{identifier}.json").exists()
