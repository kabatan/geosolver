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

import functools
from collections.abc import Callable

# グローバルレジストリ
_REGISTRY: dict[str, "MultiFunctionWrapper"] = {}
_CATEGORIES: dict[str, str] = {}


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
        self._numpy: Callable | None = None
        self._mpmath: Callable | None = None
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


def geometry_symbol(name: str = None, category: str = "general"):
    """
    幾何シンボル登録デコレータ

    Args:
        name: 関数名（省略時は関数名を使用）
        category: カテゴリ（basic, triangles, circles, etc.）

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
    )


def _geometry_symbol_decorator(
    func: Callable,
    *,
    name: str | None,
    category: str,
) -> MultiFunctionWrapper:
    symbol_name = func.__name__ if name is None else name

    # ラッパーを作成
    wrapper = MultiFunctionWrapper(symbol_name, func)

    # functools.wraps相当の属性コピー
    wrapper.__doc__ = func.__doc__

    # レジストリに登録
    _REGISTRY[symbol_name] = wrapper
    _CATEGORIES[symbol_name] = category

    return wrapper


def get_function(name: str) -> MultiFunctionWrapper | None:
    """レジストリから関数を取得"""
    return _REGISTRY.get(name)


def list_functions(category: str = None) -> dict[str, MultiFunctionWrapper]:
    """
    登録された関数を一覧

    Args:
        category: フィルタするカテゴリ（省略時は全て）

    Returns:
        名前→ラッパーの辞書
    """
    if category is None:
        return dict(_REGISTRY)
    return {k: v for k, v in _REGISTRY.items() if _CATEGORIES.get(k) == category}
