"""Candidate-local monkey patch of the frozen champion local-kernel seam."""

from __future__ import annotations

from dataclasses import replace
from collections import Counter
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import threading
from typing import Mapping, Sequence

import numpy as np

from real_seam_patch import transform_augmented_residual


HERE = Path(__file__).resolve().parent
FROZEN_ROOT = Path(os.environ.get(
    "GEOTARGET_FROZEN_REPOSITORY", "/home/kabatan/work/solver-experiment-runtime/solver"
)).resolve()
PARENT_PATH = (
    FROZEN_ROOT / "research/experiments/EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
    "corrective_nearroot_strict_restart_v2/candidate.py"
)
PARENT_SHA256 = "d2904af6e1f0f0dbc8432dfb2adf3039e28c502131df45ffdd3bfde42f7acafc"
REFERENCE_NAME = "spectral_cosh_quarter_lane_nearroot_direct_broyden_ruiz_tr_lm"


def _load_parent():
    if hashlib.sha256(PARENT_PATH.read_bytes()).hexdigest() != PARENT_SHA256:
        raise RuntimeError("frozen near-root parent changed")
    name = "geotarget_spectral_cosh_frozen_nearroot_parent"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, PARENT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(PARENT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PARENT = _load_parent()
ADProgram = PARENT.ADProgram
CandidateOutcome = PARENT.CandidateOutcome
Configuration = PARENT.Configuration
compile_program = PARENT.compile_program
REFERENCE = replace(PARENT.REFERENCE, name=REFERENCE_NAME)
CONFIGURATIONS = {REFERENCE_NAME: REFERENCE}
_PATCH_LOCK = threading.RLock()


def _source_smooth_at_start(program: object, start: Sequence[float]) -> bool:
    # A guard or an explicit selector/branch makes the nonlinear spectral frame
    # noncanonical.  The ordinary parent remains the only proposal in that case.
    guards = getattr(program, "guards", ())
    if guards:
        return False
    expressions = []
    try:
        expressions.extend(value for pair in program.construction for value in pair)
        expressions.extend(value for pair in program.constraints for value in pair)
    except Exception:
        return False
    text = " ".join(str(value).lower().replace(" ", "") for value in expressions)
    branch_or_nonsmooth_tokens = (
        "abs(", "min(", "max(", "sign(", "floor(", "ceil(", "round(",
        "where(", "piecewise(", "ifelse(", "if(", "?", "%",
        "near=", "far=", "exclude=", "selector", "intersect", "branch",
        "<", ">", "!=", "==",
    )
    if not expressions or any(token in text for token in branch_or_nonsmooth_tokens):
        return False
    try:
        rows = program.relation_rows(start)
    except Exception:
        rows = ()
    if rows and all(row is not None for row in rows):
        return True

    # The frozen AD interpreter deliberately supports only a thin operation
    # subset; an unsupported smooth geometry primitive must not disable this
    # numerical lane. Unknown calls still fail closed: this small list is the
    # candidate-local representation reopen, not a general expression parser.
    calls = set(re.findall(r"([a-z_][a-z0-9_]*)\(", text))
    safe_unsupported_calls = {
        "acos", "asin", "atan", "atan2", "cos", "cosh", "distance", "dot",
        "exp", "length", "log", "midpoint", "norm", "point", "sin", "sinh",
        "sqrt", "tan", "tanh", "vector", "x", "y",
    }
    return calls <= safe_unsupported_calls


def _raw_model_agrees(
    jacobian: np.ndarray,
    residual: np.ndarray,
    damping: float,
    ordinary_step: np.ndarray,
    spectral_step: np.ndarray,
) -> bool:
    """Require both proposals to be finite descent directions in the raw model."""

    J = np.asarray(jacobian, dtype=float)
    r = np.asarray(residual, dtype=float).reshape(-1)
    ordinary = np.asarray(ordinary_step, dtype=float).reshape(-1)
    spectral = np.asarray(spectral_step, dtype=float).reshape(-1)
    if ordinary.shape != spectral.shape or not (
        np.all(np.isfinite(J))
        and np.all(np.isfinite(r))
        and np.all(np.isfinite(ordinary))
        and np.all(np.isfinite(spectral))
    ):
        return False
    base_merit = 0.5 * float(r @ r)

    def reduction(step: np.ndarray) -> float:
        linear = r + J @ step
        return base_merit - (
            0.5 * float(linear @ linear)
            + 0.5 * max(float(damping), 0.0) * float(step @ step)
        )

    ordinary_reduction = reduction(ordinary)
    spectral_reduction = reduction(spectral)
    gradient = J.T @ r
    return bool(
        np.isfinite(ordinary_reduction)
        and np.isfinite(spectral_reduction)
        and ordinary_reduction > 0.0
        and spectral_reduction > 0.0
        and float(gradient @ spectral) < 0.0
        and float(ordinary @ spectral) > 0.0
    )


def solve_local(
    case: object,
    program: ADProgram,
    configuration: Configuration,
    start: Sequence[float],
    **kwargs,
) -> CandidateOutcome:
    """Patch only the linear RHS; all frozen acceptance/replay stays intact."""
    smooth = _source_smooth_at_start(program, start)
    ruiz = PARENT._KERNEL._RUIZ
    original = ruiz._linear_step

    def spectral_step(
        jacobian, residual, damping, rank_rtol, solver, ruiz_configuration, counters
    ):
        counters["spectral_cosh_linearizations"] = int(
            counters.get("spectral_cosh_linearizations", 0)
        ) + 1
        # Compute and retain the exact ordinary/FD-backed proposal first.  The
        # spectral proposal is surplus CPU work and can never remove insurance.
        ordinary_step, ordinary_rank = original(
            jacobian, residual, damping, rank_rtol, solver,
            ruiz_configuration, counters,
        )
        if smooth:
            transformed = transform_augmented_residual(
                jacobian, residual, damping, reference_radius=1.0, rank_rtol=rank_rtol
            )
        else:
            transformed = None
        if transformed is not None and transformed.activated:
            try:
                candidate_step, candidate_rank = original(
                    jacobian, transformed.residual, damping, rank_rtol, solver,
                    ruiz_configuration, Counter(),
                )
            except Exception:
                candidate_step, candidate_rank = None, None
            if (
                candidate_step is not None
                and candidate_rank == ordinary_rank
                and _raw_model_agrees(
                    jacobian, residual, damping, ordinary_step, candidate_step
                )
            ):
                counters["spectral_cosh_activations"] = int(
                    counters.get("spectral_cosh_activations", 0)
                ) + 1
                return candidate_step, candidate_rank
        counters["spectral_cosh_fallbacks"] = int(
            counters.get("spectral_cosh_fallbacks", 0)
        ) + 1
        return ordinary_step, ordinary_rank

    with _PATCH_LOCK:
        ruiz._linear_step = spectral_step
        try:
            return PARENT.solve_local(case, program, configuration, start, **kwargs)
        finally:
            ruiz._linear_step = original


def configuration_manifest(
    configuration: Configuration = REFERENCE,
) -> Mapping[str, object]:
    manifest = dict(PARENT.configuration_manifest(configuration))
    manifest.update({
        "candidate": configuration.name,
        "mechanism": (
            "one-in-four outer lanes replace only the frozen Ruiz LM RHS with "
            "a full-rank spectral-cosh normal-gradient lift"
        ),
        "parent_sha256": PARENT_SHA256,
        "reference_radius": 1.0,
        "source_smooth_gate": (
            "forward-AD support or source expression scan with explicit nonsmooth/branch "
            "tokens rejected"
        ),
        "rank_and_eigenframe_fail_closed": True,
        "guard_branch_selector_fail_closed": True,
        "ordinary_proposal_computed_first_and_retained": True,
        "raw_model_disagreement_falls_back_to_ordinary": True,
        "raw_model_acceptance_unchanged": True,
        "canonical_endpoint_replay_unchanged": True,
        "case_family_truth_target_or_outcome_routing": False,
    })
    return manifest


__all__ = [
    "ADProgram", "CONFIGURATIONS", "CandidateOutcome", "Configuration",
    "REFERENCE", "REFERENCE_NAME", "compile_program", "configuration_manifest",
    "solve_local",
]
