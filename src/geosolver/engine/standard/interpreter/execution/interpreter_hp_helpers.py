"""High-precision helper functions shared by interpreter execution modes."""

from __future__ import annotations

from typing import Any
from mpmath import mp

from geosolver.engine.standard.interpreter.answer import _eval_exact_to_mpf
from geosolver.engine.standard.precision.type_guards.ensure_no_float import (
    ensure_no_float,
)
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
    high_precision_mode,
)
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf

from .interpreter_helpers import CandidateEval, evaluate_candidate


def evaluate_candidate_entry(
    values: list[Any],
    *,
    residual_fn,
    guard_fn,
    objective_fn,
    degeneracy_fn=None,
    reject_float: bool = False,
    candidate_id: int | None = None,
) -> CandidateEval:
    return evaluate_candidate(
        values,
        residual_evaluator=residual_fn,
        guard_evaluator=guard_fn,
        objective_evaluator=objective_fn,
        degeneracy_evaluator=degeneracy_fn,
        reject_float=bool(reject_float),
        candidate_id=candidate_id,
    )


def evaluate_candidate_residual_high_precision(
    values: list[Any],
    *,
    residual_fn_hp,
    precision: int,
) -> list[Any]:
    with high_precision_mode():
        normalized = [
            to_mpf_value(value, precision=int(precision), context="candidate_residual_input")
            for value in values
        ]
        ensure_no_float(normalized, context="candidate_residual_input")
        residuals = residual_fn_hp(normalized)
        ensure_no_float(residuals, context="candidate_residual_output")
        return list(residuals)


def evaluate_candidate_objective_high_precision(
    values: list[Any],
    *,
    objective_fn_hp,
    precision: int,
) -> Any:
    with high_precision_mode():
        normalized = [
            to_mpf_value(value, precision=int(precision), context="candidate_objective_input")
            for value in values
        ]
        ensure_no_float(normalized, context="candidate_objective_input")
        objective = objective_fn_hp(normalized)
        ensure_no_float(objective, context="candidate_objective_output")
        return objective


def to_mpf_value(value: Any, *, precision: int, context: str) -> Any:
    if isinstance(value, str):
        return _eval_exact_to_mpf(value, int(precision))
    if isinstance(value, float):
        raise HighPrecisionContaminationError(
            f"float value reached Stage C at {context}: {value!r}. "
            "Use boundary_float_to_mpf() outside high_precision_mode() to convert Zone A floats."
        )
    return strict_to_mpf(value, context=context)


def normalize_solution_values_for_hp(
    values: list[Any],
    *,
    precision: int,
    context: str,
) -> list[Any]:
    return [
        to_mpf_value(
            value,
            precision=int(precision),
            context=f"{context}[{index}]",
        )
        for index, value in enumerate(values)
    ]


def normalize_solution_list_for_hp(
    values: list[Any],
    *,
    precision: int,
    context: str,
) -> list[Any]:
    normalized: list[Any] = []
    for index, solution in enumerate(values):
        if isinstance(solution, list):
            normalized.append(
                normalize_solution_values_for_hp(
                    solution,
                    precision=int(precision),
                    context=f"{context}[{index}]",
                )
            )
            continue
        normalized.append(
            to_mpf_value(
                solution,
                precision=int(precision),
                context=f"{context}[{index}]",
            )
        )
    return normalized


def collect_hp_float_return_symbols(
    context: dict[str, Any],
    destination: list[str] | None,
) -> None:
    if not isinstance(destination, list):
        return
    collector = context.get("_hp_get_float_return_symbols")
    if not callable(collector):
        return
    try:
        symbols = collector()
    except Exception:
        return
    for symbol in symbols:
        symbol_name = str(symbol)
        if symbol_name not in destination:
            destination.append(symbol_name)


def extract_hp_float_contamination(metadata: dict[str, Any]) -> tuple[int, list[str]]:
    contamination_count = 0
    examples: list[str] = []

    float_origin_count = metadata.get("float_origin_count", 0)
    try:
        float_origin = int(float_origin_count)
    except Exception:
        float_origin = 0
    if float_origin > 0:
        contamination_count += float_origin
        examples.append(f"float_origin_count={float_origin}")

    candidate_eval_error_count = metadata.get("candidate_eval_error_count", 0)
    try:
        candidate_eval_errors = int(candidate_eval_error_count)
    except Exception:
        candidate_eval_errors = 0
    if candidate_eval_errors > 0:
        contamination_count += candidate_eval_errors
        examples.append(f"candidate_eval_error_count={candidate_eval_errors}")
        error_examples = metadata.get("candidate_eval_error_examples")
        if isinstance(error_examples, list):
            for entry in error_examples:
                entry_text = str(entry)
                if not entry_text:
                    continue
                examples.append(f"candidate_eval_error:{entry_text}")
                if len(examples) >= 5:
                    break

    symbols = metadata.get("hp_float_return_symbols")
    if isinstance(symbols, list):
        symbol_names = [str(symbol) for symbol in symbols if str(symbol)]
        contamination_count += len(symbol_names)
        examples.extend([f"hp_float_return_symbol:{name}" for name in symbol_names[:5]])

    return contamination_count, examples[:5]
