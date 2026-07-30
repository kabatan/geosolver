from __future__ import annotations

import copy
import math
import random
import struct
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from scipy.optimize import least_squares

import geotarget.compiled_evaluator as compiled_module
import geotarget.search_pool_worker_entrypoint as search_worker_module
from geotarget.compiled_evaluator import (
    CompilationResult,
    CompiledResidualEvaluator,
    ConstantResidualEvaluator,
    compile_residual_plan,
    compiler_manifest,
    precompute_constant_constructions,
    support_decision_trace,
    supports_primitive_types,
)
from geotarget.continuation import _load_frozen

CASE001 = {
    "task": "solve",
    "id": "synthetic-circle-distance",
    "variables": {"names": ["tB", "tC", "tD"]},
    "construction": [
        {"name": "O", "expr": "Point(0, 0)"},
        {"name": "Gamma", "expr": "Circle(O, 25)"},
        {"name": "A", "expr": "Point(25, 0)"},
        {"name": "B", "expr": "PointOnCircle(Gamma, tB)"},
        {"name": "C", "expr": "PointOnCircle(Gamma, tC)"},
        {"name": "D", "expr": "PointOnCircle(Gamma, tD)"},
    ],
    "constraints": [
        {"def": "Distance(A, B)", "value": 14},
        {"def": "Distance(A, D)", "value": 50},
        {"def": "Distance(B, C)", "value": "Distance(C, D)"},
    ],
    "guards": [],
    "answer": "Distance(A, C)",
    "post_process": "",
}


def _raw_supported_problem(identifier: str = "unknown-raw-supported") -> dict:
    return {
        "task": "solve",
        "id": identifier,
        "variables": {"names": ["ax", "ay", "bx", "by", "px", "py"]},
        "construction": [
            {"name": "A", "expr": "Point(ax, ay)"},
            {"name": "B", "expr": "Point(bx, by)"},
            {"name": "P", "expr": "Point(px, py)"},
            {"name": "ell", "expr": "Line(A, B)"},
        ],
        "constraints": [
            {"def": "Distance(P, A)", "value": "Distance(P, ell)"},
            {"def": "Area(A, B, P)", "value": 1},
            {"def": "Angle(P, A, B)", "value": "pi/3"},
        ],
        "guards": [],
        "answer": "Distance(P, B)",
        "post_process": "",
    }


def _case001():
    document = copy.deepcopy(CASE001)
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_compiled_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document,
        callback_cap=256,
        deadline=time.monotonic() + 120,
    )
    return document, evaluator


def _build(document):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_compiled_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )
    return evaluator


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def test_point_on_circle_uses_general_raw_closure() -> None:
    _document, reference = _case001()
    compilation = compile_residual_plan(reference, source_sha256="a" * 64)
    assert compilation.plan is not None
    assert compilation.plan.raw_libmp_program is not None
    assert "PointOnCircle" in compilation.attempted_ast_opcode_set


def test_compiled_plan_is_source_and_ast_bound() -> None:
    evaluator = _build(_raw_supported_problem())
    first = compile_residual_plan(evaluator, source_sha256="a" * 64)
    second = compile_residual_plan(evaluator, source_sha256="b" * 64)

    assert first.plan is not None and second.plan is not None
    assert first.plan.ast_sha256 == second.plan.ast_sha256
    assert first.plan.plan_sha256 != second.plan.plan_sha256
    assert first.plan.metadata()["mode"] == "flat_tape_bf53"
    assert first.plan.flat_tape_program is not None
    assert first.plan.raw_libmp_program is None


def test_constant_construction_dependency_hoist_is_semantically_identical() -> None:
    _document, reference = _case001()
    optimized = precompute_constant_constructions(reference)
    assert optimized.precomputed_names == ("O", "Gamma", "A")
    rng = random.Random(9)
    for _ in range(16):
        point = [rng.uniform(-4, 4) for _ in range(3)]
        expected = reference.evaluate_float_residual(point)
        observed = optimized.evaluator.evaluate_float_residual(point)
        assert [_bits(value) for value in observed.residual_vector] == [
            _bits(value) for value in expected.residual_vector
        ]


def test_constant_hoist_facade_never_changes_guard_or_hard_authority() -> None:
    document = copy.deepcopy(CASE001)
    document["guards"] = ["AssumeNe(Distance(B, C), 0)"]
    reference = _build(document)
    optimized = precompute_constant_constructions(reference)
    facade = ConstantResidualEvaluator(reference, optimized.evaluator)
    point = [0.2, 0.6, 0.9]

    expected_residual = reference.evaluate_float_residual(point)
    observed_residual = facade.evaluate_float_residual(point)
    assert [_bits(value) for value in observed_residual.residual_vector] == [
        _bits(value) for value in expected_residual.residual_vector
    ]
    assert facade.evaluate_guard(point) == reference.evaluate_guard(point)
    assert facade.evaluate_float_hard_feasibility(
        point
    ) == reference.evaluate_float_hard_feasibility(point)
    assert facade.bundle is reference.bundle


def test_unknown_problem_with_supported_dag_compiles_without_identity_routing() -> None:
    evaluator = _build(_raw_supported_problem("never-seen-before-geometry"))
    compilation = compile_residual_plan(evaluator, source_sha256="c" * 64)
    renamed = compile_residual_plan(
        _build(_raw_supported_problem("unrelated-identity")),
        source_sha256="c" * 64,
    )

    assert compilation.supported
    assert compilation.plan is not None
    metadata = compilation.plan.metadata()
    assert metadata["case_specific_routing"] is False
    assert metadata["raw_semantic_gate_metadata"]["problem_identity_read"] is False
    assert renamed.plan is not None
    assert renamed.plan.plan_sha256 == compilation.plan.plan_sha256
    assert (
        renamed.plan.metadata()["raw_semantic_gate_metadata"]["support_key_sha256"]
        == metadata["raw_semantic_gate_metadata"]["support_key_sha256"]
    )


def test_unknown_point_distance_problem_uses_bit_exact_refnum_program(monkeypatch) -> None:
    document = {
        "task": "solve",
        "id": "unknown-rectangle-distance",
        "variables": {"names": ["width", "height", "px", "py"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(width, 0)"},
            {"name": "C", "expr": "Point(width, height)"},
            {"name": "P", "expr": "Point(px, py)"},
        ],
        "constraints": [
            {"def": "Distance(A, B)", "value": "Distance(A, C)"},
            {"def": "Distance(P, A)", "value": 28},
            {"def": "Distance(P, B)", "value": 16},
        ],
        "guards": [],
        "answer": "Distance(P, C)",
        "post_process": "",
    }
    reference = _build(document)
    monkeypatch.setattr(
        "geotarget.lazy_symbolic_geometry.expand_bundle_symbolically",
        lambda _bundle: (_ for _ in ()).throw(AssertionError("lazy path was entered")),
    )
    compilation = compile_residual_plan(reference, source_sha256="d" * 64)
    assert compilation.plan is not None
    assert compilation.plan.flat_tape_program is not None
    assert compilation.plan.semantic_abi_version == ("geotarget.flat-ssa-tape/sympy-1.14-bf53-v1")
    candidate = CompiledResidualEvaluator(reference, compilation.plan)
    random_source = random.Random(4)

    for _ in range(128):
        point = [random_source.uniform(-100, 100) for _ in range(4)]
        expected = reference.evaluate_float_residual(point)
        observed = candidate.evaluate_float_residual(point)
        assert [_bits(value) for value in observed.residual_vector] == [
            _bits(value) for value in expected.residual_vector
        ]

    manifest = compiler_manifest()
    assert manifest["support_decision_basis"] == "ast_opcode_type_selector_semantic_abi_only"
    assert supports_primitive_types(
        frozenset({"Point", "Distance", "Name", "Constant"}),
        frozenset({"point2", "scalar", "bf53", "exact_int"}),
    )


def test_production_search_worker_selects_qualified_flat_tape() -> None:
    """Exercise the selector used by optimized solves, not only the compiler."""

    reference = _build(_raw_supported_problem("production-worker-flat-selection"))
    budget = SimpleNamespace(evaluator=reference)
    original_installer = search_worker_module.install_fused_evaluation
    original_snapshot_installer = search_worker_module.install_compiled_callback_snapshot
    search_worker_module.install_fused_evaluation = lambda _budget: {
        "schema_version": "geotarget.fused-evaluation-budget/v1",
        "enabled": True,
        "case_specific_routing": False,
    }
    search_worker_module.install_compiled_callback_snapshot = lambda _budget, _snapshot: {
        "enabled": True,
        "dispatch": "test_budget",
    }
    try:
        evaluator, metadata = search_worker_module._activate_compiled_evaluator(
            reference,
            budget,
            source_sha256="e" * 64,
        )
    finally:
        search_worker_module.install_fused_evaluation = original_installer
        search_worker_module.install_compiled_callback_snapshot = original_snapshot_installer

    assert isinstance(evaluator, CompiledResidualEvaluator)
    assert budget.evaluator is evaluator
    assert metadata["enabled"] is True
    assert metadata["fused_evaluation"]["enabled"] is True
    assert metadata["mode"] == "flat_tape_bf53"
    assert metadata["backend_selection_chain"] == [
        "typed",
        "raw_semantic_gate",
        "flat_tape",
    ]
    assert metadata["flat_tape_metadata"]["qualification_status"] == ("permanent_test_gate")
    assert metadata["raw_semantic_gate_metadata"]["problem_identity_read"] is False


def test_flat_tape_optimizer_replay_preserves_every_observation() -> None:
    reference = _build(_raw_supported_problem("optimizer-replay-flat-selection"))
    compilation = compile_residual_plan(reference, source_sha256="f" * 64)
    assert compilation.plan is not None
    assert compilation.plan.flat_tape_program is not None
    candidate = CompiledResidualEvaluator(reference, compilation.plan)
    reference_trace: list[tuple[tuple[bytes, ...], tuple[bytes, ...]]] = []
    candidate_trace: list[tuple[tuple[bytes, ...], tuple[bytes, ...]]] = []

    def run(evaluator, trace):
        def residual(values):
            result = evaluator.evaluate_float_residual(list(values)).residual_vector
            trace.append(
                (
                    tuple(_bits(value) for value in values),
                    tuple(_bits(value) for value in result),
                )
            )
            return result

        return least_squares(
            residual,
            [1.25, -0.75, 4.5, 0.5, 0.25, 2.0],
            method="trf",
            max_nfev=40,
            ftol=None,
            xtol=1e-12,
            gtol=1e-12,
        )

    expected = run(reference, reference_trace)
    observed = run(candidate, candidate_trace)
    assert candidate_trace == reference_trace
    assert observed.status == expected.status
    assert observed.nfev == expected.nfev
    assert tuple(_bits(value) for value in observed.x) == tuple(
        _bits(value) for value in expected.x
    )
    assert tuple(_bits(value) for value in observed.fun) == tuple(
        _bits(value) for value in expected.fun
    )


def test_fallback_support_trace_preserves_actual_ast_types_and_selectors() -> None:
    problem = {
        "construction": [
            {"name": "P", "expr": "Mystery(Point(0, 0), near=Q)"},
        ],
        "constraints": [{"def": "Distance(P, Q)", "value": 1}],
        "guards": ["AssumeNe(Area(A, B, P), 0)"],
    }
    trace = support_decision_trace(
        problem, CompilationResult(plan=None, fallback_reason="unsupported")
    )
    assert trace["ast_opcode_set"] == [
        "Area",
        "AssumeNe",
        "Distance",
        "Mystery",
        "Point",
    ]
    assert trace["selector_kind_set"] == ["near"]
    assert "unsupported_result:Mystery" in trace["resolved_operand_result_type_set"]
    assert len(trace["support_key_sha256"]) == 64


def test_bool_coordinate_fails_closed_instead_of_becoming_exact_int() -> None:
    problem = {
        "task": "solve",
        "id": "bool-coordinate-counterexample",
        "variables": {"names": ["x"]},
        "construction": [
            {"name": "A", "expr": "Point(True, 0)"},
            {"name": "B", "expr": "Point(x, 0)"},
        ],
        "constraints": [{"def": "Distance(A, B)", "value": 1}],
        "guards": [],
        "answer": "Distance(A, B)",
        "post_process": "",
    }
    compilation = compile_residual_plan(_build(problem), source_sha256="1" * 64)
    assert compilation.plan is None


def test_variable_circle_validation_matches_reference_fault_semantics() -> None:
    problem = {
        "task": "solve",
        "id": "negative-radius-counterexample",
        "variables": {"names": ["r"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "gamma", "expr": "Circle(O, r)"},
            {"name": "P", "expr": "PointOnCircle(gamma, 0.25)"},
        ],
        "constraints": [{"def": "Distance(O, P)", "value": 1}],
        "guards": [],
        "answer": "Distance(O, P)",
        "post_process": "",
    }
    reference = _build(problem)
    compilation = compile_residual_plan(reference, source_sha256="2" * 64)
    assert compilation.plan is not None
    assert compilation.plan.raw_libmp_program is not None
    assert all(math.isnan(value) for value in compilation.plan.evaluate([-1.0]))


def test_dispatcher_uses_typed_signature_authority_not_legacy_predicate(
    monkeypatch,
) -> None:
    document, evaluator = _case001()
    document["construction"].append({"name": "unused", "expr": "Intersect(Line(A, B), Gamma, n=1)"})
    trace = support_decision_trace(
        document, CompilationResult(plan=None, fallback_reason="preflight")
    )
    assert "n" in trace["selector_kind_set"]

    monkeypatch.setattr(compiled_module, "supports_compilation_key", lambda *_args: False)
    compilation = compile_residual_plan(evaluator, source_sha256="3" * 64)
    assert compilation.plan is not None
    assert "PointOnCircle" in compilation.attempted_ast_opcode_set
    assert not any(
        value.startswith("unsupported_") for value in compilation.attempted_operand_result_type_set
    )


def test_fast_path_ast_and_wall_resource_limits_fail_closed(monkeypatch) -> None:
    _document, evaluator = _case001()
    monkeypatch.setattr(compiled_module, "MAX_COMPILATION_AST_NODES", 1)
    node_limited = compile_residual_plan(evaluator, source_sha256="4" * 64)
    assert node_limited.plan is None
    assert "AST node limit" in str(node_limited.fallback_reason)

    monkeypatch.setattr(compiled_module, "MAX_COMPILATION_AST_NODES", 200_000)
    monkeypatch.setattr(compiled_module, "MAX_COMPILATION_WALL_SECONDS", 0.0)
    wall_limited = compile_residual_plan(evaluator, source_sha256="5" * 64)
    assert wall_limited.plan is None
    assert "wall limit" in str(wall_limited.fallback_reason)


@pytest.mark.parametrize("bad_operand", ["x", "Z"])
def test_point_distance_fast_path_rejects_unresolved_or_nonpoint_names(
    bad_operand: str,
) -> None:
    problem = {
        "task": "solve",
        "id": "unknown-point-distance-type-error",
        "variables": {"names": ["x"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(x, 1)"},
        ],
        "constraints": [{"def": f"Distance(A, {bad_operand})", "value": 1}],
        "guards": [],
        "answer": "Distance(A, B)",
        "post_process": "",
    }
    reference = _build(problem)
    compilation = compile_residual_plan(reference, source_sha256="5" * 64)
    assert compilation.plan is None
    assert compilation.fallback_reason is not None
    expected = reference.evaluate_float_residual([2.0])
    assert all(math.isnan(value) for value in expected.residual_vector)


def test_product_dispatcher_uses_actual_general_typed_signatures() -> None:
    problem = {
        "task": "solve",
        "id": "unknown-general-dispatch-signatures",
        "variables": {"names": ["bx", "by", "cx", "cy"]},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(bx, by)"},
            {"name": "C", "expr": "Point(cx, cy)"},
            {"name": "M", "expr": "Midpoint(A, B)"},
            {"name": "I", "expr": "Incenter(A, B, C)"},
        ],
        "constraints": [{"def": "Distance(M, I)", "value": 1}],
        "guards": [],
        "answer": "Distance(M, I)",
        "post_process": "",
    }
    reference = _build(problem)
    compilation = compile_residual_plan(reference, source_sha256="6" * 64)
    assert compilation.plan is not None
    assert compilation.plan.raw_libmp_program is None
    assert compilation.plan.flat_tape_program is not None
    assert compilation.fallback_reason is None
    metadata = compilation.plan.metadata()
    assert metadata["backend_selection_chain"] == [
        "typed",
        "raw_semantic_gate",
        "flat_tape",
    ]
    assert metadata["flat_tape_fallback_reason"] is None
    assert {"MidpointPP", "Incenter"} <= set(compilation.attempted_ast_opcode_set)
    expected = reference.evaluate_float_residual([3.0, 0.25, 1.0, 4.0])
    observed = compilation.plan.evaluate([3.0, 0.25, 1.0, 4.0])
    assert [_bits(value) for value in observed] == [
        _bits(value) for value in expected.residual_vector
    ]


def test_unsupported_search_program_preserves_reference_evaluator_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = object()
    budget = SimpleNamespace(evaluator=reference)
    monkeypatch.setattr(
        search_worker_module,
        "compile_residual_plan",
        lambda evaluator, *, source_sha256: CompilationResult(
            plan=None,
            fallback_reason=f"unsupported:{source_sha256}:{evaluator is reference}",
        ),
    )
    monkeypatch.setattr(
        search_worker_module,
        "precompute_constant_constructions",
        lambda _evaluator: pytest.fail("fallback must not construct a partial facade"),
    )
    monkeypatch.setattr(
        search_worker_module,
        "install_fused_evaluation",
        lambda _budget: {
            "schema_version": "geotarget.fused-evaluation-budget/v1",
            "enabled": True,
            "case_specific_routing": False,
        },
    )

    evaluator, metadata = search_worker_module._activate_compiled_evaluator(
        reference,
        budget,
        source_sha256="7" * 64,
    )

    assert evaluator is reference
    assert budget.evaluator is reference
    assert metadata["whole_problem_reference_identity"] is True
    assert metadata["whole_problem_reference_semantics_fused"] is True
    assert metadata["fused_evaluation"]["enabled"] is True
    assert metadata["constant_constructions"] == []
