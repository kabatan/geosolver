
from typing import List, Dict, Any, Optional
import numpy as np
from geosolver.core.result import SolveResult, SolveStatus

class SolutionManager:
    """解の管理（フィルタリング、重複除去、フォーマット）を行うクラス"""
    
    def __init__(self, tolerance: float = 1e-6):
        self.tolerance = tolerance
        self.solutions: List[List[float]] = []
        self.residuals: List[float] = []
        
    def add_solution(self, x: List[float], residual: float):
        """解候補を追加（閾値以下の残差のみ）"""
        if residual > self.tolerance:
            return
            
        # 重複チェック
        arr_x = np.array(x)
        for i, sol in enumerate(self.solutions):
            # float精度で同一視できる解がある場合
            if np.allclose(arr_x, np.array(sol), atol=1e-5):
                # 既存の解の方が残差が小さければ、新しい解は追加しない
                if self.residuals[i] <= residual:
                    return
                else:
                    # 新しい解の方が良ければ入れ替える
                    self.solutions[i] = x
                    self.residuals[i] = residual
                    return
        
        self.solutions.append(x)
        self.residuals.append(residual)
        
    def get_best_solution(self) -> Optional[List[float]]:
        """最も残差の小さい解を返す"""
        if not self.solutions:
            return None
        min_idx = np.argmin(self.residuals)
        return self.solutions[min_idx]
        
    def format_result(self, best_res_obj: Any = None, status: SolveStatus = None, errors: Optional[List[str]] = None) -> SolveResult:
        """SolveResultオブジェクトを生成"""
        if errors is None:
            errors = []
        best_x = self.get_best_solution()
        
        if best_x is not None:
            min_residual = min(self.residuals)
            final_status = SolveStatus.SUCCESS
        else:
            min_residual = float('inf')
            final_status = SolveStatus.NUMERIC_INSTABILITY if not status else status

        return SolveResult(
            status=final_status,
            value=best_x,
            solutions=self.solutions,
            residual=min_residual,
            elapsed_time=0.0,
            metadata={
                "scipy_result": str(best_res_obj) if best_res_obj else "",
                "n_solutions": len(self.solutions),
            },
            errors=errors
        )
