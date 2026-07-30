"""Disposable D0: exceptional-stratum inference from replicated fibres.

The side lane receives an unstable endpoint cluster and a small, explicitly
parameterized source family.  It probes a normalized parameter ball, searches
for replicated fibre coincidence / fibre-rank or dimension jumps, and uses
nearby fibre points only as continuation starts back to the untouched source.
Perturbed problems are never output authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Callable, Iterable, Sequence

import numpy as np


SCHEMA = "geotarget.exp-v15-243.exceptional-stratum-fibre-product/v1"
BASELINE_PERIOD = 4
SOURCE_TOL = 2.0e-8
FIBRE_TOL = 2.0e-7
REAL_TOL = 2.0e-8
PAIR_TOL = 3.0e-5
RANK_TOL = 2.0e-8
INSTABILITY_TOL = 0.20
NEAR_RESIDUAL_TOL = 5.0e-2
MAX_ENDPOINTS = 12
MAX_PROJECTION_FIBRES = 12


FibreSolver = Callable[[np.ndarray], Sequence[np.ndarray]]
Residual = Callable[[np.ndarray, np.ndarray], Sequence[complex]]
Jacobian = Callable[[np.ndarray, np.ndarray], np.ndarray]
Guard = Callable[[np.ndarray, np.ndarray], bool]


@dataclass(frozen=True)
class ParameterizedProblem:
    source_parameter: np.ndarray
    parameter_scale: np.ndarray
    point_scale: np.ndarray
    residual_scale: np.ndarray
    ball_radius: float
    fibre_solver: FibreSolver
    residual: Residual
    jacobian: Jacobian
    guard: Guard
    opaque: bool = False


@dataclass(frozen=True)
class FibreSample:
    parameter: np.ndarray
    normalized_offset: tuple[float, ...]
    endpoints: tuple[np.ndarray, ...]
    unique_real_endpoints: tuple[np.ndarray, ...]
    minimum_pair_gap: float
    minimum_rank: int
    expected_rank: int
    rejected_endpoints: int


@dataclass(frozen=True)
class ExceptionalEvidence:
    activated: bool
    reason: str
    instability_metric: float
    near_source_residuals: int
    samples: int
    fibre_endpoints: int
    replicated_pairs: int
    exceptional_parameter: tuple[float, ...] | None
    exceptional_offset: tuple[float, ...] | None
    signatures: tuple[str, ...]
    projected: int
    rejected_projection: int
    rejected_replay: int


@dataclass(frozen=True)
class PortfolioResult:
    proposals: tuple[np.ndarray, ...]
    evidence: ExceptionalEvidence
    route_trace: tuple[str, ...]
    baseline_digest_before: str
    baseline_digest_after: str


def route_trace(starts: int = 16) -> tuple[str, ...]:
    if starts < BASELINE_PERIOD or starts % BASELINE_PERIOD:
        raise ValueError("starts must be a positive multiple of four")
    return tuple(
        "exceptional_stratum" if ordinal % BASELINE_PERIOD == 3 else "baseline"
        for ordinal in range(starts)
    )


def _point_digest(points: Sequence[np.ndarray]) -> str:
    digest = hashlib.sha256()
    for point in points:
        array = np.asarray(point, dtype="<f8")
        digest.update(array.ndim.to_bytes(2, "little"))
        digest.update(array.shape[0].to_bytes(4, "little"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def _valid_problem(problem: ParameterizedProblem) -> bool:
    p0 = np.asarray(problem.source_parameter, dtype=float)
    pscale = np.asarray(problem.parameter_scale, dtype=float)
    xscale = np.asarray(problem.point_scale, dtype=float)
    rscale = np.asarray(problem.residual_scale, dtype=float)
    return bool(
        p0.ndim == pscale.ndim == xscale.ndim == rscale.ndim == 1
        and p0.size in (1, 2)
        and xscale.size > 0
        and rscale.size > 0
        and pscale.size == p0.size
        and np.all(np.isfinite(p0))
        and np.all(np.isfinite(pscale))
        and np.all(np.isfinite(xscale))
        and np.all(np.isfinite(rscale))
        and np.all(pscale > 0.0)
        and np.all(xscale > 0.0)
        and np.all(rscale > 0.0)
        and math.isfinite(problem.ball_radius)
        and problem.ball_radius > 0.0
    )


def _scaled_residual(problem: ParameterizedProblem, point: np.ndarray, parameter: np.ndarray) -> np.ndarray:
    residual = np.asarray(problem.residual(point, parameter), dtype=np.complex128)
    scale = np.asarray(problem.residual_scale, dtype=float)
    if residual.ndim != 1 or residual.size != scale.size:
        raise ValueError("residual shape changed")
    if not np.all(np.isfinite(residual.real)) or not np.all(np.isfinite(residual.imag)):
        raise ValueError("nonfinite residual")
    return residual / scale


def _scaled_jacobian(problem: ParameterizedProblem, point: np.ndarray, parameter: np.ndarray) -> np.ndarray:
    jacobian = np.asarray(problem.jacobian(point, parameter), dtype=np.complex128)
    if jacobian.shape != (problem.residual_scale.size, problem.point_scale.size):
        raise ValueError("jacobian shape changed")
    if not np.all(np.isfinite(jacobian.real)) or not np.all(np.isfinite(jacobian.imag)):
        raise ValueError("nonfinite jacobian")
    return (
        jacobian
        * np.asarray(problem.point_scale, dtype=float)[np.newaxis, :]
        / np.asarray(problem.residual_scale, dtype=float)[:, np.newaxis]
    )


def canonical_source_replay(problem: ParameterizedProblem, point: np.ndarray) -> bool:
    source = np.asarray(point, dtype=np.complex128)
    if source.ndim != 1 or source.size != problem.point_scale.size:
        return False
    if not np.all(np.isfinite(source.real)) or not np.all(np.isfinite(source.imag)):
        return False
    if float(np.max(np.abs(source.imag), initial=0.0)) > REAL_TOL:
        return False
    real = np.asarray(source.real, dtype=float)
    try:
        if not bool(problem.guard(real, np.asarray(problem.source_parameter, dtype=float))):
            return False
        residual = _scaled_residual(problem, real, np.asarray(problem.source_parameter, dtype=float))
    except Exception:
        return False
    return float(np.max(np.abs(residual), initial=0.0)) <= SOURCE_TOL


def _normalized_gap(problem: ParameterizedProblem, left: np.ndarray, right: np.ndarray) -> float:
    return float(
        np.linalg.norm(
            (np.asarray(left, dtype=np.complex128) - np.asarray(right, dtype=np.complex128))
            / np.asarray(problem.point_scale, dtype=float)
        )
    )


def _deduplicate(problem: ParameterizedProblem, points: Iterable[np.ndarray], tolerance: float = 2.0e-7) -> tuple[np.ndarray, ...]:
    retained: list[np.ndarray] = []
    for point in points:
        candidate = np.asarray(point, dtype=float)
        if any(_normalized_gap(problem, candidate, previous) <= tolerance for previous in retained):
            continue
        retained.append(candidate)
    return tuple(retained)


def _sample_offsets(parameter_dimension: int) -> tuple[np.ndarray, ...]:
    offsets: list[np.ndarray] = [np.zeros(parameter_dimension, dtype=float)]
    if parameter_dimension == 1:
        for radius in (0.25, 0.5, 0.75, 1.0):
            offsets.extend((np.asarray([-radius]), np.asarray([radius])))
    elif parameter_dimension == 2:
        for radius in (0.5, 1.0):
            for ordinal in range(16):
                angle = 2.0 * math.pi * ordinal / 16.0
                offsets.append(radius * np.asarray([math.cos(angle), math.sin(angle)]))
    else:
        raise ValueError("only one- and two-dimensional parameter balls are supported")
    return tuple(offsets)


def _instability(problem: ParameterizedProblem, cluster: Sequence[np.ndarray]) -> tuple[float, int]:
    if not cluster:
        return math.inf, 0
    p0 = np.asarray(problem.source_parameter, dtype=float)
    metric = math.inf
    near_residuals = 0
    finite: list[np.ndarray] = []
    for raw in cluster:
        point = np.asarray(raw, dtype=np.complex128)
        if point.shape != (problem.point_scale.size,) or not np.all(np.isfinite(point)):
            continue
        if float(np.max(np.abs(point.imag), initial=0.0)) > REAL_TOL:
            continue
        real = np.asarray(point.real, dtype=float)
        finite.append(real)
        try:
            residual_norm = float(np.max(np.abs(_scaled_residual(problem, real, p0)), initial=0.0))
            jacobian = _scaled_jacobian(problem, real, p0)
            singular = np.linalg.svd(jacobian, compute_uv=False)
            if singular.size:
                metric = min(metric, float(singular[-1]))
            if SOURCE_TOL < residual_norm <= NEAR_RESIDUAL_TOL:
                near_residuals += 1
        except Exception:
            continue
    for left in range(len(finite)):
        for right in range(left + 1, len(finite)):
            metric = min(metric, _normalized_gap(problem, finite[left], finite[right]))
    return metric, near_residuals


def _sample_fibre(problem: ParameterizedProblem, offset: np.ndarray) -> FibreSample:
    p0 = np.asarray(problem.source_parameter, dtype=float)
    parameter = p0 + problem.ball_radius * np.asarray(problem.parameter_scale, dtype=float) * offset
    raw_endpoints = problem.fibre_solver(np.array(parameter, copy=True))
    endpoints: list[np.ndarray] = []
    real_endpoints: list[np.ndarray] = []
    ranks: list[int] = []
    rejected = 0
    expected_rank = min(problem.residual_scale.size, problem.point_scale.size)
    for raw in list(raw_endpoints)[:MAX_ENDPOINTS]:
        endpoint = np.asarray(raw, dtype=np.complex128)
        if endpoint.shape != (problem.point_scale.size,) or not np.all(np.isfinite(endpoint)):
            rejected += 1
            continue
        try:
            if float(np.max(np.abs(_scaled_residual(problem, endpoint, parameter)), initial=0.0)) > FIBRE_TOL:
                rejected += 1
                continue
            jacobian = _scaled_jacobian(problem, endpoint, parameter)
            singular = np.linalg.svd(jacobian, compute_uv=False)
            threshold = RANK_TOL * max(1.0, float(singular[0]) if singular.size else 1.0)
            ranks.append(int(np.count_nonzero(singular > threshold)))
        except Exception:
            rejected += 1
            continue
        endpoints.append(endpoint)
        if float(np.max(np.abs(endpoint.imag), initial=0.0)) <= REAL_TOL:
            real = np.asarray(endpoint.real, dtype=float)
            try:
                if bool(problem.guard(real, parameter)):
                    real_endpoints.append(real)
            except Exception:
                rejected += 1
    minimum_gap = math.inf
    for left in range(len(endpoints)):
        for right in range(left + 1, len(endpoints)):
            minimum_gap = min(minimum_gap, _normalized_gap(problem, endpoints[left], endpoints[right]))
    return FibreSample(
        parameter=np.array(parameter, copy=True),
        normalized_offset=tuple(float(value) for value in offset),
        endpoints=tuple(endpoints),
        unique_real_endpoints=_deduplicate(problem, real_endpoints),
        minimum_pair_gap=minimum_gap,
        minimum_rank=min(ranks, default=expected_rank),
        expected_rank=expected_rank,
        rejected_endpoints=rejected,
    )


def _exceptional_sample(samples: Sequence[FibreSample]) -> tuple[FibreSample | None, tuple[str, ...], int]:
    if not samples:
        return None, (), 0
    counts = [len(sample.unique_real_endpoints) for sample in samples]
    generic_count = int(np.median(counts)) if counts else 0
    ranked: list[tuple[float, int, FibreSample, tuple[str, ...]]] = []
    replicated_pairs = 0
    for sample in samples:
        signatures: list[str] = []
        if sample.minimum_pair_gap <= PAIR_TOL:
            signatures.append("replicated_fibre_coincidence")
            replicated_pairs += 1
        if sample.minimum_rank < sample.expected_rank:
            signatures.append("fibre_rank_drop")
        if len(sample.unique_real_endpoints) > generic_count:
            signatures.append("fibre_count_jump")
        if not signatures:
            continue
        distance = float(np.linalg.norm(np.asarray(sample.normalized_offset, dtype=float)))
        # Nearest structural exception wins.  Pair coincidence breaks a tie
        # ahead of a rank-only observation because it is the direct fibre-
        # product signal, never because of a case/family label.
        pair_priority = 0 if "replicated_fibre_coincidence" in signatures else 1
        ranked.append((distance, pair_priority, sample, tuple(signatures)))
    if not ranked:
        return None, (), replicated_pairs
    ranked.sort(key=lambda item: (item[0], item[1], item[2].normalized_offset))
    _distance, _priority, sample, signatures = ranked[0]
    return sample, signatures, replicated_pairs


def _correct(
    problem: ParameterizedProblem,
    start: np.ndarray,
    parameter: np.ndarray,
    *,
    maximum_iterations: int = 14,
) -> np.ndarray | None:
    point = np.asarray(start, dtype=np.complex128)
    for _ in range(maximum_iterations):
        try:
            residual = _scaled_residual(problem, point, parameter)
            residual_norm = float(np.max(np.abs(residual), initial=0.0))
            if residual_norm <= 5.0e-10:
                return point
            jacobian = _scaled_jacobian(problem, point, parameter)
            delta_scaled, *_ = np.linalg.lstsq(jacobian, -residual, rcond=1.0e-12)
            delta = delta_scaled * np.asarray(problem.point_scale, dtype=float)
        except Exception:
            return None
        if not np.all(np.isfinite(delta)):
            return None
        step_norm = float(np.linalg.norm(delta / np.asarray(problem.point_scale, dtype=float)))
        if step_norm > 2.0:
            delta *= 2.0 / step_norm
        accepted = False
        for backtrack in range(7):
            trial = point + (0.5**backtrack) * delta
            try:
                trial_norm = float(
                    np.max(np.abs(_scaled_residual(problem, trial, parameter)), initial=0.0)
                )
            except Exception:
                continue
            if trial_norm < residual_norm:
                point = trial
                accepted = True
                break
        if not accepted:
            return None
    try:
        if float(np.max(np.abs(_scaled_residual(problem, point, parameter)), initial=0.0)) <= 5.0e-8:
            return point
    except Exception:
        pass
    return None


def _project_back(
    problem: ParameterizedProblem,
    point: np.ndarray,
    from_parameter: np.ndarray,
    *,
    steps: int = 18,
) -> np.ndarray | None:
    current = np.asarray(point, dtype=np.complex128)
    source = np.asarray(problem.source_parameter, dtype=float)
    start_parameter = np.asarray(from_parameter, dtype=float)
    for ordinal in range(1, steps + 1):
        fraction = ordinal / steps
        parameter = (1.0 - fraction) * start_parameter + fraction * source
        corrected = _correct(problem, current, parameter)
        if corrected is None:
            return None
        current = corrected
    return current


def _inactive(reason: str, instability_metric: float = math.inf, near_residuals: int = 0) -> ExceptionalEvidence:
    return ExceptionalEvidence(
        False,
        reason,
        instability_metric,
        near_residuals,
        0,
        0,
        0,
        None,
        None,
        (),
        0,
        0,
        0,
    )


def discover_exceptional_proposals(
    problem: ParameterizedProblem,
    unstable_cluster: Sequence[np.ndarray],
) -> tuple[tuple[np.ndarray, ...], ExceptionalEvidence]:
    if problem.opaque:
        return (), _inactive("opaque_fallback")
    if not _valid_problem(problem):
        return (), _inactive("unsupported_parameterized_family")
    instability_metric, near_residuals = _instability(problem, unstable_cluster)
    if instability_metric > INSTABILITY_TOL and near_residuals == 0:
        return (), _inactive("stable_endpoint_fallback", instability_metric, near_residuals)
    try:
        samples = tuple(_sample_fibre(problem, offset) for offset in _sample_offsets(problem.source_parameter.size))
    except Exception as error:
        return (), _inactive(
            f"fibre_sampling_failed:{type(error).__name__}", instability_metric, near_residuals
        )
    exceptional, signatures, replicated_pairs = _exceptional_sample(samples)
    if exceptional is None:
        return (), ExceptionalEvidence(
            False,
            "no_exceptional_stratum_signal",
            instability_metric,
            near_residuals,
            len(samples),
            sum(len(sample.endpoints) for sample in samples),
            replicated_pairs,
            None,
            None,
            (),
            0,
            0,
            0,
        )

    exceptional_offset = np.asarray(exceptional.normalized_offset, dtype=float)
    proposal_samples = sorted(
        (
            sample
            for sample in samples
            if np.linalg.norm(np.asarray(sample.normalized_offset, dtype=float)) > 1.0e-14
            and sample.unique_real_endpoints
        ),
        key=lambda sample: (
            float(
                np.linalg.norm(
                    np.asarray(sample.normalized_offset, dtype=float) - exceptional_offset
                )
            ),
            float(np.linalg.norm(np.asarray(sample.normalized_offset, dtype=float))),
        ),
    )[:MAX_PROJECTION_FIBRES]

    projected: list[np.ndarray] = []
    rejected_projection = 0
    rejected_replay = 0
    for sample in proposal_samples:
        for endpoint in sample.unique_real_endpoints:
            proposal = _project_back(problem, endpoint, sample.parameter)
            if proposal is None:
                rejected_projection += 1
                continue
            if not canonical_source_replay(problem, proposal):
                rejected_replay += 1
                continue
            projected.append(np.asarray(proposal.real, dtype=float))
    retained = _deduplicate(problem, projected)
    evidence = ExceptionalEvidence(
        True,
        "exceptional_stratum_project_back",
        instability_metric,
        near_residuals,
        len(samples),
        sum(len(sample.endpoints) for sample in samples),
        replicated_pairs,
        tuple(float(value) for value in exceptional.parameter),
        exceptional.normalized_offset,
        signatures,
        len(retained),
        rejected_projection,
        rejected_replay,
    )
    return retained, evidence


def run_portfolio(
    problem: ParameterizedProblem,
    baseline: Sequence[np.ndarray],
    unstable_cluster: Sequence[np.ndarray] | None = None,
    *,
    starts: int = 16,
) -> PortfolioResult:
    frozen_baseline = tuple(np.array(point, dtype=float, copy=True) for point in baseline)
    before = _point_digest(frozen_baseline)
    side, evidence = discover_exceptional_proposals(
        problem,
        frozen_baseline if unstable_cluster is None else unstable_cluster,
    )
    proposals = _deduplicate(problem, (*frozen_baseline, *side))
    after = _point_digest(frozen_baseline)
    return PortfolioResult(proposals, evidence, route_trace(starts), before, after)
