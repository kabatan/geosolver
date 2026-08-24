"""
安全機構ユーティリティ

solver/optimizer での入力除外、Assume条件による制約を提供。

使用例:
    from geosolver.geometry.safety import Assume, AssumeGt, AssumeNe

    AssumeGt(Distance(A, B), Distance(A, C))  # AB > AC を要求
    AssumeNe(x, 0)  # x != 0 を要求
"""

from typing import Optional, Any, Tuple
from contextlib import contextmanager
import contextvars
from geosolver.geometry.safety.numeric import (
    is_acute_triangle as _is_acute_triangle_impl,
    normalize_interval as _normalize_interval_impl,
    to_float as _to_float,
    to_point_xy as _to_point_xy_impl,
)


class AssumptionError(Exception):
    """Assume(...) に違反した（入力を除外した）"""

    pass


# Assume の有効/無効フラグ
_ASSUME_ENABLED: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_ASSUME_ENABLED", default=True
)

# Assume の動作モード:
# - 'raise': 既定。失敗で AssumptionError
# - 'flag' : 例外は投げず、違反を violations に記録
# - 'ignore': 例外もフラグも無し
_ASSUME_MODE: contextvars.ContextVar[str] = contextvars.ContextVar("_ASSUME_MODE", default="raise")
_ASSUME_VIOLATIONS: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar(
    "_ASSUME_VIOLATIONS", default=None
)


def _get_assume_tolerance():
    """動的許容値を計算（現在のmpmath精度に基づく）"""
    try:
        import mpmath

        # Use 10^(-dps + 5) as tolerance (5 digits of margin)
        dps = mpmath.mp.dps
        return 10 ** (-dps + 5)
    except:
        pass
    return 1e-9  # Fallback for backward compatibility


def _get_assume_abs_tolerance():
    """動的絶対許容値を計算"""
    try:
        import mpmath

        dps = mpmath.mp.dps
        return 10 ** (-dps + 2)
    except:
        pass
    return 1e-12  # Fallback


# 既定のトレランス（許容誤差）- 動的計算に変更
# _ASSUME_REL_FLOOR = 1e-9  # 削除: 動的許容値を使用
# _ASSUME_ABS_FLOOR = 1e-12  # 削除: 動的許容値を使用


@contextmanager
def assume_mode(mode: str = "raise", *, violations: Optional[list] = None):
    """Assume 系の失敗時の挙動を切り替える。

    - mode='raise': 従来通り例外
    - mode='flag' : violations にメッセージを追加して継続
    - mode='ignore': 何もせず継続
    """
    token_mode = _ASSUME_MODE.set(str(mode))
    token_v = _ASSUME_VIOLATIONS.set(violations)
    try:
        yield
    finally:
        _ASSUME_MODE.reset(token_mode)
        _ASSUME_VIOLATIONS.reset(token_v)


@contextmanager
def assume_enabled(enabled: bool):
    """Assume 系のチェックを一時的に有効/無効化する。"""
    token = _ASSUME_ENABLED.set(bool(enabled))
    try:
        yield
    finally:
        _ASSUME_ENABLED.reset(token)


# Module-level storage for custom tolerance overrides (if set manually)
_CUSTOM_REL_FLOOR: Optional[float] = None
_CUSTOM_ABS_FLOOR: Optional[float] = None


def set_assume_tolerance(
    rel_floor: Optional[float] = None, abs_floor: Optional[float] = None
) -> None:
    """Assume(...) の既定トレランスを更新する。"""
    global _CUSTOM_REL_FLOOR, _CUSTOM_ABS_FLOOR
    if rel_floor is not None:
        _CUSTOM_REL_FLOOR = float(rel_floor)
    if abs_floor is not None:
        _CUSTOM_ABS_FLOOR = float(abs_floor)


def _get_tolerance(scale: float, rel_floor: Optional[float], abs_floor: Optional[float]) -> float:
    """スケールに応じた許容誤差を計算（動的許容値対応）"""
    # Use provided values, or custom overrides, or dynamic defaults
    if rel_floor is not None:
        rf = float(rel_floor)
    elif _CUSTOM_REL_FLOOR is not None:
        rf = _CUSTOM_REL_FLOOR
    else:
        rf = _get_assume_tolerance()

    if abs_floor is not None:
        af = float(abs_floor)
    elif _CUSTOM_ABS_FLOOR is not None:
        af = _CUSTOM_ABS_FLOOR
    else:
        af = _get_assume_abs_tolerance()

    return max(af, rf * max(1.0, abs(scale)))


def _to_point_xy(point: Any) -> Tuple[float, float]:
    """点オブジェクトを (x, y) のfloat座標に変換する。"""
    return _to_point_xy_impl(point, to_float_fn=_to_float)


def _is_acute_triangle(
    A: Any,
    B: Any,
    C: Any,
    rel_floor: Optional[float],
    abs_floor: Optional[float],
) -> bool:
    """3点が鋭角三角形を成すか判定する。"""
    return _is_acute_triangle_impl(
        A,
        B,
        C,
        rel_floor,
        abs_floor,
        to_point_xy_fn=_to_point_xy,
        get_tolerance_fn=_get_tolerance,
    )


def _handle_failure(message: str) -> None:
    """Assume失敗時の処理"""
    mode = _ASSUME_MODE.get()

    if mode == "ignore":
        return

    if mode == "flag":
        violations = _ASSUME_VIOLATIONS.get()
        if isinstance(violations, list):
            violations.append(message)
        return

    # mode == 'raise'
    raise AssumptionError(message)


def _assume_compare(
    lhs: Any,
    rhs: Any,
    op: str,
    message: Optional[str] = None,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> None:
    """lhs (op) rhs を許容誤差付きで判定"""
    if not _ASSUME_ENABLED.get():
        return

    try:
        lhs_num = _to_float(lhs)
        rhs_num = _to_float(rhs)
    except Exception:
        _handle_failure(message or f"Assume({op}) undecidable")
        return

    scale = max(abs(lhs_num), abs(rhs_num), 1.0)
    tol = _get_tolerance(scale, rel_floor, abs_floor)

    if op == "!=":
        ok = abs(lhs_num - rhs_num) > tol
    elif op == "==":
        ok = abs(lhs_num - rhs_num) <= tol
    elif op == "<":
        ok = lhs_num < (rhs_num - tol)
    elif op == "<=":
        ok = lhs_num <= (rhs_num + tol)
    elif op == ">":
        ok = lhs_num > (rhs_num + tol)
    elif op == ">=":
        ok = lhs_num >= (rhs_num - tol)
    else:
        _handle_failure(message or f"Assume({op}) unsupported")
        return

    if not ok:
        _handle_failure(message or f"Assume({lhs} {op} {rhs}) failed")


def _normalize_interval(bounds: Any) -> Tuple[Optional[float], Optional[float]]:
    """Bound/Assume 用の範囲指定を標準化する。"""
    return _normalize_interval_impl(bounds, to_float_fn=_to_float)


def Bound(
    value: Any,
    bounds: Any,
    message: Optional[str] = None,
    *,
    inclusive: bool = True,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> Any:
    """
    Bound(x, (lo, hi)) - x を指定範囲内にあると仮定するガード。
    inclusive=True なら閉区間、False なら開区間。
    """
    if not _ASSUME_ENABLED.get():
        return value

    try:
        lo, hi = _normalize_interval(bounds)
        v = _to_float(value)
    except Exception:
        _handle_failure(message or "Bound undecidable")
        return value

    if lo is None and hi is None:
        _handle_failure(message or "Bound requires finite range")
        return value
    if lo is not None and hi is not None and lo >= hi:
        _handle_failure(message or "Bound invalid interval (lo >= hi)")
        return value

    scale = max(abs(v), abs(lo) if lo is not None else 1.0, abs(hi) if hi is not None else 1.0, 1.0)
    tol = _get_tolerance(scale, rel_floor, abs_floor)

    lower_ok = True if lo is None else (v >= lo - tol if inclusive else v > lo + tol)
    upper_ok = True if hi is None else (v <= hi + tol if inclusive else v < hi - tol)
    if not (lower_ok and upper_ok):
        _handle_failure(message or f"Bound violation: {v} not in [{lo}, {hi}]")
    return value


def AssumeNe(
    lhs: Any,
    rhs: Any,
    message: Optional[str] = None,
    *,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> None:
    """Assume(lhs != rhs) - 不等を要求（ほぼ等しいも除外）"""
    _assume_compare(lhs, rhs, "!=", message, rel_floor, abs_floor)


def AssumeEq(
    lhs: Any,
    rhs: Any,
    message: Optional[str] = None,
    *,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> None:
    """Assume(lhs == rhs) - 等を要求（ほぼ等しいを許容）"""
    _assume_compare(lhs, rhs, "==", message, rel_floor, abs_floor)


def AssumeLt(
    lhs: Any,
    rhs: Any,
    message: Optional[str] = None,
    *,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> None:
    """Assume(lhs < rhs) - より小を要求"""
    _assume_compare(lhs, rhs, "<", message, rel_floor, abs_floor)


def AssumeLe(
    lhs: Any,
    rhs: Any,
    message: Optional[str] = None,
    *,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> None:
    """Assume(lhs <= rhs) - 以下を要求"""
    _assume_compare(lhs, rhs, "<=", message, rel_floor, abs_floor)


def AssumeGt(
    lhs: Any,
    rhs: Any,
    message: Optional[str] = None,
    *,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> None:
    """Assume(lhs > rhs) - より大を要求"""
    _assume_compare(lhs, rhs, ">", message, rel_floor, abs_floor)


def AssumeGe(
    lhs: Any,
    rhs: Any,
    message: Optional[str] = None,
    *,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> None:
    """Assume(lhs >= rhs) - 以上を要求"""
    _assume_compare(lhs, rhs, ">=", message, rel_floor, abs_floor)


def Assume(
    condition: Any,
    message: Optional[str] = None,
    *,
    rel_floor: Optional[float] = None,
    abs_floor: Optional[float] = None,
) -> None:
    """条件が満たされない場合に AssumptionError を投げて入力を除外する。

    使用例:
        Assume(Distance(A,B) != Distance(A,C))
        Assume(x > 0)

    NOTE:
    - sympy の Relational（==, !=, <, <=, ...）に対応
    - 数値を evalf してから許容誤差付きで判定
    """
    if not _ASSUME_ENABLED.get():
        return

    # Python bool の場合
    try:
        if isinstance(condition, bool):
            if not condition:
                _handle_failure(message or "Assume(condition) failed")
            return
    except Exception:
        pass

    # sympy の Relational を処理
    try:
        from sympy.core.relational import Relational

        if isinstance(condition, Relational):
            op = getattr(condition, "rel_op", None)
            if op in ("!=", "==", "<", "<=", ">", ">="):
                _assume_compare(condition.lhs, condition.rhs, op, message, rel_floor, abs_floor)
                return
    except ImportError:
        pass
    except Exception:
        pass

    # sympy の BooleanTrue/False
    try:
        from sympy.logic.boolalg import BooleanTrue, BooleanFalse

        if isinstance(condition, BooleanTrue):
            return
        if isinstance(condition, BooleanFalse):
            _handle_failure(message or "Assume(condition) failed")
            return
    except ImportError:
        pass
    except Exception:
        pass

    # 最後の手段: bool変換
    try:
        if not bool(condition):
            _handle_failure(message or "Assume(condition) failed")
        return
    except Exception:
        _handle_failure(message or "Assume(condition) undecidable")


from geosolver.geometry.safety.assumptions import (
    AssumeAcute,
    AssumeConvex,
    AssumeNoSelfIntersecting,
    AssumeObtuse,
    AssumeOrder,
    AssumeRight,
)


# エクスポート
__all__ = [
    "AssumptionError",
    "assume_mode",
    "assume_enabled",
    "set_assume_tolerance",
    "Bound",
    "Assume",
    "AssumeEq",
    "AssumeNe",
    "AssumeLt",
    "AssumeLe",
    "AssumeGt",
    "AssumeGe",
    "AssumeAcute",
    "AssumeRight",
    "AssumeObtuse",
    "AssumeConvex",
    "AssumeNoSelfIntersecting",
    "AssumeOrder",
]
