"""Generated semantic cells for the cut-bundle Gauss--Newton D0."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Sequence

import numpy as np

from candidate import Observation


Array = np.ndarray


@dataclass(frozen=True, slots=True)
class LocalModel:
    residual: Callable[[Array], Array]
    jacobian: Callable[[Array], Array]
    guards: tuple[Callable[[Array], bool], ...]
    target: Array | None
    branch_token: str = "smooth-source-branch"
    opaque_outside: Callable[[Array], bool] | None = None
    nonfinite_outside: Callable[[Array], bool] | None = None


@dataclass(slots=True)
class GeneratedProblem:
    model: LocalModel
    start_local: Array
    rotation: Array
    coordinate_scale: Array
    shift: Array
    guard_order: tuple[int, ...]

    @property
    def dimension(self) -> int:
        return int(self.start_local.size)

    @property
    def residual_dimension(self) -> int:
        return int(self.model.residual(self.start_local).size)

    @property
    def start(self) -> Array:
        return self.from_local(self.start_local)

    def from_local(self, local: Sequence[float]) -> Array:
        return self.shift + self.rotation @ (self.coordinate_scale * np.asarray(local, dtype=float))

    def to_local(self, physical: Sequence[float]) -> Array:
        return (self.rotation.T @ (np.asarray(physical, dtype=float) - self.shift)) / self.coordinate_scale

    def observe(self, point: Array) -> Observation:
        local = self.to_local(point)
        opaque = bool(self.model.opaque_outside is not None and self.model.opaque_outside(local))
        forced_nonfinite = bool(
            self.model.nonfinite_outside is not None and self.model.nonfinite_outside(local)
        )
        residual = np.asarray(self.model.residual(local), dtype=float)
        local_jacobian = np.asarray(self.model.jacobian(local), dtype=float)
        inverse = np.diag(1.0 / self.coordinate_scale) @ self.rotation.T
        jacobian = local_jacobian @ inverse
        guard_values = tuple(bool(self.model.guards[index](local)) for index in self.guard_order)
        finite = bool(
            not forced_nonfinite
            and np.all(np.isfinite(local))
            and np.all(np.isfinite(residual))
            and np.all(np.isfinite(jacobian))
        )
        if not finite:
            residual = np.full(self.residual_dimension, math.inf)
            jacobian = np.full((self.residual_dimension, self.dimension), math.nan)
        rank = int(np.linalg.matrix_rank(jacobian)) if finite else -1
        # Uniform rotations use a uniform coordinate scale.  Nonuniform scale
        # metamorphics are run without rotation, making this exact chart data.
        scaling = 1.0 / self.coordinate_scale
        return Observation(
            point=np.asarray(point, dtype=float).copy(),
            residual=residual,
            jacobian=jacobian,
            finite=finite,
            semantics_valid=bool(finite and not opaque and all(guard_values)),
            branch_token=self.model.branch_token,
            rank=rank,
            scaling=scaling.copy(),
            opaque=opaque,
        )

    def canonical_replay(self, point: Array) -> bool:
        fresh = self.observe(np.asarray(point, dtype=float).copy())
        if not fresh.finite or fresh.opaque or not fresh.semantics_valid:
            return False
        if self.model.target is None:
            return False
        local = self.to_local(point)
        return bool(
            np.linalg.norm(local - self.model.target, ord=np.inf) <= 3.0e-5
            and np.linalg.norm(fresh.residual, ord=np.inf) <= 3.0e-5
        )


def _rotation(angle: float) -> Array:
    cosine, sine = math.cos(angle), math.sin(angle)
    return np.asarray(((cosine, -sine), (sine, cosine)), dtype=float)


def _wrap(model: LocalModel, start: Sequence[float], seed: int) -> GeneratedProblem:
    angle = 0.17 * ((seed % 7) - 3)
    scale = np.full(2, 0.8 + 0.04 * (seed % 5))
    shift = np.asarray((0.03 * (seed % 3), -0.025 * (seed % 4)))
    order = tuple(range(len(model.guards)))
    if seed % 2:
        order = tuple(reversed(order))
    return GeneratedProblem(model, np.asarray(start, dtype=float), _rotation(angle), scale, shift, order)


def thin_curved_corridor(seed: int) -> GeneratedProblem:
    curvature = 0.24
    width = 0.115
    epsilon = 0.15
    coupling = 0.20
    target = np.asarray((1.0, curvature))
    def residual(q: Array) -> Array:
        gap = q[0] - 1.0
        cross = q[1] - curvature * q[0] * q[0]
        return np.asarray((gap, epsilon * cross + coupling * gap * gap))
    def jacobian(q: Array) -> Array:
        gap = q[0] - 1.0
        return np.asarray(
            ((1.0, 0.0), (-2.0 * epsilon * curvature * q[0] + 2.0 * coupling * gap, epsilon))
        )
    guards = (
        lambda q: abs(q[1] - curvature * q[0] * q[0]) < width,
        lambda q: -1.35 < q[0] < 1.35,
    )
    return _wrap(LocalModel(residual, jacobian, guards, target), (0.0, 0.0), seed)


def rotated_wedge(seed: int) -> GeneratedProblem:
    coupling = 0.22
    epsilon = 0.12
    slope = 0.22
    target = np.asarray((3.0, 0.0))
    def residual(q: Array) -> Array:
        gap = q[0] - 3.0
        return np.asarray((gap, epsilon * q[1] + coupling * gap * gap))
    def jacobian(q: Array) -> Array:
        gap = q[0] - 3.0
        return np.asarray(((1.0, 0.0), (2.0 * coupling * gap, epsilon)))
    guards = (
        lambda q: q[0] > 0.15,
        lambda q: q[0] < 3.5,
        lambda q: q[1] < slope * q[0],
        lambda q: -q[1] < slope * q[0],
    )
    return _wrap(LocalModel(residual, jacobian, guards, target), (1.0, 0.0), seed + 11)


def disconnected_cells(seed: int) -> GeneratedProblem:
    curvature = 0.18
    width = 0.11
    epsilon = 0.14
    coupling = 0.21
    target = np.asarray((0.95, curvature * 0.95 * 0.95))
    def residual(q: Array) -> Array:
        gap = q[0] - target[0]
        cross = q[1] - curvature * q[0] * q[0]
        return np.asarray((gap, epsilon * cross + coupling * gap * gap))
    def jacobian(q: Array) -> Array:
        gap = q[0] - target[0]
        return np.asarray(
            ((1.0, 0.0), (-2.0 * epsilon * curvature * q[0] + 2.0 * coupling * gap, epsilon))
        )
    def union(q: Array) -> bool:
        curved = -1.25 < q[0] < 1.25 and abs(q[1] - curvature * q[0] * q[0]) < width
        remote = float(np.linalg.norm(q - np.asarray((2.8, 1.7)))) < 0.35
        return bool(curved or remote)
    guards = (union, lambda q: q[0] < 3.4)
    return _wrap(LocalModel(residual, jacobian, guards, target), (0.0, 0.0), seed + 23)


def infeasible_source(seed: int) -> GeneratedProblem:
    model = LocalModel(
        lambda q: q.copy(),
        lambda q: np.eye(2),
        (lambda q: q[0] > 1.0, lambda q: q[0] < -1.0),
        None,
    )
    return _wrap(model, (0.0, 0.0), seed)


def strict_boundary_root(seed: int) -> GeneratedProblem:
    model = LocalModel(
        lambda q: np.asarray((q[0], q[1])),
        lambda q: np.eye(2),
        (lambda q: q[0] < 0.0, lambda q: abs(q[1]) < 1.0),
        None,
    )
    return _wrap(model, (-1.0, 0.0), seed)


def isolated_invalid_near_root(seed: int) -> GeneratedProblem:
    center = np.asarray((1.0, 0.0))
    radius = 0.18
    model = LocalModel(
        lambda q: q - center,
        lambda q: np.eye(2),
        (lambda q: float(np.linalg.norm(q - center)) > radius,),
        None,
    )
    return _wrap(model, (0.0, 0.0), seed)


def nonconvex_cell(seed: int) -> GeneratedProblem:
    target = np.asarray((1.0, 0.0))
    def residual(q: Array) -> Array:
        return np.asarray((math.sin(3.0 * (q[0] - 1.0)), q[1] + 0.8 * (q[0] - 1.0) ** 2))
    def jacobian(q: Array) -> Array:
        return np.asarray(((3.0 * math.cos(3.0 * (q[0] - 1.0)), 0.0), (1.6 * (q[0] - 1.0), 1.0)))
    guards = (lambda q: math.sin(7.0 * q[0]) > -0.25, lambda q: abs(q[1]) < 0.35)
    return _wrap(LocalModel(residual, jacobian, guards, target), (-0.7, 0.15), seed)


def nonfinite_or_opaque(seed: int, *, opaque: bool) -> GeneratedProblem:
    target = np.asarray((1.0, 0.0))
    predicate = lambda q: q[0] > 0.3
    model = LocalModel(
        lambda q: q - target,
        lambda q: np.eye(2),
        (lambda q: True,),
        None,
        opaque_outside=predicate if opaque else None,
        nonfinite_outside=predicate if not opaque else None,
    )
    return _wrap(model, (-1.0, 0.0), seed)


POSITIVE_FAMILIES = (thin_curved_corridor, rotated_wedge, disconnected_cells)
NEGATIVE_FAMILIES = (
    infeasible_source,
    strict_boundary_root,
    isolated_invalid_near_root,
    nonconvex_cell,
    lambda seed: nonfinite_or_opaque(seed, opaque=False),
    lambda seed: nonfinite_or_opaque(seed, opaque=True),
)


def transformed(problem: GeneratedProblem, kind: str) -> GeneratedProblem:
    if kind == "permutation":
        swap = np.asarray(((0.0, 1.0), (1.0, 0.0)))
        return GeneratedProblem(problem.model, problem.start_local, problem.rotation @ swap, problem.coordinate_scale[::-1], problem.shift, problem.guard_order)
    if kind == "reflection":
        reflect = np.asarray(((-1.0, 0.0), (0.0, 1.0)))
        return GeneratedProblem(problem.model, problem.start_local, problem.rotation @ reflect, problem.coordinate_scale, problem.shift, problem.guard_order)
    if kind == "scale":
        # Keep the diagonal scaling chart exact by removing rotation.
        return GeneratedProblem(problem.model, problem.start_local, np.eye(2), np.asarray((0.55, 1.7)), problem.shift, problem.guard_order)
    if kind == "guard-order":
        return GeneratedProblem(problem.model, problem.start_local, problem.rotation, problem.coordinate_scale, problem.shift, tuple(reversed(problem.guard_order)))
    raise ValueError(kind)


__all__ = [
    "GeneratedProblem",
    "NEGATIVE_FAMILIES",
    "POSITIVE_FAMILIES",
    "disconnected_cells",
    "rotated_wedge",
    "thin_curved_corridor",
    "transformed",
]
