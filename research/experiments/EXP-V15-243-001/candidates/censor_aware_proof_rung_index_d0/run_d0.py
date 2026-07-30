#!/usr/bin/env python3
"""Fixed synthetic D0 for the disposable censor-aware proof-rung index."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
import math
import random
from statistics import mean
from typing import Callable, Sequence

from candidate import RunResult, TaskSpec, run


SEED = 20260731
SCENARIOS_PER_FAMILY = 64
STRATEGIES = ("fifo", "round-robin", "static-shortest", "censor-index")


def _heavy_tail(rng: random.Random) -> list[TaskSpec]:
    winners = set(rng.sample(range(14), 5))
    tasks = []
    for index in range(14):
        estimates = (rng.uniform(2.5, 6.5), rng.uniform(1.5, 4.5))
        durations = (
            (rng.uniform(0.2, 0.8), rng.uniform(0.2, 0.9))
            if index in winners
            else (rng.uniform(12.0, 30.0), rng.uniform(0.3, 1.2))
        )
        tasks.append(TaskSpec(estimates, durations, (True, True)))
    rng.shuffle(tasks)
    return tasks


def _late_success(rng: random.Random) -> list[TaskSpec]:
    winners = set(rng.sample(range(12), 4))
    tasks = []
    for index in range(12):
        estimates = (
            rng.uniform(1.5, 3.5),
            rng.uniform(3.0, 6.0),
            rng.uniform(2.0, 4.0),
        )
        durations = (
            (rng.uniform(0.2, 0.6), rng.uniform(0.2, 0.6), rng.uniform(3.0, 5.0))
            if index in winners
            else (rng.uniform(0.2, 0.6), rng.uniform(30.0, 60.0), rng.uniform(0.2, 0.6))
        )
        tasks.append(TaskSpec(estimates, durations, (True, True, True)))
    rng.shuffle(tasks)
    return tasks


def _all_fail(rng: random.Random) -> list[TaskSpec]:
    tasks = [
        TaskSpec(
            (rng.uniform(1.0, 7.0),),
            (rng.uniform(2.5, 6.0),),
            (False,),
        )
        for _ in range(16)
    ]
    rng.shuffle(tasks)
    return tasks


def _nonstationary(rng: random.Random) -> list[TaskSpec]:
    tasks = []
    for index in range(16):
        estimates = (rng.uniform(2.0, 4.0), rng.uniform(2.0, 4.0))
        durations = (
            (rng.uniform(0.2, 0.7), rng.uniform(30.0, 60.0))
            if index < 8
            else (rng.uniform(2.0, 4.0), rng.uniform(0.2, 0.6))
        )
        tasks.append(TaskSpec(estimates, durations, (True, True)))
    rng.shuffle(tasks)
    return tasks


FAMILIES: dict[str, Callable[[random.Random], list[TaskSpec]]] = {
    "heavy-tail": _heavy_tail,
    "late-success": _late_success,
    "all-fail": _all_fail,
    "nonstationary": _nonstationary,
}


def _safety(result: RunResult) -> list[str]:
    failures: list[str] = []
    if not math.isclose(result.baseline_reserved, 75.0):
        failures.append("baseline reservation changed")
    if not math.isclose(result.baseline_spent, 75.0):
        failures.append("ordinary baseline lost work")
    if not math.isclose(result.side_cap, 25.0):
        failures.append("side cap changed")
    if result.side_spent > result.side_cap + 1.0e-12:
        failures.append("side lane exceeded 25%")
    if result.terminal_resurrection_count:
        failures.append("terminal route resurrected")
    if result.future_fields_exposed_to_policy:
        failures.append("hidden future exposed to policy")
    if len(set(result.selections)) > result.eligible:
        failures.append("selection contained unknown task")
    return failures


def _hidden_twin(
    specs: Sequence[TaskSpec], result: RunResult, rng: random.Random
) -> tuple[list[TaskSpec], int]:
    preserve = min(8, len(result.selections))
    protected = set(result.selections[:preserve])
    twin: list[TaskSpec] = []
    for ordinal, spec in enumerate(specs):
        if ordinal in protected:
            twin.append(spec)
            continue
        durations = tuple(
            max(0.05, 9.0 / value + rng.uniform(0.01, 0.15))
            for value in spec.hidden_durations
        )
        success = tuple(not value for value in spec.hidden_success)
        twin.append(replace(spec, hidden_durations=durations, hidden_success=success))
    return twin, preserve


def _future_leak_failure(base: RunResult, twin: RunResult, preserve: int) -> bool:
    compare = preserve + int(preserve < len(base.selections))
    if twin.selections[:compare] != base.selections[:compare]:
        return True
    return preserve == len(base.selections) and twin.selections != base.selections


def run_campaign() -> dict[str, object]:
    rng = random.Random(SEED)
    values = {
        family: {
            strategy: {"certificates": [], "first_served": [], "spent": []}
            for strategy in STRATEGIES
        }
        for family in FAMILIES
    }
    baseline_hashes: set[str] = set()
    safety_failures: list[str] = []
    future_leak_count = 0
    trace_count = 0

    for family, generator in FAMILIES.items():
        for scenario in range(SCENARIOS_PER_FAMILY):
            specs = generator(rng)
            results: dict[str, RunResult] = {}
            for strategy in STRATEGIES:
                result = run(specs, strategy=strategy)
                results[strategy] = result
                trace_count += 1
                baseline_hashes.add(result.baseline_sha256)
                safety_failures.extend(
                    f"{family}:{scenario}:{strategy}:{failure}"
                    for failure in _safety(result)
                )
                bucket = values[family][strategy]
                bucket["certificates"].append(result.certificates)
                bucket["first_served"].append(result.first_served)
                bucket["spent"].append(result.side_spent)

            twin_specs, preserve = _hidden_twin(
                specs, results["censor-index"], rng
            )
            twin = run(twin_specs, strategy="censor-index")
            trace_count += 1
            baseline_hashes.add(twin.baseline_sha256)
            safety_failures.extend(
                f"{family}:{scenario}:hidden-twin:{failure}"
                for failure in _safety(twin)
            )
            future_leak_count += _future_leak_failure(
                results["censor-index"], twin, preserve
            )

    family_results: dict[str, object] = {}
    improved_families = 0
    certificate_regression_families = 0
    for family, strategies in values.items():
        summaries = {
            strategy: {
                "certificate_mean": mean(metrics["certificates"]),
                "first_served_mean": mean(metrics["first_served"]),
                "side_spent_mean": mean(metrics["spent"]),
            }
            for strategy, metrics in strategies.items()
        }
        candidate = summaries["censor-index"]
        comparators = [summaries[name] for name in STRATEGIES if name != "censor-index"]
        best_certificate = max(item["certificate_mean"] for item in comparators)
        best_service_at_top = max(
            item["first_served_mean"]
            for item in comparators
            if math.isclose(item["certificate_mean"], best_certificate)
        )
        certificate_delta = candidate["certificate_mean"] - best_certificate
        service_delta = candidate["first_served_mean"] - best_service_at_top
        improved = certificate_delta > 1.0e-12 or (
            math.isclose(certificate_delta, 0.0) and service_delta > 1.0e-12
        )
        improved_families += int(improved)
        certificate_regression_families += int(certificate_delta < -1.0e-12)
        family_results[family] = {
            "strategies": summaries,
            "certificate_delta_vs_best_comparator": certificate_delta,
            "first_service_delta_at_best_certificate": service_delta,
            "improved": improved,
        }

    baseline_loss = bool(safety_failures or len(baseline_hashes) != 1)
    gate_pass = improved_families >= 2 and not baseline_loss and future_leak_count == 0
    return {
        "schema": "geotarget.censor-aware-proof-rung-d0/v1",
        "seed": SEED,
        "cpu": 15,
        "synthetic_only": True,
        "family_count": len(FAMILIES),
        "scenario_count": len(FAMILIES) * SCENARIOS_PER_FAMILY,
        "trace_count": trace_count,
        "strategy_traces": len(FAMILIES) * SCENARIOS_PER_FAMILY * len(STRATEGIES),
        "hidden_future_twin_traces": len(FAMILIES) * SCENARIOS_PER_FAMILY,
        "family_results": family_results,
        "aggregate": {
            "improved_family_count": improved_families,
            "certificate_regression_family_count": certificate_regression_families,
            "baseline_loss": baseline_loss,
            "future_leak_count": future_leak_count,
            "safety_failure_count": len(safety_failures),
            "baseline_hash_count": len(baseline_hashes),
            "decision": "ADVANCE" if gate_pass else "STOP",
        },
        "safety_failures": safety_failures[:10],
    }


if __name__ == "__main__":
    print(json.dumps(run_campaign(), indent=2, sort_keys=True))
