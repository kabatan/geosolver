"""Main initial-point discovery entry point."""

from collections.abc import Callable, Sequence
import inspect

from geosolver.engine.standard.config.search_budget import SearchBudget
from geosolver.engine.standard.solve.legacy_candidate_ops import (
    select_best_candidates,
)

from .evaluation import evaluate_chunk
from .strategies import generate_halton_random_points, generate_scale_adaptive_points


def _generate_halton_points(
    n: int, bounds: Sequence[tuple[float, float]], count: int, seed: int = 0
) -> list[list[float]]:
    return generate_halton_random_points(n, bounds, count, seed=seed)


_STRATEGIES: dict[str, Callable[[int, Sequence[tuple[float, float]], int], list[list[float]]]] = {
    "halton_random": _generate_halton_points,
    "scale_adaptive": generate_scale_adaptive_points,
}
_SEED_GENERATION_MULTIPLIER = 1


def _resolve_sample_count(
    n: int,
    n_points: int | None,
    search_budget: SearchBudget | None,
    has_exact: bool,
    phase_multiplier: float,
) -> int:
    if n_points is not None:
        return int(n_points)
    budget = SearchBudget() if search_budget is None else search_budget
    base_count = int(budget.compute_sample_size(dimension=n, has_exact=has_exact))
    scaled = int(base_count * max(0.1, float(phase_multiplier)))
    return max(1, scaled)


def _resolve_keep_count_for_seed_generation(sample_count: int) -> int:
    """Return the number of raw seeds to generate before ranking."""
    return max(1, int(sample_count) * int(_SEED_GENERATION_MULTIPLIER))


def _rank_candidates_with_mp_probe(
    candidates: Sequence[Sequence[float]],
    *,
    sample_count: int,
    precision: int | None,
    mp_probe_score: Callable[[Sequence[float]], float | None] | None,
) -> list[list[float]]:
    if (
        mp_probe_score is None
        or precision is None
        or int(precision) < 60
        or not candidates
    ):
        return [list(point) for point in candidates]

    probe_count = min(len(candidates), max(1, int(sample_count)))
    head = [list(point) for point in candidates[:probe_count]]
    tail = [list(point) for point in candidates[probe_count:]]

    ranked_head: list[tuple[float, list[float]]] = []
    for point in head:
        try:
            score = mp_probe_score(point)
            if score is None:
                score = float("inf")
            ranked_head.append((float(score), point))
        except Exception:
            ranked_head.append((float("inf"), point))

    ranked_head.sort(key=lambda item: item[0])
    return [point for _, point in ranked_head] + tail


def find_initial_points(
    n: int,
    bounds: Sequence[tuple[float, float]],
    objective: Callable[[Sequence[float]], float],
    *,
    n_points: int | None = None,
    strategy: str,
    search_budget: SearchBudget | None = None,
    has_exact: bool = False,
    phase_multiplier: float = 1.0,
    precision: int | None = None,
    mp_probe_score: Callable[[Sequence[float]], float | None] | None = None,
    seed: int = 0,
) -> list[list[float]]:
    """Generate and rank initial points by objective score."""
    generator = _STRATEGIES.get(strategy)
    if generator is None:
        raise ValueError(f"unknown strategy: {strategy}")
    sample_count = _resolve_sample_count(n, n_points, search_budget, has_exact, phase_multiplier)
    if sample_count <= 0:
        raise ValueError("sample count must be positive")
    generated_count = _resolve_keep_count_for_seed_generation(sample_count)
    try:
        accepts_seed = "seed" in inspect.signature(generator).parameters
    except (TypeError, ValueError):
        accepts_seed = False
    if accepts_seed:
        candidates = generator(n, bounds, generated_count, seed=seed)
    else:
        candidates = generator(n, bounds, generated_count)
    coarse_keep = min(len(candidates), max(1, sample_count))
    best = select_best_candidates(candidates, objective, limit=coarse_keep)
    best = _rank_candidates_with_mp_probe(
        best,
        sample_count=sample_count,
        precision=precision,
        mp_probe_score=mp_probe_score,
    )
    if best:
        return best[:sample_count]
    scored = sorted(evaluate_chunk(candidates, objective), key=lambda item: item[0])
    return [point for _, point in scored]
