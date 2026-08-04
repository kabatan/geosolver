#!/usr/bin/env python3
"""Strict, read-only integrity audit for the competition geometry DSL corpus.

This check deliberately sits outside the benchmark driver.  It validates the
JSON representation and its provenance before a solver run, so a successful
benchmark cannot hide a malformed or silently changed problem definition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from exact_scoring import exact_target_is_valid


ROOT = Path(__file__).resolve().parent
_ARBITRARY_GUARD_MARGIN = re.compile(r"(?<![\d.])0\.(?:01|001|1|05)(?![\d])")


class DuplicateKeyError(ValueError):
    pass


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line, object_pairs_hook=reject_duplicate_keys)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{lineno}: row is not an object")
        rows.append(value)
    return rows


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", type=Path, help="optional benchmark JSON to check for case coverage")
    args = ap.parse_args()

    errors: list[str] = []
    dsl_dir = ROOT / "dsl"
    paths = sorted(dsl_dir.glob("*.json"))
    cases: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            case = strict_json(path)
        except Exception as exc:  # pragma: no cover - exercised by corpus failures
            fail(errors, f"{path.name}: JSON: {exc}")
            continue
        stem = path.stem
        if stem in cases:
            fail(errors, f"duplicate DSL filename stem: {stem}")
        cases[stem] = case
        if case.get("id") != stem:
            fail(errors, f"{path.name}: id={case.get('id')!r} does not match filename stem")

        variables = case.get("variables")
        if not isinstance(variables, dict) or not isinstance(variables.get("names"), list):
            fail(errors, f"{path.name}: variables.names must be a list")
        else:
            names = variables["names"]
            if not all(isinstance(name, str) and name for name in names):
                fail(errors, f"{path.name}: variables.names contains a non-string/empty name")
            if len(names) != len(set(names)):
                fail(errors, f"{path.name}: duplicate variable name")
            if len(names) > 7:
                fail(errors, f"{path.name}: {len(names)} free variables (limit is 7)")

        construction = case.get("construction")
        if not isinstance(construction, list):
            fail(errors, f"{path.name}: construction must be a list")
        else:
            construction_names = []
            for i, item in enumerate(construction):
                if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("expr"), str):
                    fail(errors, f"{path.name}: construction[{i}] must contain string name/expr")
                else:
                    construction_names.append(item["name"])
            if len(construction_names) != len(set(construction_names)):
                fail(errors, f"{path.name}: duplicate construction name")

        constraints = case.get("constraints", [])
        if not isinstance(constraints, list):
            fail(errors, f"{path.name}: constraints must be a list")
        else:
            for i, item in enumerate(constraints):
                if not isinstance(item, dict) or not isinstance(item.get("def"), str) or "value" not in item:
                    fail(errors, f"{path.name}: constraints[{i}] must contain string def and value")

        guards = case.get("guards", [])
        if not isinstance(guards, list) or not all(isinstance(g, str) and g.strip() for g in guards):
            fail(errors, f"{path.name}: guards must be a list of non-empty strings")
        else:
            # These values were used in an earlier draft as numerical
            # tolerances.  They are not part of any source statement and
            # would silently remove valid configurations, so keep the final
            # corpus on exact strict inequalities instead.
            for guard in guards:
                if _ARBITRARY_GUARD_MARGIN.search(guard):
                    fail(errors, f"{path.name}: arbitrary guard margin in {guard!r}")
        if not isinstance(case.get("source_statement"), str) or not case["source_statement"].strip():
            fail(errors, f"{path.name}: missing source_statement")
        ledger = case.get("clause_ledger")
        if not isinstance(ledger, list) or not ledger:
            fail(errors, f"{path.name}: missing clause_ledger")
        else:
            for i, item in enumerate(ledger):
                if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip() for k in ("source", "dsl", "kind")):
                    fail(errors, f"{path.name}: clause_ledger[{i}] is incomplete")
        if "published_answer" in case or "expected_answer" in case or "post_process" in case:
            fail(errors, f"{path.name}: contest answer/presentation metadata leaked into DSL")

        # Let the production parser validate expression safety and the full IR
        # schema.  Import lazily so the script remains useful from this repo.
        try:
            from geosolver.ir import load_ir  # type: ignore
            load_ir(case)
        except Exception as exc:
            fail(errors, f"{path.name}: IR parser: {exc}")

    try:
        audit_rows = read_jsonl(ROOT / "manual_audit.jsonl")
        inventory_rows = read_jsonl(ROOT / "scope_inventory.jsonl")
        truth_rows = read_jsonl(ROOT / "exact_truth.jsonl")
    except Exception as exc:
        fail(errors, f"metadata JSONL: {exc}")
        audit_rows, inventory_rows, truth_rows = [], [], []

    truth_by_case = {row.get("case_id"): row for row in truth_rows}
    if len(truth_by_case) != len(truth_rows):
        fail(errors, "exact_truth.jsonl contains duplicate case_id rows")

    audit_by_path: dict[str, list[dict[str, Any]]] = {}
    for row in audit_rows:
        path = row.get("dsl_path")
        if path:
            audit_by_path.setdefault(path, []).append(row)

    inventory_paths: set[str] = set()
    ready_paths: set[str] = set()
    for row in inventory_rows:
        path = row.get("dsl_path")
        if path:
            inventory_paths.add(path)
        if row.get("scope_status") == "in_scope" and row.get("dsl_status") == "ready" and path:
            ready_paths.add(path)

    dsl_paths = {str(path.relative_to(ROOT)) for path in paths}
    if dsl_paths != ready_paths:
        fail(errors, f"DSL/inventory path mismatch: missing={sorted(ready_paths-dsl_paths)} extra={sorted(dsl_paths-ready_paths)}")

    for path in sorted(dsl_paths):
        case = cases.get(Path(path).stem)
        rows = audit_by_path.get(path, [])
        if case is None:
            continue
        if not rows:
            fail(errors, f"{path}: no manual_audit provenance row")
            continue
        source = case.get("source_statement")
        source_variants = {r.get("source_statement") for r in rows if isinstance(r.get("source_statement"), str)}
        if source not in source_variants:
            fail(errors, f"{path}: source_statement differs from audited source text")
        # dsl_source_statement is redundant audit metadata, but it must not
        # contradict the actual case.  This catches stale OCR tails and edits
        # made to only one copy of a statement.
        for row in rows:
            dsl_source = row.get("dsl_source_statement")
            if dsl_source and dsl_source != source:
                fail(errors, f"{path}: stale dsl_source_statement in audit row {row.get('problem_id')}")
        truth = truth_by_case.get(Path(path).stem)
        if truth is None:
            fail(errors, f"{path}: missing exact_truth provenance row")
        else:
            if truth.get("dsl_path") != path:
                fail(errors, f"{path}: exact_truth.dsl_path mismatch")
            expected_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
            if truth.get("source_statement_sha256") != expected_hash:
                fail(errors, f"{path}: exact_truth source hash mismatch")
            if truth.get("truth_status") not in {"verified", "unresolved", "not_executable"}:
                fail(errors, f"{path}: invalid exact_truth truth_status")
            exact = truth.get("exact_answer_set")
            if not isinstance(exact, list) or not all(isinstance(value, str) and value.strip() for value in exact):
                fail(errors, f"{path}: exact_truth.exact_answer_set must be a list of strings")
            if truth.get("truth_status") == "verified" and not exact:
                fail(errors, f"{path}: verified exact_truth row has an empty answer set")
            if truth.get("truth_status") == "verified" and not exact_target_is_valid(exact):
                fail(errors, f"{path}: verified exact_truth row contains an approximate or duplicate value")

    if {row.get("case_id") for row in truth_rows} != set(cases):
        fail(errors, "exact_truth/case mismatch")

    reference = {stem for stem, case in cases.items() if str(case.get("solver_coverage", "")).startswith("reference_only")}
    if len(paths) != 302:
        fail(errors, f"expected 302 DSL files, found {len(paths)}")
    if len(reference) != 17:
        fail(errors, f"expected 17 reference_only files, found {len(reference)}")
    if len(paths) - len(reference) != 285:
        fail(errors, f"expected 285 runnable files, found {len(paths)-len(reference)}")

    if args.benchmark:
        try:
            benchmark = strict_json(args.benchmark)
            rows = benchmark.get("results", [])
            ids = {r.get("case_id") for r in rows if isinstance(r, dict)}
            if benchmark.get("cases") != len(paths) or len(rows) != len(paths) or ids != set(cases):
                fail(errors, f"benchmark coverage mismatch: cases={benchmark.get('cases')} rows={len(rows)} ids={len(ids)}")
            if len({r.get("case_id") for r in rows}) != len(rows):
                fail(errors, "benchmark contains duplicate case IDs")
        except Exception as exc:
            fail(errors, f"benchmark: {exc}")

    summary = {
        "dsl_files": len(paths),
        "runnable_files": len(paths) - len(reference),
        "reference_only_files": len(reference),
        "audit_rows": len(audit_rows),
        "inventory_rows": len(inventory_rows),
        "inventory_ready_paths": len(ready_paths),
        "truth_rows": len(truth_rows),
        "truth_verified": sum(row.get("truth_status") == "verified" for row in truth_rows),
        "truth_unresolved": sum(row.get("truth_status") == "unresolved" for row in truth_rows),
        "variable_histogram": dict(sorted(Counter(len(c.get("variables", {}).get("names", [])) for c in cases.values()).items())),
        "errors": len(errors),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
