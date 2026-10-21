"""Second-audit precision, revision, deadline and process ownership regressions."""

import os
import sys
import time
from types import SimpleNamespace

import psutil
import pytest
from mpmath import mp

from geosolver import GeometryProblem, solve
from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.platform.processes import spawn_process, terminate_process_tree
from geosolver.runtime.deadline import runtime_session


def test_closed_expression_is_not_rounded_to_a_simple_neighbour():
    result = solve(
        GeometryProblem(
            id="offset", variables=[], constructions=[], conditions=[], target="sqrt(2)+1e-110"
        )
    )
    assert result.status == "solved"
    assert result.answers[0].value.minimal_polynomial != ["1", "0", "-2"]
    assert "closed_scalar_expression" in str(result.diagnostics)


def test_variable_offset_is_not_reconstructed_as_sqrt_two():
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "constraints": ["x-sqrt(2)-1e-110"],
                "answer": "x",
                "guards": ["x>0"],
            }
        )
    )
    with mp.workdps(180):
        candidate = RefinedCandidate((mp.sqrt(2),), mp.mpf("1e-110"), mp.sqrt(2), "stalled", ())
        result = assemble_exact_results(refined_candidates=(candidate,), evaluator=evaluator)
    assert "sqrt(2)" not in result.answer_values


def test_revised_coordinates_and_answer_are_kept_together():
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "constraints": ["x-2"],
                "answer": "x+1",
            }
        )
    )
    with mp.workdps(180):
        old = RefinedCandidate(
            (mp.mpf(2) + mp.mpf("1e-40"),),
            mp.mpf("1e-40"),
            mp.mpf(999),
            "stalled",
            (),
            candidate_id=41,
        )
        result = assemble_exact_results(refined_candidates=(old,), evaluator=evaluator)
        candidate = result.accepted_candidates[0]
        assert candidate.revision >= 1 and candidate.x_hp == (mp.mpf(2),)
        assert candidate.answer_hp == 3 and result.answer_values == ("3",)
        cached = assemble_exact_results(refined_candidates=(old,), evaluator=evaluator)
        assert cached.candidate_records[0] is result.candidate_records[0]


@pytest.mark.parametrize("power", [-100, 100])
def test_large_and_small_algebraic_values(power):
    from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer

    with mp.workdps(350):
        result = identify_answer(
            answer_hp=mp.sqrt(2) * mp.power(10, power), tier="strict", input_precision_dps=250
        )
    assert result.exact_status == "identified" and result.descriptor is not None


def test_zero_and_expired_scipy_budgets_never_enter_optimizer(monkeypatch):
    from geosolver.engine.standard.search.nomad_config import NomadConfig
    from geosolver.engine.standard.search.scipy_multistart_backend import ScipyMultistartBackend

    def forbidden(*args, **kwargs):
        pytest.fail("optimizer entered with no time budget")

    monkeypatch.setattr("scipy.optimize.least_squares", forbidden)
    for budget, deadline in ((0, None), (10, time.monotonic() - 1)):
        with runtime_session(deadline):
            result = ScipyMultistartBackend(
                NomadConfig(max_time_sec=budget, max_bb_eval=10), ([0],)
            ).run_search(bundle=SimpleNamespace(), evaluator=SimpleNamespace(), bounds=[(-1, 1)])
        assert result.evaluation_count == 0


@pytest.mark.skipif(os.name != "posix", reason="POSIX owned process group")
def test_descendants_are_reaped_after_parent_has_already_exited(tmp_path):
    code = (
        "import subprocess,sys; "
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);"
        "print(p.pid,flush=True)"
    )
    parent = spawn_process([sys.executable, "-c", code], cwd=tmp_path, env=os.environ.copy())
    child = psutil.Process(int(parent.stdout.readline()))
    parent.wait(timeout=5)
    try:
        terminate_process_tree(parent, grace_seconds=0.1)
        _, alive = psutil.wait_procs([child], timeout=2)
        assert not [p for p in alive if p.status() != psutil.STATUS_ZOMBIE]
    finally:
        if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
            child.kill()


def test_symbolic_worker_timeout_is_bounded_and_reaped(monkeypatch):
    from geosolver.runtime import symbolic
    from geosolver.runtime.symbolic import SymbolicClient

    original = symbolic.spawn_process

    def hanging(command, **kwargs):
        return original(
            [sys.executable, "-c", "import sys,time;sys.stdin.readline();time.sleep(30)"], **kwargs
        )

    monkeypatch.setattr(symbolic, "spawn_process", hanging)
    client = SymbolicClient(time.monotonic() + 0.3)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        client.call("identify", {})
    assert time.monotonic() - started < 2
    assert client.process.poll() is not None


def test_completed_answer_survives_a_later_symbolic_timeout(monkeypatch):
    import geosolver.engine.standard.orchestration.assemble_exact_results as module

    original = module.identify_answer
    calls = []

    def identify(**kwargs):
        calls.append(kwargs["answer_hp"])
        if len(calls) == 2:
            raise TimeoutError("later candidate")
        return original(**kwargs)

    monkeypatch.setattr(module, "identify_answer", identify)
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {"task": "solve", "variables": {"names": ["x"]}, "constraints": [], "answer": "x"}
        )
    )
    with mp.workdps(180):
        candidates = tuple(
            RefinedCandidate((mp.mpf(i),), mp.mpf(0), mp.mpf(i), "stalled", (), candidate_id=i)
            for i in (1, 2)
        )
        result = assemble_exact_results(refined_candidates=candidates, evaluator=evaluator)
    assert result.answer_values == ("1",)
    assert result.exact_results[0].descriptor is not None
    assert "deadline_during_exactification" in result.rejection_tags


def test_windows_job_releases_work_only_after_confirmed_membership(monkeypatch):
    from geosolver.platform import windows_job

    events = []

    class Kernel:
        def CreateJobObjectW(self, *args):
            return 1

        def CreateEventW(self, *args):
            return 2

        def SetInformationJobObject(self, *args):
            return True

        def OpenProcess(self, flags, *args):
            assert flags & 0x0400
            return 3

        def AssignProcessToJobObject(self, *args):
            events.append("assign")
            return True

        def IsProcessInJob(self, process, job, assigned):
            events.append("confirm")
            assigned._obj.value = True
            return True

        def SetEvent(self, *args):
            events.append("release")
            return True

        def CloseHandle(self, *args):
            pass

    monkeypatch.setattr(windows_job, "_kernel", Kernel)
    job = windows_job.WindowsJob()
    job.assign_and_release(123)
    job.close()
    assert events == ["assign", "confirm", "release"]


def test_inner_deadline_returns_completed_no_answer(monkeypatch):
    from geosolver.runtime import worker
    from geosolver.runtime.protocol import WorkerRequest

    def timeout(*args, **kwargs):
        raise TimeoutError("inner deadline")

    monkeypatch.setattr(worker, "run_external_pipeline", timeout)
    request = WorkerRequest(engine_document={}, deadline_monotonic=time.monotonic() + 5)
    artifact = worker.execute(request)
    assert artifact.status == "completed" and artifact.answers == []
    assert artifact.termination_reason == "time_limit_reached"


def test_candidate_artifact_preserves_precision_outside_work_context():
    from geosolver.runtime.worker import _json_value

    with mp.workdps(500):
        value = mp.sqrt(2) + mp.mpf("1e-400")
    with mp.workdps(15):
        saved = _json_value({"coordinate": value})
    with mp.workdps(500):
        assert mp.mpf(saved["coordinate"]) == value
