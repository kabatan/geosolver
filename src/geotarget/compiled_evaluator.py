"""Immutable source-bound residual plans for the frozen geometry evaluator.

The compiler evaluates the source construction once with symbolic variables.
Callbacks then execute the resulting SymPy/libmp DAG directly, preserving the
frozen evaluator's separate binary53 conversion of each constraint side.
Unsupported symbolic constructions fail closed at problem granularity.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from sympy import Float, Symbol, preorder_traversal
from sympy.core.basic import Basic
from sympy.core.numbers import mlib, rnd

from geotarget.lazy_symbolic_geometry import SEMANTIC_ABI

SCHEMA_VERSION = "geotarget.compiled-residual-plan/v1"
POINT_DISTANCE_ABI = "geotarget.refnum-point-distance/libmp-bf53-v1"
TYPED_REFNUM_ABI = "geotarget.typed-refnum-ir/sympy-1.14-libmp-bf53-v1"
MAX_COMPILATION_AST_NODES = 200_000
MAX_COMPILATION_WALL_SECONDS = 5.0

# Declarative semantic boundary. These are SymPy DAG operators, not DSL
# function names; geometry calls must disappear during symbolic construction.
OPERATOR_REGISTRY = frozenset(
    {
        "Abs",
        "Add",
        "Float",
        "Half",
        "Integer",
        "Mul",
        "Min",
        "NegativeOne",
        "One",
        "Pi",
        "Pow",
        "Rational",
        "Symbol",
        "Zero",
        "acos",
        "atan2",
        "cos",
        "sin",
    }
)
POINT_DISTANCE_PRIMITIVES = frozenset({"Constant", "Distance", "Name", "Point"})
POINT_DISTANCE_TYPES = frozenset({"bf53", "exact_int", "point2", "scalar"})


class UnsupportedCompiledEvaluator(RuntimeError):
    """The problem cannot be represented by the qualified compiled subset."""


@dataclass(frozen=True)
class ConstantConstructionResult:
    evaluator: Any
    precomputed_names: tuple[str, ...]
    dependency_sha256: str


def precompute_constant_constructions(evaluator: Any) -> ConstantConstructionResult:
    """Hoist source-constant construction nodes without reading problem identity."""

    from geosolver.ir.compiler import extract_names, safe_eval_expr

    bundle = evaluator.bundle
    variable_names = set(bundle.var_names)
    known_constants = set(bundle.base_context)
    context = dict(bundle.base_context)
    retained = []
    precomputed: list[str] = []
    dependency_rows: list[dict[str, Any]] = []
    for item in bundle.spec.construction:
        dependencies = set(extract_names(item.expr)) - set(bundle.base_context)
        function_names = set(extract_names(item.expr)) & set(bundle.base_context)
        eligible = (
            not dependencies & variable_names
            and dependencies <= known_constants
            and "Intersect" not in function_names
        )
        if eligible:
            try:
                context[item.name] = safe_eval_expr(item.expr, context)
            except Exception:
                retained.append(item)
                dependency_rows.append(
                    {"name": item.name, "dependencies": sorted(dependencies), "hoisted": False}
                )
                continue
            known_constants.add(item.name)
            precomputed.append(item.name)
            dependency_rows.append(
                {"name": item.name, "dependencies": sorted(dependencies), "hoisted": True}
            )
        else:
            retained.append(item)
            dependency_rows.append(
                {"name": item.name, "dependencies": sorted(dependencies), "hoisted": False}
            )
    specification = replace(bundle.spec, construction=retained)
    optimized_bundle = replace(bundle, spec=specification, base_context=context)
    optimized_evaluator = replace(evaluator, bundle=optimized_bundle)
    return ConstantConstructionResult(
        evaluator=optimized_evaluator,
        precomputed_names=tuple(precomputed),
        dependency_sha256=_canonical_sha256(dependency_rows),
    )


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compiler_manifest() -> dict[str, Any]:
    from geotarget.flat_tape_backend import FLAT_TAPE_ABI, FLAT_TAPE_QUALIFICATION_GATE

    return {
        "schema_version": SCHEMA_VERSION,
        "case_specific_routing": False,
        "problem_id_read": False,
        "corpus_metadata_read": False,
        "truth_or_answer_count_read": False,
        "dsl_support_policy": "frozen_symbolic_expansion_then_typed_operator_check",
        "supported_symbolic_operators": sorted(OPERATOR_REGISTRY),
        "numeric_boundary": "SymPy-1.14 symbolic DAG to binary53 via frozen libmp",
        "fallback_scope": "whole_problem",
        "support_decision_basis": "ast_opcode_type_selector_semantic_abi_only",
        "forbidden_support_inputs": [
            "problem_id",
            "corpus_membership",
            "truth",
            "answer_count",
        ],
        "support_decision_key_fields": [
            "ast_opcode_set",
            "resolved_operand_result_type_set",
            "selector_kind_set",
            "semantic_abi_version",
        ],
        "support_key_includes_problem_id": False,
        "support_key_includes_source_sha256": False,
        "support_key_includes_problem_hash": False,
        "support_key_includes_corpus_shape": False,
        "call_contract_source": (
            "bundle.base_context exported callable plus selected _sympy signature"
        ),
        "namespace_shadowing_policy": "reserved frozen symbols require whole-problem fallback",
        "resolved_type_source": "typed RefNum SupportKey shared by leaf and general dispatch",
        "production_backend_order": [
            "raw_semantic_effect_gate",
            "flat_tape",
            "raw_libmp",
            "frozen_reference",
        ],
        "qualified_flat_tape_abis": [FLAT_TAPE_ABI],
        "flat_tape_qualification_gate": FLAT_TAPE_QUALIFICATION_GATE,
        "unqualified_backend_selection": "forbidden",
    }


def supports_primitive_types(
    ast_primitive_set: frozenset[str], inferred_type_set: frozenset[str]
) -> bool:
    """Identity-free admission for the first fully typed RefNum program."""

    return (
        ast_primitive_set <= POINT_DISTANCE_PRIMITIVES and inferred_type_set <= POINT_DISTANCE_TYPES
    )


def supports_compilation_key(
    ast_opcode_set: frozenset[str],
    resolved_operand_result_type_set: frozenset[str],
    selector_kind_set: frozenset[str],
    semantic_abi_version: str,
) -> bool:
    return (
        "ParseError" not in ast_opcode_set
        and not any(value.startswith("unsupported_") for value in resolved_operand_result_type_set)
        and selector_kind_set <= {"n", "near", "far", "exclude"}
        and semantic_abi_version in {POINT_DISTANCE_ABI, TYPED_REFNUM_ABI, SEMANTIC_ABI}
    )


@dataclass(frozen=True)
class PointDistanceProgram:
    points: tuple[tuple[str, tuple[str, Any], tuple[str, Any]], ...]
    constraints: tuple[tuple[tuple[Any, ...], tuple[Any, ...]], ...]

    @staticmethod
    def _mpf(token: tuple[str, Any], values: dict[str, float]):
        kind, payload = token
        if kind == "exact_int":
            return mlib.from_int(int(payload))
        if kind == "bf53_const":
            return mlib.from_float(float(payload))
        if kind == "bf53_input":
            return mlib.from_float(float(values[str(payload)]))
        raise ValueError(f"unsupported RefNum token: {kind}")

    def evaluate(self, variable_names: tuple[str, ...], raw_values: list[float]) -> list[float]:
        values = dict(zip(variable_names, raw_values, strict=True))
        points = {
            name: (self._mpf(x_token, values), self._mpf(y_token, values))
            for name, x_token, y_token in self.points
        }

        def side(descriptor: tuple[Any, ...]) -> float:
            if descriptor[0] == "constant":
                return float(descriptor[1])
            _kind, left_name, right_name = descriptor
            left = points[str(left_name)]
            right = points[str(right_name)]
            dx = mlib.mpf_sub(left[0], right[0], 53, rnd)
            dy = mlib.mpf_sub(left[1], right[1], 53, rnd)
            dx2 = mlib.mpf_mul(dx, dx, 53, rnd)
            dy2 = mlib.mpf_mul(dy, dy, 53, rnd)
            squared = mlib.mpf_add(dx2, dy2, 53, rnd)
            return float(mlib.to_float(mlib.mpf_sqrt(squared, 53, rnd), rnd))

        return [side(left) - side(right) for left, right in self.constraints]


def _coordinate_token(node: ast.expr, variable_names: frozenset[str]):
    if isinstance(node, ast.Name) and node.id in variable_names:
        return ("bf53_input", node.id)
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    ):
        return ("exact_int", node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, float):
        return ("bf53_const", node.value)
    raise UnsupportedCompiledEvaluator("Point coordinate is outside typed RefNum subset")


def _distance_side(expression: str | int | float, point_names: frozenset[str]) -> tuple[Any, ...]:
    if isinstance(expression, bool):
        raise UnsupportedCompiledEvaluator("bool is not a numeric constraint target")
    if isinstance(expression, int | float):
        return ("constant", expression)
    node = ast.parse(expression, mode="eval").body
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Distance"
        and len(node.args) == 2
        and all(isinstance(argument, ast.Name) for argument in node.args)
        and all(argument.id in point_names for argument in node.args)
    ):
        return ("distance", node.args[0].id, node.args[1].id)
    raise UnsupportedCompiledEvaluator("constraint side is outside typed Distance subset")


def _compile_point_distance_program(bundle: Any) -> PointDistanceProgram | None:
    variable_names = frozenset(bundle.var_names)
    points: list[tuple[str, tuple[str, Any], tuple[str, Any]]] = []
    primitives: set[str] = {"Constant", "Name", "Point", "Distance"}
    inferred_types: set[str] = {"point2", "scalar"}
    try:
        for item in bundle.spec.construction:
            node = ast.parse(item.expr, mode="eval").body
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Point"
                and len(node.args) == 2
            ):
                return None
            x_token = _coordinate_token(node.args[0], variable_names)
            y_token = _coordinate_token(node.args[1], variable_names)
            inferred_types.update(
                "exact_int" if token[0] == "exact_int" else "bf53" for token in (x_token, y_token)
            )
            points.append((item.name, x_token, y_token))
        point_names = frozenset(name for name, _x, _y in points)
        constraints = tuple(
            (
                _distance_side(left, point_names),
                _distance_side(right, point_names),
            )
            for left, right in zip(bundle.spec.constraints, bundle.targets, strict=True)
        )
        if not supports_primitive_types(frozenset(primitives), frozenset(inferred_types)):
            return None
        return PointDistanceProgram(tuple(points), constraints)
    except (SyntaxError, UnsupportedCompiledEvaluator):
        return None


def _operator_names(expression: Basic) -> frozenset[str]:
    return frozenset(type(node).__name__ for node in preorder_traversal(expression))


def _to_frozen_float(expression: Any, substitutions: dict[Symbol, Float]) -> float:
    if isinstance(expression, Basic):
        return float(expression.evalf(subs=substitutions))
    try:
        return float(expression)
    except Exception as error:
        # Match the frozen `_to_float` second-chance behavior only by refusing
        # the compiled path; its exact-algebra fallback is outside this subset.
        raise UnsupportedCompiledEvaluator("non-SymPy result needs exact fallback") from error


@dataclass(frozen=True)
class CompiledResidualPlan:
    source_sha256: str
    ast_sha256: str
    plan_sha256: str
    variable_names: tuple[str, ...]
    symbols: tuple[Symbol, ...]
    sides: tuple[tuple[Any, Any], ...]
    operators: tuple[str, ...]
    flat_tape_program: Any | None = None
    raw_libmp_program: Any | None = None
    point_distance_program: PointDistanceProgram | None = None
    typed_refnum_program: Any | None = None
    deferred_validations: tuple[tuple[str, str, str], ...] = ()
    selector_kinds: tuple[str, ...] = ()
    semantic_abi_version: str = SCHEMA_VERSION
    backend_selection_chain: tuple[str, ...] = ()
    flat_tape_fallback_reason: str | None = None
    raw_semantic_gate_metadata: dict[str, Any] | None = None

    def evaluate(self, values: list[float]) -> list[float]:
        expected_dimension = (
            len(self.variable_names)
            if (
                self.flat_tape_program is not None
                or self.raw_libmp_program is not None
                or self.point_distance_program is not None
                or self.typed_refnum_program is not None
            )
            else len(self.symbols)
        )
        if len(values) != expected_dimension:
            raise ValueError("compiled evaluator dimension mismatch")
        if self.flat_tape_program is not None:
            return self.flat_tape_program.evaluate(values)
        if self.raw_libmp_program is not None:
            return self.raw_libmp_program.evaluate(values)
        if self.point_distance_program is not None:
            return self.point_distance_program.evaluate(self.variable_names, values)
        if self.typed_refnum_program is not None:
            return self.typed_refnum_program.evaluate(values)
        substitutions = {
            symbol: Float(float(value)) for symbol, value in zip(self.symbols, values, strict=True)
        }
        residuals: list[float] = []
        for left, right in self.sides:
            try:
                # Frozen semantics convert each side independently, then use
                # one host binary64 subtraction in source constraint order.
                residuals.append(
                    _to_frozen_float(left, substitutions) - _to_frozen_float(right, substitutions)
                )
            except Exception:
                residuals.append(float("nan"))
        return residuals

    def metadata(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": (
                "flat_tape_bf53"
                if self.flat_tape_program is not None
                else "raw_libmp_bf53"
                if self.raw_libmp_program is not None
                else "precompiled_symbolic_dag_bf53"
            ),
            "source_sha256": self.source_sha256,
            "ast_sha256": self.ast_sha256,
            "plan_sha256": self.plan_sha256,
            "operators": list(self.operators),
            "residual_compiled": True,
            "case_specific_routing": False,
            "dsl_support_policy": ("frozen_symbolic_expansion_then_typed_operator_check"),
            "supported_symbolic_operators": sorted(OPERATOR_REGISTRY),
            "refnum_point_distance": self.point_distance_program is not None,
            "typed_refnum_ir": self.typed_refnum_program is not None,
            "flat_tape": self.flat_tape_program is not None,
            "flat_tape_metadata": (
                self.flat_tape_program.metadata() if self.flat_tape_program is not None else None
            ),
            "flat_tape_fallback_reason": self.flat_tape_fallback_reason,
            "backend_selection_chain": list(self.backend_selection_chain),
            "raw_libmp": self.raw_libmp_program is not None,
            "raw_semantic_gate_metadata": self.raw_semantic_gate_metadata,
            "raw_libmp_metadata": (
                self.raw_libmp_program.metadata() if self.raw_libmp_program is not None else None
            ),
            "guard_backend": "source_semantic_reference_helper",
            "hard_feasibility_backend": "source_semantic_reference_helper",
            "hp_and_exact_backend": "frozen_reference_delegate",
            "deferred_validations": [list(value) for value in self.deferred_validations],
            "selector_kinds": list(self.selector_kinds),
            "semantic_abi_version": self.semantic_abi_version,
        }


@dataclass(frozen=True)
class CompilationResult:
    plan: CompiledResidualPlan | None
    fallback_reason: str | None
    attempted_ast_opcode_set: tuple[str, ...] = ()
    attempted_operand_result_type_set: tuple[str, ...] = ()
    attempted_selector_kind_set: tuple[str, ...] = ()
    attempted_semantic_abi_version: str = SEMANTIC_ABI

    @property
    def supported(self) -> bool:
        return self.plan is not None


def compile_residual_plan(evaluator: Any, *, source_sha256: str) -> CompilationResult:
    """Compile one evaluator without case identity or benchmark information."""

    compilation_started = time.monotonic()
    bundle = evaluator.bundle
    specification = bundle.spec
    ast_record = {
        "variables": list(bundle.var_names),
        "construction": [
            {"name": item.name, "expr": item.expr} for item in specification.construction
        ],
        "constraints": list(specification.constraints),
        "targets": list(bundle.targets),
    }
    ast_sha256 = _canonical_sha256(ast_record)
    support_problem = {
        "construction": ast_record["construction"],
        "constraints": [
            {"def": left, "value": right}
            for left, right in zip(specification.constraints, bundle.targets, strict=True)
        ],
        "guards": list(specification.guards),
    }

    def with_admission_inputs(result: CompilationResult) -> CompilationResult:
        trace = support_decision_trace(support_problem, result)
        return replace(
            result,
            attempted_ast_opcode_set=tuple(trace["ast_opcode_set"]),
            attempted_operand_result_type_set=tuple(trace["resolved_operand_result_type_set"]),
            attempted_selector_kind_set=tuple(trace["selector_kind_set"]),
        )

    try:
        expression_texts = [
            *(item["expr"] for item in support_problem["construction"]),
            *(item["def"] for item in support_problem["constraints"]),
            *(
                item["value"]
                for item in support_problem["constraints"]
                if isinstance(item["value"], str)
            ),
            *support_problem["guards"],
        ]
        ast_node_count = sum(
            sum(1 for _node in ast.walk(ast.parse(text, mode="eval")))
            for text in expression_texts
            if text.strip()
        )
        if ast_node_count > MAX_COMPILATION_AST_NODES:
            raise UnsupportedCompiledEvaluator("compilation AST node limit exceeded")
        if time.monotonic() - compilation_started > MAX_COMPILATION_WALL_SECONDS:
            raise UnsupportedCompiledEvaluator("compilation wall limit exceeded")

        # One type/signature authority admits both the leaf fast path and the
        # general typed executor.  This prevents a faster specialization from
        # accepting unresolved Names or invented aliases that the V15 context
        # would reject.
        from geotarget.typed_refnum_ir import dispatch_typed_refnum_program

        typed_dispatch = dispatch_typed_refnum_program(
            bundle,
            max_ast_nodes=MAX_COMPILATION_AST_NODES,
            max_compile_seconds=max(
                1e-6,
                MAX_COMPILATION_WALL_SECONDS - (time.monotonic() - compilation_started),
            ),
        )
        typed_program = typed_dispatch.program
        typed_opcodes = (
            tuple(sorted({key.opcode for key in typed_program.support_keys}))
            if typed_program is not None
            else ()
        )
        typed_types = (
            tuple(
                sorted(
                    {
                        value
                        for key in typed_program.support_keys
                        for value in (*key.operand_types, key.result_type)
                    }
                )
            )
            if typed_program is not None
            else ()
        )
        typed_selectors = (
            tuple(
                sorted(
                    {
                        key.selector_kind
                        for key in typed_program.support_keys
                        if key.selector_kind != "none"
                    }
                )
            )
            if typed_program is not None
            else ()
        )

        if typed_program is None:
            return CompilationResult(
                plan=None,
                fallback_reason=(
                    "typed admission rejected; frozen reference required: "
                    f"{typed_dispatch.fallback_reason}"
                ),
                attempted_ast_opcode_set=tuple(
                    typed_dispatch.trace.get("attempted_ast_opcodes", ())
                ),
                attempted_semantic_abi_version=TYPED_REFNUM_ABI,
            )

        from geotarget.raw_libmp_backend import (
            UnsupportedRawLibmpBackend,
            compile_raw_libmp_program,
        )

        try:
            raw_program = compile_raw_libmp_program(typed_program)
        except RecursionError:
            return CompilationResult(
                plan=None,
                fallback_reason=(
                    "raw semantic gate resource fallback: recursion depth exceeded"
                ),
                attempted_ast_opcode_set=typed_opcodes,
                attempted_operand_result_type_set=typed_types,
                attempted_selector_kind_set=typed_selectors,
                attempted_semantic_abi_version=typed_program.semantic_abi,
            )
        except UnsupportedRawLibmpBackend as error:
            # The typed executor is a semantic oracle/qualification target,
            # not a production fallback until it independently passes the
            # performance gate.  Preserve its admission trace, but execute the
            # complete problem with the frozen reference evaluator.
            return CompilationResult(
                plan=None,
                fallback_reason=(
                    "raw libmp whole-problem fallback to frozen reference: "
                    f"{type(error).__name__}: {error}"
                ),
                attempted_ast_opcode_set=typed_opcodes,
                attempted_operand_result_type_set=typed_types,
                attempted_selector_kind_set=typed_selectors,
                attempted_semantic_abi_version=typed_program.semantic_abi,
            )

        raw_metadata = raw_program.metadata()
        # The raw compiler is the semantic/effect authority for the complete
        # typed program.  Only after that gate succeeds may the flat tape be
        # selected as an execution specialization.  Opcode-subset admission
        # alone is insufficient for producer/consumer-sensitive operations.
        from geotarget.flat_tape_backend import (
            FLAT_TAPE_ABI,
            FLAT_TAPE_QUALIFICATION_GATE,
            UnsupportedFlatTapeBackend,
            compile_flat_tape_program,
        )

        qualified_flat_abis = frozenset({FLAT_TAPE_ABI})
        flat_program = None
        flat_fallback_reason = None
        try:
            candidate = compile_flat_tape_program(
                typed_program, raw_semantic_gate=raw_program
            )
            if candidate.semantic_abi not in qualified_flat_abis:
                raise UnsupportedFlatTapeBackend(
                    f"unqualified flat tape ABI: {candidate.semantic_abi}"
                )
            if candidate.metadata().get("qualification_gate") != FLAT_TAPE_QUALIFICATION_GATE:
                raise UnsupportedFlatTapeBackend("flat tape qualification gate mismatch")
            flat_program = candidate
        except UnsupportedFlatTapeBackend as error:
            flat_fallback_reason = f"{type(error).__name__}: {error}"

        if flat_program is not None:
            flat_metadata = flat_program.metadata()
            flat_semantic_metadata = {
                key: value
                for key, value in flat_metadata.items()
                if key != "admission_compile_seconds"
            }
            flat_record = {
                "schema_version": SCHEMA_VERSION,
                "source_sha256": source_sha256,
                "ast_sha256": ast_sha256,
                "operators": list(flat_metadata["opcodes"]),
                "semantic_abi_version": flat_program.semantic_abi,
                "typed_admission_support_key_sha256": typed_dispatch.trace.get(
                    "support_key_sha256"
                ),
                "typed_semantic_abi": typed_program.semantic_abi,
                "raw_semantic_gate": raw_metadata,
                # Wall timing is reported at runtime but is not part of the
                # deterministic semantic/product plan identity.
                "flat_support": flat_semantic_metadata,
                "backend_selection_chain": ["typed", "raw_semantic_gate", "flat_tape"],
            }
            return CompilationResult(
                plan=CompiledResidualPlan(
                    source_sha256=source_sha256,
                    ast_sha256=ast_sha256,
                    plan_sha256=_canonical_sha256(flat_record),
                    variable_names=tuple(bundle.var_names),
                    symbols=(),
                    sides=(),
                    operators=tuple(flat_metadata["opcodes"]),
                    flat_tape_program=flat_program,
                    typed_refnum_program=typed_program,
                    semantic_abi_version=flat_program.semantic_abi,
                    backend_selection_chain=("typed", "raw_semantic_gate", "flat_tape"),
                    raw_semantic_gate_metadata=raw_metadata,
                ),
                fallback_reason=None,
                attempted_ast_opcode_set=typed_opcodes,
                attempted_operand_result_type_set=typed_types,
                attempted_selector_kind_set=typed_selectors,
                attempted_semantic_abi_version=typed_program.semantic_abi,
            )

        raw_record = {
            "schema_version": SCHEMA_VERSION,
            "source_sha256": source_sha256,
            "ast_sha256": ast_sha256,
            "operators": list(raw_metadata["opcodes"]),
            "semantic_abi_version": raw_program.semantic_abi,
            "typed_admission_support_key_sha256": typed_dispatch.trace.get("support_key_sha256"),
            "typed_semantic_abi": typed_program.semantic_abi,
            "raw_support": raw_metadata,
            "flat_tape_fallback_reason": flat_fallback_reason,
            "backend_selection_chain": ["typed", "raw_semantic_gate", "raw_libmp"],
        }
        return CompilationResult(
            plan=CompiledResidualPlan(
                source_sha256=source_sha256,
                ast_sha256=ast_sha256,
                plan_sha256=_canonical_sha256(raw_record),
                variable_names=tuple(bundle.var_names),
                symbols=(),
                sides=(),
                operators=tuple(raw_metadata["opcodes"]),
                raw_libmp_program=raw_program,
                typed_refnum_program=typed_program,
                semantic_abi_version=raw_program.semantic_abi,
                backend_selection_chain=("typed", "raw_semantic_gate", "raw_libmp"),
                flat_tape_fallback_reason=flat_fallback_reason,
                raw_semantic_gate_metadata=raw_metadata,
            ),
            fallback_reason=None,
            attempted_ast_opcode_set=typed_opcodes,
            attempted_operand_result_type_set=typed_types,
            attempted_selector_kind_set=typed_selectors,
            attempted_semantic_abi_version=typed_program.semantic_abi,
        )

    except Exception as error:
        return with_admission_inputs(
            CompilationResult(
                plan=None,
                fallback_reason=f"{type(error).__name__}: {error}",
                attempted_semantic_abi_version=SEMANTIC_ABI,
            )
        )


def support_decision_trace(problem: Any, compilation: CompilationResult) -> dict[str, Any]:
    """Expose identity-free semantic inputs, including failed admission inputs."""

    if not isinstance(problem, Mapping):
        raise TypeError("support trace requires a problem mapping")
    expressions: list[str] = []
    for item in problem.get("construction", ()):
        if isinstance(item, Mapping):
            expressions.append(str(item.get("expr", "")))
    for item in problem.get("constraints", ()):
        if not isinstance(item, Mapping):
            continue
        expressions.append(str(item.get("def", "")))
        if isinstance(item.get("value"), str):
            expressions.append(str(item["value"]))
    expressions.extend(str(value) for value in problem.get("guards", ()))

    result_types = {
        "Point": "point2",
        "PointOnCircle": "point2",
        "Intersect": "point2",
        "Line": "line2",
        "Segment": "line2",
        "Ray": "line2",
        "Circle": "circle2",
        "Distance": "scalar",
        "Area": "scalar",
        "Angle": "scalar",
        "Bound": "guard_bool",
        "AssumeNe": "guard_bool",
        "AssumeGt": "guard_bool",
        "AssumeGe": "guard_bool",
    }
    opcodes: set[str] = set()
    types: set[str] = set()
    selectors: set[str] = set()
    selector_names = {
        "n",
        "near",
        "far",
        "exclude",
        "first",
        "branch",
        "vertex",
        "side",
        "orientation",
    }

    def infer(node: ast.AST) -> str:
        if isinstance(node, ast.Constant):
            inferred = (
                "exact_int"
                if isinstance(node.value, int) and not isinstance(node.value, bool)
                else "bf53"
                if isinstance(node.value, float)
                else "unsupported_literal"
            )
            types.add(inferred)
            return inferred
        if isinstance(node, ast.Name):
            types.add("named_value")
            return "named_value"
        if isinstance(node, ast.Call):
            function = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else "UnsupportedCallable"
            )
            opcodes.add(function)
            operand_types = tuple(infer(argument) for argument in node.args)
            selectors.update(
                keyword.arg
                for keyword in node.keywords
                if keyword.arg is not None and keyword.arg in selector_names
            )
            for keyword in node.keywords:
                infer(keyword.value)
            result = result_types.get(function, f"unsupported_result:{function}")
            types.add(result)
            types.add(f"call:{function}({','.join(operand_types)})->{result}")
            return result
        for child in ast.iter_child_nodes(node):
            infer(child)
        node_type = type(node).__name__
        if isinstance(node, ast.operator | ast.boolop | ast.cmpop | ast.unaryop):
            opcodes.add(node_type)
            types.add(f"operator_result:{node_type}:scalar")
            return "scalar"
        return "unresolved"

    for expression in expressions:
        if not expression.strip():
            continue
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            opcodes.add("ParseError")
            types.add("unsupported_parse")
            continue
        infer(tree.body)

    abi = (
        compilation.plan.semantic_abi_version
        if compilation.plan is not None
        else compilation.attempted_semantic_abi_version
    )
    key = {
        "ast_opcode_set": sorted(opcodes),
        "resolved_operand_result_type_set": sorted(types),
        "selector_kind_set": sorted(selectors),
        "semantic_abi_version": abi,
    }
    return {
        **key,
        "support_key_sha256": _canonical_sha256(key),
        "problem_id_read": False,
        "corpus_membership_read": False,
        "truth_read": False,
        "answer_count_read": False,
    }


class CompiledResidualEvaluator:
    """Evaluator facade with a compiled residual and frozen helper phases."""

    def __init__(self, reference: Any, plan: CompiledResidualPlan):
        self.reference = reference
        self.plan = plan
        self.bundle = reference.bundle
        self.compiled_guards = reference.compiled_guards

    def evaluate_float_residual(self, values: list[float]):
        from geosolver._internal.autosolve.execution.interpreter_helpers import (
            _residual_norm,
        )
        from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import (
            EvaluationStatus,
            classify_evaluation_failure,
        )
        from geosolver._internal.pipeline.evaluator.evaluate_float_residual import (
            FloatResidualEvaluation,
        )

        residuals = self.plan.evaluate(list(values))
        status = classify_evaluation_failure(residuals)
        norm = _residual_norm(residuals) if status is EvaluationStatus.OK else math.inf
        return FloatResidualEvaluation(
            residual_vector=list(residuals),
            residual_norm_float=norm,
            evaluation_status=status,
            is_finite=(status is EvaluationStatus.OK),
        )

    def evaluate_guard(self, values):
        return self.reference.evaluate_guard(values)

    def evaluate_float_hard_feasibility(self, values):
        return self.reference.evaluate_float_hard_feasibility(values)

    def __getattr__(self, name: str):
        return getattr(self.reference, name)


class ConstantResidualEvaluator:
    """Residual-only facade; every authority-bearing phase stays original."""

    def __init__(self, reference: Any, residual_evaluator: Any):
        self.reference = reference
        self.residual_evaluator = residual_evaluator
        self.bundle = reference.bundle
        self.compiled_guards = reference.compiled_guards

    def evaluate_float_residual(self, values: list[float]):
        return self.residual_evaluator.evaluate_float_residual(values)

    def evaluate_guard(self, values):
        return self.reference.evaluate_guard(values)

    def evaluate_float_hard_feasibility(self, values):
        return self.reference.evaluate_float_hard_feasibility(values)

    def __getattr__(self, name: str):
        return getattr(self.reference, name)
