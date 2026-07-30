"""Near-boundary guard-headroom x rank-confidence radius overlay (v2)."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Mapping

import numpy as np


HERE = Path(__file__).resolve().parent
BASE_ADAPTER = HERE / "charted_search_adapter.py"
BASE_ADAPTER_SHA256 = (
    "657b139f00e59f4d02a98c895b37c08cb33c7ae0eb3c72b0ad0a9ad21630f1f3"
)
HEADROOM_GATE = 0.1
MIN_OUTER_RADIUS = 0.03125
INNER_RATIO = 0.25


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load():
    if _sha256(BASE_ADAPTER) != BASE_ADAPTER_SHA256:
        raise RuntimeError("hash-bound charted v1 adapter changed")
    name = "geotarget_exp_rank_guard_001_trusted_base_adapter"
    specification = importlib.util.spec_from_file_location(name, BASE_ADAPTER)
    if specification is None or specification.loader is None:
        raise ImportError(BASE_ADAPTER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load()
SEARCH_ARM = BASE.SEARCH_ARM
ARMS = (SEARCH_ARM,)
PRECISION_RUNTIME = BASE.PRECISION_RUNTIME


def _rank_confidence(rank_ratio: float) -> float:
    normalized = min(
        1.0, max(0.0, rank_ratio / BASE.WEAK_STRONG_RATIO_MAX)
    )
    return math.sqrt(max(0.05, 1.0 - normalized))


def _bound_headroom(
    anchor: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    direction: np.ndarray,
) -> float:
    coordinate_headroom = np.ones(anchor.size, dtype=float)
    finite_lower = np.isfinite(lower)
    finite_upper = np.isfinite(upper)
    two_sided = finite_lower & finite_upper
    if np.any(two_sided):
        fraction = (anchor[two_sided] - lower[two_sided]) / (
            upper[two_sided] - lower[two_sided]
        )
        coordinate_headroom[two_sided] = np.clip(
            2.0 * np.minimum(fraction, 1.0 - fraction), 0.0, 1.0
        )
    # A one-sided interval has no source-independent affine scale.  Leave its
    # headroom at one so this policy cannot change under a unit conversion.
    weights = np.square(np.asarray(direction, dtype=float))
    return float(np.clip(np.dot(weights, coordinate_headroom), 0.0, 1.0))


def _trust_radii(rank_ratio: float, bound_headroom: float) -> tuple[float, float]:
    if bound_headroom >= HEADROOM_GATE:
        return BASE.PROPOSAL_RADII
    outer = float(
        np.clip(
            BASE.PROPOSAL_RADII[0]
            * math.sqrt(max(0.0, bound_headroom))
            * _rank_confidence(rank_ratio),
            MIN_OUTER_RADIUS,
            BASE.PROPOSAL_RADII[0],
        )
    )
    return outer, INNER_RATIO * outer


def _trusted_proposals(
    case: object,
    anchor: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    stats: dict[str, int],
) -> tuple[np.ndarray, ...]:
    evidence = BASE._jacobian_pair(case, anchor, lower, upper)
    if evidence is None:
        return ()
    _anchor_residual, coarse, fine = evidence
    direction = BASE._stable_weak_direction(coarse, fine)
    if direction is None:
        return ()
    singular_values = np.linalg.svd(fine, compute_uv=False)
    if singular_values.size < 2 or singular_values[-2] <= 0.0:
        return ()
    rank_ratio = float(singular_values[-1] / singular_values[-2])
    headroom = _bound_headroom(anchor, lower, upper, direction)
    radii = _trust_radii(rank_ratio, headroom)
    near_boundary = int(headroom < HEADROOM_GATE)
    stats.update(
        {
            "rank_guard_trust_v2_near_boundary": near_boundary,
            "rank_guard_trust_v2_control_radii": 1 - near_boundary,
            "rank_guard_trust_v2_outer_radius_microunits": int(
                round(1.0e6 * radii[0])
            ),
            "rank_guard_trust_v2_inner_radius_microunits": int(
                round(1.0e6 * radii[1])
            ),
            "rank_guard_trust_v2_headroom_microunits": int(
                round(1.0e6 * headroom)
            ),
            "rank_guard_trust_v2_rank_ratio_nanounits": int(
                round(1.0e9 * rank_ratio)
            ),
        }
    )
    chart = BASE._to_chart(anchor, lower, upper)
    proposals: list[np.ndarray] = []
    for radius in radii:
        pair = (
            BASE._from_chart(chart + radius * direction, lower, upper),
            BASE._from_chart(chart - radius * direction, lower, upper),
        )
        observations = [BASE._observation(case, point) for point in pair]
        if not all(valid for _residual, valid in observations):
            continue
        proposals.extend(np.asarray(point, dtype=float).copy() for point in pair)
    return tuple(proposals)


def _overlay_prefix(
    base_case: object,
    literal_prefix: object,
    *,
    callback_cap: int,
    callbacks_per_start: int,
):
    stats: dict[str, int] = {
        "rank_guard_trust_v2_near_boundary": 0,
        "rank_guard_trust_v2_control_radii": 0,
    }
    original = BASE._weak_chart_proposals

    def proposal(case, anchor, lower, upper):
        return _trusted_proposals(case, anchor, lower, upper, stats)

    BASE._weak_chart_proposals = proposal
    try:
        prefix, telemetry = BASE._overlay_prefix(
            base_case,
            literal_prefix,
            callback_cap=callback_cap,
            callbacks_per_start=callbacks_per_start,
        )
    finally:
        BASE._weak_chart_proposals = original
    telemetry.update(stats)
    if prefix is literal_prefix:
        return prefix, telemetry
    sources = tuple(
        "rank_guard_trusted_weak_pair_v2"
        if source == "rank_guard_charted_weak_pair"
        else source
        for source in prefix.sources
    )
    activation = dict(prefix.activation)
    activation.update(
        {
            "rank_guard_overlay": "near_boundary_guard_headroom_times_rank_v2",
            "rank_guard_trust_headroom_gate": HEADROOM_GATE,
            "rank_guard_trust_min_outer_radius": MIN_OUTER_RADIUS,
            "rank_guard_trust_inner_ratio": INNER_RATIO,
        }
    )
    return replace(prefix, sources=sources, activation=activation), telemetry


def build_literal_prefix(document, base_case, base_policy):
    return BASE.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    return BASE.compile_program(arm, document)


def run_local_arm(arm: str, **kwargs):
    if arm != SEARCH_ARM:
        raise ValueError(f"unknown trust-v2 search arm: {arm!r}")
    overlaid, telemetry = _overlay_prefix(
        kwargs["base_case"],
        kwargs["literal_prefix"],
        callback_cap=int(kwargs["callback_cap"]),
        callbacks_per_start=int(kwargs["callbacks_per_start"]),
    )
    delegated = dict(kwargs)
    delegated["literal_prefix"] = overlaid
    outcome = BASE.FROZEN.run_local_arm(BASE.SEARCH_ARM, **delegated)
    counters = dict(outcome.counters)
    counters.update(telemetry)
    return replace(outcome, counters=counters)


def configuration_manifest() -> Mapping[str, object]:
    payload: dict[str, object] = {
        "schema_version": "geotarget.exp-rank-guard-001-trust-v2-binding/v1",
        "arm": SEARCH_ARM,
        "base_adapter_sha256": BASE_ADAPTER_SHA256,
        "policy": "control radii unless weak-direction finite-two-sided bound headroom < 0.1; then bound-headroom sqrt times rank confidence",
        "headroom_gate": HEADROOM_GATE,
        "minimum_outer_radius": MIN_OUTER_RADIUS,
        "inner_ratio": INNER_RATIO,
        "radii_per_activation": 2,
        "same_callback_count_as_v1": True,
        "same_first_75_percent_baseline": True,
        "same_every_fourth_insurance": True,
        "same_tail_replacement_fraction": 0.25,
        "positive_semantic_guard_margin_claim": False,
        "proposal_only": True,
        "source_replay_hp_pslq_or_canonical_authority_modified": False,
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
    "HEADROOM_GATE",
    "PRECISION_RUNTIME",
    "SEARCH_ARM",
    "_bound_headroom",
    "_overlay_prefix",
    "_rank_confidence",
    "_trust_radii",
    "build_literal_prefix",
    "compile_program",
    "configuration_manifest",
    "run_local_arm",
]
