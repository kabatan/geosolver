#!/usr/bin/env python3
"""Reuse provisional numeric grades only for identical, source-verified cases.

This CPU-only helper never changes its packet, private key, or grade inputs. It
writes a final-ID grade file for uniquely matched provisional grades and a new
blind packet containing every final case that still needs a grade.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from prepare_blind_numeric import GRADING_INSTRUCTIONS, PacketError, _canonical_sha256


PACKET_SCHEMA = "blind-numeric-packet-v1"
VALID_CAPS = {32768, 81920}
PRIVATE_GRADE_FIELDS = {
    "condition",
    "source_condition",
    "job_id",
    "source_file",
    "source_file_sha256",
    "source_dir",
    "provisional_dir",
    "provisional_case_id",
}
CONDITION_LABEL_RE = re.compile(r"(?<![A-Za-z0-9_])(base|code128|numeric128|opd32)(?![A-Za-z0-9_])")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise PacketError(f"cannot read required file {path}: {exc}") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PacketError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except PacketError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise PacketError(f"cannot read JSON {path}: {exc}") from exc


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PacketError(f"{label} must be a JSON object")
    return value


def _validate_case(case: Any, label: str) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise PacketError(f"{label} contains a non-object case")
    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise PacketError(f"{label} contains a case without a valid case_id")
    for field, expected_type in (
        ("messages", list),
        ("expected_numeric", str),
        ("raw_response", str),
        ("final_text", str),
    ):
        if not isinstance(case.get(field), expected_type):
            raise PacketError(f"{label}/{case_id}: missing or invalid {field}")
    if case.get("selected_cap") not in VALID_CAPS:
        raise PacketError(f"{label}/{case_id}: unsupported selected_cap")
    if not isinstance(case.get("finish_reason"), str) or not case["finish_reason"]:
        raise PacketError(f"{label}/{case_id}: missing finish_reason")
    return case


def _validate_private_entry(entry: Any, label: str) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise PacketError(f"{label}: private-key entry must be an object")
    source_file = entry.get("source_file")
    source_hash = entry.get("source_file_sha256")
    if not isinstance(source_file, str) or not source_file:
        raise PacketError(f"{label}: private-key source_file is missing")
    source_path = Path(source_file)
    if not source_path.is_absolute() or str(source_path.resolve()) != source_file:
        raise PacketError(f"{label}: private-key source_file must be a canonical absolute path")
    if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        raise PacketError(f"{label}: private-key source_file_sha256 is malformed")
    actual_hash = _sha256_file(source_path)
    if actual_hash != source_hash:
        raise PacketError(f"{label}: source_file hash differs from private key")
    return entry


def _load_packet_dir(packet_dir: Path, *, provisional: bool) -> dict[str, Any]:
    packet_dir = packet_dir.resolve()
    grader_dir = packet_dir / "grader"
    packet_path = grader_dir / "blind_numeric_packet.json"
    manifest_path = grader_dir / "packet-manifest.json"
    key_path = packet_dir / "private-key.json"
    instructions_path = grader_dir / "GRADING_INSTRUCTIONS.md"
    if not packet_path.is_file():
        raise PacketError(f"missing blind numeric packet: {packet_path}")
    try:
        packet_bytes = packet_path.read_bytes()
    except OSError as exc:
        raise PacketError(f"cannot read blind numeric packet {packet_path}: {exc}") from exc
    packet = _require_dict(_read_json(packet_path), str(packet_path))
    manifest = _require_dict(_read_json(manifest_path), str(manifest_path))
    key = _require_dict(_read_json(key_path), str(key_path))
    if packet.get("schema") != PACKET_SCHEMA:
        raise PacketError(f"{packet_path}: expected schema {PACKET_SCHEMA!r}")
    expected_key_schema = (
        "provisional-blind-numeric-private-key-v1"
        if provisional
        else "blind-numeric-private-key-v1"
    )
    if key.get("schema") != expected_key_schema:
        raise PacketError(f"{key_path}: unsupported private-key schema")
    expected_manifest_schema = (
        "provisional-blind-numeric-manifest-v1"
        if provisional
        else "blind-numeric-packet-manifest-v1"
    )
    if manifest.get("schema") != expected_manifest_schema:
        raise PacketError(f"{manifest_path}: unsupported packet manifest schema")
    if not instructions_path.is_file():
        raise PacketError(f"missing grading instructions: {instructions_path}")
    cases_value = packet.get("cases")
    if not isinstance(cases_value, list):
        raise PacketError(f"{packet_path}: cases must be an array")
    cases: dict[str, dict[str, Any]] = {}
    for raw_case in cases_value:
        case = _validate_case(raw_case, str(packet_path))
        case_id = case["case_id"]
        if case_id in cases:
            raise PacketError(f"{packet_path}: duplicate case_id {case_id}")
        cases[case_id] = case

    packet_sha = _sha256_bytes(packet_bytes)
    manifest_sha = manifest.get("packet_sha256")
    if manifest_sha != packet_sha:
        raise PacketError(f"{manifest_path}: packet hash mismatch")
    if manifest.get("case_count") != len(cases):
        raise PacketError(f"{manifest_path}: case_count mismatch")
    case_hashes = manifest.get("case_sha256")
    if not isinstance(case_hashes, dict) or set(case_hashes) != set(cases):
        raise PacketError(f"{manifest_path}: case hash index differs from packet case IDs")
    for case_id, case in cases.items():
        if case_hashes.get(case_id) != _canonical_sha256(case):
            raise PacketError(f"{manifest_path}: case hash mismatch for {case_id}")

    private_cases = key.get("cases")
    if not isinstance(private_cases, dict) or set(private_cases) != set(cases):
        raise PacketError(f"{key_path}: private-key case IDs differ from packet case IDs")
    for case_id, entry in private_cases.items():
        _validate_private_entry(entry, f"{key_path}/{case_id}")

    return {
        "dir": packet_dir,
        "packet_path": packet_path,
        "packet_sha256": packet_sha,
        "manifest_path": manifest_path,
        "manifest_sha256": _sha256_file(manifest_path),
        "key_path": key_path,
        "key_sha256": _sha256_file(key_path),
        "instructions_path": instructions_path,
        "instructions_sha256": _sha256_file(instructions_path),
        "cases": cases,
        "private_cases": private_cases,
        "provisional": provisional,
    }


def _load_grades(provisional: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], Any, Path, str]:
    grade_path = provisional["dir"] / "grader" / "numeric-math-grades.json"
    document = _require_dict(_read_json(grade_path), str(grade_path))
    schema = document.get("schema")
    if schema is not None and not isinstance(schema, str):
        raise PacketError(f"{grade_path}: schema must be a string when present")
    rows = document.get("cases")
    if isinstance(rows, list):
        row_items = [(None, row) for row in rows]
    elif isinstance(rows, dict):
        row_items = list(rows.items())
    else:
        raise PacketError(f"{grade_path}: cases must be an array or object keyed by case_id")

    packet_ids = set(provisional["cases"])
    grades: dict[str, dict[str, Any]] = {}
    for map_key, raw_row in row_items:
        if not isinstance(raw_row, dict):
            raise PacketError(f"{grade_path}: a grade row is not an object")
        row = dict(raw_row)
        case_id = row.get("case_id", map_key)
        if not isinstance(case_id, str) or not case_id:
            raise PacketError(f"{grade_path}: a grade row has no valid case_id")
        if map_key is not None and row.get("case_id", map_key) != map_key:
            raise PacketError(f"{grade_path}: grade case_id disagrees with its cases key")
        if case_id not in packet_ids:
            raise PacketError(f"{grade_path}: unknown grade case_id {case_id}")
        if case_id in grades:
            raise PacketError(f"{grade_path}: duplicate grade for case_id {case_id}")
        row["case_id"] = case_id
        grade_fields = set(row) - PRIVATE_GRADE_FIELDS - {"case_id"}
        if not grade_fields:
            raise PacketError(f"{grade_path}: empty grade for case_id {case_id}")
        grades[case_id] = row
    return grades, schema, grade_path, _sha256_file(grade_path)


def _load_adjudications(path: Path | None, known_case_ids: set[str]) -> tuple[dict[str, dict[str, Any]], str | None]:
    if path is None:
        return {}, None
    document = _require_dict(_read_json(path), str(path))
    rows = document.get("cases")
    if not isinstance(rows, list):
        raise PacketError(f"{path}: adjudications.cases must be an array")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise PacketError(f"{path}: each adjudication must be an object")
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise PacketError(f"{path}: adjudication has no valid case_id")
        if case_id not in known_case_ids:
            raise PacketError(f"{path}: unknown provisional case_id {case_id}")
        if case_id in result:
            raise PacketError(f"{path}: duplicate adjudication for case_id {case_id}")
        overrides = {field: value for field, value in row.items() if field != "case_id"}
        if not overrides:
            raise PacketError(f"{path}: adjudication for {case_id} has no override fields")
        protected = PRIVATE_GRADE_FIELDS | {"case_id"}
        forbidden = sorted(set(overrides) & protected)
        if forbidden:
            raise PacketError(f"{path}: adjudication for {case_id} attempts to override protected fields {forbidden}")
        result[case_id] = overrides
    return result, _sha256_file(path)


def _same_gradeable_case(provisional_case: dict[str, Any], final_case: dict[str, Any]) -> tuple[bool, str | None]:
    if provisional_case.get("selected_cap") != final_case.get("selected_cap"):
        return False, "selected_cap_mismatch"
    for field in ("expected_numeric", "messages", "raw_response", "final_text", "finish_reason"):
        if provisional_case.get(field) != final_case.get(field):
            return False, f"{field}_mismatch"
    return True, None


def _contains_condition_label(value: Any) -> bool:
    if isinstance(value, str):
        return CONDITION_LABEL_RE.search(value) is not None
    if isinstance(value, dict):
        return any(_contains_condition_label(k) or _contains_condition_label(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_condition_label(item) for item in value)
    return False


def reuse_grades(
    final_packet_dir: Path,
    provisional_dirs: list[Path],
    out_dir: Path,
    adjudications_path: Path | None = None,
) -> dict[str, Any]:
    """Create a final-ID reused-grade file and a packet for all remaining cases."""
    if not provisional_dirs:
        raise PacketError("at least one --provisional-dir is required")
    final = _load_packet_dir(final_packet_dir, provisional=False)
    provisionals: list[dict[str, Any]] = []
    seen_dirs: set[Path] = set()
    for path in provisional_dirs:
        resolved = path.resolve()
        if resolved in seen_dirs:
            raise PacketError(f"duplicate provisional directory: {resolved}")
        seen_dirs.add(resolved)
        item = _load_packet_dir(resolved, provisional=True)
        grades, grade_schema, grade_path, grade_sha = _load_grades(item)
        item["grades"] = grades
        item["grade_schema"] = grade_schema
        item["grade_path"] = grade_path
        item["grade_sha256"] = grade_sha
        provisionals.append(item)

    schemas = {item["grade_schema"] for item in provisionals}
    if len(schemas) > 1:
        raise PacketError("provisional numeric-math-grades.json schemas differ")
    grade_schema = next(iter(schemas)) if schemas else None

    provisional_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    provisional_by_path: dict[str, list[dict[str, Any]]] = {}
    provisional_by_hash: dict[str, list[dict[str, Any]]] = {}
    provisional_ids: dict[str, dict[str, Any]] = {}
    for item in provisionals:
        for provisional_case_id, case in item["cases"].items():
            if provisional_case_id in provisional_ids:
                raise PacketError(f"duplicate provisional case_id across inputs: {provisional_case_id}")
            entry = item["private_cases"][provisional_case_id]
            candidate = {
                "case_id": provisional_case_id,
                "case": case,
                "private": entry,
                "grade": item["grades"].get(provisional_case_id),
                "input": item,
            }
            identity = (entry["source_file"], entry["source_file_sha256"])
            provisional_index.setdefault(identity, []).append(candidate)
            provisional_by_path.setdefault(entry["source_file"], []).append(candidate)
            provisional_by_hash.setdefault(entry["source_file_sha256"], []).append(candidate)
            provisional_ids[provisional_case_id] = candidate

    adjudications, adjudications_sha = _load_adjudications(
        adjudications_path, set(provisional_ids)
    )
    adjudication_applied: dict[str, list[str]] = {}
    for provisional_case_id, overrides in adjudications.items():
        candidate = provisional_ids[provisional_case_id]
        if candidate["grade"] is None:
            raise PacketError(
                f"adjudication for {provisional_case_id} cannot be applied because its provisional grade is missing"
            )
        grade = dict(candidate["grade"])
        grade.update(overrides)
        candidate["grade"] = grade
        adjudication_applied[provisional_case_id] = sorted(overrides)

    final_key = final["private_cases"]
    reused_rows: list[dict[str, Any]] = []
    remaining_cases: list[dict[str, Any]] = []
    reused_provenance: list[dict[str, Any]] = []
    remaining_provenance: list[dict[str, Any]] = []

    for final_case_id, final_case in final["cases"].items():
        final_private = final_key[final_case_id]
        identity = (final_private["source_file"], final_private["source_file_sha256"])
        candidates = provisional_index.get(identity, [])
        reason: str | None = None
        selected: dict[str, Any] | None = None
        if len(candidates) > 1:
            reason = "duplicate_provisional_source_matches"
        elif len(candidates) == 1:
            candidate = candidates[0]
            same, mismatch = _same_gradeable_case(candidate["case"], final_case)
            if not same:
                reason = mismatch
            elif candidate["grade"] is None:
                reason = "provisional_grade_missing"
            else:
                selected = candidate
        else:
            same_path = provisional_by_path.get(final_private["source_file"], [])
            same_hash = provisional_by_hash.get(final_private["source_file_sha256"], [])
            if same_path:
                reason = "source_file_sha256_mismatch"
            elif same_hash:
                reason = "source_file_path_mismatch"
            else:
                reason = "no_matching_provisional_source"

        if selected is not None:
            grade_row = dict(selected["grade"])
            grade_row.pop("case_id", None)
            grade_row = {key: value for key, value in grade_row.items() if key not in PRIVATE_GRADE_FIELDS}
            grade_row["case_id"] = final_case_id
            reused_rows.append(grade_row)
            reused_provenance.append(
                {
                    "final_case_id": final_case_id,
                    "provisional_case_id": selected["case_id"],
                    "condition": final_private.get("condition"),
                    "job_id": final_private.get("job_id"),
                    "source_file": final_private["source_file"],
                    "source_file_sha256": final_private["source_file_sha256"],
                    "provisional_dir": str(selected["input"]["dir"]),
                    "grade_fields": sorted(key for key in grade_row if key != "case_id"),
                    "adjudication_applied": selected["case_id"] in adjudication_applied,
                    "adjudication_fields": adjudication_applied.get(selected["case_id"], []),
                }
            )
        else:
            remaining_cases.append(final_case)
            remaining_provenance.append(
                {
                    "final_case_id": final_case_id,
                    "condition": final_private.get("condition"),
                    "job_id": final_private.get("job_id"),
                    "source_file": final_private["source_file"],
                    "source_file_sha256": final_private["source_file_sha256"],
                    "reason": reason,
                    "provisional_case_ids": [candidate["case_id"] for candidate in candidates],
                    "provisional_grade_missing": bool(
                        len(candidates) == 1 and candidates[0]["grade"] is None
                    ),
                }
            )

    reused_document: dict[str, Any] = {"cases": reused_rows}
    if isinstance(grade_schema, str):
        reused_document["schema"] = grade_schema
    if _contains_condition_label(reused_document):
        raise PacketError("reused-grades.json would expose a condition label")

    remaining_packet = {"schema": PACKET_SCHEMA, "cases": remaining_cases}
    remaining_bytes = (
        json.dumps(remaining_packet, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    remaining_case_hashes = {
        case["case_id"]: _canonical_sha256(case) for case in remaining_cases
    }
    remaining_manifest = {
        "schema": "blind-numeric-packet-manifest-v1",
        "packet_file": "blind_numeric_packet.json",
        "packet_sha256": _sha256_bytes(remaining_bytes),
        "case_count": len(remaining_cases),
        "case_sha256": remaining_case_hashes,
    }

    output = out_dir.resolve()
    if output.exists():
        raise PacketError(f"output directory already exists: {output}")
    input_dirs = [final["dir"], *(item["dir"] for item in provisionals)]
    if final["dir"] in seen_dirs:
        raise PacketError("final packet directory cannot also be a provisional input")
    if adjudications_path is not None:
        adjudication_resolved = adjudications_path.resolve()
        if any(parent == adjudication_resolved or parent in adjudication_resolved.parents for parent in input_dirs):
            raise PacketError("adjudications file must not be inside an input packet directory")
    if any(parent == output or parent in output.parents for parent in input_dirs):
        raise PacketError("output must be outside every input packet directory")
    if any(output == parent or output in parent.parents for parent in input_dirs):
        raise PacketError("output must not contain any input packet directory")

    output.mkdir(parents=True)
    remaining_grader_dir = output / "remaining" / "grader"
    remaining_grader_dir.mkdir(parents=True)
    (output / "reused-grades.json").write_text(
        json.dumps(reused_document, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (remaining_grader_dir / "blind_numeric_packet.json").write_bytes(remaining_bytes)
    (remaining_grader_dir / "packet-manifest.json").write_text(
        json.dumps(remaining_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(final["instructions_path"], remaining_grader_dir / "GRADING_INSTRUCTIONS.md")

    researcher_dir = output / "researcher-only"
    researcher_dir.mkdir()
    reason_counts = Counter(row["reason"] for row in remaining_provenance)
    coverage = {
        "schema": "provisional-numeric-grade-reuse-coverage-v1",
        "final_packet_cases": len(final["cases"]),
        "reused_grade_cases": len(reused_rows),
        "remaining_grade_cases": len(remaining_cases),
        "remaining_by_reason": dict(sorted(reason_counts.items())),
        "provisional_case_count": len(provisional_ids),
        "provisional_grade_count": sum(len(item["grades"]) for item in provisionals),
        "provisional_missing_grade_count": sum(
            len(item["cases"]) - len(item["grades"]) for item in provisionals
        ),
        "adjudication_cases_applied": len(adjudication_applied),
        "provisional_inputs": [
            {
                "directory": str(item["dir"]),
                "packet_cases": len(item["cases"]),
                "graded_cases": len(item["grades"]),
                "missing_grade_cases": len(item["cases"]) - len(item["grades"]),
            }
            for item in provisionals
        ],
    }
    provenance = {
        "schema": "provisional-numeric-grade-reuse-provenance-v1",
        "final_packet": {
            "directory": str(final["dir"]),
            "packet_file": str(final["packet_path"]),
            "packet_sha256": final["packet_sha256"],
            "manifest_file": str(final["manifest_path"]),
            "manifest_sha256": final["manifest_sha256"],
            "private_key_file": str(final["key_path"]),
            "private_key_sha256": final["key_sha256"],
        },
        "provisional_inputs": [
            {
                "directory": str(item["dir"]),
                "packet_file": str(item["packet_path"]),
                "packet_sha256": item["packet_sha256"],
                "manifest_file": str(item["manifest_path"]),
                "manifest_sha256": item["manifest_sha256"],
                "private_key_file": str(item["key_path"]),
                "private_key_sha256": item["key_sha256"],
                "grades_file": str(item["grade_path"]),
                "grades_sha256": item["grade_sha256"],
                "grading_instructions_sha256": item["instructions_sha256"],
                "condition": _read_json(item["key_path"]).get("source_condition"),
            }
            for item in provisionals
        ],
        "adjudications_file": None if adjudications_path is None else str(adjudications_path.resolve()),
        "adjudications_sha256": adjudications_sha,
        "matching_rule": (
            "Reuse requires exactly one provisional candidate with the identical canonical absolute source_file and source_file_sha256, "
            "verified against source bytes, plus matching selected_cap, finish_reason, expected_numeric, messages, raw_response, and final_text."
        ),
        "reused_cases": reused_provenance,
        "remaining_cases": remaining_provenance,
        "output_hashes": {
            "reused_grades_sha256": _sha256_file(output / "reused-grades.json"),
            "remaining_packet_sha256": _sha256_file(remaining_grader_dir / "blind_numeric_packet.json"),
            "remaining_instructions_sha256": _sha256_file(remaining_grader_dir / "GRADING_INSTRUCTIONS.md"),
        },
    }
    (researcher_dir / "coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (researcher_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "reused_cases": len(reused_rows),
        "remaining_cases": len(remaining_cases),
        "reused_grades_sha256": _sha256_file(output / "reused-grades.json"),
        "remaining_packet_sha256": _sha256_file(remaining_grader_dir / "blind_numeric_packet.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-packet-dir", type=Path, required=True, help="completed prepare_blind_numeric.py output directory")
    parser.add_argument(
        "--provisional-dir",
        type=Path,
        action="append",
        nargs="+",
        required=True,
        help="provisional packet directory; repeat the option or give several paths",
    )
    parser.add_argument("--adjudications", type=Path, help="optional researcher-only JSON overrides keyed by provisional case_id")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    provisional_dirs = [path for group in args.provisional_dir for path in group]
    try:
        result = reuse_grades(
            args.final_packet_dir,
            provisional_dirs,
            args.out,
            args.adjudications,
        )
    except PacketError as exc:
        parser.error(str(exc))
    # Keep stdout blind-safe: no IDs, condition labels, grade values, or answers.
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
