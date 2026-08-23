"""Unified configuration loading interface.

Example:
	>>> from geosolver._internal.config import load_config
	>>> cfg = load_config({"num_workers": 2})
	>>> assert cfg.num_workers >= 0
"""

from dataclasses import dataclass
from typing import Any, Mapping

from .environment import (
	get_allow_degenerate,
	get_branchy_backend,
	get_hp_parallel_enabled,
	get_num_workers,
	get_parallel_enabled,
)
from .search_budget import SearchBudget
from .solver_params import ConvergenceThresholds, IterationLimits, Tolerances


@dataclass(frozen=True)
class Config:
	"""Unified runtime config snapshot."""

	num_workers: int
	parallel_enabled: bool
	hp_parallel_enabled: bool
	allow_degenerate: bool
	branchy_backend: bool
	search_budget: SearchBudget
	tolerances: Tolerances
	iteration_limits: IterationLimits
	convergence_thresholds: ConvergenceThresholds


def load_config(overrides: Mapping[str, Any] | None = None) -> Config:
	"""Load unified config values using priority: env > overrides > defaults."""
	values = {} if overrides is None else dict(overrides)
	search_budget = values.get("search_budget", SearchBudget())
	tolerances = values.get("tolerances", Tolerances())
	iteration_limits = values.get("iteration_limits", IterationLimits())
	convergence_thresholds = values.get("convergence_thresholds", ConvergenceThresholds())
	return Config(
		num_workers=get_num_workers(values.get("num_workers")),
		parallel_enabled=get_parallel_enabled(values.get("parallel_enabled")),
		hp_parallel_enabled=get_hp_parallel_enabled(values.get("hp_parallel_enabled")),
		allow_degenerate=get_allow_degenerate(values.get("allow_degenerate")),
		branchy_backend=get_branchy_backend(values.get("branchy_backend")),
		search_budget=search_budget,
		tolerances=tolerances,
		iteration_limits=iteration_limits,
		convergence_thresholds=convergence_thresholds,
	)


__all__ = [
	"Config",
	"SearchBudget",
	"Tolerances",
	"IterationLimits",
	"ConvergenceThresholds",
	"load_config",
]
