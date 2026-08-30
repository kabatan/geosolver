"""Counterexamples from the second audit; paired with valid nearby configurations."""

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.compiler import compile_problem
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.ir.errors import IRCompileError, IRValidationError
from geosolver.problem.models import GeometryProblem


def evaluator(constraints, *, construction=(), guards=(), variables=("x",), answer="7"):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "id": "second-audit",
                "task": "solve",
                "variables": {"names": list(variables)},
                "construction": list(construction),
                "constraints": [{"def": text, "value": 0} for text in constraints],
                "guards": list(guards),
                "answer": answer,
            }
        )
    )


@pytest.mark.parametrize("source", ["1.000000000000000000000000000001", "1e1000"])
def test_public_compiler_keeps_numeric_lexemes(source):
    problem = GeometryProblem(
        id="lexeme", variables=[], constructions=[], conditions=[], target=source
    )
    compiled = compile_problem(problem)
    with mp.workdps(150):
        assert safe_eval_expr_hp(compiled.target.source, {"mpf": mp.mpf}) == mp.mpf(source)


def test_internal_power_compatibility_preserves_source_offsets():
    assert safe_eval_expr_hp("2^3+4", {"mpf": mp.mpf}) == 12


def test_float_and_hp_selector_evidence_identifies_the_physical_branch():
    from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.problem.evaluation_trace import evaluation_scope
    from geosolver.problem.ir.compiler import safe_eval_expr

    source = "Intersect(Circle(Point(0,0),1),Line(Point(-2,0),Point(2,0)),near=Point(2,0))"
    traces = []
    for evaluate, context in (
        (safe_eval_expr, _get_geometry_context()),
        (safe_eval_expr_hp, _get_high_precision_context(120)),
    ):
        with mp.workdps(120), capture_selection_trace() as trace:
            for name in ("P", "Q"):
                with evaluation_scope(name):
                    evaluate(source, context)
        traces.append(trace)
    for trace in traces:
        assert len(trace) == 2 and trace[0].call_site_id != trace[1].call_site_id
        assert trace[0].candidate_count == 2 and trace[0].selected_index == 1
        assert trace[0].margin > 0
    assert tuple(tuple(mp.mpf(str(v)) for v in p) for p in traces[0][0].candidates) == (
        traces[1][0].candidates
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"variables": {"names": ["x", "x"]}},
        {"v": []},
        {"m": 2},
        {"bounds": []},
        {"task": "optimize"},
        {"maximize": True},
    ],
)
def test_explicit_malformed_ir_is_not_silently_repaired(changes):
    from geosolver.problem.ir.parser import load_ir

    document = {
        "task": "solve",
        "variables": {"names": ["x"]},
        "constraints": ["x-1"],
        **changes,
    }
    with pytest.raises(IRValidationError):
        load_ir(document)


@pytest.mark.parametrize("bounds", [[[100, 200]], [[100, None]], [[2, 2]]])
def test_explicit_bounds_are_not_replaced_by_search_heuristics(bounds):
    from geosolver.problem.domain_bounds import mathematical_bounds, search_bounds
    from geosolver.problem.ir.parser import load_ir

    spec = load_ir({"task": "solve", "variables": {"names": ["x"]}, "bounds": bounds})
    axis = mathematical_bounds(spec)["x"]
    assert axis.lower == bounds[0][0]
    assert search_bounds(spec)[0][0] == bounds[0][0]
    if bounds[0][1] is not None:
        assert search_bounds(spec)[0][1] == bounds[0][1]


def test_negative_scale_is_local_to_dependent_axes():
    from geosolver.problem.domain_bounds import search_bounds

    for value in (-100, 100):
        ev = evaluator([f"x-({value})"], variables=("x", "y"))
        assert search_bounds(ev.bundle.spec) == [(-200, 200), (-10, 10)]


@pytest.mark.parametrize("t", ["-1", "2"])
def test_segment_rejects_extrapolation_in_both_contexts(t):
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.problem.ir.compiler import safe_eval_expr

    expression = f"PointOnSegment(Point(0,0),Point(1,0),{t})"
    with pytest.raises(IRCompileError):
        safe_eval_expr(expression, _get_geometry_context())
    with pytest.raises(IRCompileError):
        safe_eval_expr_hp(expression, _get_high_precision_context(80))


@pytest.mark.parametrize("t", ["-2", "2", "0.4"])
def test_extension_migration_preserves_coordinates(t):
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )

    with mp.workdps(120):
        ctx = _get_high_precision_context(120)
        ctx["A"] = safe_eval_expr_hp("Point(2,3)", ctx)
        ctx["B"] = safe_eval_expr_hp("Point(5,7)", ctx)
        ctx["L"] = safe_eval_expr_hp("Line(A,B)", ctx)
        p = safe_eval_expr_hp(
            f"PointOnLine(L,-L.b*(A.x+({t})*(B.x-A.x))+L.a*(A.y+({t})*(B.y-A.y)))", ctx
        )
        assert abs(p.x - (2 + mp.mpf(t) * 3)) < mp.mpf("1e-110")
        assert abs(p.y - (3 + mp.mpf(t) * 4)) < mp.mpf("1e-110")


@pytest.mark.parametrize("constraint", ["x", "x**2"])
def test_forbidden_zero_boundary_is_not_a_solution(constraint):
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator([constraint], guards=["x>0"]), values=(mp.mpf("1e-40"),)
        )
    assert not result.verified


def test_tiny_positive_solution_is_not_a_boundary():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(["x-1e-40"], guards=["x>0"]), values=(mp.mpf("1e-40"),)
        )
    assert result.verified


def test_periodic_circle_parameter_is_not_a_hard_unit_interval():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(
                ["x-2"],
                construction=[{"name": "P", "expr": "PointOnCircle(Circle(Point(0,0),1),x)"}],
                answer="x",
            ),
            values=(mp.mpf(2),),
        )
    assert result.verified and result.answer_hp == 2


def test_redundant_geometric_identity_keeps_roundoff_scale():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(
                ["x*x-2", "Distance(A,D)-p*Distance(A,B)"],
                variables=("x", "p"),
                construction=[
                    {"name": "A", "expr": "Point(0,0)"},
                    {"name": "B", "expr": "Point(x,1)"},
                    {"name": "D", "expr": "PointOnSegment(A,B,p)"},
                ],
                guards=["x>0", "p>0", "p<1"],
                answer="x*x",
            ),
            values=(mp.sqrt(2), mp.mpf("0.1234567")),
        )
    assert result.verified and abs(result.answer_hp - 2) < mp.mpf("1e-100")


def test_large_cancelled_terms_do_not_hide_a_nonlinear_contradiction():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(["(1e200+x)-(1e200+x+1+x*x)"]), values=(mp.mpf(0),)
        )
    assert not result.verified


def test_noisy_redundant_row_does_not_erase_reliable_rank():
    from geosolver.engine.standard.evaluation.verification_numerics import correction

    with mp.workdps(500):
        change, uncertainty = correction(
            [mp.mpf("1e-350"), mp.mpf(-1)],
            [[mp.mpf("1e-300")], [mp.mpf(1)]],
            [[mp.mpf("1e-299")], [mp.mpf("1e-450")]],
            [mp.mpf(1)],
            500,
        )
    assert change == (mp.mpf(1),) and mp.isfinite(uncertainty[0])


@pytest.mark.parametrize("parameter", [None, "0.01", "0.0125", "0.016"])
def test_aime_2001_1_9_valid_witness_survives_independent_confirmation(parameter):
    from pathlib import Path

    from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
    from geosolver.engine.standard.orchestration.assemble_exact_results import (
        assemble_exact_results,
    )

    problem = GeometryProblem.model_validate_json(
        (Path(__file__).resolve().parents[1] / "benchmarks/dsl/aime-2001-1-9.json").read_text()
    )
    ev = build_ir_evaluator(load_problem_bundle(problem.engine_document()))
    with mp.workdps(180):
        a = (10 - mp.sqrt(85)) / 45
        if parameter is None:
            p, q, r = a, a, mp.mpf(2) / 3 - 2 * a
        else:
            p = mp.mpf(parameter)
            total = mp.mpf(2) / 3 - p
            q = (total - mp.sqrt(2 * (mp.mpf(2) / 5 - p * p) - total * total)) / 2
            r = total - q
        point = (mp.mpf("3.5"), mp.sqrt(627) / 2, p, q, r)
        candidate = RefinedCandidate(point, mp.mpf("1e-170"), mp.mpf(16) / 45, "stalled", ())
        result = assemble_exact_results(refined_candidates=(candidate,), evaluator=ev)
    assert result.answer_values == ("16/45",)


def test_gauge_freedom_and_redundant_equations_are_allowed():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(
                ["x-y-1", "2*(x-y-1)"], variables=("x", "y"), guards=["y>0"], answer="x-y"
            ),
            values=(mp.mpf(3), mp.mpf(2)),
        )
    assert result.verified and result.answer_hp == 1


def test_closed_singleton_is_eliminated_as_a_fixed_variable():
    ev = evaluator(["x-2"], guards=["Bound(x,(2,2))"], answer="x")
    assert ev.bundle.var_names == ()
    assert verify_final_candidate(evaluator=ev, values=()).answer_hp == 2


def test_affine_parameter_domain_is_projected_but_nonlinear_is_not():
    from geosolver.problem.domain_bounds import mathematical_bounds
    from geosolver.problem.ir.schema import IRConstruction, IRSpec, IRVariableSpec

    for expression, expected in (("x/120", 120), ("x*x", None)):
        spec = IRSpec(
            task="solve",
            variables=IRVariableSpec(names=["x"]),
            construction=[IRConstruction("P", f"PointOnSegment(A,B,{expression})")],
        )
        assert mathematical_bounds(spec)["x"].upper == expected


@pytest.mark.parametrize(
    "selector, line, condition",
    [
        ("near=P", "Line(Point(-2,0),Point(2,0))", "Q.x+2"),
        ("n=1", "Line(Point(0,0),Point(x,1))", "Q.y+2"),
    ],
)
def test_branch_crossing_cannot_normalize_an_order_one_residual(selector, line, condition):
    constructions = [
        {"name": "C", "expr": "Circle(Point(0,0),1)"},
        {"name": "L", "expr": line},
        {"name": "P", "expr": "Point(x,0)"},
        {"name": "Q", "expr": f"Intersect(C,L,{selector})"},
    ]
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator([condition], construction=constructions), values=(mp.mpf("1e-60"),)
        )
    assert not result.verified
