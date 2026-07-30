#!/usr/bin/env python3
"""Truth-minimized family-disjoint three-fold paired run analysis.

Only the already-emitted OFFLINE_SCORE and truth-free TELEMETRY summaries are
read.  Fold assignment uses cluster sizes, never outcomes or timings.  The
normal report intentionally omits case and family identities.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from typing import Mapping, Sequence


FOLD_COUNT = 3
FAMILY_SUFFIX = re.compile(r"\([A-H]\)$")
SAFETY_STATUSES = {
    "EXTRA",
    "MISSING_AND_EXTRA",
    "DUPLICATE_DESCRIPTOR",
    "MALFORMED_OR_MISSING_RESULT",
    "WORKER_NOT_ACCEPTED",
    "TRUTH_DESCRIPTOR_ERROR",
}
HOLDOUT_PATH_TOKENS = ("validation", "sealed", "holdout")
CPU_WORKER_KEYS = (
    "worker_elapsed_cpu_seconds",
    "worker_cpu_seconds",
    "elapsed_cpu_seconds",
)
CPU_TELEMETRY_WORKER_PATHS = (
    ("worker_elapsed_cpu_seconds",),
    ("worker_cpu_seconds",),
    ("worker", "elapsed_cpu_seconds"),
    ("worker", "cpu_seconds"),
)
CPU_TELEMETRY_OUTER_PATHS = (
    ("outer_elapsed_cpu_seconds",),
    ("outer_cpu_seconds",),
    ("outer_process_cpu_seconds",),
)


@dataclass(frozen=True)
class CaseObservation:
    problem_id: str
    cluster: str
    exact: bool
    accepted: bool
    status: str
    wall_seconds: float
    wall_source: str
    cpu_seconds: float | None
    cpu_source: str


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def family(problem_id: str) -> str:
    """Match compare_runs.py's development-family clustering."""

    return FAMILY_SUFFIX.sub("", problem_id)


def _positive_float(value: object) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(converted) or converted <= 0.0:
        return None
    return converted


def _nested_value(document: Mapping[str, object], path: Sequence[str]) -> object:
    current: object = document
    for component in path:
        if not isinstance(current, Mapping) or component not in current:
            return None
        current = current[component]
    return current


def _first_positive(
    document: Mapping[str, object], paths: Sequence[Sequence[str]]
) -> float | None:
    for path in paths:
        value = _positive_float(_nested_value(document, path))
        if value is not None:
            return value
    return None


def _guard_development_path(path: Path) -> None:
    lowered = [part.lower() for part in path.expanduser().resolve().parts]
    for part in lowered:
        if any(token in part for token in HOLDOUT_PATH_TOKENS):
            raise ValueError(f"holdout-like input path is not accepted: {path}")


def resolve_run_files(path: Path) -> tuple[Path, Path]:
    """Resolve a run directory, OFFLINE_SCORE.json, or TELEMETRY.json."""

    _guard_development_path(path)
    resolved = path.expanduser().resolve()
    if resolved.is_dir():
        score = resolved / "OFFLINE_SCORE.json"
        telemetry = resolved / "TELEMETRY.json"
    elif resolved.name == "OFFLINE_SCORE.json":
        score = resolved
        telemetry = resolved.with_name("TELEMETRY.json")
    elif resolved.name == "TELEMETRY.json":
        telemetry = resolved
        score = resolved.with_name("OFFLINE_SCORE.json")
    else:
        raise ValueError(
            "input must be a run directory, OFFLINE_SCORE.json, or TELEMETRY.json"
        )
    if not score.is_file() or not telemetry.is_file():
        raise ValueError(f"paired score/telemetry files are unavailable under {resolved}")
    return score, telemetry


def _load_telemetry(path: Path) -> dict[int, Mapping[str, object]]:
    document = load_json(path)
    rows = document.get("rows") if isinstance(document, Mapping) else None
    if not isinstance(rows, list):
        raise ValueError(f"{path}: TELEMETRY.json has no rows")
    result: dict[int, Mapping[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{path}: malformed telemetry row")
        try:
            ordinal = int(row["ordinal"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{path}: malformed telemetry ordinal") from error
        if ordinal in result:
            raise ValueError(f"{path}: duplicate telemetry ordinal")
        result[ordinal] = row
    return result


def load_run(path: Path) -> dict[str, CaseObservation]:
    score_path, telemetry_path = resolve_run_files(path)
    score = load_json(score_path)
    rows = score.get("rows") if isinstance(score, Mapping) else None
    if not isinstance(rows, list):
        raise ValueError(f"{score_path}: OFFLINE_SCORE.json has no rows")
    telemetry = _load_telemetry(telemetry_path)
    result: dict[str, CaseObservation] = {}
    score_ordinals: set[int] = set()
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("problem_id"), str):
            raise ValueError(f"{score_path}: malformed score row")
        problem_id = str(row["problem_id"])
        if problem_id in result:
            raise ValueError(f"{score_path}: duplicate problem id")
        try:
            ordinal = int(row["index"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{score_path}: malformed score ordinal") from error
        if ordinal in score_ordinals:
            raise ValueError(f"{score_path}: duplicate score ordinal")
        score_ordinals.add(ordinal)
        telemetry_row = telemetry.get(ordinal)
        if telemetry_row is None:
            raise ValueError(f"{telemetry_path}: missing ordinal {ordinal}")

        # This is deliberately identical to compare_runs.py: prefer the
        # worker wall clock; use the outer elapsed clock for censored output.
        worker_wall = _positive_float(row.get("worker_elapsed_wall_seconds"))
        if worker_wall is not None:
            wall_seconds = worker_wall
            wall_source = "worker"
        else:
            outer_wall = _positive_float(telemetry_row.get("outer_elapsed_seconds"))
            if outer_wall is None:
                raise ValueError(f"{telemetry_path}: missing/non-positive censored time")
            wall_seconds = outer_wall
            wall_source = "outer_censored"

        worker_cpu = next(
            (
                value
                for key in CPU_WORKER_KEYS
                if (value := _positive_float(row.get(key))) is not None
            ),
            None,
        )
        if worker_cpu is None:
            worker_cpu = _first_positive(telemetry_row, CPU_TELEMETRY_WORKER_PATHS)
        if worker_cpu is not None:
            cpu_seconds = worker_cpu
            cpu_source = "worker"
        else:
            cpu_seconds = _first_positive(telemetry_row, CPU_TELEMETRY_OUTER_PATHS)
            cpu_source = "outer_censored" if cpu_seconds is not None else "unavailable"

        accepted_value = row.get("worker_accepted")
        if not isinstance(accepted_value, bool):
            accepted_value = telemetry_row.get("accepted")
        accepted = accepted_value is True
        result[problem_id] = CaseObservation(
            problem_id=problem_id,
            cluster=family(problem_id),
            exact=row.get("exact_set_equal") is True,
            accepted=accepted,
            status=str(row.get("status")),
            wall_seconds=wall_seconds,
            wall_source=wall_source,
            cpu_seconds=cpu_seconds,
            cpu_source=cpu_source,
        )
    if not result:
        raise ValueError(f"{score_path}: score rows are empty")
    if set(telemetry) != score_ordinals:
        raise ValueError(f"{telemetry_path}: score/telemetry ordinal sets differ")
    return result


def assign_folds(rows: Mapping[str, CaseObservation]) -> dict[str, int]:
    """Largest-cluster-first greedy balancing with a stable hash tie-break."""

    clusters: dict[str, list[str]] = defaultdict(list)
    for problem_id, row in rows.items():
        clusters[row.cluster].append(problem_id)
    ordered = sorted(
        clusters.items(),
        key=lambda item: (
            -len(item[1]),
            hashlib.sha256(item[0].encode("utf-8")).hexdigest(),
            item[0],
        ),
    )
    case_loads = [0] * FOLD_COUNT
    cluster_loads = [0] * FOLD_COUNT
    assignment: dict[str, int] = {}
    for _cluster, members in ordered:
        fold = min(
            range(FOLD_COUNT),
            key=lambda index: (case_loads[index], cluster_loads[index], index),
        )
        for problem_id in members:
            assignment[problem_id] = fold
        case_loads[fold] += len(members)
        cluster_loads[fold] += 1
    return assignment


def _geometric_mean(values: Sequence[float]) -> float:
    return math.exp(statistics.fmean(math.log(value) for value in values))


def _timing_summary(
    observations: Sequence[tuple[CaseObservation, CaseObservation]],
    *,
    metric: str,
) -> dict[str, object]:
    left_times: list[float] = []
    right_times: list[float] = []
    left_sources: Counter[str] = Counter()
    right_sources: Counter[str] = Counter()
    for left, right in observations:
        if metric == "wall":
            left_time, right_time = left.wall_seconds, right.wall_seconds
            left_source, right_source = left.wall_source, right.wall_source
        elif metric == "cpu":
            left_time, right_time = left.cpu_seconds, right.cpu_seconds
            left_source, right_source = left.cpu_source, right.cpu_source
        else:
            raise ValueError(metric)
        left_sources[left_source] += 1
        right_sources[right_source] += 1
        if left_time is None or right_time is None:
            continue
        left_times.append(left_time)
        right_times.append(right_time)
    available = len(left_times)
    result: dict[str, object] = {
        "available_pair_count": available,
        "unavailable_pair_count": len(observations) - available,
        "control_time_sources": dict(sorted(left_sources.items())),
        "candidate_time_sources": dict(sorted(right_sources.items())),
        "control_geometric_mean_seconds": None,
        "candidate_geometric_mean_seconds": None,
        "candidate_over_control_geometric_mean": None,
    }
    if available:
        result.update(
            {
                "control_geometric_mean_seconds": _geometric_mean(left_times),
                "candidate_geometric_mean_seconds": _geometric_mean(right_times),
                "candidate_over_control_geometric_mean": _geometric_mean(
                    [right / left for left, right in zip(left_times, right_times, strict=True)]
                ),
            }
        )
    return result


def _side_summary(rows: Sequence[CaseObservation]) -> dict[str, object]:
    safety = Counter(row.status for row in rows if row.status in SAFETY_STATUSES)
    accepted = sum(row.accepted for row in rows)
    return {
        "accepted_count": accepted,
        "not_accepted_count": len(rows) - accepted,
        "safety_failure_count": sum(safety.values()),
        "safety_status_counts": dict(sorted(safety.items())),
    }


def _fold_summary(
    fold: int,
    problem_ids: Sequence[str],
    control: Mapping[str, CaseObservation],
    candidate: Mapping[str, CaseObservation],
) -> dict[str, object]:
    pairs = [(control[problem_id], candidate[problem_id]) for problem_id in problem_ids]
    deltas = [int(right.exact) - int(left.exact) for left, right in pairs]
    wins = sum(delta > 0 for delta in deltas)
    losses = sum(delta < 0 for delta in deltas)
    ties = sum(delta == 0 for delta in deltas)
    cluster_count = len({left.cluster for left, _right in pairs})
    return {
        "fold": fold,
        "case_count": len(pairs),
        "family_cluster_count": cluster_count,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "net": wins - losses,
        "wins_exceed_losses": wins > losses,
        "control": _side_summary([left for left, _right in pairs]),
        "candidate": _side_summary([right for _left, right in pairs]),
        "time": {
            "wall": _timing_summary(pairs, metric="wall"),
            "cpu": _timing_summary(pairs, metric="cpu"),
        },
    }


def build_analysis(control_path: Path, candidate_path: Path) -> dict[str, object]:
    control = load_run(control_path)
    candidate = load_run(candidate_path)
    if set(control) != set(candidate):
        raise ValueError("paired runs contain different case identities")
    assignment = assign_folds(control)
    # Candidate identity must imply the same family partition independently.
    if any(control[key].cluster != candidate[key].cluster for key in control):
        raise ValueError("paired runs imply different family clusters")
    members = [
        sorted(key for key, fold in assignment.items() if fold == index)
        for index in range(FOLD_COUNT)
    ]
    folds = [
        _fold_summary(index + 1, members[index], control, candidate)
        for index in range(FOLD_COUNT)
    ]
    all_pairs = [(control[key], candidate[key]) for key in sorted(control)]
    wins = sum(right.exact and not left.exact for left, right in all_pairs)
    losses = sum(left.exact and not right.exact for left, right in all_pairs)
    ties = len(all_pairs) - wins - losses
    fold_wins = sum(bool(fold["wins_exceed_losses"]) for fold in folds)
    assignment_fingerprint = hashlib.sha256(
        json.dumps(
            sorted((control[key].cluster, assignment[key]) for key in control),
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "geotarget.exp-global-001-family-disjoint-fold-analysis/v1",
        "case_count": len(control),
        "family_cluster_count": len({row.cluster for row in control.values()}),
        "fold_count": FOLD_COUNT,
        "assignment_policy": (
            "largest family cluster first; descending size, SHA-256 family tie-break; "
            "assign to minimum case load, then cluster load, then fold ordinal"
        ),
        "assignment_uses_outcome_or_timing": False,
        "family_clusters_disjoint": True,
        "family_group_disjoint": True,
        "assignment_fingerprint_sha256": assignment_fingerprint,
        "timing_policy": {
            "wall": (
                "worker_elapsed_wall_seconds when positive; otherwise "
                "TELEMETRY.outer_elapsed_seconds as the deadline-censor fallback"
            ),
            "cpu": (
                "worker CPU when positive; otherwise outer CPU as the "
                "deadline-censor fallback; unavailable is explicit and never "
                "replaced by wall time"
            ),
        },
        "folds": folds,
        "overall": {
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "net": wins - losses,
            "control": _side_summary([left for left, _right in all_pairs]),
            "candidate": _side_summary([right for _left, right in all_pairs]),
            "time": {
                "wall": _timing_summary(all_pairs, metric="wall"),
                "cpu": _timing_summary(all_pairs, metric="cpu"),
            },
        },
        "cross_fold_gate": {
            "wins_exceed_losses_fold_count": fold_wins,
            "required_fold_count": 2,
            "wins_exceed_losses_in_at_least_2_folds": fold_wins >= 2,
        },
        "identity_disclosure": {
            "case_ids_in_report": False,
            "family_names_in_report": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    document = build_analysis(arguments.control, arguments.candidate)
    output = arguments.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{checksum}  {output.name}\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "fold_case_counts": [fold["case_count"] for fold in document["folds"]],
                "fold_nets": [fold["net"] for fold in document["folds"]],
                "wins_exceed_losses_in_at_least_2_folds": document["cross_fold_gate"][
                    "wins_exceed_losses_in_at_least_2_folds"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
