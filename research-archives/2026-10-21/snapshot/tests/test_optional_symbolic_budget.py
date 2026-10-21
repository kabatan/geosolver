"""Optional discovery cannot consume the solve deadline or poison later exact work."""

import json
import sys
import time

import pytest
from mpmath import mp

from geosolver.runtime import symbolic
from geosolver.runtime.deadline import deadline_scope
from geosolver.runtime.symbolic import OptionalSymbolicTimeout, SymbolicClient


def first_worker_hangs(monkeypatch):
    original = symbolic.spawn_process
    children = []

    def spawn(command, **kwargs):
        if not children:
            command = [sys.executable, "-c", "import sys,time;sys.stdin.readline();time.sleep(30)"]
        child = original(command, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(symbolic, "spawn_process", spawn)
    return children


@pytest.mark.parametrize("transient_cleanup_failure", [False, True])
def test_optional_timeout_reaps_old_worker_and_restarts_normalize_and_identify(
    monkeypatch, transient_cleanup_failure
):
    children = first_worker_hangs(monkeypatch)
    original_terminate = symbolic.terminate_process_tree
    calls = []

    def terminate(child, **kwargs):
        calls.append(child)
        if transient_cleanup_failure and len(calls) == 1:
            raise OSError("one transient cleanup failure")
        return original_terminate(child, **kwargs)

    monkeypatch.setattr(symbolic, "terminate_process_tree", terminate)
    client = SymbolicClient(time.monotonic() + 5)
    try:
        started = time.monotonic()
        with pytest.raises(OptionalSymbolicTimeout):
            client.call("algebraic_branches", {}, timeout_seconds=0.05)
        assert time.monotonic() - started < 2
        assert children[0].poll() is not None
        assert children[0].stdin.closed and children[0].stdout.closed
        assert not client.closed and client.process is None
        assert client.call("normalize", [["2", "0"]]) == [["2", 1]]
        result = client.call(
            "identify",
            {"value": tuple(map(int, mp.mpf(7)._mpf_)), "precision": 80, "closed_source": "7"},
        )
        assert result["exact_status"] == "identified"
        assert result["selected_exact_value"] == "7"
        assert len(children) == 2 and client.process is children[1]
        assert client.output.empty()
    finally:
        client.close()
    assert all(child.poll() is not None for child in children)


def test_optional_limit_cannot_hide_earlier_active_global_deadline(monkeypatch):
    children = first_worker_hangs(monkeypatch)
    client = SymbolicClient(time.monotonic() + 5)
    with deadline_scope(time.monotonic() + 0.05), pytest.raises(TimeoutError) as error:
        client.call("algebraic_branches", {}, timeout_seconds=1)
    assert not isinstance(error.value, OptionalSymbolicTimeout)
    assert client.closed
    assert children[0].poll() is not None


def test_global_deadline_expiring_during_optional_cleanup_still_raises(monkeypatch):
    children = first_worker_hangs(monkeypatch)
    client = SymbolicClient(time.monotonic() + 0.1)
    original_close = client.close

    def slow_cleanup():
        original_close()
        time.sleep(0.12)

    monkeypatch.setattr(client, "close", slow_cleanup)
    with pytest.raises(TimeoutError) as error:
        client.call("algebraic_branches", {}, timeout_seconds=0.02)
    assert not isinstance(error.value, OptionalSymbolicTimeout)
    assert client.closed and children[0].poll() is not None


def test_old_drain_sentinel_stays_in_old_queue_after_restart(monkeypatch):
    first_worker_hangs(monkeypatch)
    client = SymbolicClient(time.monotonic() + 5)
    try:
        # Keep the old queue reference; late output/sentinels must not cross into
        # the replacement worker even if its drain thread finishes afterwards.
        old_output = client.output
        with pytest.raises(OptionalSymbolicTimeout):
            client.call("algebraic_branches", {}, timeout_seconds=0.05)
        assert client.output is not old_output
        old_output.put(json.dumps({"result": "stale"}))
        old_output.put(None)
        assert client.call("normalize", [["3", "0"]]) == [["3", 1]]
    finally:
        client.close()


@pytest.mark.parametrize("optional", [False, True])
def test_algebraic_search_falls_back_only_for_optional_limit(monkeypatch, optional):
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.search.algebraic_branches import search_algebraic_branches

    bundle = load_problem_bundle(
        {
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": ["x*x-1"],
            "guards": [],
            "answer": "x",
        }
    )

    def failed(*args, **kwargs):
        assert kwargs["timeout_seconds"] == 1.5
        raise OptionalSymbolicTimeout() if optional else TimeoutError("solve deadline")

    monkeypatch.setattr(symbolic, "request", failed)
    if optional:
        assert (
            search_algebraic_branches(bundle=bundle, evaluator=build_ir_evaluator(bundle)) is None
        )
    else:
        with pytest.raises(TimeoutError):
            search_algebraic_branches(bundle=bundle, evaluator=build_ir_evaluator(bundle))
