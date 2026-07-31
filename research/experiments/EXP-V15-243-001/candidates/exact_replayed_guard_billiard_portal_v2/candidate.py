"""Safety reopen of frozen guard-billiard G0 with exact terminal replay."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Callable

import numpy as np


FROZEN_PATH = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/EXP-V15-243-001/candidates/wave20_guard_billiard_portal_g0/candidate.py"
).resolve()
FROZEN_SHA256 = "a659ffc11505bc75b7df4a288a4d75e1277145d668d3ebf67d639215b9981a34"


def _load_frozen():
    if hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest() != FROZEN_SHA256:
        raise RuntimeError("frozen wave20 guard-billiard candidate changed")
    specification = importlib.util.spec_from_file_location("wave20_guard_billiard_frozen", FROZEN_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load frozen guard-billiard candidate")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    if Path(module.__file__).resolve() != FROZEN_PATH:
        raise RuntimeError("frozen guard-billiard module identity changed")
    return module


FROZEN = _load_frozen()
GuardObservation = FROZEN.GuardObservation
Replay = FROZEN.Replay


@dataclass(frozen=True)
class DescriptorProposal:
    accepted: bool
    descriptor: tuple[float, ...] | None


@dataclass(frozen=True)
class ExactDescriptorReplay:
    accepted: bool
    descriptor: tuple[float, ...] | None
    descriptor_exact: bool
    source_constraints_exact: bool
    canonical_guard_replay: bool
    raw_target_link_exact: bool
    approximate_endpoint_is_authority: bool = False


@dataclass(frozen=True)
class SolverView:
    iteration_map: Callable[[np.ndarray], np.ndarray]
    guards: Callable[[np.ndarray], GuardObservation]
    approximate_replay: Callable[[np.ndarray], DescriptorProposal]
    exact_descriptor_replay: Callable[[tuple[float, ...]], ExactDescriptorReplay]
    inner: Callable[[np.ndarray, np.ndarray], float]


def _terminal_replay(view: SolverView, endpoint: np.ndarray) -> Replay:
    """Never admit a descriptor from approximate endpoint guards alone."""

    try:
        provisional = view.approximate_replay(np.asarray(endpoint, dtype=float))
        if not provisional.accepted or provisional.descriptor is None:
            return Replay(False, None)
        exact = view.exact_descriptor_replay(provisional.descriptor)
        valid = bool(
            exact.accepted
            and exact.descriptor == provisional.descriptor
            and exact.descriptor_exact
            and exact.source_constraints_exact
            and exact.canonical_guard_replay
            and exact.raw_target_link_exact
            and not exact.approximate_endpoint_is_authority
        )
        return Replay(valid, exact.descriptor if valid else None)
    except Exception:
        return Replay(False, None)


def _adapt(view: SolverView):
    return FROZEN.SolverView(
        view.iteration_map,
        view.guards,
        lambda endpoint: _terminal_replay(view, endpoint),
        view.inner,
    )


def run_control(view: SolverView, starts, fallback, *, work_cap: int = 320) -> dict:
    return FROZEN.run_control(_adapt(view), starts, fallback, work_cap=work_cap)


def run_static_one_reflection(view: SolverView, starts, fallback, *, work_cap: int = 320) -> dict:
    return FROZEN.run_static_one_reflection(_adapt(view), starts, fallback, work_cap=work_cap)


def run_candidate(view: SolverView, starts, fallback, *, work_cap: int = 320) -> dict:
    return FROZEN.run_candidate(_adapt(view), starts, fallback, work_cap=work_cap)
