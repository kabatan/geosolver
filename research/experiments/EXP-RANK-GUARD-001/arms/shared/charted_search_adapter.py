"""Proposal-only strict-bound chart weak-direction overlay for numerical-v15.

The frozen local kernel, evaluator, source replay and endpoint validation remain
authoritative.  This adapter may replace at most the final 25% of non-insurance
prefix slots with source-evaluated starts.  The first 75% and every fourth
counter-Cauchy insurance slot remain byte-for-byte baseline points.
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
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_FROZEN_SOLVER_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
FROZEN_ADAPTER = RUNTIME_ROOT / (
    "research/experiments/EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
    "corrective_nearroot_strict_restart_v2/adapter.py"
)
FROZEN_ADAPTER_SHA256 = (
    "cda4e348ce1bb848af84afaba062c931ec5f1ebf882bdb8cf122df0366e75dc2"
)
BASELINE_PREFIX_FRACTION = 0.75
INSURANCE_PERIOD = 4
FD_STEP = float(np.cbrt(np.finfo(float).eps))
PROJECTOR_DISTANCE_MAX = 0.1
WEAK_STRONG_RATIO_MAX = 0.1
PROPOSAL_RADII = (0.25, 0.0625)
MIN_INTERIOR_FRACTION = 64.0 * np.finfo(float).eps
OVERLAY_CALLBACK_FRACTION_MAX = 0.05
OVERLAY_CALLBACK_ABSOLUTE_MAX = 64

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_frozen():
    if _sha256(FROZEN_ADAPTER) != FROZEN_ADAPTER_SHA256:
        raise RuntimeError("hash-bound frozen search adapter changed")
    name = "geotarget_exp_rank_guard_001_frozen_search_adapter"
    specification = importlib.util.spec_from_file_location(name, FROZEN_ADAPTER)
    if specification is None or specification.loader is None:
        raise ImportError(FROZEN_ADAPTER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


FROZEN = _load_frozen()
SEARCH_ARM = FROZEN.CANDIDATE
ARMS = (SEARCH_ARM,)
PRECISION_RUNTIME = FROZEN.PRECISION_RUNTIME


def _canonical_line(vector: Sequence[float]) -> np.ndarray | None:
    line = np.asarray(vector, dtype=float).copy()
    magnitude = float(np.linalg.norm(line))
    if not math.isfinite(magnitude) or magnitude <= math.sqrt(np.finfo(float).eps):
        return None
    line /= magnitude
    pivot = int(np.argmax(np.abs(line)))
    if math.copysign(1.0, float(line[pivot])) < 0.0:
        line *= -1.0
    return line


def _sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    output = np.empty_like(values)
    positive = values >= 0.0
    tail = np.exp(-values[positive])
    output[positive] = 1.0 / (1.0 + tail)
    head = np.exp(values[~positive])
    output[~positive] = head / (1.0 + head)
    return np.clip(output, MIN_INTERIOR_FRACTION, 1.0 - MIN_INTERIOR_FRACTION)


def _softplus(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return np.maximum(values, 0.0) + np.log1p(np.exp(-np.abs(values)))


def _inverse_softplus(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    positive = np.maximum(values, np.nextafter(0.0, 1.0))
    return positive + np.log(-np.expm1(-positive))


def _to_chart(point: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    point = np.asarray(point, dtype=float)
    chart = point.copy()
    finite_lower = np.isfinite(lower)
    finite_upper = np.isfinite(upper)
    two_sided = finite_lower & finite_upper
    lower_only = finite_lower & ~finite_upper
    upper_only = ~finite_lower & finite_upper
    if np.any(two_sided):
        fraction = (point[two_sided] - lower[two_sided]) / (
            upper[two_sided] - lower[two_sided]
        )
        fraction = np.clip(
            fraction, MIN_INTERIOR_FRACTION, 1.0 - MIN_INTERIOR_FRACTION
        )
        chart[two_sided] = np.log(fraction / (1.0 - fraction))
    if np.any(lower_only):
        distance = point[lower_only] - lower[lower_only]
        chart[lower_only] = _inverse_softplus(distance)
    if np.any(upper_only):
        distance = upper[upper_only] - point[upper_only]
        chart[upper_only] = _inverse_softplus(distance)
    return chart


def _from_chart(chart: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    chart = np.asarray(chart, dtype=float)
    point = chart.copy()
    finite_lower = np.isfinite(lower)
    finite_upper = np.isfinite(upper)
    two_sided = finite_lower & finite_upper
    lower_only = finite_lower & ~finite_upper
    upper_only = ~finite_lower & finite_upper
    if np.any(two_sided):
        fraction = _sigmoid(chart[two_sided])
        point[two_sided] = lower[two_sided] + (
            upper[two_sided] - lower[two_sided]
        ) * fraction
    if np.any(lower_only):
        point[lower_only] = lower[lower_only] + _softplus(chart[lower_only])
    if np.any(upper_only):
        point[upper_only] = upper[upper_only] - _softplus(chart[upper_only])
    # Rounding at a very narrow or very distant boundary must not turn a chart
    # proposal into an equality.  Unsupported intervals with no representable
    # interior are rejected before reaching this function.
    if np.any(finite_lower):
        point[finite_lower] = np.maximum(
            point[finite_lower], np.nextafter(lower[finite_lower], np.inf)
        )
    if np.any(finite_upper):
        point[finite_upper] = np.minimum(
            point[finite_upper], np.nextafter(upper[finite_upper], -np.inf)
        )
    return point


def _observation(case: object, point: np.ndarray) -> tuple[np.ndarray, bool]:
    try:
        raw = case.evaluate(np.asarray(point, dtype=float))
        residual = np.asarray(raw.residual, dtype=float)
        valid = bool(
            getattr(raw, "finite", np.all(np.isfinite(residual)))
            and getattr(raw, "semantics_valid", False)
            and residual.ndim == 1
            and np.all(np.isfinite(residual))
        )
    except Exception:
        return np.empty(0, dtype=float), False
    return residual, valid


def _jacobian_pair(
    case: object,
    anchor: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    dimension = anchor.size
    anchor_residual, anchor_valid = _observation(case, anchor)
    if not anchor_valid or anchor_residual.shape != (dimension,):
        return None
    chart = _to_chart(anchor, lower, upper)
    matrices: list[np.ndarray] = []
    for step in (FD_STEP, FD_STEP / 2.0):
        matrix = np.empty((dimension, dimension), dtype=float)
        for column in range(dimension):
            plus = chart.copy()
            minus = chart.copy()
            plus[column] += step
            minus[column] -= step
            plus_residual, plus_valid = _observation(
                case, _from_chart(plus, lower, upper)
            )
            minus_residual, minus_valid = _observation(
                case, _from_chart(minus, lower, upper)
            )
            if (
                not plus_valid
                or not minus_valid
                or plus_residual.shape != (dimension,)
                or minus_residual.shape != (dimension,)
            ):
                return None
            matrix[:, column] = (plus_residual - minus_residual) / (2.0 * step)
        if not np.all(np.isfinite(matrix)):
            return None
        matrices.append(matrix)
    return anchor_residual, matrices[0], matrices[1]


def _stable_weak_direction(coarse: np.ndarray, fine: np.ndarray) -> np.ndarray | None:
    try:
        coarse_u, coarse_s, coarse_vt = np.linalg.svd(coarse, full_matrices=True)
        fine_u, fine_s, fine_vt = np.linalg.svd(fine, full_matrices=True)
    except np.linalg.LinAlgError:
        return None
    del coarse_u, fine_u
    if coarse_s.size < 2 or fine_s.size < 2:
        return None
    eta = float(np.linalg.norm(fine - coarse, ord=2))
    scale = max(float(np.linalg.norm(coarse, ord=2)), float(np.linalg.norm(fine, ord=2)))
    eta += 16.0 * coarse.shape[1] * np.finfo(float).eps * scale
    smallest_strong = min(float(coarse_s[-2]), float(fine_s[-2])) - eta
    largest_weak = max(float(coarse_s[-1]), float(fine_s[-1])) + eta
    if smallest_strong <= 0.0 or largest_weak / smallest_strong > WEAK_STRONG_RATIO_MAX:
        return None
    coarse_line = _canonical_line(coarse_vt[-1])
    fine_line = _canonical_line(fine_vt[-1])
    if coarse_line is None or fine_line is None:
        return None
    coarse_projector = np.outer(coarse_line, coarse_line)
    fine_projector = np.outer(fine_line, fine_line)
    if float(np.linalg.norm(coarse_projector - fine_projector, ord=2)) > PROJECTOR_DISTANCE_MAX:
        return None
    values, vectors = np.linalg.eigh((coarse_projector + fine_projector) / 2.0)
    del values
    return _canonical_line(vectors[:, -1])


def _weak_chart_proposals(
    case: object,
    anchor: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> tuple[np.ndarray, ...]:
    evidence = _jacobian_pair(case, anchor, lower, upper)
    if evidence is None:
        return ()
    _anchor_residual, coarse, fine = evidence
    direction = _stable_weak_direction(coarse, fine)
    if direction is None:
        return ()
    chart = _to_chart(anchor, lower, upper)
    proposals: list[np.ndarray] = []
    for radius in PROPOSAL_RADII:
        pair = (
            _from_chart(chart + radius * direction, lower, upper),
            _from_chart(chart - radius * direction, lower, upper),
        )
        observations = [_observation(case, point) for point in pair]
        if not all(valid for _residual, valid in observations):
            continue
        proposals.extend(np.asarray(point, dtype=float).copy() for point in pair)
    return tuple(proposals)


def _prefix_digest(points: Sequence[np.ndarray]) -> str:
    digest = hashlib.sha256(b"geotarget.exp-rank-guard-001.charted-prefix-f8/v1\0")
    digest.update(struct.pack("<Q", len(points)))
    for point in points:
        values = np.asarray(point, dtype="<f8")
        digest.update(struct.pack("<Q", values.size))
        digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def _overlay_prefix(
    base_case: object,
    literal_prefix: object,
    *,
    callback_cap: int,
    callbacks_per_start: int,
) -> tuple[object, dict[str, int]]:
    points = [np.asarray(point, dtype=float).copy() for point in literal_prefix.points]
    total = len(points)
    baseline_minimum = math.ceil(BASELINE_PREFIX_FRACTION * total)
    telemetry = {
        "rank_guard_overlay_eligible": 0,
        "rank_guard_overlay_activated": 0,
        "rank_guard_overlay_generated": 0,
        "rank_guard_overlay_replaced_slots": 0,
        "rank_guard_baseline_minimum_slots": baseline_minimum,
        "rank_guard_insurance_slots_preserved": sum(
            ordinal % INSURANCE_PERIOD == 0 for ordinal in range(total)
        ),
        "rank_guard_overlay_callback_budget": min(
            OVERLAY_CALLBACK_ABSOLUTE_MAX,
            int(math.floor(OVERLAY_CALLBACK_FRACTION_MAX * callback_cap)),
        ),
        "rank_guard_baseline_reserved_callbacks": (
            baseline_minimum * callbacks_per_start
        ),
    }
    dimension = int(base_case.dimension)
    lower = np.asarray(base_case.lower, dtype=float)
    upper = np.asarray(base_case.upper, dtype=float)
    if (
        dimension < 2
        or total == 0
        or lower.shape != (dimension,)
        or upper.shape != (dimension,)
        or np.any(np.isnan(lower))
        or np.any(np.isnan(upper))
        or not np.all(lower < upper)
        or np.any(
            np.isfinite(lower)
            & np.isfinite(upper)
            & (np.nextafter(lower, np.inf) >= upper)
        )
    ):
        return literal_prefix, telemetry
    # One anchor costs 1 + 4*n observations for the two central-difference
    # Jacobians and two observations for each symmetric proposal radius.  If
    # that diagnostic cannot fit inside a small, fixed share of the existing
    # callback ledger, preserve the frozen prefix without partial probing.
    required_callbacks = 1 + 4 * dimension + 2 * len(PROPOSAL_RADII)
    if (
        required_callbacks > telemetry["rank_guard_overlay_callback_budget"]
        or callback_cap - required_callbacks
        < telemetry["rank_guard_baseline_reserved_callbacks"]
    ):
        return literal_prefix, telemetry
    telemetry["rank_guard_overlay_eligible"] = 1
    candidates: list[np.ndarray] = []
    # A single fixed anchor keeps proposal work bounded and truth-blind.
    for anchor in points[: min(1, baseline_minimum)]:
        if not np.all((lower < anchor) & (anchor < upper)):
            continue
        candidates.extend(_weak_chart_proposals(base_case, anchor, lower, upper))
        if len(candidates) >= 4:
            break
    replacement_slots = [
        ordinal
        for ordinal in range(baseline_minimum, total)
        if ordinal % INSURANCE_PERIOD != 0
    ]
    replace_count = min(len(candidates), len(replacement_slots))
    if replace_count == 0:
        return literal_prefix, telemetry
    sources = list(literal_prefix.sources)
    exponents = list(literal_prefix.scale_exponents)
    for slot, proposal in zip(replacement_slots, candidates[:replace_count]):
        points[slot] = proposal.copy()
        sources[slot] = "rank_guard_charted_weak_pair"
        exponents[slot] = None
    activation = dict(literal_prefix.activation)
    activation.update(
        {
            "rank_guard_overlay": "charted_weak_pair_proposal_only",
            "rank_guard_baseline_prefix_fraction": BASELINE_PREFIX_FRACTION,
            "rank_guard_generated": len(candidates),
            "rank_guard_replaced_slots": replace_count,
            "rank_guard_insurance_period": INSURANCE_PERIOD,
            "rank_guard_canonical_authority": False,
        }
    )
    telemetry["rank_guard_overlay_activated"] = 1
    telemetry["rank_guard_overlay_generated"] = len(candidates)
    telemetry["rank_guard_overlay_replaced_slots"] = replace_count
    return replace(
        literal_prefix,
        points=tuple(points),
        sources=tuple(sources),
        scale_exponents=tuple(exponents),
        sha256=_prefix_digest(points),
        activation=activation,
    ), telemetry


def build_literal_prefix(document, base_case, base_policy):
    return FROZEN.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm != SEARCH_ARM:
        raise ValueError(f"unknown rank/guard search arm: {arm!r}")
    return FROZEN.compile_program(FROZEN.CANDIDATE, document)


def run_local_arm(arm: str, **kwargs):
    if arm != SEARCH_ARM:
        raise ValueError(f"unknown rank/guard search arm: {arm!r}")
    overlaid, telemetry = _overlay_prefix(
        kwargs["base_case"],
        kwargs["literal_prefix"],
        callback_cap=int(kwargs["callback_cap"]),
        callbacks_per_start=int(kwargs["callbacks_per_start"]),
    )
    delegated = dict(kwargs)
    delegated["literal_prefix"] = overlaid
    outcome = FROZEN.run_local_arm(FROZEN.CANDIDATE, **delegated)
    counters = dict(outcome.counters)
    counters.update(telemetry)
    return replace(outcome, counters=counters)


def configuration_manifest() -> Mapping[str, object]:
    payload: dict[str, object] = {
        "schema_version": "geotarget.exp-rank-guard-001-search-binding/v1",
        "arm": SEARCH_ARM,
        "frozen_adapter_sha256": FROZEN_ADAPTER_SHA256,
        "baseline_prefix_minimum_fraction": BASELINE_PREFIX_FRACTION,
        "insurance_period": INSURANCE_PERIOD,
        "proposal_radii": list(PROPOSAL_RADII),
        "fd_step": FD_STEP,
        "coordinate_charts": {
            "finite_lower_and_upper": "logit",
            "finite_lower_only": "softplus",
            "finite_upper_only": "reflected_softplus",
            "unbounded": "identity",
        },
        "overlay_callback_fraction_max": OVERLAY_CALLBACK_FRACTION_MAX,
        "overlay_callback_absolute_max": OVERLAY_CALLBACK_ABSOLUTE_MAX,
        "baseline_prefix_callback_reservation_required": True,
        "proposal_only": True,
        "same_frozen_local_kernel": True,
        "same_source_evaluator_and_callback_ledger": True,
        "source_problem_modified": False,
        "source_replay_modified": False,
        "hp_or_canonical_authority_modified": False,
        "truth_case_family_target_or_previous_outcome_routing": False,
    }
    payload["configuration_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


BINDING_RECORD = configuration_manifest()


__all__ = [
    "ARMS",
    "BINDING_RECORD",
    "PRECISION_RUNTIME",
    "SEARCH_ARM",
    "build_literal_prefix",
    "compile_program",
    "configuration_manifest",
    "run_local_arm",
]
