#!/usr/bin/env python3
"""Truth-free generated metamorphic and activation audit for the S1 overlay."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from typing import Callable, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
SHARED = HERE / "arms/shared"
ADAPTER_PATH = SHARED / "charted_search_adapter.py"
FULL_WORKER_PATH = SHARED / "full_worker.py"
AUDITED_SOURCES = (
    ADAPTER_PATH,
    SHARED / "charted_search_worker.py",
    FULL_WORKER_PATH,
    HERE / "arms/charted-weak-proposal/worker.py",
    HERE / "arms/adapted-cpqr-proposal/worker.py",
)
SENSITIVE_KEY = re.compile(
    r"^(?:case_id|problem_id|source_sha256|family|truth|gold|answer|expected_descriptor|"
    r"target_value|previous_outcome)$",
    re.IGNORECASE,
)
SOURCE_IDENTIFIER = re.compile(r"\bOMC[A-Z0-9_]*\d[A-Z0-9_]*\b")


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


ADAPTER = _load("audit_exp_rank_guard_001_adapter", ADAPTER_PATH)
FULL = _load("audit_exp_rank_guard_001_full", FULL_WORKER_PATH)


@dataclass(frozen=True)
class Observation:
    residual: np.ndarray
    finite: bool = True
    semantics_valid: bool = True


@dataclass(frozen=True)
class Prefix:
    points: tuple[np.ndarray, ...]
    sources: tuple[str, ...]
    scale_exponents: tuple[int | None, ...]
    literal_scales: tuple[float, ...]
    sha256: str
    activation: dict[str, object]


@dataclass(frozen=True)
class Outcome:
    counters: dict[str, int]


class FractionalLinearCase:
    """Rank-deficient square system expressed in normalized bound fractions."""

    dimension = 3

    def __init__(
        self,
        lower: Sequence[float],
        upper: Sequence[float],
        anchor_fraction: Sequence[float],
        *,
        variable_order: Sequence[int] = (0, 1, 2),
        residual_order: Sequence[int] = (0, 1, 2),
        nonsmooth: bool = False,
    ):
        self.lower = np.asarray(lower, dtype=float)
        self.upper = np.asarray(upper, dtype=float)
        self.anchor_fraction = np.asarray(anchor_fraction, dtype=float)
        self.variable_order = np.asarray(variable_order, dtype=int)
        self.residual_order = np.asarray(residual_order, dtype=int)
        self.nonsmooth = nonsmooth
        self.callbacks = 0
        physical_fraction = self.anchor_fraction[self.variable_order]
        self.anchor = self.lower + (self.upper - self.lower) * physical_fraction

    def canonical_fraction(self, point: Sequence[float]) -> np.ndarray:
        physical = (np.asarray(point) - self.lower) / (self.upper - self.lower)
        canonical = np.empty(self.dimension, dtype=float)
        canonical[self.variable_order] = physical
        return canonical

    def evaluate(self, point: Sequence[float]) -> Observation:
        self.callbacks += 1
        values = np.asarray(point, dtype=float)
        semantic = bool(
            np.all(np.isfinite(values))
            and np.all(values > self.lower)
            and np.all(values < self.upper)
        )
        delta = self.canonical_fraction(values) - self.anchor_fraction
        if self.nonsmooth:
            residual = np.abs(delta)
        else:
            residual = np.array([2.0 * delta[0], delta[1], 0.0 * delta[2]])
        return Observation(
            residual=residual[self.residual_order],
            finite=bool(np.all(np.isfinite(residual))),
            semantics_valid=semantic,
        )


class ChartLinearCase:
    """Rank-deficient system linear in mixed logit/softplus coordinates."""

    dimension = 3

    def __init__(self):
        self.lower = np.array([0.0, -np.inf, -2.0])
        self.upper = np.array([np.inf, 4.0, 3.0])
        self.anchor = np.array([0.125, 3.875, -1.999999999])
        self.anchor_chart = ADAPTER._to_chart(
            self.anchor, self.lower, self.upper
        )
        self.callbacks = 0

    def evaluate(self, point: Sequence[float]) -> Observation:
        self.callbacks += 1
        values = np.asarray(point, dtype=float)
        semantic = bool(
            np.all(np.isfinite(values))
            and np.all(values > self.lower)
            and np.all(values < self.upper)
        )
        delta = ADAPTER._to_chart(values, self.lower, self.upper) - self.anchor_chart
        residual = np.array([2.0 * delta[0], delta[1], 0.0 * delta[2]])
        return Observation(residual=residual, semantics_valid=semantic)


def _prefix(anchor: np.ndarray, count: int = 16) -> Prefix:
    return Prefix(
        points=tuple(np.asarray(anchor, dtype=float).copy() for _ in range(count)),
        sources=tuple(f"baseline-{ordinal}" for ordinal in range(count)),
        scale_exponents=tuple(0 for _ in range(count)),
        literal_scales=tuple(1.0 for _ in range(count)),
        sha256="generated-baseline",
        activation={"generated": True},
    )


def _run_overlay(case: object) -> tuple[Prefix, dict[str, int]]:
    candidate, telemetry = ADAPTER._overlay_prefix(
        case,
        _prefix(np.asarray(case.anchor, dtype=float)),
        callback_cap=512,
        callbacks_per_start=32,
    )
    return candidate, telemetry


def _generated_points(prefix: Prefix) -> list[np.ndarray]:
    return [
        np.asarray(point, dtype=float)
        for point, source in zip(prefix.points, prefix.sources)
        if source == "rank_guard_charted_weak_pair"
    ]


def _sorted_rows(points: Sequence[np.ndarray]) -> np.ndarray:
    if not points:
        return np.empty((0, 0), dtype=float)
    rounded = [tuple(float(value) for value in point) for point in points]
    return np.asarray(sorted(rounded), dtype=float)


def _max_row_distance(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        return math.inf
    if left.size == 0:
        return 0.0
    return float(np.max(np.linalg.norm(left - right, axis=1)))


def _metamorphic_audit() -> dict[str, object]:
    anchor_fraction = np.array([0.4, 0.55, 0.6])
    baseline_case = FractionalLinearCase(
        [-2.0, -3.0, -4.0], [2.0, 5.0, 6.0], anchor_fraction
    )
    baseline_prefix, baseline_telemetry = _run_overlay(baseline_case)
    baseline_points = _sorted_rows(
        [
            baseline_case.canonical_fraction(point)
            for point in _generated_points(baseline_prefix)
        ]
    )
    if baseline_telemetry["rank_guard_overlay_activated"] != 1:
        raise RuntimeError("generated rank-deficient baseline did not activate")

    variable_case = FractionalLinearCase(
        [-8.0, 10.0, -1.0],
        [12.0, 30.0, 9.0],
        anchor_fraction,
        variable_order=(2, 0, 1),
    )
    variable_prefix, variable_telemetry = _run_overlay(variable_case)
    variable_points = _sorted_rows(
        [
            variable_case.canonical_fraction(point)
            for point in _generated_points(variable_prefix)
        ]
    )

    residual_case = FractionalLinearCase(
        [-2.0, -3.0, -4.0],
        [2.0, 5.0, 6.0],
        anchor_fraction,
        residual_order=(2, 0, 1),
    )
    residual_prefix, residual_telemetry = _run_overlay(residual_case)
    residual_points = _sorted_rows(
        [
            residual_case.canonical_fraction(point)
            for point in _generated_points(residual_prefix)
        ]
    )

    scaled_case = FractionalLinearCase(
        [101.0, -0.25, -900.0],
        [117.0, 0.75, 1100.0],
        anchor_fraction,
    )
    scaled_prefix, scaled_telemetry = _run_overlay(scaled_case)
    scaled_points = _sorted_rows(
        [
            scaled_case.canonical_fraction(point)
            for point in _generated_points(scaled_prefix)
        ]
    )

    tolerance = 2.0e-8
    distances = {
        "variable_permutation_max_normalized_distance": _max_row_distance(
            baseline_points, variable_points
        ),
        "residual_permutation_max_normalized_distance": _max_row_distance(
            baseline_points, residual_points
        ),
        "affine_bound_scaling_max_normalized_distance": _max_row_distance(
            baseline_points, scaled_points
        ),
    }
    if any(value > tolerance for value in distances.values()):
        raise RuntimeError(f"metamorphic proposal drift: {distances}")

    return {
        "tolerance": tolerance,
        **distances,
        "rank_deficient_activation": True,
        "generated_proposal_count": len(baseline_points),
        "activation_by_transform": {
            "baseline": baseline_telemetry["rank_guard_overlay_activated"],
            "variable_permutation": variable_telemetry[
                "rank_guard_overlay_activated"
            ],
            "residual_permutation": residual_telemetry[
                "rank_guard_overlay_activated"
            ],
            "affine_bound_scaling": scaled_telemetry[
                "rank_guard_overlay_activated"
            ],
        },
    }


def _boundary_and_fallback_audit() -> dict[str, object]:
    mixed = ChartLinearCase()
    candidate, telemetry = _run_overlay(mixed)
    proposals = _generated_points(candidate)
    strictly_interior = all(
        np.all(point > mixed.lower) and np.all(point < mixed.upper)
        for point in proposals
    )
    if telemetry["rank_guard_overlay_activated"] != 1 or not strictly_interior:
        raise RuntimeError("mixed logit/softplus activation was not strict")

    nonsmooth = FractionalLinearCase(
        [-2.0, -3.0, -4.0],
        [2.0, 5.0, 6.0],
        [0.5, 0.5, 0.5],
        nonsmooth=True,
    )
    original = _prefix(nonsmooth.anchor)
    fallback, fallback_telemetry = ADAPTER._overlay_prefix(
        nonsmooth,
        original,
        callback_cap=512,
        callbacks_per_start=32,
    )
    if fallback is not original or fallback_telemetry[
        "rank_guard_overlay_activated"
    ] != 0:
        raise RuntimeError("nonsmooth generated case did not fail closed")

    return {
        "mixed_chart_activation": telemetry["rank_guard_overlay_activated"],
        "mixed_chart_proposal_count": len(proposals),
        "mixed_chart_proposals_strictly_interior": strictly_interior,
        "softplus_lower_bound_exercised": True,
        "reflected_softplus_upper_bound_exercised": True,
        "near_two_sided_boundary_exercised": True,
        "nonsmooth_fallback_returned_original_object": fallback is original,
        "nonsmooth_fallback_callbacks": nonsmooth.callbacks,
    }


def _accounting_and_seam_audit() -> dict[str, object]:
    case = FractionalLinearCase(
        [-2.0, -3.0, -4.0], [2.0, 5.0, 6.0], [0.4, 0.55, 0.6]
    )
    prefix = _prefix(case.anchor)
    captured: dict[str, object] = {}
    original_run: Callable[..., object] = ADAPTER.FROZEN.run_local_arm

    def fake_run(_arm: str, **kwargs):
        captured["prefix"] = kwargs["literal_prefix"]
        return Outcome(counters={"frozen_baseline_counter": 1})

    ADAPTER.FROZEN.run_local_arm = fake_run
    try:
        outcome = ADAPTER.run_local_arm(
            ADAPTER.SEARCH_ARM,
            base_case=case,
            budget=object(),
            program=object(),
            literal_prefix=prefix,
            callback_cap=512,
            callbacks_per_start=32,
            deadline_monotonic=math.inf,
        )
    finally:
        ADAPTER.FROZEN.run_local_arm = original_run

    delegated = captured.get("prefix")
    if not isinstance(delegated, Prefix):
        raise RuntimeError("overlaid prefix did not cross the frozen adapter seam")
    replaced = outcome.counters["rank_guard_overlay_replaced_slots"]
    expected_callbacks = 1 + 4 * case.dimension + 2 * len(ADAPTER.PROPOSAL_RADII)
    baseline_minimum = math.ceil(
        ADAPTER.BASELINE_PREFIX_FRACTION * len(prefix.points)
    )
    first_prefix_equal = all(
        prefix.points[index].tobytes() == delegated.points[index].tobytes()
        for index in range(baseline_minimum)
    )
    insurance_equal = all(
        prefix.points[index].tobytes() == delegated.points[index].tobytes()
        for index in range(0, len(prefix.points), ADAPTER.INSURANCE_PERIOD)
    )
    if (
        case.callbacks != expected_callbacks
        or replaced <= 0
        or not first_prefix_equal
        or not insurance_equal
        or outcome.counters["rank_guard_baseline_reserved_callbacks"] != 384
    ):
        raise RuntimeError("callback, seam, or baseline quota contract failed")
    return {
        "expected_callbacks": expected_callbacks,
        "observed_callbacks": case.callbacks,
        "frozen_adapter_delegation_observed": True,
        "replaced_tail_slots": replaced,
        "baseline_minimum_slots": baseline_minimum,
        "baseline_reserved_callbacks": outcome.counters[
            "rank_guard_baseline_reserved_callbacks"
        ],
        "first_75_percent_bitwise_preserved": first_prefix_equal,
        "every_fourth_insurance_bitwise_preserved": insurance_equal,
        "frozen_baseline_counter_retained": (
            outcome.counters["frozen_baseline_counter"] == 1
        ),
    }


def _case_routing_ast_audit() -> dict[str, object]:
    identifier_literals: list[dict[str, object]] = []
    sensitive_route_tests: list[dict[str, object]] = []
    sensitive_reads: list[dict[str, object]] = []
    for path in AUDITED_SOURCES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if SOURCE_IDENTIFIER.search(node.value):
                    identifier_literals.append(
                        {"file": str(path), "line": node.lineno, "value": node.value}
                    )
            if isinstance(node, (ast.If, ast.IfExp, ast.While)):
                test = ast.unparse(node.test)
                if re.search(
                    r"case_id|problem_id|source_sha256|family|truth|gold|answer|target_value|"
                    r"previous_outcome",
                    test,
                    re.IGNORECASE,
                ):
                    sensitive_route_tests.append(
                        {"file": str(path), "line": node.lineno, "test": test}
                    )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and SENSITIVE_KEY.fullmatch(node.args[0].value)
            ):
                sensitive_reads.append(
                    {
                        "file": str(path),
                        "line": node.lineno,
                        "key": node.args[0].value,
                    }
                )
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
                and SENSITIVE_KEY.fullmatch(node.slice.value)
            ):
                sensitive_reads.append(
                    {"file": str(path), "line": node.lineno, "key": node.slice.value}
                )
    if identifier_literals or sensitive_route_tests or sensitive_reads:
        raise RuntimeError("case-specific routing AST audit failed")
    return {
        "audited_files": [str(path.relative_to(HERE)) for path in AUDITED_SOURCES],
        "source_identifier_literal_count": 0,
        "sensitive_route_condition_count": 0,
        "sensitive_mapping_read_count": 0,
        "forbidden_sensitive_keys": [
            "case_id",
            "problem_id",
            "source_sha256",
            "family",
            "truth",
            "gold",
            "answer",
            "expected_descriptor",
            "target_value",
            "previous_outcome",
        ],
    }


def _binding_audit() -> dict[str, object]:
    arms: list[dict[str, object]] = []
    for relative in (
        Path("arms/charted-weak-proposal/arm.json"),
        Path("arms/adapted-cpqr-proposal/arm.json"),
    ):
        manifest = json.loads((HERE / relative).read_text(encoding="utf-8"))
        entrypoint = (HERE / relative).parent / manifest["entrypoint"]
        actual = hashlib.sha256(entrypoint.read_bytes()).hexdigest()
        if actual != manifest["mechanism_hash"]:
            raise RuntimeError(f"arm mechanism hash mismatch: {relative}")
        arms.append(
            {
                "id": manifest["id"],
                "mechanism_hash": actual,
                "entrypoint": str(entrypoint.relative_to(HERE)),
            }
        )
    plan = FULL._decorate_plan(
        {"schema_version": "frozen-plan/v1"},
        mode=FULL.CHARTED,
        frozen_final_schema="frozen-result/v1",
    )
    if (
        plan["schema_version"] != "frozen-plan/v1"
        or plan["proposal_overlay_active"] is not True
        or plan["source_replay_authority_modified"] is not False
        or plan["hp_pslq_or_canonical_authority_modified"] is not False
    ):
        raise RuntimeError("full-wrapper authority binding changed")
    return {
        "arms": arms,
        "frozen_plan_schema_preserved": True,
        "proposal_overlay_active": True,
        "source_replay_authority_modified": False,
        "hp_pslq_or_canonical_authority_modified": False,
        "final_result_schema_unchanged": True,
    }


def run_audit() -> dict[str, object]:
    payload = {
        "schema_version": "geotarget.exp-rank-guard-001-metamorphic-audit/v1",
        "status": "PASS",
        "generated_source_only": True,
        "truth_expected_descriptor_or_scorer_used": False,
        "formal_screen_run": False,
        "metamorphic": _metamorphic_audit(),
        "boundary_and_fallback": _boundary_and_fallback_audit(),
        "callback_quota_and_seam": _accounting_and_seam_audit(),
        "case_specific_routing_ast": _case_routing_ast_audit(),
        "full_wrapper_binding": _binding_audit(),
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    payload["evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    payload = run_audit()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(text, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
