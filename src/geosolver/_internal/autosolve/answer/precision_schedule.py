"""Precision scheduling helpers for autosolve."""


DEFAULT_TARGET_PRECISION = 50
# 30桁: mpmath が安定して動作する最低限の精度。PSLQや収束判定が15桁では誤爆するため設定。
MIN_PRECISION = 30
# Phase1: 広域探索での答え評価。目標の45%で十分な識別ができる（厳密値ではなく絞り込み用）。
PHASE1_PRECISION_RATIO = 0.45
# Phase2: 局所精緻化。目標の75%で大半のケースが収束する。
PHASE2_PRECISION_RATIO = 0.75
# Phase3: 最終オーバーシュート。識別精度を確保するため目標の150%まで引き上げる。上限180はOOM防止。
PHASE3_PRECISION_RATIO = 1.5
# Phase2は最低40桁保証（0.75*30=22.5では不足するため独立下限を設定）。
PHASE2_MIN_PRECISION = 40
# 高精度モードのメモリ・時間コストが急増するため上限を設ける。
PHASE3_CAP_PRECISION = 180
# Phase3は80桁以上の目標精度が要求されるときのみ有効化（低精度問題では不要なオーバーヘッドを避ける）。
PHASE3_ENABLE_THRESHOLD = 80


def build_precision_schedule(target_precision: int) -> list[int]:
    """Build staged precision schedule for iterative refinement."""
    try:
        precision = int(target_precision)
    except Exception:
        precision = DEFAULT_TARGET_PRECISION
    precision = max(MIN_PRECISION, precision)
    p1 = max(MIN_PRECISION, int(precision * PHASE1_PRECISION_RATIO))
    p2 = max(PHASE2_MIN_PRECISION, int(precision * PHASE2_PRECISION_RATIO))
    p3 = (
        max(precision, min(PHASE3_CAP_PRECISION, int(precision * PHASE3_PRECISION_RATIO)))
        if precision >= PHASE3_ENABLE_THRESHOLD
        else precision
    )
    return sorted({p1, p2, p3})
