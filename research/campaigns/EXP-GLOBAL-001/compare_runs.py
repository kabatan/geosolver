#!/usr/bin/env python3
"""Compare paired development runs without dropping deadline-censored cases."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
from typing import Mapping, Sequence


FAMILY_SUFFIX = re.compile(r"\([A-H]\)$")
SAFETY_STATUSES = {
    "EXTRA",
    "MISSING_AND_EXTRA",
    "DUPLICATE_DESCRIPTOR",
    "MALFORMED_OR_MISSING_RESULT",
    "WORKER_NOT_ACCEPTED",
    "TRUTH_DESCRIPTOR_ERROR",
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def family(problem_id: str) -> str:
    return FAMILY_SUFFIX.sub("", problem_id)


def percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot take percentile of an empty sequence")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def exact_mcnemar(wins: int, losses: int) -> dict[str, float | int]:
    discordant = wins + losses
    if discordant == 0:
        return {"discordant": 0, "candidate_one_sided_p": 1.0, "two_sided_p": 1.0}
    smaller = min(wins, losses)
    lower_tail = sum(math.comb(discordant, index) for index in range(smaller + 1)) / (
        2**discordant
    )
    candidate_tail = sum(
        math.comb(discordant, index) for index in range(wins, discordant + 1)
    ) / (2**discordant)
    return {
        "discordant": discordant,
        "candidate_one_sided_p": candidate_tail,
        "two_sided_p": min(1.0, 2.0 * lower_tail),
    }


def load_run(root: Path) -> dict[str, dict[str, object]]:
    score = load_json(root / "OFFLINE_SCORE.json")
    rows = score.get("rows") if isinstance(score, Mapping) else None
    if not isinstance(rows, list):
        raise ValueError(f"{root}: OFFLINE_SCORE.json has no rows")
    telemetry = load_json(root / "TELEMETRY.json")
    telemetry_rows = telemetry.get("rows") if isinstance(telemetry, Mapping) else None
    if not isinstance(telemetry_rows, list):
        raise ValueError(f"{root}: TELEMETRY.json has no rows")
    outer_seconds_by_ordinal: dict[int, float] = {}
    for telemetry_row in telemetry_rows:
        if not isinstance(telemetry_row, Mapping):
            raise ValueError(f"{root}: malformed telemetry row")
        try:
            ordinal = int(telemetry_row["ordinal"])
            outer_seconds = float(telemetry_row["outer_elapsed_seconds"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{root}: malformed telemetry timing") from exc
        if ordinal in outer_seconds_by_ordinal or outer_seconds <= 0.0:
            raise ValueError(f"{root}: invalid telemetry timing")
        outer_seconds_by_ordinal[ordinal] = outer_seconds
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("problem_id"), str):
            raise ValueError(f"{root}: malformed score row")
        problem_id = str(row["problem_id"])
        if problem_id in result:
            raise ValueError(f"{root}: duplicate problem id")
        copied = dict(row)
        try:
            worker_seconds = float(copied.get("worker_elapsed_wall_seconds") or 0.0)
            ordinal = int(copied["index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{root}: malformed score timing") from exc
        if worker_seconds > 0.0:
            copied["_comparison_elapsed_seconds"] = worker_seconds
            copied["_comparison_time_source"] = "worker"
        else:
            outer_seconds = outer_seconds_by_ordinal.get(ordinal, 0.0)
            if outer_seconds <= 0.0:
                raise ValueError(f"{root}: missing/non-positive censored time")
            copied["_comparison_elapsed_seconds"] = outer_seconds
            copied["_comparison_time_source"] = "outer_censored"
        result[problem_id] = copied
    return result


def clustered_bootstrap(
    deltas: Mapping[str, Sequence[float]], *, resamples: int, seed: int
) -> dict[str, float | int]:
    family_means = {
        name: statistics.fmean(values) for name, values in deltas.items() if values
    }
    if not family_means:
        raise ValueError("no family observations")
    names = sorted(family_means)
    generator = random.Random(seed)
    samples = []
    for _ in range(resamples):
        samples.append(
            statistics.fmean(
                family_means[names[generator.randrange(len(names))]]
                for _ in range(len(names))
            )
        )
    return {
        "family_count": len(names),
        "resamples": resamples,
        "seed": seed,
        "point_estimate": statistics.fmean(family_means.values()),
        "lower_95": percentile(samples, 0.025),
        "upper_95": percentile(samples, 0.975),
    }


def safety_counts(rows: Mapping[str, Mapping[str, object]]) -> dict[str, int]:
    counts = Counter(str(row.get("status")) for row in rows.values())
    return {
        status: counts.get(status, 0)
        for status in sorted(SAFETY_STATUSES)
        if counts.get(status, 0)
    }


def compare_pair(
    control_root: Path,
    candidate_root: Path,
    *,
    resamples: int,
    bootstrap_seed: int,
) -> dict[str, object]:
    control = load_run(control_root)
    candidate = load_run(candidate_root)
    if set(control) != set(candidate):
        raise ValueError("paired runs contain different case identities")
    wins = losses = ties = 0
    control_solved = candidate_solved = 0
    family_deltas: dict[str, list[float]] = defaultdict(list)
    log_time_ratios = []
    control_times = []
    candidate_times = []
    rows = []
    for problem_id in sorted(control):
        left = control[problem_id]
        right = candidate[problem_id]
        left_ok = left.get("exact_set_equal") is True
        right_ok = right.get("exact_set_equal") is True
        control_solved += int(left_ok)
        candidate_solved += int(right_ok)
        delta = int(right_ok) - int(left_ok)
        family_deltas[family(problem_id)].append(float(delta))
        if delta > 0:
            wins += 1
        elif delta < 0:
            losses += 1
        else:
            ties += 1
        left_time = float(left["_comparison_elapsed_seconds"])
        right_time = float(right["_comparison_elapsed_seconds"])
        if left_time <= 0.0 or right_time <= 0.0:
            raise ValueError("paired run has a missing/non-positive worker time")
        control_times.append(left_time)
        candidate_times.append(right_time)
        log_time_ratios.append(math.log(right_time / left_time))
        rows.append(
            {
                "problem_id": problem_id,
                "family": family(problem_id),
                "control_exact": left_ok,
                "candidate_exact": right_ok,
                "delta": delta,
                "control_seconds": left_time,
                "candidate_seconds": right_time,
                "control_time_source": left["_comparison_time_source"],
                "candidate_time_source": right["_comparison_time_source"],
            }
        )
    count = len(control)
    bootstrap = clustered_bootstrap(
        family_deltas, resamples=resamples, seed=bootstrap_seed
    )
    candidate_safety = safety_counts(candidate)
    return {
        "case_count": count,
        "control_root": str(control_root.resolve()),
        "candidate_root": str(candidate_root.resolve()),
        "control_solved": control_solved,
        "candidate_solved": candidate_solved,
        "net_exact_delta": candidate_solved - control_solved,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "mcnemar": exact_mcnemar(wins, losses),
        "family_clustered_recall_delta": bootstrap,
        "candidate_safety_counts": candidate_safety,
        "time": {
            "control_median_seconds": statistics.median(control_times),
            "candidate_median_seconds": statistics.median(candidate_times),
            "control_p95_seconds": percentile(control_times, 0.95),
            "candidate_p95_seconds": percentile(candidate_times, 0.95),
            "candidate_over_control_geometric_mean": math.exp(
                statistics.fmean(log_time_ratios)
            ),
            "candidate_over_control_p95": percentile(candidate_times, 0.95)
            / percentile(control_times, 0.95),
            "control_total_seconds": sum(control_times),
            "candidate_total_seconds": sum(candidate_times),
        },
        "provisional_gates": {
            "safety_zero": not candidate_safety,
            "recall_positive": candidate_solved > control_solved,
            "wins_exceed_losses": wins > losses,
            "family_clustered_lower_nonnegative": bootstrap["lower_95"] >= 0.0,
            "speed_geomean_15_percent": math.exp(statistics.fmean(log_time_ratios))
            <= 0.85,
            "speed_p95_5_percent": percentile(candidate_times, 0.95)
            / percentile(control_times, 0.95)
            <= 0.95,
        },
        "rows": rows,
    }


def aggregate(pairs: Sequence[Mapping[str, object]]) -> dict[str, object]:
    net_by_seed = [int(pair["net_exact_delta"]) for pair in pairs]
    safety_zero = [not bool(pair["candidate_safety_counts"]) for pair in pairs]
    return {
        "pair_count": len(pairs),
        "positive_net_pair_count": sum(delta > 0 for delta in net_by_seed),
        "nonnegative_net_pair_count": sum(delta >= 0 for delta in net_by_seed),
        "all_safety_zero": all(safety_zero),
        "five_seed_recall_gate": (
            len(pairs) == 5
            and sum(delta > 0 for delta in net_by_seed) >= 4
            and all(safety_zero)
        ),
        "net_exact_deltas": net_by_seed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="append", type=Path, required=True)
    parser.add_argument("--candidate", action="append", type=Path, required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    arguments = parser.parse_args()
    if len(arguments.control) != len(arguments.candidate):
        raise SystemExit("--control and --candidate counts differ")
    if arguments.bootstrap_resamples < 1:
        raise SystemExit("--bootstrap-resamples must be positive")
    pairs = [
        compare_pair(
            control,
            candidate,
            resamples=arguments.bootstrap_resamples,
            bootstrap_seed=arguments.bootstrap_seed + ordinal,
        )
        for ordinal, (control, candidate) in enumerate(
            zip(arguments.control, arguments.candidate, strict=True)
        )
    ]
    document = {
        "schema_version": "geotarget.exp-global-001-paired-comparison/v1",
        "pairs": pairs,
        "aggregate": aggregate(pairs),
    }
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
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
