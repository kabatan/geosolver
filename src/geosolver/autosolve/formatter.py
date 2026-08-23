
"""
Answer Formatter Helper Functions
ポストプロセスで使用する、数値解のフォーマット用ヘルパー関数群。
"""

from fractions import Fraction
import math
from typing import Optional, Any
from geosolver._internal.solver.exact import identify

def to_fraction(value: Any, max_denominator: int = 10000) -> Fraction:
    """数値を分数（有理数）に近似する。

    - float/int/Fraction だけでなく、mpmath.mpf などの数値型も受け付ける
    - mpf は Fraction(value) が TypeError になるため、まず str(value) から解釈する
    """
    if isinstance(value, Fraction):
        return value.limit_denominator(max_denominator)
    if isinstance(value, int):
        return Fraction(value, 1)
    try:
        return Fraction(value).limit_denominator(max_denominator)
    except TypeError:
        # e.g. mpmath.mpf
        try:
            return Fraction(str(value)).limit_denominator(max_denominator)
        except Exception:
            return Fraction(float(value)).limit_denominator(max_denominator)

def to_sqrt_form(value: float) -> Optional[str]:
    """数値を a + b*sqrt(c) などの形式で復元し、文字列で返す"""
    res = identify(value)
    # identify returns the string representation or approx string
    if res.startswith("≈"):
        return None
    return res

# その他の便利関数
def is_close_int(value: float, tol: float = 1e-9) -> bool:
    """整数に近いか判定"""
    return abs(value - round(value)) < tol

def round_int(value: float) -> int:
    """整数に丸める"""
    return round(value)
