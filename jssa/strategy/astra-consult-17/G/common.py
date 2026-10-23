"""Read-only access to the frozen solver and existing benchmark helpers."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jssa/difficulty"))
from probe_basins import (  # noqa: E402
    GeometryProblem, load_case, load_problem_bundle, build_ir_evaluator,
    reference_values, answer_float, smb, ExternalPipelineConfig,
)

RAW = ROOT / "jssa/difficulty/minima/raw-323"


def case_context(cid):
    case = load_case(cid)
    bundle = load_problem_bundle(GeometryProblem.model_validate(case["dsl"]).engine_document())
    ev = build_ir_evaluator(bundle)
    raw = json.loads((RAW / f"{cid}.json").read_text())
    bounds = raw["box"]
    lo, hi = np.array(bounds, float).T
    return case, bundle, ev, raw, bounds, lo, hi - lo


def hard(ev, x):
    try:
        return ev.evaluate_float_hard_feasibility(list(x), include_margins=False)
    except Exception:
        return None


def feasible(ev, x):
    h = hard(ev, x)
    return h is not None and bool(h.hard_feasible)


def equality(ev, x):
    try:
        r = ev.evaluate_float_residual(list(x))
        y = np.asarray(r.residual_vector, dtype=float)
        return y if r.is_finite and np.isfinite(y).all() else None
    except Exception:
        return None


def classify(ev, cand, refs):
    if cand is None:
        return {"cls": "error"}
    out = {"x": list(map(float, cand.x_float)), "hard": cand.hard_feasible,
           "tags": list(cand.hard_violation_tags)}
    if "out_of_bounds" in cand.hard_violation_tags:
        out["cls"] = "left_box"
    elif not math.isfinite(cand.residual_norm_float):
        out["cls"] = "error"
    else:
        out["res"] = float(cand.residual_norm_float)
        if cand.residual_norm_float > 1e-8:
            out["cls"] = "stuck"
        elif not cand.guard_ok or cand.hard_feasible is False:
            out["cls"] = "wrong_branch"
        else:
            val = answer_float(ev, cand.x_float)
            out["ans"] = val
            out["cls"] = "hit" if val is not None and any(
                abs(val - ref) <= 1e-6 * max(1.0, abs(ref)) for ref in refs
            ) else "wrong_answer"
    return out


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def write_json(path, obj):
    Path(path).write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2) + "\n")
