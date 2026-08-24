"""
Geometry Runtime

バックエンド/精度のスコープ管理。
グローバル状態ではなく contextvars を使用して並列/再入で壊れない設計。

使用例:
    from geosolver.geometry.runtime import use_runtime, BackendType

    # スコープ内でバックエンドを切り替え
    with use_runtime(backend=BackendType.NUMPY, precision=15):
        result = distance(A, B)

    # 高精度計算
    with use_runtime(backend=BackendType.MPMATH, precision=100):
        result = distance.mp(A, B)
"""

from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum, auto
from dataclasses import dataclass
from typing import Any, Tuple, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import MultiFunctionWrapper


class BackendType(Enum):
    """バックエンドの種類"""

    SYMPY = auto()
    """SymPy: 厳密計算、式の簡約、代数操作"""

    NUMPY = auto()
    """NumPy: float64高速計算、SIMD最適化"""

    MPMATH = auto()
    """mpmath: 任意精度数値計算"""


@dataclass
class GeometryRuntime:
    """
    幾何計算のランタイム設定

    Attributes:
        backend: 使用するバックエンド
        precision: 精度（桁数）
        raise_on_degenerate: 退化図形で例外を投げるか
    """

    backend: BackendType = BackendType.SYMPY
    precision: int = 15
    raise_on_degenerate: bool = False

    def dispatch(
        self, wrapper: "MultiFunctionWrapper", args: Tuple, kwargs: Dict[str, Any]
    ) -> Any:
        """
        バックエンドに応じて関数をディスパッチ

        Args:
            wrapper: MultiFunctionWrapper
            args: 位置引数
            kwargs: キーワード引数

        Returns:
            関数の実行結果
        """
        if self.backend == BackendType.NUMPY and wrapper._numpy is not None:
            try:
                return wrapper._numpy(*args, **kwargs)
            except Exception:
                # フォールバック
                return wrapper._sympy(*args, **kwargs)
        elif self.backend == BackendType.MPMATH and wrapper._mpmath is not None:
            try:
                return wrapper._mpmath(*args, **kwargs)
            except Exception:
                return wrapper._sympy(*args, **kwargs)
        return wrapper._sympy(*args, **kwargs)


# コンテキスト変数（スレッドセーフ、asyncセーフ）
_runtime_var: ContextVar[GeometryRuntime] = ContextVar(
    "geometry_runtime", default=GeometryRuntime()
)


def get_current_runtime() -> GeometryRuntime:
    """現在のランタイム設定を取得"""
    return _runtime_var.get()


def get_precision() -> int:
    """現在の精度設定を取得"""
    return get_current_runtime().precision


def get_backend() -> BackendType:
    """現在のバックエンドを取得"""
    return get_current_runtime().backend


@contextmanager
def use_runtime(
    backend: BackendType = None,
    precision: int = None,
    raise_on_degenerate: bool = None,
):
    """
    ランタイム設定をスコープ内で変更

    Args:
        backend: バックエンド（省略時は現在の値を維持）
        precision: 精度（省略時は現在の値を維持）
        raise_on_degenerate: 退化図形で例外を投げるか

    Yields:
        新しいGeometryRuntime

    使用例:
        with use_runtime(backend=BackendType.NUMPY):
            # このスコープ内はNumPyバックエンド
            result = distance(A, B)
        # スコープ外では元の設定に戻る
    """
    current = get_current_runtime()
    new = GeometryRuntime(
        backend=backend if backend is not None else current.backend,
        precision=precision if precision is not None else current.precision,
        raise_on_degenerate=(
            raise_on_degenerate
            if raise_on_degenerate is not None
            else current.raise_on_degenerate
        ),
    )
    token = _runtime_var.set(new)
    try:
        yield new
    finally:
        _runtime_var.reset(token)


@contextmanager
def fast_mode():
    """NumPyバックエンドに切り替えるショートカット"""
    with use_runtime(backend=BackendType.NUMPY) as runtime:
        yield runtime


@contextmanager
def high_precision_geometry_mode(precision: int = 100):
    """mpmath高精度バックエンドへ切り替えるショートカット。

    Note:
        INV-12 対応: WP6_5モンキーパッチが含まれる HP モードコンテキストマネージャ
        (``geosolver.engine.standard.precision.type_guards.high_precision_mode``)
        とは別物。このコンテキストマネージャは geometry バックエンドの切り替え専用。
    """
    with use_runtime(backend=BackendType.MPMATH, precision=precision) as runtime:
        yield runtime


@contextmanager
def high_precision_mode(precision: int = 100):
    """後方互換エイリアス。high_precision_geometry_mode を使用してください。

    .. deprecated::
        ``high_precision_geometry_mode(precision)`` を使用してください。
        このエイリアスは将来のバージョンで削除されます。
        WP6_5 動的ガード付きの HP mode コンテキストマネージャ
        (``geosolver.engine.standard.precision.type_guards.high_precision_mode``)
        とは別物です（INV-12）。
    """
    import warnings
    warnings.warn(
        "geosolver.geometry.runtime.high_precision_mode は非推奨です。"
        " high_precision_geometry_mode を使用してください。"
        " WP6_5動的ガード付きのHPモードとは別物です（INV-12）。",
        DeprecationWarning,
        stacklevel=2,
    )
    with high_precision_geometry_mode(precision=precision) as runtime:
        yield runtime
