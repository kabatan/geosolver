"""Diverse subset selection with farthest-first heuristic."""

from collections.abc import Sequence

from .remove_candidates import _distance


def select_diverse(candidates: Sequence[Sequence[float]], k: int) -> list[list[float]]:
    """Select up to ``k`` points maximizing pairwise spread."""
    pool = [[float(value) for value in point] for point in candidates]
    if not pool or k <= 0:
        return []
    selected = [pool[0]]
    while len(selected) < min(k, len(pool)):
        next_point = max(pool, key=lambda point: min(_distance(point, chosen) for chosen in selected))
        if next_point in selected:
            break
        selected.append(next_point)
    return selected
