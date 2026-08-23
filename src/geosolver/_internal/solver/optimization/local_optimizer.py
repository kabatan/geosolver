
from abc import ABC, abstractmethod
from functools import partial
from typing import List, Callable, Optional, Tuple, Any, Dict
import numpy as np
from scipy import optimize as scipy_optimize

class OptimizationResult:
    def __init__(self, x: List[float], fun: float, success: bool, message: str = ""):
        self.x = x
        self.fun = fun
        self.success = success
        self.message = message
        self.metadata: Dict[str, Any] = {}

class LocalOptimizer(ABC):
    """局所最適化戦略の抽象基底クラス"""
    
    @abstractmethod
    def optimize(
        self,
        objective: Callable[[List[float]], float],
        x0: List[float],
        bounds: List[Tuple[float, float]],
        constraints: List[Dict] = []
    ) -> OptimizationResult:
        """
        初期点から局所最適化を行う。
        """
        pass

class ScipyOptimizer(LocalOptimizer):
    """scipy.optimize.minimize (L-BFGS-B) を使用した最適化"""
    
    def __init__(self, method: str = "L-BFGS-B", options: Dict = None):
        self.method = method
        self.options = options or {"ftol": 1e-12, "gtol": 1e-12, "maxiter": 1000}
        
    def optimize(
        self,
        objective: Callable[[List[float]], float],
        x0: List[float],
        bounds: List[Tuple[float, float]],
        constraints: List[Dict] = []
    ) -> OptimizationResult:
        
        try:
            res = scipy_optimize.minimize(
                objective,
                x0,
                method=self.method,
                bounds=bounds,
                constraints=constraints,
                options=self.options
            )
            
            return OptimizationResult(
                x=res.x.tolist(),
                fun=float(res.fun),
                success=res.success or res.fun < 1e-6, # 緩和条件
                message=str(res.message)
            )
        except Exception as e:
            return OptimizationResult(
                x=x0,
                fun=float('inf'),
                success=False,
                message=str(e)
            )

class LeastSquaresOptimizer(LocalOptimizer):
    """
    scipy.optimize.least_squares を使用した最適化
    
    archive/geosolver.py の _optimize_all ロジックを移植。
    - 条件分岐を含む関数でも安定して動作
    - 勾配近似にBroydenを使用
    """
    
    def __init__(self, max_nfev: int = 5000, ftol: float = 1e-12, xtol: float = 1e-12):
        self.max_nfev = max_nfev
        self.ftol = ftol
        self.xtol = xtol
        
    def optimize(
        self,
        objective: Callable[[List[float]], float],
        x0: List[float],
        bounds: List[Tuple[float, float]],
        constraints: List[Dict] = []
    ) -> OptimizationResult:
        """
        objectiveは f(x) -> コスト(float) を返す関数を期待するが、
        least_squaresは f(x) -> 残差ベクトル を期待する。
        
        内部でラッパーを作成して対応。
        """
        n = len(x0)
        
        # residual_funcを作成するために、objectiveの構造を推測
        # objectiveがすでにコスト(スカラー)を返す関数なら、
        # 単一要素の残差ベクトルに変換する
        residual_func = partial(_least_squares_residual, objective=objective)
        
        # boundsの変換（NumPy配列化で高速化）
        bounds_arr = np.asarray(bounds, dtype=np.float64)
        lower = bounds_arr[:, 0]
        upper = bounds_arr[:, 1]
        
        try:
            res = scipy_optimize.least_squares(
                residual_func,
                x0,
                bounds=(lower, upper),
                method='trf',  # Trust Region Reflective
                ftol=self.ftol,
                xtol=self.xtol,
                max_nfev=self.max_nfev,
                diff_step=1e-8
            )
            
            # コストを再計算
            final_cost = objective(list(res.x))
            
            return OptimizationResult(
                x=res.x.tolist(),
                fun=float(final_cost) if np.isfinite(final_cost) else float('inf'),
                success=res.success or final_cost < 1e-6,
                message=str(res.message)
            )
        except Exception as e:
            return OptimizationResult(
                x=x0,
                fun=float('inf'),
                success=False,
                message=str(e)
            )

from .local_optimizer_high_precision import HighPrecisionRefiner


def _least_squares_residual(
    x: List[float],
    *,
    objective: Callable[[List[float]], float],
) -> np.ndarray:
    try:
        cost = objective(list(x))
        if not np.isfinite(cost):
            return np.full(1, 1e10)
        return np.array([np.sqrt(max(0, cost))])
    except Exception:
        return np.full(1, 1e10)

