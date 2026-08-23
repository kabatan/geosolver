"""Set mpmath dps from configured precision policy."""

from mpmath import mp
from .compute_target import _compute_target_dps


def _set_mp_dps_for_precision(precision: int, extra: int = 0) -> None:
    """Increase ``mp.dps`` to computed target when needed."""
    target = _compute_target_dps(precision, extra)
    if mp.dps < target:
        mp.dps = target
