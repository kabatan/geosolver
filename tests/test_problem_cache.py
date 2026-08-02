from __future__ import annotations

from geotarget.problem_cache import clear_validation_cache, validate_cached


def test_validation_cache_reuses_canonical_problem_order(problem: dict) -> None:
    clear_validation_cache()
    reordered = {key: problem[key] for key in reversed(tuple(problem))}

    first, first_hit = validate_cached(problem)
    second, second_hit = validate_cached(reordered)

    assert first_hit is False
    assert second_hit is True
    assert second.normalized_problem == first.normalized_problem
