#!/usr/bin/env python3
"""Champion-v2 + POC worker, requiring the existing strict triangle guards."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from mpmath import mp


HERE = Path(__file__).resolve().parent
CURRENT_WORKER = HERE / "champion_v2_poc_preloaded.py"


def _load_current():
    name = "geotarget_repro_20260722_champion_v2_poc_strict_base"
    spec = importlib.util.spec_from_file_location(name, CURRENT_WORKER)
    if spec is None or spec.loader is None:
        raise ImportError(CURRENT_WORKER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _require_strict_triangle_semantics() -> None:
    """Fail closed if the already-installed source guard correction is absent."""

    from geosolver._internal.autosolve.guards.compile import (
        compile_guard_expr,
        guard_hard_satisfied,
    )
    from geosolver.geometry.mp.mp_core_types import MPPoint

    acute = compile_guard_expr("AssumeAcute(A, B, C)")
    right = compile_guard_expr("AssumeRight(A, B, C)")
    obtuse = compile_guard_expr("AssumeObtuse(A, B, C)")
    if any(guard.kind != "triangle_class" for guard in (acute, right, obtuse)):
        raise RuntimeError("strict triangle guard compiler is not installed")

    context = {
        "A": MPPoint(mp.mpf("0"), mp.mpf("1")),
        "B": MPPoint(mp.mpf("0"), mp.mpf("0")),
        "C": MPPoint(mp.mpf("1"), mp.mpf("0")),
    }
    if (
        guard_hard_satisfied(acute, context)
        or not guard_hard_satisfied(right, context)
        or guard_hard_satisfied(obtuse, context)
    ):
        raise RuntimeError("strict triangle boundary semantics are inactive")


CURRENT = _load_current()
_require_strict_triangle_semantics()

# Preserve the current zero-dimensional, POC, preload, search, HP, and budget
# objects verbatim.  The strict guard implementation is already consumed by
# that closure; this wrapper only makes its presence an explicit requirement.
CHAMPION = CURRENT.CHAMPION
BASE = CHAMPION.BASE


def main() -> None:
    CURRENT.main()


if __name__ == "__main__":
    main()
