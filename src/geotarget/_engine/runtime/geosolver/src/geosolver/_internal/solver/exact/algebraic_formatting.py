"""Formatting helpers for exact algebraic identification."""

from __future__ import annotations

import re
from typing import Any, List, Optional


def poly_to_string(coeffs: List[int]) -> str:
    degree = len(coeffs) - 1
    terms = []

    for i, c in enumerate(coeffs):
        if c == 0:
            continue

        exp = degree - i

        if exp == 0:
            terms.append(f"{c:+d}" if terms else str(c))
        elif exp == 1:
            if c == 1:
                terms.append("+x" if terms else "x")
            elif c == -1:
                terms.append("-x")
            else:
                terms.append(f"{c:+d}x" if terms else f"{c}x")
        else:
            if c == 1:
                terms.append(f"+x^{exp}" if terms else f"x^{exp}")
            elif c == -1:
                terms.append(f"-x^{exp}")
            else:
                terms.append(f"{c:+d}x^{exp}" if terms else f"{c}x^{exp}")

    return "".join(terms) if terms else "0"


def _is_sqrt_expr(expr: Any) -> bool:
    try:
        from sympy import Rational, sqrt

        if expr.func == sqrt:
            return True
        if expr.is_Pow and len(expr.args) == 2:
            base, exp = expr.args
            return exp == Rational(1, 2)
    except Exception:
        return False
    return False


def format_sqrt_like(expr: Any) -> Optional[str]:
    try:
        from sympy import simplify

        if expr.is_Mul:
            sqrt_factor = None
            for arg in expr.args:
                if _is_sqrt_expr(arg):
                    sqrt_factor = arg
                    break
            if sqrt_factor is not None and sqrt_factor.args and sqrt_factor.args[0].is_Rational:
                try:
                    coeff = simplify(expr / sqrt_factor)
                except Exception:
                    coeff = None
                if coeff is not None and coeff.is_Rational:
                    denom = int(coeff.q)
                    if abs(denom) > 10:
                        rad = simplify(sqrt_factor.args[0] * (coeff**2))
                        return f"sqrt({rad})".replace("**", "^").replace("*", "")
                    coeff_str = str(coeff)
                    if coeff == 1:
                        return f"sqrt({sqrt_factor.args[0]})"
                    if coeff == -1:
                        return f"-sqrt({sqrt_factor.args[0]})"
                    return f"{coeff_str}sqrt({sqrt_factor.args[0]})"
    except Exception:
        return None
    return None


def normalize_expr_string(expr: str) -> str:
    s = re.sub(r"\s+", "", str(expr))
    s = s.replace("^", "**")
    s = re.sub(r"(?<=\d)(?=[A-Za-z(])", "*", s)
    s = re.sub(r"(?<=\))(?=[A-Za-z0-9(])", "*", s)
    s = s.replace("+-", "-").replace("-+", "-").replace("++", "+")
    return s


def snap_sqrt_of_near_square(s: str, precision: int) -> Optional[str]:
    try:
        from sympy import sympify

        m = re.fullmatch(r"sqrt\((.+)\)", s.strip())
        if not m:
            return None
        inner = normalize_expr_string(m.group(1))
        sympify(inner)
        return f"sqrt({inner})"
    except Exception:
        return None


def simplify_expression(root: Any, coeffs: List[int]) -> str:
    try:
        from math import isqrt

        from sympy import Rational, nsimplify, simplify, sqrt

        simplified = nsimplify(root, rational=True)
        simplified = simplify(simplified)

        try:
            if simplified.func == sqrt and simplified.args and simplified.args[0].is_Rational:
                rad = simplified.args[0]
                p, q = int(rad.p), int(rad.q)
                sp, sq = isqrt(abs(p)), isqrt(abs(q))
                if sp * sp == abs(p) and sq * sq == abs(q):
                    sign = -1 if p < 0 else 1
                    simplified = Rational(sign * sp, sq)
        except Exception:
            pass

        fmt = format_sqrt_like(simplified)
        if fmt is not None:
            return fmt.replace("**", "^").replace("*", "")

        s = str(simplified)
        return s.replace("**", "^").replace("*", "")
    except Exception:
        return str(root)