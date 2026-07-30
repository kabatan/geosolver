"""Thin source-only v15 start-prefix connection for EXP-PARTICLE-CONSENSUS-001.

Only ordinals divisible by four are eligible for the disposable particle side
lane.  The other 75% of the frozen prefix are asserted bit-identical.  The
unchanged mature local kernel and its fresh canonical endpoint replay remain
the only root authorities.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get("GEOTARGET_EXPERIMENT_RUNTIME", "/home/kabatan/work/solver-experiment-runtime/solver")
).resolve()
V15_ADAPTER_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
    "corrective_nearroot_strict_restart_v2/adapter.py"
)
V15_ADAPTER_SHA256 = "cda4e348ce1bb848af84afaba062c931ec5f1ebf882bdb8cf122df0366e75dc2"
CORE_PATH = HERE / "candidate.py"
CORE_SHA256 = "1d24ab131de635ef47c5f9f2230822f3d62a6d7b5787be95e26089d59c924a4e"

CONTROL = "frozen_v15_original_start_prefix"
CANDIDATE = "few_particle_equality_forced_prefix_25pct"
ARMS = (CONTROL, CANDIDATE)
SIDE_PERIOD = 4
GROUP_SIZE = 8


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path, expected: str):
    if _sha256(path) != expected:
        raise RuntimeError(f"hash-bound particle connection changed: {path}")
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


V15 = _load("geotarget_particle_consensus_v15_adapter", V15_ADAPTER_PATH, V15_ADAPTER_SHA256)
if _sha256(CORE_PATH) != CORE_SHA256:
    raise RuntimeError("generated D0 particle core changed")
PRECISION_RUNTIME = V15.PRECISION_RUNTIME


def _prefix_digest(points: Sequence[np.ndarray]) -> str:
    digest = hashlib.sha256(b"geotarget.exp-particle-consensus.real-prefix-f8/v1\0")
    digest.update(struct.pack("<Q", len(points)))
    for point in points:
        values = np.asarray(point, dtype="<f8")
        digest.update(struct.pack("<Q", values.size))
        digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


class _UnsupportedSideLane(RuntimeError):
    pass


def _ad_relation(program: object, point: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = tuple(program.relation_rows(point))
    if not rows:
        raise _UnsupportedSideLane("empty relation")
    values = np.full(len(rows), np.nan)
    jacobian = np.full((len(rows), point.size), np.nan)
    supported = np.zeros(len(rows), dtype=bool)
    for index, row in enumerate(rows):
        if row is None:
            continue
        derivative = np.asarray(row.derivative, dtype=float)
        if derivative.shape != (point.size,) or not (
            math.isfinite(float(row.value)) and np.all(np.isfinite(derivative))
        ):
            continue
        values[index] = float(row.value)
        jacobian[index] = derivative
        supported[index] = True
    if not np.any(supported):
        raise _UnsupportedSideLane("fully opaque relation")
    return values, jacobian, supported


def _observe(
    base_case: object,
    program: object,
    point: np.ndarray,
    *,
    chart: np.ndarray | None = None,
    need_jacobian: bool = True,
):
    observation = base_case.evaluate(point)
    residual = np.asarray(observation.residual, dtype=float)
    if residual.shape != (int(base_case.residual_dimension),) or not (
        bool(observation.finite) and np.all(np.isfinite(residual))
    ):
        raise _UnsupportedSideLane("opaque/nonfinite evaluator")
    if not need_jacobian:
        return residual, None, bool(observation.semantics_valid), 0

    ad_values, jacobian, supported = _ad_relation(program, point)
    tolerance = 2e-10 + 2e-8 * np.maximum(1.0, np.abs(residual))
    supported &= np.abs(ad_values - residual) <= tolerance
    analytic_count = int(np.count_nonzero(supported))
    if analytic_count == 0:
        raise _UnsupportedSideLane("fully opaque/parity-failed relation")
    unsupported = np.flatnonzero(~supported)
    if unsupported.size:
        if chart is None:
            raise _UnsupportedSideLane("hybrid FD has no chart")
        for column in range(point.size):
            step = 2e-7 * max(1.0, abs(float(point[column])), float(chart[column]))
            trial = point.copy()
            trial[column] = min(float(base_case.upper[column]), float(point[column] + step))
            if trial[column] == point[column]:
                trial[column] = max(float(base_case.lower[column]), float(point[column] - step))
            delta = trial[column] - point[column]
            if delta == 0.0:
                jacobian[unsupported, column] = 0.0
                continue
            trial_observation = base_case.evaluate(trial)
            trial_residual = np.asarray(trial_observation.residual, dtype=float)
            if trial_residual.shape != residual.shape or not (
                bool(trial_observation.finite) and np.all(np.isfinite(trial_residual))
            ):
                raise _UnsupportedSideLane("nonfinite charged FD")
            jacobian[unsupported, column] = (
                trial_residual[unsupported] - residual[unsupported]
            ) / delta
    if not np.all(np.isfinite(jacobian)):
        raise _UnsupportedSideLane("nonfinite hybrid Jacobian")
    return residual, jacobian, bool(observation.semantics_valid), analytic_count


def _transport_group(
    base_case: object,
    program: object,
    originals: Sequence[np.ndarray],
    deadline: float,
) -> tuple[list[np.ndarray], int]:
    particles = np.asarray(originals, dtype=float).copy()
    if not 4 <= len(particles) <= 8 or particles.ndim != 2:
        raise _UnsupportedSideLane("few-particle group size")
    chart = np.median(np.maximum(1.0, np.abs(particles)), axis=0)
    anchor_residual, anchor_jacobian, anchor_semantic, analytic_count = _observe(
        base_case, program, particles[0], chart=chart
    )
    row_scale = np.linalg.norm(anchor_jacobian * chart[np.newaxis, :], axis=1)
    positive = row_scale[np.isfinite(row_scale) & (row_scale > 0.0)]
    fallback = float(np.median(positive)) if positive.size else 1.0
    row_scale = np.where(np.isfinite(row_scale) & (row_scale > 1e-14 * fallback), row_scale, fallback)

    energies = np.full(len(particles), np.inf)
    reservoirs = particles.copy()
    reservoir_energy = np.full(len(particles), np.inf)
    reservoir_semantic = np.zeros(len(particles), dtype=bool)
    calls = 1
    for index, particle in enumerate(particles):
        if index == 0:
            residual, semantic = anchor_residual, anchor_semantic
        else:
            residual, _jacobian, semantic, _analytic = _observe(
                base_case, program, particle, need_jacobian=False
            )
            calls += 1
        energy = 0.5 * float(np.dot(residual / row_scale, residual / row_scale))
        energies[index] = energy
        if semantic:
            reservoir_energy[index] = energy
            reservoir_semantic[index] = True

    for iteration in range(15):
        if time.monotonic() >= deadline:
            raise _UnsupportedSideLane("deadline during particle portal")
        spread = max(1e-12, float(np.median(np.abs(energies - np.median(energies)))))
        logits = -3.0 * (energies - np.min(energies)) / spread
        logits -= np.max(logits)
        weights = np.exp(np.clip(logits, -60.0, 0.0))
        weights /= np.sum(weights)
        consensus = weights @ particles
        rung = max(0, iteration - 7)
        h_consensus = 0.18 if rung == 0 else 0.0
        h_force = 0.85 if rung == 0 else float(4**rung)
        next_particles = particles.copy()
        next_energies = np.full(len(particles), np.inf)
        for index, particle in enumerate(particles):
            residual, jacobian, _semantic, current_analytic = _observe(
                base_case, program, particle, chart=chart
            )
            calls += 1
            analytic_count = min(analytic_count, current_analytic)
            fn = residual / row_scale
            jz = jacobian * chart[np.newaxis, :] / row_scale[:, np.newaxis]
            displacement = (particle - consensus) / chart
            lhs = (1.0 + h_consensus) * np.eye(particle.size) + h_force * (jz.T @ jz)
            rhs = h_consensus * displacement + h_force * (jz.T @ fn)
            try:
                dz = -np.linalg.solve(lhs, rhs)
            except np.linalg.LinAlgError:
                dz = -np.linalg.lstsq(lhs, rhs, rcond=1e-12)[0]
            length = float(np.linalg.norm(dz))
            if length > 1.8:
                dz *= 1.8 / length
            trial = particle + chart * dz
            if np.any(trial < base_case.lower) or np.any(trial > base_case.upper):
                trial = particle
            trial_residual, _trial_jacobian, semantic, _trial_analytic = _observe(
                base_case, program, trial, need_jacobian=False
            )
            calls += 1
            energy = 0.5 * float(np.dot(trial_residual / row_scale, trial_residual / row_scale))
            next_particles[index] = trial
            next_energies[index] = energy
            if semantic and energy < reservoir_energy[index]:
                reservoirs[index] = trial
                reservoir_energy[index] = energy
                reservoir_semantic[index] = True
        particles, energies = next_particles, next_energies
    emitted = [
        reservoirs[i].copy() if reservoir_semantic[i] else np.asarray(originals[i], dtype=float).copy()
        for i in range(len(originals))
    ]
    return emitted, calls, analytic_count


def _candidate_prefix(base_case: object, program: object, prefix: object, deadline: float):
    original = tuple(np.asarray(point, dtype=float) for point in prefix.points)
    side = [index for index in range(len(original)) if index % SIDE_PERIOD == 0]
    if len(side) < 4:
        return prefix
    points = [point.copy() for point in original]
    total_calls = 0
    groups = 0
    try:
        for offset in range(0, len(side), GROUP_SIZE):
            indices = side[offset : offset + GROUP_SIZE]
            if len(indices) < 4:
                continue
            emitted, calls, analytic_count = _transport_group(
                base_case, program, [original[index] for index in indices], deadline
            )
            total_calls += calls
            groups += 1
            for index, point in zip(indices, emitted, strict=True):
                points[index] = point
    except Exception as error:
        # Opaque/unsupported/timeout fallback is the exact original prefix.
        activation = dict(prefix.activation)
        activation.update({
            "particle_consensus_status": f"fallback:{type(error).__name__}",
            "particle_evaluator_callbacks_before_fallback": total_calls,
            "baseline_prefix_fraction": 1.0,
        })
        return replace(prefix, activation=activation)

    for index, (before, after) in enumerate(zip(original, points, strict=True)):
        if index % SIDE_PERIOD != 0 and not np.array_equal(before, after):
            raise AssertionError("75% baseline prefix changed")
    activation = dict(prefix.activation)
    activation.update({
        "particle_consensus_status": "eligible",
        "particle_groups": groups,
        "particle_count_min": 4,
        "particle_count_max": 8,
        "particle_evaluator_callbacks": total_calls,
        "particle_min_analytic_relation_rows": analytic_count,
        "baseline_prefix_fraction": sum(i % SIDE_PERIOD != 0 for i in range(len(points))) / len(points),
        "baseline_prefix_bitwise_identical": True,
        "fresh_canonical_endpoint_replay_unchanged": True,
        "case_family_truth_or_outcome_routing": False,
    })
    sources = tuple(
        "equality_forced_few_particle" if i % SIDE_PERIOD == 0 else prefix.sources[i]
        for i in range(len(points))
    )
    exponents = tuple(None if i % SIDE_PERIOD == 0 else prefix.scale_exponents[i] for i in range(len(points)))
    return replace(
        prefix,
        points=tuple(points),
        sources=sources,
        scale_exponents=exponents,
        sha256=_prefix_digest(points),
        activation=activation,
    )


def build_literal_prefix(document, base_case, base_policy):
    return V15.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm not in ARMS:
        raise ValueError(arm)
    return V15.compile_program(V15.CANDIDATE, document)


def run_local_arm(arm: str, **kwargs):
    if arm not in ARMS:
        raise ValueError(arm)
    prefix = kwargs["literal_prefix"]
    before_callbacks = int(kwargs["budget"].callbacks)
    if arm == CANDIDATE:
        prefix = _candidate_prefix(
            kwargs["base_case"], kwargs["program"], prefix, kwargs["deadline_monotonic"]
        )
    portal_callbacks = int(kwargs["budget"].callbacks) - before_callbacks
    delegated = dict(kwargs)
    delegated["literal_prefix"] = prefix
    outcome = V15.run_local_arm(V15.CANDIDATE, **delegated)
    counters = dict(outcome.counters)
    status = str(prefix.activation.get("particle_consensus_status", "control"))
    counters[f"particle_consensus_prefix_status:{status}"] = 1
    counters["particle_consensus_prefix_callbacks"] = portal_callbacks
    counters["particle_consensus_baseline_prefix_unchanged"] = int(
        prefix.activation.get("baseline_prefix_bitwise_identical", arm == CONTROL)
    )
    counters["particle_consensus_groups"] = int(prefix.activation.get("particle_groups", 0))
    return replace(outcome, counters=counters)


def configuration_manifest() -> Mapping[str, object]:
    payload = {
        "schema": "geotarget.exp-particle-consensus-001.real-binding/v1",
        "arms": list(ARMS),
        "baseline_prefix_fraction_min": 0.75,
        "side_prefix_ordinals": "ordinal mod 4 == 0, grouped 4--8",
        "same_frozen_v15_local_kernel": True,
        "fresh_canonical_endpoint_replay_unchanged": True,
        "opaque_or_ad_parity_failure": "exact original-prefix fallback",
        "source_problem_modified": False,
        "case_family_truth_target_or_outcome_routing": False,
        "module_sha256": {
            "generated_core": CORE_SHA256,
            "frozen_v15_adapter": V15_ADAPTER_SHA256,
        },
    }
    payload["configuration_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


BINDING_RECORD = configuration_manifest()
