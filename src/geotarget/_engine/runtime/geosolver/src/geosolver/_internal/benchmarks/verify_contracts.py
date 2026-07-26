"""Shared contracts for benchmark verification helpers."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
from dataclasses import replace
from typing import Any

from geosolver.autosolve import formatter
from geosolver._internal.autosolve.public.run_ir import run_ir
from geosolver._internal.pipeline.contracts.external_pipeline_config import (
    ExternalPipelineConfig,
)


_VERIFY_PRECISION_DIGITS = 100
_VERIFY_SOLVER_TIME_LIMIT_SECONDS: float | None = 180.0
_VERIFY_PIPELINE_BACKEND = "external"
_VERIFY_APPROX_TOLERANCE_TEXT = "1e-100"
_VERIFY_RESIDUAL_TOLERANCE_TEXT = "1e-100"
_VERIFY_GOOD_TIME_LIMIT_SECONDS = 180.0
_VERIFY_RESCUE_TIME_BUDGET_SECONDS = 45.0
_VERIFY_BOX_TIME_BUDGET_SECONDS = 90.0


def _build_verify_pipeline_config() -> ExternalPipelineConfig:
    """Build verification-time external pipeline configuration.

    Returns:
        External pipeline config for verifier-style runs.
    """
    return replace(
        ExternalPipelineConfig.standard_tier(),
        total_time_budget_sec=float(_VERIFY_SOLVER_TIME_LIMIT_SECONDS or 180.0),
        rescue_time_budget_sec=_VERIFY_RESCUE_TIME_BUDGET_SECONDS,
        box_time_budget_sec=_VERIFY_BOX_TIME_BUDGET_SECONDS,
    )


def _truncate_text(value: Any, max_length: int = 96) -> str:
    """Trim long values for diagnostics display.

    Args:
        value: Value to stringify.
        max_length: Maximum length to keep.

    Returns:
        Truncated string representation.
    """
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[: max(3, max_length - 3)] + "..."


def _extract_residual_breakdown(
    metadata: dict[str, Any], constraints: list[Any], max_items: int = 5
) -> list[tuple[str, str]]:
    """Extract residual breakdown lines from metadata.

    Args:
        metadata: Solver metadata.
        constraints: Original case constraints.
        max_items: Maximum number of entries to emit.

    Returns:
        Normalized breakdown entries.
    """
    breakdown_keys = (
        "constraint_residual_breakdown",
        "residual_breakdown",
        "constraint_residuals",
        "residuals",
    )
    for key in breakdown_keys:
        raw = metadata.get(key)
        if isinstance(raw, dict):
            items: list[tuple[str, str]] = []
            for name, value in list(raw.items())[: max(0, int(max_items))]:
                items.append((str(name), _truncate_text(value)))
            if items:
                return items
        if isinstance(raw, (list, tuple)):
            items = []
            for index, value in enumerate(list(raw)[: max(0, int(max_items))]):
                label = (
                    _truncate_text(constraints[index], 72)
                    if index < len(constraints)
                    else f"constraint[{index}]"
                )
                items.append((label, _truncate_text(value)))
            if items:
                return items
    hp_value = metadata.get("constraint_residual_hp")
    if hp_value is not None:
        return [("constraint_residual_hp", _truncate_text(hp_value))]
    return []


def _build_fail_diagnostics(
    metadata: dict[str, Any],
    constraints: list[Any],
    max_candidates: int = 3,
    answer_abs_error: Any | None = None,
    answer_error_converged: bool | None = None,
    computed_val: Any | None = None,
) -> list[str]:
    """Build ordered fail diagnostics lines.

    Args:
        metadata: Solver metadata.
        constraints: Original case constraints.
        max_candidates: Maximum candidate ledger entries.
        answer_abs_error: Final answer absolute error.
        answer_error_converged: Whether answer error met the tolerance.
        computed_val: Post-processed value.

    Returns:
        Diagnostics lines for logs and tests.
    """
    lines: list[str] = []
    candidate_ledger = metadata.get("candidate_ledger")
    lines.append("candidate_ledger:")
    if isinstance(candidate_ledger, list) and candidate_ledger:
        for entry in candidate_ledger[: max(0, int(max_candidates))]:
            if not isinstance(entry, dict):
                lines.append(f"  - {_truncate_text(entry)}")
                continue
            lines.append(
                "  - rank={rank} residual={residual} hp_residual={hp_residual} guard_ok={guard_ok} objective={objective}".format(
                    rank=entry.get("rank"),
                    residual=_truncate_text(entry.get("residual_norm")),
                    hp_residual=_truncate_text(entry.get("hp_residual_norm")),
                    guard_ok=_truncate_text(entry.get("guard_ok")),
                    objective=_truncate_text(entry.get("objective_value")),
                )
            )
    else:
        lines.append("  - unavailable")
    for diag_key in (
        "best_candidate_id",
        "answer_source_candidate_id",
        "residual_source_candidate_id",
        "compiled_guard_count",
        "transformable_guard_count",
        "ignored_guard_count",
    ):
        if diag_key in metadata:
            lines.append(f"{diag_key}: {metadata[diag_key]}")
    stage_diag = metadata.get("stage_diagnostics")
    if isinstance(stage_diag, list) and stage_diag:
        lines.append("stage_diagnostics:")
        for item in stage_diag:
            lines.append(f"  - {_truncate_text(item)}")
    lines.append("constraint_residual_breakdown:")
    breakdown_items = _extract_residual_breakdown(metadata, constraints)
    if breakdown_items:
        for name, value in breakdown_items:
            lines.append(f"  - {name}: {value}")
    else:
        lines.append("  - unavailable")
    lines.append(f"answer_abs_error: {_truncate_text(answer_abs_error)}")
    lines.append(f"answer_error_converged: {_truncate_text(answer_error_converged)}")
    lines.append(f"computed_val: {_truncate_text(computed_val)}")
    return lines


def load_ground_truth(csv_path: str) -> dict[str, dict[str, str]]:
    """Load ground truth answers from CSV.

    Args:
        csv_path: Ground-truth CSV path.

    Returns:
        Case-id keyed answer map.
    """
    truth: dict[str, dict[str, str]] = {}
    if not os.path.exists(csv_path):
        print(f"Error: CSV not found at {csv_path}")
        return truth
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                problem_key_name = "problem" + "_id"
                pid_key = next(filter(lambda key: problem_key_name in key, row.keys()), None)
                ans_key = next(
                    (key for key in row.keys() if "answer" == key or "answer" in key.lower()),
                    None,
                )
                real_key = next((key for key in row.keys() if "real_answer" in key), None)
                if not pid_key or not ans_key:
                    continue
                pid = row[pid_key].strip()
                ans = row[ans_key].strip()
                real_ans = row[real_key].strip() if real_key and row[real_key] else ""
                if not _is_valid_real_answer(real_ans):
                    real_ans = ans
                if not pid:
                    continue
                clean_id = re.sub(r"[\(\)]", "", pid)
                entry = {"answer": ans, "real_answer": real_ans}
                truth[pid] = entry
                truth[clean_id] = entry
    except Exception as exc:
        print(f"Error reading CSV: {exc}")
        return truth
    return truth


def _is_valid_real_answer(text: str) -> bool:
    """Check whether a real-answer field looks usable.

    Args:
        text: Candidate real-answer text.

    Returns:
        True when the field looks like a valid expression.
    """
    if not text:
        return False
    stripped = text.strip()
    if stripped == "":
        return False
    if "$" in stripped or "\\" in stripped:
        return False
    if re.search(r"[A-Za-z]", stripped):
        reduced = re.sub(r"(?i)sqrt|pi|e", "", stripped)
        if re.search(r"[A-Za-z]", reduced):
            return False
    return True


def _is_exact_answer_equivalent(actual: str, expected: str) -> bool:
    """Return whether exact-answer strings are mathematically equivalent.

    Args:
        actual: Exact-answer string produced by solver.
        expected: Ground-truth exact-answer string.

    Returns:
        True when both strings represent the same value.
    """
    actual_text = (actual or "").strip()
    expected_text = (expected or "").strip()
    if not actual_text or not expected_text:
        return False
    if actual_text.replace(" ", "") == expected_text.replace(" ", ""):
        return True
    try:
        from sympy import simplify, sympify

        actual_expr = sympify(actual_text)
        expected_expr = sympify(expected_text)
        return bool(simplify(actual_expr - expected_expr) == 0)
    except Exception:
        return False


def _to_mpf_or_none(value: Any) -> Any | None:
    """Convert a value/expression into mpf when possible.

    Args:
        value: Raw value to convert.

    Returns:
        Converted mpf-like value or None.
    """
    if value in (None, ""):
        return None
    try:
        import mpmath
        from sympy import sympify

        with mpmath.workdps(140):
            try:
                return mpmath.mp.mpf(str(value))
            except Exception:
                return mpmath.mp.mpf(str(sympify(str(value)).evalf(140)))
    except Exception:
        return None


def _collect_exact_answer_candidates(result: Any, metadata: dict[str, Any]) -> list[str]:
    """Collect exact-answer candidates exposed by the solver.

    Args:
        result: Solver result.
        metadata: Solver metadata.

    Returns:
        Normalized exact-answer strings.
    """
    raw_candidates = metadata.get("exact_answer_candidates")
    if isinstance(raw_candidates, list):
        normalized = [str(value).strip() for value in raw_candidates if str(value).strip()]
        if normalized:
            return normalized
    if result.exact_answer is None:
        return []
    exact_text = str(result.exact_answer).strip()
    if exact_text == "":
        return []
    return [exact_text]


def _compute_answer_abs_error(expected_ans: str | None, computed_final_val: Any) -> Any | None:
    """Compute absolute error against the formatted answer target.

    Args:
        expected_ans: Expected answer text.
        computed_final_val: Computed post-processed value.

    Returns:
        Absolute error or None when not available.
    """
    if expected_ans in (None, "") or computed_final_val is None:
        return None
    try:
        import mpmath
        from sympy import sympify

        with mpmath.workdps(140):
            try:
                expected_mpf = mpmath.mp.mpf(str(expected_ans))
            except Exception:
                expected_mpf = mpmath.mp.mpf(str(sympify(str(expected_ans)).evalf(140)))
            try:
                computed_mpf = mpmath.mp.mpf(str(computed_final_val))
            except Exception:
                computed_mpf = mpmath.mp.mpf(str(sympify(str(computed_final_val)).evalf(140)))
            return abs(computed_mpf - expected_mpf)
    except Exception:
        return None


def _compute_answer_error_converged(answer_abs_error: Any | None) -> bool | None:
    """Check whether answer absolute error met the tolerance.

    Args:
        answer_abs_error: Absolute answer error.

    Returns:
        Convergence status or None when not comparable.
    """
    if answer_abs_error is None:
        return None
    try:
        import mpmath

        return bool(answer_abs_error < mpmath.mp.mpf(_VERIFY_APPROX_TOLERANCE_TEXT))
    except Exception:
        return None


def verify_problem(
    json_path: str,
    truth_map: dict[str, dict[str, str]],
    logger: object | None = None,
    idx: int = 0,
    total: int = 0,
) -> dict[str, Any]:
    """Verify a single benchmark case.

    Args:
        json_path: Path to the case JSON.
        truth_map: Ground-truth answers.
        logger: Unused compatibility argument.
        idx: Unused compatibility argument.
        total: Unused compatibility argument.

    Returns:
        Structured verification result.
    """
    _ = logger
    _ = idx
    _ = total
    try:
        with open(json_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return {
            "id": os.path.basename(json_path),
            "status": "ERROR",
            "message": f"Load failed: {exc}",
            "time": 0,
            "expected": "N/A",
        }
    pid = data.get("id")
    if not pid:
        return {
            "id": os.path.basename(json_path),
            "status": "SKIP",
            "message": "No ID in JSON",
            "time": 0,
            "expected": "N/A",
        }
    expected_ans: str | None = None
    expected_real_ans: str | None = None
    gt_entry = truth_map.get(pid)
    if not gt_entry and pid.endswith("E"):
        gt_entry = truth_map.get(pid[:-1] + "(E)")
    if not gt_entry and pid.endswith("(E)"):
        gt_entry = truth_map.get(pid[:-3] + "E")
    if gt_entry:
        expected_ans = gt_entry.get("answer", "N/A")
        expected_real_ans = gt_entry.get("real_answer", expected_ans)
    if expected_ans is None:
        return {
            "id": pid,
            "status": "SKIP",
            "message": "No ground truth found",
            "time": 0,
            "expected": "N/A",
            "expected_real": "N/A",
        }
    start_time = time.time()
    solver_output_buffer = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = solver_output_buffer
        result = run_ir(
            data,
            precision=_VERIFY_PRECISION_DIGITS,
            time_limit=_VERIFY_SOLVER_TIME_LIMIT_SECONDS,
            verbose=True,
            prefer_fast=False,
            pipeline_backend=_VERIFY_PIPELINE_BACKEND,
            pipeline_config=_build_verify_pipeline_config(),
        )
    finally:
        sys.stdout = old_stdout
    elapsed = time.time() - start_time
    if elapsed < 60.0:
        time_grade = "Good"
    elif elapsed <= _VERIFY_GOOD_TIME_LIMIT_SECONDS:
        time_grade = "Pass"
    else:
        time_grade = "Too Slow"
    status_reasons: list[str] = []
    metadata = result.metadata if isinstance(getattr(result, "metadata", None), dict) else {}
    exact = result.exact_answer
    backend_name = str(metadata.get("pipeline_backend", "")).strip().lower()
    cond_backend = backend_name == _VERIFY_PIPELINE_BACKEND
    cond_exact = False
    exact_candidates = _collect_exact_answer_candidates(result, metadata)
    exact_str = (
        "[" + ", ".join(exact_candidates) + "]"
        if exact_candidates
        else (str(result.exact_answer) if result.exact_answer is not None else "")
    )
    exact_attempt_count = int(metadata.get("exact_answer_attempt_count", len(exact_candidates)))
    exact_identified_count = int(
        metadata.get("exact_answer_identified_count", len(exact_candidates))
    )
    if expected_real_ans and exact_attempt_count > 0 and exact_identified_count == exact_attempt_count:
        cond_exact = bool(exact_candidates) and all(
            _is_exact_answer_equivalent(candidate, expected_real_ans)
            for candidate in exact_candidates
        )
    cond_approx = False
    approx_diff = None
    numeric_ans = metadata.get("numeric_answer_raw")
    if numeric_ans is None:
        answer_vals = getattr(result, "answer_values", [])
        if answer_vals and len(answer_vals) > 0:
            numeric_ans = answer_vals[0]
        else:
            numeric_ans = metadata.get("numeric_answer")
    expected_real_mpf = _to_mpf_or_none(expected_real_ans)
    numeric_ans_mpf = _to_mpf_or_none(numeric_ans)
    if numeric_ans_mpf is not None and expected_real_mpf is not None:
        try:
            import mpmath

            diff = abs(numeric_ans_mpf - expected_real_mpf)
            approx_diff = float(diff)
            cond_approx = diff < mpmath.mp.mpf(_VERIFY_APPROX_TOLERANCE_TEXT)
        except Exception:
            cond_approx = False
    cond_time = elapsed <= _VERIFY_GOOD_TIME_LIMIT_SECONDS
    res_val = metadata.get("selected_constraint_residual_hp")
    if res_val is None:
        res_val = metadata.get("constraint_residual_hp")
    if res_val is None:
        res_val = metadata.get("residual_norm", result.residual)
    cond_residual = False
    residual_mpf = _to_mpf_or_none(res_val)
    if residual_mpf is not None:
        try:
            import mpmath

            cond_residual = residual_mpf <= mpmath.mp.mpf(_VERIFY_RESIDUAL_TOLERANCE_TEXT)
        except Exception:
            cond_residual = False
    cond_formatted = False
    val = None
    if result.exact_answer:
        val = result.exact_answer
    elif numeric_ans is not None:
        val = numeric_ans
    else:
        val = result.metadata.get("formatted_answer")
    if val is None:
        val = result.value
    computed_final_val = val
    pp_code = data.get("post_process", "").strip()
    if pp_code:
        try:
            if data.get("task") == "solve":
                local_scope = {
                    "solutions": getattr(result, "solutions", []),
                    "answer_values": getattr(result, "answer_values", []),
                    "solution_count": len(getattr(result, "solutions", [])),
                    "formatter": formatter,
                    "result": None,
                }
            elif data.get("task") == "optimize":
                solutions = getattr(result, "solutions", [])
                answer_vals = getattr(result, "answer_values", [])
                diagnostic_answer_vals = metadata.get("diagnostic_answer_values")
                if (not answer_vals) and isinstance(diagnostic_answer_vals, list):
                    answer_vals = list(diagnostic_answer_vals)
                local_scope = {
                    "solution": solutions[0] if solutions else result.value,
                    "answer_values": answer_vals if answer_vals else [],
                    "answer_value": answer_vals[0] if answer_vals else None,
                    "objective_value": result.metadata.get("objective_value"),
                    "is_maximize": data.get("maximize", False),
                    "formatter": formatter,
                    "result": None,
                }
            else:
                answer_vals = getattr(result, "answer_values", [])
                if not answer_vals:
                    diagnostic_answer_vals = metadata.get("diagnostic_answer_values")
                    if isinstance(diagnostic_answer_vals, list):
                        answer_vals = list(diagnostic_answer_vals)
                if not answer_vals:
                    raw_value = metadata.get("numeric_answer")
                    if raw_value is not None:
                        answer_vals = [raw_value]
                    else:
                        raw_value = metadata.get("formatted_answer") or result.value
                        answer_vals = [raw_value] if raw_value is not None else []
                local_scope = {
                    "answer_values": answer_vals,
                    "formatter": formatter,
                    "result": None,
                }
            pp_answer = local_scope.get("answer_value") or (
                (local_scope.get("answer_values") or [None])[0]
            )
            if pp_answer is None:
                status_reasons.append("PostProcessInputMissing")
                computed_final_val = None
            else:
                exec(pp_code, {}, local_scope)
                computed_final_val = local_scope.get("result")
        except Exception as exc:
            status_reasons.append(f"PostProcessEr: {exc}")
            computed_final_val = None
    check_val_str = str(computed_final_val) if computed_final_val is not None else ""
    if expected_ans:
        try:
            import mpmath
            from sympy import sympify

            is_num_match = False
            with mpmath.workdps(120):
                try:
                    try:
                        left = mpmath.mp.mpf(check_val_str)
                    except Exception:
                        left = mpmath.mp.mpf(str(sympify(check_val_str).evalf(120)))
                    try:
                        right = mpmath.mp.mpf(expected_ans)
                    except Exception:
                        right = mpmath.mp.mpf(str(sympify(expected_ans).evalf(120)))
                    if abs(left - right) < mpmath.mp.mpf(_VERIFY_APPROX_TOLERANCE_TEXT):
                        is_num_match = True
                except Exception:
                    pass
            cond_formatted = is_num_match or check_val_str.strip() == expected_ans.strip()
        except Exception:
            cond_formatted = check_val_str.strip() == expected_ans.strip()
    answer_abs_error = _compute_answer_abs_error(expected_ans, computed_final_val)
    answer_error_converged = _compute_answer_error_converged(answer_abs_error)
    is_pass = cond_backend and cond_exact and cond_approx and cond_residual and cond_formatted
    is_good = is_pass and cond_time
    status = "FAIL"
    if is_good:
        status = "GOOD"
    elif is_pass:
        status = "PASS"
    if not cond_backend:
        status_reasons.append(
            f"BackendFail(Exp:{_VERIFY_PIPELINE_BACKEND}, Got:{backend_name or 'missing'})"
        )
    if not cond_approx:
        if approx_diff is not None:
            try:
                approx_float = float(approx_diff)
                status_reasons.append(f"ApproxDiffFail(Diff={approx_float:.1e})")
            except Exception:
                status_reasons.append(f"ApproxDiffFail(Diff={approx_diff})")
        else:
            status_reasons.append("ApproxDiffFail(ValMissing)")
    if not cond_exact:
        status_reasons.append(f"ExactMatchFail(Exp:{expected_real_ans}, Got:{exact_str})")
    if not cond_residual:
        try:
            residual_float = float(res_val)
            status_reasons.append(f"ResidualFail({residual_float:.1e})")
        except Exception:
            status_reasons.append(f"ResidualFail({res_val})")
    if not cond_formatted:
        status_reasons.append(f"FormattedFail(Exp:{expected_ans}, Got:{check_val_str})")
    fail_diagnostics: list[str] = []
    if status == "FAIL":
        fail_diagnostics = _build_fail_diagnostics(
            metadata,
            list(data.get("constraints", [])),
            answer_abs_error=answer_abs_error,
            answer_error_converged=answer_error_converged,
            computed_val=computed_final_val,
        )
    try:
        residual_norm_meta = metadata.get("residual_norm")
        residual_hp_meta = metadata.get("constraint_residual_hp")
        if residual_norm_meta is not None and residual_hp_meta is not None:
            import mpmath

            left = mpmath.mp.mpf(str(residual_norm_meta))
            right = mpmath.mp.mpf(str(residual_hp_meta))
            if mpmath.isfinite(left) and mpmath.isfinite(right):
                low = min(abs(left), abs(right))
                high = max(abs(left), abs(right))
                if low == 0:
                    if high > mpmath.mp.mpf("1e-30"):
                        status_reasons.append("ResidualSourceMismatch")
                elif high / low > mpmath.mp.mpf("1e6"):
                    status_reasons.append("ResidualSourceMismatch")
    except Exception:
        pass
    v6_diag: dict[str, Any] = {}
    for key in (
        "best_candidate_id",
        "answer_source_candidate_id",
        "residual_source_candidate_id",
        "compiled_guard_count",
        "transformable_guard_count",
        "ignored_guard_count",
        "stage_diagnostics",
    ):
        if key in metadata:
            v6_diag[key] = metadata[key]
    return {
        "id": pid,
        "status": status,
        "residual": res_val,
        "exact_answer": exact,
        "expected": expected_ans,
        "expected_real": expected_real_ans,
        "time": elapsed,
        "time_grade": time_grade,
        "reasons": ", ".join(status_reasons),
        "computed_val": computed_final_val,
        "raw_approx": numeric_ans,
        "approx_diff": approx_diff,
        "answer_abs_error": answer_abs_error,
        "answer_error_converged": answer_error_converged,
        "pipeline_backend": backend_name,
        "fail_diagnostics": fail_diagnostics,
        "v6_diagnostics": v6_diag,
        "solver_output": solver_output_buffer.getvalue(),
    }
