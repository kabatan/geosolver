from __future__ import annotations

import platform
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver import GeometryProblem, SolveOptions, solve
from geosolver.application.service import problem_hash
from geosolver.engine import EngineCancelled, EngineFailure
from geosolver.exact import assemble_exact_answers
from geosolver.runtime.protocol import WorkerArtifact
from geosolver.runtime.worker import execute


def problem_with_value(value: int | float | str = 1) -> GeometryProblem:
    return GeometryProblem(
        id="positive-dimensional",
        variables=["x"],
        constructions=[],
        conditions=[{"left": "x", "operator": "=", "right": value}],
        target="x",
    )


def options() -> SolveOptions:
    return SolveOptions(time_limit_seconds=180, cores=1)


def test_positive_dimensional_search_closure_finds_x_equals_one() -> None:
    result = solve(problem_with_value(), options())

    assert result.status == "solved"
    assert result.completeness == "unknown"
    assert result.answers[0].kind == "algebraic"
    assert result.answers[0].minimal_polynomial == ["1", "-1"]


@pytest.mark.parametrize("code", ["artifact_missing", "artifact_invalid", "worker_exception"])
def test_worker_protocol_failures_are_never_reported_as_no_answer(code: str) -> None:
    class FailedRunner:
        def run(self, *args: object, **kwargs: object) -> object:
            raise EngineFailure(code, "worker failed")

    result = solve(problem_with_value(), options(), runner=FailedRunner())  # type: ignore[arg-type]

    assert result.status == "engine_error"
    assert result.error is not None and result.error.code == code


def test_no_progress_is_an_immediate_engine_error() -> None:
    class NoProgressRunner:
        calls = 0

        def run(self, *args: object, **kwargs: object) -> object:
            self.calls += 1
            raise EngineFailure("no_progress", "checkpoint did not advance")

    runner = NoProgressRunner()
    result = solve(problem_with_value(), options(), runner=runner)  # type: ignore[arg-type]

    assert runner.calls == 1
    assert result.status == "engine_error"
    assert result.termination_reason == "no_progress"


def test_cancelling_one_session_does_not_cancel_another() -> None:
    class SessionRunner:
        def __init__(self, cancelled: bool) -> None:
            self.cancelled = cancelled

        def run(self, *args: object, **kwargs: object) -> SimpleNamespace:
            if self.cancelled:
                raise EngineCancelled
            return SimpleNamespace(
                artifact=WorkerArtifact(
                    status="completed", solver_status="success", exact_candidates=["1"]
                )
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        cancelled = executor.submit(
            solve, problem_with_value(), options(), runner=SessionRunner(True)
        )
        completed = executor.submit(
            solve, problem_with_value(), options(), runner=SessionRunner(False)
        )

    assert cancelled.result().status == "cancelled"
    assert completed.result().status == "solved"


def test_json_numbers_reject_boolean_and_preserve_int_float_identity() -> None:
    with pytest.raises(ValueError):
        problem_with_value(True)  # type: ignore[arg-type]

    integer = problem_with_value(1)
    floating = problem_with_value(1.0)
    assert integer.engine_document()["constraints"][0]["value"] == 1
    assert type(integer.engine_document()["constraints"][0]["value"]) is int
    assert type(floating.engine_document()["constraints"][0]["value"]) is float
    assert problem_hash(integer) != problem_hash(floating)


def test_exactification_precedes_deduplication() -> None:
    close_distinct = f"1 + 1/{10**30}"
    answers, warnings = assemble_exact_answers(["1", close_distinct, "sqrt(2)", "2**(1/2)"])

    assert not warnings
    assert len(answers) == 3
    assert len({answer.canonical_key() for answer in answers}) == 3


def test_worker_restores_global_mpmath_precision(monkeypatch: pytest.MonkeyPatch) -> None:
    original = mp.dps

    def precision_leaking_solver(*args: object, **kwargs: object) -> SimpleNamespace:
        mp.dps = 333
        return SimpleNamespace(
            status=SimpleNamespace(name="SUCCESS"),
            metadata={"exact_answer_candidates": ["1"]},
            exact_answer=None,
            answer_values=[1],
        )

    monkeypatch.setattr("geosolver.runtime.worker.run_ir", precision_leaking_solver)
    request = SimpleNamespace(engine_document={}, prefer_fast=True, seed=0)
    artifact = execute(request)  # type: ignore[arg-type]

    assert artifact.status == "completed"
    assert mp.dps == original


def test_reference_engine_is_not_silently_replaced_off_linux(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    result = solve(problem_with_value(), SolveOptions(engine="reference"))

    assert result.status == "unsupported_platform"
    assert result.engine.name == "reference"


@pytest.mark.skipif(platform.system() != "Linux", reason="reference is Linux-only")
def test_frozen_smoke_descriptors_match_standard_and_reference() -> None:
    corpus = [
        problem_with_value(),
        GeometryProblem(
            id="right-angle",
            variables=[],
            constructions=[
                {"name": "A", "expression": "Point(0, 0)"},
                {"name": "B", "expression": "Point(1, 0)"},
                {"name": "C", "expression": "Point(0, 1)"},
            ],
            conditions=[],
            target="Angle(B, A, C)",
        ),
    ]
    for problem in corpus:
        standard = solve(problem, options())
        reference = solve(problem, SolveOptions(engine="reference"))
        assert standard.status == reference.status == "solved"
        assert [answer.canonical_key() for answer in standard.answers] == [
            answer.canonical_key() for answer in reference.answers
        ]
