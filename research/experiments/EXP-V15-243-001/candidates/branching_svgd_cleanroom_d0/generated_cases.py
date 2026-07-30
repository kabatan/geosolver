"""Truth-local generated landscapes for Branching-SVGD D0 only.

The candidate receives score/validity callables, never the root centres or the
semantic mask.  Exactification and descriptor checks stay in this generated
runner and are intentionally not reusable solver components.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Literal

import numpy as np


Category = Literal["positive", "negative", "near_miss"]


@dataclass(frozen=True)
class GeneratedProblem:
    family_key: str
    category: Category
    canonical_centres: np.ndarray
    semantic_mask: tuple[bool, ...]
    transform: np.ndarray
    shift: np.ndarray
    source_scale: float
    well_width: float = 0.46
    capture_radius: float = 0.82

    @property
    def dimension(self) -> int:
        return int(self.canonical_centres.shape[1])

    @property
    def public_family(self) -> str:
        digest = hashlib.sha256(self.family_key.encode("utf-8")).hexdigest()
        return f"family-{digest[:8]}"

    @property
    def origin(self) -> np.ndarray:
        return self.shift.copy()

    @property
    def scale(self) -> np.ndarray:
        return np.full(self.dimension, self.source_scale)

    @property
    def world_centres(self) -> np.ndarray:
        return self.shift + (self.transform @ self.canonical_centres.T).T

    def to_canonical(self, point: np.ndarray) -> np.ndarray:
        return np.linalg.solve(self.transform, np.asarray(point) - self.shift)

    def score(self, point: np.ndarray) -> np.ndarray:
        """Gradient of a log Gaussian mixture whose wells are source roots."""
        canonical = self.to_canonical(point)
        delta = self.canonical_centres - canonical
        log_weights = -0.5 * np.sum(delta * delta, axis=1) / self.well_width**2
        log_weights -= np.max(log_weights)
        weights = np.exp(log_weights)
        weights /= np.sum(weights)
        score_canonical = np.sum(weights[:, None] * delta, axis=0) / self.well_width**2
        return np.linalg.solve(self.transform.T, score_canonical)

    def source_valid(self, point: np.ndarray) -> bool:
        if not np.all(np.isfinite(point)):
            return False
        canonical = self.to_canonical(point)
        return bool(np.all(np.abs(canonical) < 8.0))

    def initial_points(self, seed: int, count: int = 4) -> np.ndarray:
        rng = np.random.default_rng(seed)
        primary = self.canonical_centres[0]
        jitter = 0.10 * rng.standard_normal((count, self.dimension))
        canonical = primary + jitter
        return self.shift + (self.transform @ canonical.T).T

    def exactify(self, point: np.ndarray) -> tuple[int | None, bool]:
        """Local generated exactifier followed by semantic/source replay."""
        canonical = self.to_canonical(point)
        distances = np.linalg.norm(self.canonical_centres - canonical, axis=1)
        descriptor = int(np.argmin(distances))
        if float(distances[descriptor]) > self.capture_radius:
            return None, False
        exact_world = self.world_centres[descriptor]
        replay_canonical = self.to_canonical(exact_world)
        source_residual = float(
            np.min(np.linalg.norm(self.canonical_centres - replay_canonical, axis=1))
        )
        source_ok = source_residual <= 1.0e-12 and self.source_valid(exact_world)
        semantic_ok = bool(self.semantic_mask[descriptor])
        return (descriptor if source_ok and semantic_ok else None), (source_ok and not semantic_ok)

    @property
    def expected_descriptors(self) -> frozenset[int]:
        return frozenset(i for i, valid in enumerate(self.semantic_mask) if valid)


def _orthogonal(dimension: int, presentation: str) -> np.ndarray:
    if presentation == "identity":
        return np.eye(dimension)
    if presentation == "reflection":
        result = np.eye(dimension)
        result[0, 0] = -1.0
        return result
    if presentation == "permutation":
        return np.eye(dimension)[::-1]
    if presentation == "rotation":
        if dimension == 1:
            return np.array([[-1.0]])
        angle = 0.731
        result = np.eye(dimension)
        result[:2, :2] = np.array(
            [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
        )
        return result
    raise ValueError(presentation)


def make_problem(
    family: str,
    category: Category,
    *,
    presentation: str = "identity",
    affine_scale: float = 1.0,
) -> GeneratedProblem:
    families = {
        "axial": np.array([[-2.8], [0.4], [3.6]], dtype=float),
        "elbow": np.array([[-2.4, -1.8], [-0.1, 0.5], [2.6, -1.0]], dtype=float),
        "simplex": np.array(
            [
                [-1.8, -1.5, -0.8],
                [0.3, 0.8, 0.4],
                [2.1, -0.2, 1.1],
                [-0.5, 2.3, -1.2],
            ],
            dtype=float,
        ),
    }
    centres = families[family]
    if category == "negative":
        centres = centres[:1]
        semantic = (True,)
    elif category == "near_miss":
        semantic = (True,) + (False,) * (len(centres) - 1)
    else:
        semantic = (True,) * len(centres)
    dimension = centres.shape[1]
    orthogonal = _orthogonal(dimension, presentation)
    transform = affine_scale * orthogonal
    shift = np.linspace(-0.37, 0.41, dimension)
    return GeneratedProblem(
        family_key=family,
        category=category,
        canonical_centres=centres,
        semantic_mask=semantic,
        transform=transform,
        shift=shift,
        source_scale=affine_scale,
    )


def descriptors_from_points(
    problem: GeneratedProblem, points: np.ndarray
) -> tuple[frozenset[int], int]:
    descriptors: set[int] = set()
    semantic_rejections = 0
    for point in points:
        descriptor, rejected_semantic = problem.exactify(point)
        if descriptor is not None:
            descriptors.add(descriptor)
        semantic_rejections += int(rejected_semantic)
    return frozenset(descriptors), semantic_rejections


__all__ = ["GeneratedProblem", "descriptors_from_points", "make_problem"]
