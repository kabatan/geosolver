"""
Geometry Function Registry

単一登録点: @geometry_symbol デコレータで関数を登録すると、
自動的にレジストリに追加され、MultiFunctionWrapperでラップされる。

使用例:
    @geometry_symbol("Incenter", category="triangles")
    incenter = some_incenter_impl

    # NumPy高速版を追加
    incenter.set_numpy(fast_incenter)
"""

from typing import Callable, Dict, Any, Optional
import functools


# グローバルレジストリ
_REGISTRY: Dict[str, "MultiFunctionWrapper"] = {}
_METADATA: Dict[str, Dict[str, Any]] = {}


class MultiFunctionWrapper:
    """
    複数バックエンドをサポートする関数ラッパー

    使用例:
        distance(A, B)         # デフォルト（現在のruntime設定に従う）
        distance.fast(A, B)    # NumPy高速版
        distance.mp(A, B)      # mpmath高精度版
    """

    def __init__(self, name: str, sympy_func: Callable):
        self._name = name
        self._sympy = sympy_func
        self._numpy: Optional[Callable] = None
        self._mpmath: Optional[Callable] = None
        # functools.wraps相当
        self.__name__ = name
        self.__doc__ = sympy_func.__doc__

    def __call__(self, *args, **kwargs):
        """現在のランタイム設定に応じてディスパッチ"""
        from .runtime import get_current_runtime

        runtime = get_current_runtime()
        return runtime.dispatch(self, args, kwargs)

    def fast(self, *args, **kwargs):
        """NumPy高速バックエンドで実行"""
        if self._numpy is not None:
            return self._numpy(*args, **kwargs)
        return self._sympy(*args, **kwargs)

    def mp(self, *args, **kwargs):
        """mpmath高精度バックエンドで実行"""
        if self._mpmath is not None:
            return self._mpmath(*args, **kwargs)
        return self._sympy(*args, **kwargs)

    def sympy(self, *args, **kwargs):
        """SymPyバックエンドで実行（明示的）"""
        return self._sympy(*args, **kwargs)

    def set_numpy(self, func: Callable) -> "MultiFunctionWrapper":
        """NumPy版を設定"""
        self._numpy = func
        return self

    def set_mpmath(self, func: Callable) -> "MultiFunctionWrapper":
        """mpmath版を設定"""
        self._mpmath = func
        return self

    def __repr__(self) -> str:
        backends = ["sympy"]
        if self._numpy:
            backends.append("numpy")
        if self._mpmath:
            backends.append("mpmath")
        return f"<MultiFunctionWrapper '{self._name}' backends={backends}>"


def geometry_symbol(
    name: str = None, category: str = "general", auto_derive: bool = True
):
    """
    幾何シンボル登録デコレータ

    Args:
        name: 関数名（省略時は関数名を使用）
        category: カテゴリ（basic, triangles, circles, etc.）
        auto_derive: lambdifyで自動派生するか（将来用）

    Returns:
        MultiFunctionWrapper

    使用例:
        @geometry_symbol("Incenter", category="triangles")
        incenter = some_incenter_impl
    """

    return functools.partial(
        _geometry_symbol_decorator,
        name=name,
        category=category,
        auto_derive=auto_derive,
    )


def _geometry_symbol_decorator(
    func: Callable,
    *,
    name: Optional[str],
    category: str,
    auto_derive: bool,
) -> MultiFunctionWrapper:
    symbol_name = func.__name__ if name is None else name

    # ラッパーを作成
    wrapper = MultiFunctionWrapper(symbol_name, func)

    # functools.wraps相当の属性コピー
    wrapper.__doc__ = func.__doc__

    # レジストリに登録
    _REGISTRY[symbol_name] = wrapper
    _METADATA[symbol_name] = {
        "category": category,
        "doc": func.__doc__,
        "auto_derive": auto_derive,
    }

    return wrapper


def get_function(name: str) -> Optional[MultiFunctionWrapper]:
    """レジストリから関数を取得"""
    return _REGISTRY.get(name)


def list_functions(category: str = None) -> Dict[str, MultiFunctionWrapper]:
    """
    登録された関数を一覧

    Args:
        category: フィルタするカテゴリ（省略時は全て）

    Returns:
        名前→ラッパーの辞書
    """
    if category is None:
        return dict(_REGISTRY)
    return {
        k: v
        for k, v in _REGISTRY.items()
        if _METADATA.get(k, {}).get("category") == category
    }


def get_metadata(name: str) -> Optional[Dict[str, Any]]:
    """関数のメタデータを取得"""
    return _METADATA.get(name)


def clear_registry():
    """レジストリをクリア（テスト用）"""
    _REGISTRY.clear()
    _METADATA.clear()
