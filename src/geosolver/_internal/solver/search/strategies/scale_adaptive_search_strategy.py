"""Scale-adaptive initial-point search strategy."""

from collections.abc import Callable

import numpy as np

from geosolver._internal.solver.base import SolverConfig

from .halton_search_strategy import SearchStrategy, _first_primes, _halton_value


NEAR_ZERO_CHOICE_THRESHOLD = 0.4
LOG_SCALE_CHOICE_THRESHOLD = 0.7
MAX_LOG10_EXPONENT = 12.0
MIN_NORMALIZED_DISTANCE = 0.05
BEST_CANDIDATE_RATIO = 0.7


class ScaleAdaptiveSearchStrategy(SearchStrategy):
    """Scale-adaptive initial-point search strategy."""

    def generate_initial_points(
        self,
        n: int,
        bounds: list[tuple[float, float]],
        objective: Callable[[list[float]], float],
        config: SolverConfig,
    ) -> list[list[float]]:
        seed = config.seed
        rng = np.random.default_rng(seed) if seed is not None else None

        values = getattr(config, "v", None)
        if values is not None:
            auto_bounds = self._auto_bounds(values, n)
        else:
            auto_bounds = [(-100.0, 100.0) for _ in range(n)]

        is_default_bounds = True
        for low, high in bounds:
            if low != -100.0 or high != 100.0:
                is_default_bounds = False
                break

        if is_default_bounds:
            bounds = auto_bounds

        n_samples = min(5000, 1000 + 300 * n)
        n_keep = min(80, max(30, 4 * n))
        primes = _first_primes(3 * n) if rng is None else []

        valid_points: list[tuple[float, list[float]]] = []
        for index in range(n_samples):
            sample_id = 1 + index
            point: list[float] = []

            for dim, (low, high) in enumerate(bounds):
                if rng is not None:
                    choice = float(rng.random())
                    offset = float(rng.random())
                    sign = float(rng.random())
                else:
                    choice = _halton_value(sample_id, primes[dim])
                    offset = _halton_value(sample_id, primes[n + dim])
                    sign = _halton_value(sample_id, primes[2 * n + dim])

                if choice < NEAR_ZERO_CHOICE_THRESHOLD:
                    low2 = max(low, -10)
                    high2 = min(high, 10)
                    value = low2 if high2 <= low2 else low2 + offset * (high2 - low2)
                elif choice < LOG_SCALE_CHOICE_THRESHOLD:
                    if high > 1:
                        exp_max = min(float(np.log10(abs(high))), MAX_LOG10_EXPONENT)
                        exponent = offset * exp_max
                        value = 10 ** exponent
                        if sign < 0.5:
                            value = -value
                    else:
                        value = low + offset * (high - low)
                else:
                    value = low + offset * (high - low)

                value = max(low, min(high, value))
                point.append(value)

            try:
                cost = objective(point)
                if np.isfinite(cost) and cost < 1e20:
                    valid_points.append((cost, point))
            except Exception:
                continue

        valid_points.sort(key=lambda item: item[0])
        selected = self._select_diverse_points(valid_points, n_keep, bounds)
        return selected if selected else [[0.0] * n]

    def _auto_bounds(self, values: list[float], n: int) -> list[tuple[float, float]]:
        scales: list[float] = []
        for value in values:
            try:
                as_float = float(value)
                if as_float != 0 and np.isfinite(as_float):
                    scales.append(abs(as_float))
            except (TypeError, ValueError):
                continue

        max_scale = max(scales) if scales else 1.0
        scale = max(100.0, max_scale * 100.0)
        scale = min(scale, 1e12)
        return [(-float(scale), float(scale)) for _ in range(n)]

    def _select_diverse_points(
        self,
        scored_points: list[tuple[float, list[float]]],
        n_keep: int,
        bounds: list[tuple[float, float]],
    ) -> list[list[float]]:
        if not scored_points:
            return []

        ranges = [max(float(high - low), 1.0) for low, high in bounds]
        min_norm_dist = MIN_NORMALIZED_DISTANCE
        selected: list[list[float]] = []

        best_budget = max(1, int(round(BEST_CANDIDATE_RATIO * n_keep)))
        explore_budget = max(0, n_keep - best_budget)

        for _, point in scored_points:
            if len(selected) >= best_budget:
                break
            if self._is_far_enough(point, selected, ranges, min_norm_dist):
                selected.append(point)

        if explore_budget > 0 and len(selected) < n_keep:
            total = len(scored_points)
            for bucket in range(explore_budget):
                if len(selected) >= n_keep:
                    break
                base = int(round((bucket + 1) * (total - 1) / (explore_budget + 1)))
                for idx in range(base, min(total, base + 64)):
                    _, point = scored_points[idx]
                    if self._is_far_enough(point, selected, ranges, min_norm_dist):
                        selected.append(point)
                        break

        if len(selected) < n_keep:
            existing = {tuple(np.round(np.asarray(p, dtype=np.float64), 12)) for p in selected}
            for _, point in scored_points:
                if len(selected) >= n_keep:
                    break
                key = tuple(np.round(np.asarray(point, dtype=np.float64), 12))
                if key in existing:
                    continue
                selected.append(point)
                existing.add(key)

        return selected

    @staticmethod
    def _is_far_enough(
        point: list[float],
        selected: list[list[float]],
        ranges: list[float],
        min_norm_dist: float,
    ) -> bool:
        if not selected:
            return True

        point_array = np.asarray(point, dtype=np.float64)
        ranges_array = np.asarray(ranges, dtype=np.float64)
        for existing in selected:
            existing_array = np.asarray(existing, dtype=np.float64)
            diff = (point_array - existing_array) / ranges_array
            if float(np.linalg.norm(diff)) < min_norm_dist:
                return False
        return True
