#!/usr/bin/env python3
"""Evaluate frozen solver A1/B1/B2/A2 promotion evidence.

The analyzer reads only completed run artifacts.  Routing decisions remain in
the solver; problem identities are used here solely to pair offline evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

FAMILY_SUFFIX = re.compile(r"\([A-H]\)$")
SAFETY_STATUSES = {
    "EXTRA",
    "MISSING_AND_EXTRA",
    "DUPLICATE_DESCRIPTOR",
    "MALFORMED_OR_MISSING_RESULT",
    "WORKER_NOT_ACCEPTED",
    "TRUTH_DESCRIPTOR_ERROR",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot take a percentile of an empty sequence")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _positive_float(value: object, label: str) -> float:
    if not isinstance(value, int | float):
        raise ValueError(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{label} must be finite and positive")
    return result


def _descriptor_key(value: object) -> str:
    if not isinstance(value, Mapping):
        raise ValueError("exact descriptor is not an object")
    polynomial = value.get("minimal_polynomial_high_to_low")
    root = value.get("selected_real_root_index")
    if (
        not isinstance(polynomial, list)
        or not polynomial
        or not all(isinstance(coefficient, int) for coefficient in polynomial)
        or not isinstance(root, int)
    ):
        raise ValueError("exact descriptor has no canonical novelty key")
    return json.dumps([polynomial, root], separators=(",", ":"))


def _artifact_descriptors(root: Path, slug: str) -> frozenset[str]:
    value = _load_json(root / "artifacts" / slug / "RESULT.json")
    if not isinstance(value, Mapping):
        raise ValueError(f"{root}: malformed worker result for {slug}")
    descriptors = value.get("distinct_exact_target_descriptors")
    if descriptors is None:
        descriptors = value.get("distinct_exact_targets")
    if not isinstance(descriptors, list):
        raise ValueError(f"{root}: missing exact descriptors for {slug}")
    return frozenset(_descriptor_key(descriptor) for descriptor in descriptors)


def load_leg(root: Path) -> dict[str, dict[str, object]]:
    """Load paired truth-free timing and offline correctness from one leg."""

    result = _load_json(root / "RESULT.json")
    score = _load_json(root / "OFFLINE_SCORE.json")
    telemetry = _load_json(root / "TELEMETRY.json")
    if not all(isinstance(value, Mapping) for value in (result, score, telemetry)):
        raise ValueError(f"{root}: malformed top-level evidence")
    if result.get("status") != "COMPLETE" or score.get("status") != "COMPLETE":
        raise ValueError(f"{root}: leg is incomplete")
    result_rows = result.get("rows")
    score_rows = score.get("rows")
    telemetry_rows = telemetry.get("rows")
    if not all(isinstance(rows, list) for rows in (result_rows, score_rows, telemetry_rows)):
        raise ValueError(f"{root}: evidence rows are missing")

    result_by_index = {int(row["index"]): row for row in result_rows if isinstance(row, Mapping)}
    telemetry_by_index = {
        int(row["ordinal"]): row for row in telemetry_rows if isinstance(row, Mapping)
    }
    loaded: dict[str, dict[str, object]] = {}
    for score_row in score_rows:
        if not isinstance(score_row, Mapping):
            raise ValueError(f"{root}: malformed score row")
        index = int(score_row["index"])
        problem_id = str(score_row["problem_id"])
        run_row = result_by_index.get(index)
        metric = telemetry_by_index.get(index)
        if run_row is None or metric is None or str(run_row.get("problem_id")) != problem_id:
            raise ValueError(f"{root}: evidence identity mismatch at {index}")
        slug = run_row.get("slug")
        if not isinstance(slug, str) or problem_id in loaded:
            raise ValueError(f"{root}: missing slug or duplicate problem identity")
        wall_value = score_row.get("worker_elapsed_wall_seconds")
        if not isinstance(wall_value, int | float) or float(wall_value) <= 0.0:
            wall_value = metric.get("outer_elapsed_seconds")
        cpu_value = metric.get("outer_cpu_seconds")
        rss_value = metric.get("peak_rss_bytes")
        status = str(score_row.get("status"))
        loaded[problem_id] = {
            "descriptors": _artifact_descriptors(root, slug),
            "wall_seconds": _positive_float(wall_value, f"{root}:{problem_id}:wall"),
            "cpu_seconds": (
                _positive_float(cpu_value, f"{root}:{problem_id}:cpu")
                if cpu_value is not None
                else None
            ),
            "peak_rss_bytes": (
                int(rss_value)
                if isinstance(rss_value, int) and not isinstance(rss_value, bool) and rss_value > 0
                else None
            ),
            "accepted": run_row.get("accepted") is True,
            "status": status,
            "extra_identity_count": int(score_row.get("extra_identity_count") or 0),
            "returned_descriptor_error": score_row.get("returned_descriptor_error"),
            "truth_descriptor_error": score_row.get("truth_descriptor_error"),
        }
    if len(loaded) != len(score_rows) or len(loaded) != len(result_rows):
        raise ValueError(f"{root}: evidence cardinalities differ")
    return loaded


def _clustered_bootstrap_log_ratio(
    values: Mapping[str, Sequence[float]], *, resamples: int, seed: int
) -> dict[str, float | int]:
    family_means = {
        family: statistics.fmean(observations)
        for family, observations in values.items()
        if observations
    }
    if not family_means:
        raise ValueError("no family timing observations")
    names = sorted(family_means)
    generator = random.Random(seed)
    samples = [
        math.exp(
            statistics.fmean(family_means[names[generator.randrange(len(names))]] for _ in names)
        )
        for _ in range(resamples)
    ]
    return {
        "family_count": len(names),
        "resamples": resamples,
        "seed": seed,
        "geometric_mean_ratio": math.exp(statistics.fmean(family_means.values())),
        "lower_95": _percentile(samples, 0.025),
        "upper_95": _percentile(samples, 0.975),
    }


def analyze_abba_legs(
    legs: Sequence[Mapping[str, object]], *, bootstrap_resamples: int = 10_000, seed: int = 0
) -> dict[str, object]:
    """Analyze already-loaded legs grouped in strict A1/B1/B2/A2 order."""

    by_seed: dict[int, dict[str, Mapping[str, Mapping[str, object]]]] = defaultdict(dict)
    for leg in legs:
        leg_seed = int(leg["seed"])
        code = str(leg["code"])
        rows = leg.get("rows")
        if code not in {"a1", "b1", "b2", "a2"} or not isinstance(rows, Mapping):
            raise ValueError("invalid ABBA leg")
        if code in by_seed[leg_seed]:
            raise ValueError("duplicate ABBA leg")
        by_seed[leg_seed][code] = rows
    if not by_seed or any(set(group) != {"a1", "b1", "b2", "a2"} for group in by_seed.values()):
        raise ValueError("each seed must contain exactly A1/B1/B2/A2")

    lost: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    truth_outside: list[dict[str, object]] = []
    family_logs: dict[str, list[float]] = defaultdict(list)
    control_pair_times: list[float] = []
    candidate_pair_times: list[float] = []
    control_pair_cpu: list[float] = []
    candidate_pair_cpu: list[float] = []
    control_rss: list[int] = []
    candidate_rss: list[int] = []
    case_count = 0

    for leg_seed, group in sorted(by_seed.items()):
        case_ids = set(group["a1"])
        if any(set(rows) != case_ids for rows in group.values()):
            raise ValueError(f"seed {leg_seed}: case identities differ")
        case_count += len(case_ids)
        for problem_id in sorted(case_ids):
            rows = {code: group[code][problem_id] for code in group}
            control_union = set(rows["a1"]["descriptors"]) | set(rows["a2"]["descriptors"])
            candidate_union = set(rows["b1"]["descriptors"]) | set(rows["b2"]["descriptors"])
            missing = sorted(control_union - candidate_union)
            if missing:
                lost.append({"seed": leg_seed, "problem_id": problem_id, "descriptors": missing})
            for code in ("b1", "b2"):
                row = rows[code]
                if (
                    row.get("accepted") is not True
                    or str(row.get("status")) in SAFETY_STATUSES
                    or row.get("returned_descriptor_error") is not None
                    or row.get("truth_descriptor_error") is not None
                ):
                    failures.append({"seed": leg_seed, "problem_id": problem_id, "leg": code})
                if int(row.get("extra_identity_count") or 0) != 0:
                    truth_outside.append({"seed": leg_seed, "problem_id": problem_id, "leg": code})

            control_wall = math.sqrt(
                float(rows["a1"]["wall_seconds"]) * float(rows["a2"]["wall_seconds"])
            )
            candidate_wall = math.sqrt(
                float(rows["b1"]["wall_seconds"]) * float(rows["b2"]["wall_seconds"])
            )
            control_pair_times.append(control_wall)
            candidate_pair_times.append(candidate_wall)
            family_logs[FAMILY_SUFFIX.sub("", problem_id)].append(
                math.log(candidate_wall / control_wall)
            )

            cpu_values = [rows[code].get("cpu_seconds") for code in ("a1", "a2", "b1", "b2")]
            if all(isinstance(value, int | float) for value in cpu_values):
                control_pair_cpu.append(math.sqrt(float(cpu_values[0]) * float(cpu_values[1])))
                candidate_pair_cpu.append(math.sqrt(float(cpu_values[2]) * float(cpu_values[3])))
            control_rss.extend(
                int(rows[code]["peak_rss_bytes"])
                for code in ("a1", "a2")
                if isinstance(rows[code].get("peak_rss_bytes"), int)
            )
            candidate_rss.extend(
                int(rows[code]["peak_rss_bytes"])
                for code in ("b1", "b2")
                if isinstance(rows[code].get("peak_rss_bytes"), int)
            )

    bootstrap = _clustered_bootstrap_log_ratio(
        family_logs, resamples=bootstrap_resamples, seed=seed
    )
    p95_ratio = _percentile(candidate_pair_times, 0.95) / _percentile(control_pair_times, 0.95)
    cpu_ratio = (
        math.exp(
            statistics.fmean(
                math.log(candidate / control)
                for control, candidate in zip(control_pair_cpu, candidate_pair_cpu, strict=True)
            )
        )
        if control_pair_cpu
        else None
    )
    rss_p95_ratio = (
        _percentile(candidate_rss, 0.95) / _percentile(control_rss, 0.95)
        if control_rss and candidate_rss
        else None
    )
    correctness_passed = not lost and not failures and not truth_outside
    performance_passed = bool(
        bootstrap["upper_95"] < 1.0
        and p95_ratio <= 1.0
        and cpu_ratio is not None
        and cpu_ratio <= 1.0
    )
    return {
        "schema_version": "geotarget.geometry-kernel-solver-abba/v1",
        "seed_count": len(by_seed),
        "case_seed_count": case_count,
        "lost_descriptor_count": len(lost),
        "truth_outside_descriptor_run_count": len(truth_outside),
        "candidate_failure_count": len(failures),
        "lost_descriptors": lost,
        "truth_outside_descriptors": truth_outside,
        "candidate_failures": failures,
        "wall_family_clustered_bootstrap": bootstrap,
        "wall_p95_candidate_over_control": p95_ratio,
        "jobs1_cpu_geometric_mean_candidate_over_control": cpu_ratio,
        "jobs1_rss_p95_candidate_over_control": rss_p95_ratio,
        "correctness_gate_passed": correctness_passed,
        "performance_gate_passed_before_jobs7": performance_passed,
    }


def analyze_campaign(
    root: Path, *, bootstrap_resamples: int = 10_000, seed: int = 0
) -> dict[str, object]:
    manifest = _load_json(root / "S3_ABBA_ORCHESTRATION.json")
    if not isinstance(manifest, Mapping) or manifest.get("status") != "complete":
        raise ValueError("ABBA campaign is not complete")
    raw_legs = manifest.get("legs")
    if not isinstance(raw_legs, list):
        raise ValueError("ABBA campaign has no legs")
    legs: list[dict[str, object]] = []
    for leg in raw_legs:
        if not isinstance(leg, Mapping) or leg.get("status") != "completed":
            raise ValueError("ABBA campaign contains an incomplete leg")
        leg_id = str(leg.get("id"))
        match = re.fullmatch(r"seed-(\d+)-(a1|b1|b2|a2)-(control|candidate)", leg_id)
        if match is None:
            raise ValueError(f"invalid ABBA leg id: {leg_id}")
        output = Path(str(leg["output"])).expanduser().resolve()
        legs.append({"seed": int(match.group(1)), "code": match.group(2), "rows": load_leg(output)})
    report = analyze_abba_legs(legs, bootstrap_resamples=bootstrap_resamples, seed=seed)
    report["campaign_fingerprint"] = manifest.get("campaign_fingerprint")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    arguments = parser.parse_args(argv)
    if arguments.bootstrap_resamples < 1:
        raise SystemExit("--bootstrap-resamples must be positive")
    report = analyze_campaign(
        arguments.campaign.expanduser().resolve(),
        bootstrap_resamples=arguments.bootstrap_resamples,
        seed=arguments.bootstrap_seed,
    )
    output = arguments.output.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{checksum}  {output.name}\n", encoding="utf-8"
    )
    print(output)
    passed = bool(
        report["correctness_gate_passed"] and report["performance_gate_passed_before_jobs7"]
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
