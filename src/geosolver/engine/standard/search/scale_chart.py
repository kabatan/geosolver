"""Add finite polynomial proposals from a proved positive scale chart."""

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate, SearchBatchResult
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.scaled_score import scaled_score
from geosolver.engine.standard.problem.positive_scale_chart import positive_scale_chart
from geosolver.engine.standard.search.algebraic_branches import _eligible
from geosolver.runtime.deadline import count_event
from geosolver.runtime.symbolic import OptionalSymbolicTimeout, request


def search_positive_scale_chart(*, bundle, evaluator):
    if (
        not getattr(bundle, "var_names", None)
        or not getattr(getattr(bundle, "spec", None), "answer_expr", None)
        or not _eligible(bundle)
    ):
        return None
    spec = bundle.spec
    variable = positive_scale_chart(
        tuple(bundle.var_names),
        tuple((item.name, item.expr) for item in spec.construction),
        tuple(zip(spec.constraints, (str(target) for target in bundle.targets), strict=True)),
        tuple(spec.guards),
        spec.answer_expr,
    )
    if variable is None:
        return None
    try:
        data = request(
            "algebraic_branches",
            {
                "variables": [name for name in bundle.var_names if name != variable],
                "construction": [(item.name, item.expr) for item in spec.construction]
                + [(variable, "1")],
                "constraints": spec.constraints,
                "targets": bundle.targets,
                "guards": spec.guards,
                "report_work": True,
            },
            timeout_seconds=1.5,
        )
    except OptionalSymbolicTimeout:
        count_event("positive_scale_chart_outer_wall_timeout")
        return None
    if data is not None and "work_telemetry" in data:
        work = data["work_telemetry"]
        reason = work.get("stop_reason")
        if reason:
            count_event("positive_scale_chart_stop_" + reason)
        phase = work.get("interrupted_phase")
        if phase:
            count_event("positive_scale_chart_interrupted_" + phase)
        for phase, values in work.get("phases", {}).items():
            for clock in ("wall", "cpu"):
                count_event(
                    f"positive_scale_chart_{phase}_{clock}_microseconds",
                    round(values[clock + "_seconds"] * 1_000_000),
                )
        data = data["result"]
    if data is None or not data["points"]:
        return None
    records = []
    chart_names = [name for name in bundle.var_names if name != variable]
    for index, chart_point in enumerate(data["points"]):
        values = {variable: "1"} | dict(zip(chart_names, chart_point, strict=True))
        decimal_point = tuple(values[name] for name in bundle.var_names)
        point = tuple(map(float, decimal_point))
        evaluation = evaluator.evaluate_float_residual(point)
        if evaluation.evaluation_status is not EvaluationStatus.OK:
            continue
        guard_ok, violations = evaluator.evaluate_guard(point)
        records.append(
            FloatCandidate(
                x_float=point,
                score=scaled_score(evaluation.residual_vector, None),
                residual_norm_float=evaluation.residual_norm_float,
                guard_ok=guard_ok,
                evaluation_status=evaluation.evaluation_status,
                origin_seed=-1,
                origin_start_point_index=index,
                candidate_id=910000 + index,
                hard_violation_tags=tuple(violations),
                origin_backend="positive_scale_chart",
                origin_evaluation_index=index,
                initial_point_decimal=tuple(decimal_point),
            )
        )
    if not records:
        return None
    return SearchBatchResult(
        candidates=tuple(records),
        all_records=tuple(records),
        evaluation_count=len(data["points"]),
        failure_ratio=(len(data["points"]) - len(records)) / len(data["points"]),
        evaluation_failure_count=len(data["points"]) - len(records),
        search_diagnostics={
            "positive_scale_chart": {
                "positive_variable": variable,
                "target_degree": 0,
                "method": data["method"],
                "branch_count": len(records),
                "original_global_search_retained": True,
            }
        },
    )
