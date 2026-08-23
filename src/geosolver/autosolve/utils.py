"""
Auto Solver Utilities

解答の整形や変換ユーティリティ。
aimo_ir.py からの移植。
"""

from typing import Any, Optional, Tuple, Union
import re

try:
    import sympy
except ImportError:
    sympy = None

# ---------------------------------------------------------------------------
# Answer Coercion
# ---------------------------------------------------------------------------

_RADICAND_REQUEST_PATTERNS = (
    # English
    re.compile(r"in the form\s*(?:\\sqrt\(a\)|sqrt\(a\)|sqrt\s*a)", re.IGNORECASE),
    re.compile(r"expressed\s+as\s*(?:\\sqrt\(a\)|sqrt\(a\)|sqrt\s*a)", re.IGNORECASE),
    # Japanese
    re.compile(r"sqrt\(a\)|√\s*a", re.IGNORECASE),
)

_ASK_FOR_A_PATTERNS = (
    re.compile(r"\bfind\s+a\b", re.IGNORECASE),
    re.compile(r"\bdetermine\s+a\b", re.IGNORECASE),
    re.compile(r"a\s*を\s*求", re.IGNORECASE),
    re.compile(r"a\s*を\s*答", re.IGNORECASE),
)

def _problem_asks_for_radicand(problem: str) -> bool:
    if not isinstance(problem, str) or not problem.strip():
        return False
    for p in _RADICAND_REQUEST_PATTERNS:
        if p.search(problem):
            for q in _ASK_FOR_A_PATTERNS:
                if q.search(problem):
                    return True
            if "a" in problem:
                return True
    return False

def _extract_sqrt_radicand(expr: Any) -> Optional[int]:
    if sympy is None:
        return None
    try:
        if not isinstance(expr, sympy.Basic):
            expr = sympy.sympify(str(expr).strip())
    except Exception:
        return None

    try:
        expr = sympy.simplify(expr)
    except Exception:
        pass

    # Accept sqrt(n) or -sqrt(n)
    try:
        coeff, rest = expr.as_coeff_Mul()
    except Exception:
        coeff, rest = (None, expr)

    if coeff in (None, 1, -1):
        target = rest
    else:
        target = expr

    # sqrt(n)
    try:
        if getattr(target, "func", None) == sympy.sqrt and len(getattr(target, "args", ())) == 1:
            rad = target.args[0]
            if rad.is_integer is True:
                return int(rad)
    except Exception:
        pass

    # Pow(n, 1/2)
    try:
        if getattr(target, "is_Pow", False) and getattr(target, "exp", None) == sympy.Rational(1, 2):
            rad = target.base
            if rad.is_integer is True:
                return int(rad)
    except Exception:
        pass

    return None

def int_from_exact(value: Any) -> Optional[int]:
    """数値を整数に変換（誤差許容）"""
    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)

    # float-ish
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return int(round(value))
        return None

    # sympy objects
    if sympy is not None:
        try:
            if isinstance(value, sympy.Integer):
                return int(value)
            if isinstance(value, sympy.Rational):
                if value.q == 1:
                    return int(value)
                return None
            if isinstance(value, sympy.Basic):
                if value.is_integer is True:
                    return int(value)
        except Exception:
            pass

    # string exact expression
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if re.fullmatch(r"[+-]?\d+", s):
            try:
                return int(s)
            except Exception:
                return None
        if sympy is None:
            return None
        try:
            expr = sympy.sympify(s)
            if expr.is_integer is True:
                return int(expr)
            approx = float(expr.evalf())
            if abs(approx - round(approx)) < 1e-9:
                return int(round(approx))
        except Exception:
            return None

    return None

def coerce_int_answer(problem: str, value: Any) -> Optional[int]:
    """解答を整数に変換。問題文にsqrt(a)形式の要求があれば考慮する。"""
    v = int_from_exact(value)
    if v is not None:
        return int(v)

    if _problem_asks_for_radicand(problem):
        rad = _extract_sqrt_radicand(value)
        if rad is not None:
            return int(rad)

    return None
