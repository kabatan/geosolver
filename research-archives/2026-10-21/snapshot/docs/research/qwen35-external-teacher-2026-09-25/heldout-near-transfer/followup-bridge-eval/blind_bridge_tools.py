#!/usr/bin/env python3
"""Build blind bridge packets, freeze blind grades, and join frozen scores.

This utility deliberately has no model-inference code.  Condition labels are
kept in a separate private vault until blind grades have been frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONDITIONS = (
    "base",
    "rotation-1-treatment",
    "rotation-1-control",
    "rotation-2-treatment",
    "rotation-2-control",
    "rotation-3-treatment",
    "rotation-3-control",
)
ROTATION_CONDITIONS = {
    "rotation-1": ("rotation-1-treatment", "rotation-1-control"),
    "rotation-2": ("rotation-2-treatment", "rotation-2-control"),
    "rotation-3": ("rotation-3-treatment", "rotation-3-control"),
}
# Rotation numbering follows the frozen source-ID order used for this bridge.
ROTATION_OMITTED_ID = {
    "rotation-1": "H03",
    "rotation-2": "H04",
    "rotation-3": "H14",
}
TARGET_IDS = ("H03", "H04", "H14")
RETENTION_IDS = ("H01", "H02", "H07", "H13")
EXPECTED_SOURCE_COUNTS = {"H03": 2, "H04": 2, "H14": 2, "H01": 1, "H02": 1, "H07": 1, "H13": 1}
GRADE_FIELDS = ("exact", "relation", "proof", "use", "uncertain", "note")
RECEIPT_MATCH_FIELDS = (
    "samples", "cap", "context", "temperature", "top_p", "top_k",
    "presence_penalty", "thinking", "driver_sha256", "model_metadata_sha256",
)


class BridgeError(ValueError):
    """Input failed a frozen bridge protocol check."""


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha256(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError(f"cannot read valid JSON from {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def frozen_job_prompt(job: dict[str, Any]) -> str:
    messages = job.get("messages")
    if not isinstance(messages, list) or len(messages) != 1 or not isinstance(messages[0], dict):
        raise BridgeError(f"job {job.get('id')!r} must have exactly one user message")
    if messages[0].get("role") != "user" or not isinstance(messages[0].get("content"), str):
        raise BridgeError(f"job {job.get('id')!r} has an invalid user message")
    return messages[0]["content"]


def load_frozen_jobs(eval_jobs_path: Path, hashes_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], str]:
    jobs = read_json(eval_jobs_path)
    hashes = read_json(hashes_path)
    if not isinstance(jobs, list) or len(jobs) != 10:
        raise BridgeError("frozen eval_jobs.json must contain exactly ten jobs")
    eval_hash = raw_sha256(eval_jobs_path)
    if hashes.get("output_sha256") != eval_hash:
        raise BridgeError("eval_jobs.json SHA-256 does not match frozen hashes.json output_sha256")
    if hashes.get("n_jobs") != 10:
        raise BridgeError("frozen hashes.json must declare n_jobs=10")
    ids = [job.get("id") for job in jobs]
    if any(not isinstance(job_id, str) or not job_id for job_id in ids) or len(set(ids)) != 10:
        raise BridgeError("frozen jobs must have ten unique nonempty IDs")
    source_counts = Counter(job.get("source_id") for job in jobs)
    if dict(source_counts) != EXPECTED_SOURCE_COUNTS:
        raise BridgeError(f"unexpected frozen source counts: {dict(source_counts)}")
    source_list = hashes.get("sources")
    if source_list != [job.get("source_id") for job in jobs]:
        raise BridgeError("frozen hashes.json source order does not match eval_jobs.json")
    by_id: dict[str, dict[str, Any]] = {}
    for job in jobs:
        job_id = job["id"]
        prompt = frozen_job_prompt(job)
        if not isinstance(job.get("seed"), int):
            raise BridgeError(f"job {job_id} has no integer seed")
        role = job.get("evaluation_role")
        expected_role = "heldout_transfer" if job.get("source_id") in TARGET_IDS else "source_retention_control"
        if role != expected_role:
            raise BridgeError(f"job {job_id} has unexpected evaluation_role {role!r}")
        job["_prompt"] = prompt
        job["_case_sha256"] = canonical_sha256({
            "job_id": job_id,
            "source_id": job["source_id"],
            "seed": job["seed"],
            "prompt": prompt,
        })
        by_id[job_id] = job
    return jobs, by_id, eval_hash


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def read_condition_directory(
    condition: str,
    directory: Path,
    jobs: list[dict[str, Any]],
    eval_hash: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not directory.is_dir():
        raise BridgeError(f"{condition} input is not a directory: {directory}")
    receipt_path = directory / "receipt.json"
    receipt = read_json(receipt_path)
    required = {"status", "jobs_sha256", "adapter", *RECEIPT_MATCH_FIELDS}
    missing = sorted(required - set(receipt)) if isinstance(receipt, dict) else sorted(required)
    if missing:
        raise BridgeError(f"{condition} receipt is missing required keys: {missing}")
    if receipt["status"] != "complete":
        raise BridgeError(f"{condition} receipt status must be complete")
    if receipt["jobs_sha256"] != eval_hash:
        raise BridgeError(f"{condition} receipt jobs_sha256 does not match frozen eval_jobs.json")
    if receipt["samples"] != 1 or type(receipt["samples"]) is not int:
        raise BridgeError(f"{condition} receipt must declare samples=1")
    for field in ("cap", "context"):
        if type(receipt[field]) is not int or receipt[field] <= 0:
            raise BridgeError(f"{condition} receipt {field} must be a positive integer")
    if receipt["cap"] > receipt["context"]:
        raise BridgeError(f"{condition} receipt cap exceeds context")
    if type(receipt["thinking"]) is not bool:
        raise BridgeError(f"{condition} receipt thinking must be a boolean")
    if type(receipt["top_k"]) is not int or receipt["top_k"] <= 0:
        raise BridgeError(f"{condition} receipt top_k must be a positive integer")
    for field in ("temperature", "top_p", "presence_penalty"):
        if type(receipt[field]) not in (int, float):
            raise BridgeError(f"{condition} receipt {field} must be numeric")
    if not valid_sha256(receipt["driver_sha256"]) or not valid_sha256(receipt["model_metadata_sha256"]):
        raise BridgeError(f"{condition} receipt driver/model metadata hashes must be SHA-256 values")
    if receipt["adapter"] is not None and not isinstance(receipt["adapter"], str):
        raise BridgeError(f"{condition} receipt adapter must be a string or null")

    expected_names = {"receipt.json", *(f"{job['id']}-0.json" for job in jobs)}
    actual_json_names = {path.name for path in directory.glob("*.json")}
    if actual_json_names != expected_names:
        missing_names = sorted(expected_names - actual_json_names)
        extra_names = sorted(actual_json_names - expected_names)
        raise BridgeError(f"{condition} JSON files differ from the ten frozen jobs; missing={missing_names}, extra={extra_names}")

    records: list[dict[str, Any]] = []
    file_hashes: dict[str, str] = {}
    for job in jobs:
        job_id = job["id"]
        path = directory / f"{job_id}-0.json"
        record = read_json(path)
        if not isinstance(record, dict):
            raise BridgeError(f"{condition}/{path.name} must contain a JSON object")
        if record.get("id") != job_id:
            raise BridgeError(f"{condition}/{path.name} id differs from frozen job ID")
        if record.get("source_id") != job["source_id"]:
            raise BridgeError(f"{condition}/{job_id} source_id differs from frozen job")
        if record.get("seed") != job["seed"]:
            raise BridgeError(f"{condition}/{job_id} seed differs from frozen job")
        if record.get("messages") != job["messages"]:
            raise BridgeError(f"{condition}/{job_id} messages differ from frozen prompt")
        sample = record.get("sample")
        if sample is not None and sample != 0:
            raise BridgeError(f"{condition}/{job_id} file is not sample zero")
        if record.get("finish_reason") != "stop":
            raise BridgeError(f"{condition}/{job_id} did not finish with a natural stop")
        completion_ids = record.get("completion_ids")
        if not isinstance(completion_ids, list) or any(type(token_id) is not int for token_id in completion_ids):
            raise BridgeError(f"{condition}/{job_id} completion_ids must be an integer list")
        if len(completion_ids) >= receipt["cap"]:
            raise BridgeError(f"{condition}/{job_id} completion length is not below receipt cap")
        prompt_ids = record.get("prompt_ids")
        if not isinstance(prompt_ids, list) or any(type(token_id) is not int for token_id in prompt_ids):
            raise BridgeError(f"{condition}/{job_id} prompt_ids must be an integer list")
        if len(prompt_ids) + receipt["cap"] > receipt["context"]:
            raise BridgeError(f"{condition}/{job_id} prompt plus cap exceeds receipt context")
        answer = record.get("final_text")
        if not isinstance(answer, str) or not answer.strip():
            raise BridgeError(f"{condition}/{job_id} final_text must be a nonempty string")
        records.append({
            "job_id": job_id,
            "source_id": job["source_id"],
            "case_sha256": job["_case_sha256"],
            "prompt_sha256": text_sha256(frozen_job_prompt(job)),
            "answer_sha256": text_sha256(answer),
            "prompt": frozen_job_prompt(job),
            "answer": answer,
        })
        file_hashes[job_id] = raw_sha256(path)
    audit = {
        "receipt_sha256": raw_sha256(receipt_path),
        "job_files_sha256": file_hashes,
        "receipt": receipt,
    }
    return records, audit


def build_packet(
    eval_jobs_path: Path,
    hashes_path: Path,
    inputs: dict[str, Path],
    packet_path: Path,
    vault_path: Path,
    shuffle_seed: int | None,
) -> dict[str, Any]:
    if packet_path.resolve() == vault_path.resolve():
        raise BridgeError("blind packet and private vault must be separate files")
    if set(inputs) != set(CONDITIONS):
        raise BridgeError(f"provide exactly one --input for each frozen condition; got {sorted(inputs)}")
    resolved_dirs = [inputs[condition].resolve() for condition in CONDITIONS]
    if len(set(resolved_dirs)) != len(CONDITIONS):
        raise BridgeError("each condition must have a distinct generate.py output directory")
    jobs, jobs_by_id, eval_hash = load_frozen_jobs(eval_jobs_path, hashes_path)
    seed = secrets.randbits(128) if shuffle_seed is None else shuffle_seed
    assembled: list[dict[str, Any]] = []
    condition_audit: dict[str, dict[str, Any]] = {}
    common_receipt_settings: dict[str, Any] | None = None
    for condition in CONDITIONS:
        records, audit = read_condition_directory(condition, inputs[condition], jobs, eval_hash)
        settings = {field: audit["receipt"][field] for field in RECEIPT_MATCH_FIELDS}
        if common_receipt_settings is None:
            common_receipt_settings = settings
        elif settings != common_receipt_settings:
            mismatches = sorted(field for field in settings if settings[field] != common_receipt_settings[field])
            raise BridgeError(f"{condition} receipt settings differ across conditions: {mismatches}")
        condition_audit[condition] = audit
        for record in records:
            assembled.append({"condition": condition, **record})
    rng = random.Random(seed)
    rng.shuffle(assembled)
    packet_records = []
    mapping_records = []
    for index, item in enumerate(assembled, start=1):
        blind_id = f"B{index:03d}"
        packet_records.append({
            "blind_id": blind_id,
            "source_id": item["source_id"],
            "prompt": item["prompt"],
            "answer": item["answer"],
        })
        mapping_records.append({
            "blind_id": blind_id,
            "condition": item["condition"],
            "job_id": item["job_id"],
            "source_id": item["source_id"],
            "case_sha256": item["case_sha256"],
            "prompt_sha256": item["prompt_sha256"],
            "answer_sha256": item["answer_sha256"],
        })
    packet = {"format": "blind-bridge-packet-v1", "n_records": len(packet_records), "records": packet_records}
    write_json(packet_path, packet)
    packet_hash = raw_sha256(packet_path)
    vault = {
        "format": "bridge-private-vault-v1",
        "packet_sha256": packet_hash,
        "eval_jobs_sha256": eval_hash,
        "shuffle_seed_private": str(seed),
        "condition_audit": condition_audit,
        "entries": mapping_records,
    }
    write_json(vault_path, vault)
    return {
        "n_records": len(packet_records),
        "packet_sha256": packet_hash,
        "vault_sha256": raw_sha256(vault_path),
        "eval_jobs_sha256": eval_hash,
    }


def load_packet(packet_path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    packet = read_json(packet_path)
    if not isinstance(packet, dict) or packet.get("format") != "blind-bridge-packet-v1":
        raise BridgeError("invalid blind packet format")
    records = packet.get("records")
    if not isinstance(records, list) or len(records) != 70 or packet.get("n_records") != 70:
        raise BridgeError("blind packet must contain exactly seventy records")
    by_blind_id: dict[str, dict[str, Any]] = {}
    for row in records:
        if not isinstance(row, dict):
            raise BridgeError("packet contains a non-object record")
        blind_id = row.get("blind_id")
        if not isinstance(blind_id, str) or not blind_id or blind_id in by_blind_id:
            raise BridgeError("packet blind IDs must be unique nonempty strings")
        if not isinstance(row.get("source_id"), str) or not isinstance(row.get("prompt"), str) or not isinstance(row.get("answer"), str):
            raise BridgeError(f"packet row {blind_id} has malformed fields")
        by_blind_id[blind_id] = row
    return packet, by_blind_id, raw_sha256(packet_path)


def freeze_grades(packet_path: Path, input_grades_path: Path, output_path: Path) -> dict[str, Any]:
    _, packet_rows, packet_hash = load_packet(packet_path)
    grades = read_json(input_grades_path)
    if not isinstance(grades, list):
        raise BridgeError("blind grades must be a JSON list")
    grade_by_id: dict[str, dict[str, Any]] = {}
    for row in grades:
        if not isinstance(row, dict):
            raise BridgeError("grade list contains a non-object record")
        blind_id = row.get("blind_id")
        if blind_id not in packet_rows:
            raise BridgeError(f"grade contains unknown blind_id {blind_id!r}")
        if blind_id in grade_by_id:
            raise BridgeError(f"duplicate grade for {blind_id}")
        if set(row) != {"blind_id", *GRADE_FIELDS}:
            raise BridgeError(f"{blind_id} grade fields must be blind_id plus {GRADE_FIELDS}")
        for field in GRADE_FIELDS[:-1]:
            if type(row[field]) is not bool:
                raise BridgeError(f"{blind_id}.{field} must be a strict JSON boolean")
        if not isinstance(row["note"], str) or not row["note"].strip():
            raise BridgeError(f"{blind_id}.note must be a concise nonempty math note")
        grade_by_id[blind_id] = {"blind_id": blind_id, **{field: row[field] for field in GRADE_FIELDS}}
    if set(grade_by_id) != set(packet_rows):
        raise BridgeError(f"grade IDs do not match packet; missing={sorted(set(packet_rows)-set(grade_by_id))}")
    ordered = [grade_by_id[row["blind_id"]] for row in read_json(packet_path)["records"]]
    rows_hash = canonical_sha256(ordered)
    frozen = {
        "format": "frozen-blind-bridge-grades-v1",
        "packet_sha256": packet_hash,
        "grade_rows_sha256": rows_hash,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "grade_rows": ordered,
    }
    write_json(output_path, frozen)
    return {"n_grades": len(ordered), "packet_sha256": packet_hash, "grade_rows_sha256": rows_hash, "frozen_grades_sha256": raw_sha256(output_path)}


def grade_score(row: dict[str, Any]) -> dict[str, Any]:
    complete = all(row[field] for field in ("exact", "relation", "proof", "use"))
    return {**row, "complete": complete, "score_usable": not row["uncertain"]}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row["score_usable"]]
    complete_n = sum(row["complete"] for row in usable)
    return {
        "n_total": len(rows),
        "n_uncertain": len(rows) - len(usable),
        "n_scored": len(usable),
        "n_complete": complete_n,
        "complete_rate": (complete_n / len(usable)) if usable else None,
    }


def scored_entry(mapping_row: dict[str, Any], grade_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "blind_id": mapping_row["blind_id"],
        "job_id": mapping_row["job_id"],
        "source_id": mapping_row["source_id"],
        "condition": mapping_row["condition"],
        "case_sha256": mapping_row["case_sha256"],
        "answer_sha256": mapping_row["answer_sha256"],
        **grade_score(grade_row),
    }


def summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"summary": summarize(rows), "rows": rows}


def parse_condition_inputs(specs: list[str]) -> dict[str, Path]:
    inputs: dict[str, Path] = {}
    for spec in specs:
        condition, separator, directory = spec.partition("=")
        if not separator or not condition or not directory:
            raise BridgeError(f"--input must have CONDITION=DIR form, got {spec!r}")
        if condition not in CONDITIONS:
            raise BridgeError(f"unknown --input condition {condition!r}")
        if condition in inputs:
            raise BridgeError(f"duplicate --input condition {condition!r}")
        inputs[condition] = Path(directory)
    if set(inputs) != set(CONDITIONS):
        raise BridgeError(f"provide exactly one --input for each frozen condition; missing={sorted(set(CONDITIONS)-set(inputs))}")
    return inputs


def join_scores(
    packet_path: Path,
    vault_path: Path,
    frozen_grades_path: Path,
    eval_jobs_path: Path,
    hashes_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    _, packet_rows, packet_hash = load_packet(packet_path)
    _, jobs_by_id, eval_hash = load_frozen_jobs(eval_jobs_path, hashes_path)
    vault = read_json(vault_path)
    if not isinstance(vault, dict) or vault.get("format") != "bridge-private-vault-v1":
        raise BridgeError("invalid private vault format")
    if vault.get("packet_sha256") != packet_hash:
        raise BridgeError("private vault was made for a different blind packet")
    if vault.get("eval_jobs_sha256") != eval_hash:
        raise BridgeError("private vault was made for different frozen eval jobs")
    map_rows = vault.get("entries")
    if not isinstance(map_rows, list) or len(map_rows) != 70:
        raise BridgeError("private vault must contain exactly seventy rows")
    condition_audit = vault.get("condition_audit")
    if not isinstance(condition_audit, dict) or set(condition_audit) != set(CONDITIONS):
        raise BridgeError("private vault must contain one receipt/file audit per frozen condition")
    receipt_settings: dict[str, Any] | None = None
    for condition, audit in condition_audit.items():
        if not isinstance(audit, dict) or not valid_sha256(audit.get("receipt_sha256")):
            raise BridgeError(f"{condition} vault receipt hash is malformed")
        files = audit.get("job_files_sha256")
        if not isinstance(files, dict) or set(files) != set(jobs_by_id) or any(not valid_sha256(v) for v in files.values()):
            raise BridgeError(f"{condition} vault job-file hashes do not exactly match frozen jobs")
        receipt = audit.get("receipt")
        if not isinstance(receipt, dict) or receipt.get("status") != "complete" or receipt.get("jobs_sha256") != eval_hash:
            raise BridgeError(f"{condition} vault receipt does not confirm the frozen jobs")
        current_settings = {field: receipt.get(field) for field in RECEIPT_MATCH_FIELDS}
        if any(value is None for value in current_settings.values()):
            raise BridgeError(f"{condition} vault receipt is missing matched settings")
        if receipt_settings is None:
            receipt_settings = current_settings
        elif current_settings != receipt_settings:
            raise BridgeError("vault receipt settings differ across conditions")
    map_by_id: dict[str, dict[str, Any]] = {}
    pairs: set[tuple[str, str]] = set()
    for row in map_rows:
        if not isinstance(row, dict):
            raise BridgeError("private vault contains a non-object entry")
        blind_id = row.get("blind_id")
        condition = row.get("condition")
        job_id = row.get("job_id")
        if blind_id not in packet_rows or blind_id in map_by_id:
            raise BridgeError(f"private vault has invalid or duplicate blind_id {blind_id!r}")
        if condition not in CONDITIONS or job_id not in jobs_by_id:
            raise BridgeError(f"private vault has invalid condition/job pair for {blind_id}")
        if row.get("source_id") != jobs_by_id[job_id]["source_id"] or row.get("source_id") != packet_rows[blind_id]["source_id"]:
            raise BridgeError(f"private vault source ID mismatch for {blind_id}")
        if row.get("case_sha256") != jobs_by_id[job_id]["_case_sha256"]:
            raise BridgeError(f"private vault case hash mismatch for {blind_id}")
        if row.get("prompt_sha256") != text_sha256(jobs_by_id[job_id]["_prompt"]):
            raise BridgeError(f"private vault prompt hash mismatch for {blind_id}")
        if row.get("prompt_sha256") != text_sha256(packet_rows[blind_id]["prompt"]):
            raise BridgeError(f"private vault prompt hash does not match packet for {blind_id}")
        if row.get("answer_sha256") != text_sha256(packet_rows[blind_id]["answer"]):
            raise BridgeError(f"private vault answer hash does not match packet for {blind_id}")
        map_by_id[blind_id] = row
        pair = (condition, job_id)
        if pair in pairs:
            raise BridgeError(f"duplicate condition/job pair {pair}")
        pairs.add(pair)
    if set(map_by_id) != set(packet_rows):
        raise BridgeError("private vault blind IDs do not exactly match packet")
    for condition in CONDITIONS:
        condition_jobs = {job_id for cond, job_id in pairs if cond == condition}
        if condition_jobs != set(jobs_by_id):
            raise BridgeError(f"{condition} does not map exactly the frozen ten jobs")

    frozen = read_json(frozen_grades_path)
    if not isinstance(frozen, dict) or frozen.get("format") != "frozen-blind-bridge-grades-v1":
        raise BridgeError("invalid frozen blind grade format")
    if frozen.get("packet_sha256") != packet_hash:
        raise BridgeError("frozen grades were made for a different blind packet")
    grade_rows = frozen.get("grade_rows")
    if not isinstance(grade_rows, list) or len(grade_rows) != 70:
        raise BridgeError("frozen grade file must contain seventy rows")
    if canonical_sha256(grade_rows) != frozen.get("grade_rows_sha256"):
        raise BridgeError("frozen grade rows SHA-256 mismatch")
    grades: dict[str, dict[str, Any]] = {}
    for row in grade_rows:
        if not isinstance(row, dict) or row.get("blind_id") not in packet_rows or row["blind_id"] in grades:
            raise BridgeError("frozen grades contain invalid or duplicate blind ID")
        if set(row) != {"blind_id", *GRADE_FIELDS}:
            raise BridgeError(f"frozen grade {row.get('blind_id')} has invalid fields")
        for field in GRADE_FIELDS[:-1]:
            if type(row[field]) is not bool:
                raise BridgeError(f"frozen grade {row['blind_id']}.{field} is not boolean")
        if not isinstance(row["note"], str) or not row["note"].strip():
            raise BridgeError(f"frozen grade {row['blind_id']} is missing its math note")
        grades[row["blind_id"]] = row
    if set(grades) != set(packet_rows):
        raise BridgeError("frozen grade blind IDs do not exactly match packet")
    rows_by_condition: dict[str, list[dict[str, Any]]] = {condition: [] for condition in CONDITIONS}
    for blind_id, map_row in map_by_id.items():
        rows_by_condition[map_row["condition"]].append(scored_entry(map_row, grades[blind_id]))
    for condition, rows in rows_by_condition.items():
        rows.sort(key=lambda row: row["job_id"])
        if len(rows) != 10:
            raise BridgeError(f"joined {condition} has {len(rows)} rows, expected ten")

    source_by_job = {job_id: job["source_id"] for job_id, job in jobs_by_id.items()}
    rotation_reports: dict[str, Any] = {}
    for rotation, (treatment_condition, control_condition) in ROTATION_CONDITIONS.items():
        omitted = ROTATION_OMITTED_ID[rotation]
        heldout_ids = {job_id for job_id, source in source_by_job.items() if source == omitted}
        if len(heldout_ids) != 2:
            raise BridgeError(f"{rotation} omitted source {omitted} does not have exactly two jobs")
        active_conditions = ("base", treatment_condition, control_condition)
        per_condition: dict[str, Any] = {}
        paired: dict[str, dict[str, Any]] = {}
        for condition in active_conditions:
            rows = rows_by_condition[condition]
            heldout = [row for row in rows if row["source_id"] == omitted]
            seen_source = [row for row in rows if row["source_id"] in TARGET_IDS and row["source_id"] != omitted]
            retention = [row for row in rows if row["source_id"] in RETENTION_IDS]
            if len(heldout) != 2 or len(seen_source) != 4 or len(retention) != 4:
                raise BridgeError(f"{condition}/{rotation} categories have unexpected sizes")
            per_condition[condition] = {
                "heldout": summarize_bucket(heldout),
                "seen_source": summarize_bucket(seen_source),
                "retention": summarize_bucket(retention),
            }
            for row in heldout:
                paired.setdefault(row["job_id"], {})[condition] = row
        if any(set(pair) != set(active_conditions) for pair in paired.values()) or set(paired) != heldout_ids:
            raise BridgeError(f"{rotation} does not have complete base/treatment/control heldout pairs")
        rotation_reports[rotation] = {
            "omitted_source_id": omitted,
            "heldout_job_ids": sorted(heldout_ids),
            "active_conditions": list(active_conditions),
            "by_condition": per_condition,
            "paired_heldout": {job_id: paired[job_id] for job_id in sorted(paired)},
        }
    lower_bar: dict[str, Any] = {}
    for condition, rows in rows_by_condition.items():
        h04_rows = [row for row in rows if row["source_id"] == "H04"]
        if len(h04_rows) != 2:
            raise BridgeError(f"{condition} H04 lower-bar slice must contain exactly two jobs")
        lower_bar[condition] = summarize_bucket(h04_rows)
    report = {
        "format": "bridge-blind-score-report-v1",
        "eval_jobs_sha256": eval_hash,
        "packet_sha256": packet_hash,
        "private_vault_sha256": raw_sha256(vault_path),
        "frozen_grades_sha256": raw_sha256(frozen_grades_path),
        "score_definition": "complete = exact AND relation AND proof AND use; uncertain rows remain listed but are excluded from rates pending adjudication",
        "rotations": rotation_reports,
        "lower_bar_H04": lower_bar,
    }
    write_json(output_path, report)
    return {"report_sha256": raw_sha256(output_path), "rotations": list(rotation_reports), "n_conditions": len(rows_by_condition)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    build = subs.add_parser("build-packet", help="validate seven generate.py output directories and build shuffled packet plus private vault")
    build.add_argument("--eval-jobs", type=Path, required=True)
    build.add_argument("--frozen-hashes", type=Path, required=True)
    build.add_argument("--input", action="append", required=True, metavar="CONDITION=DIR")
    build.add_argument("--packet-out", type=Path, required=True)
    build.add_argument("--vault-out", type=Path, required=True)
    build.add_argument("--shuffle-seed", type=int)
    freeze = subs.add_parser("freeze-grades", help="validate and freeze a blind grade list without reading the private vault")
    freeze.add_argument("--packet", type=Path, required=True)
    freeze.add_argument("--grades", type=Path, required=True)
    freeze.add_argument("--frozen-out", type=Path, required=True)
    join = subs.add_parser("join", help="join frozen grades to the private vault and produce scoped score report")
    join.add_argument("--packet", type=Path, required=True)
    join.add_argument("--vault", type=Path, required=True)
    join.add_argument("--frozen-grades", type=Path, required=True)
    join.add_argument("--eval-jobs", type=Path, required=True)
    join.add_argument("--frozen-hashes", type=Path, required=True)
    join.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build-packet":
            inputs = parse_condition_inputs(args.input)
            result = build_packet(args.eval_jobs, args.frozen_hashes, inputs, args.packet_out, args.vault_out, args.shuffle_seed)
        elif args.command == "freeze-grades":
            result = freeze_grades(args.packet, args.grades, args.frozen_out)
        else:
            result = join_scores(args.packet, args.vault, args.frozen_grades, args.eval_jobs, args.frozen_hashes, args.report_out)
    except BridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
