"""Input normalization helpers for autosolve public run_ir."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from geosolver._internal.autosolve.answer import _evaluate_answer_high_precision
from geosolver._internal.autosolve.context import _get_fast_geometry_context, _get_geometry_context
from geosolver._internal.autosolve.guards import _evaluate_guards


@dataclass(frozen=True)
class RunIrInput:
    """Normalized inputs for autosolve run_ir orchestration."""

    prefer_fast: bool
    context_builder: Callable[..., dict[str, Any]]
    guard_evaluator: Callable[..., tuple[bool, str]]
    answer_evaluator: Callable[..., object]
    guard_probe: Any
    answer_probe: Any
    seed: int | None
    pipeline_config: Any
    nomad_config: Any
    box_solver: Any


def normalize_run_ir_input(kwargs: dict[str, Any]) -> RunIrInput:
    """Normalize run_ir kwargs into explicit orchestration dependencies."""
    prefer_fast = bool(kwargs.get("prefer_fast", False))
    default_context_builder = _get_fast_geometry_context if prefer_fast else _get_geometry_context
    context_builder = kwargs.pop("_context_builder", default_context_builder)
    guard_evaluator = kwargs.pop("_guard_evaluator", _evaluate_guards)
    answer_evaluator = kwargs.pop("_answer_evaluator", _evaluate_answer_high_precision)
    guard_probe = kwargs.pop("_guard_probe", None)
    answer_probe = kwargs.pop("_answer_probe", None)
    seed = kwargs.pop("seed", None)
    pipeline_config = kwargs.pop("pipeline_config", None)
    nomad_config = kwargs.pop("nomad_config", None)
    box_solver = kwargs.pop("box_solver", None)
    return RunIrInput(
        prefer_fast=prefer_fast,
        context_builder=context_builder,
        guard_evaluator=guard_evaluator,
        answer_evaluator=answer_evaluator,
        guard_probe=guard_probe,
        answer_probe=answer_probe,
        seed=None if seed is None else int(seed),
        pipeline_config=pipeline_config,
        nomad_config=nomad_config,
        box_solver=box_solver,
    )
