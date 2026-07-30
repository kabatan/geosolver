"""Thin local-box Krawczyk rescue over the existing validated typed DAG."""

from __future__ import annotations

import hashlib
import importlib.util
import math
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INTERVAL_PATH = ROOT / "research/experiments/EXP-INTERVAL-001/interval_rescue.py"
INTERVAL_SHA256 = "b2a17ddc6321c3157f89965a8c76fd18f376c8974c3d4288bf430ff70bc6e2a3"
BASELINE_FLOOR = 0.75
WORK_PER_ATTEMPT = 4


def _load_existing_interval() -> Any:
    if hashlib.sha256(INTERVAL_PATH.read_bytes()).hexdigest() != INTERVAL_SHA256:
        raise RuntimeError("PINNED_TYPED_INTERVAL_DAG_MISMATCH")
    specification = importlib.util.spec_from_file_location(
        "local_krawczyk_pinned_interval_dag", INTERVAL_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("PINNED_TYPED_INTERVAL_DAG_LOAD_FAILED")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


INTERVAL = _load_existing_interval()
Expr = INTERVAL.Expr
Var = INTERVAL.Var
Const = INTERVAL.Const
unsupported = INTERVAL.unsupported


CanonicalAccept = Callable[
    [tuple[float, ...], tuple[tuple[float, float], ...]], str | None
]


@dataclass(frozen=True)
class TypedLocalSource:
    residuals: tuple[Any, ...]
    dimension: int
    literal_bounds: tuple[tuple[float | None, float | None], ...] = ()
    source_kind: str = "existing-validated-dag"
    branch_state_on_local_box: str = "single"
    strict_guard_state_on_local_box: str = "interior"
    opaque_callbacks: bool = False


@dataclass(frozen=True)
class NearRoot:
    point: tuple[float, ...]
    trust_radius: float | tuple[float, ...]


@dataclass(frozen=True)
class LocalConfig:
    max_dimension: int = 2
    max_near_roots: int = 4
    min_radius: float = 1.0e-9
    max_radius: float = 0.5
    singular_rcond_floor: float = 1.0e-12


DEFAULT_CONFIG = LocalConfig()


@dataclass(frozen=True)
class LocalRescueResult:
    baseline_payload: bytes
    descriptors: tuple[str, ...]
    baseline_work: int
    side_work: int
    side_work_used: int
    eligible_boxes: int
    attempts: int
    certified_boxes: int
    canonical_calls: int
    canonical_rejections: int
    reason: str
    proposal_authority: bool = False


def split_work(total_work: int) -> tuple[int, int]:
    if total_work <= 0:
        raise ValueError("total_work must be positive")
    baseline = math.ceil(BASELINE_FLOOR * total_work)
    return baseline, total_work - baseline


def _radius_vector(near: NearRoot, dimension: int) -> tuple[float, ...] | None:
    raw = (
        (float(near.trust_radius),) * dimension
        if isinstance(near.trust_radius, (int, float))
        else tuple(float(value) for value in near.trust_radius)
    )
    if len(raw) != dimension or any(
        not math.isfinite(value) or value <= 0 for value in raw
    ):
        return None
    return raw


def _local_bounds(
    source: TypedLocalSource, near: NearRoot, config: LocalConfig
) -> tuple[tuple[float, float], ...] | None:
    if len(near.point) != source.dimension:
        return None
    centers = tuple(float(value) for value in near.point)
    if any(not math.isfinite(value) for value in centers):
        return None
    radii = _radius_vector(near, source.dimension)
    if radii is None:
        return None
    literal = source.literal_bounds or ((None, None),) * source.dimension
    if len(literal) != source.dimension:
        return None
    bounds = []
    for center, requested, (literal_lo, literal_hi) in zip(
        centers, radii, literal, strict=True
    ):
        radius = min(requested, config.max_radius)
        if literal_lo is not None:
            lower = float(literal_lo)
            if not math.isfinite(lower) or not lower < center:
                return None
            radius = min(radius, center - lower)
        if literal_hi is not None:
            upper = float(literal_hi)
            if not math.isfinite(upper) or not center < upper:
                return None
            radius = min(radius, upper - center)
        if not math.isfinite(radius) or radius < config.min_radius:
            return None
        bounds.append((center - radius, center + radius))
    return tuple(bounds)


def _append_unique(
    baseline: Sequence[str], additions: Sequence[str]
) -> tuple[str, ...]:
    output = list(baseline)
    seen = set(baseline)
    for descriptor in additions:
        if descriptor not in seen:
            output.append(descriptor)
            seen.add(descriptor)
    return tuple(output)


def _safe_accept(
    callback: CanonicalAccept,
    point: tuple[float, ...],
    enclosure: tuple[tuple[float, float], ...],
) -> str | None:
    try:
        descriptor = callback(point, enclosure)
    except Exception:  # noqa: BLE001 - unchanged authority failure rejects proposal
        return None
    return descriptor if isinstance(descriptor, str) else None


def rescue(
    source: TypedLocalSource,
    *,
    near_roots: Sequence[NearRoot],
    baseline_payload: bytes,
    baseline_descriptors: Sequence[str],
    total_work: int,
    canonical_accept: CanonicalAccept,
    config: LocalConfig = DEFAULT_CONFIG,
) -> LocalRescueResult:
    """Certify only supplied local boxes; never subdivide or search globally."""

    baseline_work, side_work = split_work(total_work)

    def result(
        *,
        descriptors: Sequence[str] = (),
        side_used: int = 0,
        eligible: int = 0,
        attempts: int = 0,
        certified: int = 0,
        calls: int = 0,
        rejected: int = 0,
        reason: str,
    ) -> LocalRescueResult:
        return LocalRescueResult(
            baseline_payload,
            _append_unique(baseline_descriptors, descriptors),
            baseline_work,
            side_work,
            side_used,
            eligible,
            attempts,
            certified,
            calls,
            rejected,
            reason,
        )

    if not 1 <= source.dimension <= config.max_dimension:
        return result(reason="DIMENSION_OUTSIDE_CAP")
    if len(source.residuals) != source.dimension:
        return result(reason="NONSQUARE_TYPED_DAG")
    if source.source_kind != "existing-validated-dag" or source.opaque_callbacks:
        return result(reason="VALIDATED_TYPED_DAG_UNAVAILABLE")
    if source.branch_state_on_local_box != "single":
        return result(reason="LOCAL_BOX_BRANCH_UNKNOWN")
    if source.strict_guard_state_on_local_box != "interior":
        return result(reason="LOCAL_BOX_STRICT_GUARD_NOT_INTERIOR")
    if side_work < WORK_PER_ATTEMPT or not near_roots:
        return result(reason="NO_BOUNDED_SIDE_ATTEMPT")

    interval_config = INTERVAL.RescueConfig(
        max_dimension=config.max_dimension,
        max_box_width=2.0 * config.max_radius,
        max_box_volume=(2.0 * config.max_radius) ** config.max_dimension,
        max_boxes=1,
        max_depth=0,
        max_proposals=1,
        singular_rcond_floor=config.singular_rcond_floor,
    )
    additions: list[str] = []
    side_used = eligible = attempts = certified = calls = rejected = 0
    cap = min(config.max_near_roots, len(near_roots), side_work // WORK_PER_ATTEMPT)
    for near in near_roots[:cap]:
        local_bounds = _local_bounds(source, near, config)
        if local_bounds is None:
            continue
        local_problem = INTERVAL.Problem(
            source.residuals,
            local_bounds,
            source_kind="validated-dag",
            branch_state=source.branch_state_on_local_box,
            strict_guard_state=source.strict_guard_state_on_local_box,
            opaque_callbacks=False,
        )
        side_used += 1  # capability/domain interval F/J validation
        gate = INTERVAL.applicability(local_problem, interval_config)
        if not gate.applicable:
            continue
        eligible += 1
        attempts += 1
        side_used += 2  # Krawczyk point F/J and interval-box F/J
        box = tuple(INTERVAL.Interval(lo, hi) for lo, hi in local_bounds)
        try:
            enclosure, _singular = INTERVAL._krawczyk(
                source.residuals, box, interval_config
            )
        except (ArithmeticError, IndexError, TypeError, ValueError):
            continue
        if enclosure is None:
            continue
        certified += 1
        encoded_enclosure = tuple((value.lo, value.hi) for value in enclosure)
        point = tuple(value.midpoint() for value in enclosure)
        calls += 1
        side_used += 1
        descriptor = _safe_accept(canonical_accept, point, encoded_enclosure)
        if descriptor is None:
            rejected += 1
        else:
            additions.append(descriptor)

    if additions:
        reason = "CANONICAL_ACCEPTED_LOCAL_CERTIFICATE"
    elif certified:
        reason = "CERTIFIED_BUT_CANONICAL_REJECTED"
    elif attempts:
        reason = "NO_STRICT_KRAWCZYK_INCLUSION"
    else:
        reason = "NO_INTERVAL_ELIGIBLE_LOCAL_BOX"
    return result(
        descriptors=additions,
        side_used=side_used,
        eligible=eligible,
        attempts=attempts,
        certified=certified,
        calls=calls,
        rejected=rejected,
        reason=reason,
    )


__all__ = [
    "BASELINE_FLOOR",
    "INTERVAL_SHA256",
    "Const",
    "Expr",
    "LocalConfig",
    "LocalRescueResult",
    "NearRoot",
    "TypedLocalSource",
    "Var",
    "rescue",
    "split_work",
    "unsupported",
]
