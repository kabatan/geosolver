"""Audit seven training-configuration code probes with the frozen numeric grader.

Usage: /usr/bin/python3 audit_probe.py RAW_OUTPUT_DIRECTORY [--out RESULT.json]
The omitted --out defaults to <script-dir>/<raw-directory-name>-audit.json.
Generated code is extracted and graded by the original isolated execution
harness against all 24 private final cases for each supported configuration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEGACY = ROOT / "docs/research/program-self-training-2026-09-26"
JOBS = HERE / "program-probe-jobs.json"
CASES = LEGACY / "numeric_cases_private.jsonl"

# Reuse the exact provenance and sandboxed program-evaluation implementations.
sys.path.insert(0, str(LEGACY))
from audit_evaluations import audit as audit_generation, read as read_json, sha  # noqa: E402
from execution_harness import evaluate_candidate, extract_program  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def supported_job_file(receipt: dict, explicit_jobs: Path | None = None) -> Path:
    """Identify which frozen probe job list produced this directory."""
    candidates = [explicit_jobs] if explicit_jobs else [JOBS, LEGACY / "program-probe-jobs.json"]
    for path in candidates:
        if path.exists() and sha(path) == receipt.get("jobs_sha256"):
            return path
    raise ValueError("receipt jobs_sha256 matches neither frozen probe job file")


def audit_probe(raw_dir: Path, explicit_jobs: Path | None = None) -> dict:
    raw_dir = raw_dir.resolve()
    receipt_path = raw_dir / "receipt.json"
    if not receipt_path.is_file():
        raise FileNotFoundError(receipt_path)
    receipt = read_json(receipt_path)
    if receipt.get("status") != "complete":
        raise ValueError(f"generation is not complete: {receipt.get('status')!r}")
    if receipt.get("samples") != 1:
        raise ValueError("the seven-configuration probe expects exactly one sample per job")

    provenance_jobs_path = supported_job_file(receipt, explicit_jobs)
    settings_keys = ("samples", "cap", "context", "temperature", "top_p", "top_k",
                     "presence_penalty", "thinking")
    settings = {key: receipt[key] for key in settings_keys}
    if ((settings['cap'], settings['context']) not in ((32768,73728),(81920,98304))
            or settings['temperature'] != 0.7 or settings['top_p'] != 0.95
            or settings['top_k'] != 20 or settings['presence_penalty'] != 0.2
            or settings['thinking'] is not False):
        raise ValueError('Probe generation differs from the frozen decoding recipe')
    adapter = Path(receipt["adapter"]) if receipt.get("adapter") else None
    generation_audit = audit_generation(raw_dir, provenance_jobs_path, settings, adapter)

    if adapter is None or not adapter.is_absolute():
        raise ValueError("a trained adapter path is required in the probe receipt")
    training_dir = adapter.parents[1]
    training_receipt_path = training_dir / "receipt.json"
    if not training_receipt_path.is_file():
        raise FileNotFoundError(training_receipt_path)
    training = read_json(training_receipt_path)
    if training.get("status") != "complete" or training.get("target_kind") not in ('code','numeric'):
        raise ValueError("probe adapter does not point to a completed SFT run")
    adapter_file = adapter / "adapter_model.safetensors"
    if sha(adapter_file) != training.get("vllm_adapter_sha256"):
        raise ValueError("probe adapter hash does not match its training receipt")

    target_jobs = read_json(JOBS)
    target_sources = [job["source_id"] for job in target_jobs]
    if len(target_sources) != 7 or len(set(target_sources)) != 7:
        raise ValueError("followup probe job file must contain seven distinct configurations")
    provenance_jobs = read_json(provenance_jobs_path)
    if explicit_jobs:
        frozen_by_id={job['id']:job for job in target_jobs}
        if (not provenance_jobs or len({j['id'] for j in provenance_jobs}) != len(provenance_jobs)
                or any(j['id'] not in frozen_by_id or j != frozen_by_id[j['id']] for j in provenance_jobs)):
            raise ValueError('Explicit retry jobs must be an exact nonempty subset of frozen jobs')
        if (settings['cap'],settings['context']) != (81920,98304):
            raise ValueError('Explicit subset is only allowed for the registered long retry')
        target_jobs=provenance_jobs
        target_sources=[job['source_id'] for job in target_jobs]
    provenance_by_source = {job["source_id"]: job for job in provenance_jobs}
    target_by_source = {job["source_id"]: job for job in target_jobs}
    for source in target_sources:
        old, target = provenance_by_source.get(source), target_by_source[source]
        if old is None or any(old[key] != target[key] for key in ("id", "seed", "messages")):
            raise ValueError(f"the {source} probe prompt/seed differs from its frozen followup job")

    raw_rows = []
    for path in sorted(raw_dir.glob("*.json")):
        row = read_json(path)
        if isinstance(row, dict) and "final_text" in row:
            raw_rows.append((path, row))
    rows_by_source = {}
    for path, row in raw_rows:
        rows_by_source.setdefault(row.get("source_id"), []).append((path, row))
    for source in target_sources:
        rows = rows_by_source.get(source, [])
        if len(rows) != 1:
            raise ValueError(f"expected one output for {source}, found {len(rows)}")
        path, row = rows[0]
        job = target_by_source[source]
        if (row.get("id") != job["id"] or row.get("sample") != 0
                or row.get("seed") != job["seed"] or row.get("messages") != job["messages"]
                or row.get("adapter") != str(adapter)):
            raise ValueError(f"output identity, sample, or prompt mismatch for {source}: {path.name}")

    cases = load_jsonl(CASES)
    final_cases = {}
    for source in target_sources:
        subset = [case for case in cases if case["source_id"] == source and case["split"] == "final"]
        if len(subset) != 24:
            raise ValueError(f"expected 24 frozen final cases for {source}, found {len(subset)}")
        final_cases[source] = subset

    records = []
    for source in target_sources:
        path, row = rows_by_source[source][0]
        record = {
            "id": row["id"], "source_id": source, "sample": row["sample"],
            "raw_file": str(path.resolve()), "raw_sha256": sha(path),
            "finish_reason": row["finish_reason"],
            "completion_tokens": len(row["completion_ids"]),
            "all_passed": False,
        }
        if row['finish_reason'] == 'length':
            record.update(status='censored',error='Generation reached its token cap; code not executed')
            records.append(record)
            continue
        try:
            extracted = extract_program(row["final_text"], row["finish_reason"])
        except (ValueError, SyntaxError) as exc:
            record.update(status="format_failure", error=str(exc))
        else:
            check = evaluate_candidate(extracted["normalized_code"], final_cases[source])
            record.update(
                status="pass" if check["all_passed"] else "fail",
                all_passed=check["all_passed"],
                extracted_program={key: extracted[key] for key in (
                    "code_sha256", "normalized_sha256", "selected_fence_index",
                    "closed_program_fences", "solve_definitions", "stripped_one_trailing_assistant_eos",
                    "finish_reason", "extraction_rule")},
                check=check,
            )
        records.append(record)

    ignored_sources = sorted(set(rows_by_source) - set(target_sources))
    result = {
        "status": "complete",
        "raw_dir": str(raw_dir),
        "generation": {
            "receipt_sha256": sha(receipt_path),
            "jobs_file_used_for_receipt": str(provenance_jobs_path),
            "jobs_sha256": receipt["jobs_sha256"],
            "settings": settings,
            "generation_audit": generation_audit,
            "adapter": str(adapter),
            "adapter_sha256": sha(adapter_file),
            "training_global_updates": training.get("global_updates"),
            "training_target_kind": training.get("target_kind"),
            "training_receipt": str(training_receipt_path),
        },
        "audit_wrapper": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha(Path(__file__).resolve()),
        },
        "grading": {
            "implementation": str(LEGACY / "execution_harness.py"),
            "case_file": str(CASES),
            "case_file_sha256": sha(CASES),
            "split": "final",
            "cases_per_configuration": 24,
            "numeric_tolerance": {"absolute": 1e-7, "relative": 1e-6},
            "execution": "same normalized-code extraction and bubblewrap-isolated evaluate_candidate used by pipeline.py final",
        },
        "summary": {
            "target_configurations": len(target_sources),
            "passed_configurations": sum(row["all_passed"] for row in records),
            "nonpassing_configurations": sum(not row["all_passed"] for row in records),
            "censored_configurations": sum(row['status']=='censored' for row in records),
            "mathematical_or_format_failures": sum(row['status'] in ('fail','format_failure') for row in records),
            "passed_sources": [row["source_id"] for row in records if row["all_passed"]],
            "failed_sources": [row["source_id"] for row in records if not row["all_passed"]],
            "ignored_out_of_scope_sources": ignored_sources,
        },
        "records": records,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_dir", type=Path, help="complete generation output directory")
    parser.add_argument("--out", type=Path, help="result JSON path; defaults beside this script")
    parser.add_argument("--jobs", type=Path, help="explicit frozen subset for an 81k retry")
    args = parser.parse_args()
    default_out = HERE / f"{args.raw_dir.name}-audit.json"
    out = (args.out or default_out).resolve()
    if out.exists():
        raise FileExistsError(out)
    result = audit_probe(args.raw_dir, args.jobs)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"result": str(out), **result["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
