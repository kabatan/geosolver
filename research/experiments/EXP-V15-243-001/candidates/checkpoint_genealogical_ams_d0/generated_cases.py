"""Target-free generated sources for checkpoint-genealogical AMS D0."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import SimpleNamespace
from typing import Sequence

import numpy as np

from candidate import StartRuntime


@dataclass(frozen=True)
class Observation:
    residual: np.ndarray
    finite: bool
    semantics_valid: bool
    violation_vector: np.ndarray


@dataclass(frozen=True)
class FamilySpec:
    name: str
    category: str
    roots_x: tuple[float, ...] = ()


PANEL = (
    FamilySpec("narrow-polynomial-multiroot", "positive", (-0.48, 0.0, 0.48)),
    FamilySpec("banana-basin-multiroot", "positive", (-0.62, 0.08, 0.66)),
    FamilySpec(
        "transcendental-residual-ridge", "positive", (-0.52, 0.0, 0.52)
    ),
    FamilySpec("guard-invalid-low-residual", "negative"),
    FamilySpec("flat-no-root", "negative"),
    FamilySpec("score-misleading-near-miss", "near_miss"),
    FamilySpec("opaque-evaluator", "negative"),
)


def _poly_and_derivative(x: float, roots: Sequence[float]) -> tuple[float, float]:
    value = 1.0
    for root in roots:
        value *= x - root
    derivative = 0.0
    for omitted in range(len(roots)):
        term = 1.0
        for index, root in enumerate(roots):
            if index != omitted:
                term *= x - root
        derivative += term
    return value, derivative


class GeneratedSource:
    """A source formulation; reporting metadata never enters the candidate."""

    dimension = 2
    residual_dimension = 2

    def __init__(
        self,
        spec: FamilySpec,
        seed: int,
        *,
        coordinate_signed_permutation: bool = False,
        residual_swap_sign: bool = False,
    ) -> None:
        self.spec = spec
        self.seed = int(seed)
        self.coordinate_signed_permutation = bool(coordinate_signed_permutation)
        self.residual_swap_sign = bool(residual_swap_sign)
        self.callbacks = 0
        if coordinate_signed_permutation:
            self.coordinate_map = np.asarray(((0.0, -1.0), (1.0, 0.0)))
        else:
            self.coordinate_map = np.eye(2)
        if residual_swap_sign:
            self.residual_map = np.asarray(((0.0, -1.0), (1.0, 0.0)))
        else:
            self.residual_map = np.eye(2)

    def physical(self, point: Sequence[float]) -> np.ndarray:
        return self.coordinate_map @ np.asarray(point, dtype=float)

    def represented(self, physical: Sequence[float]) -> np.ndarray:
        return self.coordinate_map.T @ np.asarray(physical, dtype=float)

    def _raw(self, physical: Sequence[float]) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        x, y = np.asarray(physical, dtype=float)
        name = self.spec.name
        guard = 0.0
        guard_gradient = np.zeros(2, dtype=float)
        if name in {"narrow-polynomial-multiroot", "guard-invalid-low-residual"}:
            roots = self.spec.roots_x or (-0.48, 0.0, 0.48)
            polynomial, derivative = _poly_and_derivative(float(x), roots)
            residual = np.asarray((8.0 * (y - 0.35 * x * x), 1.8 * polynomial))
            jacobian = np.asarray(((-5.6 * x, 8.0), (1.8 * derivative, 0.0)))
            if name == "guard-invalid-low-residual":
                # The numerical roots lie in the forbidden branch x < 0.9.
                guard = max(0.0, 0.9 - float(x))
                if guard > 0.0:
                    guard_gradient[0] = -1.0
        elif name == "banana-basin-multiroot":
            polynomial, derivative = _poly_and_derivative(float(x), self.spec.roots_x)
            curve = 0.72 * (x + 0.18) ** 2 - 0.28
            residual = np.asarray((11.0 * (y - curve), 1.35 * polynomial))
            jacobian = np.asarray(
                ((-15.84 * (x + 0.18), 11.0), (1.35 * derivative, 0.0))
            )
        elif name == "transcendental-residual-ridge":
            # sin(pi*x/0.52) has roots at the declared three local branches.
            residual = np.asarray(
                (7.0 * (y - math.sin(1.7 * x)), 0.34 * math.sin(math.pi * x / 0.52))
            )
            jacobian = np.asarray(
                (
                    (-11.9 * math.cos(1.7 * x), 7.0),
                    (0.34 * math.pi / 0.52 * math.cos(math.pi * x / 0.52), 0.0),
                )
            )
        elif name == "flat-no-root":
            residual = np.asarray((0.04, -0.03))
            jacobian = np.zeros((2, 2), dtype=float)
        elif name == "score-misleading-near-miss":
            residual = np.asarray((6.0 * (y - 0.4 * x * x), 2.5e-6))
            jacobian = np.asarray(((-4.8 * x, 6.0), (0.0, 0.0)))
        elif name == "opaque-evaluator":
            # The analytic facade is deliberately irrelevant: source
            # callbacks are opaque failures and must never become passages.
            residual = np.asarray((x, y))
            jacobian = np.eye(2, dtype=float)
        else:
            raise ValueError(f"unknown generated family: {name}")
        return residual, jacobian, guard, guard_gradient

    def residual_jacobian_guard(
        self, point: Sequence[float]
    ) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        physical = self.physical(point)
        residual, jacobian_physical, guard, guard_gradient_physical = self._raw(
            physical
        )
        residual = self.residual_map @ residual
        jacobian = self.residual_map @ jacobian_physical @ self.coordinate_map
        guard_gradient = guard_gradient_physical @ self.coordinate_map
        return residual, jacobian, guard, guard_gradient

    def evaluate(self, point: Sequence[float]) -> Observation:
        self.callbacks += 1
        if self.spec.name == "opaque-evaluator":
            raise RuntimeError("generated opaque evaluator")
        residual, _jacobian, guard, _guard_gradient = self.residual_jacobian_guard(point)
        finite = bool(np.all(np.isfinite(residual)) and math.isfinite(guard))
        return Observation(
            residual=np.asarray(residual, dtype=float),
            finite=finite,
            semantics_valid=bool(finite and guard == 0.0),
            violation_vector=np.asarray((guard,), dtype=float),
        )

    def replay(self, point: Sequence[float]) -> bool:
        if self.spec.name == "opaque-evaluator":
            return False
        residual, _jacobian, guard, _guard_gradient = self.residual_jacobian_guard(point)
        return bool(
            np.all(np.isfinite(residual))
            and guard == 0.0
            and float(np.linalg.norm(residual, ord=np.inf)) <= 1.0e-8
        )

    def root_key(self, point: Sequence[float]) -> str:
        physical = self.physical(point)
        # This is generated reporting after replay, never a candidate input.
        return f"{float(physical[0]):+.5f}:{float(physical[1]):+.5f}"

    def start(self, ordinal: int, *, baseline: bool) -> np.ndarray:
        # All policies receive the identical immutable start function.  The
        # central starts are intentionally correlated; AMS may branch only
        # after observing a first-passage level.
        rng = np.random.default_rng(
            np.random.SeedSequence((self.seed, int(ordinal), int(baseline), 7717))
        )
        central = 0.02 if self.spec.category == "positive" else -0.04
        if baseline:
            x = central + float(rng.normal(0.0, 0.035))
            y = 0.75 + float(rng.normal(0.0, 0.08))
        else:
            role = int(ordinal) % 4
            if role == 0:
                x = central + float(rng.normal(0.0, 0.025))
                y = 0.18 + float(rng.normal(0.0, 0.025))
            elif role == 1:
                x = central + float(rng.normal(0.0, 0.04))
                y = 1.4 + float(rng.normal(0.0, 0.1))
            elif role == 2:
                x = central + float(rng.normal(0.0, 0.04))
                y = -1.3 + float(rng.normal(0.0, 0.1))
            else:
                x = central + float(rng.normal(0.0, 0.06))
                y = 2.1 + float(rng.normal(0.0, 0.1))
        return np.clip(self.represented((x, y)), -0.78, 0.78)


class GeneratedProgram:
    dimension = 2
    residual_dimension = 2

    def __init__(self, source: GeneratedSource) -> None:
        self.source = source

    def relation_rows(self, point: Sequence[float]):
        residual, jacobian, _guard, _guard_gradient = (
            self.source.residual_jacobian_guard(point)
        )
        return tuple(
            SimpleNamespace(value=float(residual[index]), derivative=jacobian[index].copy())
            for index in range(2)
        )

    def guard_rows(self, point: Sequence[float]):
        _residual, _jacobian, guard, gradient = self.source.residual_jacobian_guard(point)
        return (SimpleNamespace(value=float(guard), derivative=gradient.copy()),)


def runtime_factory(source: GeneratedSource, *, baseline: bool):
    program = GeneratedProgram(source)
    token_text = (
        f"generated-source:{source.spec.name}:{source.seed}:"
        f"{int(source.coordinate_signed_permutation)}:"
        f"{int(source.residual_swap_sign)}"
    )
    token = hashlib.sha256(token_text.encode("ascii")).digest()

    def make_runtime(ordinal: int) -> StartRuntime:
        start = source.start(ordinal, baseline=baseline)
        return StartRuntime(
            case=source,
            program=program,
            start=start,
            scale=np.ones(2, dtype=float),
            lower=np.full(2, -0.8),
            upper=np.full(2, 0.8),
            source_binding_token=token,
        )

    return make_runtime


def cluster_replayed(source: GeneratedSource, points: Sequence[np.ndarray]) -> tuple[np.ndarray, ...]:
    clusters: list[np.ndarray] = []
    for point in points:
        if not source.replay(point):
            continue
        physical = source.physical(point)
        if all(float(np.linalg.norm(physical - source.physical(old))) > 2.0e-4 for old in clusters):
            clusters.append(np.asarray(point, dtype=float).copy())
    clusters.sort(key=lambda item: tuple(source.physical(item)))
    return tuple(clusters)
