"""
GeoSolver Result型

Solver/Optimizerの統一結果型。
例外ではなくステータスコードで失敗理由を表現する。
"""

from dataclasses import dataclass, field
from typing import Generic, List, Optional, TypeVar, Dict, Any
from geosolver.exact.value import ExactValue


from enum import Enum, auto

T = TypeVar("T")


class SolveStatus(Enum):
    """Solver/Optimizerの実行結果ステータス"""

    SUCCESS = auto()
    """解が見つかり、目標精度に達した"""

    PARTIAL_SUCCESS = auto()
    """解は見つかったが、目標精度に達しなかった"""

    NO_SOLUTION = auto()
    """解が見つからなかった"""

    TIMEOUT = auto()
    """時間制限に達した"""

    DEGENERATE = auto()
    """退化した図形（無効な入力）"""

    NUMERIC_INSTABILITY = auto()
    """数値的に不安定"""

    INVALID_INPUT = auto()
    """無効な入力パラメータ"""

    RUNTIME_ERROR = auto()
    """実行時エラー（例外発生）"""


@dataclass
class SolveResult(Generic[T]):
    """
    Solver/Optimizerの統一結果型

    Attributes:
        status: 実行結果のステータス
        value: 最良の解（成功時）
        solutions: 見つかった全ての解
        residual: 残差ノルム
        precision_achieved: 達成した精度（桁数）
        elapsed_time: 計算時間（秒）
        exact_answer: 厳密値の文字列表現
        minimal_polynomial: 最小多項式の係数
        metadata: 追加のメタデータ
        errors: エラーメッセージのリスト
    """

    status: SolveStatus
    value: Optional[T] = None
    solutions: List[T] = field(default_factory=list)
    answer_values: List[Any] = field(
        default_factory=list
    )  # Answer expression values for each solution
    residual: Any = float("inf")  # Changed from float to Any to preserve mpf precision
    precision_achieved: int = 0
    elapsed_time: float = 0.0
    exact_answer: Optional[str] = None
    minimal_polynomial: Optional[List[int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """解が成功したかどうか"""
        return self.status in (SolveStatus.SUCCESS, SolveStatus.PARTIAL_SUCCESS)

    @property
    def n_solutions(self) -> int:
        """見つかった解の数"""
        return len(self.solutions)

    def to_dict(self) -> Dict[str, Any]:
        """結果を辞書に変換（JSON出力用）"""
        return {
            "status": self.status.name,
            "success": self.success,
            "value": self.value,
            "n_solutions": self.n_solutions,
            "residual": float(self.residual),
            "precision_achieved": self.precision_achieved,
            "elapsed_time": self.elapsed_time,
            "exact_answer": self.exact_answer,
            "minimal_polynomial": self.minimal_polynomial,
            "errors": self.errors,
        }

    @classmethod
    def from_legacy(cls, solution: List[float], info: Dict[str, Any]) -> "SolveResult[List[float]]":
        """
        既存のsolve()戻り値から変換

        Args:
            solution: 解ベクトル
            info: 情報辞書（success, all_solutions, etc.）

        Returns:
            SolveResult オブジェクト
        """
        if info.get("success", False):
            status = SolveStatus.SUCCESS
        elif info.get("timeout", False):
            status = SolveStatus.TIMEOUT
        else:
            status = SolveStatus.NO_SOLUTION

        return cls(
            status=status,
            value=solution if info.get("success") else None,
            solutions=info.get("all_solutions", []),
            residual=info.get("residual_norm", float("inf")),
            precision_achieved=int(info.get("precision_achieved", 0)),
            elapsed_time=info.get("elapsed_time", 0.0),
            exact_answer=info.get("most_likely_answer"),
            metadata={
                k: v
                for k, v in info.items()
                if k
                not in (
                    "success",
                    "all_solutions",
                    "residual_norm",
                    "precision_achieved",
                    "elapsed_time",
                    "most_likely_answer",
                )
            },
        )
