"""
Numeric Solver

SciPy を用いた数値解法。初期点生成・ローカル最適化・解管理を
コンポーネント化し、ここではフロー制御に専念する。
"""

from functools import partial
from typing import Callable, List, Optional, Tuple

import numpy as np

from geosolver.core.result import SolveResult, SolveStatus
from geosolver.solver.base import AbstractSolver
from geosolver.solver.common import (
    normalize_bounds,
    objective_from_residuals,
    expand_bounds_around_point,
)
from geosolver._internal.solver.optimization.local_optimizer import ScipyOptimizer
from geosolver._internal.solver.search.strategies.search_strategy import (
    HaltonSearchStrategy,
    ScaleAdaptiveSearchStrategy,
)
from geosolver._internal.solver.optimization.solution_manager import SolutionManager


class NumericSolver(AbstractSolver):
    """
    数値解法ベースのソルバ。

    Component-based architecture:
    - SearchStrategy: 初期点探索 (Halton / ScaleAdaptive)
    - LocalOptimizer: 局所最適化 (scipy.optimize)
    - SolutionManager: 解の収集と整形
    """

    def solve(
        self,
        f: Callable[[List[float]], List[float]],
        v: List[float],
        bounds: Optional[List[Tuple[float, float]]] = None,
    ) -> SolveResult:
        """
        f(x) = v を満たす解を探索する。
        """
        n = self.config.n
        v_arr = np.asarray(v, dtype=float)

        bounds = normalize_bounds(bounds, n)
        objective = objective_from_residuals(f, v_arr)

        # 1. 初期点生成
        search_strategy = (
            ScaleAdaptiveSearchStrategy()
            if self.config.strategy == "scale_adaptive"
            else HaltonSearchStrategy()
        )
        initial_points = search_strategy.generate_initial_points(n, bounds, objective, self.config)

        # 2. 局所最適化
        optimizer = ScipyOptimizer()
        solution_manager = SolutionManager(tolerance=1e-6)

        best_opt_res = None
        min_cost = float("inf")

        find_all = self.config.find_all
        max_solutions = self.config.max_solutions if find_all else 1

        for x0 in initial_points:
            current_bounds = expand_bounds_around_point(bounds, x0)

            opt_res = optimizer.optimize(objective, x0, current_bounds)

            # 高精度リファイン（mpmath backend）
            if opt_res.success and self.config.precision > 15:
                from geosolver._internal.solver.optimization.local_optimizer import HighPrecisionRefiner

                refiner = HighPrecisionRefiner()

                residual_func = partial(_high_precision_residual, f=f, v_arr=v_arr)
                refine_res = refiner.refine(residual_func, opt_res.x, self.config.precision)

                if refine_res.success:
                    opt_res = refine_res

            if opt_res.fun < min_cost:
                min_cost = float(opt_res.fun)
                best_opt_res = opt_res

            if opt_res.success:
                solution_manager.add_solution(opt_res.x, opt_res.fun)

            # 早期終了条件
            if not find_all:
                if min_cost < 1e-12:
                    break
            else:
                if len(solution_manager.solutions) >= max_solutions:
                    break

        # 3. 結果整形
        return solution_manager.format_result(
            best_res_obj=best_opt_res,
            status=SolveStatus.SUCCESS if min_cost < 1e-6 else SolveStatus.NUMERIC_INSTABILITY,
        )


def _high_precision_residual(
    x: List[float],
    *,
    f: Callable[[List[float]], List[float]],
    v_arr: np.ndarray,
) -> List[object]:
    from mpmath import mp

    try:
        vals = f(x)
        v_mp = [mp.mpf(val) for val in v_arr]
        return [vals[i] - v_mp[i] for i in range(len(vals))]
    except Exception:
        return [mp.mpf("inf")] * len(v_arr)
