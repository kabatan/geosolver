#!/usr/bin/env python3
"""Validate and aggregate final numeric math reviews and answer-format audits.

This CPU-only helper reads blind packets, private keys, and grade JSON files. It
does not modify inputs. The output directory must not already exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
PACKET_SCHEMA = "blind-numeric-packet-v1"
NUMERIC_KEY_SCHEMA = "blind-numeric-private-key-v1"
ANSWER_SCHEMA = "blind-answer-audit-v1"
ANSWER_KEY_SCHEMA = "blind-answer-audit-private-key-v1"
CONDITIONS = {"base", "code128", "numeric128", "opd32"}
NUMERIC_STATES = {"correct", "incorrect", "unparsed"}
DERIVATION_STATES = {"valid", "invalid", "unparsed", "needs_review"}
PARSER_RELATIONS = {"agrees", "disagrees", "ambiguous"}
PRIVATE_FIELDS = {
    "condition", "source_condition", "job_id", "source_file", "source_file_sha256",
    "source_dir", "provisional_dir", "provisional_case_id",
}


class AggregateError(ValueError):
    """An input packet, grade file, or coverage relationship is invalid."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise AggregateError(f"cannot read {path}: {exc}") from exc


def _canonical_sha256(value: Any) -> str:
    data = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return _sha256_bytes(data)


def _read_json(path: Path) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AggregateError(f"{path}: duplicate JSON object key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except AggregateError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise AggregateError(f"cannot read JSON {path}: {exc}") from exc


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AggregateError(f"{label} must be a JSON object")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AggregateError(f"{label} must be a nonempty string")
    return value


def _case_rows(document: Any, label: str) -> list[dict[str, Any]]:
    root = _object(document, label)
    rows = root.get("cases")
    if isinstance(rows, list):
        result = []
        for row in rows:
            result.append(_object(row, f"{label}/cases row"))
        return result
    if isinstance(rows, dict):
        result = []
        for case_id, raw_row in rows.items():
            row = dict(_object(raw_row, f"{label}/cases/{case_id}"))
            row.setdefault("case_id", case_id)
            if row["case_id"] != case_id:
                raise AggregateError(f"{label}: grade case_id disagrees with its cases key")
            result.append(row)
        return result
    raise AggregateError(f"{label}: cases must be an array or an object keyed by case_id")


def _load_grade_files(paths: list[Path], known_ids: set[str], label: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    if not paths:
        raise AggregateError(f"at least one {label} file is required")
    grades: dict[str, dict[str, Any]] = {}
    inputs: list[dict[str, str]] = []
    for raw_path in paths:
        path = raw_path.resolve()
        if not path.is_file():
            raise AggregateError(f"missing {label} file: {path}")
        for row in _case_rows(_read_json(path), str(path)):
            case_id = _nonempty_string(row.get("case_id"), f"{path}: grade case_id")
            if case_id not in known_ids:
                raise AggregateError(f"{path}: unknown grade case_id {case_id}")
            if case_id in grades:
                raise AggregateError(f"duplicate {label} grade for case_id {case_id}")
            if len(set(row) - {"case_id"} - PRIVATE_FIELDS) == 0:
                raise AggregateError(f"{path}: empty grade for case_id {case_id}")
            grades[case_id] = row
        inputs.append({"path": str(path), "sha256": _sha256_file(path)})
    missing = sorted(known_ids - set(grades))
    if missing:
        raise AggregateError(f"{label} grade coverage is incomplete; missing case IDs: {missing}")
    return grades, inputs


def _packet_root(packet_dir: Path) -> tuple[Path, Path, Path, Path]:
    packet_dir = packet_dir.resolve()
    grader = packet_dir / "grader"
    return (
        packet_dir,
        grader / "blind_numeric_packet.json",
        grader / "packet-manifest.json",
        packet_dir / "private-key.json",
    )


def _validate_source_entry(entry: Any, label: str) -> dict[str, Any]:
    row = _object(entry, label)
    source = _nonempty_string(row.get("source_file"), f"{label}/source_file")
    digest = _nonempty_string(row.get("source_file_sha256"), f"{label}/source_file_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise AggregateError(f"{label}: malformed source_file_sha256")
    source_path = Path(source)
    if not source_path.is_absolute():
        raise AggregateError(f"{label}: source_file must be absolute")
    if str(source_path.resolve()) != source:
        raise AggregateError(f"{label}: source_file must be a canonical absolute path")
    actual = _sha256_file(source_path)
    if actual != digest:
        raise AggregateError(f"{label}: source file hash differs from private key")
    return row


def _load_numeric_packet(packet_dir: Path) -> dict[str, Any]:
    root, packet_path, manifest_path, key_path = _packet_root(packet_dir)
    instructions_path = packet_path.parent / "GRADING_INSTRUCTIONS.md"
    if not all(path.is_file() for path in (packet_path, manifest_path, key_path, instructions_path)):
        raise AggregateError(f"{root}: missing packet, packet manifest, or private key")
    packet_bytes = packet_path.read_bytes()
    packet = _object(_read_json(packet_path), str(packet_path))
    manifest = _object(_read_json(manifest_path), str(manifest_path))
    private_key = _object(_read_json(key_path), str(key_path))
    if packet.get("schema") != PACKET_SCHEMA:
        raise AggregateError(f"{packet_path}: unsupported numeric packet schema")
    if manifest.get("schema") != "blind-numeric-packet-manifest-v1":
        raise AggregateError(f"{manifest_path}: unsupported numeric manifest schema")
    if private_key.get("schema") != NUMERIC_KEY_SCHEMA:
        raise AggregateError(f"{key_path}: unsupported numeric private-key schema")
    cases_value = packet.get("cases")
    if not isinstance(cases_value, list):
        raise AggregateError(f"{packet_path}: cases must be an array")
    cases: dict[str, dict[str, Any]] = {}
    for raw_case in cases_value:
        case = _object(raw_case, str(packet_path))
        case_id = _nonempty_string(case.get("case_id"), f"{packet_path}: case_id")
        if case_id in cases:
            raise AggregateError(f"{packet_path}: duplicate case_id {case_id}")
        _nonempty_string(case.get("construction_id"), f"{packet_path}/{case_id}: construction_id")
        cases[case_id] = case
    if manifest.get("packet_file", "blind_numeric_packet.json") != "blind_numeric_packet.json":
        raise AggregateError(f"{manifest_path}: unexpected packet_file")
    if manifest.get("packet_sha256") != _sha256_bytes(packet_bytes):
        raise AggregateError(f"{manifest_path}: packet hash mismatch")
    if manifest.get("case_count") != len(cases):
        raise AggregateError(f"{manifest_path}: case_count mismatch")
    case_hashes = manifest.get("case_sha256")
    if not isinstance(case_hashes, dict) or set(case_hashes) != set(cases):
        raise AggregateError(f"{manifest_path}: case hash index differs from packet")
    for case_id, case in cases.items():
        if case_hashes.get(case_id) != _canonical_sha256(case):
            raise AggregateError(f"{manifest_path}: case hash mismatch for {case_id}")
    private_cases = private_key.get("cases")
    if not isinstance(private_cases, dict) or set(private_cases) != set(cases):
        raise AggregateError(f"{key_path}: private-key case IDs differ from packet")
    metadata: dict[str, dict[str, str]] = {}
    for case_id, raw_entry in private_cases.items():
        entry = _validate_source_entry(raw_entry, f"{key_path}/{case_id}")
        condition = _nonempty_string(entry.get("condition"), f"{key_path}/{case_id}: condition")
        job_id = _nonempty_string(entry.get("job_id"), f"{key_path}/{case_id}: job_id")
        source_id = cases[case_id]["construction_id"]
        metadata[case_id] = {
            "condition": condition,
            "job_id": job_id,
            "source_id": source_id,
            "source_file": entry["source_file"],
            "source_file_sha256": entry["source_file_sha256"],
        }
    return {
        "dir": root,
        "packet_path": packet_path,
        "manifest_path": manifest_path,
        "key_path": key_path,
        "cases": cases,
        "metadata": metadata,
        "inputs": [packet_path, manifest_path, instructions_path, key_path],
    }


def _load_answer_packet(audit_dir: Path) -> dict[str, Any]:
    audit_dir = audit_dir.resolve()
    grader = audit_dir / "grader"
    index_path = grader / "blind_answer_audit.json"
    manifest_path = grader / "packet-manifest.json"
    instructions_path = grader / "GRADING_INSTRUCTIONS.md"
    key_path = audit_dir / "private-key.json"
    if not all(path.is_file() for path in (index_path, manifest_path, key_path, instructions_path)):
        raise AggregateError(f"{audit_dir}: missing answer audit index, manifest, or private key")
    index_bytes = index_path.read_bytes()
    index = _object(_read_json(index_path), str(index_path))
    manifest = _object(_read_json(manifest_path), str(manifest_path))
    private_key = _object(_read_json(key_path), str(key_path))
    if index.get("schema") != ANSWER_SCHEMA:
        raise AggregateError(f"{index_path}: unsupported answer audit schema")
    if manifest.get("schema") != "blind-answer-audit-manifest-v1":
        raise AggregateError(f"{manifest_path}: unsupported answer audit manifest schema")
    if private_key.get("schema") != ANSWER_KEY_SCHEMA:
        raise AggregateError(f"{key_path}: unsupported answer audit private-key schema")
    if manifest.get("index_sha256") != _sha256_bytes(index_bytes):
        raise AggregateError(f"{manifest_path}: index hash mismatch")
    if manifest.get("index_file", index_path.name) != index_path.name:
        raise AggregateError(f"{manifest_path}: unexpected index_file")
    if manifest.get("grading_instructions_sha256") != _sha256_file(instructions_path):
        raise AggregateError(f"{manifest_path}: grading instructions hash mismatch")
    raw_cases = index.get("cases")
    if not isinstance(raw_cases, list):
        raise AggregateError(f"{index_path}: cases must be an array")
    cases: dict[str, dict[str, Any]] = {}
    for row in raw_cases:
        case = _object(row, f"{index_path}/cases row")
        case_id = _nonempty_string(case.get("case_id"), f"{index_path}: case_id")
        if case_id in cases:
            raise AggregateError(f"{index_path}: duplicate case_id {case_id}")
        case_file = _nonempty_string(case.get("case_file"), f"{index_path}/{case_id}: case_file")
        expected_relative = Path("cases") / f"{case_id}.json"
        if Path(case_file) != expected_relative:
            raise AggregateError(f"{index_path}/{case_id}: unexpected case_file path")
        cases[case_id] = case
    if len(cases) != 96 or manifest.get("case_count") != 96:
        raise AggregateError(f"{index_path}: expected exactly 96 answer audit cases")
    case_hashes = manifest.get("case_file_sha256")
    if not isinstance(case_hashes, dict) or set(case_hashes) != set(cases):
        raise AggregateError(f"{manifest_path}: case file hash index differs from packet")
    for case_id, case in cases.items():
        case_path = grader / "cases" / f"{case_id}.json"
        if _sha256_file(case_path) != case_hashes[case_id]:
            raise AggregateError(f"{manifest_path}: case file hash mismatch for {case_id}")
        if not isinstance(case.get("auto_numeric_status"), str):
            raise AggregateError(f"{index_path}/{case_id}: missing auto_numeric_status")
        if case.get("auto_numeric_correct") not in (True, False, None):
            raise AggregateError(f"{index_path}/{case_id}: invalid auto_numeric_correct")
    private_cases = private_key.get("cases")
    if not isinstance(private_cases, dict) or set(private_cases) != set(cases):
        raise AggregateError(f"{key_path}: private-key case IDs differ from packet")
    metadata: dict[str, dict[str, str]] = {}
    for case_id, raw_entry in private_cases.items():
        entry = _validate_source_entry(raw_entry, f"{key_path}/{case_id}")
        condition = _nonempty_string(entry.get("condition"), f"{key_path}/{case_id}: condition")
        job_id = _nonempty_string(entry.get("job_id"), f"{key_path}/{case_id}: job_id")
        metadata[case_id] = {
            "condition": condition,
            "job_id": job_id,
            "source_file": entry["source_file"],
            "source_file_sha256": entry["source_file_sha256"],
        }
    case_files = [grader / "cases" / f"{case_id}.json" for case_id in cases]
    return {
        "dir": audit_dir,
        "index_path": index_path,
        "manifest_path": manifest_path,
        "key_path": key_path,
        "cases": cases,
        "metadata": metadata,
        "inputs": [index_path, manifest_path, instructions_path, key_path, *case_files],
    }


def _load_job_groups(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    path = path.resolve()
    rows = _read_json(path)
    if not isinstance(rows, list):
        raise AggregateError(f"{path}: frozen evaluation jobs must be an array")
    by_job: dict[str, dict[str, str]] = {}
    source_group: dict[str, str] = {}
    for raw in rows:
        job = _object(raw, f"{path}: job row")
        job_id = _nonempty_string(job.get("id"), f"{path}: job id")
        source_id = _nonempty_string(job.get("source_id"), f"{path}/{job_id}: source_id")
        group = _nonempty_string(job.get("transfer_group", job.get("group")), f"{path}/{job_id}: transfer_group")
        if job_id in by_job:
            raise AggregateError(f"{path}: duplicate job id {job_id}")
        by_job[job_id] = {"source_id": source_id, "transfer_group": group}
        previous = source_group.setdefault(source_id, group)
        if previous != group:
            raise AggregateError(f"{path}: source {source_id} has multiple transfer groups")
    if len(by_job) != 24:
        raise AggregateError(f"{path}: expected the frozen 24-job evaluation set")
    return by_job, source_group


def _math_status(grade: dict[str, Any], case_id: str) -> str:
    statuses: list[str] = []
    for field in ("manual_numeric_status", "final_numeric_status", "numeric_status"):
        if field in grade:
            value = grade[field]
            if value not in NUMERIC_STATES:
                raise AggregateError(f"math grade {case_id}: invalid {field} {value!r}")
            statuses.append(value)
    for field in ("numeric_correct", "final_numeric_correct"):
        if field in grade:
            value = grade[field]
            if value not in (True, False, None):
                raise AggregateError(f"math grade {case_id}: invalid {field} {value!r}")
            statuses.append("correct" if value is True else "incorrect" if value is False else "unparsed")
    if not statuses:
        raise AggregateError(f"math grade {case_id}: missing final numeric correctness")
    if len(set(statuses)) != 1:
        raise AggregateError(f"math grade {case_id}: conflicting numeric correctness fields")
    return statuses[0]


def _math_grade_fields(grade: dict[str, Any], case_id: str) -> tuple[str, str, bool]:
    numeric = _math_status(grade, case_id)
    derivation = grade.get("derivation_status")
    if derivation not in DERIVATION_STATES:
        raise AggregateError(f"math grade {case_id}: invalid or missing derivation_status")
    core_values = [grade[field] for field in ("contains_valid_core_derivation", "valid_core_derivation", "valid_core") if field in grade]
    if not core_values or any(not isinstance(value, bool) for value in core_values):
        raise AggregateError(f"math grade {case_id}: missing boolean valid-core field")
    if len(set(core_values)) != 1:
        raise AggregateError(f"math grade {case_id}: conflicting valid-core fields")
    return numeric, derivation, core_values[0]


def _summary(rows: Iterable[dict[str, Any]], *, numeric: bool) -> dict[str, Any]:
    materialized = list(rows)
    if numeric:
        number_counts = Counter(row["numeric_status"] for row in materialized)
        derivation_counts = Counter(row["derivation_status"] for row in materialized)
        core_counts = Counter(str(row["valid_core"]).lower() for row in materialized)
        return {
            "cases": len(materialized),
            "numeric_status": {state: number_counts[state] for state in sorted(NUMERIC_STATES)},
            "derivation_status": {state: derivation_counts[state] for state in sorted(DERIVATION_STATES)},
            "contains_valid_core_derivation": {"true": core_counts["true"], "false": core_counts["false"]},
            "valid_core_and_numeric_correct": sum(
                row["valid_core"] and row["numeric_status"] == "correct" for row in materialized
            ),
        }
    primary = Counter(row["primary_status"] for row in materialized)
    manual = Counter(row["manual_status"] for row in materialized)
    parser_relation = Counter(row["parser_relation"] for row in materialized)
    return {
        "cases": len(materialized),
        "primary_auto_score": {state: primary[state] for state in sorted(NUMERIC_STATES)},
        "manual_format_sensitivity": {state: manual[state] for state in sorted(NUMERIC_STATES)},
        "parser_relation": {state: parser_relation[state] for state in sorted(PARSER_RELATIONS)},
        "newly_manual_correct": sum(
            row["manual_status"] == "correct" and row["primary_status"] != "correct"
            for row in materialized
        ),
    }


def _aggregate_numeric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_condition: dict[str, Any] = {}
    for condition in sorted({row["condition"] for row in rows}):
        selected = [row for row in rows if row["condition"] == condition]
        by_source: dict[str, Any] = {}
        by_job: dict[str, Any] = {}
        for source_id in sorted({row["source_id"] for row in selected}):
            source_rows = [row for row in selected if row["source_id"] == source_id]
            by_source[source_id] = _summary(source_rows, numeric=True)
            for row in source_rows:
                by_job[row["job_id"]] = _summary([row], numeric=True)
        by_condition[condition] = {
            **_summary(selected, numeric=True),
            "by_source_id": by_source,
            "by_job_id": dict(sorted(by_job.items())),
        }
    return {"overall": _summary(rows, numeric=True), "by_condition": by_condition}


def _auto_status(case: dict[str, Any], case_id: str) -> str:
    raw_correct = case.get("auto_numeric_correct")
    if raw_correct not in (True, False, None):
        raise AggregateError(f"answer audit case {case_id}: invalid auto_numeric_correct")
    status = case.get("auto_numeric_status")
    if status not in NUMERIC_STATES:
        raise AggregateError(f"answer audit case {case_id}: invalid auto_numeric_status {status!r}")
    from_bool = "correct" if raw_correct is True else "incorrect" if raw_correct is False else "unparsed"
    if from_bool != status:
        raise AggregateError(f"answer audit case {case_id}: automatic status fields disagree")
    return status


def _answer_aggregate(rows: list[dict[str, Any]], math_sources: set[tuple[str, str]]) -> dict[str, Any]:
    overall = _summary(rows, numeric=False)
    by_condition: dict[str, Any] = {}
    by_group: dict[str, Any] = {}
    by_condition_group: dict[str, dict[str, Any]] = {}
    for condition in sorted({row["condition"] for row in rows}):
        selected = [row for row in rows if row["condition"] == condition]
        groups = {}
        for group in sorted({row["transfer_group"] for row in selected}):
            grouped = [row for row in selected if row["transfer_group"] == group]
            groups[group] = _summary(grouped, numeric=False)
            by_group.setdefault(group, []).extend(grouped)
        by_condition[condition] = {**_summary(selected, numeric=False), "by_transfer_group": groups}
        by_condition_group[condition] = groups
    for group, grouped in list(by_group.items()):
        by_group[group] = _summary(grouped, numeric=False)

    additional = sorted(
        {
            (row["source_id"], row["condition"], row["job_id"])
            for row in rows
            if row["manual_status"] == "correct"
            and row["primary_status"] != "correct"
            and (row["condition"], row["job_id"]) not in math_sources
        }
    )
    return {
        "overall": overall,
        "by_condition": by_condition,
        "by_transfer_group": by_group,
        "by_condition_and_transfer_group": by_condition_group,
        "newly_manual_correct_without_math_packet": [
            {"source_id": source_id, "condition": condition, "job_id": job_id}
            for source_id, condition, job_id in additional
        ],
    }


def _check_snapshot(snapshot: dict[Path, str]) -> None:
    for path, expected in snapshot.items():
        if not path.is_file() or _sha256_file(path) != expected:
            raise AggregateError(f"input changed during aggregation: {path}")


def aggregate(
    numeric_packet_dir: Path,
    math_grade_paths: list[Path],
    answer_audit_dir: Path,
    answer_grade_path: Path,
    out_dir: Path,
    *,
    jobs_path: Path | None = None,
) -> dict[str, Any]:
    numeric = _load_numeric_packet(numeric_packet_dir)
    answer = _load_answer_packet(answer_audit_dir)
    jobs_path = (jobs_path or HERE / "eval-jobs-v2.json").resolve()
    jobs_by_id, _ = _load_job_groups(jobs_path)
    for case_id, meta in numeric["metadata"].items():
        if meta["condition"] not in CONDITIONS:
            raise AggregateError(f"numeric packet case {case_id}: unknown condition {meta['condition']}")
        job = jobs_by_id.get(meta["job_id"])
        if job is None or job["source_id"] != meta["source_id"]:
            raise AggregateError(f"numeric packet case {case_id}: unknown or mismatched job/source ID")
    numeric_identity = [(row["condition"], row["job_id"]) for row in numeric["metadata"].values()]
    if len(numeric_identity) != len(set(numeric_identity)):
        raise AggregateError("numeric packet contains duplicate condition/job IDs")
    answer_identity = [
        (meta["condition"], meta["job_id"]) for meta in answer["metadata"].values()
    ]
    expected_answer_identity = {
        (condition, job_id) for condition in CONDITIONS for job_id in jobs_by_id
    }
    if len(answer_identity) != len(set(answer_identity)):
        raise AggregateError("answer audit has duplicate condition/job IDs")
    if set(answer_identity) != expected_answer_identity:
        missing = sorted(expected_answer_identity - set(answer_identity))
        unknown = sorted(set(answer_identity) - expected_answer_identity)
        raise AggregateError(
            f"answer audit condition/job coverage differs from frozen jobs; missing={missing}, unknown={unknown}"
        )

    numeric_grades, numeric_grade_inputs = _load_grade_files(
        math_grade_paths, set(numeric["cases"]), "numeric math"
    )
    answer_grades, answer_grade_inputs = _load_grade_files(
        [answer_grade_path], set(answer["cases"]), "answer audit"
    )
    numeric_rows: list[dict[str, Any]] = []
    for case_id, grade in numeric_grades.items():
        numeric_status, derivation_status, valid_core = _math_grade_fields(grade, case_id)
        numeric_rows.append({**numeric["metadata"][case_id], "numeric_status": numeric_status,
                             "derivation_status": derivation_status, "valid_core": valid_core})

    math_by_identity: dict[tuple[str, str], dict[str, str]] = {}
    for row in numeric_rows:
        identity = (row["condition"], row["job_id"])
        if identity in math_by_identity:
            raise AggregateError(f"numeric packet has duplicate condition/job ID {identity}")
        math_by_identity[identity] = row
    answer_rows: list[dict[str, Any]] = []
    for case_id, grade in answer_grades.items():
        for field in ("parser_relation", "manual_format_corrected_status", "committed_answer", "reason"):
            if field not in grade:
                raise AggregateError(f"answer grade {case_id}: missing {field}")
        relation = grade["parser_relation"]
        manual_status = grade["manual_format_corrected_status"]
        if relation not in PARSER_RELATIONS:
            raise AggregateError(f"answer grade {case_id}: invalid parser_relation {relation!r}")
        if manual_status not in NUMERIC_STATES:
            raise AggregateError(f"answer grade {case_id}: invalid manual_format_corrected_status {manual_status!r}")
        if grade["committed_answer"] is not None and not isinstance(grade["committed_answer"], str):
            raise AggregateError(f"answer grade {case_id}: committed_answer must be a string or null")
        if not isinstance(grade["reason"], str):
            raise AggregateError(f"answer grade {case_id}: reason must be a string")
        meta = answer["metadata"][case_id]
        if meta["condition"] not in CONDITIONS:
            raise AggregateError(f"answer audit case {case_id}: unknown condition {meta['condition']}")
        job = jobs_by_id.get(meta["job_id"])
        if job is None:
            raise AggregateError(f"answer audit private key has unknown job_id {meta['job_id']}")
        math_row = math_by_identity.get((meta["condition"], meta["job_id"]))
        if math_row is not None and (
            math_row["source_file"] != meta["source_file"]
            or math_row["source_file_sha256"] != meta["source_file_sha256"]
        ):
            raise AggregateError(
                f"numeric and answer audit source hashes differ for {meta['condition']}/{meta['job_id']}"
            )
        answer_rows.append({
            "case_id": case_id,
            "condition": meta["condition"],
            "job_id": meta["job_id"],
            "source_id": job["source_id"],
            "transfer_group": job["transfer_group"],
            "primary_status": _auto_status(answer["cases"][case_id], case_id),
            "manual_status": manual_status,
            "parser_relation": relation,
        })

    math_sources = set(math_by_identity)
    result = {
        "schema": "review-results-aggregate-v1",
        "numeric_math": _aggregate_numeric(numeric_rows),
        "answer_audit": _answer_aggregate(answer_rows, math_sources),
        "coverage": {
            "numeric_math": {
                "packet_cases": len(numeric["cases"]),
                "graded_cases": len(numeric_grades),
                "missing_case_ids": [],
                "unknown_case_ids": [],
                "duplicate_case_ids": [],
            },
            "answer_audit": {
                "packet_cases": len(answer["cases"]),
                "graded_cases": len(answer_grades),
                "missing_case_ids": [],
                "unknown_case_ids": [],
                "duplicate_case_ids": [],
            },
        },
    }

    # Retain provenance hashes for selected original answer files referenced by both keys.
    source_artifacts = {}
    for metadata in [*numeric["metadata"].values(), *answer["metadata"].values()]:
        source_artifacts[metadata["source_file"]] = metadata["source_file_sha256"]

    input_paths = [
        *numeric["inputs"], *answer["inputs"], jobs_path,
        *(Path(row["path"]) for row in numeric_grade_inputs),
        *(Path(row["path"]) for row in answer_grade_inputs),
        *(Path(path) for path in source_artifacts),
    ]
    unique_inputs = list(dict.fromkeys(path.resolve() for path in input_paths))
    snapshot = {path: _sha256_file(path) for path in unique_inputs}
    for source_path, expected_sha in source_artifacts.items():
        if snapshot[Path(source_path).resolve()] != expected_sha:
            raise AggregateError(f"source artifact hash differs from private key: {source_path}")
    input_manifest = [{"path": str(path), "sha256": snapshot[path]} for path in unique_inputs]

    output = out_dir.resolve()
    if output.exists():
        raise AggregateError(f"output directory already exists: {output}")
    input_dirs = [numeric["dir"], answer["dir"]]
    if any(parent == output or parent in output.parents for parent in input_dirs):
        raise AggregateError("output must be outside both input packet directories")
    if any(output == parent or output in parent.parents for parent in input_dirs):
        raise AggregateError("output must not contain an input packet directory")
    _check_snapshot(snapshot)

    output.mkdir(parents=True, exist_ok=False)
    result_path = output / "aggregate.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema": "review-results-aggregate-manifest-v1",
        "inputs": input_manifest,
        "source_artifacts": [
            {"path": path, "sha256": digest} for path, digest in sorted(source_artifacts.items())
        ],
        "grade_files": {"numeric_math": numeric_grade_inputs, "answer_audit": answer_grade_inputs},
        "coverage": result["coverage"],
        "output_file": result_path.name,
        "output_sha256": _sha256_file(result_path),
        "input_unchanged_after_aggregation": True,
    }
    _check_snapshot(snapshot)
    (output / "aggregate-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"out": str(output), "case_count": result["numeric_math"]["overall"]["cases"],
            "answer_case_count": result["answer_audit"]["overall"]["cases"],
            "manifest_sha256": _sha256_file(output / "aggregate-manifest.json")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numeric-packet-dir", type=Path, required=True)
    parser.add_argument("--math-grades", type=Path, action="append", required=True,
                        help="numeric math grade JSON; repeat for reused and residual grades")
    parser.add_argument("--answer-audit-dir", type=Path, required=True)
    parser.add_argument("--answer-grades", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    try:
        result = aggregate(args.numeric_packet_dir, args.math_grades, args.answer_audit_dir,
                           args.answer_grades, args.out)
    except AggregateError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
