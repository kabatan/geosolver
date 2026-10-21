#!/usr/bin/env python3
"""Score 32k numeric runs and their union-of-caps 81k retries.

The original score_numeric.py remains the authority for every full 24-job
32k condition. This script validates the corresponding subset retries, then
builds a separate 24-job extended-budget view using the retry where available
and the preserved 32k result otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from score_numeric import (
    NATURAL_FINISH_REASONS,
    RECEIPT_SETTINGS,
    ScoreError,
    _counts,
    build_summary,
    canonical_json_hash,
    grade_numeric_text,
    load_frozen_inputs,
    score_condition,
    sha256_file,
    validate_shared_runs,
)


CONDITIONS = ("base", "code128", "numeric128", "opd32")
GROUP = "numeric"
CAP32, CONTEXT32 = 32768, 40960
CAP81, CONTEXT81 = 81920, 98304
SHARED_CROSS_BUDGET_SETTINGS = tuple(
    field for field in RECEIPT_SETTINGS if field not in ("jobs_sha256", "cap", "context")
)
NATURAL_OR_LENGTH_REASONS = NATURAL_FINISH_REASONS | {"length"}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoreError(f"cannot read JSON {path}: {exc}") from exc


def _check_result_files(out_dir: Path, expected_ids: set[str]) -> dict[str, Path]:
    json_files = {path.name: path for path in out_dir.glob("*.json")}
    unexpected = sorted(
        name for name in json_files if name != "receipt.json" and not name.endswith("-0.json")
    )
    if unexpected:
        raise ScoreError(f"{out_dir}: unexpected JSON output files: {unexpected}")
    files: dict[str, Path] = {}
    for path in out_dir.glob("*-0.json"):
        job_id = path.name.removesuffix("-0.json")
        if job_id in files:
            raise ScoreError(f"{out_dir}: duplicate result files for {job_id}")
        files[job_id] = path
    missing, extra = sorted(expected_ids - set(files)), sorted(set(files) - expected_ids)
    if missing or extra:
        raise ScoreError(f"{out_dir}: output job mismatch; missing={missing}, extra={extra}")
    return files


def _validate_run_root(run_dir: Path, jobs_path: Path) -> dict[str, Any]:
    receipt_path = run_dir / "receipt.json"
    receipt = _read_json(receipt_path)
    if receipt.get("status") not in ("running", "complete"):
        raise ScoreError(f"{receipt_path}: run status is neither running nor complete")
    inputs = receipt.get("inputs", {})
    frozen_job_hash = inputs.get(str(jobs_path.resolve()))
    if frozen_job_hash != sha256_file(jobs_path):
        raise ScoreError("run receipt does not freeze the supplied numeric jobs file")
    return receipt


def _validate_cap_receipt(
    out_dir: Path,
    jobs_sha256: str,
    n_jobs: int,
    cap: int,
    context: int,
) -> dict[str, Any]:
    path = out_dir / "receipt.json"
    receipt = _read_json(path)
    if receipt.get("status") != "complete":
        raise ScoreError(f"{path}: condition generation is incomplete")
    expected = {
        "jobs_sha256": jobs_sha256,
        "completed_jobs": n_jobs,
        "samples": 1,
        "cap": cap,
        "context": context,
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise ScoreError(f"{path}: expected {field}={value!r}, got {receipt.get(field)!r}")
    return receipt


def _score_retry_condition(
    condition: str,
    out_dir: Path,
    jobs: list[dict[str, Any]],
    key_by_id: dict[str, dict[str, Any]],
    jobs_sha256: str,
) -> dict[str, Any]:
    """Validate and score one 81k subset without relaxing numeric parsing."""
    receipt = _validate_cap_receipt(out_dir, jobs_sha256, len(jobs), CAP81, CONTEXT81)
    expected_by_id = {job["id"]: job for job in jobs}
    files = _check_result_files(out_dir, set(expected_by_id))
    rows: list[dict[str, Any]] = []
    prompt_token_hashes: dict[str, str] = {}
    raw_records: dict[str, dict[str, Any]] = {}
    for job_id, job in expected_by_id.items():
        path = files[job_id]
        record = _read_json(path)
        if record.get("id", record.get("job_id")) != job_id:
            raise ScoreError(f"{path}: output id does not match its filename")
        for field, frozen_value in job.items():
            if record.get(field) != frozen_value:
                raise ScoreError(f"{path}: {field} differs from the frozen job")
        if record.get("sample") != 0:
            raise ScoreError(f"{path}: expected sample index 0")
        if record.get("revision") != receipt.get("model_revision"):
            raise ScoreError(f"{path}: model revision differs from its receipt")
        if record.get("adapter") != receipt.get("adapter"):
            raise ScoreError(f"{path}: adapter differs from its receipt")
        raw_text = record.get("raw_text")
        completion_ids = record.get("completion_ids")
        prompt_ids = record.get("prompt_ids")
        finish_reason = record.get("finish_reason")
        if not isinstance(raw_text, str) or not isinstance(completion_ids, list):
            raise ScoreError(f"{path}: missing raw_text or completion_ids")
        if not isinstance(prompt_ids, list) or not isinstance(finish_reason, str):
            raise ScoreError(f"{path}: missing prompt_ids or finish_reason")
        if finish_reason.lower() not in NATURAL_OR_LENGTH_REASONS:
            raise ScoreError(f"{path}: unrecognized finish reason {finish_reason!r}")
        prompt_hash = canonical_json_hash(prompt_ids)
        prompt_token_hashes[job_id] = prompt_hash
        expected_answer = key_by_id[job_id]["answer_exact"]
        rows.append(
            {
                "job_id": job_id,
                "source_id": job["source_id"],
                "transfer_group": job.get("transfer_group"),
                "replicate": job["replicate"],
                "seed": job["seed"],
                "prompt_sha256": canonical_json_hash(job["messages"]),
                "prompt_token_ids_sha256": prompt_hash,
                "raw_file_sha256": sha256_file(path),
                "raw_text_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
                "source_file": str(path.resolve()),
                "cap": CAP81,
                "context": CONTEXT81,
                "completion_tokens": len(completion_ids),
                "finish_reason": finish_reason,
                "natural_end": finish_reason.lower() in NATURAL_FINISH_REASONS,
                "expected_answer_exact": expected_answer,
                **grade_numeric_text(raw_text, expected_answer),
            }
        )
        raw_records[job_id] = record
    return {
        "condition": condition,
        "output_dir": str(out_dir.resolve()),
        "receipt": receipt,
        "receipt_sha256": sha256_file(out_dir / "receipt.json"),
        "jobs": rows,
        "by_job_id": {row["job_id"]: row for row in rows},
        "prompt_token_hashes": prompt_token_hashes,
        "raw_records": raw_records,
        "result_files": files,
    }


def _validate_retries(
    base32: dict[str, dict[str, Any]],
    retry81: dict[str, dict[str, Any]],
    receipts32: dict[str, dict[str, Any]],
    receipts81: dict[str, dict[str, Any]],
) -> None:
    reference32 = receipts32[CONDITIONS[0]]
    for condition in CONDITIONS:
        receipt32, receipt81 = receipts32[condition], receipts81[condition]
        for field in SHARED_CROSS_BUDGET_SETTINGS:
            if receipt81.get(field) != receipt32.get(field):
                raise ScoreError(f"{condition}: 32k and 81k runs differ in {field}")
        for field in ("adapter", "adapter_sha256"):
            if receipt81.get(field) != receipt32.get(field):
                raise ScoreError(f"{condition}: 32k and 81k adapter {field} changed")
        for field in SHARED_CROSS_BUDGET_SETTINGS:
            if receipt81.get(field) != reference32.get(field):
                raise ScoreError(f"{condition}: 81k setting {field} differs across conditions")
    reference81 = receipts81[CONDITIONS[0]]
    for condition in CONDITIONS[1:]:
        for field in SHARED_CROSS_BUDGET_SETTINGS:
            if receipts81[condition].get(field) != reference81.get(field):
                raise ScoreError(f"81k conditions differ in shared setting {field}")

    reference_base = base32[CONDITIONS[0]]["by_job_id"]
    reference_retry = retry81[CONDITIONS[0]]["by_job_id"]
    for condition in CONDITIONS:
        full_rows = base32[condition]["by_job_id"]
        retry_rows = retry81[condition]["by_job_id"]
        if set(retry_rows) - set(full_rows):
            raise ScoreError(f"{condition}: 81k retry contains jobs absent at 32k")
        for job_id, row in retry_rows.items():
            original = full_rows[job_id]
            for field in ("seed", "prompt_sha256", "prompt_token_ids_sha256"):
                if row[field] != original[field]:
                    raise ScoreError(f"{condition}/{job_id}: 32k and 81k {field} changed")
            if row["seed"] != reference_base[job_id]["seed"]:
                raise ScoreError(f"{condition}/{job_id}: condition seed differs")
            if row["prompt_sha256"] != reference_base[job_id]["prompt_sha256"]:
                raise ScoreError(f"{condition}/{job_id}: frozen prompt differs across conditions")
            if row["prompt_token_ids_sha256"] != reference_base[job_id]["prompt_token_ids_sha256"]:
                raise ScoreError(f"{condition}/{job_id}: tokenized prompt differs across conditions")
            if row["prompt_token_ids_sha256"] != reference_retry[job_id]["prompt_token_ids_sha256"]:
                raise ScoreError(f"{condition}/{job_id}: 81k tokenized prompt differs across arms")


def _extended_rollup(
    run_dir: Path,
    base32: dict[str, dict[str, Any]],
    retry81: dict[str, dict[str, Any]],
    capped_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    combined: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        rows: list[dict[str, Any]] = []
        for base_row in base32[condition]["jobs"]:
            job_id = base_row["job_id"]
            base_path = run_dir / f"{GROUP}-{condition}-{CAP32}" / f"{job_id}-0.json"
            source32 = {
                "path": str(base_path.resolve()),
                "sha256": base_row["raw_file_sha256"],
                "cap": CAP32,
                "context": CONTEXT32,
                "finish_reason": base_row["finish_reason"],
            }
            retry_record = retry81[condition]["by_job_id"].get(job_id)
            if job_id in capped_ids:
                if retry_record is None:
                    raise ScoreError(f"{condition}/{job_id}: missing union retry")
                retry_path = run_dir / f"{GROUP}-{condition}-{CAP81}" / f"{job_id}-0.json"
                retry_ids = retry81[condition]["raw_records"][job_id]["completion_ids"]
                base_ids = _read_json(base_path).get("completion_ids")
                if not isinstance(base_ids, list):
                    raise ScoreError(f"{base_path}: missing completion token IDs")
                prefix_identical = retry_ids[: len(base_ids)] == base_ids
                selected = dict(retry_record)
                selected_source = {
                    "path": str(retry_path.resolve()),
                    "sha256": retry_record["raw_file_sha256"],
                    "cap": CAP81,
                    "context": CONTEXT81,
                    "finish_reason": retry_record["finish_reason"],
                }
                retry_source = selected_source
            else:
                prefix_identical = None
                selected = dict(base_row)
                retry_source = None
                selected_source = source32
            selected.update(
                source_file=selected_source["path"],
                source_file_sha256=selected_source["sha256"],
                cap=selected_source["cap"],
                context=selected_source["context"],
                prefix_identical_to_32k=prefix_identical,
                source_32k=source32,
                source_81k=retry_source,
            )
            rows.append(selected)
            ledger.append(
                {
                    "condition": condition,
                    "job_id": job_id,
                    "source_32k": source32,
                    "source_81k": retry_source,
                    "selected_source": selected_source,
                    "prefix_identical_to_32k": prefix_identical,
                    "used_for_extended_budget_summary": selected_source["cap"],
                }
            )
        receipt_hashes = {
            "32k": base32[condition]["receipt_sha256"],
            "81k": retry81[condition]["receipt_sha256"] if capped_ids else None,
        }
        combined[condition] = {
            "condition": condition,
            "output_dir": str(run_dir.resolve()),
            "receipt": {"effective_budget_receipts": receipt_hashes},
            "receipt_sha256": canonical_json_hash(receipt_hashes),
            "jobs": rows,
            "by_job_id": {row["job_id"]: row for row in rows},
        }
    return combined, ledger


def _extended_summary(combined: dict[str, dict[str, Any]]) -> dict[str, Any]:
    conditions = {}
    for name, condition in combined.items():
        rows = condition["jobs"]
        conditions[name] = {
            "overall": _counts(rows),
            "per_source_id": {
                source_id: _counts([row for row in rows if row["source_id"] == source_id])
                for source_id in sorted({row["source_id"] for row in rows})
            },
            "per_transfer_group": {
                group: _counts([row for row in rows if row.get("transfer_group") == group])
                for group in sorted({row.get("transfer_group") for row in rows})
            },
            "jobs": rows,
        }
    paired = {}
    for left, right in itertools.combinations(combined, 2):
        a_by_id, b_by_id = combined[left]["by_job_id"], combined[right]["by_job_id"]
        wins, losses, ties, unparsed = [], [], [], []
        for job_id, left_row in a_by_id.items():
            a, b = left_row["numeric_status"], b_by_id[job_id]["numeric_status"]
            if a == "unparsed" or b == "unparsed":
                unparsed.append(job_id)
            elif a == b:
                ties.append(job_id)
            elif a == "correct":
                wins.append(job_id)
            else:
                losses.append(job_id)
        per_source = {}
        for source_id in sorted({row["source_id"] for row in combined[left]["jobs"]}):
            ids = {
                row["job_id"] for row in combined[left]["jobs"] if row["source_id"] == source_id
            }
            per_source[source_id] = {
                "wins": [job_id for job_id in wins if job_id in ids],
                "losses": [job_id for job_id in losses if job_id in ids],
                "ties": [job_id for job_id in ties if job_id in ids],
                "unparsed_pairs": [job_id for job_id in unparsed if job_id in ids],
            }
        paired[f"{left}_vs_{right}"] = {
            "paired_jobs": len(a_by_id),
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "unparsed_pairs": unparsed,
            "per_source_id": per_source,
        }
    return {"conditions": conditions, "paired_comparisons": paired}


def _receipt_provenance(
    run_dir: Path,
    receipts32: dict[str, dict[str, Any]],
    scored32: dict[str, dict[str, Any]],
    receipts81: dict[str, dict[str, Any]],
    scored81: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    fields = (*SHARED_CROSS_BUDGET_SETTINGS, "jobs_sha256", "cap", "context", "adapter", "adapter_sha256")
    result = {}
    for condition in CONDITIONS:
        result[condition] = {
            "32k": {
                "receipt_path": str((run_dir / f"{GROUP}-{condition}-{CAP32}" / "receipt.json").resolve()),
                "receipt_sha256": scored32[condition]["receipt_sha256"],
                "settings": {field: receipts32[condition].get(field) for field in fields},
            },
            "81k": (
                {
                    "receipt_path": str((run_dir / f"{GROUP}-{condition}-{CAP81}" / "receipt.json").resolve()),
                    "receipt_sha256": scored81[condition]["receipt_sha256"],
                    "settings": {field: receipts81[condition].get(field) for field in fields},
                }
                if condition in receipts81
                else None
            ),
        }
    return result


def score_extended_run(run_dir: Path, jobs_path: Path, answer_key_path: Path) -> dict[str, Any]:
    jobs_path, answer_key_path, run_dir = jobs_path.resolve(), answer_key_path.resolve(), run_dir.resolve()
    jobs, key_by_id = load_frozen_inputs(jobs_path, answer_key_path)
    run_receipt = _validate_run_root(run_dir, jobs_path)
    jobs_sha256 = sha256_file(jobs_path)

    scored32: dict[str, dict[str, Any]] = {}
    receipts32: dict[str, dict[str, Any]] = {}
    base_dirs = {}
    for condition in CONDITIONS:
        out_dir = run_dir / f"{GROUP}-{condition}-{CAP32}"
        scored, receipt = score_condition(condition, out_dir, jobs, key_by_id, jobs_sha256)
        if receipt.get("cap") != CAP32 or receipt.get("context") != CONTEXT32:
            raise ScoreError(f"{condition}: expected 32k/40,960 receipt")
        scored32[condition], receipts32[condition], base_dirs[condition] = scored, receipt, out_dir
    validate_shared_runs(scored32, receipts32)

    capped_ids = {
        row["job_id"]
        for condition in CONDITIONS
        for row in scored32[condition]["jobs"]
        if row["finish_reason"].lower() == "length"
    }
    required32_labels = {f"{GROUP}-{condition}-{CAP32}" for condition in CONDITIONS}
    completed = set(run_receipt.get("completed", []))
    if not required32_labels <= completed:
        raise ScoreError(f"run receipt is missing completed 32k conditions: {sorted(required32_labels-completed)}")

    scored81: dict[str, dict[str, Any]] = {}
    receipts81: dict[str, dict[str, Any]] = {}
    extended_jobs_path = run_dir / f"{GROUP}-extended-jobs.json"
    extended_manifest = run_receipt.get("extended_jobs", {}).get(GROUP)
    if capped_ids:
        if not isinstance(extended_manifest, dict) or not extended_jobs_path.is_file():
            raise ScoreError("32k length outputs require the frozen numeric extended-job manifest")
        expected_subset = [job for job in jobs if job["id"] in capped_ids]
        extended_jobs = _read_json(extended_jobs_path)
        if extended_jobs != expected_subset:
            raise ScoreError("numeric extended-job manifest does not match the 32k length-job union")
        extended_hash = sha256_file(extended_jobs_path)
        if extended_manifest.get("jobs_sha256") != extended_hash:
            raise ScoreError("run receipt extended-job hash does not match the subset manifest")
        if extended_manifest.get("ids") != sorted(capped_ids):
            raise ScoreError("run receipt extended IDs do not match the 32k length-job union")
        required81_labels = {f"{GROUP}-{condition}-{CAP81}" for condition in CONDITIONS}
        if not required81_labels <= completed:
            raise ScoreError(f"run receipt is missing completed 81k conditions: {sorted(required81_labels-completed)}")
        for condition in CONDITIONS:
            out_dir = run_dir / f"{GROUP}-{condition}-{CAP81}"
            scored81[condition] = _score_retry_condition(
                condition, out_dir, expected_subset, key_by_id, extended_hash
            )
            receipts81[condition] = scored81[condition]["receipt"]
        _validate_retries(scored32, scored81, receipts32, receipts81)
    elif extended_manifest:
        raise ScoreError("run receipt records numeric retries although no 32k job hit the length cap")

    combined, ledger = _extended_rollup(run_dir, scored32, scored81, capped_ids)
    score32 = build_summary(scored32)
    extended = _extended_summary(combined)
    return {
        "status": "complete",
        "scope": "Numeric exact-answer scoring only; reasoning validity is not assessed.",
        "run_receipt": {
            "path": str((run_dir / "receipt.json").resolve()),
            "sha256": sha256_file(run_dir / "receipt.json"),
            "status": run_receipt.get("status"),
        },
        "jobs_path": str(jobs_path),
        "jobs_sha256": jobs_sha256,
        "answer_key_path": str(answer_key_path),
        "answer_key_sha256": sha256_file(answer_key_path),
        "base_scoring": "score_numeric.score_condition + validate_shared_runs + grade_numeric_text",
        "condition_run_provenance": _receipt_provenance(
            run_dir, receipts32, scored32, receipts81, scored81
        ),
        "retry_union_ids": sorted(capped_ids),
        "retry_union_count": len(capped_ids),
        "numeric_32k": {
            "conditions": score32["conditions"],
            "paired_comparisons": score32["paired_comparisons"],
        },
        "extended_budget_24_job_summary": extended,
        "source_ledger": ledger,
        "extended_budget_natural_finish_counts": {
            condition: {
                "retry_jobs": len(scored81.get(condition, {}).get("jobs", [])),
                "natural_end": sum(
                    row["natural_end"] for row in scored81.get(condition, {}).get("jobs", [])
                ),
                "length_finish": sum(
                    row["finish_reason"].lower() == "length"
                    for row in scored81.get(condition, {}).get("jobs", [])
                ),
            }
            for condition in CONDITIONS
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--answer-key", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = score_extended_run(args.run_dir, args.jobs, args.answer_key)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix(args.out.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(args.out)
    print(json.dumps(report["extended_budget_natural_finish_counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
