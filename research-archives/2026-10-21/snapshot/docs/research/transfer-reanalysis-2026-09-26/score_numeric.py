#!/usr/bin/env python3
"""Score exact numeric answers from the frozen transfer evaluation.

This is a numeric-answer check only. It does not assess whether the reasoning
is valid. It consumes completed generate_batch.py output directories and never
passes the answer key to a model.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qwen.answer_check import answers_equal, extract_answer, final_text


class ScoreError(ValueError):
    """A frozen-input or result-integrity check failed."""


ANSWER_LINE = re.compile(
    r"(?im)^[ \t]*(?:\*\*)?(?:final[ \t]+)?answer[ \t]*:[ \t]*(?:\*\*)?[ \t]*(.*?)[ \t]*(?:\*\*)?[ \t]*$"
)
BOX_START = re.compile(r"\\boxed\s*\{")
NATURAL_FINISH_REASONS = {"stop", "eos", "end_of_sequence"}
RECEIPT_SETTINGS = (
    "model_revision",
    "driver_sha256",
    "jobs_sha256",
    "cap",
    "context",
    "batch_size",
    "samples",
    "temperature",
    "top_p",
    "top_k",
    "presence_penalty",
    "enable_thinking",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(encoded)


def _boxed_spans(text: str) -> list[tuple[int, str, str]]:
    spans: list[tuple[int, str, str]] = []
    for match in BOX_START.finditer(text):
        depth = 1
        end = match.end()
        while end < len(text) and depth:
            char = text[end]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            end += 1
        if depth == 0:
            spans.append((match.start(), "boxed", text[match.start() : end]))
        else:
            # An unfinished final box is still the latest explicit commit.
            # Keep it so the parser returns unparsed instead of falling back
            # to an earlier, convenient boxed answer.
            spans.append((match.start(), "boxed", text[match.start() :]))
    return spans


def last_committed_answer(raw_text: str) -> dict[str, Any] | None:
    """Return the last explicit Answer line or ``\\boxed{...}`` marker.

    Earlier boxes do not override a later Answer line. An unmarked final number
    is intentionally ignored. An unclosed last box is selected and becomes
    unparsed rather than exposing an earlier result. ``extract_answer`` is
    applied only to the chosen commit, avoiding its whole-response box preference.
    """
    text = final_text(raw_text)
    if not text:
        return None
    commits: list[tuple[int, str, str]] = _boxed_spans(text)
    commits.extend(
        (match.start(), "answer_line", match.group(1).strip())
        for match in ANSWER_LINE.finditer(text)
    )
    if not commits:
        return None
    position, marker, expression = max(commits, key=lambda item: item[0])
    parsed = extract_answer(expression)
    return {
        "marker": marker,
        "position": position,
        "expression": expression,
        "parsed": parsed,
    }


def grade_numeric_text(raw_text: str, expected: str) -> dict[str, Any]:
    commit = last_committed_answer(raw_text)
    if commit is None:
        return {
            "numeric_status": "unparsed",
            "numeric_correct": None,
            "commit_marker": None,
            "answer_expression": None,
            "extracted_expression": None,
        }
    correct = answers_equal(commit["parsed"], expected)
    status = "unparsed" if correct is None else ("correct" if correct else "incorrect")
    return {
        "numeric_status": status,
        "numeric_correct": correct,
        "commit_marker": commit["marker"],
        "answer_expression": commit["expression"],
        "extracted_expression": commit["parsed"],
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoreError(f"cannot read JSON {path}: {exc}") from exc


def load_frozen_inputs(jobs_path: Path, key_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    jobs = _load_json(jobs_path)
    key_rows = _load_json(key_path)
    if not isinstance(jobs, list) or not isinstance(key_rows, list):
        raise ScoreError("jobs and answer key must both be JSON lists")
    ids = [row.get("id") for row in jobs]
    key_ids = [row.get("id") for row in key_rows]
    if len(jobs) != 24 or len(set(ids)) != 24:
        raise ScoreError(f"expected 24 unique frozen jobs, found {len(jobs)}")
    if len(key_rows) != 24 or len(set(key_ids)) != 24:
        raise ScoreError(f"expected 24 unique answer-key rows, found {len(key_rows)}")
    if set(ids) != set(key_ids):
        raise ScoreError(
            f"answer-key job IDs differ; missing={sorted(set(ids)-set(key_ids))}, "
            f"extra={sorted(set(key_ids)-set(ids))}"
        )
    if len({row.get("source_id") for row in jobs}) != 12:
        raise ScoreError("expected 12 unique source configurations")
    by_source: dict[str, list[dict[str, Any]]] = {}
    for row in jobs:
        by_source.setdefault(row.get("source_id"), []).append(row)
    for source_id, source_jobs in by_source.items():
        if len(source_jobs) != 2 or {row.get("replicate") for row in source_jobs} != {1, 2}:
            raise ScoreError(f"expected two replicates (1 and 2) for {source_id}")
        if len({row.get("seed") for row in source_jobs}) != 2:
            raise ScoreError(f"expected distinct inference seeds for {source_id}")
    for job in jobs:
        if "answer_exact" in job or "geometry_solution_ja" in job:
            raise ScoreError(f"private answer/solution field leaked into job {job['id']}")
        if not isinstance(job.get("seed"), int) or not isinstance(job.get("messages"), list):
            raise ScoreError(f"job {job['id']} lacks a seed or message list")
        content = "\n".join(m.get("content", "") for m in job["messages"])
        if "End with a single line of the form Answer: <exact numerical expression>." not in content:
            raise ScoreError(f"job {job['id']} does not specify the frozen answer-line format")
    key_by_id = {row["id"]: row for row in key_rows}
    for job in jobs:
        key = key_by_id[job["id"]]
        if key.get("source_id") != job.get("source_id") or not isinstance(key.get("answer_exact"), str):
            raise ScoreError(f"answer-key mismatch or invalid exact answer for {job['id']}")
        try:
            label_is_valid = answers_equal(key["answer_exact"], key["answer_exact"]) is True
        except ValueError as exc:
            raise ScoreError(f"invalid exact numeric label for {job['id']}: {exc}") from exc
        if not label_is_valid:
            raise ScoreError(f"invalid exact numeric label for {job['id']}")
    return jobs, key_by_id


def parse_condition_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("condition must be NAME=OUTPUT_DIR")
    name, path = value.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError("condition must be NAME=OUTPUT_DIR")
    return name, Path(path)


def _load_receipt(out_dir: Path, jobs_sha256: str) -> dict[str, Any]:
    path = out_dir / "receipt.json"
    receipt = _load_json(path)
    if receipt.get("status") != "complete":
        raise ScoreError(f"{path}: run receipt is not complete")
    if receipt.get("jobs_sha256") != jobs_sha256:
        raise ScoreError(f"{path}: jobs hash does not match the frozen evaluation")
    if receipt.get("completed_jobs") != 24:
        raise ScoreError(f"{path}: receipt does not report all 24 jobs complete")
    if receipt.get("samples") != 1:
        raise ScoreError(f"{path}: expected exactly one sample per job")
    return receipt


def score_condition(
    name: str,
    out_dir: Path,
    jobs: list[dict[str, Any]],
    key_by_id: dict[str, dict[str, Any]],
    jobs_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = _load_receipt(out_dir, jobs_sha256)
    expected = {job["id"]: job for job in jobs}
    result_files: dict[str, Path] = {}
    json_files = {path.name: path for path in out_dir.glob("*.json")}
    unexpected_json = sorted(
        name for name in json_files if name != "receipt.json" and not name.endswith("-0.json")
    )
    if unexpected_json:
        raise ScoreError(f"{out_dir}: unexpected JSON output files: {unexpected_json}")
    for path in out_dir.glob("*-0.json"):
        job_id = path.name.removesuffix("-0.json")
        if job_id in result_files:
            raise ScoreError(f"{out_dir}: duplicate result files for {job_id}")
        result_files[job_id] = path
    missing = sorted(set(expected) - set(result_files))
    extra = sorted(set(result_files) - set(expected))
    if missing or extra:
        raise ScoreError(f"{out_dir}: expected 24 jobs; missing={missing}, extra={extra}")

    rows: list[dict[str, Any]] = []
    prompt_token_hashes: dict[str, str] = {}
    for job in jobs:
        job_id = job["id"]
        path = result_files[job_id]
        record = _load_json(path)
        record_id = record.get("id", record.get("job_id"))
        if record_id != job_id:
            raise ScoreError(f"{path}: record job ID {record_id!r} does not match filename")
        for field, frozen_value in job.items():
            if record.get(field) != frozen_value:
                raise ScoreError(f"{path}: {field} differs from frozen eval job")
        if record.get("sample") != 0:
            raise ScoreError(f"{path}: expected sample index 0")
        if record.get("revision") != receipt.get("model_revision"):
            raise ScoreError(f"{path}: model revision differs from the run receipt")
        if record.get("adapter") != receipt.get("adapter"):
            raise ScoreError(f"{path}: adapter differs from the run receipt")
        raw_text = record.get("raw_text")
        completion_ids = record.get("completion_ids")
        finish_reason = record.get("finish_reason")
        prompt_ids = record.get("prompt_ids")
        if not isinstance(raw_text, str) or not isinstance(completion_ids, list):
            raise ScoreError(f"{path}: missing raw_text or completion_ids")
        if not isinstance(finish_reason, str) or not isinstance(prompt_ids, list):
            raise ScoreError(f"{path}: missing finish_reason or prompt_ids")
        prompt_token_hash = canonical_json_hash(prompt_ids)
        prompt_token_hashes[job_id] = prompt_token_hash
        expected_answer = key_by_id[job_id]["answer_exact"]
        grade = grade_numeric_text(raw_text, expected_answer)
        rows.append(
            {
                "job_id": job_id,
                "source_id": job["source_id"],
                "transfer_group": job.get("transfer_group"),
                "replicate": job["replicate"],
                "seed": job["seed"],
                "prompt_sha256": canonical_json_hash(job["messages"]),
                "prompt_token_ids_sha256": prompt_token_hash,
                "raw_file_sha256": sha256_file(path),
                "raw_text_sha256": sha256_bytes(raw_text.encode("utf-8")),
                "completion_tokens": len(completion_ids),
                "finish_reason": finish_reason,
                "natural_end": finish_reason.lower() in NATURAL_FINISH_REASONS,
                "expected_answer_exact": expected_answer,
                **grade,
            }
        )
    rows_by_id = {row["job_id"]: row for row in rows}
    result = {
        "condition": name,
        "output_dir": str(out_dir.resolve()),
        "receipt": receipt,
        "receipt_sha256": sha256_file(out_dir / "receipt.json"),
        "jobs": rows,
        "by_job_id": rows_by_id,
        "prompt_token_hashes": prompt_token_hashes,
    }
    return result, receipt


def validate_shared_runs(
    scored: dict[str, dict[str, Any]], receipts: dict[str, dict[str, Any]]
) -> None:
    names = list(scored)
    reference = scored[names[0]]
    reference_receipt = receipts[names[0]]
    for name in names[1:]:
        current = scored[name]
        receipt = receipts[name]
        for field in RECEIPT_SETTINGS:
            if receipt.get(field) != reference_receipt.get(field):
                raise ScoreError(f"conditions {names[0]} and {name} differ in run setting {field}")
        if set(current["by_job_id"]) != set(reference["by_job_id"]):
            raise ScoreError(f"condition {name} job set differs from {names[0]}")
        for job_id, baseline in reference["by_job_id"].items():
            other = current["by_job_id"][job_id]
            if other["seed"] != baseline["seed"]:
                raise ScoreError(f"condition {name} seed mismatch for {job_id}")
            if other["prompt_sha256"] != baseline["prompt_sha256"]:
                raise ScoreError(f"condition {name} message prompt mismatch for {job_id}")
            if other["prompt_token_ids_sha256"] != baseline["prompt_token_ids_sha256"]:
                raise ScoreError(f"condition {name} tokenized prompt mismatch for {job_id}")


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "jobs": len(rows),
        "correct": sum(r["numeric_status"] == "correct" for r in rows),
        "incorrect": sum(r["numeric_status"] == "incorrect" for r in rows),
        "unparsed": sum(r["numeric_status"] == "unparsed" for r in rows),
        "natural_end": sum(r["natural_end"] for r in rows),
        "length_finish": sum(r["finish_reason"].lower() == "length" for r in rows),
        "non_natural_end": sum(not r["natural_end"] for r in rows),
        "completion_tokens_total": sum(r["completion_tokens"] for r in rows),
        "completion_tokens_mean": (
            sum(r["completion_tokens"] for r in rows) / len(rows) if rows else None
        ),
        "completion_tokens_max": max((r["completion_tokens"] for r in rows), default=None),
        "finish_reason_counts": {
            reason: sum(r["finish_reason"].lower() == reason for r in rows)
            for reason in sorted({r["finish_reason"].lower() for r in rows})
        },
    }


def build_summary(scored: dict[str, dict[str, Any]]) -> dict[str, Any]:
    conditions: dict[str, Any] = {}
    for name, condition in scored.items():
        rows = condition["jobs"]
        per_source = {}
        for source_id in sorted({row["source_id"] for row in rows}):
            source_rows = [row for row in rows if row["source_id"] == source_id]
            per_source[source_id] = _counts(source_rows)
        per_group = {}
        for group in sorted({row.get("transfer_group") for row in rows}):
            group_rows = [row for row in rows if row.get("transfer_group") == group]
            per_group[group] = _counts(group_rows)
        conditions[name] = {
            "overall": _counts(rows),
            "per_source_id": per_source,
            "per_transfer_group": per_group,
            "receipt_sha256": condition["receipt_sha256"],
            "run_settings": {
                field: condition["receipt"].get(field)
                for field in (*RECEIPT_SETTINGS, "adapter", "adapter_sha256", "model_metadata_sha256")
            },
            "jobs": rows,
        }

    pairwise: dict[str, Any] = {}
    for left, right in itertools.combinations(scored, 2):
        left_by_id = scored[left]["by_job_id"]
        right_by_id = scored[right]["by_job_id"]
        wins: list[str] = []
        losses: list[str] = []
        ties: list[str] = []
        unparsed_pairs: list[str] = []
        for job_id in left_by_id:
            a = left_by_id[job_id]["numeric_status"]
            b = right_by_id[job_id]["numeric_status"]
            if a == "unparsed" or b == "unparsed":
                unparsed_pairs.append(job_id)
            elif a == b:
                ties.append(job_id)
            elif a == "correct":
                wins.append(job_id)
            else:
                losses.append(job_id)
        per_source = {}
        source_ids = sorted({row["source_id"] for row in scored[left]["jobs"]})
        for source_id in source_ids:
            source_job_ids = [
                row["job_id"]
                for row in scored[left]["jobs"]
                if row["source_id"] == source_id
            ]
            per_source[source_id] = {
                "wins": [job_id for job_id in wins if job_id in source_job_ids],
                "losses": [job_id for job_id in losses if job_id in source_job_ids],
                "ties": [job_id for job_id in ties if job_id in source_job_ids],
                "unparsed_pairs": [job_id for job_id in unparsed_pairs if job_id in source_job_ids],
            }
        pairwise[f"{left}_vs_{right}"] = {
            "paired_jobs": len(left_by_id),
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "unparsed_pairs": unparsed_pairs,
            "per_source_id": per_source,
        }
    return {"conditions": conditions, "paired_comparisons": pairwise}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--answer-key", type=Path, required=True)
    parser.add_argument(
        "--condition", action="append", type=parse_condition_arg, required=True,
        metavar="NAME=OUTPUT_DIR", help="completed condition output directory; repeat per arm",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    jobs, key_by_id = load_frozen_inputs(args.jobs, args.answer_key)
    if len(args.condition) < 2:
        raise ScoreError("at least two conditions are needed for paired comparisons")
    condition_names = [name for name, _ in args.condition]
    if len(set(condition_names)) != len(condition_names):
        raise ScoreError("condition names must be unique")
    resolved_dirs = [path.resolve() for _, path in args.condition]
    if len(set(resolved_dirs)) != len(resolved_dirs):
        raise ScoreError("each condition must use a distinct output directory")
    jobs_hash = sha256_file(args.jobs)
    key_hash = sha256_file(args.answer_key)
    scored: dict[str, dict[str, Any]] = {}
    receipts: dict[str, dict[str, Any]] = {}
    for name, out_dir in args.condition:
        condition, receipt = score_condition(name, out_dir, jobs, key_by_id, jobs_hash)
        scored[name] = condition
        receipts[name] = receipt
    validate_shared_runs(scored, receipts)
    summary = build_summary(scored)
    report = {
        "status": "complete",
        "scope": "Exact numeric answer scoring only; reasoning/proof validity is not assessed.",
        "jobs_path": str(args.jobs.resolve()),
        "jobs_sha256": jobs_hash,
        "answer_key_path": str(args.answer_key.resolve()),
        "answer_key_sha256": key_hash,
        "parser": "qwen.answer_check.extract_answer + answers_equal; last explicit Answer/box commit selected first",
        "conditions": summary["conditions"],
        "paired_comparisons": summary["paired_comparisons"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.with_suffix(args.out.suffix + ".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temp.replace(args.out)
    print(json.dumps({name: value["overall"] for name, value in summary["conditions"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
