"""Target precision computation helpers."""


def _compute_target_dps(precision: int, extra: int = 0) -> int:
    """Compute robust ``mp.dps`` target from requested precision."""
    try:
        prec = max(1, int(precision))
    except Exception:
        prec = 50
    buffer = max(40, min(prec // 4 + 40, 160))
    extra_guard = max(0, min(int(extra), max(40, prec // 4)))
    target = prec + buffer + extra_guard
    if prec <= 240:
        target = min(target, prec + 180)
    return min(target, 2000)
