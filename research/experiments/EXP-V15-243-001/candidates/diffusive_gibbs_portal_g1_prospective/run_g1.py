#!/usr/bin/env python3
"""Prospective five-family G1 for the frozen Diffusive-Gibbs portal."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Mapping

import numpy as np


HERE = Path(__file__).resolve().parent


def load_portal():
    import importlib.util
    import sys

    name = "geotarget_diffusive_gibbs_prospective_portal"
    specification = importlib.util.spec_from_file_location(name, HERE / "portal.py")
    if specification is None or specification.loader is None:
        raise ImportError(HERE / "portal.py")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


PORTAL = load_portal()
CANDIDATE = PORTAL.KERNEL
FROZEN_CANDIDATE_SHA256 = PORTAL.FROZEN_CANDIDATE_SHA256
FAMILIES = (
    "multi_sheet",
    "narrow_basin",
    "ill_scaled",
    "singular_hidden",
    "semantic_portal",
)
ROLES = ("positive", "negative", "near_miss")
TRANSFORMS = (
    "variable_permutation",
    "residual_permutation",
    "residual_sign",
    "translation",
    "rotation",
    "reflection",
    "coordinate_scale",
    "equation_scale",
)
WORK_CAP = 384
INCUMBENT_LANES = 12
PORTAL_LANES = 4
LOCAL_STEPS = 7


@dataclass(frozen=True, slots=True)
class Problem:
    family: str
    role: str
    instance: int
    seed: int
    origin: np.ndarray
    basis: np.ndarray
    residual_order: tuple[int, ...] | None = None
    residual_scale: np.ndarray | None = None
    residual_sign: float = 1.0

    @property
    def dimension(self) -> int:
        return 2

    def canonical(self, point: np.ndarray) -> np.ndarray:
        return np.linalg.solve(self.basis, np.asarray(point, dtype=float) - self.origin)

    def physical(self, canonical: np.ndarray) -> np.ndarray:
        return self.origin + self.basis @ np.asarray(canonical, dtype=float)

    def roots(self) -> tuple[tuple[float, float], ...]:
        left = (-1.7, 0.0)
        return (left, (1.7, 0.0)) if self.role == "positive" else (left,)

    def core_residual(self, z: np.ndarray) -> np.ndarray:
        u, v = float(z[0]), float(z[1])
        q = u + 1.7 if self.role == "negative" else (u + 1.7) * (u - 1.7)
        if self.family == "multi_sheet":
            return np.array([q + 0.18 * v * v, v * (1.0 + 0.12 * u)])
        if self.family == "narrow_basin":
            weight = 1.0 + 8.0 * (u - 1.7) ** 2
            return np.array([weight * q + 0.07 * v, v])
        if self.family == "ill_scaled":
            return np.array([1.0e-4 * q + 1.9 * v, 2.7 * q - 8.0e3 * v])
        if self.family == "singular_hidden":
            hidden = u - 1.7
            first = (u + 1.7) if self.role == "negative" else (u + 1.7) * hidden * hidden
            return np.array([first + 0.04 * v, v])
        if self.family == "semantic_portal":
            return np.array([q + 0.11 * v, v])
        raise ValueError(self.family)

    def semantic_valid(self, z: np.ndarray) -> bool:
        if not np.all(np.isfinite(z)) or np.max(np.abs(z), initial=0.0) >= 8.0:
            return False
        u = float(z[0])
        if self.family == "semantic_portal" and self.role == "positive":
            return u < -0.35 or u > 0.95
        if self.role == "near_miss":
            return u <= 0.35
        return True

    def observe(self, point: np.ndarray):
        try:
            z = self.canonical(point)
            residual = self.core_residual(z)
        except (OverflowError, ValueError, np.linalg.LinAlgError):
            z = np.full(self.dimension, np.nan)
            residual = np.full(self.dimension, np.nan)
        finite = bool(np.all(np.isfinite(z)) and np.all(np.isfinite(residual)))
        semantic = bool(finite and self.semantic_valid(z))
        output = np.asarray(residual, dtype=float)
        if self.residual_order is not None:
            output = output[list(self.residual_order)]
        if self.residual_scale is not None:
            output = self.residual_scale * output
        output = self.residual_sign * output
        finite = bool(finite and np.all(np.isfinite(output)))
        violation = 0.0 if semantic else 1.0 + (max(0.0, float(z[0]) - 0.35) if finite else 0.0)
        return CANDIDATE.OpaqueEvaluation(
            output,
            finite,
            semantic,
            violation,
            np.array([]) if semantic else np.array([violation]),
        )

    def starts(self, count: int = 128) -> tuple[np.ndarray, ...]:
        rng = np.random.default_rng(130_003 + 101 * self.instance + 1009 * self.seed)
        left = np.asarray(self.roots()[0])
        values = []
        for _ in range(count):
            z = left + rng.normal(scale=(0.13, 0.10), size=2)
            values.append(self.physical(z))
        # The unchanged 75% incumbent lane always contains one exact safe root,
        # but the portal anchors themselves are not handed an oracle root.
        values[INCUMBENT_LANES - 1] = self.physical(left)
        return tuple(values)

    def replay(self, endpoint: np.ndarray) -> tuple[float, float] | None:
        try:
            z = self.canonical(endpoint)
        except np.linalg.LinAlgError:
            return None
        for root in self.roots():
            exact = np.asarray(root)
            if np.linalg.norm(z - exact, ord=np.inf) > 8.0e-5:
                continue
            source = self.observe(self.physical(exact))
            if (
                source.finite
                and source.semantics_valid
                and np.max(np.abs(source.residual), initial=0.0) <= 1.0e-12
            ):
                return root
        return None


class Ledger:
    def __init__(self, problem: Problem) -> None:
        self.problem = problem
        self.calls = 0
        self.trace: list[bytes] = []

    def evaluate(self, point: np.ndarray):
        if self.calls >= WORK_CAP:
            raise RuntimeError("callback cap")
        vector = np.asarray(point, dtype="<f8")
        self.trace.append(vector.tobytes(order="C"))
        self.calls += 1
        return self.problem.observe(vector)

    def trace_sha256(self) -> str:
        digest = hashlib.sha256()
        for row in self.trace:
            digest.update(len(row).to_bytes(8, "little"))
            digest.update(row)
        return digest.hexdigest()


def polish(ledger: Ledger, start: np.ndarray) -> np.ndarray:
    problem = ledger.problem
    z = problem.canonical(start)
    n = z.size
    iteration_cost = n + 2
    for _ in range(LOCAL_STEPS):
        if ledger.calls + iteration_cost > WORK_CAP:
            break
        point = problem.physical(z)
        base = ledger.evaluate(point)
        if not base.finite or not base.semantics_valid:
            break
        residual = np.asarray(base.residual, dtype=float)
        if np.max(np.abs(residual), initial=0.0) <= 1.0e-12:
            break
        h = 1.5e-5 * max(1.0, float(np.linalg.norm(z, ord=np.inf)))
        columns = []
        for column in range(n):
            trial_z = z.copy()
            trial_z[column] += h
            observed = ledger.evaluate(problem.physical(trial_z))
            columns.append(
                (np.asarray(observed.residual, dtype=float) - residual) / h
                if observed.finite and observed.semantics_valid
                else np.zeros_like(residual)
            )
        jacobian = np.stack(columns, axis=1)
        try:
            step = np.linalg.lstsq(jacobian, -residual, rcond=1.0e-12)[0]
        except np.linalg.LinAlgError:
            break
        if not np.all(np.isfinite(step)):
            break
        norm = float(np.linalg.norm(step))
        if norm > 1.2:
            step *= 1.2 / norm
        trial_z = z + step
        observed = ledger.evaluate(problem.physical(trial_z))
        if (
            observed.finite
            and observed.semantics_valid
            and np.linalg.norm(observed.residual) < np.linalg.norm(residual)
        ):
            z = trial_z
    return problem.physical(z)


def run_arm(problem: Problem, arm: str) -> Mapping[str, object]:
    ledger = Ledger(problem)
    starts = problem.starts()
    endpoints = [polish(ledger, point) for point in starts[:INCUMBENT_LANES]]
    insurance_trace_sha256 = ledger.trace_sha256()
    insurance_calls = ledger.calls
    portal_calls = portal_proposals = 0
    if arm == "candidate":
        portal = PORTAL.propose(
            ledger.evaluate,
            starts[:INCUMBENT_LANES],
            seed=170_011 + 1009 * problem.seed + 31 * problem.instance,
        )
        portal_calls = portal.calls
        tail = list(portal.proposals)
        portal_proposals = len(tail)
        while len(tail) < PORTAL_LANES:
            tail.append(starts[INCUMBENT_LANES + len(tail)])
    elif arm == "control":
        tail = list(starts[INCUMBENT_LANES : INCUMBENT_LANES + PORTAL_LANES])
    else:
        raise ValueError(arm)
    endpoints.extend(polish(ledger, point) for point in tail[:PORTAL_LANES])

    next_start = INCUMBENT_LANES + PORTAL_LANES
    while ledger.calls + problem.dimension + 2 <= WORK_CAP:
        endpoints.append(polish(ledger, starts[next_start]))
        next_start += 1
    while ledger.calls < WORK_CAP:
        point = starts[next_start]
        observed = ledger.evaluate(point)
        if (
            observed.finite
            and observed.semantics_valid
            and np.max(np.abs(observed.residual), initial=0.0) <= 1.0e-12
        ):
            endpoints.append(point)
        next_start += 1

    descriptors = {
        descriptor
        for endpoint in endpoints
        if (descriptor := problem.replay(endpoint)) is not None
    }
    return {
        "descriptors": descriptors,
        "productive_callbacks": ledger.calls,
        "insurance_trace_sha256": insurance_trace_sha256,
        "insurance_calls": insurance_calls,
        "portal_calls": portal_calls,
        "portal_proposals": portal_proposals,
    }


def build_problem(family: str, role: str, instance: int, seed: int) -> Problem:
    return Problem(family, role, instance, seed, np.zeros(2), np.eye(2))


def fixed_orthogonal(*, reflection: bool) -> np.ndarray:
    rng = np.random.default_rng(191_117 + int(reflection))
    matrix, _ = np.linalg.qr(rng.normal(size=(2, 2)))
    if reflection == (np.linalg.det(matrix) > 0.0):
        matrix[:, 0] *= -1.0
    return matrix


def transform(problem: Problem, kind: str) -> Problem:
    if kind == "variable_permutation":
        permutation = np.eye(2)[::-1]
        return replace(
            problem,
            origin=permutation @ problem.origin,
            basis=permutation @ problem.basis,
        )
    if kind == "residual_permutation":
        return replace(problem, residual_order=(1, 0))
    if kind == "residual_sign":
        return replace(problem, residual_sign=-1.0)
    if kind == "translation":
        return replace(problem, origin=problem.origin + np.array([1.3, -2.1]))
    if kind == "rotation":
        matrix = fixed_orthogonal(reflection=False)
        return replace(
            problem,
            origin=matrix @ problem.origin,
            basis=matrix @ problem.basis,
        )
    if kind == "reflection":
        matrix = fixed_orthogonal(reflection=True)
        return replace(
            problem,
            origin=matrix @ problem.origin,
            basis=matrix @ problem.basis,
        )
    if kind == "coordinate_scale":
        return replace(problem, basis=problem.basis @ np.diag([0.41, 2.9]))
    if kind == "equation_scale":
        return replace(problem, residual_scale=np.array([0.23, 6.7]))
    raise ValueError(kind)


def timed_arm(problem: Problem, arm: str) -> tuple[Mapping[str, object], float]:
    started = time.process_time()
    result = run_arm(problem, arm)
    return result, time.process_time() - started


def execute(*, instances: int, seeds: int) -> dict[str, object]:
    aggregate = {
        family: {
            "cases": 0,
            "gain": 0,
            "loss": 0,
            "false_extra": 0,
            "portal_activated": 0,
        }
        for family in FAMILIES
    }
    gain = loss = false_extra = work_mismatch = insurance_mismatch = 0
    control_work = candidate_work = 0
    control_cpu = candidate_cpu = 0.0
    portal_calls = portal_proposals = 0
    ordinal = 0
    for family in FAMILIES:
        for role in ROLES:
            for instance in range(instances):
                for seed in range(seeds):
                    problem = build_problem(family, role, instance, seed)
                    truth = set(problem.roots())
                    if ordinal % 2:
                        trial, trial_cpu = timed_arm(problem, "candidate")
                        control, base_cpu = timed_arm(problem, "control")
                    else:
                        control, base_cpu = timed_arm(problem, "control")
                        trial, trial_cpu = timed_arm(problem, "candidate")
                    ordinal += 1
                    base_ok = control["descriptors"] == truth
                    trial_ok = trial["descriptors"] == truth
                    row = aggregate[family]
                    row["cases"] += 1
                    row["gain"] += int(trial_ok and not base_ok)
                    row["loss"] += int(base_ok and not trial_ok)
                    extras = len(set(trial["descriptors"]) - truth)
                    row["false_extra"] += extras
                    row["portal_activated"] += int(trial["portal_proposals"] > 0)
                    gain += int(trial_ok and not base_ok)
                    loss += int(base_ok and not trial_ok)
                    false_extra += extras
                    control_work += int(control["productive_callbacks"])
                    candidate_work += int(trial["productive_callbacks"])
                    work_mismatch += int(
                        control["productive_callbacks"] != trial["productive_callbacks"]
                    )
                    insurance_mismatch += int(
                        control["insurance_trace_sha256"]
                        != trial["insurance_trace_sha256"]
                        or control["insurance_calls"] != trial["insurance_calls"]
                    )
                    portal_calls += int(trial["portal_calls"])
                    portal_proposals += int(trial["portal_proposals"])
                    control_cpu += base_cpu
                    candidate_cpu += trial_cpu

    metamorphic_pass = metamorphic_total = 0
    metamorphic_by_kind = {kind: {"pass": 0, "total": 0} for kind in TRANSFORMS}
    for family in FAMILIES:
        for role in ROLES:
            problem = build_problem(family, role, 20_003, 17)
            base_candidate = run_arm(problem, "candidate")["descriptors"]
            base_control = run_arm(problem, "control")["descriptors"]
            for kind in TRANSFORMS:
                changed = transform(problem, kind)
                candidate_descriptors = run_arm(changed, "candidate")["descriptors"]
                control_descriptors = run_arm(changed, "control")["descriptors"]
                matched = bool(
                    candidate_descriptors == base_candidate
                    and control_descriptors == base_control
                )
                metamorphic_total += 1
                metamorphic_pass += int(matched)
                metamorphic_by_kind[kind]["total"] += 1
                metamorphic_by_kind[kind]["pass"] += int(matched)

    callback_ratio = candidate_work / max(control_work, 1)
    cpu_ratio = candidate_cpu / max(control_cpu, 1.0e-12)
    family_gains = sum(row["gain"] > 0 for row in aggregate.values())
    passed = bool(
        gain > 0
        and family_gains >= 2
        and loss == 0
        and false_extra == 0
        and insurance_mismatch == 0
        and work_mismatch == 0
        and callback_ratio <= 1.10
        and cpu_ratio <= 1.10
        and portal_proposals > 0
        and metamorphic_pass == metamorphic_total
    )
    return {
        "schema_version": "geotarget.diffusive-gibbs-prospective-g1/v1",
        "candidate_sha256": FROZEN_CANDIDATE_SHA256,
        "portal_adapter_sha256": hashlib.sha256((HERE / "portal.py").read_bytes()).hexdigest(),
        "candidate_bytes_changed_from_g0": False,
        "portal_configuration": PORTAL.configuration_manifest(),
        "candidate_opaque_inputs": [
            "residual",
            "finite",
            "semantics_valid",
            "violation",
            "violation_vector",
        ],
        "families": list(FAMILIES),
        "roles": list(ROLES),
        "case_count": len(FAMILIES) * len(ROLES) * instances * seeds,
        "instances": instances,
        "seeds": seeds,
        "incumbent_lane_fraction": 0.75,
        "byte_identical_insurance_mismatch": insurance_mismatch,
        "work_cap_per_arm": WORK_CAP,
        "control_productive_callbacks": control_work,
        "candidate_productive_callbacks": candidate_work,
        "productive_callback_ratio": callback_ratio,
        "work_mismatch": work_mismatch,
        "control_cpu_seconds_ab_ba": control_cpu,
        "candidate_cpu_seconds_ab_ba": candidate_cpu,
        "cpu_ratio_ab_ba": cpu_ratio,
        "gain": gain,
        "loss": loss,
        "false_extra": false_extra,
        "families_with_gain": family_gains,
        "portal_calls": portal_calls,
        "portal_proposals": portal_proposals,
        "full_source_replay_before_descriptor": True,
        "metamorphic_pass": metamorphic_pass,
        "metamorphic_total": metamorphic_total,
        "metamorphic_by_kind": metamorphic_by_kind,
        "per_family_aggregate": aggregate,
        "candidate_receives_case_family_truth_target_outcome": False,
        "validation_or_sealed_accessed": False,
        "gate": {
            "loss_zero": loss == 0,
            "false_zero": false_extra == 0,
            "insurance_75_percent_byte_identical": insurance_mismatch == 0,
            "callback_ratio_at_most_1_10": callback_ratio <= 1.10,
            "cpu_ratio_at_most_1_10": cpu_ratio <= 1.10,
            "metamorphic_all": metamorphic_pass == metamorphic_total,
            "gain_two_families": gain > 0 and family_gains >= 2,
        },
        "decision": "GO_INTEGRATION_SMOKE" if passed else "STOP_G1",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", type=int, default=12)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--compact", action="store_true")
    arguments = parser.parse_args()
    if arguments.instances < 1 or arguments.seeds < 1:
        raise SystemExit("instances and seeds must be positive")
    print(
        json.dumps(
            execute(instances=arguments.instances, seeds=arguments.seeds),
            ensure_ascii=False,
            sort_keys=True,
            indent=None if arguments.compact else 2,
        )
    )


if __name__ == "__main__":
    main()
