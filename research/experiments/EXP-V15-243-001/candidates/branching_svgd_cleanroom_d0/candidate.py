"""Clean-room D0 prototype of role-coloured Branching SVGD.

This module is deliberately self-contained.  It has no connection to the formal
solver/scorer and exposes only a score oracle plus source-validity predicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal, Sequence

import numpy as np


Role = Literal["E", "O", "S"]
ScoreOracle = Callable[[np.ndarray], np.ndarray]
ValidityOracle = Callable[[np.ndarray], bool]


@dataclass(frozen=True)
class Config:
    generations: int = 7
    step_size: float = 0.12
    max_normalized_step: float = 0.35
    child_sigma: float = 0.85
    explorer_birth_probability: float = 0.50
    spine_birth_low: int = 1
    spine_birth_high: int = 3
    minimum_bandwidth_squared: float = 0.04


@dataclass
class Particle:
    point: np.ndarray
    role: Role
    identity: int
    parent: int | None
    generation: int


@dataclass
class Telemetry:
    generations_completed: int = 0
    svgd_updates: int = 0
    score_calls: int = 0
    finite_score_fallbacks: int = 0
    source_rejections: int = 0
    moved_particles: int = 0
    nonzero_repulsion_updates: int = 0
    offspring_attempted: dict[str, int] = field(
        default_factory=lambda: {"E": 0, "O": 0, "S": 0}
    )
    offspring_accepted: dict[str, int] = field(
        default_factory=lambda: {"E": 0, "O": 0, "S": 0}
    )
    old_particles_retained: int = 0
    deaths: int = 0
    uniform_spine_draws: int = 0
    unique_spine_checks: int = 0
    role_counts: list[dict[str, int]] = field(default_factory=list)
    population_counts: list[int] = field(default_factory=list)
    additions_by_generation: list[int] = field(default_factory=list)


@dataclass
class RunResult:
    particles: list[Particle]
    telemetry: Telemetry

    @property
    def points(self) -> np.ndarray:
        return np.stack([p.point for p in self.particles])


def portfolio_trace(lane_count: int = 4) -> tuple[str, ...]:
    """A truth-blind 75/25 quota: lane four is the only side lane."""
    if lane_count <= 0 or lane_count % 4:
        raise ValueError("lane_count must be a positive multiple of four")
    return tuple("side" if ordinal % 4 == 3 else "baseline" for ordinal in range(lane_count))


def _normalise(points: np.ndarray, origin: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return (points - origin) / scale


def _denormalise(points: np.ndarray, origin: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return origin + points * scale


def _svgd_direction(
    z: np.ndarray,
    score_z: np.ndarray,
    minimum_bandwidth_squared: float,
) -> tuple[np.ndarray, bool]:
    """Standard RBF SVGD direction in dimensionless source coordinates."""
    differences = z[:, None, :] - z[None, :, :]
    squared = np.einsum("ijk,ijk->ij", differences, differences)
    upper = squared[np.triu_indices(len(z), 1)]
    positive = upper[upper > 0.0]
    median = float(np.median(positive)) if len(positive) else minimum_bandwidth_squared
    bandwidth_squared = max(
        minimum_bandwidth_squared,
        median / max(np.log(float(len(z)) + 1.0), 1.0),
    )
    kernel = np.exp(-0.5 * squared / bandwidth_squared)
    attraction = kernel.T @ score_z
    repulsion = -np.sum(kernel[:, :, None] * differences, axis=0) / bandwidth_squared
    direction = (attraction + repulsion) / float(len(z))
    return direction, bool(np.linalg.norm(repulsion) > 1.0e-14)


def _improve(
    particles: list[Particle],
    score: ScoreOracle,
    valid: ValidityOracle,
    origin: np.ndarray,
    scale: np.ndarray,
    config: Config,
    telemetry: Telemetry,
) -> None:
    points = np.stack([p.point for p in particles])
    z = _normalise(points, origin, scale)
    score_z = np.empty_like(z)
    for ordinal, point in enumerate(points):
        raw = np.asarray(score(point), dtype=float)
        telemetry.score_calls += 1
        if raw.shape != point.shape or not np.all(np.isfinite(raw)):
            raw = np.zeros_like(point)
            telemetry.finite_score_fallbacks += 1
        score_z[ordinal] = raw * scale
    direction, repulsion_active = _svgd_direction(
        z, score_z, config.minimum_bandwidth_squared
    )
    if repulsion_active:
        telemetry.nonzero_repulsion_updates += 1
    norms = np.linalg.norm(direction, axis=1)
    factors = np.minimum(1.0, config.max_normalized_step / np.maximum(norms, 1.0e-15))
    proposed_z = z + config.step_size * direction * factors[:, None]
    proposed = _denormalise(proposed_z, origin, scale)
    for particle, before, after in zip(particles, points, proposed, strict=True):
        if np.all(np.isfinite(after)) and valid(after):
            if not np.array_equal(before, after):
                telemetry.moved_particles += 1
            particle.point = after
        else:
            telemetry.source_rejections += 1
    telemetry.svgd_updates += 1


def _count_roles(particles: Sequence[Particle]) -> dict[str, int]:
    return {role: sum(p.role == role for p in particles) for role in ("E", "O", "S")}


def _check_unique_spine(particles: Sequence[Particle], telemetry: Telemetry) -> None:
    telemetry.unique_spine_checks += 1
    if sum(p.role == "S" for p in particles) != 1:
        raise AssertionError("branching state must contain exactly one spine")


def run_branching_svgd(
    initial_points: np.ndarray,
    score: ScoreOracle,
    valid: ValidityOracle,
    *,
    origin: np.ndarray | None = None,
    scale: np.ndarray | None = None,
    seed: int = 0,
    config: Config = Config(),
) -> RunResult:
    """Run improvement followed by seven role-coloured branch/improve epochs."""
    initial = np.asarray(initial_points, dtype=float)
    if initial.ndim != 2 or len(initial) < 2:
        raise ValueError("initial_points must be an n-by-d array with n >= 2")
    dimension = initial.shape[1]
    origin_array = np.zeros(dimension) if origin is None else np.asarray(origin, dtype=float)
    scale_array = np.ones(dimension) if scale is None else np.asarray(scale, dtype=float)
    if origin_array.shape != (dimension,) or scale_array.shape != (dimension,):
        raise ValueError("origin and scale must match the point dimension")
    if np.any(~np.isfinite(scale_array)) or np.any(scale_array <= 0.0):
        raise ValueError("scale must be finite and strictly positive")
    if not all(valid(point) for point in initial):
        raise ValueError("all initial points must pass source validity")

    rng = np.random.default_rng(seed)
    initial_spine = int(rng.integers(len(initial)))
    telemetry = Telemetry(population_counts=[len(initial)])
    particles = [
        Particle(point.copy(), "S" if ordinal == initial_spine else "E", ordinal, None, 0)
        for ordinal, point in enumerate(initial)
    ]
    next_identity = len(particles)
    _check_unique_spine(particles, telemetry)
    telemetry.role_counts.append(_count_roles(particles))
    _improve(particles, score, valid, origin_array, scale_array, config, telemetry)

    for generation in range(1, config.generations + 1):
        old = list(particles)
        children: list[Particle] = []
        for parent in old:
            if parent.role == "E":
                births = int(rng.random() < config.explorer_birth_probability)
            elif parent.role == "S":
                births = int(rng.integers(config.spine_birth_low, config.spine_birth_high + 1))
            else:
                births = 0
            telemetry.offspring_attempted[parent.role] += births
            parent_z = _normalise(parent.point[None, :], origin_array, scale_array)[0]
            for _ in range(births):
                child_z = parent_z + config.child_sigma * rng.standard_normal(dimension)
                child_point = _denormalise(child_z[None, :], origin_array, scale_array)[0]
                if not np.all(np.isfinite(child_point)) or not valid(child_point):
                    telemetry.source_rejections += 1
                    continue
                children.append(
                    Particle(child_point, "E", next_identity, parent.identity, generation)
                )
                next_identity += 1
                telemetry.offspring_accepted[parent.role] += 1

        # No particle is deleted.  The prior generation is retained and recoloured O.
        for parent in old:
            parent.role = "O"
        telemetry.old_particles_retained += len(old)
        particles = old + children
        selected = int(rng.integers(len(particles)))
        telemetry.uniform_spine_draws += 1
        particles[selected].role = "S"
        _check_unique_spine(particles, telemetry)
        telemetry.additions_by_generation.append(len(children))
        telemetry.population_counts.append(len(particles))
        telemetry.role_counts.append(_count_roles(particles))
        _improve(particles, score, valid, origin_array, scale_array, config, telemetry)
        telemetry.generations_completed += 1

    return RunResult(particles, telemetry)


def run_deterministic_svgd(
    initial_points: np.ndarray,
    score: ScoreOracle,
    valid: ValidityOracle,
    *,
    origin: np.ndarray | None = None,
    scale: np.ndarray | None = None,
    config: Config = Config(),
) -> RunResult:
    """Fixed-population deterministic control: the repository's old mechanism."""
    initial = np.asarray(initial_points, dtype=float)
    dimension = initial.shape[1]
    origin_array = np.zeros(dimension) if origin is None else np.asarray(origin, dtype=float)
    scale_array = np.ones(dimension) if scale is None else np.asarray(scale, dtype=float)
    telemetry = Telemetry(population_counts=[len(initial)])
    particles = [Particle(point.copy(), "O", ordinal, None, 0) for ordinal, point in enumerate(initial)]
    for _ in range(config.generations + 1):
        _improve(particles, score, valid, origin_array, scale_array, config, telemetry)
        telemetry.generations_completed += 1
    return RunResult(particles, telemetry)


def run_count_matched_immigration(
    initial_points: np.ndarray,
    additions_by_generation: Sequence[int],
    score: ScoreOracle,
    valid: ValidityOracle,
    *,
    origin: np.ndarray | None = None,
    scale: np.ndarray | None = None,
    seed: int = 0,
    config: Config = Config(),
) -> RunResult:
    """Count/work-matched control with memoryless global immigrants.

    Each child is drawn around the original population centroid; unlike BSVGD it
    cannot continue a successful parent's trajectory across generations.
    """
    if len(additions_by_generation) != config.generations:
        raise ValueError("one immigration count is required per generation")
    initial = np.asarray(initial_points, dtype=float)
    dimension = initial.shape[1]
    origin_array = np.zeros(dimension) if origin is None else np.asarray(origin, dtype=float)
    scale_array = np.ones(dimension) if scale is None else np.asarray(scale, dtype=float)
    rng = np.random.default_rng(seed)
    telemetry = Telemetry(population_counts=[len(initial)])
    particles = [Particle(point.copy(), "O", ordinal, None, 0) for ordinal, point in enumerate(initial)]
    initial_z = _normalise(initial, origin_array, scale_array)
    centre_z = np.mean(initial_z, axis=0)
    next_identity = len(particles)
    _improve(particles, score, valid, origin_array, scale_array, config, telemetry)
    for generation, requested in enumerate(additions_by_generation, start=1):
        accepted = 0
        attempts = 0
        while accepted < requested and attempts < max(8 * requested, 1):
            attempts += 1
            point_z = centre_z + config.child_sigma * rng.standard_normal(dimension)
            point = _denormalise(point_z[None, :], origin_array, scale_array)[0]
            if not np.all(np.isfinite(point)) or not valid(point):
                telemetry.source_rejections += 1
                continue
            particles.append(Particle(point, "O", next_identity, None, generation))
            next_identity += 1
            accepted += 1
        if accepted != requested:
            raise RuntimeError("count-matched immigration could not satisfy source validity")
        telemetry.additions_by_generation.append(accepted)
        telemetry.population_counts.append(len(particles))
        _improve(particles, score, valid, origin_array, scale_array, config, telemetry)
        telemetry.generations_completed += 1
    return RunResult(particles, telemetry)


__all__ = [
    "Config",
    "Particle",
    "RunResult",
    "Telemetry",
    "_svgd_direction",
    "portfolio_trace",
    "run_branching_svgd",
    "run_count_matched_immigration",
    "run_deterministic_svgd",
]
