"""
Geometric Sketch

幾何問題の構築と解決を行うためのハイレベルAPI。
変数管理、制約管理、ソルバー連携を担う。
"""

from typing import List, Callable, Dict, Any, Sequence
from functools import partial
import numpy as np

from geosolver.geometry.entities.base import Point, Line, Circle
from geosolver.solver import solve, SolveResult, SolveStatus

class GeometricSketch:
    """幾何スケッチクラス"""
    
    def __init__(self) -> None:
        self.points: List[Point] = []
        self.fixed_points: List[Point] = []
        self.constraints: List[Callable] = [] # 制約関数 f(x) -> float (residual)
        # 他の要素（Line, Circle）はPointに依存するので、Pointさえ管理すれば良い（変数はPointの座標のみ）
        # ただし、未知の半径などを持つCircleを扱うなら変数が必要
        self.variables: List[str] = [] # 変数名のリスト（デバッグ用）

    def point(self, x: float | None = None, y: float | None = None) -> Point:
        """
        点を作成する。
        引数が指定されている場合は固定点、Noneの場合は変数となる。
        """
        if x is not None and y is not None:
             # 固定点
             p = Point(x, y)
             self.fixed_points.append(p)
             return p
        else:
            # 変数としての点（初期値はランダム）
            # ここではSymbolではなく、solve時に動的に値を割り当てるためのプレースホルダーとしてPointを使う
            # Pointの実装がどうなっているかによるが、Coordinateがシンボリックか数値か...
            # GeometryEntityの設計では sympy.Symbol を持つことができるはず。
            
            # 簡易実装: とりあえずプレースホルダーとして機能させる
            # 座標はsolve時に決定される
            from sympy import Symbol
            import uuid
            uid = str(uuid.uuid4())[:8]
            sx = Symbol(f"x_{uid}")
            sy = Symbol(f"y_{uid}")
            p = Point(sx, sy)
            self.points.append(p)
            self.variables.append(f"x_{uid}")
            self.variables.append(f"y_{uid}")
            return p

    def add_constraint(self, constraint_func: Callable[[], float]) -> None:
        """
        制約を追加する。
        constraint_func は残差（0になるべき値）を返す関数。
        例: lambda: Distance(A, B) - 3.0
        """
        self.constraints.append(constraint_func)

    def solve(self, **kwargs: Any) -> SolveResult:
        """問題を解く"""
        # 変数の抽出
        # self.points の中で変数が割り当てられているものを対象とする
        # 変数リスト: [x1, y1, x2, y2, ...]
        
        variable_points = []
        initial_guess = []
        bounds_list = []
        
        # 変数のセットアップ
        # Point(Symbol, Symbol) の状態になっているものを探す
        # 単純化のため、すべてのpointを変数として扱い、fixed_pointsを変数としない、とする
        # しかし内部的には一律Pointリスト管理かもしれないので区別が必要
        
        # initで points と fixed_points を分けている
        for p in self.points:
            variable_points.append(p)
            # 初期値はランダム (-5 ~ 5 程度)
            import random
            initial_guess.append(random.uniform(-5, 5))
            initial_guess.append(random.uniform(-5, 5))
            # bounds（将来的にユーザー指定対応を追加予定）
            bounds_list.append((-100.0, 100.0))
            bounds_list.append((-100.0, 100.0))

        n_vars = len(initial_guess)
        
        # シンボルのバックアップ
        # Point.x, Point.y は sympy.Symbol のはず
        original_coords = []
        for p in variable_points:
            original_coords.append((p.x, p.y))
        
        # ソルバー実行
        residual_func = partial(
            _residual_from_vector,
            variable_points=variable_points,
            constraints=self.constraints,
        )

        result = solve(
            n=n_vars,
            f=residual_func,
            v=[0.0] * len(self.constraints), # 制約が返す残差は0になるべき。ただし制約数が動的なら対応必要
            # solveのインターフェースは f: x -> [float] なので、戻り値リストの長さは len(v) と一致する必要がある
            # ここでは簡単のため、constraintsの数 = 目標値の数と仮定するが、
            # 1つのconstraint_funcが複数の値を返す場合に対応できていない。
            # -> solve() の v は目標値リストだが、これが residual_func の戻り値と整合する必要がある。
            # 一般には f(x) = 0 を解くので v=[0,0,...] である。
            # Dimensionality checkを避けるため、vの長さを自動調整するか、residual_func内で調整する必要がある。
            # geosolver.solver.numeric は minimize(sum(residuals**2)) なので、
            # vの次元と f(x) の次元が一致していればOK。
            # 
            # 暫定: 最初の呼び出しで次元を決定する
        )
        
        # 実行前のダミー呼び出しで次元確認
        dummy_res = _residual_from_vector(initial_guess, variable_points, self.constraints)
        target_v = [0.0] * len(dummy_res)
        
        final_result = solve(
            n=n_vars,
            f=residual_func,
            v=target_v,
            bounds=bounds_list,
            **kwargs
        )
        
        if final_result.status == SolveStatus.SUCCESS:
            # 成功時: Pointに最終的な値をセット済み（residual_funcの副作用でセットされている可能性が高いが、
            # minimizeの最終評価でセットされているとは限らないので明示的にセット）
            sol = final_result.value
            if sol:
                idx = 0
                for p in variable_points:
                    p.x = sol[idx]
                    p.y = sol[idx+1]
                    idx += 2
        else:
            # 失敗時: 元のシンボルに戻す
            for i, p in enumerate(variable_points):
                p.x, p.y = original_coords[i]

        return final_result


def _evaluate_constraints(
    constraints: List[Callable[[], Any]],
) -> List[float]:
    res_list: List[float] = []
    for constraint_func in constraints:
        try:
            value = constraint_func()
            if isinstance(value, (list, tuple)):
                res_list.extend([float(v) for v in value])
            else:
                res_list.append(float(value))
        except Exception:
            res_list.append(1e10)
    return res_list


def _residual_from_vector(
    vec: Sequence[float],
    variable_points: List[Point],
    constraints: List[Callable[[], Any]],
) -> List[float]:
    idx = 0
    for point in variable_points:
        point.x = vec[idx]
        point.y = vec[idx + 1]
        idx += 2
    return _evaluate_constraints(constraints)
