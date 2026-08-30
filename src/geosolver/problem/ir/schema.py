"""
IR (Intermediate Representation) スキーマ定義

LLMが生成するAIMO IR JSONの構造を定義。
Pydanticではなくdataclassを使用して依存を最小化。
"""

from dataclasses import dataclass, field
from typing import Literal

TaskKind = Literal["solve", "optimize"]


@dataclass
class IRVariableSpec:
    """変数定義

    Either:
    - names: 明示的な変数名リスト
    - n: 変数の数（名前は x0, x1, ... と自動生成）

    両方指定された場合はnamesが優先。
    """

    names: list[str] | None = None
    n: int | None = None

    def resolved_names(self) -> list[str]:
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

    m: int | None = None

    bounds: list[tuple[float, float] | None] | None = None
    v: list[float] | None = None

    construction: list[IRConstruction] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    guards: list[str] = field(default_factory=list)

    answer_expr: str | None = None
    # answer_format: Optional[Dict[str, Any]] = None # Deprecated
    post_process: str | None = None  # Pythonコードによる後処理

    objective_expr: str | None = None
    maximize: bool = False
