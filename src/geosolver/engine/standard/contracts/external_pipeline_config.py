"""Configuration contract for staged external pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

from geosolver.engine.standard.refinement.refiner_config import RefinerConfig
from geosolver.engine.standard.search.nomad_config import (
    DEFAULT_SEED_VALUES,
    NomadConfig,
)

from .baseline_search_policy import BaselineSearchPolicy

SEARCH_MODE_DISCO_MADS = "disco_mads"
SEARCH_MODE_MADS = "mads"
SEARCH_MODE_SCIPY_MULTISTART = "scipy_multistart"
SEARCH_MODE_HYBRID_LEGACY_NOMAD = "hybrid_legacy_nomad"
_ALLOWED_SEARCH_MODES = (
    SEARCH_MODE_DISCO_MADS,
    SEARCH_MODE_MADS,
    SEARCH_MODE_SCIPY_MULTISTART,
    SEARCH_MODE_HYBRID_LEGACY_NOMAD,
)
_ALLOWED_RESCUE_SEARCH_MODES = (
    SEARCH_MODE_DISCO_MADS,
    SEARCH_MODE_MADS,
)

TOTAL_TIME_BUDGET_SEC_DEFAULT = 30.0
RESCUE_TIME_BUDGET_SEC_DEFAULT = 8.0
GUARD_FEASIBLE_PREFIX_MIN_DEFAULT = 64
GUARD_FEASIBLE_PREFIX_MULTIPLIER_DEFAULT = 8
MAX_RESCUE_BOXES_DEFAULT = 6
RESCUE_RADIUS_FRACTION_DEFAULT = 0.5
RESCUE_RADIUS_MIN_RATIO_DEFAULT = 0.02
RESCUE_RADIUS_MAX_RATIO_DEFAULT = 0.35
RESCUE_MAX_BB_EVAL_DEFAULT = 80
KEEP_PER_RESCUE_BOX_DEFAULT = 6
CANDIDATE_DEBUG_LIMIT_DEFAULT = 32
INTEGER_TARGET_FALLBACK_MAX_TUPLES_DEFAULT = 256


@dataclass(frozen=True)
class ExternalPipelineConfig:
    """External pipeline configuration shared across all phases."""

    search: NomadConfig
    total_time_budget_sec: float = TOTAL_TIME_BUDGET_SEC_DEFAULT
    rescue_time_budget_sec: float = RESCUE_TIME_BUDGET_SEC_DEFAULT
    guard_feasible_prefix_min: int = GUARD_FEASIBLE_PREFIX_MIN_DEFAULT
    guard_feasible_prefix_multiplier: int = GUARD_FEASIBLE_PREFIX_MULTIPLIER_DEFAULT
    max_rescue_boxes: int = MAX_RESCUE_BOXES_DEFAULT
    rescue_radius_fraction: float = RESCUE_RADIUS_FRACTION_DEFAULT
    rescue_radius_min_ratio: float = RESCUE_RADIUS_MIN_RATIO_DEFAULT
    rescue_radius_max_ratio: float = RESCUE_RADIUS_MAX_RATIO_DEFAULT
    rescue_max_bb_eval: int = RESCUE_MAX_BB_EVAL_DEFAULT
    keep_per_rescue_box: int = KEEP_PER_RESCUE_BOX_DEFAULT
    global_search_mode: str = SEARCH_MODE_DISCO_MADS
    rescue_search_mode: str = SEARCH_MODE_MADS
    candidate_debug_limit: int = CANDIDATE_DEBUG_LIMIT_DEFAULT
    integer_target_fallback_max_tuples: int = INTEGER_TARGET_FALLBACK_MAX_TUPLES_DEFAULT
    baseline_search_policy: BaselineSearchPolicy | None = None
    refiner_config: RefinerConfig = RefinerConfig()
    finalization_reserve_fraction: float = 0.2
    finalization_reserve_max_sec: float = 30.0

    def refinement_deadline(self, runtime_budget) -> float:
        """Leave finite wall time for verification and exact identification."""
        return runtime_budget.deadline_before_reserve(
            fraction=self.finalization_reserve_fraction,
            max_seconds=self.finalization_reserve_max_sec,
        )

    @property
    def discrete_target_completion_max_tuples(self) -> int:
        """Preferred strategy-neutral alias for integer target enumeration cap."""

        return int(self.integer_target_fallback_max_tuples)

    def __post_init__(self) -> None:
        if not isfinite(self.finalization_reserve_fraction) or not (
            0 < self.finalization_reserve_fraction < 1
        ):
            raise ValueError("finalization_reserve_fraction must be finite and between 0 and 1")
        if (
            not isfinite(self.finalization_reserve_max_sec)
            or self.finalization_reserve_max_sec <= 0
        ):
            raise ValueError("finalization_reserve_max_sec must be positive and finite")
        if self.global_search_mode not in _ALLOWED_SEARCH_MODES:
            raise ValueError(
                "global_search_mode must be one of "
                f"{_ALLOWED_SEARCH_MODES}, got {self.global_search_mode!r}"
            )
        if self.rescue_search_mode not in _ALLOWED_RESCUE_SEARCH_MODES:
            raise ValueError(
                "rescue_search_mode must be one of "
                f"{_ALLOWED_RESCUE_SEARCH_MODES}, got {self.rescue_search_mode!r}"
            )

    @classmethod
    def sanity_tier(cls) -> ExternalPipelineConfig:
        """Return fast/sanity configuration tier."""
        return cls(
            search=NomadConfig.sanity_tier(),
            total_time_budget_sec=15.0,
            rescue_time_budget_sec=4.0,
            guard_feasible_prefix_min=32,
            guard_feasible_prefix_multiplier=4,
            max_rescue_boxes=4,
            rescue_max_bb_eval=40,
            keep_per_rescue_box=4,
            candidate_debug_limit=16,
        )

    @classmethod
    def standard_tier(cls) -> ExternalPipelineConfig:
        """Return standard/default configuration tier."""
        return cls(search=NomadConfig.standard_tier())

    @classmethod
    def production_baseline_tier(
        cls,
        *,
        seed: int,
        total_time_budget_sec: float,
        global_search_mode: str = SEARCH_MODE_DISCO_MADS,
    ) -> ExternalPipelineConfig:
        """Return the production baseline tier used by solver experiment runs."""
        base_config = cls.standard_tier()
        search_config = replace(
            base_config.search,
            seed_values=(int(seed),),
        )
        baseline_search_policy = BaselineSearchPolicy.production_baseline(
            authoritative_seed=seed,
            primary_search_mode=global_search_mode,
            hybrid_fallback_search_mode=SEARCH_MODE_HYBRID_LEGACY_NOMAD,
            fallback_seed_count=max(
                len(DEFAULT_SEED_VALUES),
                len(search_config.seed_values),
            ),
        )
        return replace(
            base_config,
            search=search_config,
            total_time_budget_sec=float(total_time_budget_sec),
            global_search_mode=global_search_mode,
            baseline_search_policy=baseline_search_policy,
        )
