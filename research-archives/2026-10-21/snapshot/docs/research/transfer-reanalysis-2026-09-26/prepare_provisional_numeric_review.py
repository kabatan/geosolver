#!/usr/bin/env python3
"""Prepare a provisional, blinded numeric derivation review packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from prepare_blind_numeric import (
    GRADING_INSTRUCTIONS,
    PacketError,
    _canonical_sha256,
    _sha256_file,
)
from score_numeric import (
    NATURAL_FINISH_REASONS,
    ScoreError,
    load_frozen_inputs,
    score_condition,
    sha256_file,
)


CAP32, CONTEXT32 = 32768, 40960


PROVISIONAL_POLICY = {
    "status": "provisional",
    "grade_reuse": (
        "Reuse a provisional grade only when the final scorer selects the same source file "
        "and matching SHA-256 for that answer."
    ),
    "length_retry": (
        "Responses ending with finish_reason='length' are omitted here because the 81k "
        "regeneration will be selected for final scoring. Any 81k response that differs "
        "from a provisional response must be graded separately. Omitting a 32k length "
        "response here does not exclude it from final scoring."
    ),
    "primary_score_authority": (
        "The primary score is the frozen scorer result after every condition is complete."
    ),
}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PacketError(f"cannot read JSON {path}: {exc}") from exc


def _check_outside_raw(raw_dir: Path, out_dir: Path) -> None:
    raw_dir, out_dir = raw_dir.resolve(), out_dir.resolve()
    if raw_dir == out_dir or raw_dir in out_dir.parents:
        raise PacketError("--out must be outside --raw-dir so the raw run remains unchanged")
    if out_dir.exists():
        raise PacketError(f"output directory already exists: {out_dir}")


def _make_case(
    case_id: str,
    job: dict[str, Any],
    record: dict[str, Any],
    expected: str,
    finish_reason: str,
) -> dict[str, Any]:
    raw_response, final_text = record.get("raw_text"), record.get("final_text")
    if not isinstance(raw_response, str) or not isinstance(final_text, str):
        raise PacketError(f"{job['id']}: raw output lacks full raw_text/final_text")
    return {
        "case_id": case_id,
        "construction_id": job["source_id"],
        "messages": job["messages"],
        "expected_numeric": expected,
        "final_text": final_text,
        "raw_response": raw_response,
        "selected_cap": CAP32,
        "finish_reason": finish_reason,
    }


def prepare_packet(raw_dir: Path, jobs_path: Path, answer_key_path: Path, out_dir: Path) -> dict[str, Any]:
    raw_dir = raw_dir.resolve()
    out_dir = out_dir.resolve()
    _check_outside_raw(raw_dir, out_dir)
    receipt_path = raw_dir / "receipt.json"
    receipt_sha_before = _sha256_file(receipt_path)

    jobs, key_by_id = load_frozen_inputs(jobs_path, answer_key_path)
    jobs_sha256 = sha256_file(jobs_path)
    # Run the frozen scorer itself, with no scoring-rule changes.
    score_result, receipt = score_condition(raw_dir.name, raw_dir, jobs, key_by_id, jobs_sha256)
    if receipt.get("cap") != CAP32 or receipt.get("context") != CONTEXT32:
        raise ScoreError(
            f"{receipt_path}: provisional review requires cap={CAP32}, context={CONTEXT32}"
        )
    if receipt_sha_before != _sha256_file(receipt_path):
        raise PacketError("raw run receipt changed while it was being scored")

    job_by_id = {job["id"]: job for job in jobs}
    score_by_id = {row["job_id"]: row for row in score_result["jobs"]}
    if set(score_by_id) != set(job_by_id) or len(score_by_id) != 24:
        raise ScoreError("frozen scorer did not return exactly the 24 frozen jobs")

    cases: list[dict[str, Any]] = []
    private_cases: dict[str, dict[str, Any]] = {}
    excluded_length: list[dict[str, Any]] = []
    excluded_other_finish: list[dict[str, Any]] = []
    source_hashes_before: dict[str, str] = {}
    seen_case_ids: set[str] = set()

    for job in jobs:
        job_id = job["id"]
        scored = score_by_id[job_id]
        source_path = raw_dir / f"{job_id}-0.json"
        source_hash = scored["raw_file_sha256"]
        if _sha256_file(source_path) != source_hash:
            raise PacketError(f"{source_path}: source changed after frozen scoring")
        source_hashes_before[job_id] = source_hash
        if scored["finish_reason"] == "length":
            excluded_length.append(
                {
                    "job_id": job_id,
                    "source_file": str(source_path.resolve()),
                    "source_file_sha256": source_hash,
                }
            )
            continue
        if scored["finish_reason"].lower() not in NATURAL_FINISH_REASONS:
            excluded_other_finish.append(
                {
                    "job_id": job_id,
                    "source_file": str(source_path.resolve()),
                    "source_file_sha256": source_hash,
                    "finish_reason": scored["finish_reason"],
                }
            )
            continue
        if scored["numeric_status"] not in {"correct", "unparsed"}:
            continue

        record = _read_json(source_path)
        case_id = "case_" + secrets.token_hex(16)
        while case_id in seen_case_ids:
            case_id = "case_" + secrets.token_hex(16)
        seen_case_ids.add(case_id)
        case = _make_case(
            case_id,
            job,
            record,
            key_by_id[job_id]["answer_exact"],
            scored["finish_reason"],
        )
        cases.append(case)
        private_cases[case_id] = {
            "source_file": str(source_path.resolve()),
            "source_file_sha256": source_hash,
            "job_id": job_id,
        }

    # Hash every raw result once more to prove this operation left the input run intact.
    if receipt_sha_before != _sha256_file(receipt_path):
        raise PacketError("raw run receipt changed during packet preparation")
    for job_id, expected_hash in source_hashes_before.items():
        source_path = raw_dir / f"{job_id}-0.json"
        if _sha256_file(source_path) != expected_hash:
            raise PacketError(f"{source_path}: raw output changed during packet preparation")

    secrets.SystemRandom().shuffle(cases)
    packet_value = {"schema": "blind-numeric-packet-v1", "cases": cases}
    packet_bytes = (
        json.dumps(packet_value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    packet_sha = _sha256_file_bytes(packet_bytes)
    case_hashes = {case["case_id"]: _canonical_sha256(case) for case in cases}
    manifest = {
        "schema": "provisional-blind-numeric-manifest-v1",
        "provisional": True,
        "packet_file": "blind_numeric_packet.json",
        "packet_sha256": packet_sha,
        "case_count": len(cases),
        "case_sha256": case_hashes,
        **PROVISIONAL_POLICY,
    }

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    grader_dir = out_dir / "grader"
    grader_dir.mkdir(parents=True, exist_ok=False)
    (grader_dir / "blind_numeric_packet.json").write_bytes(packet_bytes)
    (grader_dir / "packet-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (grader_dir / "GRADING_INSTRUCTIONS.md").write_text(
        GRADING_INSTRUCTIONS, encoding="utf-8"
    )
    (out_dir / "private-key.json").write_text(
        json.dumps(
            {
                "schema": "provisional-blind-numeric-private-key-v1",
                "source_dir": str(raw_dir),
                "source_condition": raw_dir.name,
                "receipt_file": str(receipt_path.resolve()),
                "receipt_sha256": receipt_sha_before,
                "cases": private_cases,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "private-manifest.json").write_text(
        json.dumps(
            {
                "schema": "provisional-blind-numeric-private-manifest-v1",
                "excluded_length_count": len(excluded_length),
                "excluded_length_outputs": excluded_length,
                "excluded_other_finish_count": len(excluded_other_finish),
                "excluded_other_finish_outputs": excluded_other_finish,
                "excluded_from_provisional_only": True,
                "final_scoring_note": (
                    "Length-finished 32k outputs remain eligible for final scoring through their 81k reruns."
                ),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"case_count": len(cases), "packet_sha256": packet_sha}


def _sha256_file_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True, help="completed single-condition 32k output directory")
    parser.add_argument("--jobs", type=Path, required=True, help="frozen 24-job manifest")
    parser.add_argument("--answer-key", type=Path, required=True, help="researcher-only frozen numeric answer key")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    result = prepare_packet(args.raw_dir, args.jobs, args.answer_key, args.out)
    # Keep stdout limited to packet size and integrity hash; never print scores or answers.
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
