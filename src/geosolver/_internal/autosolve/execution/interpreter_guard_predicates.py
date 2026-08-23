from __future__ import annotations


def is_guard_feasible_candidate(
    values: list[float],
    *,
    guard_fn,
) -> bool:
    try:
        return len(list(guard_fn(values))) == 0
    except Exception:
        return False
