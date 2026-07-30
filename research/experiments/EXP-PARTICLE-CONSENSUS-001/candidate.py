"""Disposable few-particle equality-forced consensus prototype.

The side lane follows Carrillo--Jin--Zhang--Zhu (arXiv:2405.00891): a
Gibbs consensus drift is combined with a stiff force toward ``F(x)=0``.  For
residual systems we use ``G=0.5*||F||^2`` and the paper's stable linearized
implicit step, replacing the exact Hessian of G by its positive-semidefinite
Gauss--Newton part.  This is a generated-only experiment, not a solver API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

import numpy as np


Array = np.ndarray
Arm = Literal["control", "candidate"]


class WorkExhausted(RuntimeError):
    pass


@dataclass(frozen=True)
class NumericalProblem:
    residual: Callable[[Array], Array]
    jacobian: Callable[[Array], Array] | None
    start: Array
    chart_scale: Array
    guard: Callable[[Array], bool] = lambda _x: True
    # Capability bit only: no case/family/source/truth information is exposed.
    smooth_numeric_jacobian: bool = True


@dataclass
class Ledger:
    problem: NumericalProblem
    cap: int
    callbacks: int = 0
    nonfinite: int = 0

    def residual(self, x: Array) -> Array:
        if self.callbacks >= self.cap:
            raise WorkExhausted
        self.callbacks += 1
        try:
            value = np.asarray(self.problem.residual(np.asarray(x, dtype=float)), dtype=float)
        except Exception:
            self.nonfinite += 1
            return np.full(1, np.inf)
        if value.ndim != 1 or not np.all(np.isfinite(value)):
            self.nonfinite += 1
            return np.full(max(1, value.size), np.inf)
        return value

    def exhaust_with_shadow_replays(self, x: Array) -> None:
        """Make paired work exact; shadow values never affect an output."""
        while self.callbacks < self.cap:
            self.residual(x)


@dataclass
class LaneResult:
    proposals: list[Array]
    callbacks: int
    nonfinite: int
    activation: dict[str, int | float | bool | str] = field(default_factory=dict)


@dataclass
class PortfolioResult:
    proposals: list[Array]
    callbacks: int
    baseline_callbacks: int
    side_callbacks: int
    activation: dict[str, int | float | bool | str]


def _finite_norm(value: Array) -> float:
    return float(np.linalg.norm(value)) if np.all(np.isfinite(value)) else np.inf


def _row_scale(problem: NumericalProblem, x: Array) -> Array:
    assert problem.jacobian is not None
    jac = np.asarray(problem.jacobian(x), dtype=float)
    scaled = jac * problem.chart_scale[np.newaxis, :]
    norms = np.linalg.norm(scaled, axis=1)
    good = norms[np.isfinite(norms) & (norms > 0.0)]
    fallback = float(np.median(good)) if good.size else 1.0
    return np.where(np.isfinite(norms) & (norms > 1e-14 * fallback), norms, fallback)


def _reduced_values(problem: NumericalProblem, x: Array, row_scale: Array) -> tuple[Array, Array]:
    assert problem.jacobian is not None
    f = np.asarray(problem.residual(x), dtype=float) / row_scale
    j = np.asarray(problem.jacobian(x), dtype=float)
    jz = j * problem.chart_scale[np.newaxis, :] / row_scale[:, np.newaxis]
    return f, jz


def _local_lane(problem: NumericalProblem, start: Array, cap: int) -> LaneResult:
    """Small numeric insurance lane, intentionally fixed and unabstracted."""
    ledger = Ledger(problem, cap)
    x = np.asarray(start, dtype=float).copy()
    best = x.copy()
    f = ledger.residual(x)
    best_value = _finite_norm(f)
    proposals = [best.copy()]
    damping = 1e-5
    completed = 0

    if problem.jacobian is not None and problem.smooth_numeric_jacobian:
        row_scale = _row_scale(problem, x)
        while ledger.callbacks < cap:
            fn = f / row_scale if f.shape == row_scale.shape else f
            if not np.all(np.isfinite(fn)):
                break
            jac = np.asarray(problem.jacobian(x), dtype=float)
            jz = jac * problem.chart_scale[np.newaxis, :] / row_scale[:, np.newaxis]
            lhs = jz.T @ jz + damping * np.eye(x.size)
            rhs = -(jz.T @ fn)
            try:
                dz = np.linalg.solve(lhs, rhs)
            except np.linalg.LinAlgError:
                dz = np.linalg.lstsq(lhs, rhs, rcond=1e-12)[0]
            radius = float(np.linalg.norm(dz))
            if radius > 1.5:
                dz *= 1.5 / radius
            trial = x + problem.chart_scale * dz
            trial_f = ledger.residual(trial)
            completed += 1
            trial_value = _finite_norm(trial_f / row_scale) if trial_f.shape == row_scale.shape else np.inf
            current_value = _finite_norm(fn)
            if trial_value < current_value:
                x, f = trial, trial_f
                damping = max(1e-10, damping * 0.35)
                if trial_value < best_value:
                    best, best_value = x.copy(), trial_value
                    proposals.append(best.copy())
            else:
                damping = min(1e8, damping * 8.0)
            if completed >= 36 or best_value <= 1e-11:
                break
    else:
        # Opaque/nonsmooth capability fallback: coordinate polling only.
        step = 1.0
        cursor = 0
        while ledger.callbacks < cap and step > 1e-8:
            axis = cursor % x.size
            sign = -1.0 if (cursor // x.size) % 2 else 1.0
            trial = x.copy()
            trial[axis] += sign * step * problem.chart_scale[axis]
            trial_f = ledger.residual(trial)
            trial_value = _finite_norm(trial_f)
            completed += 1
            if trial_value < best_value:
                x, f = trial, trial_f
                best, best_value = x.copy(), trial_value
                proposals.append(best.copy())
            if cursor % (2 * x.size) == 2 * x.size - 1:
                step *= 0.55
            cursor += 1

    ledger.exhaust_with_shadow_replays(best)
    return LaneResult(
        proposals=proposals,
        callbacks=ledger.callbacks,
        nonfinite=ledger.nonfinite,
        activation={"completed_local_steps": completed, "best_residual_norm": best_value},
    )


def _directions(dimension: int, count: int = 8) -> Array:
    """Permutation/sign-equivariant deterministic set for the few-particle lane."""
    if dimension == 1:
        base = np.array([[-1.0], [1.0]])
        return np.resize(base, (count, 1))
    vectors: list[Array] = []
    eye = np.eye(dimension)
    for axis in range(dimension):
        vectors.extend((eye[axis], -eye[axis]))
    diag = np.ones(dimension) / np.sqrt(dimension)
    vectors.extend((diag, -diag))
    alt = np.where(np.arange(dimension) % 2 == 0, 1.0, -1.0) / np.sqrt(dimension)
    vectors.extend((alt, -alt))
    while len(vectors) < count:
        vectors.extend((diag, -diag))
    return np.asarray(vectors[:count], dtype=float)


def _particle_lane(problem: NumericalProblem, cap: int, *, equality_force: bool) -> LaneResult:
    assert problem.jacobian is not None and problem.smooth_numeric_jacobian
    ledger = Ledger(problem, cap)
    count = 8
    radius = 2.4
    particles = problem.start[np.newaxis, :] + radius * _directions(problem.start.size, count) * problem.chart_scale
    row_scale = _row_scale(problem, problem.start)
    values: list[Array] = []
    energies = np.empty(count)
    reservoirs = particles.copy()
    reservoir_energy = np.full(count, np.inf)
    proposals = [p.copy() for p in particles]

    for i, particle in enumerate(particles):
        f = ledger.residual(particle)
        fn = f / row_scale if f.shape == row_scale.shape else f
        values.append(f)
        energies[i] = 0.5 * _finite_norm(fn) ** 2
        reservoir_energy[i] = energies[i]

    consensus_motion = 0
    force_motion = 0
    completed_steps = 0
    # 8 + 15*8 = 128 active residual calls: the side lane uses its whole rung.
    for iteration in range(15):
        finite = np.isfinite(energies)
        if not np.any(finite):
            break
        finite_energy = energies[finite]
        spread = max(1e-12, float(np.median(np.abs(finite_energy - np.median(finite_energy)))))
        logits = np.full(count, -np.inf)
        logits[finite] = -3.0 * (finite_energy - np.min(finite_energy)) / spread
        logits -= np.max(logits[finite])
        weights = np.exp(np.clip(logits, -60.0, 0.0))
        weights /= np.sum(weights)
        consensus = weights @ particles

        next_particles = particles.copy()
        next_values: list[Array] = []
        next_energies = np.full(count, np.inf)
        for i, particle in enumerate(particles):
            displacement_z = (particle - consensus) / problem.chart_scale
            # Repair A: consensus explores for eight steps, then a four-rung
            # equality-only stiff limit prevents the barycenter from holding a
            # particle a fixed distance off a disconnected component.
            exactification_rung = max(0, iteration - 7)
            h_consensus = 0.18 if exactification_rung == 0 else 0.0
            if equality_force:
                fn, jz = _reduced_values(problem, particle, row_scale)
                grad = jz.T @ fn
                # Linearized semi-implicit force plus implicit consensus drift.
                h_force = 0.85 if exactification_rung == 0 else float(4 ** exactification_rung)
                lhs = (1.0 + h_consensus) * np.eye(particle.size) + h_force * (jz.T @ jz)
                rhs = h_consensus * displacement_z + h_force * grad
                try:
                    dz = -np.linalg.solve(lhs, rhs)
                except np.linalg.LinAlgError:
                    dz = -np.linalg.lstsq(lhs, rhs, rcond=1e-12)[0]
                force_motion += int(np.linalg.norm(h_force * grad) > 1e-12)
            else:
                # Nearest completed repository lineage: ordinary CBO drift only.
                dz = -h_consensus * displacement_z / (1.0 + h_consensus)
            norm = float(np.linalg.norm(dz))
            if norm > 1.8:
                dz *= 1.8 / norm
            consensus_motion += int(np.linalg.norm(displacement_z) > 1e-12)
            trial = particle + problem.chart_scale * dz
            f = ledger.residual(trial)
            fn = f / row_scale if f.shape == row_scale.shape else f
            energy = 0.5 * _finite_norm(fn) ** 2
            next_particles[i] = trial
            next_values.append(f)
            next_energies[i] = energy
            if energy < reservoir_energy[i]:
                reservoirs[i] = trial
                reservoir_energy[i] = energy
            completed_steps += 1
        particles, values, energies = next_particles, next_values, next_energies

    proposals.extend(p.copy() for p in reservoirs)
    ledger.exhaust_with_shadow_replays(reservoirs[int(np.argmin(reservoir_energy))])
    return LaneResult(
        proposals=proposals,
        callbacks=ledger.callbacks,
        nonfinite=ledger.nonfinite,
        activation={
            "particle_count": count,
            "completed_particle_steps": completed_steps,
            "consensus_motion_events": consensus_motion,
            "equality_force_motion_events": force_motion,
            "best_G": float(np.min(reservoir_energy)),
            "mode": "equality_forced" if equality_force else "consensus_only",
        },
    )


def solve_portfolio(problem: NumericalProblem, arm: Arm) -> PortfolioResult:
    """Run a 75% numeric baseline plus one 25% particle/opaque lane."""
    total_cap = 512
    lane_cap = total_cap // 4
    starts = [
        problem.start.copy(),
        problem.start + 0.35 * problem.chart_scale,
        problem.start - 0.35 * problem.chart_scale,
    ]
    proposals: list[Array] = []
    baseline_callbacks = 0
    local_nonfinite = 0
    for start in starts:
        lane = _local_lane(problem, start, lane_cap)
        proposals.extend(lane.proposals)
        baseline_callbacks += lane.callbacks
        local_nonfinite += lane.nonfinite

    eligible = problem.jacobian is not None and problem.smooth_numeric_jacobian
    if eligible:
        side = _particle_lane(problem, lane_cap, equality_force=(arm == "candidate"))
    else:
        # Exact fallback parity: the fourth ordinary lane is identical in both arms.
        side = _local_lane(problem, problem.start + 0.7 * problem.chart_scale, lane_cap)
        side.activation["mode"] = "opaque_numeric_fallback"
    proposals.extend(side.proposals)
    activation = dict(side.activation)
    activation.update(
        {
            "eligible": eligible,
            "baseline_quota_fraction": baseline_callbacks / total_cap,
            "total_nonfinite": local_nonfinite + side.nonfinite,
            "case_or_family_routing": False,
        }
    )
    return PortfolioResult(
        proposals=proposals,
        callbacks=baseline_callbacks + side.callbacks,
        baseline_callbacks=baseline_callbacks,
        side_callbacks=side.callbacks,
        activation=activation,
    )


def replay_valid(problem: NumericalProblem, proposals: list[Array], tolerance: float = 2e-8) -> list[Array]:
    """Fresh complete source/guard replay; the algorithm cannot bypass it."""
    accepted: list[Array] = []
    for proposal in proposals:
        x = np.asarray(proposal, dtype=float)
        if x.shape != problem.start.shape or not np.all(np.isfinite(x)) or not problem.guard(x):
            continue
        try:
            residual = np.asarray(problem.residual(x), dtype=float)
        except Exception:
            continue
        if residual.ndim != 1 or not np.all(np.isfinite(residual)) or np.linalg.norm(residual, ord=np.inf) > tolerance:
            continue
        if not any(np.linalg.norm((x - prior) / problem.chart_scale, ord=np.inf) <= 1e-6 for prior in accepted):
            accepted.append(x.copy())
    return accepted
