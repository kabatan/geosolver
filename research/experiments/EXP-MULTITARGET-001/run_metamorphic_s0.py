#!/usr/bin/env python3
"""Truth-free counterexample and metamorphic S0 for the tail policy."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Callable, Sequence

import candidate


HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Endpoint:
    label: str
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float
    cluster_ordinal: int
    cluster_rank: int


class VirtualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _descriptor(root: int) -> dict[str, object]:
    return {
        "minimal_polynomial_high_to_low": [1, -root],
        "selected_real_root_index": 0,
    }


def _endpoint(
    label: str,
    point: Sequence[float],
    residual: Sequence[float],
    target: float,
    cluster: int,
    rank: int,
) -> Endpoint:
    values = tuple(float(value) for value in point)
    digest = hashlib.sha256(
        json.dumps(values, separators=(",", ":")).encode()
    ).hexdigest()
    return Endpoint(
        label=label,
        endpoint=values,
        endpoint_sha256=digest,
        residual_inf=max(abs(float(value)) for value in residual),
        provisional_target=float(target),
        cluster_ordinal=cluster,
        cluster_rank=rank,
    )


class GeneratedBase:
    FINALIZE_RESERVE_SECONDS = 2.0
    MIN_HP_ATTEMPT_SECONDS = 3.0
    MAX_HP_ATTEMPT_SECONDS = 18.0
    MAX_RESTORATION_ATTEMPT_SECONDS = 12.0

    def __init__(
        self,
        roots: dict[str, int],
        *,
        clock: VirtualClock | None = None,
        consume_full_timeout: bool = False,
    ) -> None:
        self.roots = roots
        self.clock = clock
        self.consume_full_timeout = consume_full_timeout
        self.trace: list[tuple[str, str, float]] = []

    @staticmethod
    def _configuration_distance(left: Endpoint, right: Endpoint) -> float:
        difference = math.sqrt(
            sum(
                (a - b) ** 2
                for a, b in zip(left.endpoint, right.endpoint, strict=True)
            )
        )
        denominator = math.sqrt(sum(value * value for value in left.endpoint))
        denominator += math.sqrt(sum(value * value for value in right.endpoint))
        return difference / max(denominator, 1.0)

    @staticmethod
    def _primary_tranche_capacity(remaining: float, count: int) -> int:
        return candidate._tranche_capacity(remaining, count, 18.0, 3.0)

    @staticmethod
    def _select_primary_tranche(items, capacity):
        ordered = tuple(
            sorted(
                items,
                key=lambda item: (
                    item[1].residual_inf,
                    item[1].endpoint_sha256,
                ),
            )
        )
        return ordered[:capacity], ordered[capacity:]

    @staticmethod
    def _wave_attempt_seconds(remaining: float, count: int, maximum: float) -> float:
        admitted = min(maximum, remaining - 3.0 * (count - 1))
        return admitted if admitted >= 3.0 else 0.0

    @staticmethod
    def _descriptor_key(descriptor):
        return json.dumps(descriptor, sort_keys=True, separators=(",", ":"))

    def _run_hp_candidate(self, **kwargs):
        item = kwargs["candidate"]
        seconds = float(kwargs["timeout_seconds"])
        self.trace.append(("hp", item.label, seconds))
        if self.consume_full_timeout:
            assert self.clock is not None
            self.clock.advance(seconds)
        return {
            "authority_pass": True,
            "descriptor": _descriptor(self.roots[item.label]),
        }

    def _run_restoration_candidate(self, **kwargs):
        item = kwargs["candidate"]
        seconds = float(kwargs["timeout_seconds"])
        self.trace.append(("restoration", item.label, seconds))
        if self.consume_full_timeout:
            assert self.clock is not None
            self.clock.advance(seconds)
        return {"authority_pass": False, "descriptor": None}


POINTS = {
    "a": (1.0, -2.0, 0.5),
    "b": (4.0, 1.5, -3.0),
    "c": (-5.0, 2.0, 7.0),
}
RESIDUALS = {
    "a": (1.0e-12, -2.0e-13, 5.0e-14),
    "b": (-2.0e-12, 7.0e-13, 1.0e-13),
    "c": (3.0e-12, -4.0e-13, 2.0e-13),
}
TARGETS = {"a": 0.0, "b": 2.0, "c": 9.0}
ROOTS = {"a": 1, "b": 2, "c": 3}


def _permuted_panel(
    variable_permutation: tuple[int, ...],
    residual_permutation: tuple[int, ...],
    target_transform: Callable[[float], float],
) -> tuple[Endpoint, ...]:
    return tuple(
        _endpoint(
            label,
            tuple(POINTS[label][index] for index in variable_permutation),
            tuple(RESIDUALS[label][index] for index in residual_permutation),
            target_transform(TARGETS[label]),
            ordinal,
            0,
        )
        for ordinal, label in enumerate(("a", "b", "c"))
    )


def _run_panel(items: Sequence[Endpoint]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    base = GeneratedBase(ROOTS)
    _attempts, descriptors, schedule = candidate.service_candidates(
        base,
        source=Path("truth-free-generated-source.json"),
        source_sha256=hashlib.sha256(b"truth-free-metamorphic-source").hexdigest(),
        candidates=items,
        cpu=0,
        output=Path("truth-free-generated-output"),
        hard_deadline=candidate.time.monotonic() + 60.0,
    )
    assert schedule["attempts_after_first_authority"] == 2
    trace = tuple(label for kind, label, _seconds in base.trace if kind == "hp")
    return trace, tuple(sorted(descriptors))


def _deadline_panel() -> dict[str, object]:
    primaries = tuple(
        _endpoint(
            f"p{index}",
            (float(index), float(index + 1)),
            (float(index + 1) * 1.0e-12,),
            float(index),
            index,
            0,
        )
        for index in range(3)
    )
    alternates = tuple(
        _endpoint(
            f"q{index}",
            (float(index) + 0.25, float(index + 1) + 0.5),
            (float(index + 4) * 1.0e-12,),
            float(index),
            index,
            1,
        )
        for index in range(3)
    )
    roots = {
        item.label: ordinal + 1
        for ordinal, item in enumerate((*primaries, *alternates))
    }
    clock = VirtualClock()
    base = GeneratedBase(roots, clock=clock, consume_full_timeout=True)
    original_monotonic = candidate.time.monotonic
    candidate.time.monotonic = clock.monotonic
    try:
        attempts, _descriptors, schedule = candidate.service_candidates(
            base,
            source=Path("truth-free-deadline-source.json"),
            source_sha256=hashlib.sha256(b"truth-free-deadline-source").hexdigest(),
            candidates=(*primaries, *alternates),
            cpu=0,
            output=Path("truth-free-deadline-output"),
            hard_deadline=30.0,
        )
    finally:
        candidate.time.monotonic = original_monotonic
    attempt_seconds = [seconds for _kind, _label, seconds in base.trace]
    return {
        "attempt_count": len(attempts),
        "attempt_seconds": attempt_seconds,
        "final_clock_seconds": clock.now,
        "hard_deadline_seconds": 30.0,
        "finalize_reserve_seconds": base.FINALIZE_RESERVE_SECONDS,
        "deadline_overrun": clock.now
        > 30.0 - base.FINALIZE_RESERVE_SECONDS + 1.0e-12,
        "minimum_attempt_seconds_held": all(
            seconds >= base.MIN_HP_ATTEMPT_SECONDS for seconds in attempt_seconds
        ),
        "attempts_after_first_authority": schedule["attempts_after_first_authority"],
    }


def _same_target_multiple_configurations() -> dict[str, object]:
    items = (
        _endpoint("same-primary", (1.0, 2.0), (1.0e-12,), 10.0, 0, 0),
        _endpoint("same-alternate", (20.0, -4.0), (2.0e-12,), 10.0, 0, 1),
    )
    roots = {"same-primary": 7, "same-alternate": 11}
    base = GeneratedBase(roots)
    attempts, descriptors, schedule = candidate.service_candidates(
        base,
        source=Path("truth-free-same-target-source.json"),
        source_sha256=hashlib.sha256(b"truth-free-same-target-source").hexdigest(),
        candidates=items,
        cpu=0,
        output=Path("truth-free-same-target-output"),
        hard_deadline=candidate.time.monotonic() + 40.0,
    )
    return {
        "configuration_count": len(items),
        "attempt_count": len(attempts),
        "distinct_descriptor_count": len(descriptors),
        "same_target_candidate_suppression": schedule[
            "same_target_candidate_suppression"
        ],
    }


def _case_branch_audit() -> dict[str, object]:
    forbidden = (
        "case_id",
        "problem_id",
        "family",
        "gold_target",
        "known_target_count",
        "answer_count",
        "benchmark_outcome",
    )
    condition_count = 0
    hits: list[dict[str, object]] = []
    for path in (HERE / "candidate.py", HERE / "worker.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.If, ast.IfExp, ast.While)):
                continue
            condition_count += 1
            condition = ast.get_source_segment(source, node.test) or ""
            lowered = condition.lower()
            matched = [term for term in forbidden if term in lowered]
            if matched:
                hits.append(
                    {
                        "file": path.name,
                        "line": node.lineno,
                        "terms": matched,
                    }
                )
    return {
        "conditional_count": condition_count,
        "forbidden_condition_hits": hits,
        "forbidden_terms": list(forbidden),
    }


def run() -> dict[str, object]:
    def identity(value: float) -> float:
        return value

    baseline_trace, baseline_descriptors = _run_panel(
        _permuted_panel((0, 1, 2), (0, 1, 2), identity)
    )
    affine_transforms = (
        (2.0, 7.0),
        (-3.0, 11.0),
        (0.125, -19.0),
        (-0.5, -3.25),
    )
    affine_mismatches = 0
    for scale, shift in affine_transforms:
        trace, descriptors = _run_panel(
            _permuted_panel(
                (0, 1, 2),
                (0, 1, 2),
                lambda value, a=scale, b=shift: a * value + b,
            )
        )
        affine_mismatches += int(
            trace != baseline_trace or descriptors != baseline_descriptors
        )

    variable_permutations = tuple(itertools.permutations(range(3)))
    variable_mismatches = 0
    for permutation in variable_permutations:
        trace, descriptors = _run_panel(
            _permuted_panel(permutation, (0, 1, 2), identity)
        )
        variable_mismatches += int(
            trace != baseline_trace or descriptors != baseline_descriptors
        )

    residual_permutations = tuple(itertools.permutations(range(3)))
    residual_mismatches = 0
    for permutation in residual_permutations:
        trace, descriptors = _run_panel(
            _permuted_panel((0, 1, 2), permutation, identity)
        )
        residual_mismatches += int(
            trace != baseline_trace or descriptors != baseline_descriptors
        )

    result = {
        "schema": "geotarget.exp-multitarget-001-metamorphic-s0/v1",
        "truth_or_gold_input": False,
        "baseline_trace": list(baseline_trace),
        "target_affine_transform_count": len(affine_transforms),
        "target_affine_trace_or_descriptor_mismatches": affine_mismatches,
        "variable_permutation_count": len(variable_permutations),
        "variable_permutation_trace_or_descriptor_mismatches": variable_mismatches,
        "residual_permutation_count": len(residual_permutations),
        "residual_permutation_trace_or_descriptor_mismatches": residual_mismatches,
        "same_target_multiple_configurations": _same_target_multiple_configurations(),
        "deadline_tail": _deadline_panel(),
        "case_specific_branch_audit": _case_branch_audit(),
        "tail_mechanism_sha256": hashlib.sha256(
            (HERE / "candidate.py").read_bytes()
        ).hexdigest(),
        "metamorphic_generator_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
    }
    assert affine_mismatches == variable_mismatches == residual_mismatches == 0
    same_target = result["same_target_multiple_configurations"]
    assert same_target == {
        "configuration_count": 2,
        "attempt_count": 2,
        "distinct_descriptor_count": 2,
        "same_target_candidate_suppression": False,
    }
    deadline = result["deadline_tail"]
    assert deadline["deadline_overrun"] is False
    assert deadline["minimum_attempt_seconds_held"] is True
    assert deadline["final_clock_seconds"] <= 28.0
    audit = result["case_specific_branch_audit"]
    assert audit["forbidden_condition_hits"] == []
    return result


def main() -> None:
    print(json.dumps(run(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
