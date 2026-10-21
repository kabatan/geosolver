"""Add starts on proven positive-radius internal-contact manifolds."""

from __future__ import annotations

import math
from dataclasses import dataclass

from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.high_precision_expressions import (
    build_solution_context_high_precision,
)
from geosolver.engine.standard.evaluation.scaled_score import scaled_score
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.positive_radius_contacts import positive_radius_contact_plans
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.runtime.deadline import check_deadline

from .affine_guards import affine_interior_points


@dataclass(frozen=True)
class PositiveRadiusContactSampler:
    strategy_id: str = "positive_radius_contact_manifold"

    def sample(self, *, bundle, evaluator, bounds, existing_candidates):
        from .manifold import ManifoldSampleResult

        spec = getattr(bundle, "spec", None)
        if spec is None or not getattr(spec, "constraints", None):
            return ManifoldSampleResult(self.strategy_id, (), {})
        definitions = tuple((item.name, item.expr) for item in spec.construction)
        plans = positive_radius_contact_plans(
            tuple(bundle.var_names),
            definitions,
            tuple(zip(spec.constraints, (str(x) for x in bundle.targets), strict=True)),
        )
        if not plans:
            return ManifoldSampleResult(self.strategy_id, (), {})
        seed = min((candidate.origin_seed for candidate in existing_candidates), default=0)
        points = [candidate.x_float for candidate in existing_candidates]
        points.extend(
            affine_interior_points(
                variables=bundle.var_names,
                constructions=definitions,
                guards=tuple(spec.guards),
                bounds=bounds,
                count=32,
                seed=seed,
            )
        )
        axes = {name: index for index, name in enumerate(bundle.var_names)}
        records = []
        seen = {tuple(candidate.x_float) for candidate in existing_candidates}
        next_id = max((candidate.candidate_id for candidate in existing_candidates), default=0)

        def project(source_point):
            point = list(source_point)
            for radius, _equation, closure in plans:
                check_deadline()
                with mp.workdps(50), high_precision_mode():
                    context = build_solution_context_high_precision(
                        spec,
                        list(bundle.var_names),
                        [mp.mpf(str(x)) for x in point],
                        bundle.base_context,
                        50,
                        expressions=[closure],
                    )
                    value = safe_eval_expr_hp(closure, context)
                point[axes[radius]] = float(value)
            return tuple(point)

        for index, source_point in enumerate(points):
            check_deadline()
            try:
                point = project(source_point)
            except TimeoutError:
                raise
            except Exception:
                continue
            point = tuple(point)
            if point in seen or not all(math.isfinite(value) for value in point):
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
        # A single remaining coordinate admits inexpensive scalar brackets.
        # Evaluate each original signed residual, retain only witnessed sign
        # changes, and submit every resulting point to the usual evaluator.
        # This adds starts; neither sampled intervals nor this heuristic box
        # assert completeness or remove the ordinary global search.
        free_axes = [axis for name, axis in axes.items() if name not in {p[0] for p in plans}]
        bracket_attempts = 0
        if len(free_axes) == 1 and len(records) > 1:
            from scipy.optimize import brentq

            axis = free_axes[0]
            ordered = sorted(records, key=lambda candidate: candidate.x_float[axis])
            root_points = []
            for left, right in zip(ordered, ordered[1:], strict=False):
                if left.x_float[axis] == right.x_float[axis]:
                    continue
                left_values = evaluator.evaluate_float_residual(left.x_float).residual_vector
                right_values = evaluator.evaluate_float_residual(right.x_float).residual_vector
                for row, (a, b) in enumerate(zip(left_values, right_values, strict=True)):
                    if a * b >= 0 or max(abs(a), abs(b)) < 1e-10:
                        continue
                    if bracket_attempts >= 32:
                        break
                    bracket_attempts += 1

                    def residual(value, base=left.x_float, index=row):
                        point = list(base)
                        point[axis] = value
                        point = project(point)
                        result = evaluator.evaluate_float_residual(point)
                        if result.evaluation_status is not EvaluationStatus.OK:
                            raise ValueError("invalid bracket interior")
                        return result.residual_vector[index]

                    try:
                        root = brentq(
                            residual,
                            left.x_float[axis],
                            right.x_float[axis],
                            xtol=1e-13,
                            rtol=1e-13,
                            maxiter=64,
                        )
                        point = list(left.x_float)
                        point[axis] = root
                        point = project(point)
                    except TimeoutError:
                        raise
                    except Exception:
                        continue
                    root_points.append(point)
            for point in root_points:
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
                        origin_start_point_index=next_id,
                        candidate_id=next_id,
                        hard_feasible=None,
                        origin_phase="probe",
                        origin_backend=self.strategy_id,
                        origin_evaluation_index=next_id,
                        hard_violation_tags=(),
                        validity_margin_float=None,
                    )
                )
                seen.add(point)
        return ManifoldSampleResult(
            self.strategy_id,
            tuple(records),
            {
                "contact_plan_count": len(plans),
                "scalar_bracket_attempts": bracket_attempts,
                "proposed_point_count": len(points),
                "guard_feasible_count": len(records),
            },
        )
