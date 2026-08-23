"""
代数的数の厳密値復元モジュール

近似値から最小多項式を予測し、代数的数の厳密値を計算する。
"""
from typing import Optional, Tuple, List, Union, Any
import re
from mpmath import mp, mpf, nstr, polyroots, fabs
from geosolver._internal.observability.logging import emit_legacy_log as _emit_log
from .algebraic_formatting import (
    format_sqrt_like as _format_sqrt_like,
    normalize_expr_string as _normalize_expr_string,
    poly_to_string as _poly_to_string,
    simplify_expression as _simplify_expression,
    snap_sqrt_of_near_square as _snap_sqrt_of_near_square,
)
from .polynomial_search import (
    _to_mpf_sanitized,
    find_minimal_polynomial,
)
from .strict_verify import is_exact_match

def exact_algebraic(
    r: Union[float, Any],
    precision: int = 15,
    max_degree: int = 8,
    verbose: bool = False,
    *,
    max_coeff: int = 10**15,
    max_steps: int = 10000,
) -> Tuple[Optional[any], Optional[List[int]], Optional[str]]:
    """
    近似値から代数的数の厳密値を計算する
    
    Args:
        r: 代数的数の近似値
        precision: rの精度（小数点以下の桁数）
        max_degree: 探索する多項式の最大次数
        verbose: デバッグ出力
    
    Returns:
        (厳密値, 最小多項式係数, 説明文字列) のタプル
        見つからない場合は (None, None, None)
    
    Example:
        >>> r = 1.7320508075688772  # sqrt(3)
        >>> exact, poly, desc = exact_algebraic(r, precision=15)
        >>> _emit_log(desc)  # 'sqrt(3)'
        >>> _emit_log(poly)  # [1, 0, -3]
    """
    mp.dps = max(precision + 30, 50)
    r = _to_mpf_sanitized(r)
    
    if verbose:
        _emit_log(f"入力値: {nstr(r, min(precision, 30))}")
        _emit_log(f"精度: {precision}桁")
    
    # 最小多項式を探す
    coeffs = find_minimal_polynomial(r, precision, max_degree, max_coeff=max_coeff, max_steps=max_steps, verbose=verbose)
    
    if coeffs is None:
        if verbose:
            _emit_log("最小多項式が見つかりませんでした")
        return None, None, None
    
    if verbose:
        _emit_log(f"最小多項式: {_poly_to_string(coeffs)}")
    
    # sympyで厳密値を計算
    try:
        from sympy import Poly, symbols, real_roots, nroots, Abs, N as sympy_N
        from sympy import sqrt as sympy_sqrt, Rational, nsimplify
        
        x = symbols('x')
        poly = Poly(coeffs, x)
        
        # 実根を求める
        roots = real_roots(poly)
        
        if not roots:
            # 実根がない場合は複素根を試す
            roots = poly.all_roots()
        
        # rに最も近い根を選択
        best_root = None
        best_diff = mpf('inf')
        
        for root in roots:
            try:
                root_val = complex(sympy_N(root, precision + 10))
                if abs(root_val.imag) > 1e-10:
                    continue  # 複素数は除外
                
                diff = fabs(_to_mpf_sanitized(root_val.real) - r)
                if diff < best_diff:
                    best_diff = diff
                    best_root = root
            except:
                continue
        
        if best_root is not None:
            desc = _simplify_expression(best_root, coeffs)
            if is_exact_match(desc, r, precision):
                if verbose:
                    _emit_log(f"厳密値: {desc}")
                return best_root, coeffs, desc
            if verbose:
                _emit_log("厳密値候補が要求精度一致を満たしませんでした")
        
    except ImportError:
        if verbose:
            _emit_log("sympyがないため、厳密値は計算できません")
    except Exception as e:
        if verbose:
            _emit_log(f"sympy処理エラー: {e}")
    
    # sympyが使えない場合はmpmathで高精度根を返す
    mp.dps = precision + 50
    roots = polyroots(coeffs)
    
    best_root = None
    best_diff = mpf('inf')
    
    for root in roots:
        if fabs(root.imag) > mpf(10) ** (-precision // 2):
            continue
        diff = fabs(root.real - r)
        if diff < best_diff:
            best_diff = diff
            best_root = root.real
    
    if best_root is not None and fabs(best_root - r) <= mp.power(mpf(10), -max(1, int(precision))):
        # 数値近接のみでの記号表現は厳密値文字列として返さない
        return None, None, None

    return None, None, None


# ============================================================================
# 便利関数
# ============================================================================

def identify(
    r: Union[float, Any],
    precision: int = 15,
    max_degree: int = 8,
    *,
    max_coeff: int = 10**15,
    max_steps: int = 10000,
) -> str:
    """Identify exact symbolic form only when required precision is satisfied."""
    try:
        rr = _to_mpf_sanitized(r)
    except Exception:
        return f"≈ {r}"

    try:
        _, _, desc = exact_algebraic(
            rr,
            precision=precision,
            max_degree=max_degree,
            max_coeff=max_coeff,
            max_steps=max_steps,
        )
        if desc is not None and is_exact_match(desc, rr, precision):
            try:
                from sympy import sympify

                normalized = _normalize_expr_string(desc)
                fmt = _format_sqrt_like(sympify(normalized))
                if fmt is not None and is_exact_match(fmt, rr, precision):
                    return fmt
            except Exception:
                pass
            return desc
    except Exception:
        pass

    return f"≈ {nstr(rr, min(int(precision), 50))}"

def algebraic_sqrt(n: int) -> Tuple[any, List[int], str]:
    """√n の厳密値と最小多項式を返す（テスト用）"""
    from mpmath import sqrt as mp_sqrt
    mp.dps = 50
    r = mp_sqrt(n)
    return exact_algebraic(r, precision=40, max_degree=2)

