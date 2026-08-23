"""Worker management for multi-solution refinement."""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor


def refine_with_workers(
    solutions: Sequence[Sequence[object]],
    refine_one: Callable[[Sequence[object]], list[object]],
    *,
    use_parallel: bool,
    max_workers: int,
) -> list[list[object]]:
    """Refine candidate solutions in serial or thread-parallel mode."""
    if not use_parallel or max_workers <= 1:
        return [refine_one(solution) for solution in solutions]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(refine_one, solutions))
