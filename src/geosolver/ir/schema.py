"""
IR (Intermediate Representation) スキーマ定義

LLMが生成するAIMO IR JSONの構造を定義。
Pydanticではなくdataclassを使用して依存を最小化。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Literal

TaskKind = Literal["solve", "optimize"]


@dataclass
class IRVariableSpec:
    """変数定義

    Either:
    - names: 明示的な変数名リスト
    - n: 変数の数（名前は x0, x1, ... と自動生成）

    両方指定された場合はnamesが優先。
    """

    names: Optional[List[str]] = None
    n: Optional[int] = None

    def resolved_names(self) -> List[str]:
        """解決された変数名リストを返す"""
        if self.names is not None:
            return list(self.names)
        if self.n is not None:
            return [f"x{i}" for i in range(self.n)]
        return []

    @property
    def count(self) -> int:
        """変数の数"""
        return len(self.resolved_names())


@dataclass
class IRConstruction:
    """構築ステップ

    name = expr の形式で幾何オブジェクトを構築。
    """

    name: str
    expr: str


@dataclass
class IRSpec:
    """AIMO IR スキーマ

    Attributes:
        task: 'solve' または 'optimize'
        variables: 変数定義
        m: 制約の数（optimizeの場合必須）
        bounds: 各変数の探索範囲 [(lo, hi), ...]
        v: 目標値ベクトル
        construction: 構築ステップのリスト
        constraints: 制約式のリスト
        guards: ガード条件のリスト
        answer_expr: 解答式
        answer_format: 解答形式指定
        objective_expr: 目的関数
    """

    task: TaskKind
    variables: IRVariableSpec
    
    m: Optional[int] = None

    bounds: Optional[List[Optional[Tuple[float, float]]]] = None
    v: Optional[List[float]] = None

    construction: List[IRConstruction] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    guards: List[str] = field(default_factory=list)
    
    answer_expr: Optional[str] = None
    # answer_format: Optional[Dict[str, Any]] = None # Deprecated
    post_process: Optional[str] = None # Pythonコードによる後処理
    
    objective_expr: Optional[str] = None
    maximize: bool = False
