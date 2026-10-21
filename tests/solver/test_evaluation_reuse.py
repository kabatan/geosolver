"""Evaluation reuse contracts and numerical regressions."""

import importlib
from collections import OrderedDict
from dataclasses import replace
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import (
    candidate_attempt,
)
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.selection_trace import (
    capture_selection_trace,
    use_selection_symbol,
)
from geosolver.engine.standard.evaluation.snapshots import evaluation_session, numerical_snapshot
from geosolver.engine.standard.evaluation.verification_domains import DomainVerifier, _combine
from geosolver.engine.standard.evaluation.verification_system import sample_equations
from geosolver.engine.standard.orchestration.run_initial_probe import run_initial_probe
from geosolver.engine.standard.precision.type_guards.ensure_no_float import (
    ValidatedHPContext,
    ensure_no_float,
)
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem import domain_bounds
from geosolver.problem.evaluation_trace import capture_calls
from geosolver.runtime.deadline import deadline_scope


def test_shared_dependency_dag_is_expanded_once(monkeypatch):
    construction = [SimpleNamespace(name="c0", expr="x+100")]
    construction.extend(
        SimpleNamespace(name=f"c{i}", expr=f"c{i - 1}+c{i - 1}") for i in range(1, 45)
    )
    spec = SimpleNamespace(
        variables=SimpleNamespace(resolved_names=lambda: ["x"]),
        construction=construction,
        constraints=["c44"],
        v=[0],
        logical_plans=(),
    )
    monkeypatch.setattr(
        domain_bounds,
        "mathematical_bounds",
        lambda spec: {"x": SimpleNamespace(lower=None, upper=None)},
    )
    calls = 0
    original = domain_bounds.ast.parse

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(domain_bounds.ast, "parse", counted)
    assert domain_bounds.search_bounds(spec) == [(-200, 200)]
    assert calls <= 50


def test_static_residual_dependencies_include_targets_and_shared_constructions():
    from geosolver.engine.standard.problem.analysis_plan import ProblemAnalysisPlan

    spec = SimpleNamespace(
        construction=[SimpleNamespace(name="A", expr="x+x"), SimpleNamespace(name="B", expr="A+3")],
        constraints=["B-y", "z"],
        v=[0, "x"],
        logical_plans=(),
    )
    plan = ProblemAnalysisPlan(SimpleNamespace(spec=spec, var_names=("x", "y", "z")))
    assert plan.residual_variable_dependencies == (frozenset((0, 1)), frozenset((0, 2)))


@pytest.mark.parametrize("precision", [30, 100])
@pytest.mark.parametrize("scale", ["1e-100", "1", "1e100"])
@pytest.mark.parametrize(
    "vertices,convex,crossed",
    [
        ([(0, 0), (2, 0), (2, 2), (0, 2)], True, False),
        ([(0, 0), (2, 2), (2, 0), (0, 2)], False, True),
        ([(0, 0), (2, 0), (1, 1), (2, 2), (0, 2)], False, False),
        ([(0, 0), (2, 0), (2, 2), (0, 0)], False, True),
    ],
)
def test_polygon_predicate_reuse_preserves_scaled_degeneracy_and_topology(
    precision, scale, vertices, convex, crossed
):
    from geosolver.geometry.mp.mp_core_types import MPPoint
    from geosolver.geometry.mp.mp_polygon_checks import mp_has_self_intersection, mp_is_convex

    with mp.workdps(precision):
        factor = mp.mpf(scale)
        points = [MPPoint(x * factor, y * factor) for x, y in vertices]
        for _ in range(2):
            assert mp_is_convex(*points) is convex
            assert mp_has_self_intersection(*points) is crossed


def test_polygon_predicate_reuse_invalidates_precision_and_exact_coordinate_changes():
    from geosolver.geometry.mp.mp_core_types import MPPoint
    from geosolver.geometry.mp.mp_polygon_checks import mp_is_convex

    with mp.workdps(100):
        points = [MPPoint(0, 0), MPPoint(1, 0), MPPoint(1, mp.mpf("1e-70"))]
        assert mp_is_convex(*points) is True
    with mp.workdps(40):
        assert mp_is_convex(*points) is False
    with mp.workdps(100):
        assert mp_is_convex(*points) is True
        # Reusing a mutable point object cannot return its previous answer.
        points[2].y = mp.mpf(0)
        assert mp_is_convex(*points) is False
        points[2].y = mp.mpf("1e-70")
        assert mp_is_convex(*points) is True


def evaluator():
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "construction": [
                    {"name": "A", "expr": "Point(0,0)"},
                    {"name": "B", "expr": "Point(5,0)"},
                    {"name": "C", "expr": "Point(5,12)"},
                    {"name": "D", "expr": "Point(x,y)"},
                ],
                "constraints": ["Angle(A,C,B)", "Distance(A,D)-2"],
                "guards": ["Dot(Vector(A,D),Vector(A,D))>1", "x>0"],
                "answer": "Angle(A,D,B)",
            }
        )
    )


@pytest.mark.parametrize("precision", [80, 180, 500])
def test_constant_scalar_reuse_replays_evidence_and_keeps_precision(monkeypatch, precision):
    from geosolver.engine.standard.evaluation import snapshots

    ev = evaluator()
    source = "Angle(A,C,B)"
    original = snapshots.safe_eval_expr_hp
    counts = []

    def evaluate(expression, context):
        if expression == source:
            counts.append(mp.prec)
        return original(expression, context)

    monkeypatch.setattr(snapshots, "safe_eval_expr_hp", evaluate)
    results = []
    with evaluation_session(ev), mp.workdps(precision), high_precision_mode():
        for x in (1, 2, 3):
            snap = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [mp.mpf(x), mp.mpf(1)], ev.bundle.base_context
            )
            snap.for_expressions([source])
            with capture_calls() as calls, capture_selection_trace() as trace:
                value = snap.evaluate(source)
            results.append((value, calls, trace))
        assert len(counts) == 1
        assert results[0] == results[1] == results[2]
        assert results[0][1]
        with mp.workdps(precision + 30):
            other = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [mp.mpf(1), mp.mpf(1)], ev.bundle.base_context
            )
            other.for_expressions([source])
            other.evaluate(source)
        assert len(counts) == 2
        # Mutable point attributes and variable bindings must invalidate reuse.
        snap.context["C"].x = mp.mpf(6)
        assert snap.evaluate(source) != value
        assert len(counts) == 3
        with use_selection_symbol("other-scope"), capture_calls() as scoped:
            snap.evaluate(source)
        assert all(row[0].startswith("other-scope:") for row in scoped)


def test_guard_truth_penalty_share_leaves_without_changing_values_or_trace(monkeypatch):
    from geosolver.engine.standard.evaluation import snapshots
    from geosolver.engine.standard.interpreter.guards.compile import (
        guard_hard_satisfied,
        guard_violation_value,
    )

    ev = evaluator()
    with mp.workdps(180), evaluation_session(ev):
        snap = numerical_snapshot(
            ev.bundle.spec, ev.bundle.var_names, [mp.mpf(2), mp.mpf(1)], ev.bundle.base_context
        )
        context = snap.for_expressions(ev.bundle.spec.guards)
        guard = ev.compiled_guards[0]
        original = snapshots.safe_eval_expr_hp
        calls = []

        def evaluate(expression, ctx):
            calls.append(expression)
            return original(expression, ctx)

        monkeypatch.setattr(snapshots, "safe_eval_expr_hp", evaluate)

        def check(ctx):
            with capture_calls() as evidence, capture_selection_trace() as trace:
                result = guard_violation_value(guard, ctx), guard_hard_satisfied(guard, ctx)
            return result, evidence, trace

        cached = check(context)
        assert len(calls) == 2  # Dot(...) and 1, shared between the two operations.
        uncached = check(dict(context))
        assert cached[0] == uncached[0] and cached[2] == uncached[2]

        def geometry_value(value):
            if hasattr(value, "x") and hasattr(value, "y"):
                return value.x._mpf_, value.y._mpf_
            return value

        def call_values(rows):
            return [
                (site, name, tuple(map(geometry_value, args)), kwargs, geometry_value(result))
                for site, name, args, kwargs, result in rows
            ]

        assert call_values(cached[1]) == call_values(uncached[1])
        context["D"].x = mp.mpf(0)
        context["D"].y = mp.mpf(0)
        assert check(context)[0] == check(dict(context))[0]
        assert check(context)[0] != cached[0]


def test_validated_context_does_not_trust_mutable_containers_or_replacements():
    external = {"nested": [mp.mpf(1)]}
    context = ValidatedHPContext({"value": mp.mpf(1), "external": external})
    fork = context.fork()
    ensure_no_float(fork, context="fixture")
    external["nested"][0] = 1.25
    with pytest.raises(HighPrecisionContaminationError, match="external.nested"):
        ensure_no_float(fork, context="fixture")
    external["nested"][0] = mp.mpf(1)
    fork["value"] = 1.0
    with pytest.raises(HighPrecisionContaminationError, match="value"):
        ensure_no_float(fork, context="fixture")
    ensure_no_float(context, context="original")
    with pytest.raises(TypeError):
        context._base["value"] = 1.0
    del fork["value"]
    with pytest.raises(KeyError):
        _ = fork["value"]


def test_completed_unresolved_revision_reused_but_new_revision_or_schedule_is_not(monkeypatch):
    assembly = importlib.import_module(
        "geosolver.engine.standard.orchestration.assemble_exact_results"
    )
    ev = SimpleNamespace(final_verification_cache=OrderedDict())
    candidate = SimpleNamespace(candidate_key="a", revision=0, x_hp=(mp.mpf(1),))
    calls = []
    unresolved = SimpleNamespace(verified=False, status="unresolved")

    def verify(**kwargs):
        calls.append(kwargs)
        return unresolved

    monkeypatch.setattr(assembly, "verify_final_candidate", verify)
    assert assembly._verify_revision(ev, candidate) is unresolved
    assert assembly._verify_revision(ev, candidate) is unresolved
    assert len(calls) == 1
    for updates, schedule in (
        ({"revision": 1}, None),
        ({"candidate_key": "b"}, None),
        ({"x_hp": (mp.mpf(2),)}, None),
        ({}, (250, 500)),
    ):
        other = SimpleNamespace(**(vars(candidate) | updates))
        assembly._verify_revision(ev, other, precision_schedule=schedule)
    assert len(calls) == 5
    with deadline_scope(0), pytest.raises(TimeoutError):
        assembly._verify_revision(ev, candidate)


def test_interrupted_verification_is_never_cached(monkeypatch):
    assembly = importlib.import_module(
        "geosolver.engine.standard.orchestration.assemble_exact_results"
    )
    ev = SimpleNamespace(final_verification_cache=OrderedDict())
    candidate = SimpleNamespace(candidate_key="a", revision=0, x_hp=(mp.mpf(1),))

    def timeout(**kwargs):
        raise TimeoutError("fixture")

    monkeypatch.setattr(assembly, "verify_final_candidate", timeout)
    for _ in range(2):
        with pytest.raises(TimeoutError):
            assembly._verify_revision(ev, candidate)
    assert not ev.final_verification_cache


@pytest.mark.parametrize("precision", [80, 180, 500])
@pytest.mark.parametrize("offset", ["0", "1e-100", "1"])
def test_margin_batch_preserves_scalar_error_estimates(precision, offset):
    with mp.workdps(precision):
        point = (mp.mpf(offset), mp.mpf(2))
        args = (None, point, (mp.mpf("1e-60"),) * 2, (mp.mpf(1),) * 2, precision)
        batched, scalar = DomainVerifier(*args), DomainVerifier(*args)
        counter = [0]

        def margins(p):
            counter[0] += 1
            return {"positive": p[0] ** 2 + p[1] ** 2, "boundary": abs(p[0]), "bad": mp.nan}

        state = batched.verify_margins(margins, "fixture:")
        batch_calls = counter[0]
        counter[0] = 0
        states = []
        for key in margins(point):
            value, error = scalar.measure(lambda p, k=key: (margins(p)[k], ()), "fixture:" + key)
            states.append(True if value > 100 * error else (False if value <= 0 else None))
        assert state == _combine(states)
        for a, b in zip(batched.evidence, scalar.evidence, strict=True):
            assert a["condition"] == b["condition"]
            for field in ("value", "uncertainty"):
                assert a[field]._mpf_ == b[field]._mpf_
        assert batch_calls < counter[0]


@pytest.mark.parametrize("precision", [80, 180, 500])
def test_trial_batch_preserves_scalar_branches_values_and_errors(precision):
    ev = evaluator()
    with mp.workdps(precision), high_precision_mode():
        equations = ev.verification_equations
        point = (mp.mpf(1), mp.mpf(2))
        a = sample_equations(equations, point, precision)
        b = tuple(e.sample(point, precision) for e in equations)
        assert a == b


def test_pi_priority_is_only_an_order_hint_and_wrong_pi_proposal_falls_back(monkeypatch):
    module = importlib.import_module("geosolver.engine.standard.exact_assembly.identify_answer")
    from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
    from geosolver.runtime.symbolic_operations import decode_identification, dispatch

    with mp.workdps(180):
        result = ExactIdentificationResult(
            "identified", "fixture", 120, None, None, "pi", mp.mpf(0), None
        )
        pi_calls, normal_calls = [], []

        def pi_propose(**kwargs):
            pi_calls.append(kwargs)
            return result

        def normal_propose(**kwargs):
            normal_calls.append(kwargs)
            return replace(
                result, selected_exact_value="2", minimal_polynomial=(1, -2), polynomial_degree=1
            )

        monkeypatch.setattr(module, "_identify_affine_pi_result", pi_propose)
        monkeypatch.setattr(module, "_identify_answer_proposal", normal_propose)

        def identify(value, prefer):
            return decode_identification(
                dispatch(
                    "identify",
                    {
                        "value": value._mpf_,
                        "tier": "strict",
                        "precision": 120,
                        "uncertainty": mp.mpf("1e-100")._mpf_,
                        "prefer_affine_pi": prefer,
                    },
                )
            )

        good = identify(+mp.pi, True)
        assert good.descriptor is not None and not normal_calls
        wrong = identify(mp.mpf(2), True)
        assert wrong.selected_exact_value == "2" and len(normal_calls) == 1
        identify(mp.mpf(2), False)
        assert len(pi_calls) == 2 and len(normal_calls) == 2
        assert evaluator().bundle.analysis_plan.answer_uses_pi


def test_hp_contract_retains_variadic_and_default_argument_checks():
    from geosolver.engine.standard.precision.type_guards.hp_contract import hp_contract

    @hp_contract(input_names=("values", "options"))
    def variadic(*values, **options):
        return mp.mpf(0)

    @hp_contract(input_names=("value",))
    def default(value=1.0):
        return mp.mpf(0)

    with high_precision_mode():
        assert variadic(mp.mpf(1), x=mp.mpf(2)) == 0
        for args, kwargs in (((mp.mpf(1), 2.0), {}), ((), {"x": 1.0})):
            with pytest.raises(HighPrecisionContaminationError):
                variadic(*args, **kwargs)
        with pytest.raises(HighPrecisionContaminationError):
            default()


def test_bad_margin_row_does_not_discard_independent_evidence():
    with mp.workdps(80):
        verifier = DomainVerifier(None, (mp.mpf(1),), (mp.mpf("1e-60"),), (mp.mpf(1),), 80)
        assert verifier.verify_margins(lambda p: {"bad": None, "valid": p[0] + 2}, "") is None
        assert [r["condition"] for r in verifier.evidence] == ["valid"]
        assert verifier.evidence[0]["value"] == 3


def test_evicted_snapshot_is_not_retained_by_its_surviving_context():
    import gc
    import weakref

    from geosolver.engine.standard.evaluation.snapshots import evaluate_scalar_expression

    ev = evaluator()
    ev.evaluation_store.capacity = 1
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        with mp.workdps(180), evaluation_session(ev):
            snapshot = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [mp.mpf(1), mp.mpf(2)], ev.bundle.base_context
            )
            context = snapshot.for_expressions(["Distance(A,D)"])
            before = evaluate_scalar_expression("Distance(A,D)", context)
            reference = weakref.ref(snapshot)
            del snapshot
            numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [mp.mpf(2), mp.mpf(3)], ev.bundle.base_context
            )
            assert reference() is None
            # A retained verifier context still works after its cache owner dies.
            assert evaluate_scalar_expression("Distance(A,D)", context) == before
    finally:
        if was_enabled:
            gc.enable()


def test_speculative_pi_prefix_is_cheap_but_full_fallback_is_preserved(monkeypatch):
    module = importlib.import_module("geosolver.engine.standard.exact_assembly.identify_answer")
    calls = []

    def find(**kwargs):
        calls.append(kwargs["max_total_degree"])
        return None

    monkeypatch.setattr(module, "identify_affine_pi", find)
    config = max(module.TIER_CONFIGS.values(), key=lambda c: c.max_affine_pi_total_degree)
    arguments = dict(answer_hp=mp.mpf(2), config=config, input_precision_dps=120)
    module._identify_affine_pi_result(**arguments, rational_only=True)
    module._identify_affine_pi_result(**arguments)
    assert calls == [1, config.max_affine_pi_total_degree]
    assert config.max_affine_pi_total_degree > 1


def circle_evaluator(*, extra=()):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["t"]},
                "construction": [
                    {"name": "O", "expr": "Point(0,0)"},
                    {"name": "omega", "expr": "Circle(O,2)"},
                    {"name": "P", "expr": "PointOnCircle(omega,t)"},
                    {"name": "A", "expr": "Point(-3,0)"},
                    {"name": "B", "expr": "Point(3,0)"},
                    {"name": "Q", "expr": "Intersect(Line(A,B),omega,n=1)"},
                    *extra,
                ],
                "constraints": ["Distance(P,O)-2"],
                "guards": ["t>0"],
                "answer": "Distance(P,Q)",
            }
        )
    )


def test_float_residual_is_numeric_lazy_and_reuses_constructions():
    ev = circle_evaluator()
    assert ev.evaluate_float_residual([0.173]).is_finite
    store = ev.evaluation_store
    ordinary = next(s for k, s in store.snapshots.items() if k[0] == "float")
    assert set(ordinary.completed) == {"O", "omega", "P"}
    assert isinstance(ordinary.completed["P"].x, mp.mpf)
    assert ordinary.precision_bits == 53
    assert ev.evaluate_float_hard_feasibility([0.173], include_margins=False).hard_feasible
    before = store.construction_evaluations
    assert ev.evaluate_guard([0.173])[0]
    assert ev.evaluate_float_residual([0.173]).is_finite
    assert store.construction_evaluations == before
    assert set(ordinary.completed) == {"O", "omega", "P", "A", "B", "Q"}


def test_unneeded_invalid_construction_is_still_a_hard_rejection():
    ev = circle_evaluator(extra=({"name": "bad", "expr": "Circle(O,0)"},))
    assert ev.evaluate_float_residual([0.173]).is_finite
    assert not ev.evaluate_float_hard_feasibility([0.173]).hard_feasible


def test_guard_preparation_is_not_repeated(monkeypatch):
    ev = circle_evaluator()
    from geosolver.engine.standard.evaluation import guard_penalty

    def forbidden(*_args):
        raise AssertionError("guards were compiled during evaluation")

    monkeypatch.setattr(guard_penalty, "compile_guards", forbidden)
    for t in (0.17, 0.28):
        assert ev.evaluate_float_hard_feasibility([t]).hard_feasible
        assert ev.evaluate_guard([t])[0]
    with mp.workdps(120), high_precision_mode():
        assert ev.evaluate_hp_hard_feasibility([mp.mpf("0.17")], precision=120).hard_feasible


def test_cached_constructions_replay_identical_branch_and_call_evidence():
    ev = circle_evaluator()
    with evaluation_session(ev), mp.workdps(120), high_precision_mode():
        snap = numerical_snapshot(
            ev.bundle.spec, ev.bundle.var_names, [mp.mpf("0.17")], ev.bundle.base_context
        )
        with capture_calls() as calls1, capture_selection_trace() as trace1:
            snap.for_expressions(["Distance(P,Q)"])
        before = ev.evaluation_store.construction_evaluations
        with capture_calls() as calls2, capture_selection_trace() as trace2:
            snap.for_expressions(["Distance(P,Q)"])
        assert ev.evaluation_store.construction_evaluations == before
        assert calls1 == calls2 and trace1 == trace2
        assert trace1 and trace1[0].call_site_id.startswith("Q:")


def test_cache_never_merges_close_coordinates_or_precisions():
    ev = circle_evaluator()
    with mp.workdps(180):
        first = mp.mpf("0.17")
        close = first + mp.mpf("1e-150")
    with evaluation_session(ev), high_precision_mode():
        with mp.workdps(80):
            a = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [first], ev.bundle.base_context
            )
            b = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [close], ev.bundle.base_context
            )
            assert a is not b
        with mp.workdps(180):
            c = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [first], ev.bundle.base_context
            )
            assert c is not a
            with pytest.raises(RuntimeError, match="different precision"):
                a.for_expressions(["P.x"])


def test_hp_equation_slices_can_share_a_construction_plan():
    ev = circle_evaluator()
    spec = replace(ev.bundle.spec, constraints=["P.x"], v=[0])
    child = build_ir_evaluator(
        replace(ev.bundle, spec=spec, targets=(0,)), evaluation_store=ev.evaluation_store
    )
    with mp.workdps(120), high_precision_mode():
        point = [mp.mpf("0.17")]
        assert ev.evaluate_hp_residual(point, precision=120).is_finite
        before = ev.evaluation_store.construction_evaluations
        assert child.evaluate_hp_residual(point, precision=120).is_finite
        assert ev.evaluation_store.construction_evaluations == before


def test_guard_cache_replays_inline_selector_evidence():
    ev = circle_evaluator()
    spec = replace(ev.bundle.spec, guards=["Intersect(Line(A,B),omega,n=1).x<0"])
    ev = build_ir_evaluator(replace(ev.bundle, spec=spec))
    with capture_calls() as calls1, capture_selection_trace() as trace1:
        first = ev.evaluate_guard([0.173])
    with capture_calls() as calls2, capture_selection_trace() as trace2:
        second = ev.evaluate_guard([0.173])
    assert first == second
    assert trace1 and trace1 == trace2
    assert calls1 == calls2


def test_failed_construction_is_not_retried_at_identical_coordinates():
    ev = circle_evaluator(extra=({"name": "bad", "expr": "Circle(O,0)"},))
    assert not ev.evaluate_float_hard_feasibility([0.17]).hard_feasible
    before = ev.evaluation_store.construction_evaluations
    assert not ev.evaluate_float_hard_feasibility([0.17]).hard_feasible
    assert ev.evaluation_store.construction_evaluations == before


def test_snapshot_capacity_is_bounded_and_eviction_preserves_values():
    ev = circle_evaluator()
    ev.evaluation_store.capacity = 2
    first = ev.evaluate_float_residual([0.173]).residual_vector
    for t in (0.19, 0.21, 0.23):
        ev.evaluate_float_residual([t])
    assert len(ev.evaluation_store.snapshots) == 2
    assert ev.evaluate_float_residual([0.173]).residual_vector == first


def test_constants_are_reused_at_different_points_but_not_across_precisions():
    ev = circle_evaluator()
    ev.evaluate_float_residual([0.173])
    before = ev.evaluation_store.construction_evaluations
    ev.evaluate_float_residual([0.271])
    # O and omega are constant; P depends on the coordinate.
    assert ev.evaluation_store.construction_evaluations - before == 1
    with mp.workprec(53), high_precision_mode(), evaluation_session(ev):
        first = numerical_snapshot(
            ev.bundle.spec, ev.bundle.var_names, [mp.mpf("0.173")], ev.bundle.base_context
        )
        before = ev.evaluation_store.construction_evaluations
        first.for_expressions(["P.x"])
        # Same bits, but HP and float arithmetic have separate constant caches.
        assert ev.evaluation_store.construction_evaluations - before == 3
    with mp.workdps(120), high_precision_mode():
        before = ev.evaluation_store.construction_evaluations
        assert ev.evaluate_hp_residual([mp.mpf("0.173")], precision=120).is_finite
        assert ev.evaluation_store.construction_evaluations - before == 3
        before = ev.evaluation_store.construction_evaluations
        assert ev.evaluate_hp_residual([mp.mpf("0.271")], precision=120).is_finite
        assert ev.evaluation_store.construction_evaluations - before == 1


def test_constant_cache_replays_complete_evidence_at_new_coordinates():
    ev = circle_evaluator()
    with mp.workdps(120), high_precision_mode(), evaluation_session(ev):

        def sample(t):
            snap = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [mp.mpf(t)], ev.bundle.base_context
            )
            with capture_calls() as calls, capture_selection_trace() as trace:
                snap.for_expressions(["Q.x"])
            return snap.context["Q"], calls, trace

        value1, calls1, trace1 = sample("0.173")
        before = ev.evaluation_store.construction_evaluations
        value2, calls2, trace2 = sample("0.271")
        assert ev.evaluation_store.construction_evaluations == before
        assert value1 == value2 and calls1 == calls2 and trace1 == trace2
        assert trace1


def test_cached_failure_does_not_accumulate_tracebacks():
    ev = circle_evaluator(extra=({"name": "bad", "expr": "Circle(O,0)"},))
    with mp.workdps(80), evaluation_session(ev):
        snap = numerical_snapshot(
            ev.bundle.spec, ev.bundle.var_names, [mp.mpf("0.173")], ev.bundle.base_context
        )
        lengths = []
        for _ in range(12):
            try:
                snap.for_expressions(["bad"])
            except Exception as error:
                length, traceback = 0, error.__traceback__
                while traceback is not None:
                    length += 1
                    traceback = traceback.tb_next
                lengths.append(length)
        assert len(lengths) == 12 and len(set(lengths)) == 1


def _evaluator(constraints=("x*x-1", "y-2"), guards=("x>0",)):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "bounds": [[-3, 3], [-3, 3]],
                "construction": [{"name": "P", "expr": "Point(x,y)"}],
                "constraints": list(constraints),
                "guards": list(guards),
                "answer": "x+y",
            }
        )
    )


def test_probe_reuse_keeps_attempt_identity_and_recomputes_scales():
    ev = _evaluator(("1e10*x", "y"))
    bounds = [(-3.0, 3.0), (-3.0, 3.0)]
    with candidate_attempt(0):
        a = run_initial_probe(evaluator=ev, bounds=bounds, seeds=(0,), points_per_seed=5)
    with candidate_attempt(1):
        b = run_initial_probe(evaluator=ev, bounds=bounds, seeds=(0, 1), points_per_seed=5)
    fresh = run_initial_probe(
        evaluator=_evaluator(("1e10*x", "y")), bounds=bounds, seeds=(0, 1), points_per_seed=5
    )
    assert b.metrics["reused_random_points"] == 5
    assert b.constraint_scales == fresh.constraint_scales
    assert [c.score for c in b.candidates] == [c.score for c in fresh.candidates]
    assert a.candidates[0].candidate_key != b.candidates[0].candidate_key
    assert all(c.hard_feasible is None for c in b.candidates)
