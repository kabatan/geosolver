"""Interior sampling of the affine part of original hard inequalities.

A random box probe rarely satisfies narrow ordered-variable guards. A maximum
margin LP finds an interior point of their intersection; hit-and-run directions
then provide varied starts. Nonlinear guards and every original residual are
still evaluated normally. This sampler adds witnesses and removes no starts.
"""

from __future__ import annotations

import ast
import math
import random
import time
import warnings
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.scaled_score import scaled_score
from geosolver.runtime.deadline import check_deadline, current_deadline

if TYPE_CHECKING:
    from .manifold import ManifoldSampleResult


@lru_cache(maxsize=256)
def affine_guard_rows(variables, constructions, guards):
    """Return a*x+c>=(>)0 rows; ignore unsupported nonlinear expressions."""
    n = len(variables)
    axes = {name: index for index, name in enumerate(variables)}
    definitions = dict(constructions)
    active = set()

    def scalar(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return [0.0] * n, float(node.value)
        if isinstance(node, ast.Name):
            if node.id in axes:
                values = [0.0] * n
                values[axes[node.id]] = 1.0
                return values, 0.0
            if node.id in {"pi", "e"}:
                return [0.0] * n, getattr(math, node.id)
            if node.id in definitions and node.id not in active:
                active.add(node.id)
                try:
                    return scalar(ast.parse(definitions[node.id], mode="eval").body)
                finally:
                    active.remove(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            a, c = scalar(node.operand)
            sign = -1 if isinstance(node.op, ast.USub) else 1
            return [sign * x for x in a], sign * c
        if isinstance(node, ast.BinOp):
            a, c = scalar(node.left)
            b, d = scalar(node.right)
            if isinstance(node.op, ast.Add | ast.Sub):
                sign = -1 if isinstance(node.op, ast.Sub) else 1
                return [x + sign * y for x, y in zip(a, b, strict=True)], c + sign * d
            if isinstance(node.op, ast.Mult) and (not any(a) or not any(b)):
                if any(a):
                    return [x * d for x in a], c * d
                return [x * c for x in b], c * d
            if isinstance(node.op, ast.Div) and not any(b) and d:
                return [x / d for x in a], c / d
        raise ValueError("non-affine guard")

    rows = []
    for source in guards:
        try:
            node = ast.parse(source, mode="eval").body
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and len(node.args) == 2
                and not node.keywords
                and node.func.id in {"AssumeGt", "AssumeGe", "AssumeLt", "AssumeLe"}
            ):
                continue
            a, c = scalar(node.args[0])
            b, d = scalar(node.args[1])
            sign = -1 if node.func.id in {"AssumeLt", "AssumeLe"} else 1
            a = tuple(sign * (x - y) for x, y in zip(a, b, strict=True))
            c = sign * (c - d)
            if not all(math.isfinite(value) for value in (*a, c)):
                continue
            if not any(a):
                # A false constant guard cannot have an interior witness.
                if c < 0 or (c == 0 and node.func.id in {"AssumeGt", "AssumeLt"}):
                    return None
                continue
            rows.append((a, c))
        except (ValueError, TypeError, SyntaxError, ArithmeticError, RecursionError):
            continue
    return tuple(rows)


def affine_interior_points(*, variables, constructions, guards, bounds, count=32, seed=0):
    """Sample within finite heuristic bounds, or return () on unsupported LPs."""
    rows = affine_guard_rows(tuple(variables), tuple(constructions), tuple(guards))
    if rows is None or len(rows) < 2 or len(bounds) != len(variables):
        return ()
    if any(
        not math.isfinite(low) or not math.isfinite(high) or high <= low for low, high in bounds
    ):
        return ()
    import numpy as np
    from scipy.optimize import OptimizeWarning, linprog

    dimension = len(variables)
    # Normalize equation units, including positive scalar rewrites. Box rows
    # keep the optional sampler bounded without treating the box as a proof.
    normals = []
    limits = []
    for coefficients, constant in rows:
        norm = math.hypot(*coefficients)
        if not math.isfinite(norm) or norm == 0:
            return ()
        normals.append(tuple(-value / norm for value in coefficients))
        limits.append(constant / norm)
    for index, (low, high) in enumerate(bounds):
        row = [0.0] * dimension
        row[index] = 1.0
        normals.append(tuple(row))
        limits.append(high)
        normals.append(tuple(-value for value in row))
        limits.append(-low)
    matrix = np.asarray(normals, dtype=float)
    rhs = np.asarray(limits, dtype=float)
    check_deadline()
    try:
        deadline = current_deadline()
        budget = 0.25 if deadline is None else min(0.25, max(0.0, deadline - time.monotonic()))
        if budget <= 0:
            check_deadline()
            return ()
        # SciPy forwards threads to HiGHS; a public single-core solve must
        # not create a native parallel worker pool for this optional LP.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="Unrecognized options detected.*", category=OptimizeWarning
            )
            solution = linprog(
                [0.0] * dimension + [-1.0],
                A_ub=np.column_stack((matrix, np.ones(len(matrix)))),
                b_ub=rhs,
                bounds=[(None, None)] * dimension + [(0, None)],
                method="highs-ds",
                options={"presolve": True, "threads": 1, "time_limit": budget},
            )
    except (ValueError, ArithmeticError):
        return ()
    check_deadline()
    if not solution.success or solution.x[-1] <= 1e-9:
        return ()
    current = np.asarray(solution.x[:-1], dtype=float)
    if not np.isfinite(current).all() or np.min(rhs - matrix @ current) <= 0:
        return ()
    rng = random.Random(int(seed))
    points = []
    burn_in = 3 * dimension
    for iteration in range(burn_in + max(0, int(count))):
        check_deadline()
        if iteration % 2 == 0:
            # Coordinate directions let weakly bounded variables traverse a
            # long interval even when other coordinates have narrow guards.
            direction = np.zeros(dimension)
            direction[rng.randrange(dimension)] = 1.0
        else:
            direction = np.asarray([rng.gauss(0.0, 1.0) for _ in range(dimension)])
        norm = float(np.linalg.norm(direction))
        if not norm:
            continue
        direction /= norm
        rate = matrix @ direction
        slack = rhs - matrix @ current
        lower = -math.inf
        upper = math.inf
        for change, margin in zip(rate, slack, strict=True):
            if change > 1e-14:
                upper = min(upper, float(margin / change))
            elif change < -1e-14:
                lower = max(lower, float(margin / change))
        if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
            continue
        proposal = current + (lower + (upper - lower) * rng.uniform(0.05, 0.95)) * direction
        if np.min(rhs - matrix @ proposal) <= 0:
            continue
        current = proposal
        if iteration >= burn_in:
            points.append(tuple(float(x) for x in current))
    return tuple(points)


@dataclass(frozen=True)
class AffineGuardSampler:
    sample_count: int = 32
    strategy_id: str = "affine_guard_interior"

    def sample(self, *, bundle, evaluator, bounds, existing_candidates) -> ManifoldSampleResult:
        from .manifold import ManifoldSampleResult

        if any(candidate.guard_ok for candidate in existing_candidates):
            return ManifoldSampleResult(self.strategy_id, (), {})
        seed = min((candidate.origin_seed for candidate in existing_candidates), default=0)
        points = affine_interior_points(
            variables=bundle.var_names,
            constructions=tuple((item.name, item.expr) for item in bundle.spec.construction),
            guards=tuple(bundle.spec.guards),
            bounds=bounds,
            count=self.sample_count,
            seed=seed,
        )
        if not points:
            return ManifoldSampleResult(self.strategy_id, (), {})
        records = []
        seen = {tuple(candidate.x_float) for candidate in existing_candidates}
        next_id = max((candidate.candidate_id for candidate in existing_candidates), default=0)
        for index, point in enumerate(points):
            check_deadline()
            if point in seen:
                continue
            result = evaluator.evaluate_float_residual(point)
            if result.evaluation_status is not EvaluationStatus.OK:
                continue
            guard_ok, _ = evaluator.evaluate_guard(point)
            if not guard_ok:
                continue
            next_id += 1
            records.append(
                FloatCandidate(
                    x_float=point,
                    score=scaled_score(result.residual_vector, None),
                    residual_norm_float=result.residual_norm_float,
                    guard_ok=True,
                    evaluation_status=result.evaluation_status,
                    origin_seed=int(seed),
                    origin_start_point_index=index,
                    candidate_id=next_id,
                    hard_feasible=None,
                    origin_phase="probe",
                    origin_backend=self.strategy_id,
                    origin_evaluation_index=index,
                    hard_violation_tags=(),
                    validity_margin_float=None,
                )
            )
            seen.add(point)
        return ManifoldSampleResult(
            self.strategy_id,
            tuple(records),
            {
                "interior_point_count": len(points),
                "guard_feasible_count": len(records),
                "seed": int(seed),
            },
        )
