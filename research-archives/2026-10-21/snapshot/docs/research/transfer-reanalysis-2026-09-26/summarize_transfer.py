#!/usr/bin/env python3
"""Summarize source-level and job-level exact-match changes from scored transfer results.

This script reads only the JSON report emitted by score_extended_numeric.py. It
does not read generation files, rerun scoring, or modify the scoring programs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CONDITIONS = ("base", "code128", "numeric128", "opd32")
REQUIRED_COMPARISONS = (
    ("base", "code128"),
    ("base", "numeric128"),
    ("base", "opd32"),
    ("code128", "numeric128"),
)
STATUS_ORDER = ("correct", "incorrect", "unparsed")


class SummaryError(ValueError):
    """The scored report does not match the expected complete schema."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_scores(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SummaryError(f"cannot read scored report {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("status") != "complete":
        raise SummaryError("--scores must be a complete score_extended_numeric.py JSON report")
    return value


def _validate_rows(condition: str, rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise SummaryError(f"{condition}: condition jobs must be a non-empty list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SummaryError(f"{condition}: a job row is not an object")
        job_id = row.get("job_id")
        if not isinstance(job_id, str) or job_id in seen:
            raise SummaryError(f"{condition}: missing or duplicate job_id {job_id!r}")
        seen.add(job_id)
        if not isinstance(row.get("source_id"), str):
            raise SummaryError(f"{condition}/{job_id}: missing source_id")
        if row.get("numeric_correct") not in (True, False, None):
            raise SummaryError(f"{condition}/{job_id}: invalid numeric_correct value")
        if row.get("numeric_status") not in STATUS_ORDER:
            raise SummaryError(f"{condition}/{job_id}: invalid numeric_status")
        if not isinstance(row.get("completion_tokens"), int):
            raise SummaryError(f"{condition}/{job_id}: missing completion token count")
        if not isinstance(row.get("finish_reason"), str):
            raise SummaryError(f"{condition}/{job_id}: missing finish reason")
        if row["numeric_correct"] is True and row["numeric_status"] != "correct":
            raise SummaryError(f"{condition}/{job_id}: correct flag and status disagree")
        if row["numeric_correct"] is False and row["numeric_status"] != "incorrect":
            raise SummaryError(f"{condition}/{job_id}: incorrect flag and status disagree")
        if row["numeric_correct"] is None and row["numeric_status"] != "unparsed":
            raise SummaryError(f"{condition}/{job_id}: unparsed flag and status disagree")
    return rows


def _success(row: dict[str, Any]) -> bool:
    """Main exact-match success is strictly numeric_correct is True."""
    return row.get("numeric_correct") is True


def _count_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    successes = sum(_success(row) for row in rows)
    statuses = Counter(row["numeric_status"] for row in rows)
    natural_end = sum(row.get("natural_end") is True for row in rows)
    length_finish = sum(row["finish_reason"].lower() == "length" for row in rows)
    tokens = [row["completion_tokens"] for row in rows]
    return {
        "jobs": total,
        "exact_match_successes": successes,
        "non_successes": total - successes,
        "exact_match_success_rate": successes / total if total else None,
        "numeric_status_counts": {status: statuses.get(status, 0) for status in STATUS_ORDER},
        "unparsed": statuses.get("unparsed", 0),
        "natural_end": natural_end,
        "completion_rate": natural_end / total if total else None,
        "length_finish": length_finish,
        "completion_tokens_mean": statistics.fmean(tokens) if tokens else None,
        "completion_tokens_max": max(tokens, default=None),
    }


def _score_by_source(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    rows_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_source[row["source_id"]].append(row)
    result: dict[str, dict[str, Any]] = {}
    for source_id, source_rows in sorted(rows_by_source.items()):
        if len(source_rows) != 2:
            raise SummaryError(f"{source_id}: expected two inference jobs, found {len(source_rows)}")
        replicates = {row.get("replicate") for row in source_rows}
        if replicates != {1, 2}:
            raise SummaryError(f"{source_id}: expected replicates 1 and 2, found {sorted(map(str, replicates))}")
        successes = sum(_success(row) for row in source_rows)
        result[source_id] = {
            "exact_match_successes": successes,
            "jobs": len(source_rows),
            "score": f"{successes}/2",
            "numeric_status_counts": {
                status: sum(row["numeric_status"] == status for row in source_rows)
                for status in STATUS_ORDER
            },
            "job_ids": [row["job_id"] for row in sorted(source_rows, key=lambda r: r["replicate"])],
            "seeds": [row["seed"] for row in sorted(source_rows, key=lambda r: r["replicate"])],
        }
    return result, rows_by_source


def _condition_summary(condition: str, condition_data: Any) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if not isinstance(condition_data, dict):
        raise SummaryError(f"{condition}: missing condition summary")
    rows = _validate_rows(condition, condition_data.get("jobs"))
    source_scores, rows_by_source = _score_by_source(rows)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        group = row.get("transfer_group")
        if not isinstance(group, str):
            raise SummaryError(f"{condition}/{row['job_id']}: missing transfer_group")
        groups[group].append(row)
    return ({
        "overall": _count_rows(rows),
        "source_id_scores": source_scores,
        "transfer_group_results": {
            group: _count_rows(group_rows) for group, group_rows in sorted(groups.items())
        },
    }, {job["job_id"]: job for job in rows})


def _paired_reference(paired: Any, left: str, right: str) -> dict[str, Any]:
    """Copy the scorer's both-parsed result, keeping its exclusion rule explicit."""
    if not isinstance(paired, dict):
        raise SummaryError("scored report is missing scorer paired comparisons")
    pair_key = f"{left}_vs_{right}"
    scorer_left, scorer_right = left, right
    row = paired.get(pair_key)
    reversed_pair = False
    if row is None:
        pair_key = f"{right}_vs_{left}"
        scorer_left, scorer_right = right, left
        row = paired.get(pair_key)
        reversed_pair = True
    if not isinstance(row, dict):
        raise SummaryError(f"scored report is missing paired comparison {left} vs {right}")
    left_wins = row.get("wins", [])
    right_wins = row.get("losses", [])
    if reversed_pair:
        left_wins, right_wins = right_wins, left_wins
    ties = row.get("ties", [])
    unparsed_pairs = row.get("unparsed_pairs", [])
    return {
        "metric_name": "score_extended_numeric paired_comparisons (both parsed only)",
        "exclusion_rule": "A job is omitted from wins/losses/ties when either condition is unparsed; it is listed under unparsed_pairs.",
        "requested_left_condition": left,
        "requested_right_condition": right,
        "source_pair_key": pair_key,
        "source_pair_orientation": {"left": scorer_left, "right": scorer_right},
        "left_wins": len(left_wins),
        "right_wins": len(right_wins),
        "ties": len(ties),
        "unparsed_pairs": len(unparsed_pairs),
        "left_win_job_ids": left_wins,
        "right_win_job_ids": right_wins,
        "tie_job_ids": ties,
        "unparsed_job_ids": unparsed_pairs,
    }


def _compare_conditions(
    left: str,
    right: str,
    left_jobs: dict[str, dict[str, Any]],
    right_jobs: dict[str, dict[str, Any]],
    left_source_scores: dict[str, dict[str, Any]],
    right_source_scores: dict[str, dict[str, Any]],
    scorer_pairs: dict[str, Any],
) -> dict[str, Any]:
    if set(left_jobs) != set(right_jobs):
        raise SummaryError(f"{left} and {right} job sets differ")
    if set(left_source_scores) != set(right_source_scores):
        raise SummaryError(f"{left} and {right} source configurations differ")
    source_deltas = {}
    improved, worsened, tied = [], [], []
    for source_id in sorted(left_source_scores):
        delta = (right_source_scores[source_id]["exact_match_successes"]
                 - left_source_scores[source_id]["exact_match_successes"])
        if delta > 0:
            improved.append(source_id)
        elif delta < 0:
            worsened.append(source_id)
        else:
            tied.append(source_id)
        source_deltas[source_id] = {
            "left_score": left_source_scores[source_id]["score"],
            "right_score": right_source_scores[source_id]["score"],
            "score_delta_right_minus_left": delta,
        }

    success_to_failure = []
    failure_to_success = []
    unchanged_success = []
    unchanged_non_success = []
    status_transitions: Counter[tuple[str, str]] = Counter()
    for job_id in sorted(left_jobs):
        left_row, right_row = left_jobs[job_id], right_jobs[job_id]
        left_success, right_success = _success(left_row), _success(right_row)
        status_transitions[(left_row["numeric_status"], right_row["numeric_status"])] += 1
        if left_success and not right_success:
            success_to_failure.append(job_id)
        elif not left_success and right_success:
            failure_to_success.append(job_id)
        elif left_success:
            unchanged_success.append(job_id)
        else:
            unchanged_non_success.append(job_id)

    return {
        "left_condition": left,
        "right_condition": right,
        "geometry_score_delta_definition": "right condition exact-match successes minus left condition exact-match successes, each out of 2 jobs per source_id",
        "geometry_score_differences": source_deltas,
        "improved_source_ids": improved,
        "worsened_source_ids": worsened,
        "unchanged_source_ids": tied,
        "improved_source_count": len(improved),
        "worsened_source_count": len(worsened),
        "unchanged_source_count": len(tied),
        "job_exact_match_transitions": {
            "definition": "Success is numeric_correct is True; incorrect and unparsed are both non-success for this transition metric.",
            "failure_to_success_count": len(failure_to_success),
            "failure_to_success_job_ids": failure_to_success,
            "success_to_failure_count": len(success_to_failure),
            "success_to_failure_job_ids": success_to_failure,
            "unchanged_success_count": len(unchanged_success),
            "unchanged_success_job_ids": unchanged_success,
            "unchanged_non_success_count": len(unchanged_non_success),
            "unchanged_non_success_job_ids": unchanged_non_success,
            "numeric_status_transition_counts": {
                f"{left_status}_to_{right_status}": status_transitions.get((left_status, right_status), 0)
                for left_status in STATUS_ORDER for right_status in STATUS_ORDER
            },
        },
        "scorer_paired_both_parsed_reference": _paired_reference(scorer_pairs, left, right),
    }


def _summarize_budget(budget_name: str, budget_data: Any) -> dict[str, Any]:
    if not isinstance(budget_data, dict) or not isinstance(budget_data.get("conditions"), dict):
        raise SummaryError(f"{budget_name}: missing condition summaries")
    source = budget_data["conditions"]
    missing_conditions = sorted(set(CONDITIONS) - set(source))
    if missing_conditions:
        raise SummaryError(f"{budget_name}: missing conditions {missing_conditions}")
    conditions = {}
    by_job_id = {}
    for condition in CONDITIONS:
        summary, job_map = _condition_summary(condition, source[condition])
        if by_job_id:
            reference_ids = set(next(iter(by_job_id.values())))
            if set(job_map) != reference_ids:
                raise SummaryError(f"{budget_name}/{condition}: job set differs across conditions")
        by_job_id[condition] = job_map
        conditions[condition] = summary
    source_sets = [set(conditions[condition]["source_id_scores"]) for condition in CONDITIONS]
    if any(source_set != source_sets[0] for source_set in source_sets[1:]):
        raise SummaryError(f"{budget_name}: source_id sets differ across conditions")
    if len(source_sets[0]) != 12:
        raise SummaryError(f"{budget_name}: expected 12 configurations, found {len(source_sets[0])}")
    job_total = len(by_job_id[CONDITIONS[0]])
    if job_total != 24:
        raise SummaryError(f"{budget_name}: expected 24 jobs, found {job_total}")

    base_source = conditions["base"]["source_id_scores"]
    geometry_table = []
    for source_id in sorted(source_sets[0]):
        transfer_groups = {by_job_id[condition][job_id].get("transfer_group")
                           for condition in CONDITIONS
                           for job_id in by_job_id[condition]
                           if by_job_id[condition][job_id]["source_id"] == source_id}
        if len(transfer_groups) != 1:
            raise SummaryError(f"{budget_name}/{source_id}: inconsistent transfer-group assignment")
        geometry_table.append({
            "source_id": source_id,
            "transfer_group": next(iter(transfer_groups)),
            "conditions": {
                condition: conditions[condition]["source_id_scores"][source_id]
                for condition in CONDITIONS
            },
        })

    comparisons = {}
    for left, right in REQUIRED_COMPARISONS:
        key = f"{left}_vs_{right}"
        comparisons[key] = _compare_conditions(
            left, right, by_job_id[left], by_job_id[right],
            conditions[left]["source_id_scores"], conditions[right]["source_id_scores"],
            budget_data.get("paired_comparisons"),
        )
    return {
        "budget": budget_name,
        "main_success_rule": "A job succeeds only when numeric_correct is exactly true.",
        "denominator_rule": "Every scored job remains in the denominator; incorrect and unparsed both count as non-success, with unparsed reported separately.",
        "conditions": conditions,
        "geometry_table": geometry_table,
        "condition_comparisons": comparisons,
    }


def summarize_report(scores: dict[str, Any], score_path: Path) -> dict[str, Any]:
    numeric_32k = scores.get("numeric_32k")
    extended = scores.get("extended_budget_24_job_summary")
    if not isinstance(numeric_32k, dict):
        raise SummaryError("score report missing numeric_32k section")
    if not isinstance(extended, dict):
        raise SummaryError("score report missing extended_budget_24_job_summary section")
    return {
        "schema_version": 1,
        "source_score_file": str(score_path.resolve()),
        "source_score_sha256": sha256_file(score_path),
        "budgets": {
            "32k": _summarize_budget("32k", numeric_32k),
            "extended_budget": _summarize_budget("extended_budget", extended),
        },
        "design_and_interpretation": {
            "evaluation_unit": "12 geometry configurations, each with two inference-seed jobs; this is not 24 independent problems.",
            "training_replication": "Each learned condition has a single training seed in this comparison.",
            "inferential_scope": "Descriptive exploratory counts only; no test or definitive significance decision is made.",
            "unparsed_rule": "For the primary exact-match success and transition metrics, only numeric_correct is True is success. Unparsed outputs remain non-successes in the full denominator and are separately counted.",
            "scorer_paired_comparison_distinction": "The scorer's paired_comparisons are reported separately and include wins/losses/ties only when both jobs were parsed. The all-job exact-match transitions above instead retain unparsed as non-success.",
            "transfer_groups": {
                "related_construction": "Related construction",
                "different_construction_or_composition": "Different construction or composition",
            },
        },
        "synthetic_check": run_synthetic_checks(),
    }


def run_synthetic_checks() -> dict[str, Any]:
    """Check two source configurations, one win/one loss, and unparsed failures."""
    source_rows = {
        "synthetic-related": {
            "base": ["unparsed", "incorrect"],
            "code128": ["correct", "incorrect"],
        },
        "synthetic-composition": {
            "base": ["correct", "incorrect"],
            "code128": ["unparsed", "incorrect"],
        },
    }
    left_jobs: dict[str, dict[str, Any]] = {}
    right_jobs: dict[str, dict[str, Any]] = {}
    left_source_scores = {}
    right_source_scores = {}
    for source_id, arms in source_rows.items():
        left_successes = 0
        right_successes = 0
        for replicate, (left_status, right_status) in enumerate(zip(arms["base"], arms["code128"]), 1):
            job_id = f"{source_id}-s{replicate}"
            left_success = left_status == "correct"
            right_success = right_status == "correct"
            left_successes += left_success
            right_successes += right_success
            left_jobs[job_id] = {"job_id": job_id, "source_id": source_id,
                                 "numeric_status": left_status, "numeric_correct": True if left_success else None if left_status == "unparsed" else False}
            right_jobs[job_id] = {"job_id": job_id, "source_id": source_id,
                                  "numeric_status": right_status, "numeric_correct": True if right_success else None if right_status == "unparsed" else False}
        left_source_scores[source_id] = {"exact_match_successes": left_successes, "score": f"{left_successes}/2"}
        right_source_scores[source_id] = {"exact_match_successes": right_successes, "score": f"{right_successes}/2"}
    comparison = _compare_conditions("base", "code128", left_jobs, right_jobs,
                                     left_source_scores, right_source_scores,
                                     {"base_vs_code128": {"wins": [], "losses": [], "ties": [], "unparsed_pairs": []}})
    transitions = comparison["job_exact_match_transitions"]
    passed = (
        comparison["improved_source_ids"] == ["synthetic-related"]
        and comparison["worsened_source_ids"] == ["synthetic-composition"]
        and comparison["unchanged_source_ids"] == []
        and transitions["failure_to_success_count"] == 1
        and transitions["success_to_failure_count"] == 1
        and transitions["unchanged_non_success_count"] == 2
        and transitions["numeric_status_transition_counts"]["unparsed_to_correct"] == 1
        and transitions["numeric_status_transition_counts"]["correct_to_unparsed"] == 1
    )
    if not passed:
        raise AssertionError(f"synthetic transfer checks failed: {comparison}")
    return {
        "passed": True,
        "synthetic_source_configurations": 2,
        "improved_source_count": comparison["improved_source_count"],
        "worsened_source_count": comparison["worsened_source_count"],
        "unchanged_source_count": comparison["unchanged_source_count"],
        "failure_to_success_jobs": transitions["failure_to_success_count"],
        "success_to_failure_jobs": transitions["success_to_failure_count"],
        "unchanged_non_success_jobs": transitions["unchanged_non_success_count"],
        "unparsed_counted_as_non_success": True,
        "note": "Synthetic only; the score_extended_numeric.py scorer retains the separate 24-job frozen-input validation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, required=True,
                        help="complete JSON report written by score_extended_numeric.py")
    parser.add_argument("--out", type=Path, required=True, help="summary JSON output path")
    args = parser.parse_args()
    score_path = args.scores.expanduser().resolve()
    scores = read_scores(score_path)
    report = summarize_report(scores, score_path)
    report["summary_script_sha256"] = sha256_file(Path(__file__).resolve())
    out_path = args.out.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "out": str(out_path),
        "summary_script_sha256": report["summary_script_sha256"],
        "source_score_sha256": report["source_score_sha256"],
        "budgets": {
            budget: {
                "conditions": {
                    condition: summary["overall"]["exact_match_successes"]
                    for condition, summary in data["conditions"].items()
                }
            }
            for budget, data in report["budgets"].items()
        },
        "synthetic_check_passed": report["synthetic_check"]["passed"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
