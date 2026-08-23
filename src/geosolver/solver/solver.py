"""
Geometric Solver

数値計算とシンボリック計算を統合した高位ソルバー。
初期値探索、数値最適化、高精度化、厳密値復元を一連のパイプラインとして実行する。

NOTE: 完全な機能は solve.py の solve() 関数を使用してください。
このGeometricSolverは後方互換性のためのラッパーです。
"""

from typing import Callable, List, Optional, Tuple

from geosolver.core.result import SolveResult
from geosolver.solver.base import AbstractSolver
from geosolver.solver.numeric import NumericSolver


class GeometricSolver(AbstractSolver):
    """
    幾何問題ソルバー

    NOTE: 新しい solve() 関数 (solve.py) がフル機能を提供します。
    このクラスは後方互換性のためのラッパーです。
    """

    def solve(
        self,
        f: Callable[[List[float]], List[float]],
        v: List[float],
        bounds: Optional[List[Tuple[float, float]]] = None,
    ) -> SolveResult:
        """
        NumericSolver を呼び出す後方互換ラッパー。

        Process:
        1. 初期点探索
        2. 数値最適化 (NumericSolver)
        3. 厳密値復元 (将来実装)
        """
        # 1. 範囲自動設定（簡易版）
        if bounds is None:
            bounds = [(-100.0, 100.0) for _ in range(self.config.n)]

        # 2. 数値ソルバー実行
        numeric_result = NumericSolver(self.config).solve(f, v, bounds)

        # 3. 厳密値復元は未実装。将来の AlgebraicReconstructor に委ねる。
        return numeric_result

