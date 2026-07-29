from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

from geotarget.continuation import _load_frozen
from geotarget.typed_refnum_ir import (
    ConsumerCapability,
    ConsumerRole,
    NumericEffectPolicy,
    NumericExactness,
    analyze_numeric_effects,
    certify_numeric_effects,
    compile_typed_refnum_program,
)


def _build(document):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_numeric_effect_test_runtime", base.PRECISION_RUNTIME)
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )
    return evaluator


def _problem(*, derived_point: bool, identifier: str = "unknown-effect-program") -> dict:
    construction = [
        {"name": "O", "expr": "Point(0, 0)"},
        {"name": "B", "expr": "Point(bx, by)"},
        {"name": "P", "expr": "Point(px, py)"},
        {"name": "omega", "expr": "Circle(O, abs(radius))"},
    ]
    point_name = "P"
    if derived_point:
        construction.append(
            {
                "name": "X",
                "expr": (
                    "Point((7/Distance(O, B))*B.x, "
                    "(7/Distance(O, B))*B.y)"
                ),
            }
        )
        point_name = "X"
    return {
        "task": "solve",
        "id": identifier,
        "variables": {"names": ["bx", "by", "px", "py", "radius"]},
        "construction": construction,
        "constraints": [
            {"def": f"OnCircle({point_name}, omega)", "value": 0},
            {"def": "Distance(P, B)", "value": 1},
        ],
        "guards": [],
        "answer": "px",
        "post_process": "",
    }


def _symbolic_root_only_policy() -> NumericEffectPolicy:
    permissive = ConsumerCapability(
        allow_may_fault=True,
        allow_may_nonfinite=True,
        allow_signed_zero=True,
        allow_subnormal=True,
        allow_branch_sensitive=True,
        preserve_symbolic_composition=False,
    )
    root = replace(permissive, preserve_symbolic_composition=True)
    return NumericEffectPolicy(
        default=permissive,
        by_role={ConsumerRole.CONSTRAINT_SIDE_ROOT: root},
    )


def test_effect_lattice_propagates_exact_bf53_and_numeric_hazards() -> None:
    program = compile_typed_refnum_program(_build(_problem(derived_point=True)).bundle)
    analysis = analyze_numeric_effects(program)
    exact = [node for node in analysis.nodes if node.opcode == "ExactInt"]
    inputs = [node for node in analysis.nodes if node.opcode == "BF53Input"]
    divisions = [node for node in analysis.nodes if node.opcode == "Div"]
    products = [node for node in analysis.nodes if node.opcode == "Mult"]
    assert exact and all(node.effects.exactness is NumericExactness.EXACT for node in exact)
    assert inputs and all(node.effects.exactness is NumericExactness.BF53 for node in inputs)
    assert all(node.effects.may_signed_zero and node.effects.may_subnormal for node in inputs)
    assert divisions and all(
        node.effects.may_fault
        and node.effects.may_nonfinite
        and node.effects.branch_sensitive
        for node in divisions
    )
    assert products and any(
        node.effects.exactness is NumericExactness.MIXED for node in products
    )


def test_consumer_role_policy_rejects_symbolic_geometry_composition_generically() -> None:
    direct = compile_typed_refnum_program(_build(_problem(derived_point=False)).bundle)
    derived = compile_typed_refnum_program(_build(_problem(derived_point=True)).bundle)
    direct_result = certify_numeric_effects(
        direct.numeric_effect_analysis(), _symbolic_root_only_policy()
    )
    derived_result = certify_numeric_effects(
        derived.numeric_effect_analysis(), _symbolic_root_only_policy()
    )
    assert direct_result.certified
    assert not derived_result.certified
    assert any(
        issue.edge.role
        in {ConsumerRole.ARITHMETIC_OPERAND, ConsumerRole.GEOMETRY_COORDINATE}
        and "requires_symbolic_composition" in issue.unsupported_effects
        for issue in derived_result.issues
    )
    assert all(
        "Distance" not in effect
        for issue in derived_result.issues
        for effect in issue.unsupported_effects
    )


def test_effect_analysis_is_problem_identity_free() -> None:
    first = compile_typed_refnum_program(
        _build(_problem(derived_point=True, identifier="first-id")).bundle
    )
    second = compile_typed_refnum_program(
        _build(_problem(derived_point=True, identifier="unrelated-id")).bundle
    )
    assert (
        first.numeric_effect_analysis().fingerprint()
        == second.numeric_effect_analysis().fingerprint()
    )


def test_consumer_capability_can_restrict_exact_vs_bf53_per_role() -> None:
    problem = _problem(derived_point=False)
    problem["construction"].append(
        {"name": "M", "expr": "Point(1 + bx, by)"}
    )
    analysis = compile_typed_refnum_program(_build(problem).bundle).numeric_effect_analysis()
    permissive = ConsumerCapability(
        allow_may_fault=True,
        allow_may_nonfinite=True,
        allow_signed_zero=True,
        allow_subnormal=True,
        allow_branch_sensitive=True,
        preserve_symbolic_composition=True,
    )
    bf53_coordinates = replace(
        permissive,
        accepted_exactness=frozenset({NumericExactness.BF53}),
    )
    result = certify_numeric_effects(
        analysis,
        NumericEffectPolicy(
            default=permissive,
            by_role={ConsumerRole.GEOMETRY_COORDINATE: bf53_coordinates},
        ),
    )
    assert not result.certified
    assert any(
        issue.edge.role is ConsumerRole.GEOMETRY_COORDINATE
        and "exactness:mixed" in issue.unsupported_effects
        for issue in result.issues
    )


def test_intersection_selector_edges_are_branch_sensitive_and_typed() -> None:
    problem = {
        "task": "solve",
        "id": "unknown-selector-effect",
        "variables": {"names": ["rx", "ry"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "A", "expr": "Point(-10, 0)"},
            {"name": "B", "expr": "Point(10, 0)"},
            {"name": "R", "expr": "Point(rx, ry)"},
            {"name": "axis", "expr": "Line(A, B)"},
            {"name": "omega", "expr": "Circle(O, 5)"},
            {"name": "P", "expr": "Intersect(axis, omega, near=R)"},
        ],
        "constraints": [{"def": "Distance(P, O)", "value": 5}],
        "guards": [],
        "answer": "rx",
        "post_process": "",
    }
    analysis = analyze_numeric_effects(
        compile_typed_refnum_program(_build(problem).bundle)
    )
    selector_edges = [edge for edge in analysis.edges if edge.role is ConsumerRole.SELECTOR]
    assert len(selector_edges) == 1
    assert selector_edges[0].consumer_opcode == "Intersect"
    assert selector_edges[0].consumer_effects is not None
    assert selector_edges[0].consumer_effects.branch_sensitive
    intersect = next(node for node in analysis.nodes if node.opcode == "Intersect")
    assert intersect.effects.may_fault
    assert intersect.effects.may_nonfinite
    assert intersect.effects.branch_sensitive
