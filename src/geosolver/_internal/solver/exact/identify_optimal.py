"""Internal helper for exact identification of optimized objective values."""

from __future__ import annotations

from typing import Any

from geosolver._internal.observability.logging import emit_legacy_log as _emit_log
from geosolver._internal.solver.exact.strict_verify import (
    is_exact_match,
    normalize_expression,
)

try:
    import sympy as _sympy
except Exception:
    _sympy = None


def _sanitize_exact_string(s: str) -> str:
    out = str(s).strip().replace("?", "")
    if out.startswith("~="):
        return ""
    if out.startswith("≈"):
        return ""
    return out


def _evaluate_exact_expression(expr_str: str, precision: int):
    """Evaluate exact-expression string and return mpf value when possible."""
    if not expr_str or _sympy is None:
        return None

    from mpmath import mp

    old_dps = mp.dps
    normalized = normalize_expression(expr_str)

    try:
        sym_expr = _sympy.sympify(normalized)
        mp.dps = max(mp.dps, precision * 2 + 60)
        approx = sym_expr.evalf(mp.dps)
        try:
            return mp.mpf(approx)
        except Exception:
            # sympy.Float をHP安全な文字列経由で変換（str(evalf) は sympy.Float.str で精度保持）
            try:
                return mp.mpf(str(approx.evalf(mp.dps)))
            except Exception:
                return None
    except Exception:
        try:
            sym_expr = _sympy.nsimplify(normalized)
            mp.dps = max(mp.dps, precision * 2 + 60)
            approx = sym_expr.evalf(mp.dps)
            try:
                return mp.mpf(approx)
            except Exception:
                try:
                    return mp.mpf(str(approx.evalf(mp.dps)))
                except Exception:
                    return None
        except Exception:
            return None
    finally:
        mp.dps = old_dps


def identify_exact_optimal_value(value: float, precision: int, verbose: bool = True) -> dict[str, Any]:
    """Identify exact-form objective value from numeric optimized result."""
    try:
        from geosolver._internal.solver.exact import identify
        from mpmath import mp, mpf
    except ImportError:
        if verbose:
            _emit_log("\n[Phase 6] exact identification dependency is unavailable")
        return {}

    if verbose:
        _emit_log("\n[Phase 6] 厳密値同定...")

    required_precision = max(1, int(precision))

    old_dps = mp.dps
    mp.dps = required_precision + 20
    try:
        if not isinstance(value, mpf):
            # float / sympy.Float を文字列経由でmpf変換（boundary_float_to_mpfは呼び出し時にHP mode外か確認済み）
            from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
                BoundaryOrigin, boundary_float_to_mpf,
            )
            import math
            if isinstance(value, float):
                if math.isfinite(value):
                    value = boundary_float_to_mpf(value, origin=BoundaryOrigin.OBJECTIVE_VALUE)
                else:
                    return {}
            else:
                # sympy.Float 等の非mpf値は文字列経由で変換
                try:
                    value = mp.mpf(str(value))
                except Exception:
                    return {}

        exact = _sanitize_exact_string(identify(value, precision=required_precision))
        exact_numeric = None
        if exact and is_exact_match(exact, value, required_precision):
            exact_numeric = _evaluate_exact_expression(exact, required_precision)
        else:
            exact = None

        return {
            "exact_value": exact,
            "optimal_value_hp": value,
            "exact_value_numeric": exact_numeric,
        }
    finally:
        mp.dps = old_dps

