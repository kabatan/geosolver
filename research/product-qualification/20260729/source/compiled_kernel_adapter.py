"""Frozen-reference adapter for the standalone compiled-kernel gate."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import math
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from geotarget import compiled_evaluator
from geotarget.compiled_evaluator import CompiledResidualEvaluator
from geotarget.continuation import _load_frozen
from geotarget.kernel_qualification import Observation


def _source_sha256(problem: Mapping[str, Any]) -> str:
    payload = (
        json.dumps(
            problem,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _nonfinite(values: tuple[float, ...]) -> tuple[str, ...]:
    result = []
    for value in values:
        if math.isnan(value):
            result.append("nan")
        elif value == math.inf:
            result.append("positive_infinity")
        elif value == -math.inf:
            result.append("negative_infinity")
        else:
            result.append("finite")
    return tuple(result)


def _snapshot(evaluator: Any, point: np.ndarray) -> Observation:
    exception_type = None
    exception_stage = None
    selection_rows: tuple[str, ...] = ()
    try:
        from geosolver._internal.pipeline.evaluator.selection_trace import (
            capture_selection_trace,
        )

        with capture_selection_trace() as selection_trace:
            residual = evaluator.evaluate_float_residual(point.tolist())
        selection_rows = tuple(
            f"{entry.symbol_name}:{entry.selector_kind}:"
            f"{entry.candidate_count}:{entry.selected_index}"
            for entry in selection_trace
        )
        residuals = tuple(float(value) for value in residual.residual_vector)
        residual_norm = float(residual.residual_norm_float)
        status = str(getattr(residual.evaluation_status, "value", residual.evaluation_status))
        finite = bool(residual.is_finite)
    except Exception as error:
        residuals = ()
        residual_norm = math.nan
        status = "exception"
        finite = False
        exception_type = type(error).__name__
        exception_stage = "residual"
    try:
        guard_ok, guard_violations = evaluator.evaluate_guard(point.tolist())
    except Exception as error:
        guard_ok, guard_violations = False, (f"{type(error).__name__}: {error}",)
        exception_type = exception_type or type(error).__name__
        exception_stage = exception_stage or "guard"
    try:
        hard = evaluator.evaluate_float_hard_feasibility(point.tolist())
        hard_feasible = bool(hard.hard_feasible)
        hard_tags = tuple(str(value) for value in hard.failure_tags)
        hard_min_margin = (
            None if hard.min_margin is None else float(hard.min_margin)
        )
    except Exception as error:
        hard_feasible = False
        hard_tags = (f"{type(error).__name__}: {error}",)
        hard_min_margin = None
        exception_type = exception_type or type(error).__name__
        exception_stage = exception_stage or "hard_feasibility"
    classifications = _nonfinite((*residuals, residual_norm))
    return Observation(
        values=(residual_norm,),
        residuals=residuals,
        guard_outcomes=(bool(guard_ok),),
        guard_violations=tuple(str(value) for value in guard_violations),
        hard_feasible=hard_feasible,
        hard_failure_tags=hard_tags,
        hard_min_margin=hard_min_margin,
        threshold_decisions=(status, f"is_finite={str(finite).lower()}"),
        selector_trace=selection_rows,
        exception_type=exception_type,
        exception_stage=exception_stage,
        nonfinite_classification=classifications,
        status=status,
    )


SELECTOR_NAMES = frozenset(
    {"near", "far", "exclude", "first", "branch", "vertex", "side", "orientation"}
)


def _opcode_selector_sets(
    problem: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    expressions = [
        *(str(item.get("expr", "")) for item in problem.get("construction", ())),
        *(str(item.get("def", "")) for item in problem.get("constraints", ())),
        *(
            str(item.get("value", ""))
            for item in problem.get("constraints", ())
            if isinstance(item.get("value"), str)
        ),
        *(str(item) for item in problem.get("guards", ())),
        str(problem.get("answer", "")),
        str(problem.get("post_process", "")),
    ]
    opcodes = set()
    selectors = set()
    for expression in expressions:
        if not expression.strip():
            continue
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            opcodes.add("ParseError")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Name):
                    opcodes.add(function.id)
                elif isinstance(function, ast.Attribute):
                    opcodes.add(function.attr)
                selectors.update(
                    keyword.arg
                    for keyword in node.keywords
                    if keyword.arg in SELECTOR_NAMES
                )
            elif isinstance(node, ast.operator | ast.boolop | ast.cmpop | ast.unaryop):
                opcodes.add(type(node).__name__)
    return sorted(opcodes), sorted(selectors)


def _diagnostic_support_trace(problem: Mapping[str, Any]) -> dict[str, Any]:
    opcodes, selectors = _opcode_selector_sets(problem)
    return {
        "ast_opcode_set": opcodes,
        "resolved_operand_result_type_set": [],
        "selector_kind_set": selectors,
        "semantic_abi_version": "",
        "support_key_sha256": "",
        "problem_id_read": False,
        "corpus_membership_read": False,
        "truth_read": False,
        "answer_count_read": False,
    }


@dataclass
class _Prepared:
    reference_evaluator: Any
    candidate_evaluator: Any
    dimension: int
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    compiled_supported: bool
    fallback_reason: str | None
    support_decision_trace: Mapping[str, Any]

    def reference(self, point: np.ndarray) -> Observation:
        return _snapshot(self.reference_evaluator, point)

    def candidate(self, point: np.ndarray) -> Observation:
        return _snapshot(self.candidate_evaluator, point)

    def optimizer_replay_probes(self) -> tuple[Mapping[str, Any], ...]:
        # Formal qualification supplies frozen optimizer traces explicitly.
        return ()


class CompiledKernelQualificationAdapter:
    def __init__(self) -> None:
        runtime_root = Path(__file__).resolve().parent / "_engine/runtime"
        solver_root = runtime_root / "solver"
        geosolver_source = runtime_root / "geosolver/src"
        for path in (solver_root, geosolver_source):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        self.base = _load_frozen(runtime_root)
        self.runtime = self.base._load_module(
            "geotarget_kernel_qualification_runtime", self.base.PRECISION_RUNTIME
        )

    def compiler_manifest(self) -> Mapping[str, Any]:
        factory = getattr(compiled_evaluator, "compiler_manifest", None)
        if factory is None:
            return {
                "case_specific_routing": None,
                "support_decision_basis": "unverified",
                "forbidden_support_inputs": [],
            }
        return factory()

    def support_decision_source(self) -> str:
        function = getattr(compiled_evaluator, "supports_compilation_key", None)
        if function is None:
            return "def supports(problem_id):\n    return False\n"
        return inspect.getsource(function)

    def qualification_capabilities(self) -> Mapping[str, Any]:
        # This adapter compares callback observations only. It neither runs the
        # real optimizer/candidate ledger nor the product worker pool, so it
        # must not self-certify those independent production gates.
        return {
            "optimizer_replay": False,
            "candidate_records": False,
            "actual_parallel_execution": False,
            "parallel_core_counts": [],
        }

    def prepare(self, problem: Mapping[str, Any], *, cores: int) -> _Prepared:
        del cores
        source_sha256 = _source_sha256(problem)
        case, _budget, reference = self.runtime.build_source_case(
            dict(problem),
            callback_cap=10_000_000,
            deadline=time.monotonic() + 24 * 60 * 60,
        )
        compilation = compiled_evaluator.compile_residual_plan(
            reference, source_sha256=source_sha256
        )
        trace_factory = getattr(compiled_evaluator, "support_decision_trace", None)
        support_trace = (
            _diagnostic_support_trace(problem)
            if trace_factory is None
            else trace_factory(problem, compilation)
        )
        candidate = (
            reference
            if compilation.plan is None
            else CompiledResidualEvaluator(reference, compilation.plan)
        )
        return _Prepared(
            reference_evaluator=reference,
            candidate_evaluator=candidate,
            dimension=int(case.dimension),
            lower=tuple(float(value) for value in case.lower),
            upper=tuple(float(value) for value in case.upper),
            compiled_supported=compilation.plan is not None,
            fallback_reason=compilation.fallback_reason,
            support_decision_trace=support_trace,
        )


def create_adapter() -> CompiledKernelQualificationAdapter:
    return CompiledKernelQualificationAdapter()
