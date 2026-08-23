"""Projection algorithms extracted from high_precision_projection."""

from __future__ import annotations

import re
import time
from functools import partial
from typing import Callable, List, Optional, Tuple

from mpmath import mp, mpf

from geosolver._internal.config.environment.findroot_polish_enabled import get_findroot_polish_enabled
from geosolver._internal.solver.precision.type_guards.ensure_no_float import (
    ensure_high_precision_mode,
    ensure_no_float,
)
from geosolver._internal.solver.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver._internal.solver.precision.type_guards.strict_to_mpf import strict_to_mpf
from geosolver.geometry.mp.mp_primitives_intersections import (
    SelectorTrace,
    capture_selector_trace,
    freeze_selector_trace,
)

from .high_precision_projection_fast import (
    project_to_constraint_hp_fast_impl as _project_to_constraint_hp_fast,
)


FINDROOT_POLISH_ENABLED = True
FINDROOT_POLISH_MAX_DIMENSION = 4

# P2: target_digits is set this many digits ABOVE the requested precision so that the
# final residual check (which uses the exact precision) passes with comfortable margin.
_HP_PROJECTION_TARGET_MARGIN: int = 5

# P2: FD delta floor scale factor — delta >= 10^(-precision * this).
# Must be large enough for the Jacobian to reflect the current residual scale.
# The previous cap of min(50, ...) was the primary cause of convergence stall near 1e-50.
_FD_DELTA_FLOOR_PRECISION_FACTOR: float = 4.0 / 5.0

# P2: Absolute minimum digits for FD delta floor (floor of floor).
_FD_DELTA_FLOOR_MIN_DIGITS: int = 30

# P3: Upper bound for Levenberg-Marquardt regularisation strength.
# Previous cap of 1e-4 was insufficient for severely ill-conditioned Jacobians.
_LAMBDA_LM_MAX_LOG10: int = 0  # 10^0 = 1.0
_FD_DELTA_DPS_RATIO: float = 1.0 / 2.0
_LM_RATIO_SHRINK_THRESHOLD = mpf("0.25")
_LM_RATIO_GROW_THRESHOLD = mpf("0.75")
_LM_RATIO_STRONG_REJECT_THRESHOLD = mpf("0.05")
_STAGNATION_PERTURBATION_PERIOD = 12
_STAGNATION_PERTURBATION_SCALE = mpf("0.25")
_SELECTOR_MARGIN_DPS_RATIO = mpf("0.5")


def _is_findroot_polish_enabled() -> bool:
    return get_findroot_polish_enabled(default=FINDROOT_POLISH_ENABLED)


def _projection_to_mpf(val, *, precision: int, to_mpf_value: Callable):
    return to_mpf_value(val, precision)


def _findroot_residual_tuple(
    *vals,
    to_mpf: Callable,
    f: Callable,
    v: List,
    m: int,
):
    vec = [to_mpf(vv) for vv in vals]
    fv = f(vec)
    return tuple(to_mpf(fv[k]) - v[k] for k in range(m))


def _resolve_base_helpers():
    from . import high_precision_projection as _base

    return _base._set_mp_dps_for_precision, _base._to_mpf_value, _base._clamp_to_bounds_hp


def _selector_margin_noise_floor() -> mpf:
    return mp.power(mpf(10), -max(12, int(mp.dps * _SELECTOR_MARGIN_DPS_RATIO)))


def _selector_margin_is_low(trace: SelectorTrace) -> bool:
    if not trace.has_entries:
        return False
    if not mp.isfinite(trace.min_margin):
        return False
    return trace.min_margin <= _selector_margin_noise_floor()


def _predicted_reduction(step: List[mpf], jtr_vector: List[mpf]) -> mpf:
    total = mpf("0")
    for step_value, jtr_value in zip(step, jtr_vector):
        total += step_value * jtr_value
    return max(mpf("0"), total / 2)


def _update_lambda_from_ratio(
    lambda_lm: mpf,
    *,
    ratio: mpf,
    accepted: bool,
    full_step: bool,
) -> mpf:
    if not accepted or ratio <= _LM_RATIO_STRONG_REJECT_THRESHOLD:
        return min(mpf(10) ** _LAMBDA_LM_MAX_LOG10, lambda_lm * mpf("4"))
    if ratio < _LM_RATIO_SHRINK_THRESHOLD:
        return min(mpf(10) ** _LAMBDA_LM_MAX_LOG10, lambda_lm * mpf("2"))
    if ratio > _LM_RATIO_GROW_THRESHOLD and full_step:
        return max(mpf(10) ** (-20), lambda_lm / 2)
    return lambda_lm


def _apply_stagnation_perturbation(
    x: List[mpf],
    *,
    iteration: int,
    precision: int,
    bounds: Optional[List[Tuple[float, float]]],
    to_mpf: Callable,
    clamp_to_bounds: Callable,
) -> List[mpf]:
    perturb_digits = max(12, min(int(mp.dps * _FD_DELTA_DPS_RATIO), int(precision)))
    perturb_scale = mp.power(mpf(10), -perturb_digits) * _STAGNATION_PERTURBATION_SCALE
    perturbed: List[mpf] = []
    for index, value in enumerate(x):
        direction = mpf("1") if (iteration + index) % 2 == 0 else mpf("-1")
        magnitude = max(mpf("1"), abs(to_mpf(value)))
        perturbed.append(to_mpf(value) + direction * perturb_scale * magnitude)
    return clamp_to_bounds(perturbed, bounds, to_mpf)


def _project_to_constraint_hp(
    f: Callable,
    v: List,
    x: List,
    n: int,
    m: int,
    precision: int,
    deadline: Optional[float] = None,
    bounds: Optional[List[Tuple[float, float]]] = None,
) -> List:
    """Gauss-Newton法で制約f(x)=vを満たす点に射影（ロバスト版・高精度改善版）"""
    ensure_high_precision_mode(context="_project_to_constraint_hp")
    ensure_no_float(v, context="_project_to_constraint_hp.target")
    ensure_no_float(x, context="_project_to_constraint_hp.seed")
    _set_mp_dps_for_precision, _to_mpf_value, _clamp_to_bounds_hp = _resolve_base_helpers()
    _set_mp_dps_for_precision(precision, extra=80)

    to_mpf = partial(_projection_to_mpf, precision=precision, to_mpf_value=_to_mpf_value)

    x = _clamp_to_bounds_hp(x, bounds, to_mpf)
    x_initial = x[:]

    v_norm = mp.sqrt(sum(to_mpf(vi) ** 2 for vi in v))
    if v_norm < 1:
        v_norm = mpf("1")

    # 高精度収束のためのパラメータ調整
    max_iter = min(1000, max(300, int(precision * 3)))
    # P2: target_digits は precision を _HP_PROJECTION_TARGET_MARGIN だけオーバーシュートさせる。
    # 旧実装: int(precision * 99/100) → precision=100 で 1e-99 が目標となり
    # 最終チェック閾値 1e-100 に 1 桁届かず residual_not_converged が頻発していた。
    target_digits = int(precision) + _HP_PROJECTION_TARGET_MARGIN
    target_relative_residual = mpf(10) ** (-target_digits)
    # 絶対残差の目標も同様にマージンを付与
    target_absolute_residual = mpf(10) ** (-(int(precision) + _HP_PROJECTION_TARGET_MARGIN + 30))

    # Soft deadline when caller did not supply one to prevent runaway projections.
    if deadline is None:
        # Allow more wall‑time for high‑precision runs; still cap to avoid runaway loops.
        try:
            deadline = time.time() + min(max(3 * float(precision) / 5, 30), 120)
        except Exception:
            deadline = time.time() + 60

    prev_res_norm = mpf("inf")
    stagnant_count = 0
    best_x = x[:]
    best_res_norm = mpf("inf")
    selector_trace = SelectorTrace()

    # Levenberg-Marquardtパラメータの適応的制御
    lambda_LM = mpf(10) ** (-8)  # 初期値
    lm_success_count = 0  # 成功回数カウンタ
    # R3a Bug D: ラインサーチ失敗追跡
    consecutive_ls_failures = 0  # 連続ラインサーチ失敗カウンタ
    prev_ls_failed = False  # 前回ラインサーチが失敗したか

    for iteration in range(max_iter):
        if deadline is not None and time.time() >= deadline:
            x = best_x[:]
            break

        try:
            with capture_selector_trace() as selector_trace:
                f_val = f(x)
            residual = [to_mpf(f_val[k]) - v[k] for k in range(m)]
        except HighPrecisionContaminationError:
            raise
        except Exception:
            x = best_x[:]
            continue

        res_norm = mp.sqrt(sum(r**2 for r in residual))
        relative_res_norm = res_norm / v_norm

        if res_norm < best_res_norm:
            best_res_norm = res_norm
            best_x = x[:]
            stagnant_count = 0
            lm_success_count += 1
            # 成功が続いたらlambdaを減らして信頼領域を広げる
            if lm_success_count >= 3:
                lambda_LM = max(mpf(10) ** (-20), lambda_LM * (mpf(7) / 10))
                lm_success_count = 0
        else:
            stagnant_count += 1
            lm_success_count = 0
            # R3a Bug D: 前回ラインサーチが失敗した場合は lambda を増やさない。
            # 失敗後に x が変わっていないため res_norm == best_res_norm となり
            # 以前の実装では毎回 lambda *= 1.5 してトラスト領域が縮み続けていた。
            # ラインサーチ失敗起因の停滞では lambda を据え置く。
            # P3: 上限を 10^_LAMBDA_LM_MAX_LOG10 (= 1.0) に引き上げ。
            if not prev_ls_failed:
                lambda_LM = min(mpf(10) ** _LAMBDA_LM_MAX_LOG10, lambda_LM * (mpf(3) / 2))

        # 両方の基準で収束判定
        if relative_res_norm < target_relative_residual or res_norm < target_absolute_residual:
            break

        # R3a Bug E: max_stagnant を引き上げて高精度ターゲットで早期終了しないようにする。
        # 旧値 max(60, precision*0.5) は precision=100 で 60 となり、
        # ラインサーチ失敗ペナルティ (+3) で ~15回の失敗後に終了していた。
        # 新値: max(120, precision) で十分な反復余地を確保する。
        # また、残差が既に小さい（< 1e-6）場合はラインサーチ失敗ペナルティを
        # stagnant_count に加算しない（収束直前の誤終了を防ぐ）。
        max_stagnant = max(120, int(precision))
        if stagnant_count > max_stagnant:
            x = best_x[:]
            break

        if (
            stagnant_count > 0
            and stagnant_count % int(_STAGNATION_PERTURBATION_PERIOD) == 0
        ) or _selector_margin_is_low(selector_trace):
            x = _apply_stagnation_perturbation(
                x,
                iteration=iteration,
                precision=int(precision),
                bounds=bounds,
                to_mpf=to_mpf,
                clamp_to_bounds=_clamp_to_bounds_hp,
            )
            continue

        # Jacobian (FD) - 適応的差分ステップ
        # 残差に応じてdeltaを動的に調整
        # N4: ループ内の target_digits を別名にして外側の int 定数をシャドウしない。
        current_digits = -mp.log(res_norm, 10) if res_norm > 0 else mp.mpf("0")
        _loop_target_digits = mp.mpf(int(precision) + _HP_PROJECTION_TARGET_MARGIN)
        remaining_digits = max(mp.mpf("0"), _loop_target_digits - current_digits)

        # delta は残差スケールと現在の精度に連動させる。
        # catastrophic cancellation を防ぐため delta = 10^-(remaining + buffer)。
        buffer_digits = mp.mpf("10")
        delta_exp = min(
            int(precision * 3),
            int(mp.dps * _FD_DELTA_DPS_RATIO),
            int(remaining_digits + buffer_digits + 10),
        )
        delta_exp = max(delta_exp, _FD_DELTA_FLOOR_MIN_DIGITS)
        delta = mpf(10) ** (-delta_exp)
        # P2: delta の床値から min(50, ...) 上限キャップを除去。
        # 旧実装では precision=100 時に delta >= 1e-50 に固定され
        # ヤコビアン誤差が O(delta) で残差が ~1e-50 以下に収束できなかった。
        delta_floor = mpf(10) ** (-max(_FD_DELTA_FLOOR_MIN_DIGITS, int(precision * _FD_DELTA_FLOOR_PRECISION_FACTOR)))
        if delta < delta_floor:
            delta = delta_floor

        J = []
        try:
            for j in range(n):
                x_plus = x[:]
                x_plus[j] = to_mpf(x_plus[j]) + delta
                with freeze_selector_trace(selector_trace.entries):
                    f_plus = f(x_plus)
                col = [(to_mpf(f_plus[k]) - to_mpf(f_val[k])) / delta for k in range(m)]
                J.append(col)
        except HighPrecisionContaminationError:
            raise
        except Exception:
            x = best_x[:]
            break

        res_vec = [-residual[r] for r in range(m)]
        jtr_vector = [
            sum(J[col_index][row_index] * res_vec[row_index] for row_index in range(m))
            for col_index in range(n)
        ]

        try:
            step = None

            # SVDベースのダンピング付き最小二乗（小規模系向けに安定）
            try:
                from mpmath import matrix
                # Convert explicitly for SVD, but avoid if we can
                J_mat_mp = matrix(m, n)
                for r in range(m):
                    for c in range(n):
                        J_mat_mp[r, c] = J[c][r]
                
                U, S, V = mp.svd(J_mat_mp)

                Ut_r = [mpf("0") for _ in range(len(S))]
                for k in range(len(S)):
                    s = mpf("0")
                    for i in range(m):
                        s += U[i, k] * res_vec[i]
                    Ut_r[k] = s

                coeffs = []
                for s_val, ur in zip(S, Ut_r):
                    if s_val == 0:
                        coeffs.append(mpf("0"))
                    else:
                        coeffs.append((s_val / (s_val * s_val + lambda_LM)) * ur)

                # mpmath SVD convention: A = U * diag(S) * V
                # Pseudoinverse: A^+ = V^T * diag(1/S) * U^T
                # So we must use V^T (i.e., V[k, j]) not V[j, k].
                step = [mpf("0") for _ in range(n)]
                for j in range(n):
                    s = mpf("0")
                    for k in range(len(S)):
                        s += V[k, j] * coeffs[k]
                    step[j] = s
            except HighPrecisionContaminationError:
                raise
            except Exception:
                step = None

            if step is None:
                # Fast fallback implementation for 1x1 and 2x2 normal equations
                if n == 1:
                    jtj = sum(J[0][r] * J[0][r] for r in range(m)) + lambda_LM
                    jtr = sum(J[0][r] * res_vec[r] for r in range(m))
                    if jtj != 0:
                        step = [jtr / jtj]
                elif n == 2:
                    j00 = sum(J[0][r] * J[0][r] for r in range(m)) + lambda_LM
                    j11 = sum(J[1][r] * J[1][r] for r in range(m)) + lambda_LM
                    j01 = sum(J[0][r] * J[1][r] for r in range(m))
                    jr0 = sum(J[0][r] * res_vec[r] for r in range(m))
                    jr1 = sum(J[1][r] * res_vec[r] for r in range(m))
                    
                    det = j00 * j11 - j01 * j01
                    if det != 0:
                        step = [
                            (j11 * jr0 - j01 * jr1) / det,
                            (j00 * jr1 - j01 * jr0) / det
                        ]
                
                if step is None:
                    # Generic fallback using mpmath LU solver
                    from mpmath import matrix, lu_solve
                    J_mat = matrix(m, n)
                    for r in range(m):
                        for c in range(n):
                            J_mat[r, c] = J[c][r]
                    res_m = matrix(m, 1)
                    for r in range(m):
                        res_m[r, 0] = res_vec[r]

                    jtj = J_mat.T * J_mat
                    for k in range(n):
                        jtj[k, k] += lambda_LM
                    jtr = J_mat.T * res_m
                    step_m = lu_solve(jtj, jtr)
                    step = [step_m[j, 0] for j in range(n)]


            # P3: line search — 厳格な単調減少のみ受け付ける。
            # 旧実装は最良 alpha が 10% 悪化まで許容していたが、
            # これは収束後期で振動を引き起こし単調収束を破壊していた。
            alpha = mpf("1")
            accepted = False
            accepted_ratio = mpf("0")
            accepted_full_step = False
            predicted_reduction = _predicted_reduction(step, jtr_vector)

            for ls_step in range(12):
                x_next = []
                for j in range(n):
                    x_next.append(x[j] + alpha * step[j])
                x_next = _clamp_to_bounds_hp(x_next, bounds, to_mpf)

                try:
                    with freeze_selector_trace(selector_trace.entries):
                        res_next_val = f(x_next)
                    res_next = [to_mpf(res_next_val[k]) - v[k] for k in range(m)]
                    norm_next = mp.sqrt(sum(r * r for r in res_next))

                    # R3a Bug C: 厳密な < 比較は評価ノイズが O(delta) のときに
                    # res_norm が僅かに増えた "ノイズフロア" ステップを全て棄却してしまう。
                    # 代わりに: 絶対改善 OR ノイズフロア内（|diff| < res_norm * 10^(-dps/2)）
                    # のどちらかを満たすステップを受理する。
                    actual_reduction = max(
                        mpf("0"),
                        (res_norm * res_norm - norm_next * norm_next) / 2,
                    )
                    if predicted_reduction > 0:
                        accepted_ratio = actual_reduction / predicted_reduction
                    else:
                        accepted_ratio = mpf("0")
                    if norm_next < res_norm:
                        x = x_next
                        accepted = True
                        accepted_full_step = ls_step == 0
                        break
                except HighPrecisionContaminationError:
                    raise
                except Exception:
                    pass
                alpha /= 2

            lambda_LM = _update_lambda_from_ratio(
                lambda_LM,
                ratio=accepted_ratio,
                accepted=accepted,
                full_step=accepted_full_step,
            )

            if not accepted:
                # R3a Bug D: ラインサーチ失敗を追跡して lambda 制御に使う。
                consecutive_ls_failures += 1
                prev_ls_failed = True
                # R3a Bug E: 残差が既に小さい（< 1e-6）場合はペナルティを加算しない。
                # 収束直前のノイズフロアで不当に早期終了するのを防ぐ。
                if alpha < mpf(10) ** (-6) and best_res_norm >= mpf("1e-6"):
                    stagnant_count += 3  # Penalty
                # R3a Bug D: 3回連続失敗後は lambda を大幅に減らしてトラスト領域を広げる。
                if consecutive_ls_failures >= 3:
                    lambda_LM = max(mpf(10) ** (-20), lambda_LM * (mpf(7) / mpf(10)))
                    consecutive_ls_failures = 0
            else:
                consecutive_ls_failures = 0
                prev_ls_failed = False

        except HighPrecisionContaminationError:
            raise
        except Exception:
            break

    # Final square-system polish with mp.findroot (disabled by default)
    # N1: old_dps_fr を try ブロックの外で初期化する。
    # 旧実装では if 条件が False のときや if に入る前に例外が発生した場合に
    # NameError が except ブロックで黙殺され mp.dps が復元されないバグがあった。
    old_dps_fr = mp.dps
    try:
        if _is_findroot_polish_enabled() and m == n and 0 < n <= FINDROOT_POLISH_MAX_DIMENSION:
            old_dps_fr = mp.dps  # ここでも更新（findroot 前の正確な値を保持）
            mp.dps = max(mp.dps, int(precision) + 40)

            _F_root = partial(_findroot_residual_tuple, to_mpf=to_mpf, f=f, v=v, m=m)

            try:
                root = mp.findroot(
                    _F_root,
                    *[to_mpf(xj) for xj in best_x],
                    tol=mp.power(mp.mpf(10), -(int(precision) + 6)),
                    maxsteps=30,
                )
            except HighPrecisionContaminationError:
                raise
            except Exception:
                root = None

            if root is not None:
                cand = list(root) if isinstance(root, (list, tuple)) else [root]
                if len(cand) == n:
                    try:
                        f_val = f(cand)
                        residual = [to_mpf(f_val[k]) - v[k] for k in range(m)]
                        res_norm = mp.sqrt(sum(r * r for r in residual))
                        if mp.isfinite(res_norm) and res_norm < best_res_norm:
                            best_res_norm = res_norm
                            best_x = [to_mpf(xx) for xx in cand]
                    except HighPrecisionContaminationError:
                        raise
                    except Exception:
                        pass
            mp.dps = old_dps_fr
    except HighPrecisionContaminationError:
        raise
    except Exception:
        try:
            mp.dps = old_dps_fr
        except Exception:
            pass

    return best_x


def project_constraint_follow(
    f: Callable,
    v: List,
    x: List,
    n: int,
    m: int,
    precision: int,
    deadline: Optional[float] = None,
    bounds: Optional[List[Tuple[float, float]]] = None,
) -> List:
    """Project candidate onto constraint manifold with robust fallback."""
    try:
        projected = _project_to_constraint_hp(
            f,
            v,
            x,
            n,
            m,
            precision,
            deadline=deadline,
            bounds=bounds,
        )
        if isinstance(projected, list) and len(projected) == n:
            return projected
    except HighPrecisionContaminationError:
        raise
    except Exception:
        pass
    try:
        projected_fast = _project_to_constraint_hp_fast(
            f,
            v,
            x,
            n,
            m,
            precision,
            deadline=deadline,
            bounds=bounds,
        )
        if isinstance(projected_fast, list) and len(projected_fast) == n:
            return projected_fast
    except HighPrecisionContaminationError:
        raise
    except Exception:
        pass
    return x[:]
