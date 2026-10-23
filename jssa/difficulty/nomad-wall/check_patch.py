"""Synthetic protocol checks, with no benchmark search outcomes."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "patch"))
import nomad_wall_patch as patch
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.evaluate_float_residual import FloatResidualEvaluation
from geosolver.engine.standard.search.nomad_blackbox_adapter import NomadBlackboxAdapter
from geosolver.engine.standard.search.nomad_config import NomadConfig


class Point:
    def __init__(self, x):
        self.x = x
        self.payload = None

    def size(self):
        return len(self.x)

    def get_coord(self, i):
        return self.x[i]

    def setBBO(self, value):
        self.payload = value


class Evaluator:
    def __init__(self, hard, finite=True, tiny=False):
        self.hard, self.finite, self.tiny = hard, finite, tiny
        self.calls = []

    def evaluate_float_residual(self, values):
        self.calls.append("residual")
        vector = [1e-12, 0.] if self.tiny else [3., 4.]
        if self.finite:
            return FloatResidualEvaluation(vector, 1e-12 if self.tiny else 5., EvaluationStatus.OK, True)
        return FloatResidualEvaluation([float("nan")], float("inf"),
                                       EvaluationStatus.NON_FINITE, False)

    def evaluate_float_hard_feasibility(self, values, **kwargs):
        self.calls.append("hard")
        return SimpleNamespace(hard_feasible=self.hard, failure_tags=() if self.hard else ("synthetic",),
                               min_margin=None)

    def evaluate_guard(self, values):
        self.calls.append("guard")
        return self.hard, () if self.hard else ("synthetic",)


def evaluate(mode, hard, scales, scope="disco_mads", finite=True, tiny=False):
    events = []
    if mode:
        patch.install(mode, lambda event, **data: events.append({"event": event, **data}))
    ev = Evaluator(hard, finite, tiny)
    point = Point([1., 2.])
    adapter = NomadBlackboxAdapter(ev, NomadConfig.standard_tier(), 0, 0, scales)
    token = patch.SCOPE.set(scope)
    try:
        code = adapter(point)
    finally:
        patch.SCOPE.reset(token)
        if mode:
            patch.uninstall()
    return code, point.payload, [asdict(r) for r in adapter.records], ev.calls, events


def main():
    checks = []
    # Finite false/true, scaled/unscaled, and precision-sensitive tiny residual.
    for hard in (False, True):
        for scales in (None, (3., 2.)):
            for tiny in (False, True):
                raw = evaluate(None, hard, scales, tiny=tiny)
                b = evaluate("B", hard, scales, tiny=tiny)
                n = evaluate("N", hard, scales, tiny=tiny)
                assert raw[:4] == b[:4]
                assert raw[0] == n[0] == 1 and raw[2:4] == n[2:4]
                if hard:
                    assert raw[1] == n[1]
                else:
                    ev = Evaluator(False, tiny=tiny)
                    expected = patch.equality_score(ev.evaluate_float_residual([]), scales)
                    assert float(n[1]) == expected
                for scope in (None, "hybrid_legacy_nomad"):
                    other = evaluate("N", hard, scales, scope=scope, tiny=tiny)
                    assert raw[:4] == other[:4]
                checks.append({"hard": hard, "scales": scales, "tiny": tiny, "passed": True})
    raw = evaluate(None, False, None, finite=False)
    for mode in ("B", "N"):
        checked = evaluate(mode, False, None, finite=False)
        assert checked[:4] == raw[:4]
        assert checked[0] == 0 and checked[1] is None
    checks.append({"nonfinite_preserved": True})
    checks.append({"params": NomadConfig.standard_tier().build_params(
        dimension=2, seed=0, search_mode="disco_mads")})
    result = {"passed": True, "benchmark_searches": 0, "checks": checks}
    (HERE / "patch-check.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
