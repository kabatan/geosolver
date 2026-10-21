"""Add bounded proposals on rational affine alternatives in original guards.

Finite assignments only guide floating search. Every original constraint, guard,
construction domain and independent high-precision verification stays in force.
"""

from __future__ import annotations

import itertools
import math
import random
import time
from functools import lru_cache

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate, SearchBatchResult
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.scaled_score import scaled_score
from geosolver.engine.standard.evaluation.search_point import evaluate_search_point
from geosolver.engine.standard.interpreter.guards.compile import compile_guards
from geosolver.problem.domain_bounds import affine
from geosolver.runtime.deadline import check_deadline, count_event


class _LocalBudget(Exception):
    """The optional finite proposal pass has used its own smaller budget."""


def _check_budget(deadline):
    check_deadline()  # A solve deadline must propagate, never become a fallback.
    if time.monotonic() >= deadline:
        raise _LocalBudget


@lru_cache(maxsize=128)
def _finite_assignments(var_names, definitions, clauses, guards, cap):
    # Cache only immutable mathematical source. Failed/expired computation never
    # enters the cache; unsupported sources do, avoiding repeated rescue costs.
    if not clauses:
        return ()
    from geosolver.problem.scalar_geometry import ScalarGeometry

    deadline = time.monotonic() + 0.25
    names = set(var_names)
    indices = {name: i for i, name in enumerate(var_names)}
    cache = {}

    def coefficients(source):
        _check_budget(deadline)
        if source not in cache:
            try:
                # The AST affine parser rejects powers/products without expanding
                # them into a polynomial. Geometry only resolves named coordinates
                # and elementary Cartesian constructions, with its own visit cap.
                pair = affine(source, names)
                if pair is None:
                    geometry = ScalarGeometry(dict(definitions))
                    scalar = geometry.scalar(geometry.parse(source))
                    pair = affine(str(scalar), names)
                cache[source] = pair
            except (ValueError, TypeError, KeyError, ArithmeticError, RecursionError):
                cache[source] = None
        _check_budget(deadline)
        return cache[source]

    domains = {}
    for alternatives in clauses:
        if not 2 <= len(alternatives) <= 16:
            continue
        axis, values = None, set()
        for clause in alternatives:
            if len(clause) != 1:
                break
            pair = coefficients(clause[0])
            if pair is None or len(pair[0]) != 1:
                break
            ((name, coefficient),) = pair[0].items()
            if not coefficient or (axis is not None and axis != indices[name]):
                break
            value = -pair[1] / coefficient
            try:
                if not math.isfinite(float(value)):
                    break
            except OverflowError:
                break
            axis = indices[name]
            values.add(value)
        else:
            if axis is not None:
                domains[axis] = values if axis not in domains else domains[axis] & values
    if not domains or len(domains) > 6 or math.prod(map(len, domains.values())) > cap:
        return ()
    axes = tuple(sorted(domains))
    comparisons = []

    def visit(guard):
        _check_budget(deadline)
        if guard.kind == "logical_and":
            for child in guard.children:
                visit(child)
        elif guard.kind == "compare":
            pair = coefficients(f"({guard.lhs_expr})-({guard.rhs_expr})")
            if pair is not None and all(indices[name] in domains for name in pair[0]):
                comparisons.append((pair[0], pair[1], guard.operator))

    for guard in compile_guards(guards):
        visit(guard)
    result = []
    for values in itertools.product(*(sorted(domains[axis]) for axis in axes)):
        _check_budget(deadline)
        assignment = dict(zip(axes, values, strict=True))
        valid = True
        for coefficients_by_name, constant, operator in comparisons:
            value = constant + sum(
                coefficient * assignment[indices[name]]
                for name, coefficient in coefficients_by_name.items()
            )
            if not {
                "==": value == 0,
                "!=": value != 0,
                ">": value > 0,
                ">=": value >= 0,
                "<": value < 0,
                "<=": value <= 0,
            }[operator]:
                valid = False
                break
        if valid:
            result.append(tuple(assignment.items()))
    return tuple(result)


def finite_assignments(bundle, cap=256):
    """Extract exact rational one-coordinate disjunctions; unsupported means ()."""
    check_deadline()
    plans = getattr(getattr(bundle, "spec", None), "logical_plans", ())
    if not plans or cap <= 0:
        return ()
    result = _finite_assignments(
        tuple(bundle.var_names),
        tuple((item.name, item.expr) for item in bundle.spec.construction),
        tuple(plan.clauses for plan in plans),
        tuple(bundle.spec.guards),
        int(cap),
    )
    check_deadline()
    return result


def search_finite_guards(
    *, bundle, evaluator, bounds, initial_probe_result, config, constraint_scales=None
):
    """Return additional proposals, or None when no finite search is applicable."""
    check_deadline()
    if config.max_bb_eval <= 0 or (config.max_time_sec is not None and config.max_time_sec <= 0):
        return None
    started = time.monotonic()
    local_budget = min(12.0, (12.0 if config.max_time_sec is None else config.max_time_sec) * 0.2)
    deadline = started + local_budget
    try:
        assignments = finite_assignments(bundle)
    except _LocalBudget:
        count_event("finite_guard_compile_budget_exhausted")
        return None
    if not assignments:
        return None
    if not all(math.isfinite(lo) and math.isfinite(hi) and lo <= hi for lo, hi in bounds):
        return None
    import numpy as np
    from scipy.optimize import least_squares

    randomizer = random.Random((config.seed_values or (0,))[0])
    free = [i for i in range(len(bounds)) if i not in dict(assignments[0])]
    starts = sorted(initial_probe_result.candidates, key=lambda c: (c.score, c.candidate_id))
    starts = [list(c.x_float) for c in starts[:3] if all(map(math.isfinite, c.x_float))]
    starts += [[randomizer.uniform(lo, hi) for lo, hi in bounds] for _ in range(2)]
    scales = (
        initial_probe_result.constraint_scales if constraint_scales is None else constraint_scales
    )
    records, evaluations, failures = [], 0, 0
    attempted, completed, local_timeouts, candidate_failures = 0, 0, 0, 0
    best = math.inf

    def evaluate(point):
        nonlocal evaluations, failures
        check_deadline()
        evaluations += 1
        count_event("finite_guard_residual_evaluations")
        try:
            evaluation = evaluator.evaluate_float_residual(point)
        except TimeoutError:
            raise
        except Exception:
            failures += 1
            return None
        if (
            evaluation.evaluation_status is not EvaluationStatus.OK
            or not evaluation.is_finite
            or not math.isfinite(evaluation.residual_norm_float)
            or len(evaluation.residual_vector) != len(bundle.targets)
            or not all(map(math.isfinite, evaluation.residual_vector))
        ):
            failures += 1
            return None
        return evaluation

    for start_index, start in enumerate(starts):
        for branch_index, assignment in enumerate(assignments):
            check_deadline()
            if time.monotonic() >= deadline:
                break
            branch_point = list(start)
            for axis, value in assignment:
                branch_point[axis] = float(value)
            if any(
                not lo <= value <= hi for value, (lo, hi) in zip(branch_point, bounds, strict=True)
            ):
                continue
            point = list(branch_point)
            branch_deadline = min(
                deadline, time.monotonic() + max(0.1, local_budget / len(assignments))
            )

            def residual(active, branch_deadline=branch_deadline, branch_point=branch_point):
                _check_budget(branch_deadline)
                proposal = list(branch_point)
                for axis, value in zip(free, active, strict=True):
                    proposal[axis] = float(value)
                evaluation = evaluate(proposal)
                if evaluation is None:
                    return np.full(len(bundle.targets), 1e6)
                vector = evaluation.residual_vector
                return np.asarray(
                    vector
                    if scales is None
                    else [v / s for v, s in zip(vector, scales, strict=True)]
                )

            attempted += 1
            try:
                if free:
                    solution = least_squares(
                        residual,
                        np.array([point[i] for i in free]),
                        method="lm" if len(bundle.targets) >= len(free) else "trf",
                        max_nfev=min(160, max(1, config.max_bb_eval)),
                        ftol=1e-11,
                        xtol=1e-11,
                        gtol=1e-11,
                    )
                    for axis, value in zip(free, solution.x, strict=True):
                        point[axis] = float(value)
                _check_budget(branch_deadline)
                if any(
                    not lo <= value <= hi for value, (lo, hi) in zip(point, bounds, strict=True)
                ):
                    continue
                evaluation = evaluate(point)
                completed += 1
                if evaluation is None:
                    continue
                best = min(best, evaluation.residual_norm_float)
                if evaluation.residual_norm_float > 1e-5:
                    continue
                check_deadline()
                checked = evaluate_search_point(
                    evaluator=evaluator, values=point, residual=evaluation
                )
                hard = checked.hard
                records.append(
                    FloatCandidate(
                        x_float=tuple(point),
                        score=scaled_score(evaluation.residual_vector, scales)
                        + (0.0 if hard.hard_feasible else config.guard_penalty),
                        residual_norm_float=evaluation.residual_norm_float,
                        guard_ok=checked.guard_ok,
                        evaluation_status=evaluation.evaluation_status,
                        origin_seed=(config.seed_values or (0,))[0],
                        origin_start_point_index=start_index,
                        candidate_id=8_000_000 + start_index * 256 + branch_index,
                        origin_backend="finite_guard_local",
                        origin_family=f"branch:{branch_index}",
                        origin_evaluation_index=evaluations - 1,
                        hard_feasible=hard.hard_feasible,
                        hard_violation_tags=tuple(hard.failure_tags),
                        validity_margin_float=(
                            None if hard.min_margin is None else float(hard.min_margin)
                        ),
                    )
                )
            except _LocalBudget:
                local_timeouts += 1
            except TimeoutError:
                raise
            except Exception:
                # This optional proposal cannot make unsupported numerical or
                # geometry evaluation abort the ordinary search backend.
                candidate_failures += 1
    count_event("finite_guard_assignments", len(assignments))
    count_event("finite_guard_proposals", len(records))
    return SearchBatchResult(
        candidates=tuple(records),
        all_records=tuple(records),
        evaluation_count=evaluations,
        evaluation_failure_count=failures,
        failure_ratio=0.0 if not evaluations else failures / evaluations,
        search_diagnostics={
            "finite_guard_local": {
                "assignments": len(assignments),
                "attempted": attempted,
                "completed": completed,
                "local_timeouts": local_timeouts,
                "candidate_failures": candidate_failures,
                "residual_evaluations": evaluations,
                "failed_residual_evaluations": failures,
                "elapsed_sec": time.monotonic() - started,
                "best_residual": None if not math.isfinite(best) else best,
            }
        },
    )
