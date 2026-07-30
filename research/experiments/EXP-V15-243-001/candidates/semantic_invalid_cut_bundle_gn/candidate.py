"""Candidate-private semantic-invalid cut-bundle Gauss--Newton prototype.

Only a Boolean semantic replay is used to learn cuts.  A cut is never an
answer or feasibility authority: every claimed root is independently replayed
by the supplied canonical callback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
import math
from typing import Protocol, Sequence

import numpy as np


Array = np.ndarray


@dataclass(frozen=True, slots=True)
class Configuration:
    maximum_dimension: int = 4
    maximum_cuts: int = 8
    bisection_steps: int = 4
    damping: float = 1.0e-4
    initial_radius: float = 2.0
    minimum_radius: float = 2.0e-3
    maximum_radius: float = 3.0
    root_tolerance: float = 2.0e-6
    movement_flush_radii: float = 0.35
    isolated_probe_factor: float = 1.25
    model_disagreement_ratio: float = -0.25
    maximum_cut_disagreements: int = 3
    baseline_fraction: float = 0.75


DEFAULT = Configuration()


@dataclass(frozen=True, slots=True)
class Observation:
    point: Array
    residual: Array
    jacobian: Array
    finite: bool
    semantics_valid: bool
    branch_token: str
    rank: int
    scaling: Array
    opaque: bool = False


class Problem(Protocol):
    dimension: int
    residual_dimension: int

    def observe(self, point: Array) -> Observation: ...

    def canonical_replay(self, point: Array) -> bool: ...


@dataclass(frozen=True, slots=True)
class Cut:
    normal: Array
    boundary: Array
    source_anchor: Array
    branch_token: str
    rank: int
    scaling: Array


@dataclass(slots=True)
class CutBundle:
    cuts: list[Cut] = field(default_factory=list)
    flushes: int = 0
    learned: int = 0
    disagreements: int = 0
    maximum_retained: int = 0

    def clear(self) -> None:
        if self.cuts:
            self.flushes += 1
        self.cuts.clear()


@dataclass(frozen=True, slots=True)
class Outcome:
    solved: bool
    point: Array
    callbacks: int
    invalid_evaluations: int
    valid_evaluations: int
    nonfinite_evaluations: int
    canonical_replays: int
    cuts_learned: int
    cuts_retained: int
    maximum_retained_cuts: int
    cut_flushes: int
    cut_disagreements: int
    qp_solves: int
    accepted_steps: int
    status: str
    accounting_padding_callbacks: int


class Runtime:
    def __init__(self, problem: Problem, callback_cap: int):
        self.problem = problem
        self.callback_cap = int(callback_cap)
        self.callbacks = 0
        self.invalid = 0
        self.valid = 0
        self.nonfinite = 0
        self.canonical_replays = 0

    @property
    def remaining(self) -> int:
        return max(0, self.callback_cap - self.callbacks)

    def observe(self, point: Sequence[float]) -> Observation | None:
        if self.remaining <= 0:
            return None
        self.callbacks += 1
        try:
            observation = self.problem.observe(np.asarray(point, dtype=float).copy())
        except Exception:
            self.nonfinite += 1
            return None
        if not observation.finite or observation.opaque:
            self.nonfinite += 1
        elif observation.semantics_valid:
            self.valid += 1
        else:
            self.invalid += 1
        return observation

    def replay(self, point: Sequence[float]) -> bool:
        if self.remaining <= 0:
            return False
        self.callbacks += 1
        self.canonical_replays += 1
        try:
            accepted = bool(self.problem.canonical_replay(np.asarray(point, dtype=float).copy()))
        except Exception:
            self.nonfinite += 1
            return False
        if accepted:
            self.valid += 1
        else:
            self.invalid += 1
        return accepted


def portfolio_trace(start_count: int) -> tuple[str, ...]:
    """Keep exactly three ordinary slots for every one side slot."""

    return tuple("side" if ordinal % 4 == 3 else "baseline" for ordinal in range(start_count))


def _compatible(left: Observation, right: Observation) -> bool:
    return bool(
        left.finite
        and right.finite
        and not left.opaque
        and not right.opaque
        and left.branch_token == right.branch_token
        and left.rank == right.rank
        and left.scaling.shape == right.scaling.shape
        and np.allclose(left.scaling, right.scaling, rtol=2.0e-8, atol=2.0e-11)
    )


def _objective(hessian: Array, gradient: Array, point: Array) -> float:
    return float(0.5 * point @ hessian @ point + gradient @ point)


def solve_small_dense_qp(
    hessian: Array,
    gradient: Array,
    inequalities: Array,
    bounds: Array,
    *,
    tolerance: float = 2.0e-9,
) -> Array | None:
    """Enumerate active sets for a tiny strictly-convex dense QP."""

    hessian = np.asarray(hessian, dtype=float)
    gradient = np.asarray(gradient, dtype=float)
    inequalities = np.asarray(inequalities, dtype=float)
    bounds = np.asarray(bounds, dtype=float)
    dimension = gradient.size
    if (
        hessian.shape != (dimension, dimension)
        or inequalities.ndim != 2
        or inequalities.shape[1] != dimension
        or bounds.shape != (inequalities.shape[0],)
        or not np.all(np.isfinite(hessian))
        or not np.all(np.isfinite(gradient))
        or not np.all(np.isfinite(inequalities))
        or not np.all(np.isfinite(bounds))
        or np.any(bounds < -tolerance)
    ):
        return None
    best: Array | None = None
    best_value = math.inf
    constraint_count = inequalities.shape[0]
    for active_size in range(min(dimension, constraint_count) + 1):
        for active in combinations(range(constraint_count), active_size):
            if active:
                active_matrix = inequalities[np.asarray(active, dtype=int)]
                active_bounds = bounds[np.asarray(active, dtype=int)]
                kkt = np.block(
                    [
                        [hessian, active_matrix.T],
                        [active_matrix, np.zeros((active_size, active_size))],
                    ]
                )
                right = np.concatenate((-gradient, active_bounds))
            else:
                kkt = hessian
                right = -gradient
            try:
                solution = np.linalg.solve(kkt, right)
            except np.linalg.LinAlgError:
                continue
            point = solution[:dimension]
            multipliers = solution[dimension:]
            if not np.all(np.isfinite(point)) or np.any(multipliers < -tolerance):
                continue
            if np.any(inequalities @ point - bounds > tolerance):
                continue
            value = _objective(hessian, gradient, point)
            if value < best_value:
                best_value = value
                best = point.copy()
    return best


def _step(
    observation: Observation,
    radius: float,
    cuts: Sequence[Cut],
    configuration: Configuration,
) -> Array | None:
    dimension = observation.point.size
    scaling = np.asarray(observation.scaling, dtype=float)
    if (
        dimension > configuration.maximum_dimension
        or scaling.shape != (dimension,)
        or np.any(scaling <= 0.0)
        or not np.all(np.isfinite(scaling))
    ):
        return None
    jacobian = np.asarray(observation.jacobian, dtype=float)
    residual = np.asarray(observation.residual, dtype=float)
    if jacobian.shape != (residual.size, dimension):
        return None
    hessian = jacobian.T @ jacobian + configuration.damping * np.diag(scaling * scaling)
    gradient = jacobian.T @ residual
    rows: list[Array] = []
    limits: list[float] = []
    for column in range(dimension):
        row = np.zeros(dimension)
        row[column] = scaling[column]
        rows.extend((row.copy(), -row.copy()))
        limits.extend((radius, radius))
    for cut in cuts:
        if (
            cut.normal.shape != (dimension,)
            or not np.all(np.isfinite(cut.normal))
            or not np.allclose(cut.scaling, scaling, rtol=2.0e-8, atol=2.0e-11)
        ):
            continue
        limit = float(cut.normal @ (cut.boundary - observation.point))
        if limit < -2.0e-8:
            continue
        rows.append(cut.normal.copy())
        limits.append(max(0.0, limit))
    return solve_small_dense_qp(
        hessian,
        gradient,
        np.vstack(rows),
        np.asarray(limits, dtype=float),
    )


def _learn_cut(
    runtime: Runtime,
    accepted: Observation,
    rejected: Observation,
    configuration: Configuration,
) -> tuple[Cut | None, str]:
    if not accepted.semantics_valid or rejected.semantics_valid:
        return None, "not-valid-invalid-pair"
    if not _compatible(accepted, rejected):
        return None, "branch-rank-scaling-disagreement"
    direction = rejected.point - accepted.point
    scaled_length = float(np.linalg.norm(accepted.scaling * direction, ord=np.inf))
    if not math.isfinite(scaled_length) or scaled_length <= 1.0e-10:
        return None, "degenerate-chord"
    if runtime.remaining < configuration.bisection_steps + 2:
        return None, "insufficient-callbacks"

    beyond = accepted.point + configuration.isolated_probe_factor * direction
    outer = runtime.observe(beyond)
    if outer is None or not _compatible(accepted, outer):
        return None, "nonfinite-opaque-or-branch-disagreement"
    if outer.semantics_valid:
        return None, "isolated-invalid-pocket"

    valid = accepted
    invalid = rejected
    for _ in range(configuration.bisection_steps):
        midpoint = runtime.observe(0.5 * (valid.point + invalid.point))
        if midpoint is None or not _compatible(accepted, midpoint):
            return None, "bisection-disagreement"
        if midpoint.semantics_valid:
            valid = midpoint
        else:
            invalid = midpoint
    normal = rejected.point - valid.point
    normal_length = float(np.linalg.norm(normal))
    if not math.isfinite(normal_length) or normal_length <= 1.0e-12:
        return None, "degenerate-normal"
    normal = normal / normal_length
    # The valid bracket endpoint, not the unknown exact boundary, defines the
    # conservative local cut.  It is a proposal constraint only.
    return (
        Cut(
            normal=normal,
            boundary=valid.point.copy(),
            source_anchor=accepted.point.copy(),
            branch_token=accepted.branch_token,
            rank=accepted.rank,
            scaling=accepted.scaling.copy(),
        ),
        "learned",
    )


def solve(
    problem: Problem,
    start: Sequence[float],
    *,
    callback_cap: int,
    arm: str,
    configuration: Configuration = DEFAULT,
    fixed_work: bool = True,
) -> Outcome:
    if arm not in {"control", "candidate"}:
        raise ValueError("arm must be control or candidate")
    runtime = Runtime(problem, callback_cap)
    current = runtime.observe(start)
    bundle = CutBundle()
    solved = False
    status = "budget"
    padding = qp_solves = accepted_steps = 0
    if (
        current is None
        or not current.finite
        or current.opaque
        or not current.semantics_valid
        or current.point.shape != (int(problem.dimension),)
    ):
        status = "invalid-start-fail-closed"
        point = np.asarray(start, dtype=float).copy()
        return Outcome(
            False,
            point,
            runtime.callbacks,
            runtime.invalid,
            runtime.valid,
            runtime.nonfinite,
            runtime.canonical_replays,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            status,
            0,
        )

    radius = configuration.initial_radius
    invalid_streak = 0
    side_enabled = arm == "candidate"
    while runtime.remaining > 1:
        residual_norm = float(np.linalg.norm(current.residual, ord=np.inf))
        if residual_norm <= configuration.root_tolerance and not solved:
            solved = runtime.replay(current.point)
            status = "canonical-root" if solved else "replay-rejected"
            if solved and not fixed_work:
                break
        if solved:
            repeated = runtime.observe(current.point)
            if repeated is None:
                break
            padding += 1
            continue

        active_cuts = bundle.cuts if side_enabled else ()
        proposal = _step(current, radius, active_cuts, configuration)
        qp_solves += 1
        if proposal is None or not np.all(np.isfinite(proposal)):
            side_enabled = False
            bundle.clear()
            status = "qp-fail-closed"
            proposal = _step(current, radius, (), configuration)
            if proposal is None:
                break
        trial = runtime.observe(current.point + proposal)
        if trial is None or not trial.finite or trial.opaque:
            side_enabled = False
            bundle.clear()
            radius *= 0.5
            status = "nonfinite-opaque-fail-closed"
            if radius < configuration.minimum_radius:
                break
            continue
        if not _compatible(current, trial):
            bundle.clear()
            side_enabled = False
            radius *= 0.5
            status = "branch-rank-scaling-fail-closed"
            continue
        if not trial.semantics_valid:
            invalid_streak += 1
            if side_enabled and invalid_streak >= 2:
                cut, cut_status = _learn_cut(runtime, current, trial, configuration)
                status = cut_status
                if cut is None:
                    side_enabled = False
                    bundle.clear()
                else:
                    if bundle.cuts:
                        cosine = min(float(old.normal @ cut.normal) for old in bundle.cuts)
                        if cosine < -0.35:
                            bundle.disagreements += 1
                    bundle.cuts.append(cut)
                    bundle.cuts[:] = bundle.cuts[-configuration.maximum_cuts :]
                    bundle.learned += 1
                    bundle.maximum_retained = max(bundle.maximum_retained, len(bundle.cuts))
                    radius = min(
                        configuration.maximum_radius,
                        max(radius, float(np.linalg.norm(current.scaling * proposal, ord=np.inf))),
                    )
                    if bundle.disagreements >= configuration.maximum_cut_disagreements:
                        side_enabled = False
                        bundle.clear()
                        status = "strongly-nonconvex-cut-disagreement"
            else:
                # The D0 target is the existing far poor-model churn mode:
                # semantic rejection does not supply an achieved/predicted
                # ratio, so the ordinary radius can repeat the same remote
                # invalid trial.  The side waits for a repeated observation
                # before learning; the control deliberately remains that
                # unchanged no-information policy.
                pass
            if radius < configuration.minimum_radius:
                status = "radius-floor"
                break
            continue

        invalid_streak = 0
        old_norm = 0.5 * float(current.residual @ current.residual)
        new_norm = 0.5 * float(trial.residual @ trial.residual)
        predicted_residual = current.residual + current.jacobian @ proposal
        predicted = old_norm - 0.5 * float(predicted_residual @ predicted_residual)
        actual = old_norm - new_norm
        ratio = actual / predicted if predicted > 1.0e-16 else 0.0
        if side_enabled and bundle.cuts and ratio < configuration.model_disagreement_ratio:
            side_enabled = False
            bundle.clear()
            radius *= 0.5
            status = "strongly-nonconvex-model-disagreement"
            continue
        if actual > max(1.0e-13, 1.0e-8 * old_norm):
            movement = float(np.linalg.norm(current.scaling * proposal, ord=np.inf))
            current = trial
            accepted_steps += 1
            if movement > configuration.movement_flush_radii * radius:
                bundle.clear()
            radius = min(configuration.maximum_radius, radius * (1.35 if ratio > 0.5 else 1.0))
            status = "accepted"
        else:
            if side_enabled and bundle.cuts:
                # A cut bundle is local to its accepted anchor.  If its face
                # blocks every residual-model descent direction, retire it
                # instead of treating that local outer approximation as a
                # feasibility certificate.
                bundle.clear()
                radius = max(0.1, radius * 0.65)
                status = "stale-cut-bundle-retired"
            else:
                radius *= 0.5
                status = "no-model-progress"
            if radius < configuration.minimum_radius:
                break

    if not solved and runtime.remaining > 0:
        residual_norm = float(np.linalg.norm(current.residual, ord=np.inf))
        if residual_norm <= configuration.root_tolerance:
            solved = runtime.replay(current.point)
            status = "canonical-root" if solved else "replay-rejected"
    while fixed_work and runtime.remaining > 0:
        if runtime.observe(current.point) is None:
            break
        padding += 1
    if not solved and bundle.learned > 0 and "fail-closed" not in status:
        status = "local-cut-model-unresolved-fail-closed"
    return Outcome(
        solved,
        current.point.copy(),
        runtime.callbacks,
        runtime.invalid,
        runtime.valid,
        runtime.nonfinite,
        runtime.canonical_replays,
        bundle.learned,
        len(bundle.cuts),
        bundle.maximum_retained,
        bundle.flushes,
        bundle.disagreements,
        qp_solves,
        accepted_steps,
        status,
        padding,
    )


__all__ = [
    "Configuration",
    "Cut",
    "CutBundle",
    "DEFAULT",
    "Observation",
    "Outcome",
    "portfolio_trace",
    "solve",
    "solve_small_dense_qp",
]
