"""Configuration for mpmath local refiner."""

from __future__ import annotations

from dataclasses import dataclass

from mpmath import mp

CLOSURE_SCHEDULE_DPS = (120, 250, 350, 500)
SCHEDULE_DPS = (50, 100, 120)
TARGET_RESIDUALS = {
    50: mp.mpf("1e-20"),
    100: mp.mpf("1e-50"),
    120: mp.mpf("1e-80"),
    250: mp.mpf("1e-150"),
    350: mp.mpf("1e-220"),
    500: mp.mpf("1e-320"),
}
DAMPING_INITIAL = mp.mpf("1e-6")
DAMPING_MIN = mp.mpf("1e-12")
DAMPING_SCALE = mp.mpf("4")
STAGE_TOLERANCE = mp.mpf("1e-10")
MAX_STAGE_ITERS = 80
STALL_LIMIT = 5
LINE_SEARCH_FAILURE_LIMIT = 12
LINE_SEARCH_MAX_STEPS = 20
DEDUP_ANSWER_TOLERANCE = mp.mpf("1e-20")
STAGE_PROMOTION_RELAX_POWER = mp.mpf("0.5")
DIRECT_ACCEPT_RESIDUAL = mp.mpf("1e-15")
DIRECT_ACCEPT_DPS = 120


@dataclass(frozen=True)
class RefinerConfig:
    """Runtime configuration for multi-stage refinement."""

    schedule_dps: tuple[int, ...] = SCHEDULE_DPS
    closure_schedule_dps: tuple[int, ...] = CLOSURE_SCHEDULE_DPS
    max_stage_iters: int = MAX_STAGE_ITERS
    stage_tolerance: object = STAGE_TOLERANCE
    damping_initial: object = DAMPING_INITIAL
    damping_min: object = DAMPING_MIN
    damping_scale: object = DAMPING_SCALE
    stall_limit: int = STALL_LIMIT
    line_search_failure_limit: int = LINE_SEARCH_FAILURE_LIMIT
    line_search_max_steps: int = LINE_SEARCH_MAX_STEPS
    dedup_answer_tolerance: object = DEDUP_ANSWER_TOLERANCE
    stage_promotion_relax_power: object = STAGE_PROMOTION_RELAX_POWER
    direct_accept_residual: object | None = DIRECT_ACCEPT_RESIDUAL
    direct_accept_dps: int = DIRECT_ACCEPT_DPS

    def target_for_dps(self, dps: int) -> object:
        """Return stage target residual for a precision level."""
        if dps not in TARGET_RESIDUALS:
            raise ValueError(f"Unsupported dps stage: {dps}")
        return TARGET_RESIDUALS[dps]

    def promotion_threshold_for_dps(self, dps: int) -> object:
        """Return relaxed residual threshold that allows promotion to the next stage."""
        target = mp.mpf(self.target_for_dps(dps))
        relax_power = mp.mpf(self.stage_promotion_relax_power)
        if relax_power <= mp.mpf("0") or relax_power > mp.mpf("1"):
            raise ValueError("stage_promotion_relax_power must be in (0, 1]")
        return mp.power(target, relax_power)

