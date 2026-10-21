#!/usr/bin/env python3
"""Summarize completed rounds from one or more formal OPD study directories.

This is a read-only aggregation of existing study artifacts. Numeric answer
grades apply the frozen numeric parser to the on-policy selected rollout and
the reference stored in selected-batch.json; they are descriptive diagnostics,
not an independent evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
SCORE_DIR = ROOT / "docs/research/transfer-reanalysis-2026-09-26"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCORE_DIR) not in sys.path:
    sys.path.insert(0, str(SCORE_DIR))

from score_numeric import grade_numeric_text  # noqa: E402
from qwen.answer_check import answers_equal, extract_answer, final_text  # noqa: E402


NATURAL_FINISH_REASONS = {"stop", "eos", "end_of_sequence"}
ROUND_RE = re.compile(r"^round-(\d{3,})$")
TRAINING_FINAL_VALUE_INSTRUCTION = "Write the solution in English and end with the exact value."


class IncompleteRound(Exception):
    """An artifact set does not yet describe a fully completed round."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IncompleteRound(f"cannot read {path.name}: {exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        result = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise IncompleteRound(f"invalid JSONL {path.name}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise IncompleteRound(f"non-object row in {path.name}:{line_number}")
            result.append(row)
        return result
    except OSError as exc:
        raise IncompleteRound(f"cannot read {path.name}: {exc}") from exc


def finite_numbers(values: Iterable[Any]) -> list[float]:
    result = []
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
            if math.isfinite(number):
                result.append(number)
    return result


def percentile(values: list[float], fraction: float) -> float | None:
    """Linear-interpolated percentile, matching common descriptive-statistic APIs."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def describe(values: Iterable[Any]) -> dict[str, Any]:
    numbers = finite_numbers(values)
    if not numbers:
        return {"n": 0, "mean": None, "median": None, "q1": None, "q3": None,
                "min": None, "max": None}
    return {
        "n": len(numbers),
        "mean": statistics.fmean(numbers),
        "median": statistics.median(numbers),
        "q1": percentile(numbers, 0.25),
        "q3": percentile(numbers, 0.75),
        "min": min(numbers),
        "max": max(numbers),
    }


def optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def natural_finish(value: Any) -> bool:
    return isinstance(value, str) and value.lower() in NATURAL_FINISH_REASONS


def grade_native_training_final_line(raw_text: str, expected: str) -> dict[str, Any]:
    """Grade only the final nonempty line, matching the training prompt's style."""
    visible_text = final_text(raw_text)
    lines = visible_text.splitlines() if visible_text else []
    final_line = next((line.strip() for line in reversed(lines) if line.strip()), None)
    extracted = extract_answer(final_line) if final_line is not None else None
    correct = answers_equal(extracted, expected)
    status = "unparsed" if correct is None else ("correct" if correct else "incorrect")
    return {
        "native_training_final_line": final_line,
        "native_training_final_line_extracted": extracted,
        "native_training_final_line_numeric_correct": correct,
        "native_training_final_line_numeric_status": status,
    }


def training_prompt_format(schedule: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Record the frozen prompt wording used for the first 128 scheduled examples."""
    rows = list(schedule.values())[:128]
    student_matches = 0
    teacher_matches = 0
    teacher_hint_matches = 0
    for row in rows:
        student_text = "\n".join(message.get("content", "") for message in row.get("student_messages", []))
        teacher_text = "\n".join(message.get("content", "") for message in row.get("teacher_messages", []))
        if TRAINING_FINAL_VALUE_INSTRUCTION in student_text:
            student_matches += 1
        if TRAINING_FINAL_VALUE_INSTRUCTION in teacher_text:
            teacher_matches += 1
        reference = row.get("reference")
        if isinstance(reference, str) and f"Verified exact numeric-answer hint: {reference}" in teacher_text:
            teacher_hint_matches += 1
    return {
        "source": "docs/research/answer-opd-pilot-2026-09-26/train-schedule.json",
        "scheduled_rows_checked": len(rows),
        "student_prompt_requirement": TRAINING_FINAL_VALUE_INSTRUCTION,
        "student_prompts_containing_requirement": student_matches,
        "teacher_prompts_containing_requirement": teacher_matches,
        "teacher_prompts_with_their_verified_answer_hint": teacher_hint_matches,
        "final_value_instruction_verified_for_all_rows": bool(rows) and student_matches == len(rows),
        "interpretation": (
            "The generation prompt asks for the exact value at the end, without requiring an Answer: or \\boxed marker. "
            "The native diagnostic parses only the final nonempty line as a numeric expression."
        ),
    }


def native_final_line_synthetic_checks() -> list[dict[str, Any]]:
    """Small regression checks for the deliberately narrow final-line parser."""
    cases = [
        {
            "name": "final_formula_line",
            "raw_text": "Reasoning.\nAnswer: 7\n\\frac{4\\sqrt{3441}}{93}",
            "expected": r"\frac{4\sqrt{3441}}{93}",
            "expected_native_status": "correct",
            "expected_explicit_status": "incorrect",
        },
        {
            "name": "unfinished_last_box",
            "raw_text": "Reasoning.\n\\boxed{40/11}\n\\boxed{40/11",
            "expected": "40/11",
            "expected_native_status": "unparsed",
            "expected_explicit_status": "unparsed",
        },
        {
            "name": "last_line_prose",
            "raw_text": "Reasoning.\n40/11\nThe exact value is 40/11.",
            "expected": "40/11",
            "expected_native_status": "unparsed",
            "expected_explicit_status": "unparsed",
        },
    ]
    results = []
    for case in cases:
        native = grade_native_training_final_line(case["raw_text"], case["expected"])
        explicit = grade_numeric_text(case["raw_text"], case["expected"])
        passed = (native["native_training_final_line_numeric_status"] == case["expected_native_status"]
                  and explicit["numeric_status"] == case["expected_explicit_status"])
        results.append({
            "name": case["name"],
            "native_status": native["native_training_final_line_numeric_status"],
            "expected_native_status": case["expected_native_status"],
            "explicit_answer_box_status": explicit["numeric_status"],
            "expected_explicit_status": case["expected_explicit_status"],
            "passed": passed,
        })
    if not all(row["passed"] for row in results):
        raise AssertionError(f"native final-line synthetic checks failed: {results}")
    return results


def load_schedule_map(study_receipt: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Load pass labels only from the frozen schedule named by the study receipt."""
    inputs = study_receipt.get("inputs")
    if not isinstance(inputs, dict):
        return {}, None
    for raw_path, expected_hash in inputs.items():
        path = Path(raw_path)
        if path.name != "train-schedule.json" or not path.is_file():
            continue
        try:
            actual_hash = sha256_file(path)
            if actual_hash != expected_hash:
                return {}, "train-schedule hash mismatch; pass labels unavailable"
            rows = read_json(path)
            if not isinstance(rows, list):
                return {}, "train-schedule is not a JSON list; pass labels unavailable"
            return ({row["id"]: row for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)},
                    str(path.resolve()))
        except (OSError, IncompleteRound, KeyError, TypeError):
            return {}, "train-schedule could not be read; pass labels unavailable"
    return {}, "train-schedule path unavailable; pass labels unavailable"


def resolve_rollout_receipt(round_dir: Path) -> Path:
    """Find the complete rollout receipt, including copied-resume round dirs."""
    candidates: list[Path] = [round_dir / "rollout32k" / "receipt.json"]
    provenance_path = round_dir / "selection-provenance.json"
    if provenance_path.is_file():
        try:
            provenance = read_json(provenance_path)
            if isinstance(provenance, dict):
                for value in provenance.values():
                    if isinstance(value, dict) and isinstance(value.get("raw_directory"), str):
                        candidates.append(Path(value["raw_directory"]) / "receipt.json")
        except IncompleteRound:
            pass
    unique = list(dict.fromkeys(path.expanduser().resolve() for path in candidates))
    complete_eight = []
    readable = []
    for candidate in unique:
        if not candidate.is_file():
            continue
        try:
            receipt = read_json(candidate)
        except IncompleteRound:
            continue
        readable.append(candidate)
        if receipt.get("status") == "complete" and optional_int(receipt.get("n_examples")) == 8:
            complete_eight.append(candidate)
    if complete_eight:
        return complete_eight[0]
    if readable:
        return readable[0]
    return unique[0]


def require_complete_round(study_dir: Path, round_dir: Path, round_number: int,
                           segment: str, schedule: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    train_dir = round_dir / "train"
    rollout_receipt_path = resolve_rollout_receipt(round_dir)
    train_receipt_path = train_dir / "receipt.json"
    selected_raw_path = round_dir / "selected-raw.json"
    selected_batch_path = round_dir / "selected-batch.json"
    examples_path = train_dir / "examples.jsonl"

    artifacts = [rollout_receipt_path, train_receipt_path, selected_raw_path,
                 selected_batch_path, examples_path]
    missing = [path.name for path in artifacts if not path.is_file()]
    if missing:
        raise IncompleteRound("missing " + ", ".join(missing))

    rollout_receipt = read_json(rollout_receipt_path)
    train_receipt = read_json(train_receipt_path)
    if rollout_receipt.get("status") != "complete":
        raise IncompleteRound("rollout receipt is not complete")
    if train_receipt.get("status") != "complete":
        raise IncompleteRound("train receipt is not complete")
    if optional_int(train_receipt.get("round")) != round_number:
        raise IncompleteRound("train receipt round does not match directory")
    if optional_int(train_receipt.get("n_examples")) != 8:
        raise IncompleteRound("trainer receipt does not report eight examples")
    if optional_int(train_receipt.get("updates")) != 2:
        raise IncompleteRound("trainer receipt does not report two updates")
    if optional_int(train_receipt.get("global_updates")) != 2 * round_number:
        raise IncompleteRound("trainer receipt global update count is unexpected")
    if optional_int(train_receipt.get("truncated_prefixes")) not in (0, None):
        raise IncompleteRound("trainer receipt reports truncated prefixes")

    raw_rows = read_json(selected_raw_path)
    batch = read_json(selected_batch_path)
    batch_rows = batch.get("examples") if isinstance(batch, dict) else None
    training_rows = read_jsonl(examples_path)
    if not isinstance(raw_rows, list) or not isinstance(batch_rows, list):
        raise IncompleteRound("selected raw or batch is not a row list")
    if len(raw_rows) != 8 or len(batch_rows) != 8 or len(training_rows) != 8:
        raise IncompleteRound("expected eight selected raw, batch, and training rows")

    def by_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
        if any(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in rows):
            raise IncompleteRound(f"{label} contains a row without an id")
        mapping = {row["id"]: row for row in rows}
        if len(mapping) != 8:
            raise IncompleteRound(f"{label} does not contain eight unique ids")
        return mapping

    raw_by_id = by_id(raw_rows, "selected-raw")
    batch_by_id = by_id(batch_rows, "selected-batch")
    train_by_id = by_id(training_rows, "train/examples.jsonl")
    if set(raw_by_id) != set(batch_by_id) or set(raw_by_id) != set(train_by_id):
        raise IncompleteRound("selected raw, batch, and training ids differ")
    if optional_int(rollout_receipt.get("n_examples")) != 8:
        raise IncompleteRound("rollout receipt does not report eight examples")
    if optional_int(batch.get("round")) not in (None, round_number):
        raise IncompleteRound("selected batch round does not match directory")

    finish_counts = Counter(str(raw_by_id[row_id].get("finish_reason", "unknown")).lower()
                            for row_id in raw_by_id)
    natural_count = sum(count for reason, count in finish_counts.items()
                        if reason in NATURAL_FINISH_REASONS)
    if natural_count != 8:
        raise IncompleteRound(f"only {natural_count}/8 selected rollouts ended naturally")

    trajectory_rows: list[dict[str, Any]] = []
    for row_id, raw in raw_by_id.items():
        batch_row = batch_by_id[row_id]
        train_row = train_by_id[row_id]
        raw_text = raw.get("raw_text")
        reference = batch_row.get("reference")
        if not isinstance(raw_text, str) or not isinstance(reference, str):
            raise IncompleteRound(f"missing raw text or batch reference for {row_id}")
        grade = grade_numeric_text(raw_text, reference)
        native_grade = grade_native_training_final_line(raw_text, reference)
        scheduled = schedule.get(row_id, {})
        pass_value = raw.get("pass", scheduled.get("pass"))
        trajectory_rows.append({
            "segment": segment,
            "study_dir": str(study_dir.resolve()),
            "round": round_number,
            "global_updates": train_receipt.get("global_updates"),
            "id": row_id,
            "source_id": raw.get("source_id", scheduled.get("source_id")),
            "variant": raw.get("variant", scheduled.get("variant")),
            "pass": pass_value,
            "source_condition_id": scheduled.get("source_condition_id"),
            "augmentation": scheduled.get("augmentation"),
            "seed": raw.get("seed", scheduled.get("seed")),
            "finish_reason": raw.get("finish_reason"),
            "natural_end": natural_finish(raw.get("finish_reason")),
            "completion_tokens": len(raw.get("completion_ids", []))
            if isinstance(raw.get("completion_ids"), list) else None,
            "trained_completion_tokens": train_row.get("trained_completion_tokens"),
            "reference": reference,
            "numeric_status": grade["numeric_status"],
            "numeric_correct": grade["numeric_correct"],
            "commit_marker": grade["commit_marker"],
            "answer_expression": grade["answer_expression"],
            "extracted_expression": grade["extracted_expression"],
            **native_grade,
            "kl": train_row.get("kl"),
            "kl_by_completion_quartile": train_row.get("kl_by_completion_quartile"),
            "completion_sha256": raw.get("completion_sha256"),
        })

    trained_tokens = optional_int(train_receipt.get("trained_completion_tokens"))
    example_token_values = [optional_int(row.get("trained_completion_tokens")) for row in training_rows]
    example_token_values = [value for value in example_token_values if value is not None]
    sum_example_tokens = sum(example_token_values) if len(example_token_values) == 8 else None
    kl_values = [row.get("kl") for row in training_rows]
    quartile_values: list[list[Any]] = [[] for _ in range(4)]
    for row in training_rows:
        values = row.get("kl_by_completion_quartile")
        if isinstance(values, list) and len(values) == 4:
            for index, value in enumerate(values):
                quartile_values[index].append(value)

    optimizer_path = train_dir / "optimizer.pt"
    optimizer_expected_hash = train_receipt.get("optimizer_sha256")
    optimizer_actual_hash = sha256_file(optimizer_path) if optimizer_path.is_file() else None
    optimizer_hash_matches = (optimizer_actual_hash == optimizer_expected_hash
                              if optimizer_actual_hash and isinstance(optimizer_expected_hash, str)
                              else False)
    global_updates = train_receipt.get("global_updates")
    saved_steps = train_receipt.get("optimizer_step_values_after")
    step_values_match = saved_steps == [global_updates]
    state_save_reload_equal = train_receipt.get("optimizer_state_save_reload_equal") is True
    optimizer_verified = optimizer_hash_matches and step_values_match and state_save_reload_equal

    paths_to_hash = [rollout_receipt_path, train_receipt_path, selected_raw_path,
                     selected_batch_path, examples_path]
    if optimizer_path.is_file():
        paths_to_hash.append(optimizer_path)
    hashes = {}
    for path in paths_to_hash:
        try:
            key = str(path.resolve().relative_to(study_dir.resolve()))
        except ValueError:
            key = str(path.resolve())
        hashes[key] = sha256_file(path)
    max_example_tokens = max(example_token_values, default=None)
    max_raw_tokens = max((row["completion_tokens"] for row in trajectory_rows
                          if isinstance(row.get("completion_tokens"), int)), default=None)
    receipt_peak_allocated = train_receipt.get("peak_allocated_gib")
    receipt_peak_reserved = train_receipt.get("peak_reserved_gib")
    example_peak_allocated = max(finite_numbers(row.get("peak_allocated_gib") for row in training_rows),
                                 default=None)
    example_peak_reserved = max(finite_numbers(row.get("peak_reserved_gib") for row in training_rows),
                                default=None)

    round_summary = {
        "segment": segment,
        "study_dir": str(study_dir.resolve()),
        "round": round_number,
        "global_updates": global_updates,
        "round_status": "complete",
        "examples": len(training_rows),
        "updates": train_receipt.get("updates"),
        "all_8_natural_end": natural_count == 8,
        "natural_end_count": natural_count,
        "finish_reason_counts": dict(sorted(finish_counts.items())),
        "trained_completion_tokens": trained_tokens,
        "trained_tokens_sum_from_examples": sum_example_tokens,
        "trained_token_counts_match": (trained_tokens == sum_example_tokens
                                        if trained_tokens is not None and sum_example_tokens is not None
                                        else None),
        "longest_trained_completion_tokens": max_example_tokens,
        "longest_selected_completion_tokens": max_raw_tokens,
        "optimizer_save_verification": {
            "verified": optimizer_verified,
            "file_present": optimizer_path.is_file(),
            "receipt_hash": optimizer_expected_hash,
            "actual_sha256": optimizer_actual_hash,
            "sha256_matches": optimizer_hash_matches,
            "state_save_reload_equal": state_save_reload_equal,
            "saved_state_entries": train_receipt.get("optimizer_state_entries"),
            "saved_step_values": saved_steps,
            "global_update_step_matches": step_values_match,
        },
        "peak_gpu_gib": {
            "allocated_receipt": receipt_peak_allocated,
            "reserved_receipt": receipt_peak_reserved,
            "allocated_examples_max": example_peak_allocated,
            "reserved_examples_max": example_peak_reserved,
        },
        "kl_descriptive": {
            "overall_per_example": describe(kl_values),
            "completion_quartiles_per_example": [
                {"quartile": index + 1, **describe(values)}
                for index, values in enumerate(quartile_values)
            ],
        },
        "numeric_diagnostic_counts": dict(sorted(Counter(
            row["numeric_status"] for row in trajectory_rows
        ).items())),
        "explicit_answer_box_diagnostic_counts": dict(sorted(Counter(
            row["numeric_status"] for row in trajectory_rows
        ).items())),
        "native_training_final_line_diagnostic_counts": dict(sorted(Counter(
            row["native_training_final_line_numeric_status"] for row in trajectory_rows
        ).items())),
        "artifact_sha256": hashes,
        "trajectory_rows": trajectory_rows,
    }
    return round_summary, trajectory_rows


def aggregate_rounds(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    ordered_rounds = sorted(rounds, key=lambda summary: summary["round"])
    trajectories = [row for summary in rounds for row in summary["trajectory_rows"]]
    quartiles: list[list[Any]] = [[] for _ in range(4)]
    for row in trajectories:
        values = row.get("kl_by_completion_quartile")
        if isinstance(values, list) and len(values) == 4:
            for index, value in enumerate(values):
                quartiles[index].append(value)
    statuses = Counter(row.get("numeric_status", "unparsed") for row in trajectories)
    native_statuses = Counter(row.get("native_training_final_line_numeric_status", "unparsed")
                              for row in trajectories)
    updates = sum(optional_int(summary.get("updates")) or 0 for summary in rounds)
    total_tokens = sum(optional_int(summary.get("trained_completion_tokens")) or 0
                       for summary in rounds)
    global_updates = [optional_int(summary.get("global_updates")) for summary in rounds]
    global_updates = [value for value in global_updates if value is not None]
    included_round_numbers = sorted({optional_int(summary.get("round")) for summary in rounds
                                     if optional_int(summary.get("round")) is not None})
    missing_round_numbers = (sorted(set(range(included_round_numbers[0], included_round_numbers[-1] + 1))
                                    - set(included_round_numbers))
                             if included_round_numbers else [])
    peak_allocated = finite_numbers(summary["peak_gpu_gib"].get("allocated_receipt")
                                    for summary in rounds)
    peak_reserved = finite_numbers(summary["peak_gpu_gib"].get("reserved_receipt")
                                   for summary in rounds)
    all_kl = [row.get("kl") for row in trajectories]
    adjacency_pairs = []
    for left, right in zip(ordered_rounds, ordered_rounds[1:]):
        left_round = optional_int(left.get("round"))
        right_round = optional_int(right.get("round"))
        left_updates = optional_int(left.get("global_updates"))
        right_updates = optional_int(right.get("global_updates"))
        if None in (left_round, right_round, left_updates, right_updates):
            continue
        expected_delta = 2 * (right_round - left_round)
        observed_delta = right_updates - left_updates
        adjacency_pairs.append({
            "from_round": left_round,
            "to_round": right_round,
            "from_global_updates": left_updates,
            "to_global_updates": right_updates,
            "rounds_apart": right_round - left_round,
            "expected_global_update_delta": expected_delta,
            "observed_global_update_delta": observed_delta,
            "passed": observed_delta == expected_delta,
        })
    return {
        "completed_rounds": len(rounds),
        "included_round_numbers": included_round_numbers,
        "missing_round_numbers_between_included": missing_round_numbers,
        "completed_examples": len(trajectories),
        "optimizer_updates_included": updates,
        "last_global_updates": max(global_updates, default=None),
        "global_update_adjacency_check": {
            "checked_pairs": len(adjacency_pairs),
            "all_passed": all(pair["passed"] for pair in adjacency_pairs),
            "pairs": adjacency_pairs,
        },
        "trained_completion_tokens": total_tokens,
        "longest_trained_completion_tokens": max(
            (summary.get("longest_trained_completion_tokens") for summary in rounds
             if isinstance(summary.get("longest_trained_completion_tokens"), int)), default=None),
        "longest_selected_completion_tokens": max(
            (summary.get("longest_selected_completion_tokens") for summary in rounds
             if isinstance(summary.get("longest_selected_completion_tokens"), int)), default=None),
        "all_natural_end_examples": sum(bool(row.get("natural_end")) for row in trajectories),
        "all_included_examples_natural_end": all(bool(row.get("natural_end")) for row in trajectories),
        "numeric_diagnostic_counts": {key: statuses.get(key, 0)
                                       for key in ("correct", "incorrect", "unparsed")},
        "explicit_answer_box_diagnostic_counts": {key: statuses.get(key, 0)
                                                  for key in ("correct", "incorrect", "unparsed")},
        "native_training_final_line_diagnostic_counts": {
            key: native_statuses.get(key, 0) for key in ("correct", "incorrect", "unparsed")
        },
        "optimizer_verified_rounds": sum(
            summary["optimizer_save_verification"].get("verified") is True for summary in rounds),
        "peak_gpu_gib": {
            "allocated_max": max(peak_allocated, default=None),
            "reserved_max": max(peak_reserved, default=None),
        },
        "kl_descriptive": {
            "overall_per_example": describe(all_kl),
            "completion_quartiles_per_example": [
                {"quartile": index + 1, **describe(values)}
                for index, values in enumerate(quartiles)
            ],
        },
    }


def source_variant_pass_rows(trajectories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for row in trajectories:
        grouped[(row.get("source_id"), row.get("variant"), row.get("pass"))].append(row)
    output = []
    for (source_id, variant, pass_value), rows in sorted(
            grouped.items(), key=lambda item: tuple("" if value is None else str(value)
                                                   for value in item[0])):
        quartiles: list[list[Any]] = [[] for _ in range(4)]
        for row in rows:
            values = row.get("kl_by_completion_quartile")
            if isinstance(values, list) and len(values) == 4:
                for index, value in enumerate(values):
                    quartiles[index].append(value)
        counts = Counter(row.get("numeric_status", "unparsed") for row in rows)
        native_counts = Counter(row.get("native_training_final_line_numeric_status", "unparsed")
                                for row in rows)
        output.append({
            "source_id": source_id,
            "variant": variant,
            "pass": pass_value,
            "source_condition_id": next((row.get("source_condition_id") for row in rows
                                          if row.get("source_condition_id") is not None), None),
            "augmentation": next((row.get("augmentation") for row in rows
                                  if row.get("augmentation") is not None), None),
            "examples": len(rows),
            "rounds": sorted({row["round"] for row in rows}),
            "segments": sorted({row["segment"] for row in rows}),
            "numeric_diagnostic_counts": {key: counts.get(key, 0)
                                           for key in ("correct", "incorrect", "unparsed")},
            "explicit_answer_box_diagnostic_counts": {key: counts.get(key, 0)
                                                      for key in ("correct", "incorrect", "unparsed")},
            "native_training_final_line_diagnostic_counts": {
                key: native_counts.get(key, 0) for key in ("correct", "incorrect", "unparsed")
            },
            "natural_end_count": sum(bool(row.get("natural_end")) for row in rows),
            "completion_tokens": describe(row.get("completion_tokens") for row in rows),
            "trained_completion_tokens": describe(row.get("trained_completion_tokens") for row in rows),
            "kl_descriptive": {
                "overall_per_example": describe(row.get("kl") for row in rows),
                "completion_quartiles_per_example": [
                    {"quartile": index + 1, **describe(values)}
                    for index, values in enumerate(quartiles)
                ],
            },
            "ids": [row.get("id") for row in rows],
        })
    return output


def summarize_study(study_dir: Path, study_index: int,
                    shared_schedule: dict[str, dict[str, Any]] | None = None,
                    shared_schedule_source: str | None = None
                    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    study_dir = study_dir.expanduser().resolve()
    segment = study_dir.name or f"study-{study_index:02d}"
    if not study_dir.is_dir():
        return ({"segment": segment, "study_dir": str(study_dir), "status": "unavailable",
                 "error": "study path is not a directory", "included_rounds": [],
                 "skipped_rounds": []}, [])
    receipt_path = study_dir / "receipt.json"
    if receipt_path.is_file():
        try:
            study_receipt = read_json(receipt_path)
        except IncompleteRound as exc:
            study_receipt = {}
            receipt_error = str(exc)
        else:
            receipt_error = None
    else:
        study_receipt = {}
        receipt_error = "study receipt unavailable"
    if segment in {"study", "formal"} or not segment:
        segment = f"study-{study_index:02d}:{segment or 'unnamed'}"
    schedule, schedule_source = load_schedule_map(study_receipt)
    if not schedule and shared_schedule:
        schedule = shared_schedule
        schedule_source = shared_schedule_source
    candidate_dirs = []
    for path in study_dir.iterdir():
        match = ROUND_RE.match(path.name)
        if match and path.is_dir():
            candidate_dirs.append((int(match.group(1)), path))
    candidate_dirs.sort()

    included = []
    skipped = []
    trajectories = []
    for round_number, round_dir in candidate_dirs:
        try:
            summary, rows = require_complete_round(study_dir, round_dir, round_number,
                                                   segment, schedule)
        except IncompleteRound as exc:
            skipped.append({"round": round_number, "reason": str(exc)})
            continue
        included.append(summary)
        trajectories.extend(rows)
    study_summary = {
        "segment": segment,
        "study_dir": str(study_dir),
        "status": study_receipt.get("status"),
        "start_round": study_receipt.get("start_round"),
        "end_round": study_receipt.get("end_round"),
        "receipt_rounds_completed": study_receipt.get("rounds_completed"),
        "receipt_global_updates": study_receipt.get("global_updates"),
        "root_receipt_sha256": sha256_file(receipt_path) if receipt_path.is_file() else None,
        "receipt_error": receipt_error,
        "train_schedule_source": schedule_source,
        "pass_label_note": None if schedule else "pass labels unavailable; see raw trajectory rows",
        "candidate_rounds": [number for number, _ in candidate_dirs],
        "included_rounds": [summary["round"] for summary in included],
        "skipped_rounds": skipped,
        "round_summaries": included,
    }
    if not schedule and schedule_source:
        study_summary["pass_label_note"] = "pass labels unavailable despite schedule path"
    elif schedule_source:
        study_summary["pass_label_note"] = "pass labels loaded from the hash-verified frozen train schedule"
    return study_summary, trajectories


def infer_round_number(round_dir: Path) -> int:
    match = re.search(r"round-?(\d+)", round_dir.name)
    if match:
        return int(match.group(1))
    train_receipt_path = round_dir / "train" / "receipt.json"
    if train_receipt_path.is_file():
        receipt = read_json(train_receipt_path)
        number = optional_int(receipt.get("round")) if isinstance(receipt, dict) else None
        if number is not None:
            return number
    raise IncompleteRound(f"cannot infer global round number from {round_dir}")


def summarize_round_dir(round_dir: Path, round_dir_index: int,
                        schedule: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    round_dir = round_dir.expanduser().resolve()
    segment = f"round-dir-{round_dir_index:02d}:{round_dir.name}"
    if not round_dir.is_dir():
        return ({"segment": segment, "study_dir": str(round_dir), "status": "unavailable",
                 "error": "round path is not a directory", "included_rounds": [],
                 "skipped_rounds": []}, [])
    try:
        round_number = infer_round_number(round_dir)
        summary, trajectories = require_complete_round(round_dir.parent, round_dir,
                                                       round_number, segment, schedule)
    except IncompleteRound as exc:
        round_number = None
        summary = None
        trajectories = []
        reason = str(exc)
    if summary is None:
        return ({"segment": segment, "study_dir": str(round_dir), "status": "manual_round_dir",
                 "candidate_rounds": [round_number] if round_number is not None else [],
                 "included_rounds": [],
                 "skipped_rounds": [{"round": round_number, "reason": reason}],
                 "round_summaries": []}, [])
    return ({"segment": segment, "study_dir": str(round_dir), "status": "manual_round_dir",
             "candidate_rounds": [round_number], "included_rounds": [round_number],
             "skipped_rounds": [], "round_summaries": [summary]}, trajectories)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", action="append", nargs="+", type=Path,
                        metavar="STUDY_DIR",
                        help="study output directory; repeat --study or pass several paths per option")
    parser.add_argument("--round-dir", action="append", nargs="+", type=Path,
                        metavar="ROUND_DIR",
                        help="completed round directory outside a study root, such as a resumed round")
    parser.add_argument("--out", required=True, type=Path, help="summary JSON output path")
    args = parser.parse_args()
    study_paths = [path for group in (args.study or []) for path in group]
    round_paths = [path for group in (args.round_dir or []) for path in group]
    if not study_paths and not round_paths:
        parser.error("provide at least one --study or --round-dir")

    shared_schedule: dict[str, dict[str, Any]] = {}
    shared_schedule_source = None
    for study_path in study_paths:
        receipt_path = study_path.expanduser().resolve() / "receipt.json"
        if not receipt_path.is_file():
            continue
        try:
            candidate, source = load_schedule_map(read_json(receipt_path))
        except IncompleteRound:
            continue
        if candidate:
            candidate_identity = {
                key: (row.get("source_id"), row.get("variant"), row.get("pass"), row.get("seed"))
                for key, row in candidate.items()
            }
            current_identity = {
                key: (row.get("source_id"), row.get("variant"), row.get("pass"), row.get("seed"))
                for key, row in shared_schedule.items()
            }
            if shared_schedule and candidate_identity != current_identity:
                parser.error("study inputs contain different frozen train schedules")
            if not shared_schedule:
                shared_schedule = candidate
                shared_schedule_source = source

    studies = []
    all_trajectories = []
    all_rounds = []
    for index, study_path in enumerate(study_paths, 1):
        study, trajectories = summarize_study(study_path, index, shared_schedule,
                                             shared_schedule_source)
        studies.append(study)
        all_trajectories.extend(trajectories)
        all_rounds.extend(study.get("round_summaries", []))
    for index, round_path in enumerate(round_paths, 1):
        study, trajectories = summarize_round_dir(round_path, index, shared_schedule)
        studies.append(study)
        all_trajectories.extend(trajectories)
        all_rounds.extend(study.get("round_summaries", []))

    seen_rounds: dict[int, str] = {}
    for summary in all_rounds:
        number = optional_int(summary.get("round"))
        if number is None:
            continue
        if number in seen_rounds:
            parser.error(f"round {number} would be counted twice: {seen_rounds[number]} and {summary['segment']}")
        seen_rounds[number] = summary["segment"]

    output = {
        "schema_version": 1,
        "created_from_existing_artifacts": True,
        "cli": {
            "study_dirs": [str(path.expanduser().resolve()) for path in study_paths],
            "round_dirs": [str(path.expanduser().resolve()) for path in round_paths],
            "out": str(args.out.expanduser().resolve()),
        },
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "interpretation_note": (
            "The explicit Answer/boxed diagnostic and native final-line diagnostic both use selected on-policy "
            "training rollouts and the reference from selected-batch.json. They are descriptive diagnostics only, "
            "not an independent evaluation or a fixed-test-loss trend. The native diagnostic parses only the last "
            "nonempty line, following the source prompt's request to end with the exact value. KL values are "
            "per-example training observations; quartile summaries describe the four completion segments and do "
            "not imply a learning effect."
        ),
        "training_prompt_format": training_prompt_format(shared_schedule),
        "native_final_line_synthetic_checks": native_final_line_synthetic_checks(),
        "studies": studies,
        "aggregate": aggregate_rounds(all_rounds),
        "source_variant_pass_rows": source_variant_pass_rows(all_trajectories),
        "trajectory_rows": all_trajectories,
    }
    out_path = args.out.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                        encoding="utf-8")
    output_hash = sha256_file(out_path)
    print(json.dumps({
        "out": str(out_path),
        "out_sha256": output_hash,
        "script_sha256": output["script_sha256"],
        "completed_rounds": output["aggregate"]["completed_rounds"],
        "completed_examples": output["aggregate"]["completed_examples"],
        "last_global_updates": output["aggregate"]["last_global_updates"],
        "included_round_numbers": output["aggregate"]["included_round_numbers"],
        "missing_round_numbers_between_included": output["aggregate"]["missing_round_numbers_between_included"],
        "global_update_adjacency_check": output["aggregate"]["global_update_adjacency_check"],
        "trained_completion_tokens": output["aggregate"]["trained_completion_tokens"],
        "longest_trained_completion_tokens": output["aggregate"]["longest_trained_completion_tokens"],
        "longest_selected_completion_tokens": output["aggregate"]["longest_selected_completion_tokens"],
        "numeric_diagnostic_counts": output["aggregate"]["numeric_diagnostic_counts"],
        "explicit_answer_box_diagnostic_counts": output["aggregate"]["explicit_answer_box_diagnostic_counts"],
        "native_training_final_line_diagnostic_counts": output["aggregate"]["native_training_final_line_diagnostic_counts"],
        "peak_gpu_gib": output["aggregate"]["peak_gpu_gib"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
