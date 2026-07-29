"""Production callback adapter for the identity-free same-work performance gate."""

from __future__ import annotations

import ast
import copy
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from geotarget.compiled_kernel_adapter import (
    CompiledKernelQualificationAdapter,
)
from geotarget.same_work_performance import SameWorkload, _canonical_sha256


def _expressions(problem: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        [str(row.get("expr", "")) for row in problem.get("construction", ())]
        + [str(row.get("def", "")) for row in problem.get("constraints", ())]
        + [str(row.get("value", "")) for row in problem.get("constraints", ())]
        + [str(row) for row in problem.get("guards", ())]
        + [str(problem.get("answer", ""))]
    )


def structural_profile(problem: Mapping[str, Any]) -> dict[str, Any]:
    """Describe expression shape without consulting id, corpus, truth, or answers."""

    constructions = list(problem.get("construction", ()))
    names = {str(row.get("name", "")) for row in constructions}
    depth: dict[str, int] = {}
    consumers: Counter[str] = Counter()
    opcodes: Counter[str] = Counter()
    maximum_arity = 0
    for row in constructions:
        name = str(row.get("name", ""))
        expression = str(row.get("expr", ""))
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            depth[name] = 1
            continue
        dependencies = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} & names
        for dependency in dependencies:
            consumers[dependency] += 1
        depth[name] = 1 + max((depth.get(dependency, 0) for dependency in dependencies), default=0)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                function = node.func
                opcode = function.id if isinstance(function, ast.Name) else type(function).__name__
                opcodes[opcode] += 1
                maximum_arity = max(maximum_arity, len(node.args) + len(node.keywords))
    ast_nodes = 0
    for expression in _expressions(problem):
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            continue
        ast_nodes += sum(1 for _ in ast.walk(tree))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                function = node.func
                opcode = function.id if isinstance(function, ast.Name) else type(function).__name__
                opcodes[opcode] += 1
                maximum_arity = max(maximum_arity, len(node.args) + len(node.keywords))
    consumer_expressions = tuple(
        [str(row.get("def", "")) for row in problem.get("constraints", ())]
        + [str(row.get("value", "")) for row in problem.get("constraints", ())]
        + [str(row) for row in problem.get("guards", ())]
        + [str(problem.get("answer", ""))]
    )
    for expression in consumer_expressions:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            continue
        consumers.update(
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id in names
        )
    maximum_depth = max(depth.values(), default=0)
    maximum_fanout = max(consumers.values(), default=0)
    tags = []
    if maximum_depth >= 8:
        tags.append("deep_dag")
    if maximum_fanout >= 8:
        tags.append("high_fanout")
    if maximum_arity >= 8 or ast_nodes >= 256:
        tags.append("wide_expression")
    return {
        "structural_class": "+".join(tags) if tags else "general_v15",
        "construction_depth": maximum_depth,
        "maximum_fanout": maximum_fanout,
        "maximum_call_arity": maximum_arity,
        "ast_nodes": ast_nodes,
        "opcode_counts": dict(sorted(opcodes.items())),
    }


def _proposals(
    starts: int, callbacks_per_start: int, dimension: int
) -> tuple[tuple[float, ...], ...]:
    if starts < 1 or dimension < 1:
        raise ValueError("V15 performance workloads require variables and starts")
    return tuple(
        tuple(
            (((callback + 7) * (axis + 11) * 2246822519) % 104729) / 52364.5 - 1.0
            for axis in range(dimension)
        )
        for callback in range(starts * callbacks_per_start)
    )


def workload_from_v15(
    problem: Mapping[str, Any], *, starts: int, callbacks_per_start: int
) -> SameWorkload:
    document = copy.deepcopy(dict(problem))
    # Product compilation remains source-bound, but the original corpus/case
    # identity is neither retained nor available to performance admission.
    document["id"] = "same-work-generic-v15"
    variable_names = tuple(document.get("variables", {}).get("names", ()))
    profile = structural_profile(document)
    return SameWorkload(
        structural_class=str(profile["structural_class"]),
        start_ordinals=tuple(range(starts)),
        callbacks_per_start=callbacks_per_start,
        proposals=_proposals(starts, callbacks_per_start, len(variable_names)),
        expression={"kind": "v15", "profile": profile, "problem": document},
    )


def workloads_from_v15_paths(
    paths: Sequence[Path], *, starts: int, callbacks_per_start: int
) -> tuple[SameWorkload, ...]:
    workloads = []
    for path in paths:
        problem = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(problem, dict):
            raise ValueError(f"{path}: V15 document must be an object")
        workloads.append(
            workload_from_v15(
                problem, starts=starts, callbacks_per_start=callbacks_per_start
            )
        )
    return tuple(workloads)


def _problem(workload: SameWorkload) -> Mapping[str, Any]:
    if workload.expression.get("kind") == "v15":
        problem = workload.expression.get("problem")
        if isinstance(problem, Mapping):
            return problem
        raise ValueError("V15 workload has no problem document")
    raise ValueError("performance workloads must contain an actual V15 problem")


class ProductionSameWorkExecutor:
    """Drive the frozen reference and current optimized callback evaluators."""

    def __init__(self) -> None:
        self._qualification = CompiledKernelQualificationAdapter()
        self._prepared: dict[str, Any] = {}
        self._correctness: dict[str, Mapping[str, Any]] = {}
        self._workloads: dict[str, SameWorkload] = {}

    def manifest(self) -> Mapping[str, Any]:
        return {
            "adapter": "geotarget.production-same-work/v1",
            "case_specific_routing": False,
            "problem_id_read": False,
            "corpus_metadata_read": False,
            "truth_read": False,
            "answer_count_read": False,
            "work_identity": [
                "start_ordinals",
                "callbacks_per_start",
                "proposal_sha256",
            ],
            "semantic_snapshot": "kernel_qualification._snapshot/Observation",
            "timed_callback": "evaluate_float_residual",
            "timed_semantic_fields": [
                "residual_vector",
                "residual_norm_float",
                "evaluation_status",
                "is_finite",
                "exception_type",
            ],
            "digest_and_full_snapshot_inside_timed_region": False,
            "runner_owned_callback_wrapper": True,
            "compiler_manifest": dict(self._qualification.compiler_manifest()),
            "prepared_support": [
                {
                    "work_sha256": work_sha256,
                    "compiled_supported": bool(prepared.compiled_supported),
                    "fallback_reason": prepared.fallback_reason,
                    "support_decision_trace": dict(prepared.support_decision_trace),
                    "structural_profile": structural_profile(
                        _problem(self._workloads[work_sha256])
                    ),
                    "problem_sha256": _canonical_sha256(
                        _problem(self._workloads[work_sha256])
                    ),
                }
                for work_sha256, prepared in sorted(self._prepared.items())
            ],
            "untimed_correctness": [
                dict(self._correctness[key]) for key in sorted(self._correctness)
            ],
        }

    def prepare(self, workloads: Sequence[SameWorkload]) -> None:
        for workload in workloads:
            self._workloads[workload.work_sha256] = workload
            if workload.work_sha256 not in self._prepared:
                self._prepared[workload.work_sha256] = self._qualification.prepare(
                    _problem(workload), cores=1
                )
            if workload.work_sha256 not in self._correctness:
                self._correctness[workload.work_sha256] = {
                    "work_sha256": workload.work_sha256,
                    "status": "deferred_until_performance_callback_passes",
                    "proposal_snapshots_checked": 0,
                    "guard_hard_selector_fault_checked": False,
                }

    def callback(
        self,
        mode: Literal["reference", "optimized"],
        workload: SameWorkload,
        point: tuple[float, ...],
    ) -> Mapping[str, Any]:
        if workload.work_sha256 not in self._prepared:
            self.prepare((workload,))
        prepared = self._prepared[workload.work_sha256]
        evaluator = (
            prepared.reference_evaluator
            if mode == "reference"
            else prepared.candidate_evaluator
        )
        try:
            residual = evaluator.evaluate_float_residual(list(point))
            status = str(
                getattr(residual.evaluation_status, "value", residual.evaluation_status)
            )
            return {
                "residual_vector": tuple(float(value) for value in residual.residual_vector),
                "residual_norm_float": float(residual.residual_norm_float),
                "evaluation_status": status,
                "is_finite": bool(residual.is_finite),
                "exception_type": None,
            }
        except Exception as error:
            return {
                "residual_vector": (),
                "residual_norm_float": math.nan,
                "evaluation_status": "exception",
                "is_finite": False,
                "exception_type": type(error).__name__,
            }


def create_executor() -> ProductionSameWorkExecutor:
    """CLI factory for ``geotarget.same_work_performance``."""

    return ProductionSameWorkExecutor()
