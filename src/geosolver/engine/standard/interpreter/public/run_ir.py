"""Clean run_ir() orchestrator for autosolve public API."""

from typing import Any

from mpmath import mp

from geosolver.engine.standard.interpreter.answer.eval_to_mpf import _eval_exact_to_mpf
from geosolver.engine.standard.interpreter.answer.wrap_value import _wrap_exact_value
from geosolver.core.result import SolveResult, SolveStatus
from geosolver.engine.standard.orchestration.run_external_pipeline import (
    run_external_pipeline,
)
from .run_ir_input import normalize_run_ir_input

BACKEND_EXTERNAL = "external"


def _build_context(context_builder: Any, prefer_fast: bool) -> dict[str, Any]:
    try:
        return context_builder(prefer_fast=prefer_fast)
    except TypeError:
        return context_builder()


def _extract_fallback_answers_from_refined(external_result: Any) -> list[Any]:
    refined_candidates = tuple(getattr(external_result, "refined_candidates", ()))
    if not refined_candidates:
        return []
    ranked: list[tuple[Any, Any]] = []
    for candidate in refined_candidates:
        answer_hp = getattr(candidate, "answer_hp", None)
        residual_norm_hp = getattr(candidate, "residual_norm_hp", None)
        if answer_hp is None or residual_norm_hp is None:
            continue
        if (not mp.isfinite(answer_hp)) or (not mp.isfinite(residual_norm_hp)):
            continue
        ranked.append((residual_norm_hp, answer_hp))
    if not ranked:
        return []
    ranked.sort(key=lambda item: item[0])
    dedup_tolerance = mp.mpf("1e-20")
    selected: list[Any] = []
    for _residual, answer in ranked:
        if any(abs(answer - existing) <= dedup_tolerance for existing in selected):
            continue
        selected.append(answer)
    return selected


def _extract_external_residual(summary: dict[str, Any]) -> Any:
    refinement = summary.get("refinement")
    if not isinstance(refinement, dict):
        return float("inf")
    best_residual = refinement.get("best_residual")
    if best_residual is None:
        return float("inf")
    try:
        return mp.mpf(best_residual)
    except Exception:
        return float("inf")


def _extract_exact_payload(external_result: Any) -> tuple[Any | None, list[int] | None, Any | None]:
    exact_results = tuple(getattr(external_result, "exact_results", ()))
    for exact_result in exact_results:
        exact_value = getattr(exact_result, "selected_exact_value", None)
        if exact_value is None:
            continue
        minimal_poly = getattr(exact_result, "minimal_polynomial", None)
        numeric_value = _eval_exact_to_mpf(exact_value, precision=120)
        minimal_poly_list = None if minimal_poly is None else [int(value) for value in minimal_poly]
        return exact_value, minimal_poly_list, numeric_value
    for exact_result in exact_results:
        numeric_fallback = getattr(exact_result, "numeric_fallback_value", None)
        if numeric_fallback is None:
            continue
        if not mp.isfinite(numeric_fallback):
            continue
        minimal_poly = getattr(exact_result, "minimal_polynomial", None)
        minimal_poly_list = None if minimal_poly is None else [int(value) for value in minimal_poly]
        return None, minimal_poly_list, numeric_fallback
    return None, None, None


def _extract_exact_candidates(external_result: Any) -> tuple[list[str], int, int]:
    """Extract all exact-answer candidates and exact-identification counts."""
    exact_results = tuple(getattr(external_result, "exact_results", ()))
    candidates = [
        str(getattr(exact_result, "selected_exact_value", "")).strip()
        for exact_result in exact_results
        if getattr(exact_result, "selected_exact_value", None) is not None
        and str(getattr(exact_result, "selected_exact_value", "")).strip()
    ]
    return candidates, len(exact_results), len(candidates)


def _to_solve_result_from_external(external_result: Any) -> SolveResult:
    status = (
        SolveStatus.SUCCESS
        if getattr(external_result, "status", "") == "success"
        else SolveStatus.NO_SOLUTION
    )
    accepted_answers = tuple(getattr(external_result, "accepted_answers", ()))
    if accepted_answers:
        answer_values = list(accepted_answers)
    else:
        selected_answer = getattr(external_result, "selected_answer", None)
        if selected_answer is not None:
            answer_values = [selected_answer]
        else:
            answer_values = _extract_fallback_answers_from_refined(external_result)
    summary = dict(getattr(external_result, "summary", {}))
    exact_value, minimal_polynomial, exact_numeric = _extract_exact_payload(external_result)
    exact_candidates, exact_attempt_count, exact_identified_count = _extract_exact_candidates(
        external_result
    )
    if exact_numeric is not None:
        summary["numeric_answer_raw"] = exact_numeric
        summary["numeric_answer"] = exact_numeric
    elif answer_values:
        summary["numeric_answer_raw"] = answer_values[0]
        summary["numeric_answer"] = answer_values[0]
    if answer_values:
        summary["diagnostic_answer_values"] = list(answer_values)
    summary["exact_answer_candidates"] = list(exact_candidates)
    summary["exact_answer_attempt_count"] = int(exact_attempt_count)
    summary["exact_answer_identified_count"] = int(exact_identified_count)
    summary["pipeline_backend"] = BACKEND_EXTERNAL
    residual = _extract_external_residual(summary)
    exact_answer = None
    if exact_value is not None:
        exact_answer = _wrap_exact_value(exact_value, precision=120)
    return SolveResult(
        status=status,
        value=None,
        answer_values=answer_values,
        exact_answer=exact_answer,
        minimal_polynomial=minimal_polynomial,
        metadata=summary,
        residual=residual,
    )


def run_ir(ir: Any, **kwargs: Any) -> SolveResult:
    """Run IR via external pipeline orchestrator."""
    normalized = normalize_run_ir_input(dict(kwargs))

    context = _build_context(normalized.context_builder, prefer_fast=normalized.prefer_fast)
    if normalized.guard_probe is not None:
        ok, message = normalized.guard_evaluator(normalized.guard_probe, context, kwargs)
        if not ok:
            return SolveResult(status=SolveStatus.INVALID_INPUT, errors=[str(message)])
    if normalized.answer_probe is not None:
        normalized.answer_evaluator(*normalized.answer_probe)

    external_kwargs: dict[str, Any] = {
        "prefer_fast": normalized.prefer_fast,
    }
    if normalized.seed is not None:
        external_kwargs["seed"] = normalized.seed
    if normalized.nomad_config is not None:
        external_kwargs["nomad_config"] = normalized.nomad_config
    if normalized.pipeline_config is not None:
        external_kwargs["pipeline_config"] = normalized.pipeline_config
    if normalized.box_solver is not None:
        external_kwargs["box_solver"] = normalized.box_solver
    external_result = run_external_pipeline(
        ir,
        **external_kwargs,
    )
    return _to_solve_result_from_external(external_result)
