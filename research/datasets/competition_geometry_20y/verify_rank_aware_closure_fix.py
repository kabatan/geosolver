#!/usr/bin/env python3
"""Verify the frozen rank-aware closure runtime and benchmark artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "runtime_rank_aware_closure_fix_manifest.json"
EXPECTED_SIX = {
    "AIME-2009-I-05": "72",
    "AIME-2016-I-06": "10/3",
    "AIME-2022-II-11": "180",
    "HMMT-2006-FEB-GEO-03": "31",
    "HMMT-2013-FEB-GEO-05": "-1/8",
    "HMMT-2023-FEB-GEO-01": "189",
}
EXPECTED_CONTROL = {"AIME-2015-II-11": "18/5"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_hash(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise AssertionError(f"SHA256 mismatch for {path}: {actual} != {expected}")


def check_benchmark(path: Path, expected: dict[str, str]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["budget_sec"] == 180.0
    assert payload["jobs"] == 1
    assert payload["hard_timeout"] is True
    assert payload["cpu_affinity"] == [0]
    assert payload["one_core_enforced"] is True
    assert payload["runs"] == len(expected)
    assert payload["success_runs"] == len(expected)
    assert payload["correct_runs"] == len(expected)
    assert payload["no_solution_runs"] == 0
    assert payload["timeout_runs"] == 0
    assert payload["exception_runs"] == 0
    rows = {row["case_id"]: row for row in payload["results"]}
    assert set(rows) == set(expected)
    for case_id, exact_value in expected.items():
        row = rows[case_id]
        assert row["status"] == "success"
        assert row["expected_answer"] == [exact_value]
        assert row["solution_values"] == [exact_value]
        assert row["phasec"]["answer_values"] == [exact_value]
        assert row["answer_set_exact"] is True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    runtime_root = args.runtime_root or Path(manifest["runtime_root"])

    for entry in manifest["files"]:
        check_hash(runtime_root / entry["path"], entry["sha256"])
    for entry in manifest["dsl_inputs"]:
        check_hash(ROOT / entry["path"], entry["sha256"])
    for entry in manifest["benchmarks"]:
        check_hash(ROOT / entry["path"], entry["sha256"])
    check_hash(ROOT / manifest["patch"]["path"], manifest["patch"]["sha256"])

    check_benchmark(ROOT / manifest["benchmarks"][0]["path"], EXPECTED_SIX)
    check_benchmark(ROOT / manifest["benchmarks"][1]["path"], EXPECTED_CONTROL)
    print(
        json.dumps(
            {
                "runtime_root": str(runtime_root),
                "runtime_files_verified": len(manifest["files"]),
                "dsl_inputs_verified": len(manifest["dsl_inputs"]),
                "strict_exact_matches": "7/7",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
