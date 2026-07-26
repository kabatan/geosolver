"""Reusable candidate operations for legacy solver/optimizer flows."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import math
from typing import Any


def safe_objective_value(
    objective: Callable[[Sequence[float]], float],
    point: Sequence[float],
) -> float | None:
    try:
        score = float(objective(point))
    except Exception:
        return None
    if not math.isfinite(score):
        return None
    return score


def select_best_candidates(
    candidates: Sequence[Sequence[float]],
    objective: Callable[[Sequence[float]], float],
    *,
    limit: int,
) -> list[list[float]]:
    scored: list[tuple[float, list[float]]] = []
    for candidate in candidates:
        point = [float(value) for value in candidate]
        score = safe_objective_value(objective, point)
        if score is None:
            continue
        scored.append((score, point))
    if not scored:
        fallback = [[float(value) for value in candidate] for candidate in candidates]
        return fallback[: max(0, int(limit))]
    scored.sort(key=lambda item: item[0])
    return [point for _, point in scored[: max(0, int(limit))]]


def pick_best_solution(
    candidates: Sequence[Sequence[float]],
    *,
    g: Callable[[list[float]], float],
    mode: str,
) -> list[float] | None:
    if not candidates:
        return None
    if mode == "max":
        best = max(candidates, key=lambda point: safe_objective_value(g, point) or float("-inf"))
    else:
        best = min(candidates, key=lambda point: safe_objective_value(g, point) or float("inf"))
    return [float(value) for value in best]


def safe_optimize_candidate(
    optimize_one: Callable[[Sequence[float]], Sequence[float]],
    candidate: Sequence[float],
) -> list[float]:
    seed = [float(value) for value in candidate]
    try:
        optimized = optimize_one(seed)
    except Exception:
        return seed
    if not isinstance(optimized, (list, tuple)):
        return seed
    normalized = [float(value) for value in optimized]
    if len(normalized) != len(seed):
        return seed
    if any(not math.isfinite(value) for value in normalized):
        return seed
    return normalized


def safe_refine_candidate(
    refine_one: Callable[[Sequence[Any]], Sequence[Any]],
    solution: Sequence[Any],
) -> list[Any]:
    seed = list(solution)
    try:
        refined = refine_one(seed)
    except Exception:
        return seed
    if not isinstance(refined, (list, tuple)):
        return seed
    normalized = list(refined)
    if len(normalized) != len(seed):
        return seed
    return normalized


def dedupe_refined_solutions(
    solutions: Sequence[Sequence[Any]],
    *,
    tolerance: float = 1e-9,
) -> list[list[Any]]:
    unique: list[list[Any]] = []
    for solution in solutions:
        candidate = list(solution)
        is_duplicate = False
        for accepted in unique:
            if len(candidate) != len(accepted):
                continue
            diffs: list[float] = []
            comparable = True
            for left, right in zip(candidate, accepted):
                try:
                    diffs.append(abs(float(left) - float(right)))
                except Exception:
                    comparable = False
                    break
            if comparable and all(diff <= tolerance for diff in diffs):
                is_duplicate = True
                break
            if not comparable and candidate == accepted:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(candidate)
    return unique
