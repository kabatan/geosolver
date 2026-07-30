"""Candidate-local truth-blind chart adapter for the frozen DiGS kernel."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Sequence

import numpy as np


ARCHIVE = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/epoch_d_diffusive_gibbs_portal_g0"
)
CANDIDATE_PATH = ARCHIVE / "candidate.py"
FROZEN_CANDIDATE_SHA256 = (
    "e53660ad093682662ab4056ef11d6fece82d1ea9ffa46e8bbce0389ce4278df6"
)
CHART_SPAN_MULTIPLIER = 10.0


def _load_candidate():
    if hashlib.sha256(CANDIDATE_PATH.read_bytes()).hexdigest() != FROZEN_CANDIDATE_SHA256:
        raise RuntimeError("frozen Diffusive-Gibbs candidate changed")
    name = "geotarget_diffusive_gibbs_prospective_portal_kernel"
    specification = importlib.util.spec_from_file_location(name, CANDIDATE_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(CANDIDATE_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


KERNEL = _load_candidate()


def affine_chart(anchors: Sequence[Sequence[float]]):
    """Use the first original-order full-rank anchor differences, or fail closed."""

    if not anchors:
        return None
    points = [np.asarray(point, dtype=float).reshape(-1) for point in anchors]
    dimension = points[0].size
    if (
        dimension < 1
        or any(point.shape != (dimension,) or not np.all(np.isfinite(point)) for point in points)
    ):
        return None
    origin = points[0].copy()
    columns: list[np.ndarray] = []
    for point in points[1:]:
        trial = columns + [point - origin]
        matrix = np.stack(trial, axis=1)
        if np.linalg.matrix_rank(matrix) > len(columns):
            columns.append(point - origin)
        if len(columns) == dimension:
            break
    if len(columns) != dimension:
        return None
    basis = CHART_SPAN_MULTIPLIER * np.stack(columns, axis=1)
    try:
        singular = np.linalg.svd(basis, compute_uv=False)
    except np.linalg.LinAlgError:
        return None
    if singular[-1] <= 1.0e-10 * singular[0]:
        return None
    return KERNEL.Chart(origin, basis)


def propose(evaluate, anchors, *, seed: int):
    chart = affine_chart(anchors)
    if chart is None:
        return KERNEL.Result((), 0, 0, 0, "CHART_INELIGIBLE")
    return KERNEL.propose(evaluate, anchors[:4], chart, seed=seed)


def configuration_manifest() -> dict[str, object]:
    return {
        **KERNEL.configuration_manifest(),
        "kernel_sha256": FROZEN_CANDIDATE_SHA256,
        "chart": "first original-order full-rank anchor differences",
        "chart_span_multiplier": CHART_SPAN_MULTIPLIER,
        "chart_inputs": "immutable proposal coordinates only",
        "ineligible_behavior": "no proposals; byte-identical incumbent fallback",
        "oracle_origin_basis_used": False,
    }


__all__ = [
    "FROZEN_CANDIDATE_SHA256",
    "KERNEL",
    "affine_chart",
    "configuration_manifest",
    "propose",
]
