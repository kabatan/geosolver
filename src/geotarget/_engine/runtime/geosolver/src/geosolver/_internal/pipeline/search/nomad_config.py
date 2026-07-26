"""Configuration for NOMAD global-search backend."""

from __future__ import annotations

from dataclasses import dataclass

DISCO_MADS_OPTIMIZATION = True
DISCO_MADS_HID_CONST = True
DISCO_MADS_HID_CONST_OUTPUT_VALUE = 1e20
DISPLAY_DEGREE = 0
ADD_SEED_TO_FILE_NAMES = "no"
SEARCH_MODE_DISCO_MADS = "disco_mads"
SEARCH_MODE_MADS = "mads"
DEFAULT_SEED_VALUES = (11, 22, 33, 44, 55)

SANITY_TIER_BUDGET_DEFAULT = 100
STANDARD_TIER_BUDGET_DEFAULT = 200
GUARD_PENALTY_DEFAULT = 1e6
KEEP_PER_RUN_DEFAULT = 64
KEEP_AFTER_DEDUP_DEFAULT = 20
MIN_PER_SEED_AFTER_DEDUP_DEFAULT = 3
START_DEDUP_DISTANCE_DEFAULT = 1e-2
DEDUP_DISTANCE_DEFAULT = 1e-4
BOUND_EXPANSION_RATIO_DEFAULT = 0.25


def derive_seed_values(
    external_seed: int,
    *,
    count: int = len(DEFAULT_SEED_VALUES),
) -> tuple[int, ...]:
    """Derive deterministic backend seeds from an authoritative external seed."""
    normalized_seed = int(external_seed)
    normalized_count = max(0, int(count))
    return tuple(normalized_seed + index for index in range(normalized_count))


@dataclass(frozen=True)
class NomadConfig:
    """NOMAD runtime parameters."""

    max_bb_eval: int
    max_time_sec: float | None = None
    seed_values: tuple[int, ...] = DEFAULT_SEED_VALUES
    guard_penalty: float = GUARD_PENALTY_DEFAULT
    keep_per_run: int = KEEP_PER_RUN_DEFAULT
    keep_after_dedup: int = KEEP_AFTER_DEDUP_DEFAULT
    min_per_seed_after_dedup: int = MIN_PER_SEED_AFTER_DEDUP_DEFAULT
    start_dedup_distance: float = START_DEDUP_DISTANCE_DEFAULT
    dedup_distance: float = DEDUP_DISTANCE_DEFAULT
    bound_expansion_ratio: float = BOUND_EXPANSION_RATIO_DEFAULT
    # Compatibility flag for callers that distinguish exhaustive portfolio runs
    # from early-stopping search. The current implementation keeps the complete
    # schedule by default and does not short-circuit after the first admissible point.
    complete_search: bool = True

    @classmethod
    def sanity_tier(cls) -> "NomadConfig":
        return cls(max_bb_eval=SANITY_TIER_BUDGET_DEFAULT)

    @classmethod
    def standard_tier(cls) -> "NomadConfig":
        return cls(max_bb_eval=STANDARD_TIER_BUDGET_DEFAULT)

    def build_params(
        self,
        *,
        dimension: int,
        seed: int,
        search_mode: str,
    ) -> list[str]:
        """Build NOMAD parameter list."""
        if search_mode == SEARCH_MODE_DISCO_MADS:
            disco_mads_optimization = "true"
        elif search_mode == SEARCH_MODE_MADS:
            disco_mads_optimization = "false"
        else:
            raise ValueError(
                f"search_mode must be '{SEARCH_MODE_DISCO_MADS}' or '{SEARCH_MODE_MADS}', got {search_mode!r}"
            )
        return [
            f"DIMENSION {dimension}",
            "BB_OUTPUT_TYPE OBJ",
            f"DISCO_MADS_OPTIMIZATION {disco_mads_optimization}",
            f"DISCO_MADS_HID_CONST {str(DISCO_MADS_HID_CONST).lower()}",
            f"DISCO_MADS_HID_CONST_OUTPUT_VALUE {DISCO_MADS_HID_CONST_OUTPUT_VALUE}",
            f"MAX_BB_EVAL {self.max_bb_eval}",
            *(
                [f"MAX_TIME {int(self.max_time_sec)}"]
                if self.max_time_sec is not None and int(self.max_time_sec) > 0
                else []
            ),
            f"DISPLAY_DEGREE {DISPLAY_DEGREE}",
            f"SEED {seed}",
            f"ADD_SEED_TO_FILE_NAMES {ADD_SEED_TO_FILE_NAMES}",
        ]

