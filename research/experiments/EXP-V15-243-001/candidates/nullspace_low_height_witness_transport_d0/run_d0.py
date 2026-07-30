#!/usr/bin/env python3
"""Fixed synthetic D0 for nullspace low-height witness transport."""

from __future__ import annotations

from fractions import Fraction
import json
import math
import random
from statistics import mean
from typing import Callable

from candidate import RunResult, System, run


SEED = 20260731
SCENARIOS = 32
TRANSFORMS = {
    "identity": ((1.0, 0.0), (0.0, 1.0)),
    "row-permutation": ((0.0, 1.0), (1.0, 0.0)),
    "row-scale": ((7.0, 0.0), (0.0, 0.2)),
    "row-rotation": (
        (math.cos(0.7), -math.sin(0.7)),
        (math.sin(0.7), math.cos(0.7)),
    ),
}
PRIMARY = ("affine-positive-dimensional", "curved-rational", "singular-narrow-guard")


def _apply(matrix, residual):
    return tuple(sum(row[index] * residual[index] for index in range(2)) for row in matrix)


def _system(base, guard, bounds, matrix) -> System:
    return System(
        residual=lambda point: _apply(matrix, base(point)),
        guard=guard,
        bounds=bounds,
    )


def _affine(rng: random.Random, matrix):
    constant = Fraction(rng.randint(-3, 3), rng.randint(1, 5))
    parameter = rng.uniform(-0.7, 0.7) + math.sqrt(2.0) * 1.0e-3
    exact = (float(constant) - 2.0 * parameter, parameter)
    initial = (exact[0] + rng.uniform(-1.0e-5, 1.0e-5), exact[1])
    base = lambda point: (
        point[0] + 2.0 * point[1] - float(constant),
        2.0 * (point[0] + 2.0 * point[1] - float(constant)),
    )
    guard = lambda point: -1.9 < point[0] < 1.9 and -0.9 < point[1] < 0.9
    return _system(base, guard, ((-1.9, 1.9), (-0.9, 0.9)), matrix), initial, constant


def _circle(rng: random.Random, matrix):
    theta = rng.uniform(0.45, 1.05)
    exact = (math.cos(theta), math.sin(theta))
    initial = (exact[0] * (1.0 + rng.uniform(-1.0e-5, 1.0e-5)), exact[1])
    base = lambda point: (
        point[0] * point[0] + point[1] * point[1] - 1.0,
        2.0 * (point[0] * point[0] + point[1] * point[1] - 1.0),
    )
    guard = lambda point: 0.05 < point[0] < 0.98 and 0.05 < point[1] < 0.98
    return _system(base, guard, ((0.05, 0.98), (0.05, 0.98)), matrix), initial, None


def _cusp(rng: random.Random, matrix):
    parameter = rng.uniform(0.09, 0.28)
    exact = (parameter * parameter, parameter**3)
    initial = (exact[0] + rng.uniform(-1.0e-7, 1.0e-7), exact[1])
    base = lambda point: (
        point[1] * point[1] - point[0] ** 3,
        3.0 * (point[1] * point[1] - point[0] ** 3),
    )
    guard = lambda point: 0.004 < point[0] < 0.09 and 0.0 < point[1] < 0.04
    return _system(base, guard, ((0.004, 0.09), (1.0e-7, 0.04)), matrix), initial, None


def _isolated(rng: random.Random, matrix):
    first = Fraction(rng.randint(-4, 4), rng.randint(1, 5))
    second = Fraction(rng.randint(-4, 4), rng.randint(1, 5))
    initial = (
        float(first) + rng.uniform(-1.0e-5, 1.0e-5),
        float(second) + rng.uniform(-1.0e-5, 1.0e-5),
    )
    base = lambda point: (point[0] - float(first), point[1] - float(second))
    guard = lambda point: -5.0 < point[0] < 5.0 and -5.0 < point[1] < 5.0
    return _system(base, guard, ((-5.0, 5.0), (-5.0, 5.0)), matrix), initial, (first, second)


def _irrational(rng: random.Random, matrix):
    parameter = rng.uniform(-0.7, 0.7) + math.pi * 1.0e-3
    initial = (math.sqrt(2.0) + rng.uniform(-1.0e-6, 1.0e-6), parameter)
    base = lambda point: (point[0] * point[0] - 2.0, 2.0 * (point[0] * point[0] - 2.0))
    guard = lambda point: point[0] > 0.0 and -0.8 < point[1] < 0.8
    return _system(base, guard, ((1.0, 2.0), (-0.8, 0.8)), matrix), initial, None


FAMILIES: dict[str, Callable] = {
    "affine-positive-dimensional": _affine,
    "curved-rational": _circle,
    "singular-narrow-guard": _cusp,
    "negative-isolated-full-rank": _isolated,
    "irrational-only": _irrational,
}


def _descriptor(value: float):
    rational = Fraction(value).limit_denominator(4096)
    if abs(value - float(rational)) <= 1.0e-10:
        return ("rational", rational)
    square = Fraction(value * value).limit_denominator(4096)
    if abs(value * value - float(square)) <= 1.0e-9:
        return ("sqrt", square, 1 if value >= 0.0 else -1)
    return None


def _recognizable(family: str, point, metadata) -> bool:
    left = _descriptor(point[0])
    right = _descriptor(point[1])
    if left is None or right is None:
        return False
    if family == "affine-positive-dimensional":
        if left[0] != "rational" or right[0] != "rational":
            return False
        return left[1] + 2 * right[1] == metadata
    if family == "curved-rational":
        left_square = left[1] ** 2 if left[0] == "rational" else left[1]
        right_square = right[1] ** 2 if right[0] == "rational" else right[1]
        return left_square + right_square == 1
    if family == "singular-narrow-guard":
        if left[0] != "rational":
            return False
        right_square = right[1] ** 2 if right[0] == "rational" else right[1]
        return right_square == left[1] ** 3 and point[1] > 0.0
    if family == "negative-isolated-full-rank":
        return (
            left[0] == "rational"
            and right[0] == "rational"
            and left[1] == metadata[0]
            and right[1] == metadata[1]
        )
    if family == "irrational-only":
        left_square = left[1] ** 2 if left[0] == "rational" else left[1]
        return left_square == 2 and right[0] == "rational"
    raise ValueError(family)


def _score(family: str, result: RunResult, metadata) -> int:
    return int(any(_recognizable(family, point, metadata) for point in result.accepted))


def run_campaign() -> dict[str, object]:
    rng = random.Random(SEED)
    family_rows = {
        family: {"control": [], "candidate": [], "activation": [], "invalid": []}
        for family in FAMILIES
    }
    transform_invariance_failures = 0
    baseline_mismatch = 0
    fallback_mismatch = 0
    trace_count = 0

    for family, generator in FAMILIES.items():
        for scenario in range(SCENARIOS):
            scenario_seed = rng.randrange(1 << 30)
            generator_seed = rng.randrange(1 << 30)
            per_transform = []
            for transform_name, matrix in TRANSFORMS.items():
                local = random.Random(generator_seed)
                system, initial, metadata = generator(local, matrix)
                control = run(system, initial, seed=scenario_seed, candidate=False)
                candidate = run(system, initial, seed=scenario_seed, candidate=True)
                trace_count += 2
                baseline_mismatch += int(
                    control.shared_baseline_signature
                    != candidate.shared_baseline_signature
                    or control.shared_baseline_accept_count
                    != candidate.shared_baseline_accept_count
                )
                fallback_mismatch += int(
                    family == "negative-isolated-full-rank"
                    and (
                        not candidate.fallback_used
                        or candidate.activated
                        or candidate.accepted != control.accepted
                    )
                )
                control_score = _score(family, control, metadata)
                candidate_score = _score(family, candidate, metadata)
                per_transform.append(
                    (candidate_score, candidate.activated, candidate.fallback_used)
                )
                row = family_rows[family]
                row["control"].append(control_score)
                row["candidate"].append(candidate_score)
                row["activation"].append(int(candidate.activated))
                row["invalid"].append(candidate.invalid_accept_count)
            transform_invariance_failures += int(len(set(per_transform)) != 1)

    results = {}
    improved_primary = 0
    residual_guard_regression = 0
    for family, row in family_rows.items():
        control_rate = mean(row["control"])
        candidate_rate = mean(row["candidate"])
        delta = candidate_rate - control_rate
        improved = family in PRIMARY and delta > 0.0
        improved_primary += int(improved)
        residual_guard_regression += sum(row["invalid"])
        results[family] = {
            "control_exact_recognizable_rate": control_rate,
            "candidate_exact_recognizable_rate": candidate_rate,
            "rate_delta": delta,
            "activation_rate": mean(row["activation"]),
            "invalid_accept_count": sum(row["invalid"]),
            "improved_primary": improved,
        }

    gate_pass = (
        improved_primary >= 2
        and residual_guard_regression == 0
        and baseline_mismatch == 0
        and fallback_mismatch == 0
        and transform_invariance_failures == 0
    )
    return {
        "schema": "geotarget.nullspace-low-height-witness-transport-d0/v1",
        "seed": SEED,
        "cpu": 15,
        "synthetic_only": True,
        "trace_count": trace_count,
        "family_results": results,
        "aggregate": {
            "primary_improved_family_count": improved_primary,
            "residual_guard_regression_count": residual_guard_regression,
            "shared_baseline_mismatch_count": baseline_mismatch,
            "fallback_mismatch_count": fallback_mismatch,
            "transform_invariance_failure_count": transform_invariance_failures,
            "baseline_quota": 0.75,
            "side_quota": 0.25,
            "decision": "ADVANCE" if gate_pass else "STOP",
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_campaign(), indent=2, sort_keys=True))
