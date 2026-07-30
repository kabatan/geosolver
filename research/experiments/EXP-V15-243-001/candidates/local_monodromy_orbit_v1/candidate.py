"""Disposable D0 prototype for a local-germ monodromy side lane.

The code deliberately owns no solver backend.  It receives a rank-deficient
local germ, follows a small generic slice loop, records the induced permutation
of localized witness points, and uses permutation orbits plus tangent labels to
diversify proposals.  Every emitted real proposal is replayed against the
original source residual and guard.
"""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from typing import Callable, Iterable, Sequence

import numpy as np


SCHEMA = "geotarget.exp-v15-243.local-monodromy-orbit/v1"
BASELINE_PERIOD = 4
DEFAULT_STEPS = 96
MAX_FIBRE_DEGREE = 6
SOURCE_TOL = 5.0e-8
REAL_TOL = 2.0e-9


FibreCoefficients = Callable[[complex], Sequence[complex]]
ToSource = Callable[[complex, complex], np.ndarray]
SourceResidual = Callable[[np.ndarray], Sequence[complex]]
SourceGuard = Callable[[np.ndarray], bool]


@dataclass(frozen=True)
class LocalGermProblem:
    singular_point: np.ndarray
    local_jacobian_rank: int
    projection_radius: float
    fibre_coefficients: FibreCoefficients
    to_source: ToSource
    source_residual: SourceResidual
    source_guard: SourceGuard
    ambient_dimension: int = 2
    expected_codimension: int = 1
    opaque: bool = False


@dataclass(frozen=True)
class LocalProposal:
    point: np.ndarray
    orbit_ordinal: int
    witness_ordinal: int
    tangent: tuple[float, ...]


@dataclass(frozen=True)
class OrbitLedger:
    activated: bool
    reason: str
    directions: tuple[int, ...]
    permutations: tuple[tuple[int, ...], ...]
    orbits: tuple[tuple[int, ...], ...]
    orbit_tangents: tuple[tuple[tuple[float, ...], ...], ...]
    proposals: tuple[LocalProposal, ...]
    rejected_nonreal: int
    rejected_replay: int
    path_steps: int


@dataclass(frozen=True)
class PortfolioResult:
    proposals: tuple[np.ndarray, ...]
    ledger: OrbitLedger
    route_trace: tuple[str, ...]
    baseline_digest_before: str
    baseline_digest_after: str


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root

    def groups(self) -> tuple[tuple[int, ...], ...]:
        grouped: dict[int, list[int]] = {}
        for item in range(len(self.parent)):
            grouped.setdefault(self.find(item), []).append(item)
        return tuple(sorted((tuple(items) for items in grouped.values()), key=lambda x: x[0]))


def route_trace(starts: int = 16) -> tuple[str, ...]:
    """Reserve exactly one quarter of starts for the disposable side lane."""

    if starts < BASELINE_PERIOD or starts % BASELINE_PERIOD:
        raise ValueError("starts must be a positive multiple of four")
    return tuple("local_monodromy" if i % BASELINE_PERIOD == 3 else "baseline" for i in range(starts))


def _point_digest(points: Sequence[np.ndarray]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for point in points:
        array = np.asarray(point, dtype="<f8")
        digest.update(array.shape[0].to_bytes(4, "little"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def _root_sort_key(value: complex) -> tuple[float, float]:
    return (round(float(value.real), 14), round(float(value.imag), 14))


def _fibre_roots(problem: LocalGermProblem, parameter: complex) -> tuple[complex, ...]:
    coefficients = np.asarray(problem.fibre_coefficients(parameter), dtype=np.complex128)
    if coefficients.ndim != 1 or not 2 <= coefficients.size <= MAX_FIBRE_DEGREE + 1:
        raise ValueError("unsupported fibre polynomial degree")
    if not np.all(np.isfinite(coefficients.real)) or not np.all(np.isfinite(coefficients.imag)):
        raise ValueError("non-finite fibre coefficients")
    scale = float(np.max(np.abs(coefficients)))
    if scale == 0.0 or abs(coefficients[0]) <= 1.0e-14 * scale:
        raise ValueError("fibre degree changed on the loop")
    roots = np.roots(coefficients / scale)
    if roots.size != coefficients.size - 1:
        raise ValueError("fibre root count changed")
    if not np.all(np.isfinite(roots.real)) or not np.all(np.isfinite(roots.imag)):
        raise ValueError("non-finite fibre root")
    return tuple(complex(root) for root in roots)


def _minimum_assignment(left: Sequence[complex], right: Sequence[complex]) -> tuple[int, ...]:
    if len(left) != len(right) or not left:
        raise ValueError("assignment requires equal nonempty fibres")
    best: tuple[int, ...] | None = None
    best_cost = math.inf
    for permutation in itertools.permutations(range(len(right))):
        cost = sum(abs(left[i] - right[permutation[i]]) ** 2 for i in range(len(left)))
        if cost < best_cost:
            best_cost = float(cost)
            best = tuple(permutation)
    assert best is not None
    return best


def _track_loop(
    problem: LocalGermProblem,
    *,
    direction: int,
    steps: int,
    initial_order: Sequence[int] | None,
) -> tuple[tuple[complex, ...], tuple[int, ...]]:
    if direction not in (-1, 1):
        raise ValueError("loop direction must be -1 or +1")
    radius = float(problem.projection_radius)
    initial = tuple(sorted(_fibre_roots(problem, complex(radius)), key=_root_sort_key))
    if initial_order is not None:
        order = tuple(int(i) for i in initial_order)
        if sorted(order) != list(range(len(initial))):
            raise ValueError("initial root labels must be a permutation")
        initial = tuple(initial[i] for i in order)
    tracked = initial
    for step in range(1, steps + 1):
        angle = direction * 2.0 * math.pi * step / steps
        parameter = radius * complex(math.cos(angle), math.sin(angle))
        raw = _fibre_roots(problem, parameter)
        assignment = _minimum_assignment(tracked, raw)
        next_tracked = tuple(raw[index] for index in assignment)

        # A step must be small relative to the current fibre separation.  This
        # is an outcome-blind fail-closed guard against a spurious permutation.
        if len(next_tracked) > 1:
            separation = min(
                abs(next_tracked[i] - next_tracked[j])
                for i in range(len(next_tracked))
                for j in range(i + 1, len(next_tracked))
            )
            movement = max(abs(next_tracked[i] - tracked[i]) for i in range(len(tracked)))
            if separation <= 1.0e-12 or movement > 0.35 * separation:
                raise ValueError("ambiguous local path matching")
        tracked = next_tracked
    endpoint_assignment = _minimum_assignment(tracked, initial)
    return initial, endpoint_assignment


def canonical_source_replay(problem: LocalGermProblem, point: np.ndarray) -> bool:
    source_point = np.asarray(point, dtype=float)
    if source_point.ndim != 1 or source_point.size != problem.ambient_dimension:
        return False
    if not np.all(np.isfinite(source_point)):
        return False
    try:
        if not bool(problem.source_guard(source_point)):
            return False
        residual = np.asarray(problem.source_residual(source_point), dtype=np.complex128)
    except Exception:
        return False
    if residual.ndim != 1 or residual.size == 0:
        return False
    if not np.all(np.isfinite(residual.real)) or not np.all(np.isfinite(residual.imag)):
        return False
    return float(np.max(np.abs(residual))) <= SOURCE_TOL


def _real_source_point(problem: LocalGermProblem, root: complex) -> np.ndarray | None:
    source = np.asarray(problem.to_source(complex(problem.projection_radius), root), dtype=np.complex128)
    if source.ndim != 1 or source.size != problem.ambient_dimension:
        return None
    if not np.all(np.isfinite(source.real)) or not np.all(np.isfinite(source.imag)):
        return None
    if float(np.max(np.abs(source.imag))) > REAL_TOL:
        return None
    return np.asarray(source.real, dtype=float)


def _tangent(problem: LocalGermProblem, point: np.ndarray) -> tuple[float, ...]:
    displacement = np.asarray(point, dtype=float) - np.asarray(problem.singular_point, dtype=float)
    norm = float(np.linalg.norm(displacement))
    if not math.isfinite(norm) or norm <= 1.0e-15:
        return tuple(0.0 for _ in range(problem.ambient_dimension))
    return tuple(float(value) for value in displacement / norm)


def _deduplicate_proposals(proposals: Iterable[LocalProposal]) -> tuple[LocalProposal, ...]:
    retained: list[LocalProposal] = []
    for proposal in proposals:
        if any(np.linalg.norm(proposal.point - previous.point) <= 1.0e-9 for previous in retained):
            continue
        retained.append(proposal)
    return tuple(retained)


def _inactive(reason: str) -> OrbitLedger:
    return OrbitLedger(False, reason, (), (), (), (), (), 0, 0, 0)


def discover_local_orbits(
    problem: LocalGermProblem,
    *,
    directions: Sequence[int] = (1, -1),
    steps: int = DEFAULT_STEPS,
    initial_order: Sequence[int] | None = None,
) -> OrbitLedger:
    """Compute a local witness permutation ledger and replay real proposals."""

    if problem.opaque:
        return _inactive("opaque_fallback")
    if problem.ambient_dimension != 2 or problem.expected_codimension != 1:
        return _inactive("unsupported_local_shape")
    if problem.local_jacobian_rank >= problem.expected_codimension:
        return _inactive("regular_germ_fallback")
    if not math.isfinite(problem.projection_radius) or problem.projection_radius <= 0.0:
        return _inactive("invalid_projection_radius")
    if steps < 24:
        return _inactive("insufficient_loop_resolution")

    try:
        tracked = [
            _track_loop(
                problem,
                direction=int(direction),
                steps=steps,
                initial_order=initial_order,
            )
            for direction in directions
        ]
    except Exception as error:
        return _inactive(f"tracking_failed:{type(error).__name__}")

    initial = tracked[0][0]
    if any(len(other_initial) != len(initial) for other_initial, _ in tracked):
        return _inactive("inconsistent_fibre_size")
    permutations = tuple(permutation for _, permutation in tracked)
    union_find = _UnionFind(len(initial))
    for permutation in permutations:
        for left, right in enumerate(permutation):
            union_find.union(left, right)
    orbits = union_find.groups()
    orbit_by_witness = {
        witness: orbit_ordinal
        for orbit_ordinal, orbit in enumerate(orbits)
        for witness in orbit
    }

    rejected_nonreal = 0
    rejected_replay = 0
    proposals: list[LocalProposal] = []
    for witness_ordinal, root in enumerate(initial):
        point = _real_source_point(problem, root)
        if point is None:
            rejected_nonreal += 1
            continue
        if not canonical_source_replay(problem, point):
            rejected_replay += 1
            continue
        proposals.append(
            LocalProposal(
                point=point,
                orbit_ordinal=orbit_by_witness[witness_ordinal],
                witness_ordinal=witness_ordinal,
                tangent=_tangent(problem, point),
            )
        )
    proposals = list(_deduplicate_proposals(proposals))
    proposals.sort(
        key=lambda proposal: (
            proposal.orbit_ordinal,
            tuple(round(value, 12) for value in proposal.tangent),
            tuple(round(float(value), 12) for value in proposal.point),
        )
    )
    orbit_tangents: list[tuple[tuple[float, ...], ...]] = []
    for orbit_ordinal in range(len(orbits)):
        tangents = {
            tuple(round(value, 12) for value in proposal.tangent)
            for proposal in proposals
            if proposal.orbit_ordinal == orbit_ordinal
        }
        orbit_tangents.append(tuple(sorted(tangents)))
    return OrbitLedger(
        activated=True,
        reason="local_rank_deficient_germ",
        directions=tuple(int(direction) for direction in directions),
        permutations=permutations,
        orbits=orbits,
        orbit_tangents=tuple(orbit_tangents),
        proposals=tuple(proposals),
        rejected_nonreal=rejected_nonreal,
        rejected_replay=rejected_replay,
        path_steps=steps * len(tuple(directions)),
    )


def run_portfolio(
    problem: LocalGermProblem,
    baseline_proposals: Sequence[np.ndarray],
    *,
    starts: int = 16,
    directions: Sequence[int] = (1, -1),
    steps: int = DEFAULT_STEPS,
    initial_order: Sequence[int] | None = None,
) -> PortfolioResult:
    """Preserve the baseline objects and append only replayed side proposals."""

    trace = route_trace(starts)
    baseline = tuple(np.array(point, dtype=float, copy=True) for point in baseline_proposals)
    before = _point_digest(baseline)
    ledger = discover_local_orbits(
        problem,
        directions=directions,
        steps=steps,
        initial_order=initial_order,
    )
    retained = list(baseline)
    for proposal in ledger.proposals:
        if any(np.linalg.norm(proposal.point - point) <= 1.0e-9 for point in retained):
            continue
        retained.append(np.array(proposal.point, copy=True))
    after = _point_digest(baseline)
    return PortfolioResult(tuple(retained), ledger, trace, before, after)
