"""Regression fixtures for reuse without weakening numerical verification."""

import importlib
from collections import OrderedDict
from dataclasses import replace
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.selection_trace import (
    capture_selection_trace,
    use_selection_symbol,
)
from geosolver.engine.standard.evaluation.snapshots import evaluation_session, numerical_snapshot
from geosolver.engine.standard.evaluation.verification_domains import DomainVerifier, _combine
from geosolver.engine.standard.evaluation.verification_system import sample_equations
from geosolver.engine.standard.precision.type_guards.ensure_no_float import (
    ValidatedHPContext,
    ensure_no_float,
)
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.evaluation_trace import capture_calls
from geosolver.runtime.deadline import deadline_scope


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
