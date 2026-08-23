"""
厳密値識別モジュール

archive/geosolver.py の _identify_exact_answers 関数を移植。
ans関数を各解に適用し、代数的数を識別する。
"""

from typing import Callable, List, Dict, Optional, Any
from geosolver.utils import to_mpf_sanitized
from geosolver._internal.observability.logging import emit_legacy_log as _emit_log
from geosolver._internal.config.environment.skip_exact_identification import (
    get_skip_exact_identification,
)
from geosolver._internal.solver.exact.strict_verify import is_exact_match

try:
    from mpmath import mp, mpf
except ImportError:
    mp = None
    mpf = float


def _sanitize_exact_string(value: Any) -> str:
    if not isinstance(value, str):
        value = str(value)
    out = value.replace("≈", "~=").replace("→", "->").strip()
    if out.startswith("~="):
        return ""
    return out


def _to_mpf_sanitized_local(val: Any, *, dps: int) -> Any:
    return to_mpf_sanitized(val, dps=dps)

def identify(value: Any, precision: int = 50) -> str:
    """
    代数的数を識別する (sympy.nsimplifyを使用)

    Args:
        value: 識別対象の値 (float, mpf, or string)
        precision: 許容誤差の計算に使用する精度推定
    """
    try:
        from geosolver._internal.solver.exact.algebraic_compat import (
            identify as _identify_algebraic,
        )

        return _identify_algebraic(value, precision=int(precision), max_degree=8)
    except Exception:
        return str(value)


def exact_algebraic(value: Any, precision: int = 50, max_degree: int = 8, **kwargs):
    """Compatibility shim for post_process code expecting exact_algebraic."""
    try:
        from geosolver._internal.solver.exact import exact_algebraic as _exact_algebraic
    except Exception as exc:
        raise ImportError("exact_algebraic is unavailable") from exc
    return _exact_algebraic(value, precision=precision, max_degree=max_degree, **kwargs)


def identify_exact_answers(
    ans: Callable,
    all_solutions: List,
    precision: int,
    verbose: bool = True,
    residuals: Optional[List] = None,
) -> Dict:
    """Identify exact answers with strict precision verification."""
    if get_skip_exact_identification():
        if verbose:
            _emit_log("\n[Phase 8] 厳密値識別をスキップ（検証モード）")
        return {"exact_answers": [], "most_likely_answer": None, "answer_counts": {}}

    if mp is None:
        if verbose:
            _emit_log("\n[Phase 8] 警告: mpmathがインストールされていません")
        return {}

    required_precision = max(1, int(precision))
    if verbose:
        _emit_log("\n[Phase 8] 厳密値識別...")
        _emit_log(f"  識別精度: {required_precision}桁（要求精度）")

    old_dps = mp.dps
    mp.dps = required_precision + 20

    try:
        from geosolver.geometry.mp.mp_api import use_mpmath_api
        use_mpmath = True
    except ImportError:
        use_mpmath = False

    exact_answers: List[str] = []
    answer_values: List[Any] = []

    try:
        for i, sol in enumerate(all_solutions):
            try:
                mp.dps = required_precision + 20
                mp_sol = [
                    _to_mpf_sanitized_local(
                        xi,
                        dps=int(getattr(mp, "dps", required_precision + 20)),
                    )
                    for xi in sol
                ]

                if use_mpmath:
                    globals_dict = ans.__globals__
                    with use_mpmath_api(globals_dict, required_precision):
                        ans_value = ans(mp_sol)
                else:
                    ans_value = ans(mp_sol)

                ans_value = _to_mpf_sanitized_local(
                    ans_value,
                    dps=int(getattr(mp, "dps", required_precision + 20)),
                )
                answer_values.append(ans_value)

                candidate = _sanitize_exact_string(identify(ans_value, precision=required_precision))
                if candidate and is_exact_match(candidate, ans_value, required_precision):
                    exact = candidate
                else:
                    exact = "不明"

                exact_answers.append(exact)
                if verbose:
                    try:
                        _emit_log(f"  解#{i + 1}: {ans_value} -> {exact}")
                    except Exception:
                        _emit_log(f"  解#{i + 1}: 識別完了")
            except Exception as e:
                if verbose:
                    _emit_log(f"  解#{i + 1}: 識別エラー ({e})")
                exact_answers.append("不明")
    finally:
        mp.dps = old_dps

    answer_counts: Dict[str, int] = {}
    for exact in exact_answers:
        if exact != "不明":
            answer_counts[exact] = answer_counts.get(exact, 0) + 1

    most_likely_answer: Optional[str] = None
    if answer_counts:
        max_count = max(answer_counts.values())
        tied = [k for k, c in answer_counts.items() if c == max_count]

        if residuals is not None and len(residuals) == len(exact_answers):
            best_res = None
            best_exact = None
            for idx, exact in enumerate(exact_answers):
                if exact not in tied:
                    continue
                try:
                    r = float(residuals[idx])
                except Exception:
                    continue
                if best_res is None or r < best_res:
                    best_res = r
                    best_exact = exact
            if best_exact is not None:
                most_likely_answer = best_exact

        if most_likely_answer is None:
            most_likely_answer = sorted(tied)[0]

    return {
        "exact_answers": exact_answers,
        "most_likely_answer": most_likely_answer,
        "answer_counts": answer_counts,
        "answer_values": answer_values,
    }

