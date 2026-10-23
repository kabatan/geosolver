"""Q13: search-only role reassignment; original admission gates are retained."""
from __future__ import annotations

import atexit
from collections import Counter
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import time


@lru_cache(maxsize=512)
def plans_for(constraints, targets, constructions):
    from geosolver.engine.standard.refinement.mpmath_refiner import _zero_constraint_plans
    from geosolver.engine.standard.problem.tangency_contacts import (
        contact_tangency_source, distance_contact_sources,
    )
    equalities = tuple(zip(constraints, map(str, targets), strict=True))
    contacts = distance_contact_sources(constructions, equalities)
    plans = {i: ("contact", source) for i, source in contacts.items()}
    for i, (kind, arguments) in _zero_constraint_plans(constraints, targets).items():
        if kind != "istangent" or i in plans:
            continue
        source = contact_tangency_source(*arguments, constructions, equalities)
        plans[i] = ("contact", source) if source else ("tangent", arguments)
    return plans


def bundle_plans(bundle):
    return plans_for(tuple(bundle.spec.constraints), tuple(bundle.targets),
                     tuple((x.name, x.expr) for x in bundle.spec.construction))


def rewrite_float(bundle, values, vector, constraint_scales, counts):
    """Mirror frozen tangency rules only, at the original float precision."""
    from mpmath import mp
    from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
    from geosolver.problem.ir.compiler import safe_eval_expr_hp
    from geosolver.geometry.mp.signed_tangency import signed_tangency

    plans = bundle_plans(bundle)
    if not plans:
        return vector
    counts["signed_evaluation_attempts"] += 1
    sources = [source for kind, data in plans.values()
               for source in ((data,) if kind == "contact" else data)]
    try:
        with mp.workprec(53):
            snapshot = numerical_snapshot(bundle.spec, list(bundle.var_names), list(values),
                                          dict(bundle.base_context), arithmetic="float")
            context = snapshot.for_expressions(sources)
            replacements = {}
            for index, (kind, data) in plans.items():
                if kind == "contact":
                    value = safe_eval_expr_hp(data, context)
                    family = "contact"
                else:
                    left, right = (safe_eval_expr_hp(s, context) for s in data)
                    left, right = getattr(left, "circle", left), getattr(right, "circle", right)
                    if hasattr(left, "radius") and hasattr(right, "radius"):
                        value, family = signed_tangency(left, right), "circle_circle"
                    else:
                        if hasattr(left, "a") and hasattr(right, "radius"):
                            line, circle = left, right
                        elif hasattr(right, "a") and hasattr(left, "radius"):
                            line, circle = right, left
                        else:
                            counts["signed_unsupported_rows"] += 1
                            continue
                        distance = (mp.mpf(line.a) * mp.mpf(circle.center.x)
                                    + mp.mpf(line.b) * mp.mpf(circle.center.y) + mp.mpf(line.c))
                        value = distance * distance - mp.mpf(circle.radius) ** 2
                        family = "line_circle"
                value = float(value)
                if constraint_scales is not None and len(constraint_scales) == len(bundle.spec.constraints):
                    value /= constraint_scales[index]
                if not math.isfinite(value):
                    raise ValueError("nonfinite replacement")
                replacements[index] = (value, family)
            result = vector.copy()
            for index, (value, family) in replacements.items():
                counts["signed_rows_applied"] += 1
                counts[f"signed_rows_{family}"] += 1
                counts["signed_rows_changed"] += int(result[index] != value)
                result[index] = value
            return result
    except TimeoutError:
        raise
    except Exception as error:
        counts["signed_fallback_evaluations"] += 1
        counts[f"fallback:{type(error).__name__}"] += 1
        return vector


def install():
    from geosolver.engine.standard.search import scipy_multistart_backend as smb
    from geosolver.engine.standard.refinement import mpmath_refiner as mr
    from geosolver.engine.standard.evaluation.ir_evaluator import IREvaluator
    from geosolver.engine.standard.evaluation.snapshots import uses_evaluation_store
    from geosolver.runtime import artifact_commit

    mode = os.environ["ROLE_CONDITION"]
    if mode not in {"B", "R"}:
        raise ValueError(mode)
    audit_path = Path(os.environ["ROLE_AUDIT_PATH"])
    counts = Counter()
    original_hard = smb._evaluate_hard_feasibility_penalty
    original_vector = smb._evaluate_augmented_residual_vector
    original_search = smb.ScipyMultistartBackend.run_search
    original_smooth = mr._smooth_zero_constraint_residuals
    original_commit = artifact_commit.atomic_write
    preserved = {name: getattr(IREvaluator, name) for name in (
        "evaluate_float_residual", "evaluate_hp_residual", "evaluate_guard",
        "evaluate_float_hard_feasibility", "evaluate_hp_hard_feasibility",
    )}

    def emit(event, **fields):
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(event=event, condition=mode, pid=os.getpid(),
                                         unix=time.time(), counts=dict(counts), **fields)) + "\n")

    def commit(path, artifact):
        unchanged = all(getattr(IREvaluator, name) is value for name, value in preserved.items())
        embedded = dict(installed=1, verified=unchanged, final_evaluator_unchanged=unchanged,
                        malformed=0, counts=dict(counts), exited=False, condition=mode,
                        source="embedded_worker_artifact", pid=os.getpid(), utc_unix=time.time())
        artifact = artifact.model_copy(update={"diagnostics": {
            **artifact.diagnostics, "q13_role_audit": embedded}})
        return original_commit(path, artifact)

    def hard(**kwargs):
        counts["hard_calls"] += 1
        if mode == "R":
            value = 0.0
            counts["hard_bypassed"] += 1
        else:
            value = original_hard(**kwargs)
        if counts["hard_calls"] == 1:
            emit("first_hard", bypassed=(mode == "R"))
        return value

    @uses_evaluation_store()
    def vector(*, bundle, evaluator, values, n_constraints, telemetry, constraint_scales=None):
        kwargs = dict(bundle=bundle, evaluator=evaluator, values=values,
                      n_constraints=n_constraints, telemetry=telemetry,
                      constraint_scales=constraint_scales)
        counts["augmented_calls"] += 1
        result = original_vector(**kwargs)
        if mode == "R":
            # The source callback uses this whole vector for invalid constructions.
            if not all(x == smb._NONFINITE_RESIDUAL_PENALTY for x in result):
                before = counts["signed_rows_applied"]
                result = rewrite_float(kwargs["bundle"], kwargs["values"], result,
                                       kwargs.get("constraint_scales"), counts)
                if before == 0 and counts["signed_rows_applied"]:
                    emit("first_signed")
        if counts["augmented_calls"] % 2048 == 0:
            emit("checkpoint")
        return result

    def smooth(**kwargs):
        counts["hp_smoothing_calls"] += 1
        result = original_smooth(**kwargs)
        if counts["hp_smoothing_calls"] == 1:
            emit("first_existing_hp_smoothing")
        return result

    def search(self, **kwargs):
        counts["local_search_calls"] += 1
        plans = bundle_plans(kwargs["bundle"])
        emit("search_begin", signed_plans={str(i): value for i, value in plans.items()})
        try:
            return original_search(self, **kwargs)
        finally:
            emit("search_end", final_evaluator_unchanged=all(
                getattr(IREvaluator, name) is value for name, value in preserved.items()))

    smb._evaluate_hard_feasibility_penalty = hard
    smb._evaluate_augmented_residual_vector = vector
    smb.ScipyMultistartBackend.run_search = search
    mr._smooth_zero_constraint_residuals = smooth
    # Worker imports this name after sitecustomize; equations and gate results
    # are untouched. The audit now travels with the request-bound artifact.
    artifact_commit.atomic_write = commit
    emit("installed", patch_enabled=(mode == "R"),
         final_evaluator_unchanged=all(getattr(IREvaluator, n) is v for n, v in preserved.items()))

    def finish():
        emit("exit", final_evaluator_unchanged=all(
            getattr(IREvaluator, n) is v for n, v in preserved.items()))
    atexit.register(finish)
